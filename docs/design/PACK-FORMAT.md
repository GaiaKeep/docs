!!! success "Status: Current"
    The storage-node container format: fixed blocks, sealed records and repack (shipped in 1.3, 2026-10-01).

# The GaiaKeep pack container, format version 1

*2026-09-26. Branch `wip/pack`. Implements OUT-15 (pack blocks into large files) and the on-media
format half of OUT-16 (tape parcels). Java: `io.cresco.gfs.core.pack`. Independent reference
reader: `eval/pack_reader.py`, written from this document alone. Golden containers:
`src/test/resources/pack/golden-v1-*.gkp`, each with a `.json` manifest.*

This document is normative for §2 to §9 and §17. Everything a reader needs is in those sections; a
reader must not need the Java source. Sections §10 to §16 give the rationale, the disclosure
inventory, the tape mapping, repack, the answer to SPECIFICATION §8.4, the integration plan and the
open questions. §18 reports measurements.

---

## 1. What it is

One on-media format for every medium: a **container** is a file (on disk or NVMe) or a tape file
(one parcel between filemarks) that holds many **extents**, the sealed blocks the storage core
stores today (`FsBinding`/`BlockStore` keep each as its own file plus a `.meta` sidecar). The
container does not re-encrypt extent bytes: they are already AES-256-GCM ciphertext produced by
`BlockCodec`. It does seal its own metadata, because the design record requires it (SPECIFICATION
§13.1: nothing outside a seal may be a function of plaintext, "not names, not real lengths, not
record counts, not timestamps finer than a day").

Properties:

- **Self-describing and versioned.** Every block carries magic, version, block size and container id.
- **Append-only while open, sealed once closed.** No byte is ever rewritten, except that a disk
  writer may rewrite the 64-byte header of its current, partially written tail block (§7.3). A tape
  writer never rewrites anything.
- **Every record is independently verifiable** under the container key: its header is AES-GCM
  sealed and its payload has a SHA-384 in that header.
- **Every block is independently checkable without a key**: a CRC-32 in its cleartext header.
- **The index is at the end.** A trailer in the last 256 bytes locates a footer that indexes every
  record; the footer ends where the trailer begins. Periodic checkpoints repeat the index in the
  stream, so a container whose footer never landed is recovered by scanning.
- **A holder without the key sees block headers and pseudorandom bytes**: no identifiers, no record
  boundaries, no lengths, no counts, no times (§10).

---

## 2. Conventions

- All integers are **unsigned, big-endian**. `u8`, `u16`, `u32`, `u64` are 1, 2, 4, 8 bytes.
- Offsets and lengths are in bytes. A "hex" value is lower-case hexadecimal.
- `‖` is concatenation. `"ABCD"` is the ASCII bytes of the string, no terminator.
- `align16(x)` is `x` rounded up to a multiple of 16.
- **SHA-384**: FIPS 180-4. **HMAC-SHA-384**: RFC 2104 with SHA-384.
- **HKDF(ikm, info, L)**: RFC 5869 with SHA-384 and **no salt** (the RFC's default: a salt of 48
  zero bytes). Output length `L` bytes.
- **info(p1, p2, ...)**: for each part in order, `u32 length(p) ‖ p`, concatenated. A string part is
  its UTF-8 bytes; a byte-string part is used as is. Example: `info("gfs/pack/v1/meta")` is
  `00000010 ‖ "gfs/pack/v1/meta"`.
- **AES-256-GCM**: NIST SP 800-38D, 96-bit IV, 128-bit tag. A sealed value is the ciphertext
  followed by its 16-byte tag (`len(sealed) = len(plaintext) + 16`).
- **CRC-32**: the ISO-HDLC CRC-32 of zlib, PNG and Ethernet (reflected polynomial 0xEDB88320, initial
  value and final XOR 0xFFFFFFFF); Java `java.util.zip.CRC32`, Python `zlib.crc32`.
- A **container id** (`cid`) is 16 random bytes. It is never reused under one pack root (§7.1).

---

## 3. Keys

The caller supplies a 32-byte **pack root** `K_root`. Integration derives it from the core master
key (§15.7); this format does not care where it comes from. From it and the container id:

| Key | Derivation | Length | Used for |
|---|---|---|---|
| `K_c` | `HKDF(K_root, info("gfs/pack/v1/container", cid), 32)` | 32 | derives the four below |
| `K_meta` | `HKDF(K_c, info("gfs/pack/v1/meta"), 32)` | 32 | AES-256-GCM: record headers, metadata bodies, trailer |
| `K_mac` | `HKDF(K_c, info("gfs/pack/v1/mac"), 48)` | 48 | HMAC-SHA-384: the trailer MAC |
| `K_sync` | `HKDF(K_c, info("gfs/pack/v1/sync"), 48)` | 48 | HMAC-SHA-384: record sync words |
| `K_tag` | `HKDF(K_root, info("gfs/pack/v1/tag"), 48)` | 48 | HMAC-SHA-384: extent tags |

`K_tag` alone depends only on the root, so an extent keeps the same tag in every container under that
root, and repack can move a record whose id it does not know. Everything else is per container.

**Tag** of an extent id: `tag(id) = HMAC-SHA-384(K_tag, UTF-8(id))[0:32]`.

**Sync word** of a record: `sync(seq) = HMAC-SHA-384(K_sync, u64 seq)[0:8]`.

**GCM IVs** are a counter pair, never random (SPECIFICATION §20 applied to container metadata, OPEN-QUESTIONS S1):
`IV = u64 seq ‖ u32 domain`, with domain 1 for a record header, 2 for a metadata body, 3 for the
trailer (whose seq is `0xFFFFFFFFFFFFFFFF`). Each `(seq, domain)` is used once per container, and
each container has its own `K_meta`, so no IV is ever reused under a key.

**Test vectors** (`K_root = 000102...1f`, `cid = a0a1...af`, the growing golden container):

```
info("gfs/pack/v1/container", cid) = 000000156766732f7061636b2f76312f636f6e7461696e657200000010a0a1a2a3a4a5a6a7a8a9aaabacadaeaf
K_c    = c966c31ddfc919d596c60b97849caee7bc915ce9f4c5999111239fe96470c896
K_meta = b75b9a25d0baad0614bcb5fc122baa4b5d13980135018ad504eaf038cb4219c5
K_mac  = e7f4e64b82d03a90ab324f91aaf6d3df1289e7119847e6fe45925f1d0a707e6612ed9c83e4aa35742e04f6d69b48f295
K_sync = 30597a2b2d861256f460b400efa640fb25e001d7807342fc5c97e339bf8d8364027154183052540c2e2713ce6c8fa350
K_tag  = e038bfd0a00c3a17b9883f80c731b1136142e35040072c78872f9344ab819e6f7a7e9438d1b6d7100cca8b0a92fd3646
tag("b_none_objid-0") = 9887f09f2e31a12616a6ea5a062a37c5d4b3f4072fff2801e0aa66e2186dec4f
sync(0) = 9b838e126ffc1c83   sync(1) = e3897543dfe69ff0   sync(2) = cf6ee83139a8ad2e
R_0     = 4de79d1499f5cf9ac10635185977bf48d8e99d222b6525f973b7d1ca111366dc919eb4de8a677e4e3ab206fa36ef327b
IV, header of seq 1 = 000000000000000100000001   IV, body of seq 4 = 000000000000000400000002
IV, trailer         = ffffffffffffffff00000003
```

---

## 4. Blocks

A container is a sequence of **blocks** of `B = 2^log2` bytes, `16 <= log2 <= 23` (64 KiB to
8 MiB). Every block begins with a 64-byte cleartext **block header**; the remaining
`P = B - 64` bytes are the block's **payload**. A sealed container is a whole number of blocks.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic `"GKPB"` (47 4B 50 42) |
| 4 | 2 | format version, `1` |
| 6 | 1 | flags: bit 0 `FIRST` (set on block 0), bit 1 `LAST` (set on the block holding the trailer); other bits 0 |
| 7 | 1 | `log2` of the block size |
| 8 | 16 | container id |
| 24 | 8 | block index, from 0 |
| 32 | 4 | `fill`: payload bytes this header vouches for, `0 <= fill <= P`; `P` in every block of a sealed container |
| 36 | 4 | CRC-32 of `payload[0:fill]` |
| 40 | 20 | zero |
| 60 | 4 | CRC-32 of header bytes `[0, 60)` |

A block header is **valid** when its magic and header CRC match, its version is 1, `log2` is in
range and `fill <= P`. Reserved flag bits and the 20 reserved bytes are written as zero and ignored
by a version-1 reader (the header CRC covers them). A valid header whose payload CRC also matches
the bytes present proves the block intact. No key is needed for any of this.

**The stream.** The payloads of blocks 0, 1, 2, ... concatenated form the **stream**. Stream offset
`s` is at file offset `(s div P) * B + 64 + (s mod P)`. Records live in the stream and cross block
boundaries freely; the 64 header bytes in between are not part of any record.

---

## 5. Records

### 5.1 Layout

The stream is a sequence of **records**. Record `i` has sequence number `seq = i` (the first record
is seq 0, the next seq 1, with no gaps) and starts at a stream offset `o` that is a multiple of 16:

| Stream range | Size | Content |
|---|---:|---|
| `[o, o+8)` | 8 | sync word `sync(seq)` (§3). A search hint only; never trusted |
| `[o+8, o+296)` | 288 | sealed header: `AES-256-GCM(K_meta, IV = u64 seq ‖ u32 1, AAD = "GKPR" ‖ cid, header plaintext)`; 272 bytes of ciphertext then the 16-byte tag |
| `[o+296, o+296+L)` | `L` | payload, `L = payload_length` from the header |
| `[o+296+L, align16(o+296+L))` | 0-15 | filler: CSPRNG bytes, not authenticated, ignored |

The next record starts at `align16(o + 296 + L)`. The smallest record occupies 304 bytes
(`MIN_RECORD`). A record's **digest** is SHA-384 of its bytes from `o` to `o+296+L` (sync word,
sealed header and payload; not the filler).

