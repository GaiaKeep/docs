!!! info "Status: Current (software path)"
    How containers map to tape; items marked [HW] still need a real drive.

# GaiaKeep tape: on-media format v1, command set, crash rules

**PRIVATE (B4, owner decision pending): not part of the public docs sync.** This is the format a volume
written by `io.cresco.gfs.tape.TapeBinding` has (OUT-16, the software path), the SCSI command set the
production path may send, how sense is classified, and what every crash leaves. Nothing here was
verified on a real LTO drive: items that need one are marked **[HW]**.

## 1. Keys (K_media)

Every tape key is derived from K_media (`tape_media_key_file` / `_env`; a plain value in dev mode only;
per tape node by default, escrowed with KeySplit and attested outside dev mode, S4/S5).

| Key | Derivation | Used for |
|---|---|---|
| packRoot | HKDF-SHA-384(K_media, "gfs/tape/pack-root/v1") | pack container metadata and TAG_ONLY record tags |
| kcvKey | HKDF-SHA-384(K_media, "gfs/tape/kcv-key/v1") | kcv(volume_id) = HMAC-SHA-384(kcvKey, "gfs/tape/kcv/v1" ‖ volume_id)[0:8] |
| catalogRoot | HKDF-SHA-384(K_media, "gfs/tape/catalog/v1") | the catalogue's CoreLog MAC chain, and the footer-file MAC key ("gfs/tape/footer-mac/v1") |
| label / tail / ckpt | CounterAead(K_media, purpose, volume_id or session_id) | the sealed parts below |

CounterAead: AES-256-GCM, key = Kdf.derive(K_media, purpose, id), IV = counter[8] ‖ kind[4]. Counters:
a label is counter 0 once per (random) volume id; a tail is its ordinal under its session's key (a
session id is 16 DRBG bytes, journaled as `tsess` before first use); a checkpoint is its seq under the
volume's key, **reserved in the journal (`tckres`) before the counter seals anything**, so a crash
between the medium and the journal can never reuse (key, IV) with other content. One CounterAead per
(purpose, id) lives in the process and refuses a second, different seal under a used (counter, kind).

## 2. Layout (single partition 0, variable-block mode, compression OFF, drive encryption verified OFF)

All integers big-endian; every cleartext structure carries a CRC-32; record size R = 1 MiB = one pack
block (B5; `tape_record_bytes` must equal `1 << pack log2Block` or the node refuses to start).

```
FILE 0     LABEL       one record of R, then FM
           "GFSVOL01" fmt u16 | volume_id[16] | R u32 | kcv[8] | crc32
           | u32 n | seal_label(volume_id; ctr 0, kind 1; aad = the cleartext)
               {volume_id[16], pool_token[16], worm u8, label_epoch u64} | DRBG fill to R
FILE k     CONTAINER   block_count pack blocks (one per record, verbatim), then ONE TAIL record, then FM
           "GFSTEND1" fmt u16 | kind u8 (1 container, 3 aborted) | flags u8 | ordinal u32 | session_id[16]
           | block_count u64 | crc32
           | u32 n | seal_tail(session_id; ctr = ordinal, kind 1; aad = the cleartext)
               {volume_id[16], ordinal u32, container_id[16], block_count u64, sha384(last block)[48],
                sha384(footer entries)[48], prev_tail_tag[16]} | DRBG fill to R
CHECKPOINT one or more records of R, then FM (at each quarter of capacity and at volume close)
           "GFSCKPT1" fmt u16 | seq u64 | records u32 | crc32
           | u32 n | seal_ckpt(volume_id; ctr = seq, kind 2; aad = the cleartext)
               {volume_id, seq, prev_checkpoint_tag, containers[{ordinal, file_no, first_lbn, block_count,
                container_id, tail_tag}], retain floors of extents on this volume [{tag, until}],
                tags that died on this volume since the previous checkpoint} | DRBG fill
```

- Extent payloads are the engine's AEAD ciphertext, copied verbatim: the tape layer never encrypts or
  re-encrypts a payload (D4). Every record is written TAG_ONLY with tag = PackFormat.tag(packRoot,
  extentId): no extent id appears on the medium, sealed or not.
- A structure's tag is the GCM tag of its sealed part: tails chain by `prev_tail_tag`, checkpoints by
  `prev_checkpoint_tag`.
- MAM writes: only 0x0800-0x0802 (constants), 0x0803 = base32(volume_id) and 0x080C = {volume_id,
  checkpoint lbn, seq, fmt, write epoch}. Anything else is refused by the allowlist before a CDB is built.
- Footer files (node-local, `<tape_catalog_dir>/footers/<container_id>.ftr`): "GFSFTR01" | container_id |
  n | entries {tag 32, seq, offset, length, sha384 48} | HMAC-SHA-384 under the footer key. Written
  (temp, fsync, rename, directory fsync) before `tcont(WRITTEN)`; a bad MAC refuses start.