### 5.2 Header plaintext (272 bytes)

| Offset | Size | Field |
|---:|---:|---|
| 0 | 1 | `kind` (§5.3) |
| 1 | 1 | `flags`: bit 0 `RELOCATED` (the record was copied from another container; `ref_container`, `ref_seq` name the source). Other bits 0 |
| 2 | 1 | `id_form`: 0 `NONE` (no extent id: metadata records), 1 `SEALED` (the id is in this header), 2 `TAG_ONLY` (only the tag is kept) |
| 3 | 1 | `id_len`: bytes of `id` in use, 0..128; 0 unless `id_form = 1` |
| 4 | 4 | `aux`: TOMBSTONE reason code (1 abandoned write, 2 reclaimed, 3 superseded); 0 otherwise |
| 8 | 8 | `seq`; must equal the seq in the IV |
| 16 | 8 | `payload_length` |
| 24 | 48 | `payload_sha384`: SHA-384 of the payload as stored; 48 zero bytes for PAD |
| 72 | 32 | `tag`: `tag(extent id)` for EXTENT; the dead record's tag for TOMBSTONE; zeros otherwise |
| 104 | 128 | `id`: the extent id, UTF-8, `id_len` bytes then zeros; all zeros unless `id_form = 1` |
| 232 | 8 | `stored_ms`: when the extent was first stored (ms since the Unix epoch); 0 if unknown |
| 240 | 8 | `retain_until_ms`: the extent's retention floor when written; 0 for none |
| 248 | 16 | `ref_container`: RELOCATED: the source container id; zeros otherwise |
| 264 | 8 | `ref_seq`: RELOCATED: the source seq; TOMBSTONE: the dead record's seq; 0 otherwise |

A header **opens** at stream offset `o` with seq `n` when GCM authentication succeeds with
`IV = u64 n ‖ u32 1`, the decrypted `seq` equals `n`, `kind` is 1 to 6, `id_form` is 0 to 2,
`id_len` is at most 128, and `id_len` is 0 unless `id_form` is 1. Nothing else may be read from a
header that does not open.

### 5.3 Kinds

| `kind` | Name | Payload | Rules |
|---:|---|---|---|
| 1 | `HEADER` | sealed body (§5.4), 272 bytes | seq 0 at stream offset 0; exactly one |
| 2 | `EXTENT` | the extent's stored bytes, as is | `id_form` 1 or 2; `tag` set |
| 3 | `TOMBSTONE` | empty; `payload_sha384 = SHA-384("")` | `ref_seq` names an earlier EXTENT of this container, which is dead from here on; `tag` is that extent's tag |
| 4 | `CHECKPOINT` | sealed body (§5.6) | written periodically by the writer |
| 5 | `FOOTER` | sealed body (§5.7) | the last record of a sealed container |
| 6 | `PAD` | CSPRNG bytes; never hashed | at most one, immediately before the FOOTER |

An extent is **live** in a container when an EXTENT record holds it and no TOMBSTONE in the same
container names that record's seq.

### 5.4 Metadata bodies

HEADER, CHECKPOINT and FOOTER payloads are sealed:
`payload = AES-256-GCM(K_meta, IV = u64 seq ‖ u32 2, AAD = "GKPM" ‖ cid ‖ u8 kind, body)`,
and `payload_sha384` is SHA-384 of that payload as stored (ciphertext and tag).

**HEADER body** (256 bytes):

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | format version, 1 |
| 2 | 1 | `log2` of the block size |
| 3 | 1 | zero |
| 4 | 4 | `checkpoint_every_records` |
| 8 | 8 | `checkpoint_every_bytes` |
| 16 | 8 | `capacity_bytes`: the container's fixed file size, or 0 for a growing container |
| 24 | 8 | `created_ms` |
| 32 | 8 | `lease_epoch`: the writer's fencing epoch (STORAGE-BINDINGS-DECISION §6); 0 if none |
| 40 | 32 | `binding`: `u8 n` (0..31), then `n` bytes of UTF-8, then zeros. E.g. `fs`, `tape` |
| 72 | 128 | `locus`: `u8 n` (0..127), then `n` bytes of UTF-8, then zeros. An opaque locus token |
| 200 | 56 | zero |

### 5.5 Index entries (120 bytes)

CHECKPOINT and FOOTER bodies carry arrays of entries, one per record:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `seq` |
| 8 | 8 | `offset`: stream offset of the record (its sync word) |
| 16 | 8 | `payload_length` |
| 24 | 1 | `kind` |
| 25 | 1 | `flags` |
| 26 | 1 | `id_form` |
| 27 | 1 | zero |
| 28 | 4 | `aux` |
| 32 | 8 | `ref_seq` |
| 40 | 32 | `tag` |
| 72 | 48 | `payload_sha384` |

An entry repeats its record's header fields except the id, the times and `ref_container`. Because
the entry is authenticated, it proves a record's payload even when that record's own header is
damaged. The footer is the container's `extent id → (offset, length)` map in keyed form: a caller
holding an extent id computes `tag(id)` (§3) and looks the tag up, so the index needs no id in any
form.

### 5.6 CHECKPOINT body

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | checkpoint number, from 1 |
| 4 | 4 | `n`: entry count |
| 8 | 8 | `first_seq`: seq of the first entry |
| 16 | 48 | `R_k`: the running hash (§5.8) before this checkpoint, `k` being the checkpoint's own seq |
| 64 | 48 | digest of the previous CHECKPOINT record, or of the HEADER record for checkpoint 1 |
| 112 | 120·n | entries for seqs `first_seq .. k-1`, in order |

Checkpoint 1 covers seqs from 0; checkpoint `j+1` covers from the seq of checkpoint `j` (so each
checkpoint record is itself listed by the next). Together the checkpoints index every record before
the last of them.

### 5.7 FOOTER body

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `n`: entry count, equal to the footer's own seq |
| 8 | 8 | `data_end`: the 16-aligned stream offset after the last record that is not PAD or FOOTER (after its filler): the PAD's offset if there is a PAD, else the FOOTER's |
| 16 | 48 | `R_n`: the running hash before the footer |
| 64 | 48 | digest of the HEADER record |
| 112 | 48 | digest of the last CHECKPOINT record, or zeros if there is none |
| 160 | 4 | checkpoint count |
| 164 | 4 | zero |
| 168 | 120·n | entries for seqs `0 .. n-1`, in order |

### 5.8 Running hash

`R_0 = SHA-384("GKPRUN01" ‖ cid)` and `R_{i+1} = SHA-384(R_i ‖ sealed header of record i)`, the
sealed header being its 288 stored bytes. `R_n` commits to every record before seq `n`: each sealed
header authenticates its payload's SHA-384.

---

## 6. Trailer

The last 256 bytes of the stream (and so of the file) of a sealed container:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic `"GKPT"` |
| 4 | 2 | format version, 1 |
| 6 | 2 | zero |
| 8 | 248 | `AES-256-GCM(K_meta, IV = FF FF FF FF FF FF FF FF ‖ u32 3, AAD = trailer[0:8] ‖ cid, T)` |

`T`, the 232-byte trailer plaintext:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `footer_offset`: stream offset of the FOOTER record |
| 8 | 8 | `footer_bytes`: `footer_offset + footer_bytes` = stream length − 256 |
| 16 | 8 | `data_end`, as in the footer |
| 24 | 8 | `footer_seq` |
| 32 | 8 | `closed_ms` |
| 40 | 48 | digest of the HEADER record |
| 88 | 48 | digest of the FOOTER record |
| 136 | 48 | `R_n`, the running hash before the footer |
| 184 | 48 | `mac = HMAC-SHA-384(K_mac, "GKPTMAC1" ‖ cid ‖ T[0:184])` |

The trailer MAC covers the header (by digest), the footer (by digest) and every record (by the
running hash). A reader that cannot verify it **must not use the trailer or the footer it points at**.

---

## 7. Writing

### 7.1 Order and identity

1. Choose a fresh random container id. Never write two containers with one id under one pack root:
   the id selects `K_meta`, and the record seq is the GCM counter under it.
2. Write the HEADER record (seq 0) at stream offset 0.
3. Append EXTENT and TOMBSTONE records. After each, if at least `checkpoint_every_bytes` of stream
   or `checkpoint_every_records` records have been written since the last checkpoint (or since the
   start), write a CHECKPOINT.
4. To seal: optionally a PAD, then the FOOTER, then the trailer (§7.4).

A seq is spent when its header is encrypted. After any write error the writer stops for good; it
never re-encrypts different content under a spent seq. A container left unsealed by a crash is
never appended to again: readers recover it (§8.4) and a new container carries on.

### 7.2 Blocks

Bytes are put into the current block's payload; when it is full the block is emitted with
`fill = P`. On tape each block is exactly one `write(2)` of `B` bytes (one tape record).

### 7.3 The durability barrier

On a medium that can rewrite (disk, NVMe) the writer may make every record so far durable before the
current block is full: it writes the block header with `fill` = the payload bytes so far and those
payload bytes, then syncs. When more bytes arrive it appends them and **rewrites that block's 64-byte
header** (payload first, then header, so a crash between leaves an older header whose `fill` and CRC
still describe a correct prefix). This is the only rewrite in the format. A tape writer never does
it: on tape the only barrier is sealing.

### 7.4 Sealing layout

Let `data_end` be the (16-aligned) stream offset after the last record, `n` the records so far, and
`F(m) = align16(296 + 16 + 168 + 120·m)` the size of a footer record with `m` entries. The footer
**ends exactly where the trailer begins**, and any gap before it is one PAD record:

- **Fixed capacity** (a tape parcel): stream length `S = (capacity / B) · P`. If
  `S − 256 − F(n) − data_end = 0` there is no PAD; otherwise a PAD record occupies exactly
  `S − 256 − F(n+1) − data_end` bytes (at least 304; the writer refuses appends that would make this
  impossible). The PAD's payload length is that size minus 296.
- **Growing**: `S` is the smallest multiple of `P` with `S ≥ data_end + F(n) + 256`; if that leaves a
  gap, `S` grows by `P` until `S − 256 − F(n+1) − data_end ≥ 304`, and the gap is one PAD as above.

The FOOTER then occupies `[S − 256 − F, S − 256)` and the trailer `[S − 256, S)`. The last block is
emitted with the `LAST` flag, and the file is exactly `S / P` blocks.

---

## 8. Reading

### 8.1 Opening

The container id and block size come from the block-0 header if it is valid and says index 0.
Otherwise from any other valid block header: for each `log2` from 16 to 23, a valid header at file
offset `k·2^log2` (`k ≥ 1`) whose `log2` and index `k` agree. (A reader may bound how many `k` it
probes; the Java reader probes up to 1,024 per block size.) If no header is valid the caller must
supply the container id (the catalogue has it; files are named `<cid hex>.gkp`), and the reader
tries each `log2` for which the file size is a whole number of blocks until the trailer opens.

`blocks = ceil(file size / B)`. The stream bytes **present** are
`(blocks − 1)·P + max(0, bytes of the last block − 64)`, and 0 for an empty file. A reader uses every
byte present, including bytes past a tail block's `fill` that a crash between the payload write and
the header rewrite of §7.3 can leave: a record there is data if it authenticates.

### 8.2 The index: one seek to the end

1. The file size must be a whole number of blocks; `S = blocks · P`.
2. Read the trailer (stream `[S − 256, S)`). Check magic and version; open `T` with GCM; recompute
   and compare the MAC in constant time. Check `footer_offset` is a multiple of 16,
   `footer_offset + footer_bytes = S − 256` and `footer_bytes ≥ 304`.
3. Read stream `[footer_offset, S − 256)`. Its header must open with seq `footer_seq` and kind
   FOOTER; `align16(296 + payload_length)` must equal `footer_bytes` (the footer fills the space
   before the trailer exactly); its payload must hash to `payload_sha384`; the record digest must
   equal the trailer's footer digest; its body must open (§5.4) and agree with the trailer on
   `n = footer_seq`, `data_end`, `R_n` and the header digest; the entries must have seqs `0..n−1`.

If any step fails the container is **not sealed** for this reader, and nothing from the trailer or
footer is used. On tape: the trailer is in the container's last block, so the index costs one locate
to that block and a short read back of the footer, which ends where the trailer begins.

### 8.3 One record

Given an index entry (or a location `seq`, `offset`, `payload_length`): read stream
`[offset, offset + 296 + payload_length)`. The header must open with that seq and agree with the entry
on `kind`, `payload_length`, `tag` and `payload_sha384`; the payload must hash to it. If only the
header fails to open, an authenticated entry still proves the payload (the record's id, times and
provenance are then unknown). A payload that does not hash is never returned.

### 8.4 The recovery scan

This needs neither trailer nor footer. A reader may implement it differently but must recover the
same records, report the same `valid_end` and `torn_at`, and reach the same verdict.

**Terms.** A record is **found** when its own header opens and its payload hashes (and, for HEADER,
CHECKPOINT and FOOTER, its body opens), or when only an authenticated index entry proves it: its
payload bytes are present and hash to the entry's `payload_sha384` (and a metadata body then opens
too). A found record is reported with `via: "header"` or `via: "index"`. A PAD is never found through
an entry (it has nothing to prove) and is never counted as lost. Every other record the walk meets
but cannot find is **damaged**. A **gap** is any record whose header did not open; a header that
opened over a damaged payload is not a gap, because the running hash covers headers only.

1. **Index.** Try §8.2. If it succeeds the container is **sealed**: the footer's entries are
   **known** and the walk's **limit** is `S − 256`. If it fails but the container carries the
   **marks of sealing** — a whole number of blocks, and either the trailer magic and version at
   `S − 256` or a valid last block header with the `LAST` flag and index `blocks − 1` — it is treated
   as a damaged sealed container: the limit is still `S − 256`, and whatever the walk cannot reach is
   damage, never a torn tail. Otherwise the container is **unsealed**, the limit is the stream bytes
   present, and nothing is known yet.
2. **Blocks.** For each block `i`, check that its header is valid, names this container, has index
   `i` and this `log2`, that at least `fill` payload bytes are present, and that the payload CRC
   matches; for a sealed container also that `fill = P`, `FIRST` is set exactly on block 0 and `LAST`
   exactly on the last block. Report one problem per bad block, naming the first check that failed.
   Block damage never stops the walk: the records decide.
3. **Walk.** `pos = 0`, `expect = 0`. While `pos + 296 ≤ limit`:
   - Try to open the header at `pos + 8` with seq `expect`. Ignore the sync word.
   - **It opens.** Let `end = pos + 296 + payload_length`. If `end > limit` the record runs off the
     end: unsealed, this is the torn tail (`torn_at = pos`, stop); otherwise it is damage (stop).
     Else verify the payload (PAD: skip it) and open the body of a HEADER, CHECKPOINT or FOOTER; a
     CHECKPOINT's or FOOTER's entries become known. The record is found, or damaged if its payload
     does not hash or its body does not open. Advance `pos = align16(end)`, `expect += 1`. **Stop after
     any FOOTER whose header opened**, whatever its body: it is the last record.
   - **It does not open, and an entry for `expect` is known with `offset = pos`.** The header is
     damaged (a gap). Try to find the record through the entry. Either way advance
     `pos = align16(pos + 296 + entry payload_length)`, `expect += 1`, and stop if the entry is the
     FOOTER's. (Entries for `expect` exist ahead of the walk only when the footer is known: a
     checkpoint lists earlier records, so in an unsealed walk this branch does not fire and step 4
     does that work.)
   - **Otherwise, resynchronise.** For `p = pos + 16, pos + 32, ...` while `p + 296 ≤ limit`, the
     seqs that could start at `p` are `expect .. expect + floor((p − pos) / 304)` (a record occupies at
     least 304 bytes). If the 8 bytes at `p` equal the sync word of one of them, `s`, and the header at
     `p + 8` opens with seq `s`, the region `[pos, p)` is damaged with seqs `expect .. s − 1` and the
     walk resumes at `pos = p`, `expect = s`. If nothing is found: unsealed, `torn_at = pos` and stop;
     otherwise the region `[pos, limit)` is damaged (seqs `expect .. footer_seq − 1` when the footer is
     known, else unknown) and stop.

   Resynchronisation over `d` bytes computes up to `d / 304` sync words: about 3.5 million HMACs,
   seconds of CPU, for a 1 GiB region. A reader may bound the distance it scans and report the rest as
   damage; it must say so.
4. **Entries the walk did not use.** Every known entry for a record not yet found (other than PAD and
   FOOTER, and in a sealed container only seqs below `footer_seq`) is tried again through the entry.
   Bodies opened here can add entries: repeat until nothing new is found. A known entry that still
   cannot be proved, and lies in no damaged region already reported, is reported damaged by itself.
   A damaged region is **recovered** when every seq in it was found (or is a known PAD).
5. **End.** `valid_end` is `pos` when the walk stopped. In an unsealed container, if the walk stopped
   short of the limit without a FOOTER and without having set `torn_at`, then `torn_at = valid_end`
   (a fragment of a record). Everything from `torn_at` on is the torn tail: bounded, reported, never
   data, and not damage. If **no record at all** is found, report the problem "no record
   authenticates" (the wrong key, or not a container); there is then no torn tail.