### Disclosure residual (declared)

Magics, format versions, random ids (volume, session, container), ordinals, block counts, file counts,
pack cleartext block headers (container id, index, fill, crc), the DRBG fill, and drive-maintained MAM
counters. No timestamps, names, extent ids or plaintext-derived values. Container lengths are exact to
R until pack R7 (padding to `tape_container_size_class_bytes`) lands.

## 3. The node's catalogue (TapeCatalog)

A CoreLog of its own (fsync, MAC chain under catalogRoot, torn tail truncated, anything else refused);
entries are batches of tape-only ops; **no core Delta**. Ops (unknown ops fail closed, before anything is
journaled): `tvol`, `tsess`, `tcont`, `teod`, `torphan`, `tseal`, `tdead(tag, reason[, dead_before])`,
`tdoom(container, tag)`, `tretain`, `tckpt`, `tckres`, `thold`, `thold_clear`.

- `tdead` kills every copy of a tag in containers journaled before it; a copy written later (a re-archive
  of the same content-derived extent) is live again. `tdoom` kills the copy in one in-flight container
  (a reclaim or abandon while the write was open or queued): it lands dead and is never reported present.
- The extent cap (`tape_catalog_max_extents`) is enforced before a `tcont(VERIFIED)` is journaled, never
  in apply: a node whose log is past the cap still starts.
- The extent index is memory only (open addressing on tag[0:8], every hit checked against the full tag in
  the authenticated footer): about 24 B an extent.

## 4. Write path and crash rules

1. append: id checked, SHA-256 verified, spool bound (`tape_spool_max_bytes`), domain-pure containers.
2. seal: finish the container, fsync, rename `.part` to `.pack`, journal `tseal(QUEUED)`, return QUEUED
   (deferredWrites). A repeated seal of the same tid answers from the journal.
3. A write session (up to `tape_write_sessions`, each on its own drive and volume) takes the OPEN volume
   no other session writes, else labels a blank pool cartridge: `tvol(SUSPECT)` is journaled **before**
   the label is written, and the label is read back and checked before the volume becomes OPEN (a garbled
   label would make every container behind it unreadable).
4. Session start: `tsess(OPEN)` journaled and fsynced, then the MAM epoch. SPACE to EOD + READ POSITION
   against the catalogue EOD: equal, append; past it with an OPEN session of ours, `torphan` then
   WRITE FILEMARKS(1, immed=0) to terminate the torn file, then append; past it otherwise, SUSPECT;
   before it, SUSPECT and an integrity alarm. The node never writes anywhere but the medium's EOD.
5. Per container: records, tail, WRITE FILEMARKS(1, immed=0) (the barrier), READ POSITION must be
   first + blocks + 2, footer file, `tcont(WRITTEN)`; then VERIFY FULL (LOCATE, read every record, SHA-384
   against the spool, pack trailer and footer under packRoot, the tail under CounterAead, a filemark after
   it); then one append of `tcont(VERIFIED)` + `tseal(DONE)`; only then is the ticket DONE (the extents
   become durable to the core) and the spool deleted.
6. Early warning or end of medium: FM, `tcont(ABORTED)`, a final checkpoint inside the reserve, volume
   FULL, the same spool bytes re-driven to a new volume. Medium error or data protect: volume SUSPECT,
   re-driven up to `tape_write_attempts`, then `tseal(FAILED)`.
7. **A drive that dies** (HARDWARE ERROR 4/xx): the drive is taken out of service (an operator calls
   `driveRepaired`), the volume is not blamed, its session stays OPEN (rule 4 then orphans whatever the
   dead drive left past EOD), and the work resumes on another drive (writes re-drive from the spool;
   reads re-queue their undelivered extents).
8. Startup: replay (fail closed), footers verified; `tcont(WRITTEN)` becomes ABORTED and its spool is
   re-driven; `.part` spools, `.pack` spools without a live `tseal`, and verify scratch are deleted.

## 5. Read path

Admission refuses at once (absent, dead, SUSPECT/FOREIGN/RETIRED volume, a hold, or the modelled p95 past
the deadline). Per volume, a free drive (one already holding it first; else the earliest deadline, then
the most demand, after `tape_read_coalesce_ms`) reads the wanted extents in ascending position: one LOCATE
per container reached, extents sharing a record served from the one read, small gaps streamed through
**inside one container only** (never across a tail and filemark), each extent's SHA-384 checked against
the footer and moved whole into the sink. A running read stops at the next extent boundary on cancel.
Faults (B6): MEDIUM_ERROR with native sense is retried once, then that extent fails and the job goes on;
no native sense, no retry; UNIT ATTENTION / POSITION UNKNOWN re-find the position; a negative ILI residue is
FORMAT_VIOLATION (volume SUSPECT). A read failure alone never condemns a copy; a VERIFY ticket reports
matched (delivered), read-back-wrong (failed: positive evidence) and unreadable (neither: unknown).