6. **Integrity.** While the walk has had no gap, it keeps the running hash (§5.8). At each CHECKPOINT
   whose header opened it compares `R_k`, and at the FOOTER it compares `R_n` against the trailer's
   or, when §8.2 failed, the FOOTER body's; once a gap has occurred these running-hash checks are
   **not checkable** and are skipped. When the HEADER record was found through its own header, its
   digest is compared against the one the trailer (or else a FOOTER body) records. A mismatch is an
   **integrity problem**: it cannot happen without the key, so it means a writer defect or a keyed
   forgery, and it fails both `scan` and `verify`.

### 8.5 Full verification

A container **verifies** when all of the following hold. These are the checks a conforming verifier
must make. Some field-level rules of §4 to §7 (reserved zero fields, TOMBSTONE `aux` range, the PAD's
zero hash, checkpoint cadence, §7.4 sizing) are obligations on the writer that a verifier is not yet
required to check (§16, P4).

1. §8.2 succeeds; §8.4 reports no bad block, no damage (recovered or not), no torn tail and no
   integrity problem; the running hash and the header digest were both checkable and match.
2. The walk found exactly `footer_seq + 1` records, every one through its own header, and each agrees
   with its footer entry on all nine entry fields (`offset`, `payload_length`, `kind`, `flags`,
   `id_form`, `aux`, `ref_seq`, `tag`, `payload_sha384`).
3. Kinds: HEADER is exactly seq 0 (at offset 0); FOOTER is exactly seq `footer_seq`; there is at most
   one PAD and only at seq `footer_seq − 1`; HEADER, CHECKPOINT, FOOTER and PAD have `id_form` 0,
   `flags` 0, a zero tag and `ref_seq` 0; only bit 0 of `flags` is ever set, and only on an EXTENT;
   every EXTENT has `id_form` 1 or 2, and a SEALED one has `tag = tag(id)`; an EXTENT without
   `RELOCATED` has a zero `ref_container` and `ref_seq` 0; every TOMBSTONE has payload length 0 and
   names by `ref_seq` an earlier EXTENT whose tag equals its own.
4. The HEADER body has version 1, the blocks' `log2`, and `capacity_bytes` either 0 or the file size.
5. Checkpoints, in seq order, are numbered 1, 2, 3, ...; checkpoint `j` has `first_seq` equal to the
   seq of checkpoint `j − 1` (0 for the first) and `n = its seq − first_seq`; its previous-digest is
   the digest of checkpoint `j − 1` (of the HEADER record for the first); its `R_k` matched the walk;
   and each of its entries equals the footer's entry for that seq on all nine fields.
6. The FOOTER body's checkpoint count equals the checkpoints found; its last-checkpoint digest is the
   last checkpoint record's digest (zeros if none); and `data_end` is the PAD's offset if there is a
   PAD, else the FOOTER's.

### 8.6 What a reader must never do

Return a payload that has not been proved by a header that opens or an authenticated entry; use
anything from a trailer whose MAC fails; trust a sync word; or treat a torn tail as data.

---

## 9. What each check catches

| Fault | Detected by | Localised to | Extents lost |
|---|---|---|---|
| A bit flip anywhere in a block | payload or header CRC-32 (keyless) | the block | nothing, unless it hit a record |
| A flip in a record payload | `payload_sha384` | that record | that record |
| A flip in a sealed record header | GCM tag | that record | nothing: the footer entry (or a checkpoint entry) proves the payload; the id and times are lost |
| A flip in a sync word or filler | block CRC only | the block | nothing |
| A flip in a CHECKPOINT | its payload hash | that checkpoint | nothing while the footer stands |
| A flip in the FOOTER or trailer | footer hash / GCM / MAC | the tail | nothing: the walk re-derives the index |
| A torn tail (power loss mid-write) | a header that does not open, or a payload that runs off the end | `torn_at` | the torn record; everything before it is recovered |
| A footer that never landed | §8.2 fails | the tail | nothing: the walk and the checkpoints recover every record |
| An unreadable tape block | the reader's I/O error; the block counts as damaged | the block | the records overlapping it; the walk resynchronises by sync word |
| A trailer from another container, or a forged one | GCM (the AAD binds the cid) and MAC | the tail | the index is refused |
| Wrong key | nothing opens | — | nothing is listed |
| A block from the wrong container or position | block header cid and index | the block | as for damage |
| A sealed container truncated on purpose (tail removed) | nothing in the container: it reads as an unsealed one with fewer records | — | caught only against the catalogue, which records that the container was sealed and its footer digest (§15.2), as SPECIFICATION §7.1 cross-checks checkpoints against the registry |

---

## 10. Disclosure: what is on the medium outside a seal

This is SPECIFICATION §13.2's inventory for this format.

| Where | Field | Bits it carries |
|---|---|---|
| Block header | magic, version, flags, block size | none (constants; FIRST/LAST mark the first and last block) |
| Block header | container id | a random 128-bit label, unlinkable across containers |
| Block header | block index, fill, CRCs | the container's size in blocks, which on a fixed-capacity parcel is a constant; CRCs of ciphertext |
| Stream | sync words | nothing: pseudorandom under a per-container key, so they do not even mark record boundaries |
| Stream | sealed headers, sealed bodies, trailer ciphertext | nothing without `K_meta` |
| Stream | extent payloads | the extent ciphertext, as it is already on disk today |
| Stream | filler, PAD | CSPRNG output |
| Trailer | magic and version | that the container is sealed |

A holder with the medium and no key cannot find record boundaries, so cannot learn record lengths,
record counts, ids, times, the binding or the locus. The one exception is inherent to GLOBAL
(convergent) extents, not to the container: anyone with a candidate public plaintext can compute its
ciphertext and search for it (TENANCY-AND-DEDUP §3 accepts this for public data).

**Identifiers (SPECIFICATION §19).** No extent id is ever written outside a seal. §19.3's test —
a field is legal iff an adversary with a candidate plaintext and no key cannot reproduce it — is met
by every field above. Inside the seal the policy is per domain, from the decision log ("no
plaintext-derived identifier on write-once media: mandatory in sealed domains, relaxed in global"):

| Domain | `id_form` | Why |
|---|---|---|
| Sealed tenant, write-once medium | `TAG_ONLY` | the id `HMAC(K_dom, H)` is a function of plaintext under a tenant-root key; SPECIFICATION §13.1's third clause keeps it off WORM even sealed. The keyed tag lets the engine find the record; media-only rebuild yields tags, and meaning comes back only through the catalogue (§2.2 of the specification) |
| Everything else | `SEALED` | GLOBAL ids are public by design; `HMAC(K_dom, H)` needs `K_dom` to test; NONE ids are random. Sealing keeps them from anyone without `K_meta`, and lets a catalogue-free rebuild name every extent |

`PackFormat.idFormFor(sealedTenant, writeOnce)` returns this. The integration passes the domain's
flags; the pack package never decides policy on its own.

**What the key holder learns.** `K_meta` (a storage-layer key, like SPECIFICATION §7.4's
`K_idx(v)`) reveals each record's length, time, retention floor, tag and (SEALED) id. This is what
the index and the node's `.meta` sidecars hold in the clear today. Hiding lengths from a `K_meta`
holder would need a second key per record; it is not done (§16).

---

## 11. Tape: how this maps onto LTO

- **One block is one tape record.** The drive runs in variable-block mode and every write is exactly
  `B` bytes, one `write(2)` per record (risk register row 5: a short write mis-frames every later
  read, so any other length is a hard failure). `B` is recorded in every block header, so a reader
  sizes its buffer from the medium. LTO drives accept records up to 8 MiB (`READ BLOCK LIMITS`
  reports the drive's limit), which is why `log2 ≤ 23`.
- **One container is one parcel, and one tape file.** A single filemark follows each container
  (risk register row 3: no double filemark at EOD). The container is self-delimiting (its trailer is
  in its last block), so the filemark is a positioning aid and never needed for parsing. No
  structure spans a filemark.
- **Fixed-size parcels.** The tape binding writes containers with `capacity_bytes` = the parcel size
  (SPECIFICATION §3.1: 1 GiB), padded with a CSPRNG PAD record, so every parcel on a cartridge has
  the same length and none carries a cleartext length.
- **No seek-back.** The header is the first record, written once. The index is at the end. Nothing
  is rewritten (§7.3's tail rewrite is disk-only and is refused by a sequential sink).
- **The index after one seek to the end**: locate to the parcel's last block (`first block + capacity/B − 1`),
  read the trailer, read back the footer that ends where the trailer begins (a few blocks: 120 bytes
  per record, about 2 MB for a 1 GiB parcel of 64 KiB extents).
- **Found by scanning** when the tail is lost: §8.4 reads front to back, which is the drive's natural
  direction; checkpoints bound what a lost tail costs to index.
- **Hardware compression off**, drive encryption off (SPECIFICATION §6.1): the stream is
  ciphertext and CSPRNG and would not compress anyway, and compression would re-vary stored length.
  Logical Block Protection (a CRC-32C the drive appends per record) may be on; it is independent of
  the block CRC-32 here, which travels with the data onto disk and into staging.

**Block size: 1 MiB by default.** It is the value SPECIFICATION §6.1 requires for streaming (1–2 MiB
keeps a 400 MB/s drive above its speed-match floor through a spooled feed), it is within every LTO
drive's record limit and the Linux `st` driver's default buffer, and at 64 header bytes per MiB the
cost is 0.006 %. 256 KiB is the floor we would accept on tape (LTFS uses 512 KiB); smaller blocks
cost more records per second without buying anything, because the host writes whole blocks from
memory either way. 2 MiB and 4 MiB are allowed; M2 (the LTO-10 speed-match floor) decides whether
anything above 1 MiB is needed. The same default serves disk, where the block size only sets how
coarsely damage is localised by the keyless CRC.

---

## 12. Defaults and why

| Parameter | Default | Why |
|---|---|---|
| Block size | 1 MiB (`log2 = 20`) | §11 |
| Container size (disk) | 1 GiB, growing, rolled over when full | one unit on every medium, equal to the tape parcel; 10^6 files per PB instead of 10^9–10^10 |
| Container size (tape) | 1 GiB fixed (`capacity_bytes`) | SPECIFICATION §3.1 parcel |
| Record alignment | 16 bytes | AES block size; keeps the resync scan to one probe per 16 bytes |
| Checkpoint interval | 64 MiB of stream or 4,096 records | a lost tail costs at most one interval of index; each checkpoint is at most ~480 KB; 16 per 1 GiB container |
| Record header | 296 bytes | the id field is fixed at 128 bytes so a header's length never depends on the id; 0.45 % on 64 KiB extents, 0.03 % on 1 MiB |
| Index entry | 120 bytes | each record is listed twice (a checkpoint and the footer): 0.37 % on 64 KiB extents. Measured total overhead: 0.88 % on 64 KiB extents, 0.10 % on 1 MiB (§18) |
| Filler and PAD | AES-256-CTR keystream under a fresh random key from the JDK `SecureRandom` | CSPRNG output at memory speed; zeros would expose every record boundary (SPECIFICATION §3.1) |

---

## 13. Repack (D4)

`io.cresco.gfs.core.pack.Repack` copies the live records of a set of containers into new containers
and drops the rest. The rewrite rule it follows (OPEN-QUESTIONS D4): a rewrite **copies ciphertext
bit-identically and always mints a fresh container** (a fresh id, so a fresh `K_meta` and a fresh
counter space); it never re-encrypts and never reuses a counter. Each copied record carries
`RELOCATED` with its source `(container, seq)`, so the new container proves where everything in it
came from, and a record missing from the output is either in the plan's dropped list with a reason
or the verification fails. A botched repack cannot read as a lawful redaction.

**Liveness.** The caller supplies a predicate over `(container, seq, extent id or null, tag, length,
stored_ms, retain_until_ms)`. It is evaluated once, at planning, and the decision is recorded. Records
named by a TOMBSTONE are dead. A record whose retention floor has not passed is kept whatever the
predicate says, since dropping it would be a reclaim and reclaim refuses under a floor. Records a
damaged source cannot prove are listed as dropped with "unreadable in source; repair from another copy".

**States**, persisted in the job's work directory (`repack.json`, written atomically: temp file, sync,
rename, directory sync):

| Phase | Done | A crash here leaves |
|---|---|---|
| `PLANNED` | the live set and the dropped list are decided | sources untouched |
| `COPIED` | new containers written in `work/out`, each sealed and synced | sources untouched; on resume every file in `work/out` is verified and adopted only if it is sealed, verifies in full and holds exactly planned records none of which is already covered; anything else (a torn output) is deleted and its records copied again |
| `VERIFIED` | every output verified in full; the planned set is covered exactly once | sources untouched |
| `PUBLISHED` | outputs moved atomically into the output directory; directory synced | sources untouched; an interrupted move is recognised by name |
| `MAPPED` | `map.json` written: old → new locations, one line per record | sources untouched; the map is re-read, never re-derived differently |
| `ACKNOWLEDGED` | the caller has journaled the map as reloc deltas | sources untouched |
| `RETIRED` | each source retired (disk: deleted and directory synced), one at a time, recorded after each | the remaining sources; all outputs are published and verified |

A source is never retired before `ACKNOWLEDGED`, and `retire()` re-checks that every output is
present and its index authenticates before it retires anything. Each map line is
`{extentId, tag, fromContainer, fromSeq, fromOffset, toContainer, toSeq, toOffset, length}`
(`extentId` null for TAG_ONLY records): exactly what the engine journals as a reloc delta.

Repack stays within one pack root: a TAG_ONLY record's tag is valid only under the root that made it,
and a SEALED record from another root is refused (its tag would not match its id).

---

## 14. How this answers SPECIFICATION §8.4

§8.4 left a hole: with `K_rdom` retired the purity unit became the object, pure packing is ruinous
for small objects, and "the packing unit and the shred unit must be re-separated by something".

The container separates them by construction:

- **The shred unit is never the container.** A container holds opaque ciphertext and has no content
  key; destroying a container key (`K_meta`) destroys only the container's metadata, never an extent's
  confidentiality, and this document never calls it an erasure (SPECIFICATION §13.3 claim 1). Shredding
  stays key destruction at the object or domain (TENANCY-AND-DEDUP §8); a pooled container may hold
  records of many objects and domains without widening any shred.
- **Reclaim is a rewrite of the container, not an erasure inside it.** `live_fraction` is computable
  exactly, with zero medium access, per container: the engine knows which extents it references and
  each extent's location (§15.2). That is the quantity §8.4 rule 1 said pooling made "uncomputable";
  at record granularity it is exact again, because the unit of accounting is the record, not the
  parcel. Repack (§13) is the rewrite, so pooled packing no longer strands dead space permanently on
  rewritable media, and on WORM it is exactly §11.3's migration-time compaction.
- **Blast radius is bounded by the index, not by guesswork.** Damage is localised to a block by CRC
  and to a record by its authenticated header or entry; a mistake names its records.
- **What is packed together is the caller's decision, above the encryption boundary** (§8.4's first
  sentence): the binding appends to whichever open container the packer chooses (by collection,
  retention class, and later co-access), and the format records no cohort, domain or affinity in
  the clear.

What this does **not** settle: §8.4 rule 2 (interleave consent units versus cluster by co-access,
OPEN-QUESTIONS D2) is a placement policy, not a format property; the container supports either. §15.3
states the default.

---

## 15. Integration plan

§15.1 to §15.4, §15.7 and §15.8 are built on branch `wip/packint` (§15.9 says what, and where the build
departs from the plan below); §15.5 and §15.6 (tape) are not. Each item names the files it touches.

### 15.1 `FsBinding` packs into containers

- **Layout.** `<root>/pack/<cid>.gkp` for containers, `<root>/pack/open/` for containers still being
  written, and `<root>/pack/catalogue/` for the node catalogue (§15.2). `BlockStore` keeps its custody
  share functions and loses extent storage.
- **Write path.** `beginWrite` picks (or opens) the active container for the write's packing class
  (§15.3). A `ContainerWriter` is single-threaded, and appends to one write may arrive concurrently
  today, so the binding holds one lock per active container; the lock order is the record order.
  The sink is `PackSink.async(PackSink.file(path), 4)`: blocks are written in order on a background
  thread, up to four ahead, so hashing and sealing overlap the device (§18); `sync()` and `finish()`
  wait for the queue before they force, and a failed write surfaces at the next call. `append(writeId, extentId, data, sha256)` checks the caller's SHA-256, then
  `ContainerWriter.append(extentId, data, idForm, now, 0)` and returns an `ExtentRef` whose `opaque`
  is the `Location` string (`gkp1:<cid>:<seq>:<offset>:<len>`); `durable = false`. `seal(writeId)`
  calls `ContainerWriter.sync()` (§7.3) and then marks every ref of the write durable: one
  `force` per seal, as today's `commitStaged` pays one per batch. `abandonWrite` appends TOMBSTONE
  records (reason 1) for the write's extents, which makes them dead to repack at once.
- **Rollover.** When `fits()` refuses, `finish()` the container (sealed; moved from `open/` to
  `pack/` by rename) and open the next. An idle timeout (default 10 min) seals a container that has
  stopped growing, so the unsealed tail is bounded in time as well as size.
- **Reads.** `readNow` and `enqueue` take locations: the engine passes `opaque` back (§15.4);
  `ContainerReader.read(Location)` is a single positioned read of 296 + length bytes and a verify.
  Readers are cached per container (an open file handle each).
- **Descriptor.** `capacityBytes` becomes the pack directory's measured free space refreshed at every
  rollover, not `getTotalSpace()` once at commission (OUT-15); `appendOnly` stays `NO`.
- **`reclaim`.** Appends a TOMBSTONE (reason 2) and answers `LOGICAL_ONLY` until repack rewrites the
  container, then `ERASED` — the honest two-step that STORAGE-BINDINGS-DECISION §4 asks for.
- **`verify(CONTENT)`.** `read(Location)`; scrub becomes `ContainerReader.verify()` per container,
  rate-limited and resumable by container (OUT-36), replacing NodeAgent's 60 s re-hash of every file.

### 15.2 Startup no longer stats every file

Today `BlockStore` lists the directory twice and stats every file into a heap map (OUT-15). With
containers:

- **The engine holds locations.** `RefIndex` records, per (block, site), the binding's `opaque`
  location (a new `loc` delta, journaled with the placement it belongs to). The node needs no
  per-extent state at startup at all.
- **The node catalogue is a cache.** For `locate(extentId)` and `x.reclaim(extentId)` without a
  location, the node keeps an append-only catalogue log `tag → location`, synced at each seal, and
  rebuilds it from container footers when it is missing (one index read per container: §8.2). For
  each sealed container it also records the footer digest and record count, so a sealed container
  that later reads as unsealed (its tail removed) is an integrity alarm, not a torn write.
- **Startup reads** the list of sealed containers (a few thousand files per PB-node, one directory
  listing), and recovers each container in `open/` with `ContainerReader.scan()`: the records it
  proves are adopted (their writes were sealed, or they are orphans the engine will reclaim), the torn
  tail is discarded, and the container is sealed as it stands into a new file by repack, or its
  proven prefix is kept read-only. Nothing is ever appended to it again (§7.1).
- **Usage** is the sum of container sizes (one stat per container), and dead space is
  `Σ size − Σ live`, from the engine.

### 15.3 Packing classes and the compaction trigger

- **Packing class** (what shares an open container): `(domain, retention class)` by default, so a
  domain's reclaim and a retention class's expiry empty whole containers where they can. This is the
  reclamation grouping of D2; interleaving across consent units is available by making the class
  coarser. Sealed tenants never share a container with another tenant.
- **Trigger.** The engine computes each container's `live_fraction` from its own references (no
  medium access). A container is a repack candidate when `live_fraction < 0.5` (D8's recommendation,
  "refuse above 50 % live") or when it holds more than 25 % of a node's dead bytes. Candidates are
  batched (up to 8 per job) by packing class, and run as a budgeted standing obligation
  (SPECIFICATION §10.6, OUT-36): one job at a time per node, rate-limited in bytes per second.