## 6. SCSI command set (production path: raw sg; B2 transport not built)

| Command | Opcode | Restriction |
|---|---|---|
| TEST UNIT READY / REWIND / REQUEST SENSE / READ BLOCK LIMITS | 00 / 01 / 03 / 05 | |
| INITIALIZE ELEMENT STATUS / READ(6) / WRITE(6) / WRITE FILEMARKS(6) | 07 / 08 / 0A / 10 | |
| INQUIRY / LOAD UNLOAD / PREVENT ALLOW MEDIUM REMOVAL | 12 / 1B / 1E | |
| READ POSITION | 34 | service action 06 (long form) only |
| REPORT DENSITY SUPPORT / LOG SENSE | 44 / 4D | |
| MODE SELECT(10) | 55 | block descriptor and page 0Fh (data compression) only |
| MODE SENSE(10) / READ ATTRIBUTE | 5A / 8C | |
| WRITE ATTRIBUTE | 8D | ids 0800, 0801, 0802, 0803, 080C only |
| SPACE(16) / LOCATE(16) | 91 / 92 | |
| SECURITY PROTOCOL IN | A2 | protocol 20h only |
| MAINTENANCE IN | A3 | service action 0C only |
| MOVE MEDIUM / READ ELEMENT STATUS | A5 / B8 | |

Everything else is refused before the transport, in particular ERASE (19), FORMAT MEDIUM (04), SET
CAPACITY (0B), WRITE BUFFER (3B) and PERSISTENT RESERVE IN/OUT (5E/5F). Golden vectors: READ(6) 1 MiB =
`08 00 10 00 00 00`; WRITE FILEMARKS(6) immed=0, 1 = `10 00 00 00 01 00`; REWIND = `01 00 00 00 00 00`.
Timeouts: LOCATE/SPACE 3 h, LOAD/UNLOAD/REWIND 20 min, READ/WRITE 30 min, others 60 s, replaced by the
drive's own (A3/0C with RCTD) **[HW]**.

Sense classification (fixed 70/71 and descriptor 72/73 formats; every row to be checked against SSC-5,
SPC-5, SMC-3 and a real drive **[HW]**): 1/xx RECOVERED; 0/00/01 FILEMARK; 0/00/02 EARLY_WARNING;
D/00/02 EOM; 0/00/04 BOP; 0/00/05 and 8/00/05 EOD; 3/3B POSITION_UNKNOWN; other 3/xx MEDIUM_ERROR;
7/27/00 DATA_PROTECT; 7/30/0C WORM_OVERWRITE; 6/28/00, 6/29/xx UNIT_ATTENTION; 2/04/01 NOT_READY;
2/3A/00 NO_MEDIUM; 4/xx DRIVE_FAULT; 0/00/17 CLEANING_REQUIRED; 5/xx ILLEGAL_REQUEST; B/xx
TRANSPORT_RETRYABLE; anything else UNKNOWN (no retry).

### Transport options (B2, owner decision)

- **FFM SG_IO** (Rec): JDK 22+ Foreign Function & Memory, no dependency; CI is on JDK 21 today.
- A separate Apache-2.0 helper process with its own allowlist.
- **The st driver is not the production path**: its ioctls hide native sense (B6 needs it). It is built
  as test infrastructure only (`tape-st`, dev mode): records through /dev/nstN, positioning through mt,
  READ POSITION / MAM / capacity / encryption through this node's own SCSI command set over `sg_raw`,
  the changer through mtx. It drives mhVTL (`eval/tape/mhvtl`, docs/TAPE-SIMULATION.md). st's own
  behaviours it absorbs: one open at a time (the record stream is closed before any mt or sg_raw), a
  filemark written by st when a write stream closes (used as the container's barrier), ENOSPC at early
  warning (treated as end of medium: the record was not written, the container is re-driven).

## 7. Owner flags and hardware

D1 WORM classes, D2 volume grouping (+ domain-pure containers), D3 fragment-granular repack, D4 no
re-encryption (adopted), S1 counter-IV metadata (adopted), S2 leases (adopted), B3 reference reader
(adopted: blocking gate, reader not yet written), B4 this document private, M1/M2 timings and session
sizes MODELLED (need a real LTO-10), B5 R = 1 MiB and quarter checkpoints, B6 retry only on native sense,
B7 single host (MAM epoch fencing advisory, PR off), B8 test rig = mhVTL in a Lima VM (owner direction
2026-09-30). Needs hardware: a native SG transport, maximum block size, MAM support (0x080C writability),
WORM detection bits, EW/EOM sense behaviour, the cost and power safety of WRITE FILEMARKS immed=0,
locate/reposition timings, TapeAlert and cleaning, the changer element map, A3/0C timeouts, the
commissioning disclosure lint on a scratch cartridge.