- **Journal.** The engine plans the job with its liveness predicate (the `RefIndex` holder set, and
  the retention floor), runs it, journals the returned map as one `reloc` delta batch
  (`(domain, block, site) → new opaque`), and only then calls `acknowledge()` and `retire()`. A crash
  of the index between `MAPPED` and `ACKNOWLEDGED` leaves both copies; the job's map is re-read and
  journaled again, idempotently.

### 15.4 The engine's read path

`StorageEngine.fetch/fetchMany` pass `(extentId, opaque)` pairs; `FsBinding.readNow` reads by
location; a stale location (the record moved) fails its tag and seq checks and the engine retries
through the node catalogue, then repairs. `ExtentBinding` gains `readNow(String[] extentIds, String[]
opaque)` (a default method delegating to today's signature, so `MemBinding` and `RemoteBinding`
compile unchanged); `RemoteBinding`/`ExtentServer` carry the `opaque` array in `x.fetch`.

### 15.5 Tape parcels are containers

- The tape binding writes each parcel as one fixed-capacity container (`capacity_bytes` = 1 GiB,
  `binding = "tape"`, `locus` = an opaque volume token) to the `st` device through a sequential sink:
  one `write(2)` per block, one filemark per parcel, positions confirmed by `READ POSITION` after the
  filemark (risk register rows 4 and 6). `ExtentRef.opaque` is the `Location` plus the volume and
  parcel ordinal, which live in the volume registry, not in the container.
- The tape sink is `PackSink.async(PackSink.sequential(st, B), n)`, so the drive is fed from memory
  while the next blocks are framed; order and whole-block writes are unchanged.
- Parcels are spooled on disk as containers first (the spool is the same format), so despool is a
  byte copy of whole blocks at streaming rate, and a spool crash is recovered by §8.4.
- The volume index (SPECIFICATION §7.1 checkpoints and trailer, `res_ords`) is a Layer-1 structure
  **above** containers; each parcel's footer is what it indexes. Erasure coding (RS over parcels) is
  later work (owner decision: 3-way replication now) and would code over whole containers.
- **Reads.** A read of extents on tape reads whole parcels (or block ranges of them) sequentially to
  staging and serves records from there with `ContainerReader`, so the reader never needs random
  access to the medium.

### 15.6 The deferred-read contract

A tape read is not a call that returns bytes: `enqueue(extentIds, deadline, sink)` returns a ticket
in milliseconds; the plant scheduler groups tickets by cartridge and parcel, mounts, reads the needed
parcels front to back into staging, verifies each record with `ContainerReader.read`, writes the
payloads to the sink and completes the ticket. `ticket()` reports `QUEUED → RUNNING → DONE` with
`estCompleteMs` from the plan. The engine must stop busy-polling with a 30 s timeout against a 265 s
mount (OUT-16): its fetch waits on the ticket with the deadline the caller set, and `cancel()` has the
post-condition the descriptor declares. The container format supports this by making the parcel
self-verifying: staging holds whole containers, so a read verifies against the parcel's own index
with no catalogue round trip.

### 15.7 Keys

The pack root is `HKDF(core_master_key, info("gfs/pack/root/v1", node_id), 32)`, derived by the index
and provisioned to the storage node with its registration (a storage-layer key, like `K_idx(v)`:
compromise is bounded to one node's containers' metadata, never to content). Rotating it means
repacking under the new root. OUT-03/OUT-25 (master key custody) apply unchanged.

### 15.8 Migration from file-per-extent

A one-time job per node: list the existing extent files, append each (with its sidecar's times and
retention floor) to containers of its packing class, emit the map as reloc deltas, and after
acknowledgement delete the files. It is the repack procedure with a different source reader.

### 15.9 What `wip/packint` built

**Store and binding.** `io.cresco.gfs.store.PackStore` is the node's packed store; `FsBinding.packed(...)`
puts it behind `ExtentBinding` (`core_store_format=pack`, the default for a storage node; `files` keeps one
file per extent). Every `BindingContractTest` passes for it (locus `PACK` in the test fixtures). Seal is one
`ContainerWriter.sync()` per container the write touched (in parallel) and one catalogue force.
`ExtentRef.opaque` is the `Location` string. Abandon appends TOMBSTONE records (reason 1) where the
container is still open. Rollover seals the container and renames it from `open/` into `pack/`; an idle
container is sealed after `core_pack_idle_seal_ms` (10 min). Each packing class has `core_pack_stripes`
(2) open containers, so concurrent appends do not queue on one writer; at most `core_pack_max_open` (32)
are open, each holding about 5 MiB of blocks. Reads go through `core.pack.LocationReader`: thread-safe,
one positional read per record, and it checks the record's **tag** against the asked-for extent, so a
stale or wrong location can never return another extent's bytes (§8.3 checks only the header and the
payload hash), and a location that runs past the bytes its container holds is refused before anything is
allocated for it (a location is data from the journal; the bound is compared without overflow). A container's reader is opened before rollover moves
its file into place, so no first read can name the path in between. All file operations go through `FileOps` (`PackSink.file(ops, ...)`,
`ContainerReader.open(FileChannel, ...)`, `Repack.Config.ops`), so the power-loss harness runs the store.

**Reclaim is `LOGICAL_ONLY`.** The extent leaves the catalogue (a forced `DEAD` frame) and is tombstoned
while its container is open; its bytes go when repack rewrites the container. The packed locus declares
`deleteSupported = NO`, and the contract test now asserts the outcome the descriptor declares (ERASED for
a locus that can delete one extent, LOGICAL_ONLY for one that cannot). The engine already treats every
outcome but RETAINED as removed.

**The node catalogue (P3).** `store.PackLog` + `store.PackCatalogue`. An append-only log of typed frames,
each `u8 type ‖ u16 length ‖ payload ‖ mac16`, `mac = HMAC-SHA-384(K, prev_mac ‖ type ‖ length ‖
payload)[0:16]` with `K = HKDF(K_root, info("gfs/pack/log/v1", kind), 48)`, chained from a random log id in
a 40-byte header (`"GKCL"`, version 1, kind, log id, and a key check `HMAC-SHA-384(K, "GKCL-KEY" ‖ u16 kind ‖
log id)[0:16]`, so a log written under another root is refused whole, never read as damage to cut).
Frames: PUT (tag, cid, seq, offset, length, id), DEAD, MOVE, SEALED (cid, file bytes, records, log2,
footer digest), RECOVERED, RETIRED. A log is created whole and synced under a temporary name before it is
named, so one shorter than its header is damage. **Torn tail or damage** is decided so that no
acknowledged frame is ever cut: the writer never leaves more than `catalogueMaxUnforcedBytes` (1 MiB)
unforced, forcing first when an append would; a failing frame with more than that after it is damage; within
the bound it is damage when the next frame chains to its stored MAC (its payload or type was hit), or to the
MAC its contents recompute to (its MAC was hit), or its contents authenticate under another length (its
length was hit). A sector that never landed cannot produce any of these, because a frame is shorter than a
sector and the next begins where it ends; the 1,500-round power-cut campaign (all three loss modes) raised
none. Damage sets the log aside and rebuilds it from the containers' own indexes. What stays ambiguous is a
hit on the payload or MAC of the very last frame. Frames re-read after load (listing, the catalogue
rewrite) are verified again, so a frame changed on the medium since is never listed or rewritten under a
fresh MAC. The log is rewritten (live entries only) once it holds more than twice the frames it describes
plus `catalogueRewriteSlackFrames` (65,536); a rewrite records each sealed container at the size its seal
recorded, never the size it has now, so a cut container's alarm survives it. The power-cut campaign runs
with the slack at 24, so rewrites are cut too (1,500 rounds, seed 11, clean). In memory the map keeps 16 bytes of each tag and
the location in primitive arrays (about 48 bytes an extent). Startup lists `pack/` and `pack/open/` once,
stats each container once (a sealed container shorter than the catalogue recorded is an alarm), replays
the log, and recovers each container left in `open/` with the recovery scan into a read-only container.
With a catalogue it trusts, a record the catalogue does not name (never acknowledged, or reclaimed since)
is never adopted; only a rebuild adopts what the containers hold.

**Retention floors** live in their own log (same frames, kind 2), forced before `retain` returns and
never rebuilt: a floor log missing while containers exist, or damaged, makes every reclaim fail
(fail closed) and the node reports it CRITICAL. Its frames fill fixed **64-byte slots** (the header fills
the first), eight to a 512-byte sector so none straddles one, and at most one slot is ever unforced (an
append forces whatever is pending first). A power cut therefore leaves the last slot whole or all zeros,
and a failing slot is a torn tail only when it and everything after it are zero: damage anywhere, the last
frame included, is refused, never cut.

**The index holds locations (§15.2).** `BlockTable.setLocation/location` keep, per (block, site), the
binding's opaque; `CompactBlockTable` stores the packed form in 16 bytes per inline site (container
ordinal, seq, offset/16, length), other strings in its side map, and the fact `l(domain, id, site,
location)` joins the table digest (and so `metaHash`). New deltas, in `StorageEngine.PACK_OPS` (the
delta-type registry must list them): **`loc`** (lines `domain, block, site, location`), journaled in the
same batch as the placement it belongs to (`landed`, or repair's `sites`); and **`locMove`** (lines
`domain, block, site, from, to`), applied only while the location is still `from` or unset. The plan
above calls the second "reloc"; that op name is taken (COPY-on-withdrawal relocations). Snapshots carry
locations in an eighth `blk` field, present only when a block has one. A binding whose address is the id
(RAM, the file store, a remote node today) journals nothing new.

**A foreign root is refused.** A root under which neither log's key check holds and no container with a
valid block header authenticates is another root (a master rotated since the containers were written and
the custody file lost, or roots mixed up between nodes): the store refuses to open under it before it
creates or cuts anything, and the node stays rootless (writes refused, presence UNKNOWN). Accepted, it
would have rebuilt an empty catalogue and the node's own compaction would have retired every container.

**Compaction by the engine's references (§15.3).** `StorageEngine.compactSite` (and the scheduler's
COMPACT pass, `core_pack_compact_period_ms`, 1 h): containers the locus reports compactable (sealed, no
write in flight in them) whose recorded live bytes are below `core_pack_compact_live_fraction` (0.5) of
their size, or that hold more than `core_pack_compact_dead_share` (0.25) of the site's dead bytes and are
at least 20 % dead; up to `core_pack_compact_batch` (8) per job. A record is kept when the index records
the block's copy on that site and its location is that record, or no location is recorded (it cannot
tell), or a write that placed it is still owed its landing; retention floors keep anything under them.
The map is journaled as `locMove` and made durable before `finishCompaction` retires the sources; a job a
restart interrupted after its map is journaled again, then finished. A source is retired only once its live
records are copied, so it must prove what it holds first: one that does not open, in which nothing
authenticates, whose scan reports integrity damage, or that was sealed and no longer proves its seal (its
index does not open, or its footer is not the one the catalogue recorded: a removed tail would otherwise scan
as a crash's torn tail) is **set aside** (never compacted, so never deleted;
an integrity alarm), and so is one where a live record fails verification during the copy (the job is
re-planned without it). One bad container never blocks the others, and none is ever deleted for holding
records compaction could not read. At startup, jobs are resumed only after every container is registered and
(on a rebuild) indexed, so a record a rebuild adopted from a source is moved with the job, not dropped with
the source. It runs as maintenance, so gc,
withdrawal and reconciliation wait for it. For a **remote** node the index holds no locations (x.* still
carries ids: the transport redesign owns `RemoteBinding`), so the node compacts on its own by its
catalogue (`FsBinding.compactByCatalogue`, every `core_pack_compact_node_ms`, 10 min): a record is kept
while the catalogue names it.

**Reads with locations (§15.4).** `ExtentBinding.readNow(ids, opaque)` is a default method; the engine
passes the locations it holds, and the packed binding falls back to its catalogue when one is stale.

**Keys (§15.7).** `KeyRing.packRoot(node, kid)` is exactly `HKDF(master_kid, info("gfs/pack/root/v1",
node id), 32)`. The leader sends it with **`x.packroot`** (a destructive x.* verb: never served unsigned)
wrapped to the node's pinned identity key (`crypto.PackRootWrap`: ECDH P-384 with a fresh ephemeral
key, HKDF-SHA-384, AES-256-GCM, node id and kid bound in). The node keeps the wrapped root
(`store.PackRootCustody`, `pack-root.json` beside `node-identity.p8`) and reinstalls it at start; until it
has one it refuses writes and answers `UNKNOWN`, never `ABSENT`, for what its containers might hold. A
node reports only the root's fingerprint (`packKey`) and kid (`packKid`) in its descriptor; one that holds
another root than the index derives is a key-mismatch alarm and is never re-keyed.

**Migration (§15.8).** `FsBinding.migrateLegacy`: files are appended, their floors put in the pack, the batch
sealed (containers and catalogue forced), and only then are the files deleted under one directory barrier. An
extent a cut left in both places keeps its file's floor (a reclaim takes the larger of the two floors), and a
reclaim erases the file with the logical reclaim, so no later batch can pack a reclaimed extent again; a file
whose digest no independent sidecar vouches for is left in place. Until migrated, files stay readable
through the packed locus. A storage node runs it in the background (`core_pack_migrate=auto`). The index
journals no locations for migrated copies (it cannot see them move on a remote node); they are found by id.

**Not built here:** tape (§15.5, §15.6); scrub by container (`ContainerReader.verify` per container,
OUT-36; the engine's scrub still reads each copy); capacity refreshed at rollover (the free-space probe
refreshes every 500 ms as before); a `core.compact` operator verb (it should be a C3 job once the jobs API
is merged; the scheduler runs compaction meanwhile); carrying locations across x.* (transport redesign).

---

## 16. Open questions this depends on, and the defaults chosen

| Question | Dependency | Default taken here |
|---|---|---|
| **S1** K_meta counter discipline | container metadata is GCM under a key | **Answered for containers**: IV = (seq, domain) under a per-container key; injective by construction, no RNG in the IV. The catalogue cnodes are outside this format and remain open |
| **S2** Idempotency-key lease | two writers under one container id would share a counter space | A container id is fresh random per container and never reopened; the file sink refuses an existing name; the tape binding must check its catalogue for the id before writing. A lease is still needed for cross-host writers |
| **B3** Independent reference reader | the format is a one-way door | `eval/pack_reader.py`, written from this document alone, checks the goldens and Java-written containers (§17) |
| **B4** Publish the format | a future reader | This document contains no secret and is written to be published; the owner decides |
| **B5** Block size, filemarks, partitions, checkpoints | tape layout | 1 MiB blocks; one filemark per container; no partitions; checkpoints every 64 MiB inside a container. The volume-level index checkpoints are Layer 1 |
| **D1** Which data on drive-enforced WORM | none: the format never rewrites on tape | the tape writer behaves as WORM on every cartridge |
| **D2** Interleave consent units vs. group for reclamation | packing class (§15.3) | group by `(domain, retention class)` on disk; tape policy open |
| **D3** Repack granularity | repack | record-granular: citations name extents, not positions, and positions change only through journaled reloc deltas, so sub-container repack breaks nothing |
| **D4** The rewrite rule | repack | adopted in the form of §13: bit-identical payloads, fresh container key, provenance on every record |
| **D8** GC on by default | compaction trigger | on for disk, `live_fraction < 0.5`; off for WORM |
| **M1** Mount cycle | none for the format | — |
| **M2** Speed-match floor | block size above 1 MiB? | 1 MiB until measured |
| **S7** FIPS 140-3 module | JCA provider | JDK JCA only; algorithms are CNSA (SHA-384, HMAC-SHA-384, AES-256-GCM, HKDF-SHA-384) |
| **new: P1** Lengths from a `K_meta` holder | §10 | not hidden; would need a per-record key |
| **new: P2** Keyless proof of possession | block CRC-32 detects media errors but is forgeable | a keyed or Merkle challenge over blocks is future work (SPECIFICATION §4 `prove`) |
| **new: P3** Node catalogue format | §15.2 | append-only, MAC-chained `tag → location` log; built on `wip/packint` (§15.9) |
| **new: P4** Reference-reader findings still open | §8.1, §8.4, §8.5, §17 | the second pass of `eval/pack_reader.py` raised 11 points (a gap found through its entry is reported as recovered damage; a wrong key on a sealed-looking file also yields one damage region; a resync that loses no seq has null seqs; `--cid` needs a trailer that opens, though the HEADER record could supply the block size; the 1,024-probe bound; writer-side rules §8.5 does not require). None changes the byte layout; each is a reporting or verifier-scope rule to settle before the format is frozen |

---

## 17. The reference reader (`eval/pack_reader.py`)

Python 3 standard library plus the `cryptography` package (for AES-GCM only). Written from this
document; it must not import or port the Java implementation.

```
python3 eval/pack_reader.py list    --key HEX [--cid HEX] [--json] FILE...   # §8.2: the index of sealed containers
python3 eval/pack_reader.py verify  --key HEX [--cid HEX] [--json] FILE...   # §8.5: full verification
python3 eval/pack_reader.py scan    --key HEX [--cid HEX] [--json] FILE...   # §8.4: recovery scan
python3 eval/pack_reader.py extract --key HEX [--cid HEX] --seq N FILE       # one verified payload to stdout
python3 eval/pack_reader.py selftest                                         # the §3 test vectors
```

`--cid` supplies the container id for §8.1's last resort, when no block header is valid.

`--key` is the 32-byte pack root in hex. Exit status: 0 when every file succeeded, 1 when any file did
not (including a file that cannot be opened), 2 for a usage error. Success is, for `list`: the index
authenticated (§8.2); for `verify`: the container verifies (§8.5); for `scan`: every damaged region
was recovered and there was no integrity problem (bad blocks and a torn tail are reported but
allowed; a wrong key fails, by "no record authenticates"); for `extract`: the record was found and
written.

`list` reads the footer and each record's header, not the payloads. `extract` uses the index when the
container is sealed and the scan otherwise; it writes the payload as stored (for HEADER, CHECKPOINT
and FOOTER, the sealed body, not the opened one) and refuses a PAD, which carries nothing provable.

With `--json` the output is a JSON array with one object per file:

```
{
  "file": str, "container_id": hex, "log2_block": int, "file_bytes": int, "blocks": int,
  "sealed": bool,                 # §8.2 succeeded
  "ok": bool,                     # the command's success criterion above
  "problems": [str],              # human-readable; includes §8.4 integrity problems
  "bad_blocks": [{"index": int, "problem": str}],      # one per bad block: the first check it failed
  "damage": [{"seq_from": int|null, "seq_to": int|null, "stream_from": int, "stream_to": int,
              "recovered": bool, "reason": str}],      # one per damaged region (§8.4 step 3 or 4);
                                                       # seq_to null when the range's end is unknown
  "torn_at": int|null,            # §8.4 step 5; null when there is no torn tail
  "valid_end": int|null,          # §8.4 step 5 (scan and verify); null for list
  "footer_seq": int|null, "run_hash": hex|null,        # from the trailer, only when sealed (§8.2)
  "header": {"version", "log2_block", "checkpoint_every_records", "checkpoint_every_bytes",
             "capacity_bytes", "created_ms", "lease_epoch", "binding", "locus"},   # {} if unreadable
  "records": [ {
      "seq": int, "kind": "HEADER|EXTENT|TOMBSTONE|CHECKPOINT|FOOTER|PAD",
      "flags": int, "id_form": int, "extent_id": str|null, "tag": hex, "offset": int,
      "payload_length": int, "payload_sha384": hex, "stored_ms": int|null,
      "retain_until_ms": int|null, "ref_container": hex|null, "ref_seq": int, "aux": int,
      "via": "header|index"
  } ]
}
```

`records` lists every record the reader found, in seq order, including HEADER, CHECKPOINT, PAD and
FOOTER. `via` is `"header"` when the record's own header opened and `"index"` when only an entry
proved it; with `"index"`, the four fields an entry does not carry (`extent_id`, `stored_ms`,
`retain_until_ms`, `ref_container`) are null. For `list` the records are the footer's entries plus
the FOOTER record itself, each with its header read (so `via: "header"` unless that header fails to
open).

The golden manifests (`src/test/resources/pack/golden-v1-*.json`) list, for each golden container,
the fields above that any correct reader must reproduce, and the key (`key`).

---

## 18. Measurements

`PackMeasurementsTest`, 2026-09-26, `eval/results/pack_bench_20260926-110204.json` (earlier runs of
the same harness: `-104742`, `-105433`). One Mac: Apple M3 Max, 36 GB, internal SSD (APFS, 92 %
full), JDK 23.0.2, one writer thread. **Other agents' test suites were running throughout** (load
average 6–7), so the device figures are low and noisy for this SSD; the CPU figures are steady across
all three runs. 1 GiB per case, three repetitions, medians. Reads come from the page cache (the file
was just written), so read and verify figures are the CPU cost of verification, not a cold-disk rate.

| Extent / block | Raw write + sync | Pack write | Pack write, async sink | Writer CPU only | Index open | Verified read, in order / random | Full verify | Scan, unsealed | Space overhead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 KiB / 1 MiB | 242 MB/s | 174 MB/s | **375 MB/s** | 1,224 MB/s | 6.2 ms | 1,313 / 1,338 MB/s | 1,107 MB/s | 1,105 MB/s | 0.88 % |
| 1 MiB / 1 MiB | 369 MB/s | 171 MB/s | **357 MB/s** | 1,258 MB/s | 0.4 ms | 1,330 / 1,345 MB/s | 1,106 MB/s | 1,101 MB/s | 0.10 % |
| 64 KiB / 256 KiB | 220 MB/s | 104 MB/s | 201 MB/s | 1,241 MB/s | 6.1 ms | 1,303 / 1,314 MB/s | 1,093 MB/s | 1,104 MB/s | 0.88 % |

Primitives on one core: SHA-384 1,540 MB/s; CRC-32 9,495 MB/s; sealing one record header (AES-GCM,
272 bytes) 0.34 µs; one sync word 0.43 µs.

What the numbers say:

- **The writer's own cost is SHA-384 of each payload**: 1.22–1.26 GB/s on one core, three times an
  LTO-10 drive's 400 MB/s. Framing, sealing and the running hash are under 2 µs per record.
- **Written synchronously the writer adds its hashing to the device time; with the async sink the
  two overlap** and it reaches the device: 357–375 MB/s against 369 MB/s for raw 1 MiB writes (the
  raw 64 KiB case, 242 MB/s, is lower because it writes in 64 KiB pieces; the container always
  writes whole blocks). The integration uses the async sink (§15.1). A 1 MiB block writes faster than
  256 KiB here, which supports the default.
- **Reading and verifying are SHA-384-bound**: about 1.1–1.35 GB/s, so a full verification of a
  1 GiB container costs about 0.95 s of one core; the keyless CRC pass alone is about 0.1 s per GiB.
- **Opening the index is one trailer read and one footer read**: 0.4 ms for 1,024 records, 6 ms for
  16,384 (a 2 MB footer).
- **Recovering a container whose footer never landed costs one sequential read** at verify speed.
- **Against today's file-per-extent path**, reproduced in the same run under the same contention
  (a file and sidecar per 64 KiB extent, data synced in parallel at seal, one directory sync):
  3.2 MB/s written, because the path pays one fsync per extent (4,096 for 256 MiB) where a container
  pays one per seal. MODULE-DECISIONS F-C10-2 measured the same path at 46–78 MB/s (R = 3 publish)
  on a quieter machine; the ratio that does not depend on the load is fsyncs per seal, N against 1.
  Its startup listing and stat took 41 ms for 8,192 files (5 µs a file): at 10^9 extents (2×10^9
  files) that is about 2.8 hours and a 10^9-entry heap map, where a pack store lists about 10^6
  containers per PB (about 5 s at the same rate) and holds no per-extent state. The 10^9 figure is an
  extrapolation, not a measurement.

---

## 19. Tests

`src/test/java/io/cresco/gfs/core/pack/`:

- `ContainerTest`: round trip; 3,000 extents and one spanning five blocks, across blocks and
  checkpoints; the sync barrier and the partial tail block (a crash snapshot after every sync recovers
  exactly what was synced); the sequential sink (whole blocks only, no rewrite, no partial barrier);
  the async sink (order, barriers, and a failing device that surfaces at a later call and ends the
  writer); fixed-capacity parcels, full and nearly empty; no id, length or time readable outside a
  seal, and under a wrong key nothing listed and no torn tail; tombstones; the location string.
- `DamageTest`: a torn tail at every byte offset of the last record (which straddles a block header),
  sealed and unsealed; bit flips across the whole container (every 53rd byte, every block header, the
  footer and trailer region, and every record's sync word, header and payload edges): each detected,
  localised to its block, costing at most its own record, and never read as a torn tail; the first two
  block headers damaged (the container still opens); a footer that never landed (truncated, and
  destroyed in place) recovered by scan; a trailer whose MAC fails, a flipped trailer, a trailer from
  another container, and a wrong root: the metadata is refused and the records still authenticate on
  their own.
- `RepackTest`: live records move bit-identically with provenance, dead and tombstoned ones are
  dropped and reported, retention floors hold, TAG_ONLY stays TAG_ONLY, the map is stable; a crash at
  each of twelve points (plan, first and seventeenth copied record, first and second output closed,
  copied, verified, published, mapped, acknowledged, first and second source retired) is resumed to
  the same final state, and no source is retired before the map is acknowledged.
- `GoldenTest`: the committed goldens read exactly as their manifests say; the reference reader
  agrees on both goldens, on a fresh 300-extent Java-written container, and on a torn copy of it.
- `PackMeasurementsTest` (tag `measure`, not in the normal build): §18.
