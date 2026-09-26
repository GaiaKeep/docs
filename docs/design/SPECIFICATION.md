!!! warning "Status: Partly superseded"
    The write-once block fabric specification, written tape-first. **Superseded in part:** deduplication and content-derived block ids were retired here (§12.3, §18.4) without owner approval, and are being restored under configurable dedup domains. The ban on plaintext-derived identifiers (§19.3) becomes policy-dependent, and Bareos (§6) has been removed. A re-cut to a media-neutral core is pending (question Q1). §20 (GCM counter discipline) is current for sealed data.

# THE SPECIFICATION — STELE

**A three-layer block substrate for a monotonic, blind, federated archive.**

**Status:** Specification. Supersedes the four candidate designs (Cairn, Quire, HOLD, MONOTONE) and the sixteen attacks against them; adopts what survived and states what did not.

**Binding constraint, which supersedes an earlier premise of this document:** *we deal with the volumes and Bareos does the low-level placement.* Every prior draft, and all four candidate designs, assumed we own the medium byte-for-byte via `st` plus `SG_IO`. We do not. §2.3 states exactly what that deletes, what it costs, and what it hands back.

**Depends on:** `ENTAIL-AGENT-NATIVE-FS.md` (the agent-facing design of record — `realise`, `prospect`, Coverage, S14), `STORAGE-DIRECTION.md` (the cryptographic substrate, the redaction-domain model and the dataset versioning specification), `TAPE-RESEARCH-PROMPT.md` (the plant and its arithmetic), `STORAGE-BINDINGS-DECISION.md` (one plugin, one SPI, one binding per media class).

**Normative corrections this document makes to its own dependencies** are collected in §12.6 and §17. They are corrections, not clarifications: three of them are defects that defeat crypto-shredding permanently if built as currently written.

---

> **Provenance and status, recorded 2026-09-19.** Produced by a 21-agent design pass (four
> from-scratch designs — minimal-mechanism, placement-first, materialisation-first, worm-native —
> each attacked on subtraction, physics, the whole loop and cryptography, then synthesised). The
> synthesis agent's own brief did **not** mention Bareos; it read a concurrently-running workflow's
> script file from disk and incorporated the owner's Bareos framing from it. The integration is
> sound, but note the consequence: **§2's layer cut treats "Bareos is Layer 0" as settled, and it is
> not.** That question is under evaluation in its own right, and this document should be re-read
> against that decision when it lands. Everything above Layer 0 — the locator, the block plane, the
> placement ledger, materialisation, the scheduler — is independent of how Layer 0 is implemented
> and stands either way.
>
> **Update, same day:** that evaluation has since landed as `BAREOS-RECOMMENDATION.md` and
> reaches the same conclusion by an independent route, verified against cloned source. The
> layer cut is therefore sound, though §2's `gfs-mover` is superseded: under the division it is
> *deleted* rather than replaced, by Bareos plus a five-opcode read-only probe helper.

---

## 1. Thesis, and the reduction that makes it small

Encryption, deduplication, naming, hierarchy, metadata, versioning and access control are all handled **above** this substrate. The storage layer therefore sees only opaque, already-encrypted, fixed-size blocks. Every conventional storage product — LTFS, object stores, NAS protocols, our own `filerepo` — exists to supply naming, hierarchy, metadata, dedup, compression, encryption and access control *at* the storage layer. We need none of it there.

Those mechanisms are not neutral overhead. They are **liability**, because anything plaintext-derived written in the clear to unerasable media survives the erasure it documents for the 10–30 year life of the medium, and therefore defeats crypto-shredding permanently. A cartridge catalogue of names, sizes and dates is not merely redundant here; it is a standing disclosure that no key destruction can reach.

What remains is a **write-once block plane**: opaque bytes go on media at a position the volume manager assigns, and come back verified. Above it, a **placement ledger** that records where each block landed and reconstructs from survivors. Above that, **materialisation**: gather, decode, decrypt and present accessible storage at an arbitrary point in the network, as a disposable cache, because everything live is already a cache.

The name is STELE: a slab inscribed once and never altered, legible to whoever holds the script and opaque to everyone else.

### 1.1 The reduction as proposed

```
write(opaque_bytes) -> locator        locator = (resource, position, length, verifier)
read(locator)       -> opaque_bytes
verify(locator)     -> ok | bad
enumerate(resource) -> [locator]
```

### 1.2 Verdict: mostly true, wrong in six places, and the corrections are the design

**(1) `write() -> locator` cannot exist.** On append-only media the writer does not choose the position and nothing is durable until a filemark lands and the position is read back. Streaming is mandatory — below roughly 112 MB/s an LTO drive backhitches — so a per-block barrier destroys streaming. The locator is **discovered at a durability barrier, never predicted**. `append` + `seal` replaces it, and `seal` is the naming event: *a locator that was not returned by a successful `seal` does not exist.* This is the single most load-bearing correction in the document, it is forced by the medium rather than by taste, and almost everything good downstream descends from it.

**(2) `verify(locator)` is not a call at block granularity, and a whole-fragment digest cannot serve what it was reaching for.** Verification is what `read` does unconditionally. A standalone verify over a flat digest is a whole-fragment read — 103 GB and a mount — so sampled proof-of-possession against a blind holder becomes unaffordable and is therefore never run. Worse, a single digest over a 103 GB fragment cannot verify a ranged read *at all*, which is the dominant access pattern, and cannot localise an erasure position, which is what the local erasure code needs. The fix is one field: a **Merkle root over 8 MiB leaves**, giving ranged verification, resumable scrub and cheap challenge-response. The verb becomes `prove(locator, leaf, nonce)`.

**(3) `enumerate()` is not a method, it is a 20.8-hour job** (30 TB at 400 MB/s) unless the medium carries its own index. It does, written at longitudinal checkpoints and pointed at by MAM, so enumeration is one locate and one short read (§7) — and the full sweep survives as the last-resort fallback it should always have been.

**(4) `delete` is correctly absent, and must stay absent.** This is the load-bearing subtraction. A NAS unlinks, a block device discards, WORM cannot; every prior attempt at a uniform storage SPI foundered on that method. Removing it passes the honesty test by *subtraction* rather than by exception. But `retire` — the whole-resource replacement — reintroduces the same lie unless it declares what it actually achieved, so it returns a typed disposition (§5.4), and it is token-authorised, because it destroys 30 TB irreversibly.

**(5) "A few hundred lines per medium" was right for disk, roughly 6× optimistic for tape — and is now moot.** The excess was never an abstraction failure: it was end-of-medium handling and recoverable-versus-unrecoverable error classification, properties of the medium that no interface removes and whose failure mode is silent data loss. Under the binding constraint we do not write it. §2.3.

**(6) The reduction implies the *quantum* is a free parameter.** It is not one parameter; it is four fused together — the padding unit, the erasure symbol, the streaming unit and the read unit — and every candidate design that fused them failed on at least one attack as a direct consequence. §3 separates them, and that separation is what dissolves the padding-waste, accumulation, read-amplification and duty-cycle attacks simultaneously.

**Missing entirely** from the reduction: `recover` for a torn tail, a typed fault taxonomy, a residual/health report, and an admission gate on *writes*. Four calls become ten. Each addition is justified at its call site.

---

## 2. The layer cut

### 2.1 Four layers, three of them ours

| | Layer | Owns | Never sees |
|---|---|---|---|
| **0** | **Volume manager (Bareos)** | Drives, changer, device reservation, block framing, filemarks, end-of-medium, sense-key classification, volume labelling, spooling | Anything we do not hand it; it is fed opaque parcels under opaque names |
| **1** | **Block plane** | Parcels on one volume; the parcel format; the durability barrier; the Merkle tree; the volume index | Names, keys, stripes, other volumes, time |
| **2** | **Placement ledger** | Coding, placement, packing, repair, migration, the volume registry, drive-second scheduling | Plaintext, keys, file names, selectors |
| **3** | **Materialisation** | Gather, decode, decrypt-on-stream, present, lease, release | Physical position, cartridge identity |

Three rules bind them, and they are the abstraction-integrity claim in full:

- **No layer above the block plane ever records a physical position.** Layer 2 stores a locator as opaque bytes and joins it to a medium through a ~10³-row registry. This is what makes generational migration a row swap that invalidates no citation, no manifest, no extract certificate and no receipt.
- **No layer below materialisation ever holds plaintext or a content key.** Repair, scrub, rebuild and proof-of-possession are keyless by construction, so durability never depends on the authorisation path.
- **Every caller reads the medium's difference as a declared value; no caller branches on the binding.** The difference between media is a fact about *time*; no signature can hide a fact about time from a caller with a timeout, so `latencyClass` and `firstByteP50Ms/P95Ms` are fields, and stripe placement enforces latency-class homogeneity so the branch happens once per stripe, not once per fragment.

### 2.2 The single most important structural statement

**The locator is a *where*, never a *what*. Nothing above the placement ledger ever holds one.**

This is the load-bearing wall. It is why `retire` can destroy a whole volume, why migration can re-code and re-pack freely, and why `delete` never has to come back to repair a broken reference. The moment a citation held a position, all three of those become impossible. The identity of bytes lives above (as `xid`, a keyed HMAC); the position lives below; the two never touch.

Its corollary, which is the reconciliation of media-only rebuild with crypto-shredding: **placement is recoverable from physics, meaning is recoverable only with custody quorum.** A media-only sweep yields locators and nothing else. That asymmetry is designed, not accidental (§7.3).

### 2.3 What the owner's constraint deletes, what it costs, and what it hands back

Under *we deal with the volumes and Bareos does the low-level placement*, Layer 0 is not ours.

**Deleted outright** — approximately 1,600 lines whose failure mode is silent data loss, plus the machinery around them:

- the `st` ioctl/IO wrapper, fixed-versus-variable block mode, filemark discipline;
- `MTSEEK`/`MTFSF`/`MTBSF` plus `READ POSITION` (0x34) positioning;
- early-warning to programmable-early-warning end-of-medium handling;
- sense key / ASC / ASCQ classification and reposition-after-error;
- the medium changer (`MOVE MEDIUM` 0xA5, `READ ELEMENT STATUS` 0xB8, slot inventory);
- `gfs-mover` as a privileged process, `CAP_SYS_RAWIO`, the CDB allowlist;
- SCSI Persistent Reserve on the changer and every drive LUN, epoch-keyed takeover, reservation-conflict fencing;
- rows 2–9, 11, 15, 16 and 20 of the twenty-row SCSI risk register in `STORAGE-BINDINGS-DECISION.md` §8, which become *configure and assert* rather than *implement and hope*;
- **and the largest non-technical liability in the prior draft**: the standing obligation to publish and maintain a versioned on-media format specification and a reference reader for the thirty-year life of the medium, with no standards body to inherit it. `bls`, `bextract` and `bscan` are that reader, and they are maintained by someone else. This is the single biggest thing the constraint buys, and it was previously the design's worst unanswered weakness.

**Retained on our side of the boundary**, because Bareos does not have them:

- the locator and its Merkle tree (§4);
- the parcel format and the fixed-size invariant (§3.1);
- the volume index and the media-only rebuild path (§7);
- erasure coding, placement, packing affinity and repair (§8);
- **wave formation**: Bareos allocates drives per job but performs no coalescing across requests, so batching to a drive-seconds target is ours (§10);
- materialisation, keys and Coverage (§9);
- and, non-negotiably, the **disclosure contract over everything Bareos writes** (§6.3, §13).

**Retained SCSI, read-only, diagnostics only, never on a data path:** `LOG SENSE` pages 0x0C/0x31 for write-error and lifetime counters, TapeAlert via a single reader, MAM read/write for the index pointer, and the medium-serial read at commissioning. That is not a device driver and it does not reintroduce the deleted lines.

**What it costs, stated plainly:**

1. **Bareos writes plaintext-derived identifiers onto unerasable media.** Volume labels and per-session labels carry names and timestamps; per-block headers carry a second-resolution `VolSessionTime`; attribute records carry the filename we supply and its stat data. This is the LTFS-index problem with different syntax, arriving through the back door, and §6.3 and §13 are the entire answer to it. It is fatal if unaddressed and cheap to address, which is exactly the combination that gets skipped.
2. **We do not own the retry policy.** `STORAGE-BINDINGS-DECISION.md` §8 row 12 — at most one same-drive retry, then rebuild from local parity on the pass in progress — is not expressible through a third party's error handling. A marginal cartridge can consume a drive in an internal retry storm, and local-parity reconstruction moves from *during the pass* to *after the error*, costing one extra mount in the rare case. That is the whole price.
3. **No Recommended Access Order.** Bareos follows bootstrap-record order. `TAPE-RESEARCH-PROMPT.md` Q3(iv) flags RAO as load-bearing and unmeasured. Mitigated, not solved, by contiguity: a fragment is 103.1 GB contiguous on one volume by construction, which is the RAO substitute we already own (§3.3). Recorded as a costed trade, not absorbed silently.
4. **Bareos is a second catalogue and a second failure mode.** Its retention, pruning and recycling machinery is a deletion engine pointed at an archive whose defining property is that deletion does not exist. §6.2 fences it; §6.4 demotes its catalogue from authority to cache.
5. **Drive arbitration is the Storage Daemon's.** Our published obligation reserve is real only because we partition devices physically between pools (§10.4), not because we declare a percentage.

---

## 3. Geometry: four quanta, deliberately separated

| Quantum | Value | Sole job | What fusing it broke |
|---|---|---|---|
| **Parcel** | **exactly 1 GiB** | Padding unit; local erasure symbol; the unit `append` accepts; one Bareos file | Fusing it with the read unit gave a 1.5 % duty floor; fusing it with the fragment gave 19×–192× amplification on a forced seal |
| **Band** | 32 parcels = **28 data + 4 local parity** | Local repair group | Fusing it with the fragment forced a fixed minimum stripe and made short stripes ruinous |
| **Fragment** | **96 parcels contiguous on one volume** (3 bands: 84 data + 12 parity) = 103.1 GB written, 90.2 GB payload | Global erasure symbol; the reposition unit; the read unit | Fusing it with the padding unit produced the amplification above; fusing it with the stripe made a lineage wait weeks to accumulate |
| **Stripe** | 2 data fragments + 1 parity fragment, one per site | Durability unit | Fusing it with the fragment made the minimum viable commit 168 GiB |

Derived: local rate 32/28 = **1.1429×**; global rate 3/2 = **1.5×**; combined **1.714×**. Stripe payload = 2 × 84 GiB = 180.4 GB; stripe media = 3 × 96 GiB = 309.2 GB.

### 3.1 Why the parcel is exactly 1 GiB and never varies

Arithmetic check 16: `log₂(1 PB / 64 KB) = 33.8` bits of addressing against ~4.6 bits of entropy per chunk-boundary spacing, so **eight consecutive cleartext lengths localise a run of content in a petabyte corpus** — permanently, on media that cannot be rewritten, beyond the reach of any key destruction.

> *2026-09-19: with content-defined chunking retired for content (`eval/results/cdc_largefile.json`) and content chunked at fixed 64 KiB, the boundary-spacing entropy this check quantifies no longer exists in the data plane; it survives in the metadata plane, where CDC is retained and the boundary function is keyed. **The fixed-1 GiB-parcel argument below is independent of that and is unchanged** — it deletes the one cleartext length on the medium regardless of how the payload inside was chunked.*

We do not mitigate that channel. We **delete** it: every parcel is exactly `PARCEL_BYTES = 1073741824`, so the one cleartext length that cannot be removed from the medium carries zero bits, and positions are a constant stride. The invariant is enforced as a hard refusal in `append`, not as a convention — a specification that relies on nobody ever writing a short parcel will get a short parcel.

**Padding is CSPRNG output, never zeros.** A zero tail is a visible ciphertext/pad boundary, and every trailing parcel's true payload length becomes recoverable from the medium alone, with no key, permanently. That single implementation default would defeat the entire fixed-size argument. It is a conformance item (§17), tested by sampling the last 64 KiB of every sealed parcel and comparing its entropy against the head of the same parcel.

This is the second, decisive reason **LTO hardware compression must be disabled**: compression re-varies stored length and destroys the property outright. Ciphertext not compressing is the weaker argument. Under Bareos the same rule extends to SD-side Auto Deflate/Auto Inflate and to FD-side software compression (§6.1).

### 3.2 Why the local code is RS(j, 4) with j ≤ 28, not RS(28, 4)

A band shorter than full gets `j =` its actual data-parcel count. This is what removes the accumulation problem: a lineage that must force-seal writes `j + 4` parcels for `j` parcels of data, so overhead is the code rate and padding is at most one parcel per fragment. **Minimum viable stripe ≈ 2 GiB of payload**, against the 128–192 GiB that made forced seals catastrophic in the candidate designs.

Local parity is written at the **end** of each band, so the healthy read is contiguous data parcels and never touches parity.

Rate choice: 28+4 rather than 30+2 costs 16 extra cartridges at 4.2 PB (~$21k) and buys two additional parcel failures per band tolerated **at zero external mounts and zero wide-area bytes** — which matters precisely during the zero-margin site-loss rebuild window (§8.6). 30+2 (1.6× combined, 224 cartridges) is the budget alternative and is stated here so the choice is explicit rather than inherited.

### 3.3 Why the fragment is 96 parcels, from two independent derivations

Let `R = 400 MB/s`, `T` the serpentine reposition between two runs, `O` the non-transfer mount cycle, `d` the target duty.

**Run-length law.** Within one loaded medium, sustaining duty `d` across repositions requires a contiguous run of `B ≥ d·R·T/(1−d)`:

| d | T = 20 s | T = 40 s | T = 60 s |
|---|---|---|---|
| 0.80 | 32 GB | 64 GB | 96 GB |
| 0.85 | 45 GB | **91 GB** | 136 GB |

**Bytes-per-mount law.** Across mounts, `B ≥ d·R·O/(1−d)`: 408 GB at the optimistic `O = 180 s`, **601 GB** at the four-term cycle of §3.4. At four fragments coalesced per mount that is 412 GB.

The two laws converge from opposite directions on a contiguous run of ~96 GiB, coalesced roughly four-deep per mount. That is the fragment.

**Contiguity does the work, not size.** The mount count for a scattered selection is identical at every fragment size (any uniform sample touches essentially every cartridge — check 15). Fragment size buys only on the *reposition* term, and pays for it in read amplification. A larger fragment is not better; 96 parcels is where the reposition term stops dominating and before amplification starts to. This is also the answer to the deleted RAO capability (§2.3): we obtain monotone forward motion by construction rather than by asking the drive for it.

### 3.4 The mount cycle, honestly, with four terms

The candidate designs used a single 90 s or 180 s figure. The physical cycle is:

```
robot fetch + insert        ~15 s
load / thread / calibrate   60–120 s
locate to first target      20–90 s
    [ transfer ]
rewind to BOT               50–90 s     <- mandatory before eject; omitted by every candidate
unthread / unload / eject    ~25 s
robot return + shelve       ~15 s
                            ---------
non-transfer total          185–355 s
```

**`O = 265 s` is the planning figure; 355 s is the pessimistic bound. Basis: MODELLED, not measured.** It is the highest-leverage unmeasured constant in the document — a 45 % error in `O` moves the coalescing requirement by 44 % and plant output by ~23 % — and §16 item 1 makes measuring it the first commissioning task.

### 3.5 Wave economics, computed

One wave = one mount of one volume, sweeping `W` contiguous fragments in a single monotone pass, `W−1` repositions at 40 s, `O = 265 s`:

| W | delivered | drive-seconds | effective rate | duty | bytes/mount |
|---|---|---|---|---|---|
| 1 | 103 GB | 523 | 197 MB/s | 49 % | 103 GB |
| 2 | 206 GB | 820 | 251 MB/s | 63 % | 206 GB |
| **4** | **412 GB** | **1,416** | **291 MB/s** | **73 %** *(MODELLED per-mount ceiling — see note)* | **412 GB** |
| 8 | 825 GB | 2,607 | 316 MB/s | 79 % | 825 GB |
| ∞ | — | — | 346 MB/s | 87 % | — |

> **ANNOTATED 2026-09-19 by `eval/results/plant_sim.json`.** This table bounds a **single mount**; it is not a plant rate, and **duty is an output of placement and queue depth rather than a constant**. Measured at the simulated operating point (2,000 requests of 4 GiB over 24 h, 8 h deadlines, clustered, batched, media-ordered): **111.1 GB per mount, 46.5 % payload, 653.3 GB/drive-hour** — well below this row. Payload *rises* with offered load as deeper queues amortise each mount — **63.2 % at 19.5, 72.0 % at 39.1, 77.5 % at 78.1, 80.5 % at 156.3 TiB/day, all at 0 % late** — and breaks only at 312.5 TiB/day (82.1 % payload, 25.6 % late). On a scattered workload the same policy reaches only **12.3 %**. So 73 % duty is reachable, but only above the plant's own sustainable delivery and never without clustering. **Do not derive a plant rate from this row** (§14.1).

Compare the design of record's own decomposition (check 3): a 200 GB container read as six 33.3 GB symbols, one mount each, yields **126.6 MB/s**. STELE delivers **291 MB/s** at W = 4 — ~~a 2.3× improvement in the conserved resource~~ — from three changes that cost nothing: contiguous fragments, no racing (§8.5), and systematic direct reads (§8.3).

> **RESTATED 2026-09-19 (`eval/results/plant_sim.json`).** The mechanism is worth **more** than 2.3× and the absolute rate is **lower** than this section claims. Scheduling policy alone, holding placement fixed, is **9.4× in GB per drive-hour** (clustered reactive 69.5 → clustered batched and media-ordered 653.3). Placement adds a further **3.8×** (scattered 172.3 → clustered 653.3). Absolute delivered rate at the simulated operating point is **653.3 GB/drive-hour ≈ 180–195 MB/s** — the spread is the harness's own unit ambiguity, its "GB" being 2³⁰ in its request arithmetic and 10⁹ in its rate conversions — rising toward this row's 291 MB/s only at offered loads above sustainable delivery. **Keep the mechanism; drop 2.3× and drop 291 MB/s as a planning rate.**

**Target: W = 4, B\* = 412 GB per mount.** §14.2 shows that a second, entirely independent constraint — media load-cycle life — forbids W = 1 as well, and lands within 27 % of the same answer. *(2026-09-19: at the simulated operating point measured bytes-per-mount is **111.1 GB**, so §10.4's admission trigger fires there on its deadline clause, not its byte clause. The harness does not report bytes-per-mount above 2,000 requests, where payload reaches 80.5 %, so **whether B\* is reached at high load is UNMEASURED** — recorded, not resolved, and not refuted.)*

---

## 4. The locator

**56 bytes, fixed, explicit wire codec, big-endian, no struct serialisation, no padding field.**

```
Locator {
  volume_id   : u128    // RANDOM at label. Not a barcode. Not a hash of the serial.
  ordinal     : u32     // first parcel ordinal of the fragment; monotone within the volume
  parcels     : u16     // fragment length in parcels, including local parity
  code_epoch  : u16     // bumped by any re-coding; readers refuse to mix epochs
  leaf_root   : u256    // Merkle root over 8 MiB leaves of the stored ciphertext
}
```

A 96-parcel fragment has 12,288 leaves; a `prove` path is 14 hashes (448 B); a ranged read of `X` bytes verifies against `ceil(X / 8 MiB)` leaves and their paths.

**Deleted relative to the candidate designs, and why each had to go.** `offset` — derivable as `ordinal × PARCEL_BYTES`, and a non-authoritative hint inside an identifier is an equality bug waiting to happen. `length` — a constant times `parcels`; a field that can express a different size will eventually express one, and that destroys §3.1. `fmt` — lives in the volume label; a per-fragment format version implies a mixed-format read path that will never be exercised and will therefore be wrong. `gen` — `leaf_root` already detects position reuse and reports the correct verdict. `_pad` — four bytes of uninitialised process memory written to unerasable media is CWE-200, at ~3.9 MB across the plant. `site`/`domain` — properties of where a medium *currently is*, joined from the ~10³-row volume registry; denormalising them means shipping one cartridge rewrites every row for every fragment on it, which negates the entire point of the indirection. `verifier` as a flat digest — replaced by `leaf_root`, for the three reasons in §1.2(2).

**`volume_id` must be random**, not `H(serial ‖ epoch)`: LTO serials are vendor-structured and sequential, the joint search space is under 2⁴⁰, and cartridges are purchased in per-site batches — so a derived id is a brute-forceable institution-targeting map replicated into every locator in the federation. The Bareos `VolumeName` is `base32(volume_id)` and nothing else (§6.3).

**The Bareos coordinates are not in the locator.** `(VolSessionId, VolSessionTime, VolFile, VolBlock, FileIndex)` live in a mutable position row in the volume registry. Because `Maximum File Size = PARCEL_BYTES`, `VolFile` is monotone in `ordinal` by construction, so the position row is *derivable from* the ordinal and is a cache, not a fact. **`ordinal` is authoritative; `VolFile` is a cache of `ordinal`.** A Bareos catalogue rebuild therefore changes no locator anywhere.

**Formed** by `seal()`, never by the caller, never by `append()`. The ordinal is confirmed from the Storage Daemon's acknowledged job record after the session closes.

**Verified** with no key: read the leaf, recompute, check the path to `leaf_root`. The root covers ciphertext *as stored*, so a blind holder verifies with no key and no approval, and durability is severed from the authorisation path by construction rather than by policy.

**The root is supplied by the origin and compared at commit; it is never computed by the holder.** A holder that computes the digest over whatever it actually wrote produces a self-consistent locator that never fails a read check, so repair — which requires the fragment to be *detectably* bad — can never fire, and the sibling-recovery join becomes poisonable. `seal()` compares and refuses on mismatch. The fabric's integrity root is the origin-side per-chunk AEAD plus the manifest digest; `leaf_root` is a media-error detector and a possession challenge, not an authenticity claim.

**`code_epoch` is not optional.** Two LTO generations coexist for roughly four years of six, migration may re-code, and a reader that assembles fragments from two epochs gets a successful decode of garbage — every parcel verifies, because each leaf is a correct hash of its own bytes — detected only at the per-chunk GCM tag, after the mounts and the decode. Silent wrong data across a four-year window is the worst failure available here, and two bytes prevent it.

---

## 5. Layer 1 — the block plane over volumes

### 5.1 The SPI — ten calls

Synchronous and blocking against a volume the plant scheduler has already arranged to have mounted. There is no queue, no ETA, no job, no async in this layer: asynchrony is the plant scheduler's business one layer up (§10). That is what keeps the block plane an implementation rather than a system.

```java
// ---- attachment: the PLANNER moves media; the block plane attaches to a session ----
Result<Handle>        open(StorageId sd, VolumeId expected, Mode mode);   // READ | APPEND
Result<MediumReport>  close(Handle h);      // residual, health, faults — free, medium is loaded
Result<Recovery>      recover(Handle h);    // MANDATORY first call in APPEND mode

// ---- write: one durability barrier, and it is the naming event ----
Result<Provisional>   append(Handle h, ByteBuffer parcel, Hash leaf_root_hint);
                                            // exactly PARCEL_BYTES or refused
Result<Locator[]>     seal(Handle h);       // THE barrier: band parity, session close,
                                            // flush, confirm ordinals, compare roots
Result<Void>          abandon(Handle h);    // tombstone the extent; prefix is dead media

// ---- read: streaming, verified, range-capable within a fragment ----
Result<Void>          read(Handle h, Locator l, long off, long len, WritableByteChannel sink);
Result<Proof>         prove(Handle h, Locator l, long leaf, byte[] nonce);

// ---- recovery only; never on a hot path ----
Result<Stream<IndexEntry>> index(Handle h, Checkpoint at);

// ---- lifecycle ----
Result<Retirement>    retire(VolumeId v, Disposition d, RetireReason r, String token);
```

> *2026-09-19: the deduplication retirement changes nothing in this SPI.* The block plane never had a chunk id, a dedup query or a content-addressed lookup: it accepts opaque parcels of exactly `PARCEL_BYTES`, names them by ordinal and locator, and verifies them by leaf tree. Every retirement in that pass lands in the object layer above it. Recorded so a reader is not left hunting for block-plane edits that do not exist.

**`open` takes a storage identity plus an expected volume id, not a volume id.** The changer belongs to Layer 0; the block plane attaches to a session whose volume is already loaded, confirms the label matches, and refuses otherwise. That makes "synchronous against a loaded handle" literally true, is honest on all three media (a directory has no readiness concept), and produces the barcode ↔ `volume_id` binding as a by-product of a check that has to happen anyway.

**`read` is sink-driven, not `byte[]`-returning.** A 103 GB fragment cannot be a Java array (the 2³¹−1 ceiling, prerequisite P3), the tape path never has the fragment in memory, and a caller that wants a range must not pay for the whole.

**There is no `stat()`.** Every field a `stat` would return is either catalogue state (residual, sealed, writable) or requires a mount (`LOG SENSE` health, position). A placement solver that polls `stat` across candidate media spends drive-seconds to decide how to spend drive-seconds — at three candidates per fragment with a 10 % miss rate that is ~260 drive-hours per year answering capacity questions. Residual and health come back from `close()`, when the medium is loaded anyway and the refresh is free, and are exact because nothing else can have written to a WORM volume since. **No method on this SPI may cause a mount except `open`.**

**There is no `sweep()` / `list()` / `scan()` on the hot path.** A binding never discovers its own contents by traversing the medium. `index()` reads the sealed on-media checkpoint; full traversal is `bscan`, an operator-authorised last resort (§7.2), never a routine path.

### 5.2 `append` returns a provisional reference, and `seal` promotes it

A `seal` that mints all identities at once leaves a window — 96 parcels at 400 MB/s is ~258 s — in which the caller holds nothing durable and a crash orphans up to 103 GB of WORM with nothing naming it. On WORM there is no second chance to annotate it.

```java
final class Provisional { long ordinal; Hash leaf_root; long atMillis; }
```

~~`append` returns the real ordinal immediately~~ — **SUPERSEDED 2026-09-19 by this document's own §1.2(1) and §4**, and by the `Spool Data = yes` contract of §6.1: bytes are spooled and the Storage Daemon assigns position at commit, so no ordinal is knowable at `append` time. `append` returns a provisional reference with no position, journalled with `fsync` before the next parcel. A **write-intent row is committed to the ledger before the first byte**, so a crash leaves an explicit unresolved row rather than orphaned media — that property, and the crash-window argument opening this section, are unchanged and are why the provisional exists at all. `seal` is the naming event: it promotes `PROVISIONAL` to `DURABLE` and the ordinal is confirmed from the Storage Daemon's acknowledged job record after the session closes. A locator not returned by a successful `seal` does not exist.

> **The `ordinal` field on `Provisional` above is a defect of this correction and must be removed or re-typed before the SPI is built.** Named, not redesigned here: no replacement field name is invented.

> **Measured** (`eval/results/fsync_cost.json`, 2026-09-19): the barrier costs **0.737 ms per call on Linux node-local storage** and is per-call, not per-byte. At 96 parcels per fragment that is ~71 ms of journal barrier against a ~258 s fragment write — 0.03 %, so the per-parcel journal force is affordable as specified. The arithmetic assumes a node-local journal: on the shared project filesystem the same call measures ~29 ms, ~2.8 s per fragment or ~1.1 %, still small but only because the fragment write on that path has itself collapsed to 8.6 MB/s. Where the ledger journal lives is not specified here.

`abandon` writes a tombstone naming the abandoned extent, so `index` and any later scan skip it deterministically and the orphaned bytes are charged to capacity (§14.4). An abandoned extent is not free space and must never present as headroom.

**Idempotency.** Every write job carries a caller-supplied idempotency key, recoverable at index time, so a retry after an ambiguous failure is detectable rather than duplicated on unerasable media.

### 5.3 Faults are a return type, not an exception

```java
enum Fault { NONE, RECOVERED, MEDIA_TRANSIENT, MEDIA_PERMANENT,
             HARDWARE, END_OF_MEDIUM, FORMAT, TORN_TAIL }

final class Result<T> {
    T value; Fault fault; int senseKey, asc, ascq, retries; long atOrdinal;
}
```

Bareos classifies and acts; we still need the classification, because four failures demand four different *placement* actions: reposition and retry (Layer 0's business); stop scheduling writes to this volume and raise its scrub priority; hand this fragment to the repair planner; **quarantine this drive and do not condemn the cartridge**. Misclassifying the last as the third condemns healthy media and triggers a multi-week rebuild against a drive fault.

The ledger keeps a rolling fault histogram per **(drive, volume)** pair. The cross-tabulation is the only thing that separates a bad drive from a bad tape; it is two LSM tables and a nightly attribution pass, not a product; and it is the best operational engineering in the programme. Two rules make it work: **exactly one TapeAlert reader** (flags are cleared on report, so racing readers mis-attribute), and **two distinct drives must implicate a volume before it is retired**.

### 5.4 `recover` and `retire`

`abandon()` models the failure where the writer decides to stop. `recover()` models the one where the writer *stops deciding*: the host dies mid-session, no tombstone is written, and a possibly-torn extent sits on media that cannot be overwritten.

```java
final class Recovery { long lastSealedOrdinal; Fault tail; long tornAt; boolean resumable; }
```

Contract: a fragment is adoptable iff its trailer verifies and its `leaf_root` matches the ledger's provisional row or the last index checkpoint; everything past the first bad trailer is abandoned and the append cursor advances past it. The durability point is defined narrowly and in one place — **parcels, band parity, trailer, session close, flush, ordinal confirmation, root comparison, and only then are locators returned** — so a torn tail costs one fragment (~103 GB, ~0.34 % of a cartridge), never a cartridge.

`retire` is the only call that destroys 30 TB irreversibly, so it is token-authorised (`CryptoBox.verifyToken`, carrying op, extent-set hash, expiry and authorising user), journalled, and refused while any live placement row references the volume unless a drain campaign has completed. It declares what it achieved:

```java
enum Disposition { RELEASE, PURGE }
enum Erasure     { ERASED, KEY_DESTROYED, MEDIUM_DESTROYED, LOGICAL_ONLY }
final class Retirement { Erasure achieved; String attestationId;
                         long reclaimedBytes; long unreclaimableBytes; long mediumExpiryEpochMs; }
```

A directory returns `ERASED`. A raw device returns `ERASED` only if it actually overwrote, `LOGICAL_ONLY` otherwise — TRIM/UNMAP is advisory and on many devices guarantees nothing. WORM tape returns `KEY_DESTROYED`: `K_idx(v)` is destroyed so the on-media index is unreadable, and the parcels remain, still opaque under their object keys *(2026-09-19: was `K_rdom`; retired, rename only)*. Reaching `MEDIUM_DESTROYED` is a separate, attested, two-person physical act recorded as a `DestructionRec` parallel to `RedactionRec`, with the cartridge serial and a disposal certificate id. **WORM status must have been read from the medium at commissioning, never from a config file**, or the system can tell the governance layer that a redaction is physically permanent when the bytes are erasable.

---

## 6. Layer 0 — the Bareos contract

Everything in this section is normative configuration. Every item is a place where a default silently destroys a property this design depends on.

> **Verification obligation.** The field lists and directive names below are from knowledge of the Bareos media format, not from an install. They are structurally right; the exact spellings and the exact set of on-media cleartext fields **must be confirmed against the deployed version before the first cartridge is labelled**, by the commissioning lint in §6.3. On WORM this is one-shot.

### 6.1 Streaming, framing and encryption

| Directive | Value | Why |
|---|---|---|
| `Maximum Block Size` | **1–2 MiB**, set on Device *and* Pool | The 64 KiB default will not keep a 400 MB/s drive above the ~112 MB/s speed-match floor through a network-fed spool. Below it the drive backhitches and **every rate figure in this document is void.** Recorded in the volume label and **irreversible per volume** — changing it later makes written volumes unreadable. |
| `Maximum File Size` | **1 GiB = `PARCEL_BYTES`** | One parcel = one Bareos file = one filemark = one hardware-locatable `VolFile`, so `VolFile` is monotone in `ordinal` and a ranged read is expressible in a bootstrap record. |
| `Maximum Concurrent Jobs` | **1** on every WORM device | Multiplexing interleaves blocks from several jobs onto one volume and shatters fragment contiguity — up to 62× on the read. Concurrency belongs on the spool disk, not on the tape. |
| `Spool Data` | **yes**; `Maximum Spool Size` ≥ 2 × fragment per device | Mandatory (§8.7): the raw federation feed is ~5.8 MB/s, twenty times below the speed-match floor. |
| Hardware compression | **OFF** | Destroys the fixed-parcel property (§3.1). Ciphertext not compressing is the weaker argument. |
| SD `Auto Deflate` / `Auto Inflate`, FD software compression | **OFF** | Same reason; these are the two that get missed because they are not the drive. |
| Bareos PKI data encryption; drive encryption (`scsicrypto` / library-managed) | **OFF**, asserted by read-back | Each creates a second key-custody domain weaker than the Shamir *t*-of-*n* one, and a restore path must never be able to depend on it. |
| `Alert Command` | exactly one reader, writing to our ledger | §5.3. |

### 6.2 Fencing the deletion engine

Bareos is architected around retention and recycling. On WORM the physical delete fails; the dangerous half is the catalogue half, where pruning silently discards the `Job` and `JobMedia` rows that carry the position index, producing a catalogue loss with no media loss — bytes intact and unreachable except by a 20.8-hour-per-cartridge `bscan`. It is triggered by a default, not by an operator, and it surfaces a year later when a pool's config drifts during an upgrade.

Required on every WORM pool: `Recycle = no`, `AutoPrune = no`, `Purge Oldest Volume = no`, `Volume Retention` ≥ 100 years, `Job Retention` and `File Retention` ≥ the archive horizon, `Volume Use Duration = 0`, `Action On Purge` never `Truncate`, volume status set to `Used`/`Full` on seal.

**Because config drifts, policy is not enough.** The commissioning run records an expected configuration hash in the volume registry, and the ledger-side submitter **reads the live pool and device configuration before submitting any job and refuses on deviation**. A volume-status transition toward `Recycle` is a fabric alarm, not a state change.

### 6.3 The naming contract, and the lint that enforces it

Bareos's on-media format is deliberately self-describing — that is how `bscan` works. Permanent cleartext therefore includes, at minimum: the volume label (`VolName`, `PrevVolName`, `PoolName`, `PoolType`, `MediaType`, `HostName`, `LabelProg`, version, label timestamps); start- and end-of-session labels per job (`JobId`, `JobName`, `ClientName`, `FileSetName`, `JobType`, `JobLevel`, session times, and at EOS `JobFiles`/`JobBytes`); per-block headers (`BlockNumber`, `VolSessionId`, **`VolSessionTime`, a unix timestamp**); and file attribute records carrying the filename we supply and its stat data.

Every one of those is unerasable for the life of the medium and is outside the reach of any key destruction. The contract is therefore that **no string reaching Layer 0 may be a function of plaintext, and the ones that cannot be removed must carry zero bits.**

| Field | Required value |
|---|---|
| `VolumeName` | `base32(volume_id)` — random 128-bit, nothing else |
| `PoolName` | `p-<retention class ordinal>-<n>` |
| `ClientName`, `FileSetName`, `JobName` | fixed constants from a non-identifying namespace; **never** a lineage, institution, study, subject, modality or date |
| `HostName` | overridden to an opaque per-site token |
| attribute filename | `<volume_id hex>/<parcel ordinal>` and nothing else |
| job granularity | **one job per fragment**, so `FileIndex` 1..96 maps to parcel ordinal and `JobFiles`/`JobBytes` are constants carrying zero bits |
| ingest batching | one job epoch per day, so session timestamps coarsen toward a day |

The submitter enforces this as a **hard refusal in code**: any string outside `^[A-Za-z0-9._/-]{1,64}$`, or any field derived from a lineage, subject or study identifier, fails the submission. A convention here will be violated; a refusal will not.

**The commissioning lint, which is what makes any of this checkable.** Write a scratch cartridge through the real profile. Run `bls` and `bextract` over it and a raw `dd` of the leading blocks. Dump every cleartext octet Bareos placed on the medium and diff it against an allowlist. Fail on any hit for a study name, institution name, MRN pattern, calendar date, or any timestamp field that is not the volume's own write epoch. **This lint is a gate in the ship chain, re-run at every Bareos upgrade and at every generational migration**, because the on-media format is version-dependent and the decision is one-shot.

The irreducible residual, declared rather than assumed absent, is in §13.2.

### 6.4 Two catalogues, and which is authoritative for what

- **Ours** is authoritative for *extent*: which fragments exist, what stripe they belong to, what they contain, and where they belong. It is quorum-committed and replicated to all three sites.
- **Bareos's** is authoritative for *position*: `VolFile`/`VolBlock`. It is per-site Postgres.

Because `Maximum File Size = PARCEL_BYTES` makes `VolFile` monotone in `ordinal`, position is *derivable* from extent. Therefore **we can drive a restore with Bareos's catalogue empty**, by handing the Director a bootstrap record we generated ourselves. That is the structural point of the split: their catalogue is a cache, not an authority, and its loss costs a BSR regeneration rather than a 27-day plant-wide `bscan` campaign.

Three consequences, all normative. (i) Capture `(VolumeName, VolSessionId, VolSessionTime, VolFile, VolBlock, FileIndex)` into our quorum-committed ledger at every seal. (ii) Back up each site's Bareos catalogue into the fabric as an opaque container under a site key, and bring it inside the erasure discipline — it is a placement copy and a second metadata archive. (iii) Name an owner for reconciliation, whose job is to *detect divergence*, never to silently pick a side.

### 6.5 What we are not taking from Bareos

Its catalogue as source of truth; its `File`/`Path` attribute tables as an index; its retention, recycle and purge machinery; its `FileSet`/`Client` model as anything but two constants; its job-level restore semantics as a consumer-facing API; its compression; its encryption; and its notion that a purged volume is an erased volume. **A purged volume is not an erased volume and must never be reported as one.**

---

## 7. The volume index, and rebuild from media alone

### 7.1 On-media structures

Three structures. Nothing else is ever written.

```
PARCEL                        exactly 1 GiB, always
  cleartext head  24 B        magic "STELE\0\2" | parcel ordinal u32 | flags u8 | crc32
  body                        ciphertext ‖ CSPRNG padding to PARCEL_BYTES

FRAGMENT TRAILER              one per seal; LENGTH IS A CONSTANT — every field below is
                              fixed-length or a fixed-length array (§18.3)
  cleartext        16 B       magic | trailer ordinal u32 | crc32
  sealed (AEAD under K_idx(v), iv = 0^32 ‖ volume_id[0:4] ‖ ordinal,
          aad = volume_id ‖ ordinal ‖ code_epoch):
        { stripe_id, fragment_i, k, m, code_epoch, coding_id, j, class,
          class ∈ {DATA, MANIFEST, JOURNAL, PARITY},   // PARITY added 2026-09-19, §18.3
          leaf_root, leaf_hashes[12288],            // 393 KB; makes `prove` a single-leaf read
          xorbs[1344] { xid 16 B, parcel_ordinal u16, offset u32, len u32, pad → 32 B },
                                                    // 43,008 B; 84 GiB payload / 64 MiB = 1344 EXACTLY;
                                                    // ABSENT sentinel for a short fragment
          res_gran u8, res_scope u8,                // {ABSENT,OBJECT,POOL_GROUP}, {VOLUME}
          res_ords[84] u32,                         // 336 B; ONE SLOT PER DATA PARCEL, positional
                                                    // SPARSE OPAQUE ORDINALS: res_ord(i) =
                                                    //   PRP(K_ord(v), i) over [0, 2^32-1)
                                                    // 0xFFFFFFFF = ABSENT. Never subject ids,
                                                    // never dense, never in write order.
          idempotency_key }

INDEX CHECKPOINT              at ~1/4, 1/2, 3/4 of the medium and at end of data; cumulative
  cleartext        16 B       magic | checkpoint ordinal u32 | crc32
  sealed under K_idx(v):      { volume_id, format_epoch, checkpoint_seq,
                                entries[ { ordinal, parcels, leaf_root, class, coding_id,
                                           stripe_id, fragment_i,
                                           xorbs[1344],            // REQUIRED: §7.3 promises the
                                                                   // xid set and `place` is this
                                                                   // array inverted
                                           res_gran, res_scope, res_ords[84] } ],
                                lineage_heads[ { lineage_handle, head_vid, head_seq, head_term } ],
                                prev_checkpoint_mac }
```

Size, **recomputed 2026-09-19 and corrected in two independent places** (§18.2): **291.04 → 291
fragments per 30 TB cartridge** — pure geometry, invariant under every granularity question —
**43,404 B per index entry** (56 fixed + 2 `coding_id` + 2 discriminators + 336 `res_ords` +
43,008 `xorbs[]`) → **~12.63 MB per cartridge**, *constant at every object size*.

The old "~96 B per entry → ~28 KB, one short read" was low by ~470× **before any question of
object granularity arose**: it omitted `xorbs[]`, while §7.3 promises the rebuild yields the `xid`
set and the `place` ledger it must rebuild is exactly that array inverted. "One short read" is
restated honestly as **one locate and one 12.63 MB contiguous streaming read — 31.6 ms of transfer
against a 265 s mount, 1.2 % of the 1 %-of-mount budget.** It is one *block* at no object size and
never was.

Four format decisions, each of which was a failure in a candidate design.

- **Checkpoints at longitudinal positions, not cumulatively at every seal.** Writing the full index at each of ~291 seals is LTFS index rewrite with an append-only spelling. Two copies a few centimetres apart on one wrap share essentially every physical failure mode — creases, edge damage, contamination streaks and head-clog bursts run for metres. Four checkpoints on different wraps cost nothing (the head passes those points during the write pass anyway) and cap the degraded-path cost at a quarter-cartridge sweep. **MAM carries the position and generation of the latest checkpoint, read at load with no tape motion**, so recovery is a direct locate rather than a space-to-EOD; MAM also carries the observed block size and format version, and a MAM-versus-medium disagreement is a refusal to write.
- **The checkpoint chain is MAC'd.** WORM refuses overwrite; it does not refuse *append*. An adversary with physical possession of a cartridge and a drive can append a checkpoint whose index omits entries, and an unauthenticated rebuild silently yields a short catalogue. `prev_checkpoint_mac` plus strictly monotone `checkpoint_seq`, cross-checked against the registry's high-water mark, closes it. Media are authoritative for content; the registry is authoritative for extent; a mismatch is an integrity alarm, not a rebuild.
- **`class` and `res_ords` are in the sealed half and are load-bearing.** `class ∈ {DATA, MANIFEST, JOURNAL, PARITY}` is what makes the *catalogue tier* rebuildable from media rather than only the bytes (§7.3); `PARITY` was added 2026-09-19 because a global-parity fragment holds no objects and cannot name residency on two peer volumes, and without the enum value one third of the plant could not be joined to the journal at all (§18.3). `res_ords` is what lets a media-only rebuild join the key-destruction journal and mark dead parcels (§11.1) — without it, repair, scrub and migration maintain provably unopenable noise forever. It is a **fixed-length positional vector, one slot per data parcel**, not a set: the structure's length is therefore never a function of plaintext, its size is independent of the object-size distribution and of the §8.4 packing decision, and the per-volume ordinal namespace is bounded at 194 × 84 = 16,296 values, four orders below `u32`. A per-object *set* would have made trailer and checkpoint length a cleartext object count (D-2's `ehdr_len` defect at two new sites) and would have overflowed a dense `u32` ordinal at a mean object size of 4,074 B. **Decided in §18.3.**

> **HOLE OPENED 2026-09-19, CLOSED 2026-09-19 — DECIDED IN §18.3.** The hole asked for the
> objects-per-domain ratio and declared it unquantified. That ratio is real but does not enter the
> arithmetic and cannot be measured into the answer, because the redaction domain is no longer a key
> and no document ever counted domains. The variable that enters is **ρ = 1 + F_pay/S̄, residency
> units per fragment** (§18.1), and the decision is to write a structure that does not depend on it:
> `obj_ords` is replaced by **`res_ords`, a fixed-length parcel-resolution residency vector**, with
> ordinals drawn from a custody-keyed permutation over a per-volume namespace. All three flagged
> figures are recomputed in §18.2 — two of them (291 fragments; the rebuild time) do not move at any
> granularity, and the third moved for a reason the hole did not name. The `DENSE OPAQUE ORDINALS`
> guarantee is **retired and replaced** by `SPARSE OPAQUE ORDINALS, the image of a custody-keyed
> permutation`: density and write-order adjacency were the disclosures, not fineness, and both are
> now deleted at zero cost. The custody-held ordinal map is specified, bounded at ≤ 16,296 rows per
> volume, and given a destroy path (§18.3).
- **No `xid`, no `bid`, no length, no timestamp, no rdom identifier and no name in any cleartext field.** A globally stable content identifier in a cleartext header is a confirmation oracle that survives the erasure it documents.

### 7.2 Cost of rebuild, three modes

**Corrected 2026-09-19 (§18.2, §18.8). Four modes, not three, and the index row used the wrong `O`.**
The planning `O = 265 s` is an average over read targets distributed along the tape. MAM points at
the *latest* checkpoint, which §7.1 places **at end of data**, so the index-mode mount selects the
maximum of *both* tape-motion terms by construction: the locate runs to the far end (90 s) and §3.4's
mandatory rewind is proportional to how far the read drove the head (90 s). `O_EOD` = 15 + (60–120)
+ 90 + 90 + 25 + 15 = **295–355 s**. Transfer is 31.6 ms at 12.63 MB and does not appear.

| Mode | Per cartridge | Whole plant (240 cartridges, 9 drives) |
|---|---|---|
| **Index, registry surviving** (MAM pointer → one locate → 12.63 MB read) | **~295–355 s** *(was ~265 s)* | **~2.19–2.63 h** *(was ~2.0 h)* |
| **Index, chain-verified** (registry lost with the catalogue; the `prev_checkpoint_mac` chain must be walked — 3 backward quarter-cartridge locates at 20–90 s) | ~355–625 s | ~2.6–4.6 h |
| **Degraded** (MAM lost; space to a checkpoint) | ~325–385 s | ~2.6 hours |
| **Partial sweep** (latest checkpoint unreadable; fall back to the ¾ checkpoint and sweep the final quarter — the mode the four-checkpoint design exists to bound, and which appeared in no table) | **5.21 drive-h** | **~5.8 days** |
| **Full sweep** (`bscan`; all checkpoints unreadable) | 20.8 drive-hours | ~23 days |

**Registry survival is a stated precondition of row 1, not an assumption.** §7.1's anti-truncation
defence cross-checks `checkpoint_seq` against the volume registry's high-water mark, and rebuild-from-
media is the catalogue-loss case. §8.8 replicates the 6.7 MB `loc` ledger and the ~10³-row volume
registry to every site as a quorum-committed file; if that survives, row 1 applies. If it does not,
row 2 is the operational number and the MAC chain is the only remaining anti-truncation evidence.

**The index read is not what these figures measure.** Transfer is 31.6 ms against a 265–355 s mount,
and it stays under 1 % of the mount cycle up to ρ = 1.8 × 10⁶ residency units per fragment even under
the *rejected* variable-length set (§18.2). Rebuild is mount-bound, not index-bound, at every
granularity. The index mode is the operational path; the sweep is the last resort it should always
have been. Robot serialisation (80 cartridges × 2 moves × ~15 s ≈ 40 min per site) overlaps the drive
time and does not bind.

> **Owed, and priced nowhere (§18.8).** Every row above prices the *locator* tier only. §7.3 requires
> that full recovery additionally follow `class = MANIFEST` parcels to the cnode closure and
> `class = JOURNAL` parcels to the journal chain. A cnode closure is a graph walk, not a sweep, on a
> substrate with 265–355 s access latency, so at closure depth *d* with perfect per-level batching it
> costs *d* × the row-1 figure and without batching it is unbounded. **A closure walk that issues
> mounts as it discovers references must be refused by construction**, exactly as §8.5 refuses racing
> and for the same reason: here a wasted traversal costs a mount. Manifest bytes per cartridge,
> discontiguous manifest run count and closure depth are unmeasured.

### 7.3 What rebuild recovers, and what it deliberately does not

A rebuild yields `(locator, class, coding_id, stripe_id, fragment_i, xid set with its parcel offsets, res_ords)`. It **never** yields a plaintext, a name, a subject, a size that means anything, or a time finer than the write epoch. Those never existed on the medium. *(2026-09-19: the `xid` set is named here and must therefore be carried by the index checkpoint, not only by the fragment trailer — §7.1 previously omitted it from the checkpoint entry while §7.3 promised it, and `place` is exactly that array inverted. A checkpoint that omitted it would force a 291-locate trailer pass at ~3.2 h per cartridge to satisfy this line.)*

- **Catalogue loss + custody intact → full recovery.** Read the index of every volume, unwrap `K_idx(v)` from custody, rebuild the placement ledger, then follow `class = MANIFEST` parcels to the cnode closure and `class = JOURNAL` parcels to the journal chain. This is the correction that makes "the catalogue is a cache of the media" *true* rather than nearly true: without a `class` byte and a WORM home for the cnode tier, every byte survives and the dataset does not — you recover locators and cannot name a single slide.
- **Catalogue loss + custody loss → unrecoverable, by design.** That is the correct answer, not a bug. It is also why §12.5 makes proactive resharing a prerequisite rather than an improvement.
- **After a shred → the parcels are still enumerable, still verifiable, still occupying media, and permanently unreadable.** Enumeration after a shred discloses "N opaque 1 GiB parcels in M fragments, some of which are marked dead by ordinal." That is the whole disclosure budget. *(2026-09-19: this budget SURVIVES the `K_rdom` retirement only because of the §18.3 decision. A per-object `obj_ords` set would have falsified it outright — it would have disclosed a per-fragment object count, a co-residency partition over the volume's whole population, and, joined to §13.2's conceded per-volume second-resolution timeline, an object-arrival census. `res_ords` discloses `min(ρ, 84)` distinct ordinals per fragment, capped by geometry at ~6.4 bits, to a custody-quorum holder only; the ordinal is the image of a permutation that holder cannot invert without `K_ord(v)`, and the catalogue row that resolves it has had its identity field destroyed by the shred. §18.5.)*

### 7.4 The per-volume index key, and the claim it must not be sold with

```
K_idx(v) = HKDF(K_custody_root, "idx" ‖ volume_id)
```

Derived, never stored; `K_custody_root` is the existing Shamir *t*-of-*n* root under proactive resharing. Compromise is bounded to one volume; rotation is a re-share of the root, not a rewrite of 240 cartridges; there is no new custody domain and no per-cartridge key population.

**This rejects both the owner's candidate resolution and the candidates' counter-proposals, for three separate reasons, and all four candidate designs independently reached the same verdict:**

1. **It is not a shred unit, and saying it is would be the design's one dishonest claim.** Parcels are encrypted under their objects' keys *(2026-09-19: was `HKDF(K_rdom, "chunk" ‖ sid)`; `K_rdom` retired by `eval/results/ckpt_dedup_results.json` — a rename, flagged so the sweep does not weaken this section)*. Destroying an index key destroys *recoverability*, not *confidentiality*: anyone holding the object keys who reads the volume sequentially still decrypts every chunk. It buys a cost multiplier — a 28 KB read becomes a 20.8-hour sweep — and nothing else. **It must never appear in a compliance document as an erasure.**
2. **Making it a real shred unit would be worse.** That requires encrypting parcels under it, which collapses shred granularity from per-subject to per-cartridge *and* creates a second custody domain weaker than the Shamir one — the identical objection that correctly rules out LTO hardware encryption.
3. **A per-cartridge key population is a new ten-year failure mode.** 240 independently split keys against a custody scheme with no resharing and ~5 %/yr share loss makes the archive's dominant risk worse in exchange for compartmentalisation that ~~a one-line HKDF derivation already provides~~ **per-object keys already provide more finely** *(2026-09-19: the HKDF leg is struck with `K_rdom`; the conclusion survives a fortiori on the custody-risk leg alone, whose arithmetic — n=12, t=7, 5 %/yr share loss, P(≥7 of 12 survive) ≈ 0.66, ~34 % of ten-year-old citations undecryptable — is untouched by any measurement)*.

Equally rejected: a **single fabric-wide, decade-lived index key**. Because it seals footers on write-once media it can never be rotated for the life of every cartridge already written, its compromise is unremediable and global, and its loss costs a full sweep of the entire plant. Derivation is what makes compartmentalisation and rotatability coexist.

**And the index is also written into the fabric as an ordinary erasure-coded `class = MANIFEST` parcel.** A per-volume index that exists only on the volume it describes is a single point of failure on the medium it is insuring. This, not a sibling-verifier cross-index, is the recovery path: it recovers the *full entry* rather than an identity join, and it is exercised on every ordinary read of the manifest tier rather than only on the night it is needed.

> **Cost restated 2026-09-19 (§18.2), and the "one parcel" property is gone.** It costs **12.63 MB per
> cartridge**, not ~28 KB — **3.03 GB of payload plant-wide, 5.20 GB of media at the 1.714× combined
> rate, ~5 parcels.** Because §3.1 fixes the parcel at exactly 1 GiB and §5.1 makes the parcel the
> unit `append` accepts, the floor is `max(1 parcel, ceil(1.714 × 240 × I / 1 GiB))` and the in-fabric
> index is no longer a single self-locating object. It therefore needs a **bootstrap root whose
> locator is replicated with the 6.7 MB `loc` ledger** (§8.8 already quorum-commits that to every
> site), or the recursion "you need an index to find the index" terminates on WORM. State the
> batching policy with it: batching 240 indexes into one write lags cartridge finalisation by up to a
> `seal_deadline`, and that lag is the exposure on the structure that exists as insurance.

---

## 8. Layer 2 — distribution

### 8.1 Coding

Two layers, all parity computed at commit while the stripe is spool-resident, never lazily and never from tape. Lazy parity costs `k` mounts per stripe, recurring on every width change, class promotion and site addition.

- **Local, intra-volume:** systematic RS(j, 4) over 1 GiB parcels, `j ≤ 28`, contiguous within a band. **1.1429×.** Repairs a localised media defect at **zero external mounts and zero wide-area bytes**, which is the only repair this plant can afford and is the dominant failure mode. Stripe contiguity is a durability requirement of the format, not an optimisation: a band written as one uninterrupted run repairs one parcel in 75 s; an interleaved band costs 75 s plus 27 repositions, a 16× swing on the operation the layer exists to make cheap.
- **Global, across sites:** systematic RS(2, 1) — 2 data fragments + 1 parity fragment, one per site. **1.5×.** With `m = 1` the parity is XOR; no Galois field is needed on the global path.

**Why `k` is minimal.** With `D` failure domains and one fragment per domain, site tolerance is `D·(1 − k/n)`, which is *independent of `k`*. At `D = 3` and a 1.5× rate, RS(2,1) and RS(6,3) have identical capacity and identical site tolerance — and RS(6,3) costs 6 mounts per stripe where RS(2,1) costs 1–2. On a mount-bound plant, **minimal `k` at the target rate, always.** Wide codes buy overhead reduction at fixed `m`; at three domains that trade is unavailable, so the width is pure loss. This is why RS(5,4), RS(6,3), RS(6,4) and k=6 geometries are all rejected, and why 1.806× and 1.9125× do not appear anywhere in this document.

Plain Reed–Solomon over GF(2⁸), not RaptorQ: our geometry delivers exactly zero decode overhead, and at RaptorQ's published ~10⁻² failure at zero overhead a site loss silently loses ~1 % of the archive with every surviving cartridge in perfect condition.

### 8.2 Placement

```java
Placement solve(PlaceReq r) throws Unsatisfiable;

PlaceReq { int k, m; DomainKey origin;                 // excluded
           Class cls { int min_domains; Set<Jurisdiction> allowed;
                       LatencyClass latency; Instant retain_until; }
           Set<DomainKey> exclude; }                    // repair: domains already holding
Placement { Target[] n; long est_write_drive_seconds, est_repair_drive_seconds, est_wan_bytes; }
```

Rules, in order: one fragment per failure domain; refuse loudly with arithmetic if `distinct(domains) < k+m`, never downgrade silently; **fragment role rotates per stripe** (D0→A, D1→B, P→C, then D0→B, …) so read load and degraded-mode cost spread evenly; then choose the volume within the site by cohort affinity (§8.4), not by residual.

There is **no weighted-random sampler on the tape tier.** At three domains the choice is not "which nine of fifty" but "which volume at each of three", a deterministic decision. A sampler is CRUSH furniture imported into a problem with no sampling in it. The sampler belongs, if anywhere, to the disk tier across ~50 institutions, and the two are named solvers, not one interface pretending to be general.

**There is no rebalancing.** Placement changes at exactly three moments: repair, class change, media migration. A joining resource receives only new stripes and moves nothing; a leaving resource marks its volumes `RETIRED` and its stripes enter the repair queue oldest-degraded-first under budget. Over a decade the fabric drifts onto new hardware by attrition, which is the cheapest possible policy when the alternative is mounts.

### 8.3 DIRECT and DECODE: the two read strategies

Because the global code is **systematic with contiguous data fragments**, a parcel lives entirely inside exactly one data fragment at exactly one site. Therefore:

- **DIRECT** — one fragment, one site, **one mount**, no decode, no cross-site traffic, no quorum of fragments. This is the common case and it is the single largest cost saving in the design.
- **DECODE** — read the other data fragment and the parity fragment and XOR. Used only when the direct fragment is unreachable or fails its leaf check.

The place row therefore *must* carry intra-fragment position, or the design throws away its own upside and the minimum read becomes the stripe:

```
place : xid -> { stripe_id, frag_i, parcel_ordinal, offset, len, created_seq, created_term }
```

**A site outage converts ⅔ of reads from DIRECT to DECODE** — two mounts at two sites plus a WAN leg — because ⅓ of stripes have D0 there, ⅓ have D1 and ⅓ have P. That repricing must be visible in `prospect` before a consumer commits, not discovered at the mount.

### 8.4 Packing: the largest lever, and it is a write-time decision

Container membership decides mount cost, it is chosen once, and on WORM it is irreversible. It must therefore be decided by co-access, **above the encryption boundary where names still exist**, and handed to Layer 2 as pre-formed opaque parcels. Layer 2's blindness is genuine because the packer, not the holder, does the grouping.

```java
append(a, parcel, leaf_root_hint, affinity_key)   // affinity minted by the packer
```

Three rules, in precedence order, and the precedence must be written down because they conflict:

1. **Parcels are shred-unit-pure**, or pooled with a declared coarser shred granularity. ~~Cross-rdom deduplication is impossible by construction (§12.3), so mixing domains in a parcel buys literally nothing~~ and costs three things: `live_fraction` becomes uncomputable so reclaim has no reachable trigger; the blast radius of a mistake becomes hundreds of unrelated subjects; and pin amplification rises. Padding cost is ½ parcel per run — ~6 % at 8 GB/subject imaging, ruinous at 80 KB/subject clinical notes — so `packing: pure | pooled(n)` is a per-lineage declaration with the arithmetic published at ingest, not a global constant.

  > *2026-09-19: the struck clause cited a premise retired by `eval/results/ckpt_dedup_results.json`. The rule survives unchanged on its other two grounds, which were always the load-bearing ones — `live_fraction` computability and blast radius. §12.3's impossibility argument itself survives its own retirement and is where the cross-reference now points.*
  >
  > **HOLE opened 2026-09-19, recorded not filled.** With `K_rdom` retired the purity unit becomes the **object** rather than the redaction domain. Purity was affordable because a domain aggregated many objects; at object granularity the ½-parcel padding is charged per object, so **pure packing is ruinous for every small-object population and `pooled(n)` becomes the default rather than the exception** — which means the three costs this rule names as the price of pooling are now paid **by default**, not by exception. The packing unit and the shred unit must be re-separated by something, and `K_rdom` was that something. Nothing replaces it. **Not designed here.** Note also that `pooled(n)` is the same mixing that `BAREOS-RECOMMENDATION.md` §5 offers as the partial mitigation for its write-timestamp concession, so the two decisions are now coupled and must be costed together.
2. **Consent-unit runs are interleaved across the fragment and the volume, never cohorted.** Cohort packing makes physical adjacency a function of redaction domain, so after a shred the contiguous run that is never read, never repaired and dropped wholesale at migration *is* the domain — inferable by an operator, a blind holder or a subpoena, with no key, from a layout that cannot be changed for 7–10 years. The reclamation benefit it was bought for is ~1 %/yr of dead space, priced in §11.2 as not worth buying. Concentration, if wanted, is taken at migration time when the output layout can be chosen after the shreds are known.

  > **Incomplete as priced, 2026-09-19.** The disclosure argument above and the ~1 %/yr figure are untouched by any measurement and both stand: §11.2 derives ~1 %/yr as the *dead-space accrual* rate driven by the withdrawal rate, and it remains correct for what it prices. What is wrong is that the rule is **incomplete**. It omits a second, far larger cost it never considered: `eval/results/plant_sim.json` and `eval/results/plant_contention.json` price co-occurrence clustering at **3.8× in GB per drive-hour (172 → 653)** and at the difference between **11.9 PB/yr scattered and 45.0 PB/yr clustered** delivered capacity. What rule 2 forbids is clustering *by redaction domain specifically*, while clustering *by co-access* is now mandatory. **Where the consent unit and the co-access unit coincide — longitudinal clinical data, where a read is a subject — these are one decision, it is irreversible on WORM, and this document does not resolve it.** Provenance: both figures come from a simulated plant with synthetic cartridge assignment; `plant_sim.json` `model_limits` states that real co-occurrence must be mined from an actual request log.
3. **Successive stripes of one cohort share volumes.** This is what makes a sequential read 1 mount instead of 1,000. Expressed as a Bareos pool per (retention class, cohort band), so the SD's own volume selection produces the contiguity without any volume being held open.

**Packing quality is a measured, published number** — fragments touched per unit of bytes wanted, against the ideal — recorded per version, because a bad packing decision is permanent and must be visible before it is felt.

**Sample-shaped reads are refused, not served.** A uniform `p`-sample of a lineage touches `1 − (1−p)^c` of its packing units; at fragment granularity any sample touches essentially all of them. `SAMPLE` over an unclustered lineage returns `SAMPLE_ORTHOGONAL_TO_PACKING` with the arithmetic attached, and the offered rewrite is a derived, sample-ordered lineage — which is the mechanism ENTAIL already provides.

### 8.5 No racing

Hedged requests are free where a discarded request costs a socket. Here it costs a mount, and a cancelled tape read does not return the drive early — the cartridge still has to rewind and unload. Issuing `n` to take `k` therefore wastes `(n−k)` full mount cycles per stripe.

**The planner selects `k` deterministically at plan time** by predicted cost against the plant calendar: already-mounted volumes first, then queue depth, then WAN cost. It commits and cancels nothing. Hedging is retained only for fragments whose declared `latencyClass` is disk- or cache-resident, where speculation is genuinely free.

### 8.6 Repair, and what it must never do

```java
List<RepairTask> plan(Degraded d, Budget b);   // b in drive-seconds AND wan_bytes
RepairTask { stripe_id, int[] read_idx, Locus decode_at, Target[] write, Cost c }
```

- **Ordinary repair never requires a tape mount beyond the one in progress.** A media error is repaired by the local band; only a lost volume or a lost site reaches the global code.
- **Tape-resident fragments are excluded from availability-driven repair entirely.** Their only repair trigger is *positive evidence* — a failed leaf check on a completed read, a TapeAlert or `LOG SENSE` media flag, or a scrub result — never absence or timeout. A 5-second liveness sweep over a medium with 265–1,400 s access latency reads every transient as a missing fragment: a ten-minute partition touching 1 % of stripes would trigger ~700 fragment reads, ~350 writes, ~700 mounts and 72 TB of WAN to repair nothing.
- **Repair is a reserving tenant with a published share and a WAN budget**, not a background sweep. It is rate-limited against the federation core, not only against drives, because §14.5 shows the WAN is the binding constraint on the case that matters.
- **Repair consults the shred journal and refuses on a tombstone.** A stripe whose rdoms are dead is `REDACTED`, a terminal state distinct from `LOST`, and is never regenerated. A 2036 reader must be able to tell an audited erasure from media loss, and a real breach must not be launderable as a redaction.
- **Local parity is never restored in place on WORM.** A band that has lost a parcel pays the reconstruction cost on every subsequent read for the life of the volume. The correct response to the first unrecoverable parcel is therefore to promote the volume to `DRAIN` and schedule it into the next migration wave, and to record the reconstructed-parcel count so the migration planner can sort by it.

### 8.7 The write path

The raw federation feed is ~1 TB/day logical, roughly 5.8 MB/s per open cohort — twenty times below the speed-match floor. Writing that directly to tape backhitches continuously: throughput collapses, drive-seconds burn on repositioning, and media and head wear accelerate, with no error raised anywhere.

Therefore: **parcels accumulate on the site's spool until a full fragment (96 parcels) or a `seal_deadline`, then despool in one continuous pass at streaming rate.** Volumes are opened, written and closed per despool wave, never held open — which is also what dissolves the "150 open volumes against 3 drives" impossibility that per-lineage open volumes create. Spool sizing: 2 × fragment × devices ≈ 620 GB per site minimum; specify 2 TB NVMe.

> **Measured risk, unresolved (2026-09-19).** A spool path is specified here by *size* and by *media type*, and **nothing in the system distinguishes a spool that silently resolves to a shared filesystem.** `eval/results/fsync_cost.json` measures a shared project filesystem at **8.1–8.8 MB/s regardless of barrier** on the same Linux host that delivers **339 MB/s** node-local — 13× below the ~112 MB/s speed-match floor of §6 and 46× below the 400 MB/s drive rate. A spool that lands there backhitches every despool wave, and **by §6's own statement every rate figure in this document is then void.** **What is missing is the threshold, not the awareness:** the required sustained spool rate is the speed-match floor plus whatever concurrent inbound a despool wave carries, and that number has not been derived or measured. Until it is, no commissioning refusal can be specified, and the risk is recorded rather than enforced (§16 item 20).

**Pre-seal durability has an owner.** The spool is a new single point of loss and is named as one. Three rules: a `PROVISIONAL` ledger row exists before the first byte; the spool holds each fragment on ≥ 2 distinct hosts at the site; and **the origin's copy is retained until the stripe reaches `DURABLE`** — all three fragments sealed, roots compared, ordinals confirmed. A live object is a cache only if `entail()` over it is feasible now; un-entailable spooled bytes are not a cache and carry their own survivability policy.

**Forced seal.** A cohort that has not accumulated a full fragment within its `seal_deadline` (per-lineage, default 7 days) seals short with RS(j,4). Padding waste ≤ 1 parcel per fragment. This is what makes the accumulation problem disappear rather than be endured.

**Degraded commit.** With one site unreachable a stripe cannot reach three domains. It commits at **2 of 3** — which under RS(2,1) is still fully decodable, so the data is durable and only the *margin* is missing — marks `DURABILITY_DEBT` with the missing fragment index, and repays in the `OBLIGATION` lane when the domain returns. Outstanding debt is capped in bytes; above the cap ingest is refused with a typed refusal naming the constraint. Silence here means either an unbounded spool pile or a stopped archive, chosen by accident.

**Writes are admitted, not merely accepted.** `TAPE-RESEARCH-PROMPT.md` Q4 is decisive: no store-versus-recompute test denominated in money will ever say *do not store* (a 7B checkpoint set is ~$170 of tape against ~$17,500 of GPU to recompute), so the only throttle is a hard quota on committed bytes per day. `commit` draws against the contributing institution's pledge and a per-day plant byte budget and refuses with the same `Refusal{bindingConstraint, arithmetic, rewrites[], retry_after, intentId}` shape as `realise`. Offered rewrites: reduce retention class, route to the disk tier, or register a Derivation with `residency: ABSENT` and store no bytes at all.

### 8.8 The ledger, at three cardinalities that must not be confused

Conflating these produced the "10⁹-row table is the largest engineering item in the plan" blocker. They are three different structures at three layers.

| Table | Rows at 4.2 PB | Size | Mutability | Layer |
|---|---|---|---|---|
| ~~`chunk dedup : sid -> xid`~~ | ~~~10¹¹~~ | ~~large; sharded, per-rdom~~ | ~~append~~ | ~~above the substrate~~ |
| `place : xid -> (stripe_id, frag_i, parcel_ordinal, offset, len)` | 65.6 M | ~2.6 GB, LSM, sharded by `xid` prefix | **immutable** | object layer |
| `loc : stripe_id -> Locator[3]` | **23,283** | **~6.7 MB** | **mutable** | **storage ledger** |

> **The `chunk dedup : sid -> xid` row is RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`: real training checkpoints share 0 of 184,044 64 KiB weight blocks adjacent, 0 distant, 0 between the two weight copies inside one checkpoint, and 0 cross-run, with the cross-run control confirming the measurement discriminates). It was the ~10¹¹-row structure and it was the one that sat *above* the substrate — `eval/results/cdc_measure.json` gives 17,845–26,872 chunks per GB, i.e. 1.7–2.7 × 10¹⁰ chunks per PB, which is the number that made it unaffordable and which is now not needed. Replaced by per-object manifests, on the order of **10⁶ rows at 4.2 PB — a document estimate (`STORAGE-DIRECTION.md`, *What this deletes*), not a measurement** — inside what the index is already proven at. The table is now two rows plus the ~10³-row volume registry, and §8.8's point survives intact: the 10⁹-row blocker was a conflation of layers, and the largest of the three conflated tables has been **dissolved by measurement rather than solved by engineering**, which reads differently in the record and should be stated plainly.

`loc` is the only table a generational migration writes. `place` never changes, so migration touches no manifest, no `VersionRoot`, no `ExtractCert`, no `ExtractEnum`, no receipt and no citation. That is the payoff of §2.2, and at 6.7 MB the storage ledger is a single quorum-committed file replicated to every site — which removes rebuild-from-media from the operational critical path entirely and leaves it as the archival-independence property it should be.

Plus the ~10³-row **volume registry**: `volume_id -> { site, institution, media_class, latency_class, presence, append_ordinal, residual, health, seal_epoch, config_hash }`. Only this table changes when a cartridge is exported, shipped or re-shelved.

**Presence is three-valued and includes off-site custody:** `PRESENT_VERIFIED` (barcode seen in an element this inventory epoch), `PRESENT_CLAIMED`, `EXPORTED{custodian, since}`. A shelved volume is never counted as an available copy for read planning nor as a missing copy for repair, and `plan()` refuses on `EXPORTED` while naming the custodian. A rebuild that silently omits off-site custody reports a smaller universe than exists, which is the worst possible error in a recovery path.

**Every `loc` row carries `coding_id: u16`** into a small versioned coding registry (family, k, m, band parameters). The domain count is expected to change in both directions — the most likely site-loss event over ten years is an institution withdrawing at a budget cycle — and the day the parameters change, every fragment written under the old ones is undecodable without a per-stripe record of how it was coded. Two bytes × 23,283 rows = 47 KB, replicated with the catalogue and written into every volume index.

---

## 9. Layer 3 — materialisation

### 9.1 One verb

There is no `materialise`, no `cast`, and no read verb. Exactly one verb moves bytes:

```
realise(target, sink, draw, token) -> Job | Refusal{bindingConstraint, arithmetic, rewrites[], retry_after, intentId}
```

always asynchronous, always preceded by `prospect`, admitted against four gates in order — **Coverage, Pledge, Plant, Policy** — with the refusal naming which bound. `form` is a field on `sink`, not a second verb. A parallel byte-moving verb without those gates is the cheapest uncounted exfiltration route in the fabric, and it is cheapest precisely for the broadest possible request.

Coverage is charged leaf-for-leaf and rdom-for-rdom, identically by delivery, enumeration and aggregation. `distinct_rdoms_touched` is the number that matters for PHI.

### 9.2 The Plane

The primitive delivered at an arbitrary network point is a locus-local, sparse, content-addressed tree:

```
plane/
  by-parcel/<ordinal>      staged parcels, CIPHERTEXT AT REST, exactly as on media
  spans                    { leaf_ord -> [ (xid, offset, len) ] }  -- itself an encrypted chunk
  frontier                 roaring bitmap over leaf ordinals currently resident
```

- **The stage holds ciphertext**, per-chunk AEAD preserved exactly as written, decrypted on the stream into the sandbox. That is what makes a withdrawal landing mid-residency settle with no eviction protocol and no race.
- **`spans` is not in the clear.** It maps `rel -> spans`, and `rel` is often MRN-derived; writing it as a plain file hands a remote institution the exact artefact the whole design keeps off unerasable media, on a disk the fabric does not administer. It is an ordinary chunk under its object's key *(2026-09-19: was "its rdom's key"; `K_rdom` retired, rename only)*, materialised only into the sandbox.
- **`spans` carries a binding header** `{extract_id, lineage, v, vid, index_seq, materialised_at, coverage_charge}`. A Plane is valid only while its `vid` matches the cert it was realised from. A relocate never invalidates it (positions are not in it); a redaction does, which is correct and should be observable.

### 9.3 Two forms, and one reference adapter

| form | what the consumer gets | partial? |
|---|---|---|
| `VIEW` | read-only random access over the ordinal space; plaintext exists only in the reading process, decrypted on the stream under a key lease | yes |
| `STREAM` | framed byte stream in **physically optimal order**, flow-controlled, resumable by cursor | yes |

`MAP`, `BLOCKDEV`, `ENDPOINT`, `S3` and `SHARD` are **consumer-side adapters over `VIEW`**, shipped as reference code we publish and do not operate. Keeping them inside the fabric buys two admission paths, a `COMPLETE`-versus-`PARTIAL` bifurcation in the core, a network listener at a locus that is otherwise unix-socket-only, and ownership of bucket semantics, listing, ACLs and versioning. `STREAM` is the only genuinely distinct contract, because physically optimal order is a different scheduling promise rather than a different presentation.

**We ship exactly one reference adapter over `spans` and make it the conformance test**, so "three consumers each write a reassembler and the first bug in one of them looks like a storage bug" becomes one reassembler with three callers.

### 9.4 Absent, redacted and undeliverable are typed, never `ENOENT`

On tape, *not yet* and *never* are indistinguishable from the recall path, so the distinction must be published up front:

```
non_deliverable: [ { leaf_ord, reason: NOT_YET{projected_window} | REDACTED{redaction_rec_digest,
                     authority, effective_index_seq} | LOST{stripe_id} } ]
```

returned at admission, before a single mount is scheduled. A redacted leaf owes the consumer the signed redaction attestation, without which the cited extract's root no longer verifies; an `ENOENT` destroys that. A silently holed dataset that a training job reads past is far worse than a refusal.

### 9.5 Keys at the locus

**The locus never receives an object content key.** *(2026-09-19: was "never receives `K_rdom`"; `K_rdom` retired by `eval/results/ckpt_dedup_results.json`. The rule is unchanged in substance.)* A key agent, at the locus but outside the sandbox, holds the keys for the jobs currently in flight and issues short-TTL derived chunk keys. Two rules make it load-bearing:

- it **refuses to issue once it observes `shred_epoch ≥ S`**;
- it **fails closed on staleness** — unable to renew the watermark within the TTL, it stops issuing unprompted.

Without the second, a partitioned locus keeps decrypting after a shred and the purge SLO is unbounded in exactly the failure it exists to cover. This fabric's own measurements record ~20 s failover reconnects and up to ~44 s for all agents to return after a global restart, so the partition case is routine, not exotic.

**Lease at redaction-domain granularity, not chunk granularity.** A 200 GB cohort at a 64 KB chunk target is ~3.1 × 10⁶ chunks; re-minting per chunk every 60 s is ~52,000 authenticated mints per second, which is not servable. Fifty rdom keys re-leased every 60 s is 0.83 mints/s. At TTL 60 s the new-decryption window after a shred is ~75 s including the measured 14.2 s replica lag, and **that number is published as the declared lower bound on shred latency** rather than claimed as zero.

> **HOLE opened 2026-09-19, recorded not filled.** With `K_rdom` retired (`eval/results/ckpt_dedup_results.json`) the lease unit is the **object**, which sits between the two poles this paragraph contrasts. For large objects it is better than the domain: a 200 GB cohort of ~51 GB checkpoints is ~4 objects. For small objects it is far worse: the same 200 GB of 80 KB clinical notes is ~2.5 × 10⁶ objects, ≈41,700 mints/s at TTL 60 s — the regime this paragraph itself declares not servable, arrived at from the opposite direction. **The published 75 s lower bound on shred latency is therefore established only for large-object lineages and must be annotated wherever it appears** (here, and `ENTAIL-AGENT-NATIVE-FS.md` §14.10's timeline). Some aggregation unit for leasing small objects is required and is not designed here; note that it must be a *lease* aggregation, not a *key* aggregation, or it reintroduces the shared key the measurement just removed.

### 9.6 Policy, leases and eviction

- **`materialisation_policy` is a grant on the (lineage × Purpose) pair with an explicit `valid_until`**, re-evaluated at every `realise` and every `extend`, not a static lineage attribute. A DUA is bilateral and per-protocol: site X may decode for IRB-2026-114 and not for IRB-2027-003, and a lineage-scoped field cannot express that. Refusal code `AUTHORITY_EXPIRED`.
- **Where may ciphertext fragments live** and **where may plaintext be reconstituted** are different questions with different legal answers. Placement policy and materialisation policy are separate objects. Without the second, reconstruct-anywhere means plaintext-anywhere.
- **A Residency is a cache and never counts toward a survivability policy.** Conflating them is how a system convinces itself it is durable while holding one coded copy and a pile of caches.
- **Refcount at parcel granularity**, not stripe granularity, so an open handle pins what it reads rather than the 180 GB it landed in.
- **`avail_until` is monotone-raise within an epoch only.** A shred enumerates residencies whose Coverage intersects the shredded rdom ordinals, drops their refcount regardless of attachers, destroys the per-residency stage key, and returns a signed kill receipt per locus. This is the one place the lifecycle needs a non-monotone operation and it is stated rather than inherited away.
- **Eviction is key destruction, not unlink.** Every stage and sandbox writes under an ephemeral per-residency key generated in RAM at `PLANNING` and destroyed at `RELEASED`; the release receipt carries the destruction attestation. Unlinking a file on a wear-levelled SSD at an institution outside the custody perimeter is not erasure.
- **Physical reclamation is lazy, not wall-clock.** An expired, refcount-0 extent becomes *reclaimable*, not reclaimed, and is dropped only under genuine staging pressure, oldest-expired-first. This introduces no ranking function and no shadow price, and it preserves the property that makes 10⁵ callers affordable: two independent 1 % selections overlap almost totally at *fragment* granularity even when their file sets barely intersect, so the second consumer's marginal physical cost is an index lookup. Destroying an extent on a clock, while the stage is half empty and shortly before the next overlapping consumer arrives, costs a full re-gather at ~$46/drive-hour to save pennies of disk.
- **`attach` credits the first payer** and charges a late joiner a bounded join fee — neither nothing, which invites the deadlock-by-politeness equilibrium on cold data, nor everything.

### 9.7 What the receipt must say that nothing currently says

Every Residency and every Receipt carries `rdom_closure_size` and `expected_underivable_by`. **`rdom_closure_size` is the number of distinct *consent units* in the closure, not the number of contributing object keys** *(stated explicitly 2026-09-19: with per-object keys one withdrawal destroys every object key belonging to that subject, so computing the closure over object keys would over-state the hazard by the objects-per-subject ratio. The consent unit survives as the counting unit even though it is no longer a key.)*

A MIX derivative's key is derived from the concatenation of its contributing keys, so **any one withdrawal makes it underivable**. At the 1 %/yr withdrawal rate the documents use, the hazard is `0.01·j` per year, with `j` = |distinct consent units|:

| contributors `j` | hazard | half-life | P(dead at 8 months) |
|---|---|---|---|
| 25 | 0.25/yr | 2.8 yr | **15.4 %** |
| 5,000 | 50/yr | **5.1 days** | ~1 |
| 100,000 | 1,000/yr | **8.8 hours** | ~1 |

Eight months is exactly the "cite now, reproduce later" interval. So for every cohort aggregate, `entail()` returns `INPUT_REDACTED` well within the citation horizon, and the disposable cache becomes the only extant copy of a result that carries no survivability policy. AND-survival is right for anything subject-identifiable and wrong for a de-identified aggregate: **`CERTIFIED_DEIDENT` is the mandatory path for any aggregate intended to outlive its inputs above a stated `j`**, with the certifier and approver quorum on the record, and the fabric surfaces the arithmetic in `prospect` while the choice is still free.

---

## 10. Mount scheduling: the plant

### 10.1 Where it lives, and why

**One plant scheduler per medium changer** — not per site (a library exposing two partitions legitimately carries two), not federation-wide (drive-seconds are conserved per library and are not fungible across sites), and not at the consumer.

Under the Bareos split its authority is not "it holds the device handles" — the Storage Daemon does. Its authority is that **it is the only submitter to the Director.** Two schedulers over one conserved resource is where mount thrash comes from, so this must be enforced operationally and stated plainly: *an operator running `bconsole restore` bypasses the entire scarcity model.*

A federation-level coalescer exists but does not schedule: it routes intents to sites and merges duplicate demand.

### 10.2 The declared-demand book is the input

Optimal mount planning is an offline problem — adding one request changes the plan for all of them — and the error every prior design made was converting a batchable request into a scheduled one at the moment of claim, turning 10⁵ individually optimal passes into a cartridge-exchange storm.

`intend` / `intent_status` / `withdraw_intent` is therefore the **only** writer of the book. `realise` on cold data returns a queue position against a published window, not a job.

```
Intent { intent_id, coalesce_key, locators[], not_before, deadline, lane, purpose_id }
Wave   { volume_id, storage_id, window{start,end},
         bsr: FileIndex ranges ASC,          // = one Bareos restore job
         est_drive_seconds, est_loads, est_robot_seconds, lane }
lane ∈ { OBLIGATION, DEADLINE, BULK, SCAVENGE }
```

**The wave closes at a published time `T`**, and that is an agent-visible contract, not an implementation detail: Bareos will not merge two in-flight restore jobs onto one mount, so a late intent goes to the next wave and must be told so.

### 10.3 Wave formation, and the two derived rules

Group pending intents by `volume_id`; order strictly ascending by `ordinal` (equivalently by `VolFile`) in a single monotone pass; emit one Bareos restore job per volume per wave with a bootstrap record already in that order. Never mount one volume twice in a window; never back-seek within a pass.

We are re-deriving Hillyer–Silberschatz serpentine scheduling and taking only its monotone-sweep result. We are also re-deriving the bootstrap record, which *is* the wave — Bareos already sorts a restore by (Volume, VolFile, VolBlock) and performs one forward pass — so the wave planner is a BSR generator plus a lane policy, perhaps 200 lines, not a subsystem.

Two rules fall out of the arithmetic and are normative:

- **Coalesce-gap rule.** A reposition costs 40 s = **16.0 GB** of streaming. Two reads on one volume are merged into one contiguous read whenever the gap between them is under 16 GB.
- **Read-widening rule.** A mount costs 265 s = **106 GB** of streaming. Widening a read by `X` bytes is rational whenever `P(the extra bytes are wanted before this volume's next mount) > X / (X + 1.06 × 10¹¹)` — about 1 % at 1 GB, 10 % at 12 GB, 50 % at 106 GB. `draw` therefore carries a widen budget rather than an exact extent. The marginal byte from a located cartridge is nearly free; the mount is not.

### 10.4 Admission, lanes and the reserve

**Trigger:** `bytes_pending(volume) ≥ B* (412 GB)` **or** `deadline − now ≤ mount_latency + sweep_time`.

The deadline clause is an uncapped generator of sub-threshold mounts if left alone — one deadline-bearing request produces a mount at whatever happens to be pending, potentially one parcel at 1 % duty. It is therefore **charged against a bounded per-requester budget of low-duty mounts**, debited in loads and robot-seconds at the real rate, so a 2 GB deadline mount costs the requester as much of the budget as a 412 GB wave. The lane exists; it is priced.

**The obligation reserve is physical, not a percentage.** Devices are partitioned into Bareos storage/device resources — **2 tenant drives and 1 obligation drive per site** — because `Maximum Concurrent Jobs = 1` per device and a running job is never abandoned, so a declared share that shares devices with tenants is a fiction. This is also the concrete answer to the open question of what the third drive per site is for: *the third drive is the obligation lane.*

**Deadline preemption does not exist**, and promising it would be a lie. A mounted, running job runs to completion. The honest worst-case latency for a deadline-bearing read is therefore **remaining wave (≤ ~1,416 s at W = 4) + one mount cycle**, and that is what is published.

`realise` does not reserve drive-seconds. Held-but-unused capacity bills continuously as byte-days and lane-seconds, so abandoning is never cheaper than releasing and hoarding is self-limiting. The reason is precedent rather than preference: binding reservation across sovereign institutions has been built (SRM space tokens, Globus GARA, Maui advance reservations, SHARP), run at ~150 sites over tape, and retreated from. What is returned instead is a feasibility boundary, a cost interval with a per-term basis, the binding constraint, offered rewrites, and a real queue position.

### 10.5 What the planner exposes upward

A lane, a queue position, a projected window, and **bucketed** residual. Never a cartridge identifier, never a wave membership list, never a per-peer instantaneous load, never a serpentine position. A truthful cost oracle over physical layout is simultaneously a cross-tenant covert channel, a targeting map across fifty institutions, and a defection oracle ("wait for someone else to pay the mount").

### 10.6 Four conserved resources, not one

The scheduler refuses against all four, and all four appear in the locus descriptor:

| Resource | Budget | §14 |
|---|---|---|
| Drive-seconds | 2.84 × 10⁸ /yr across 9 drives | §14.1 |
| **Load/unload cycles** | 2,000 per cartridge per year (20,000-cycle media rating over ten years) | §14.2 |
| **Robot exchanges** | ~200,000 per accessor per year | §14.2 |
| **Slots** | free slots ≥ (archive ÷ domains) ÷ cartridge capacity | §14.3 |

Drive-seconds alone was the error in every candidate design. Media load cycles independently forbid `W = 1`; slots independently forbid "buy a cartridge instead" as a reclamation answer; robot-seconds independently bound every campaign whose per-cartridge work is short, including the catalogue rebuild.

---

## 11. The WORM lifecycle

### 11.1 Forget

**Destroy the object keys of the consent unit.** *(2026-09-19: was "Destroy `K_rdom`"; retired by `eval/results/ckpt_dedup_results.json`. This is a rename and is flagged so the sweep does not weaken the section — the zero-mount property follows from encryption at origin, not from key granularity.)* Zero mounts, zero bytes moved, exact blast radius — now the **object** rather than the domain — effective in the archive, in every pinned extract, in every version and in every cartridge, including ones in a vault in another county. The parcels remain as unopenable noise. **This is the only forget.**

Fragment destruction stays retired, for three independent reasons: automatic repair regenerates destroyed fragments from survivors needing neither key nor approval (a stable attractor, not a race); it is impossible in place on WORM; and a packing unit bundles unrelated subjects.

Four things the shred must reach that a naive implementation does not:

1. **The decode path must consult the shred store before classifying anything as a media error.** A shredded chunk's ciphertext is intact, the leaf check passes, the RS decode succeeds, and only the per-chunk GCM tag fails — which is indistinguishable from corruption. Without a branch, the repair sweep bills drive-seconds to repair data that was legally destroyed. A GCM failure on a shredded rdom returns the signed redaction attestation and moves the extract to `PARTIALLY_REDACTED`.
2. **`prospect` must disclose it before the mount**: *one of 25 rdoms in your selection is shredded; you will pay full recall for 4 % dead bytes.* The drive-seconds are spent either way and only the agent can decide whether that changes its plan.
3. **Live residencies are fenced** (§9.6).
4. **The acknowledgement ordering is custody-first.** The act that makes a shred true is the destruction of the key, which is instantaneous and global. Requiring three WORM journal writes to complete *before* acknowledgement means a single library outage blocks acknowledging a withdrawal that has already taken effect, and consent-withdrawal timelines are regulatory. Acknowledge on custody-quorum destruction; emit the journal record asynchronously with durable retry and an alarm if it has not reached *t*-of-*n* sites within a stated bound.

### 11.2 Reclaim

**You cannot, below whole-volume granularity, and you should not try above it.**

Arithmetic: a 30 TB volume rewrite is 20.8 h of read plus the write of the live fraction, ~24–27 drive-hours, to recover at most ~$100 of media. At any plausible loaded drive-hour cost the threshold at which compaction pays is effectively zero. **Buy a cartridge instead — except that there is nowhere to put it.**

That is the real reason, and it is a slot argument, not a media-price argument. Dead space accrues at roughly the withdrawal rate: 1 %/yr against 4.2 PB is ~27 cartridges of media over a decade against ~12 free slots per site. Slot exhaustion, not cost, is what binds, and it is why slots are a conserved resource (§10.6) and why the dead-space rate is a first-class projection in the ledger rather than a dollar figure in a footnote.

**GC on the WORM tier is OFF by default.** `live_fraction` is computable with zero mounts from `loc` plus the **catalogue-side residency map** plus the key-destruction journal — **which is only true for parcels that are object-pure, and §8.4 rule 1 can no longer guarantee that (hole recorded there, 2026-09-19)** *(2026-09-19: was "plus `obj_ords`". The on-media `res_ords` vector (§18.3) is for the catalogue-loss branch of §7.3 only; the ordinary zero-mount path reads the catalogue, and §18.3 changes nothing about it. On the media-only path under `pooled(n)`, `res_ords` names the pool group rather than the member, so a parcel is marked dead only when its whole group is — the same conservative direction this paragraph already declares.)* — and is maintained incrementally by a decrement on every `redaction.shred`, never by a sweep. *Under `pooled(n)` packing `live_fraction` is a **bound, not a value**, and the incremental decrement on every shred becomes a decrement of an upper bound. The surrounding reclaim argument — 20.8 h rewrite for ~$100 of media, slot exhaustion rather than cost being what binds, GC off by default on WORM — is untouched.*

**Unreclaimable tombstoned capacity is its own term in the descriptor**, so a tape locus at 80 % with 30 % tombstoned does not present to placement as a disk with headroom.

### 11.3 Migrate

The LTO-10 compatibility break is the most consequential vendor fact in the plan. **The migration deadline is set by drive-fleet health, not by media rating**: LTO-10 reads and writes only its own generation, so when the last working LTO-10 drive dies every LTO-10 cartridge is unreadable regardless of a 30-year media rating. Working-drive count and spares availability per site are ledger-visible metrics and the campaign trigger is set on them. Overlapping-generation procurement is a **durability requirement with a deadline**, not a throughput preference, and it is a drive-bay, slot and floor-space line as well as a drive line.

Cost: 7.20 PB read + 7.20 PB written = 3.60 × 10⁷ drive-seconds = **417 drive-days**, ≈ 46 wall-days at 100 % of nine drives, ≈ 23 with two generations running concurrently, realistically **2–4 months at a 25–35 % plant share**. It is a reserving tenant in the plant calendar with a published projected completion, not a background sweep. Verification is performed from the decode stage during the read, never by a second full read pass of the new cartridge — that alone removes ~27 fleet-days.

Mechanically:

```
for each fragment: read(old) -> verify leaves -> skip if REDACTED or unreferenced
                   -> append(new) -> seal
atomically swap loc[stripe_id][frag_i]          // 56 bytes
emit migrate record; retire(old, PURGE, token)
```

Nothing above Layer 2 changes. **Migration is the only rewrite that ever happens, and therefore the only place compaction, re-coding and repacking are free** — the read is already paid for and the output layout can be chosen after the shreds are known.

**Migration is a ciphertext copy-forward: key-free, blind-safe, and it does not re-encrypt.** Re-keying would require plaintext at the migration locus (destroying the blind-holder property that is the point of the tier) and would require every content key in the archive to be simultaneously recoverable at one moment *(2026-09-19: was "every `K_rdom`"; retired, and the argument is stronger at object granularity)*, against a custody scheme whose ten-year loss rate is the archive's dominant risk. The consequence is stated as an accepted permanent constraint rather than left implied: **content keys are immutable for the life of the medium; only the wrapping rotates. Periodic content-key rotation is unmeetable on WORM by construction**, and any policy mandating it must be answered with that fact rather than with a plan.

### 11.4 Mistakes

On WORM a bad write is permanent, so the entire correction budget sits at write time.

| Kind | Remedy | Bounded cost |
|---|---|---|
| Session fails mid-flight | `abandon()`: tombstone, prefix is dead media, resume at the next boundary | ~103 GB, 0.34 % of a cartridge |
| Caller wrote the wrong bytes | never referenced; dead space | one fragment |
| Data that must never have been written | destroy its object key | zero mounts; the shred unit is the object, so you never shred more than you meant. ~~and if the rdom was coarser than the mistake you shred more than you meant — which is the argument for `rdom = object` on quarantine-class lineages, forgoing dedup within them~~ — **the special case became the default 2026-09-19; the forgone dedup measures zero** (`eval/results/ckpt_dedup_results.json`). Blast radius is a property of the key, not of packing, so this holds even under `pooled(n)`: pooling affects reclaim, not the shred unit |
| A whole volume written under a wrong or compromised key | `retire`, regenerate its fragments from the two survivors per stripe | ~3.6 drive-days + 30 TB of WAN |
| Logically wrong write — correct bytes, wrong content | **not recoverable by any mechanism here** | this is why the write path is quorum-confirmed one layer up |

`Quarantine{stripe_id, reason, ordered_by, seq}` makes `read` refuse fabric-wide, enforced **at the key-lease service and at admission, never at the holder** — a blind holder must need no key, no approval and no live fabric state, or repair becomes stallable by an expired credential. Quarantine is an **operational advisory with no enforcement behind it**: a party holding both the medium and the key can still read. That limit travels with the type's documentation, and quarantine is never counted in a disclosure or erasure argument.

### 11.5 Scrub and verification

**Verify-after-write is not an inline read-back.** A sampled read-back at seal costs two serpentine repositions against the transfer it verifies — 31 % to 93 % of write throughput, not the 3 % a byte ratio suggests — and it re-reads through the same head that wrote, so it structurally cannot catch an off-track write, which is the documented LTO failure producing cartridges readable only in the drive that wrote them. The regime is:

- (a) the drive's own read-while-write verification, monitored through `LOG SENSE` 0x0C/0x31 thresholds read at unmount, with a budget breach failing the fragment;
- (b) an end-to-end digest of the buffer on the way out of memory, compared against the manifest — catches host-side corruption upstream of the drive's CRC at near-zero cost;
- (c) 100 % read-back **only while the format and path are unproven**, scoped per drive model and firmware revision, then tapering;
- (d) a steady-state **1 % cross-drive, later-mount** sampled read-back — the only control that catches the off-track case — at ~1 % of ingest drive-seconds.

`verifyRate` is published per drive model in the descriptor and the verify pass is carried in the capacity model. *(2026-09-19: **only the 1 % cross-drive verify is carried** — §14.4's 0.01 % row. The 100 % read-back of (c), at 2.2–2.5× write drive-seconds, is in no capacity table here and in none of `eval/results/plant_contention.json`'s standing obligations. It must be priced into §14.4 as an explicit commissioning-period obligation with an end date before it is adopted; see `STORAGE-BINDINGS-DECISION.md` §8 row 13.)*

**Scrub** is a full sequential pass of every volume annually: **5,127 drive-hours = 214 drive-days = 6.5 % of the plant-year** (MEASURED 2026-09-19, `eval/results/plant_contention.json`, priced as sequential whole-cartridge passes at 90 s mount + 20 s unload + 30 TB at 400 MB/s; ~~7.20 PB at 400 MB/s = 208 drive-days = 6.3 %~~ was byte-only and omitted per-cartridge mount, unload and positioning). It is affordable and is therefore specified rather than replaced — **the measurement confirms this document's judgement**: standing obligations are cheap because they are sequential whole-cartridge passes, and retrieval, not obligation, is what consumes the plant. Sampled proof-of-possession complements it but does not replace it, because a blind holder that discards bytes and answers challenges from a cache is undetectable without periodic full reads.

**Proof-of-possession is scheduled, not injected.** An unpredictable challenge is an anti-scheduler: every challenge is a forced `W = 1` mount displacing a `W = 4` wave, so its marginal cost is ~10× its own drive-seconds. The construction that keeps unforgeability while costing nothing: **the auditor may not choose which volume is mounted, but chooses, at mount time and not before, which leaf on it must be returned.** Sampling rides on visits the demand book and the scrub already scheduled. `prove(locator, leaf, nonce)` costs 8 MiB, not 103 GB.

**Every ordinary read is also a possession sample.** The holder returns, alongside the bytes, a signed `(locator, leaf_root, read_epoch, nonce)` tuple — one signature per read. Corruption acquires an attributable origin, and the cache-the-answers attack now requires caching the bytes themselves, which is what the holder was being paid to store.

---

## 12. Cryptography and forgetting

### 12.1 The hierarchy

```
K_L      per-lineage AES-256, wrapped under the site KEK, Shamir t-of-n custody
~~K_mac    = HKDF(K_L, "sid")     chunk ids:   sid = HMAC(K_mac, chunk)~~
K_mac    = HKDF(K_L, "sid")     XORB NAMING FROM THE WRITE INTENT, §18.4:
                                xid = HMAC(K_mac, idempotency_key ‖ xorb_seq), 16 B
                                There is no chunk id. A chunk is addressed as (xid, i).
K_ord(v) = HKDF(K_custody_root, "ord" ‖ volume_id)   -- §18.3, residency-ordinal permutation
K_meta   = HKDF(K_L, "meta")    cnode encryption
K_mid    = HKDF(K_L, "mid")     cnode ids
K_bnd    = HKDF(K_L, "bnd")     run boundary function
~~K_rdom   per REDACTION DOMAIN, random, wrapped, in the shred store only~~
~~         chunk key = HKDF(K_rdom, "chunk" || sid)~~
K_obj    per OBJECT, random, wrapped, in the key store only; chunk key = K_obj
K_idx(v) = HKDF(K_custody_root, "idx" || volume_id)      -- §7.4, storage layer only
```

> **RETIRED 2026-09-19** — `eval/results/ckpt_dedup_results.json`. The heading previously read "The hierarchy, **unchanged**"; it has now changed, and the word is dropped rather than left to mislead. `K_rdom` existed so that chunks shared by deduplication could be shredded despite the sharing; measured sharing on the dominant population is exactly zero (adjacent weights 0 of 184,044 blocks, distant 0, intra-checkpoint 0, cross-run control 0, optimizer 0.002 % excluding zero blocks), so there is no shared key. `K_mac`, `K_meta`, `K_mid`, `K_bnd`, `K_idx(v)` and the SHA-256 / hash-based-signature / CNSA 2.0 choices below are untouched by the measurement and stand verbatim.

Digest choice: **SHA-256, truncated to 128 bits where 16 bytes are wanted** (FIPS 180-4 with SP 800-107 truncation), not BLAKE3. The leaf tree and `leaf_root` are written into every fragment on unerasable media and must still be computable and approvable in 2056; the defense-hardening track requires FIPS/CNSA-approved primitives; and there is no performance argument, because 400 MB/s of tape is three orders below any modern SHA-256 implementation. Any signature written to WORM is hash-based (LMS or XMSS, SP 800-208), since a 2026 signature must verify well past its own algorithm's horizon. KEK wrapping and share transport follow CNSA 2.0.

### 12.2 The three defects that defeat shredding if built as currently written

These are **normative corrections to `STORAGE-DIRECTION.md`**, not observations. Each is a plaintext-derived artefact that lands on unerasable media under a key that a withdrawal never destroys.

**D-1. The in-xorb chunk table is under `K_meta`, not under the shred key.** The wire format writes `GCM(K_meta, …){ n, sids[n], offs[n], lens[n], rdoms[n] }` onto the cartridge, and `K_meta = HKDF(K_L, "meta")` survives every shred. Three disclosures therefore survive the erasure they document: `sid` is a *keyed plaintext digest*, so every authorised reader of that lineage for the next thirty years holds a membership-confirmation oracle against subjects who already withdrew; `lens[n]` is the CDC boundary-spacing sequence, i.e. arithmetic check 16 preserved verbatim per chunk, forever, *inside* the parcel whose outer length we went to such trouble to fix; and `rdoms[n]` permanently records which blocks belonged to the subject who withdrew.

> **Required (restated at object granularity, 2026-09-19):** shard the chunk table **by object** and encrypt each row-group under the object's own key `K_obj`, leaving only the group count and per-group offsets under `K_meta`. A shred then blanks its own rows. ~~Where a single table must remain for rebuild, store only blinded ids `sid' = HMAC(HKDF(K_obj, "id"), sid)` on media and keep `sid` solely in the erasable catalogue.~~ *(2026-09-19: the blinding construction is **retired with its subject** — §18.4 deletes `sid` outright, and blinding a field that does not exist is one fewer WORM-permanent construction to get right.)* The `rdoms[n]` column becomes `obj_ids[n]`, **and it moves inside the per-object row-group under `K_obj`; it never appears under `K_meta`.**
>
> **HOLE OPENED 2026-09-19, CLOSED 2026-09-19 — DECIDED IN §18.4.** `sid` is **deleted**: `sids[n]`
> is removed from the xorb wire format and a chunk is addressed positionally as `(xid, i)`, which the
> table's own `offs[n]`/`lens[n]` and the per-chunk AEAD's `aad = lineage|xid|i` already support.
> Deduplication was `sid`'s only consumer and it measures zero; integrity is discharged four times
> over without it; addressing is positional; write idempotency relocates to the trailer's
> `idempotency_key`. **Deleting `sid` alone would have closed nothing**, because
> `xid = HMAC(K_mac, sid₀ ‖ … ‖ sid_{n−1})` is independently on media in the sealed trailer's
> `xorbs[]` and in `xorb.place` under `K_mac = HKDF(K_L, "sid")`, which survives every shred — so the
> decision covers `xid` too, and re-derives it from the **write intent** rather than from content,
> from ciphertext (circular: `xid` is an AAD input, so it must exist before the bytes) or from a
> CSPRNG (loses idempotency on media that cannot be reclaimed).
>
> **D-1's mitigation above is NOT retired with `sid`, and this is the part that stays blocking.**
> Removing `sid` narrows D-1 from a membership-confirmation oracle to a **size fingerprint**; it does
> not close it. `lens[n]` under fixed 64 KiB chunking sums to the **exact** object size (the constant
> entries supply the quotient, the remainder the low bits — verified against
> `ckpt_dedup_results.json`: 184,043 × 65,536 + remainder reproduces 12,061,485,864 B exactly), and
> per-group offsets under the sharding remedy are invertible to the same quantity. So the sharding by
> object under `K_obj` is still required, **and group extents must additionally be padded to a fixed
> quantum** or nothing size-bearing leaves `K_meta` (§18.7 M5, blocking). The `sid'` blinding construction is
> retired with its subject. `obj_ids[n]` — which §12.2 D-1 describes as permanently recording which
> blocks belonged to the subject who withdrew, and which got *finer* at object granularity — moves
> into the per-object row-group under `K_obj` and is covered by the same item.
>
> **NARROWED 2026-09-19 (one of the three disclosures shrinks).** With content-defined chunking retired for content (`eval/results/cdc_largefile.json`: CDC is −0.12 to −0.15 % on append and −5.04 % on scattered in-place overwrite, the dominant mutation profile) and content chunked at fixed 64 KiB, `lens[n]` becomes a constant sequence **except for one trailing remainder per object**: it carries essentially no content-localisation entropy, leaving only object size mod 64 KiB, so arithmetic check 16 no longer applies to the data plane in the form stated. It continues to apply to the METADATA plane, where CDC is retained — but there the boundary function is keyed (`HMAC(K_bnd, …)`), which was already the stated reason for keying it. **The `sids[n]` and `rdoms[n]`/`obj_ids[n]` disclosures are untouched by this and remain live defects**, and `sids[n]` is now the sharper of the two (§12.3). *(2026-09-19, and this narrowing is itself too generous: `lens[n]` does not leave "only object size mod 64 KiB" — under fixed 64 KiB chunking the constant entries supply the quotient and the remainder the low bits, so `sum(lens[n])` is the **exact** object size, and per-group offsets under the sharding remedy are invertible to the same quantity. `sids[n]` is deleted by §18.4; the exact-size channel is not, and closing it requires fixed-quantum group extents — §18.7 M5, blocking.)*
>
> **Add to the hard write-path invariant in D-3 below:** no object identifier that is content-derived.

**D-2. The GFSX cleartext preamble discloses content-derived structure.** `[ "GFSX" | ver | key_epoch | iv_base | ehdr_len ]` is in the clear by construction, ~16 times per parcel, ~6.7 × 10⁶ parcels. `ehdr_len` is a linear function of the chunk count and therefore a content-class fingerprint; `iv_base`'s session field clusters and orders xorbs across cartridges and across sites with no key at all; `key_epoch` makes rotation history readable.

> **Required:** pad the encrypted header to a fixed quantum so its length carries no bits; derive the IV (`HKDF(K_meta, volume_id ‖ ordinal ‖ offset)`) rather than storing it; move `ver` and `key_epoch` into the sealed fragment trailer.

**D-3. `ExtractEnum` protects only `leaf_salt`.** Entries are `{ rel, size, sha256, rdom, leaf_salt, spans[] }` and only the salt is under the redaction-domain key. `rel` is often MRN-derived; `sha256` is the *unsalted plaintext digest*, a pure confirmation oracle for any templated clinical text; `rdom` is the subject label. A cite-class extract is precisely the object designed to persist for a decade.

> **Required:** encrypt the whole entry body under the file's own key *(2026-09-19: "the file's redaction-domain key" literally becomes the file's own key — simpler and stronger)*, publish only `leaf_i = SHA-256(leaf_salt_i ‖ rel_i ‖ digest_i ‖ size_i)` outside the shred domain, keep no unsalted plaintext digest anywhere, and make it a hard invariant on the write path that no record containing `rel`, an unsalted plaintext digest or an rdom identifier may be admitted to the WORM tier.

### 12.3 Dedup across redaction domains was impossible; there is now no dedup, and the equality oracle survives the retirement

> **RETIRED 2026-09-19 — superseded by per-object keys** (`eval/results/ckpt_dedup_results.json`; `eval/results/cdc_measure.json` mean CDC marginal 0.795 %, exactly 0.0 in 3 of 8 pairs; `eval/results/cdc_largefile.json` overwrite_scattered −5.04 % at 4 %, the mutation a weight update is). The body below is kept verbatim as record. What each part becomes:
>
> - Cross-object dedup **remains impossible for exactly the reason given** — a copy readable under two keys is recoverable through two paths and re-encryption is impossible on WORM — and is now **moot**, because content dedup is retired outright. That impossibility argument survives this retirement and is what §8.4 rule 1 now cross-references.
> - The `dedup` table is retired, so **the catalogue-side equality oracle that table carried is gone**. The *media-side* oracle named in §12.2 D-1 is **NOT** gone: it lives in the in-xorb chunk table under `K_meta`, independent of the dedup table, and survives until `sid` itself is changed — **which §18.4 now decides: `sid` is deleted, and `xid` is re-derived from the write intent rather than from the sid sequence, because removing `sid` alone would have left the same oracle at whole-xorb granularity under `K_mac`, which survives every shred exactly as `K_meta` does.** D-1's mitigation is **still required** for the columns that remain: the sharding by object under `K_obj`, the `obj_ids[n]` relocation, and the fixed-quantum group extents that close the exact-object-size channel. Deduplication was the only thing that ever bought the oracle; it bought nothing, and the plaintext-equality half of it is now gone from the data plane. The **metadata** plane (`cid`, `vid`, the manifest `sha256`) is not, and is recorded at §16 item 14 and §18.8.
> - The partitioning requirement, `StageReport.dedup_loss_vs_single_domain` and `dedup_ratio`, and the open pricing question about `rdom_rule: subject` are retired with the choice they priced.
> - **Granularity can no longer be too coarse**, so the one-way door and the ingest refusal built on it are gone.

Storing one copy readable by two domains means its key is recoverable through two paths; destroying domain A's key then leaves the bytes readable through B. Re-encryption is the only escape and it is impossible on WORM. So **cross-rdom dedup is a contradiction, not a cost**, and the substrate is right to scope dedup within a domain.

The equality oracle exists and must not be used: `sid = HMAC(K_mac, chunk)` is rdom-independent while the `dedup` table records `rdom`, so a catalogue holder can test whether two subjects contain the same chunk with no content key — a re-identification channel on clinical text, where shared chunks are shared template and shared narrative. **Partition the `dedup` table by rdom** so the cross-rdom lookup is structurally impossible rather than policy-forbidden; it buys nothing but the oracle.

What must be stated, because it is currently an assertion where a measurement exists: the price of `rdom_rule: subject` is the *cross-subject* dedup forfeited, and nobody has measured it on this corpus. `StageReport` returns `dedup_loss_vs_single_domain` alongside `dedup_ratio`, so the choice is priced per lineage at ingest rather than argued in prose. **Rdom granularity can never be made finer retroactively** — bytes already on WORM are sealed under the coarse domain's key and no rewrite is possible — so declaring the redaction domain at ingest is a one-way door and a request to change it on a live lineage is refused with that reason.

### 12.4 Shredding must be a hardware key destruction

`redaction.shred` as specified destroys an LSM row and compacts the store. That is not sanitization: LSM compaction is a rewrite plus an unlink; wear-levelled flash retains compacted pages in spare area; and replicas, snapshots, operational backups and page cache of that store have no stated lifecycle. The design levels exactly this objection at LTFS and then rests its entire forget story on an unaudited delete from a rewritable store. It is also the first question an IRB or an auditor asks.

> **Required:** every content key is wrapped under a per-site HSM/KMS key with a *t*-of-*n* release policy, and `redaction.shred` is a KMS destroy-handle operation producing a **signed destruction receipt from each site**. `shred_state ∈ { ORDERED, CONVERGED, ATTESTED }`; a withdrawal is never reported as executed below `CONVERGED`; `unconverged_shreds` and time-to-converge are published operational metrics. No backup or snapshot of the key store may outlive the shortest legal withdrawal SLO.
>
> **HOLE opened 2026-09-19, recorded not filled.** The wrap-under-HSM and the per-site signed destruction receipt were priced per redaction domain — a handful of operations. Per object they are up to **~10⁶ destroy-handle operations and ~10⁶ receipts per consent-unit withdrawal** (the ~10⁶ is `STORAGE-DIRECTION.md`'s own object-count estimate, not a measurement, and **not** §8.8's row counts, which are chunks, xids and locators), against a *t*-of-*n* release policy. `shred_state` and the rule that a withdrawal is never reported executed below `CONVERGED` are unaffected **in intent**, but convergence time and receipt volume are unpriced at this granularity and `unconverged_shreds` may no longer be a small number. `STORAGE-BINDINGS-DECISION.md` already routes erasure through `NodeAgent.siteKeyDelete` (which requires `confirm=yes`) — the same scaling question lands there. **Not designed here.**

Note the inverted semantics this fixes: under threshold custody, destroying a *shared* key needs only `n−t+1` custodians to comply and a minority cannot preserve it; destroying a *replicated row* needs every holder to comply and a single unreachable replica preserves it. The coarse unit carrying no legal obligation had the strong destroy and the fine unit carrying the obligation had the weak one.

**Key rotation must never resurrect a shredded key.** Content keys are wrapped under `K_L`, so rotating `K_L` re-wraps every content key in the lineage — the one operation in the system capable of restoring a destroyed key if it ever runs against a stale copy of the key store. The re-wrap reads the live store, enumerates `SHREDDED` rows, and **refuses to re-wrap them**, with the refusal journalled and counted. Re-wrap from any other source is forbidden. *(2026-09-19: this paragraph is unaffected in substance by the retirement of `K_rdom` and survives intact at object granularity; only the key's name changes.)*

~~Separately, the per-PiB `K_L` rotation figure is stale under the `K_rdom` scheme: chunk data is encrypted under per-chunk keys with one GCM invocation each, so the SP 800-38D invocation cap is not the binding constraint.~~ **Rotation is driven by custody membership change, not by invocation count.**

> **The stated reason above became FALSE on 2026-09-19 and must be recomputed, not carried forward.** With one key per object, a 12.06 GB weights object is **184,044 GCM invocations under a single key** (`eval/results/ckpt_dedup_results.json`, `a_stats.blocks`), not one invocation per per-chunk key. The conclusion is probably still right — 1.8 × 10⁵ is far below any NIST bound — but nothing here has recomputed it against SP 800-38D for the largest object the archive will hold. No measurement bears on it. **Recorded, not resolved.**

### 12.5 Custody is the ten-year failure mode, and resharing is a prerequisite

At `n = 12`, `t = 7` with 5 %/yr irrecoverable share loss, a share survives ten years with probability `0.95¹⁰ = 0.599`, and `P(≥7 of 12 survive) ≈ 0.66`. **About 34 % of ten-year-old citations become undecryptable** — a ten-year WORM archive failing its only purpose one time in three, with every byte intact and every cartridge in perfect condition.

That is not a cost line. Having subtracted all access control down to the key, the design owes the key layer's maintenance mechanism.

> **Required, before any bytes are written:** proactive secret resharing on a fixed `key_epoch` boundary (Herzberg-style), which both repairs attrition and re-randomises against slow compromise. Under annual resharing the ten-year failure falls from ~34 % to below 10⁻⁴. A hard alarm at `t+2` surviving shares. An annual quorum drill whose measured output — time to assemble a quorum for a randomly chosen lineage — is a published operational metric, because an untested quorum is an untested backup. `decryptability_horizon` is an admission gate: a new cite-class pin into a lineage whose horizon falls inside the citation's retention is refused.

Durability keys are escrowed separately, at a lower threshold, with the fabric's own service identity holding a share. `K_idx(v)` and the scrub path protect placement metadata, not content; if they sit behind the same confidentiality quorum as the content keys *(2026-09-19: was `K_rdom`; retired, rename only)*, an expired credential or an unavailable approver stops an automatic repair. **Durability must never depend on the authorisation path**, and key material must never land on a locus whose `reclaimSemantics` is not `UNLINK`, or the storage tier itself destroys crypto-shred.

### 12.6 What an adversary learns

| Adversary holds | Learns |
|---|---|
| One cartridge, no keys | N opaque 1 GiB parcels, their count, write order, and the residual Bareos cleartext of §13.2. No names, no sizes that mean anything, no subjects, no plaintext digests. |
| One cartridge + custody quorum for that volume | Its full index: stripe ids, fragment indices, xids (keyed HMACs of the *write intent*, §18.4, so not a plaintext-confirmation oracle even to a `K_mac` holder), residency **ordinals** (opaque — the image of `PRP(K_ord(v), ·)`, so neither the value nor `max(ordinal)` is a population count — and useless without the custody-held ordinal map), and **which of a fragment's 84 data parcels share a residency unit**: `min(ρ, 84)` distinct ordinals, capped by geometry at ~6.4 bits per fragment. Not content, not an object count, not a co-residency partition over the volume's population, not an arrival order. *(2026-09-19: was "rdom ordinals"; restated at the §18.3 decision rather than renamed, because a per-object variable-length set would have made every one of those four "not"s false.)* |
| Two cartridges from two sites | Linkage by `leaf_root`: which cartridges hold fragments of a stripe. **This is accepted, and it is why `leaf_root` must never be published outside the fabric** — a root in an extract certificate or a leaked ledger turns a keyless integrity check into a targeting confirmation. |
| The catalogue | **Everything but content keys**, including filenames. This is the unresolved metadata-confidentiality problem and it is in scope for this design, not outside it — see below. |
| Two whole sites | All ciphertext for every stripe. A 2-of-3 collusion threshold **forced by the domain count, not chosen.** The erasure code provides *no confidentiality margin whatsoever*; all confidentiality rests on the custody quorum, which is the mechanism with the 34 %/decade failure rate. "Blind holding sites" must not be read as implying a margin that does not exist. |

The catalogue row is the one that is not yet answered by mechanism, and it must be treated as in scope:

> **Required:** (i) salt `rel` per object under that object's key *(2026-09-19: was "per redaction domain under `K_rdom`"; retired, rename only — the property is unchanged and the blast radius is tighter)*, exactly as `leaf_salt` is salted, so the path tree does not survive the erasure it documents; (ii) federate the `place` rows so each site holds only what it needs to plan repair, and keep the `volume_id -> (site, institution)` binding local to that site's scheduler rather than federation-wide — repair and materialisation need a content key and reachability, not a building address; (iii) hold index nodes under per-institution metadata trust domains.

The `RedactionRec` presents the same problem in miniature. Its survival is deliberate and right — a 2036 reader must distinguish audited erasure from media loss, and a breach must not be launderable as a redaction — but combined with `rdom_set` and monotone write positions it produces a standing register of who withdrew and when, and withdrawal correlates with adverse events. **Publish per-lineage, per-epoch aggregate redaction counts, which is all that is needed for that distinction, and hold the per-consent-unit detail in the shred store under the same destroy path.** *(2026-09-19: the §18.3 decision is what keeps this satisfiable. A per-object `obj_ords` set on WORM would have reinstated exactly this standing register at finer granularity on media that cannot be erased, after the key destruction it documents. `res_ords` does not: the surviving artefact is `(volume, PRP-image, SHREDDED)` in the erasable catalogue, carrying no subject, no time and no ordering, and the on-media vector is a bounded co-residency fact the §8.4 `packing:` declaration already publishes per lineage.)*

---

## 13. Disclosure: the complete inventory of what is permanent

### 13.1 The standing lint

> **Nothing written outside a seal may be a function of plaintext.** Not names, not real lengths, not record counts, not timestamps finer than a day, not plaintext digests, not content identifiers. Violate it once on WORM and it is permanent.

and its second clause, which is what makes the first enforceable across the Bareos boundary:

> **No plaintext-derived identifier — `xid`, a stripe id derived from content, a lineage id, or any content digest — may appear outside a seal, including in job names, volume labels, pool names, filenames, or any log or telemetry crossing a holder boundary.**

and, **added 2026-09-19 (§18.4), its third clause — scoped by KEY LIFETIME rather than by field name,
which is what makes it greppable and what makes it cover the fields nobody enumerated:**

> **No identifier written to WORM may be a function of plaintext under any key derived from `K_L`,
> because every such key survives every shred.**

One formulation covers `sid` (deleted), `xid` (re-derived from the write intent), the cnode `cid`,
the `vid`, the manifest whole-file `sha256` and any content-derived stripe id. It replaces §17's
old chunk-id line, whose parenthetical exempting `xid` was **unsound**: `xid` was a keyed hash of a
sequence of keyed hashes of plaintext, so `place` — 65.6 M immutable federation-wide rows sharded by
`xid` prefix — was exactly the structure the rule forbade, and a reviewer grepping as instructed
would have found nothing and certified the design conformant.

This is the only *generative* rule in the document: it decides questions nobody has asked yet, it converts into a test against a component we did not write (§6.3), and it is the only invariant here whose violation is irreversible. It is therefore a refusal in code, not a principle in prose.

### 13.2 Everything permanent on unerasable media, after the contract

| Source | Field | Bits it carries |
|---|---|---|
| Parcel head | magic, parcel ordinal, flags, crc32 | write order within the volume — inherent to append-only media |
| Parcel body | ciphertext ‖ CSPRNG padding | none; every parcel is exactly 1 GiB |
| Fragment trailer | magic, ordinal, crc32 (cleartext); everything else sealed under `K_idx(v)` | count of fragments — **and nothing more, because the trailer's length is a constant (§7.1, §18.3). Had `obj_ords` been written as a variable-length set, trailer length would have become a cleartext function of the fragment's object count, readable with a drive and no key: D-2's `ehdr_len` defect reintroduced at a new site, permanently.** |
| Index checkpoint | magic, ordinal, crc32 (cleartext); everything else sealed | count of checkpoints, and — because checkpoints are cumulative and every entry is fixed-length — the count of fragments written before each one, which the row above already books. **Unpadded and variable-length it would have carried the whole cartridge's object count, measurable with a ruler; this is the structure where that defect is worst, and §18.3 closes it by construction rather than by a padding rule.** |
| **Bareos volume label** | `VolumeName` (random), `PoolName` (class ordinal), `MediaType`, `HostName` (opaque site token), `LabelProg`/version, **label timestamp** | the volume's own commissioning day |
| **Bareos session labels** | `JobId` (counter), `JobName`/`ClientName`/`FileSetName` (constants), `JobFiles`/`JobBytes` | **zero** — one job = one fragment = a constant parcel count of a constant size |
| **Bareos block headers** | `BlockNumber`, `VolSessionId`, **`VolSessionTime` (unix timestamp)** | **a per-volume, second-resolution write-order timeline** |
| **Bareos attribute records** | filename `<volume_id>/<ordinal>`, size (= `PARCEL_BYTES`), mtime | the same timeline |

**The residual, declared:** *a per-volume, second-resolution ingest timeline, and the fact that N opaque 1 GiB parcels exist in M fragments.* Nothing else. Removing the timestamp channel means forking the Bareos block header, which forfeits `bls`, `bextract` and `bscan` and with them the externally maintained reference reader that §2.3 identifies as the largest thing the split buys. **That is the trade, and it is decided here explicitly rather than by a claim of absence.** Ingest is batched into per-epoch-day jobs so the channel degrades toward day resolution in practice.

### 13.3 The three claims that must never be made

1. **"Destroying the index key shreds the cartridge."** It does not (§7.4). It is a cost multiplier.
2. **"A purged Bareos volume is an erased volume."** It is not (§6.5).
3. **"Quarantine prevents reading."** It does not (§11.4). It is an advisory with no enforcement behind it.

The only erasure claim this system may make to a governance body is **key destruction at redaction-domain granularity, attested by HSM destruction receipts from *t*-of-*n* sites** (§12.4).

---

## 14. Conserved resources and the capacity model

All figures derive from: 3 sites × 3 LTO-10 drives, ~100 licensed slots per site, 30 TB native per cartridge, 400 MB/s native, `O = 265 s`, reposition 40 s, `W = 4`, combined coding rate 1.714×. Basis: **MODELLED** except where marked.

### 14.1 Drive-seconds

| | |
|---|---|
| Fleet drive-seconds per year | 9 × 3.15 × 10⁷ = **2.84 × 10⁸ s** |
| Wave (W = 4) | 1,416 s, 412.4 GB, 291 MB/s, 73 % duty |
| Waves per year at 100 % dedication | **200,400** |
| Fragment bytes read per year | ~~**82.7 PB/yr = 226 TB/day**~~ **RETIRED 2026-09-19** — see the measured rows below |
| Tenant share after the 15 % standing reserve | ~~**192 TB/day**~~ **RETIRED 2026-09-19** — the measured standing commitment is **8.5 %**, not 15 %, and no reserve setting recovers the gap; clustering does |
| Delivered payload per year — **MEASURED 2026-09-19** | **45.0 PB/yr = 126.2 TB/day clustered; 23.4 PB/yr = 65.5 TB/day hot; 11.9 PB/yr = 33.3 TB/day scattered**, already net of the 8.5 % standing commitment (`eval/results/plant_contention.json`) |
| Same plant, deepest deadline-feasible load in the load sweep | **~156 TiB/day clustered ≈ 57 PB/yr** at 80.5 % payload and 0 % late (`eval/results/plant_sim.json`) |

> **CORRECTED 2026-09-19.** The retired row is §3.5's W = 4 wave (291 MB/s) × 9 drives × 3.15 × 10⁷ s at 100 % dedication — a drives × rate × hours figure. Measurement puts delivered capacity between **11.9 and 45.0 PB/yr** depending entirely on co-occurrence clustering, and at most **~57 PB/yr** clustered at the deepest load the plant sustains without missing a deadline: **1.5× to 7× below the retired row**.
>
> **Two things this table can no longer pretend.** (1) **Unit change, stated rather than hidden:** the retired row counted *fragment bytes read*, coding amplification included; the measured rows count *delivered payload*, because that is what the harness moves. The factor between them (nominally 1.07× intra-cartridge, more under orthogonal packing) is unmeasured, so the old and new rows are **not interconvertible**. (2) **The two harnesses disagree by ~1.3× on the clustered figure**, and the disagreement is not resolved: `plant_contention` scales the 7.8 TiB/day operating point (653.3 GB/drive-hour) linearly to a year, while `plant_sim`'s load sweep measures GB/drive-hour *rising* with queue depth (46.5 % payload at 7.8 TiB/day → 80.5 % at 156.3). Until one harness prices the other's effect, this plant has a **range, not a number** — and both harnesses model a 90 s mount against §3.4's `O = 265 s`, so both are optimistic in the same direction.

### 14.2 Load cycles and robot exchanges

Media rating ~20,000 load/unload cycles ⇒ a budget of **2,000 loads per cartridge per year** over a decade ⇒ **480,000 plant mounts per year**.

Setting that equal to the drive-second budget gives a crossover: **below ~131 GB per mount, media life binds before drive-seconds.** A `W = 1` wave is 103 GB and therefore violates the media budget outright. So the mount-size floor is confirmed by a second, entirely independent physical constraint, landing within 27 % of the duty-derived answer. This is the single strongest evidence that the geometry of §3 is right rather than merely internally consistent.

~~At `W = 4`: 835 loads per cartridge per year, **8,350 over ten years, 42 % of the rating.** Robot: 66,800 mounts per site-year × 2 moves × ~15 s = **6.4 % accessor duty**~~ — **CORRECTED 2026-09-19.** At the **measured** bytes-per-mount (`eval/results/plant_sim.json`), not at `B*`, with each workload run at its own measured delivered capacity (`eval/results/plant_contention.json`):

| workload | GB/mount | plant mounts/yr at delivered capacity | loads/cartridge-yr | % of the 2,000 budget | accessor duty |
|---|---|---|---|---|---|
| clustered | 111.1 | 404,770 | 1,687 | **84 %** | 12.8 % |
| hot | 27.6 | 846,014 | 3,525 | **176 %** | 26.8 % |
| scattered | 13.3 | 891,729 | 3,716 | **186 %** | 28.3 % |

**The 131 GB/mount crossover derived above is confirmed and binding**: measured bytes-per-mount is 111.1 GB clustered and 13.3 GB scattered, so on anything but a clustered workload **media load-cycle life is exhausted before the drive-hour budget is** — the second, independent constraint fails first. Clustering is a precondition for media life as well as for throughput. Accessor duty at 26–28 % is still not binding but is no longer comfortable, and it interacts with the serialising changer lock (`BAREOS-RECOMMENDATION.md` R-8). It *is* still the constraint on any campaign whose per-cartridge work is short (§7.2).

**Basis, stated:** every row is computed at the harness's operating point of 2,000 requests over 24 h. Bytes-per-mount rises with queue depth (§3.5 note) and the harness does not report it at higher load, so the 176 % and 186 % overshoots are **measured at shallow queues and may shrink at depth — by how much is unmeasured.** The clustered 84 % and the ordering across workloads are not in doubt. **What happens when the budget is exceeded is unspecified anywhere in this document set** — no cartridge-retirement plan, no consumable budget for premature replacement, no admission rule denominated in load cycles (§16).

Cleaning cartridges are an annual consumable, not a fixture: at ~70 % duty, three drives run ~18,400 tape-motion hours per site-year, so at a ~100-hour cadence that is ~184 cleaning cycles, against ~50 uses per cartridge. **Budget ≥ 8 cleaning cartridges per site per year** and reserve 4 resident slots.

### 14.3 Slots, capacity and the bill of materials

| | |
|---|---|
| Logical target | 4.2 PB |
| Media at 1.714× | **7.20 PB** |
| Cartridges | **240 (80 per site)** |
| Slots occupied | 80 + 4 cleaning = **84 of 100** |
| Growth headroom before expansion frames | 16 cartridges/site = 1.44 PB media = **0.84 PB logical** |
| Alternative at local RS(30,2) | 1.6× → 6.72 PB → 224 cartridges → 75/site |

**The slot-headroom finding that has no cheap answer:** a site-loss rebuild must write 80 cartridges' worth of fragments. At 16 free slots per surviving site, re-placing onto the survivors **is not possible**. Regeneration therefore requires a *replacement domain with slots*, and **procurement lead time is inside the repair window**. The recovery plan is procure-a-site, and that must be written into the operations runbook rather than discovered during a durability emergency.

### 14.4 Standing obligations

| Obligation | Drive-days/yr | % of 3,285 |
|---|---|---|
| Annual full scrub (7.20 PB) | 208 | 6.3 % |
| Generational migration, amortised over 8 yr | 52 | 1.6 % |
| Ingest at 1 TB/day logical | 18 | 0.55 % |
| Expected repair (1 cartridge/yr) | 3.6 | 0.11 % |
| 1 % cross-drive verify | 0.2 | 0.01 % |
| **Total standing** | **282** | **8.6 %** *(VALIDATED 2026-09-19: measured committed standing load **8.5 %** — `eval/results/plant_contention.json`)* |

> **Repack is deliberately absent from this table** because GC is off on the WORM tier. Priced, for the case where it is nevertheless run: **1,537 drive-hours = 1.9 % of the plant-year at 85 % dead (15 % live to rewrite); 5,124 drive-hours = 6.5 % at 50 % dead; 1,025 = 1.3 % at 90 % dead.** Generational migration is **10,247 drive-hours = 13.0 % once per decade** (the amortised 1.6 %/yr row above reproduces it). All are sequential whole-cartridge passes, which is why they are cheap; none is what the plant runs out of. *(Note for readers reconciling against the JSON: `plant_contention.json` `conclusions[0]` calls the 1,537-hour row "a 15%-dead repack" while its own `standing_obligations` row is labelled "repack at 85% dead". The row is the cheap case — 15 % live. The label, not the number, is the slip.)*
>
> **The annual scrub row is corrected to 214 drive-days / 6.5 %** by the same measurement (§11.5); 208 / 6.3 % was byte-only.

The obligation device is **33 % of the plant by device count and ~9 % by standing load**. The surplus is surge capacity for repair campaigns and a hot spare. During a migration or a site-loss rebuild the partition is re-cut (2 obligation, 1 tenant) with a published service-level change, because the alternative — starving obligations to protect tenants — is how a plant arrives at a rebuild it cannot finish.

Abandoned extents (§5.2) are charged to capacity and reported as `unreclaimableTombstoned`, never as headroom.

### 14.5 Failure campaigns

| Event | Read | Write | WAN | Wall | Drive-days |
|---|---|---|---|---|---|
| One parcel, media defect | 28 GiB, same mount | — | 0 | **75 s** | 0.001 |
| One cartridge lost | 60 TB | 30 TB | 30 TB | **~9.5 h** | 3.6 |
| **One site lost** | **4.8 PB** | **2.4 PB** | **2.4 PB** | **32 days drive-bound; 24 days at 100 % of the federation core, 96 days at a 25 % share** | **285** |

**The site-loss window is WAN-bound, not drive-bound**, so drives cannot buy it down: the two constraints land within 4 % of each other at a 100 % network share and diverge in the WAN's favour at any realistic share. Plan on **~3 months, at zero global coding margin throughout**, with only the local RS(j,4) band standing between a second fault and data loss. That number, and not the code's nominal tolerance, is the durability figure to put in front of whoever signs the statement — and it is the argument for a fourth failure domain (§16 item 8).

### 14.6 The selectivity law, and what affinity is worth

Useful delivery is fragment bytes multiplied by the fraction of touched bytes actually wanted. Worked, on a 40 TB pathology lineage (222 stripes, 222 data fragments per site, 22.9 TB on one cartridge), delivering a 200 GB cohort of 50 subjects at 4 GB each:

| | Affinity-packed (subject-affine) | Unpacked (arrival order) |
|---|---|---|
| Mounts | **1** | ~50 |
| Bytes read | 214.7 GB (1.07× amplification) | 214.7 GB |
| Repositions | 49 × 40 s | 0 (but 50 mount cycles) |
| Wall | 265 + 1,960 + 537 = **2,762 s (46 min)**, one drive | ~1,530 s, but only by seizing all nine |
| Drive-hours consumed | **0.77** (MODELLED; = 260 GB/drive-hour, inside the measured clustered band of 189–653) | 3.83 (= 52 GB/drive-hour; **measured reactive baseline 68.06** — same order, modelled figure ~24 % conservative) |
| Media load cycles | **1** | 50 |
| Bytes per mount | **215 GB** (MODELLED; best measured is 111.1 GB) | 4.3 GB (**measured reactive 4.0 GB** — closely corroborated) |

> *2026-09-19 (`eval/results/plant_sim.json`): the unpacked column is corroborated by measurement; the affinity-packed column is a modelled upper bound roughly 1.9× above the best bytes-per-mount observed in any configuration. **The direction and the load-cycle argument stand** — packing is what keeps a workload above the 131 GB/mount media crossover of §14.2 — but read the 5× as a ceiling, not a measurement.*

**Affinity packing is worth 5× in drive-seconds and 50× in load cycles on this workload, it is chosen once at write time, and it is irreversible on WORM.** The load-cycle column is the sharper one: at 4.3 GB per mount the unpacked read sits ~30× below the 131 GB media-budget crossover of §14.2, so a workload of that shape does not merely run slowly — it consumes the cartridges. That is why §8.4 makes packing a precedence-ordered rule with a published quality metric rather than a hint.

The same lineage under a 0.5 % *uniform tile sample* touches ~100 % of its fragments: 22.9 TB read to deliver 200 GB — **114× amplification and ~7.3 hours of one site's entire drive complement**. That request is **refused**, with the `1 − (1−p)^c` arithmetic attached and a derived sample-ordered lineage offered (§8.4).

---

## 15. What was deleted, and what each deletion cost

**Deleted from the storage layer:** filesystems; namespace and hierarchy; path lookup; per-object metadata; extended attributes; timestamps finer than a day; meaningful lengths; permissions and ACLs; free-space maps; allocation; defragmentation; in-place mutation, `truncate`, `rename`; at-rest deduplication, compression and encryption; journalling and `fsck`; quotas; LTFS; any object-store API on the medium; LTO hardware compression; LTO hardware encryption; predicate pushdown at the holder; every eviction ranking function; the synchronous read verb; `stat()`; `verify()` as a block call; `scan()` as a routine path; racing `k` of `n`; rebalancing; the weighted-random placement sampler on the tape tier; `materialise`/`cast` as a second byte-moving verb; the per-cartridge index key as a shred unit; a fabric-wide index key; the cumulative tail index; sibling-verifier cross-indices; LRC local groups; `offset`, `length`, `fmt`, `gen`, `day` and `_pad` from the locator; the 10⁹-row placement table; and — the one that does the structural work — **`delete`**.

**Deleted by the owner's constraint:** the ~1,600-line tape block layer; `gfs-mover` and `CAP_SYS_RAWIO`; the CDB allowlist; SCSI Persistent Reserve; twelve of the twenty SCSI risk-register rows; and the decade-long obligation to publish a format spec and maintain a reference reader.

**What each cost:**

| Deletion | Cost |
|---|---|
| **`delete`** | Capacity is never reclaimed below a whole volume, so forgotten data occupies media until the next generational migration — ~1 %/yr, and the binding constraint is slots, not dollars. **Bought:** an SPI that is honest on every medium by subtraction rather than by exception, and the freedom for `retire` and `migrate` to rewrite everything without breaking a reference. |
| **Names on media** | Media are worthless without custody quorum — which is the security property we wanted — but rebuild now has a *governance* dependency, not merely a technical one. Mitigated by escrowing durability keys separately at a lower threshold (§12.5). |
| **The tape block layer** | We do not own the retry policy; a marginal cartridge can consume a drive in an internal retry storm, and local-parity reconstruction moves from during-the-pass to after-the-error, costing one extra mount in the rare case. We lose RAO. **Bought:** the removal of the design's own worst weakness — 1,600 lines with zero field exposure whose failure mode is silent data loss — and an externally maintained reference reader. |
| **Owning the on-media format** | Bareos writes a permanent, unerasable, second-resolution write-order timeline (§13.2). Contained by a naming contract and a commissioning lint, never eliminated. |
| **At-rest dedup and compression** | The tape tier stores 1.714× the logical bytes with no cross-dataset savings. **Measured twice, this costs ~0.** Indirectly: CDC bought 0.8 % over whole-file reuse on 561 commits of real source history (zero in three of eight version pairs) and −5.04 % to +1.47 % on the dominant mutation profile; intra-corpus chunk dedup was 0.6 % on a venv and 0.0 % on audio and video. **Directly (2026-09-19, `eval/results/ckpt_dedup_results.json`):** real training checkpoints share **exactly zero** 64 KiB blocks — adjacent, distant, between the two weight copies inside one checkpoint, and cross-run — with a cross-run control at zero confirming the measurement discriminates. **Bought:** the 10¹⁰-entry index at the storage layer, and a per-block read-modify-write path that WORM cannot serve. **And bought back:** per-object keys, and with them the per-object crypto-shred D1 had removed. |
| **`verify()` as a call** | No cheap integrity poll at block granularity. Replaced at strictly lower cost by the leaf tree: `prove` is 8 MiB, ranged reads verify, and RS gets its erasure positions. |
| **Asynchrony in the block layer** | The block plane cannot be called by a consumer; every path goes through the plant scheduler. This is the point. |
| **The read verb** | Existing synchronous callers do not port. **Bought:** one planner, one union, one receipt, and fetch-versus-ship as a strategy selection inside one call rather than an architectural fork. |
| **Racing** | A slow holder costs a re-plan after a timeout instead of a hedge. **Bought:** roughly 17 % of the plant that hedging silently consumed. |
| **Access control at the storage layer** | Every enforcement is at the key, which concentrates the archive's entire failure profile into custody health. This is what makes §12.5 a prerequisite rather than an improvement. |
| **Rebalancing** | Resources join and leave without moving a byte, at the cost of long-lived placement skew corrected only by repair and attrition — the cheapest policy available when the alternative is mounts. |
| **Predicate pushdown** | Not a cost of this design: a blind holder cannot evaluate a predicate over ciphertext under any on-media format, so raw SCSI and LTFS lose it identically. Stated because it was historically the strongest argument for owning the format, and it is void. |

**Re-derivations, declared so a reviewer need not find them.** The append-and-seal fragment log is a write-ahead log; we take its durability barrier and refuse its checkpointing and truncation. The sealed per-volume index is a self-describing archive volume (tar/AFF/BagIt lineage); we take the trailer placement and refuse every cleartext field. The wave scheduler is Hillyer–Silberschatz serpentine scheduling; we take the monotone-sweep result and refuse the reservation semantics. The bootstrap record is Bareos's and we take it whole. "Placement is recorded, never computed" is what HPSS, Enstore, CERN CTA and Bareos's own `Media`/`JobMedia` tables already do, for exactly our reason — we adopt it without claiming it, and take the independent convergence as evidence rather than coincidence. Nothing here is new except the separation of the four quanta (§3) and the `class`-plus-`res_ords` sealed index that makes media-only rebuild reach the catalogue tier and the shred journal (§7, §18.3).

---

## 16. What is unmeasured, and what must be measured before media is bought

Ordered by how much of this document turns on them.

1. **`O`, the four-term mount cycle**, on the actual library. Instrument robot pick, load, ready, first-byte, rewind, unload and robot place over a few thousand exchanges and publish the *distribution*, not the mean. A 45 % error moves `B*` by 44 % and plant output by ~23 %. Everything in §14 scales off it. **First commissioning task.**
2. **Achieved streaming rate at `Maximum Block Size` 1–2 MiB through a network-fed spool.** If the drive shoe-shines, every rate in this document is void. Measure before believing any of them.
3. **LTO-10 reposition time and whether RAO or an equivalent exists**, and the wrap count, tape length and search velocity. The 40 s figure is inherited from LTO-8/9-class media and LTO-10 holds 67 % more bytes at the same 400 MB/s, so tape length per byte went up and locate per byte plausibly got worse.
4. **Cartridge and drive load/unload cycle ratings, in writing, before purchase.** These set hardware life (§14.2) and they are a capital line, not a footnote.
5. **The exact Bareos on-media cleartext field list for the deployed version** (§6.3). One-shot, version-dependent, and the whole disclosure argument rests on it.
6. **Cross-subject sharing on the real KOS corpus — still open, but it no longer decides a key question.** ~~This single number decides whether `rdom_rule: subject` costs 1 % or 40 %~~ — `rdom_rule` is retired (2026-09-19) and §12.3's preserved impossibility argument already forbids cross-domain dedup, so this number cannot change the key design. **It still decides whether 4.2 PB logical is real**, which is a capacity input and stays in this section. Measure *whole-object* reuse, not chunk reuse: `eval/results/cdc_measure.json` shows the recoverable sharing on real version history is whole-file (13.4–47.9 %) with CDC's marginal contribution 0.795 % mean and exactly 0.0 in 3 of 8 pairs. **Note this remains the one population where no measurement exists in either direction** — §12.3 argues shared chunks on clinical text are shared template and shared narrative, and with cross-object dedup retired any such saving is now **forgone by decision, not measured absent**. Plan accordingly: logical bytes equal stored bytes, times 1.714×, times pin amplification, times ~1.7× for two-LTO-generation coexistence. Nothing in this document may take credit for at-rest deduplication.
7. ~~**Checkpoint-to-checkpoint sharing on real model weights.**~~ **ANSWERED 2026-09-19** — `eval/ckpt_dedup.py`, `eval/results/ckpt_dedup_results.json`, measured on a DGX compute node over `ft/checkpoints/sft_v530_v6_long_p2` (checkpoints every 500 steps, ~48 GB of tensors each). Frozen backbones do **not** share byte-identical regions: adjacent weights **0 of 184,044** 64 KiB blocks, distant weights (500 → 3727) 0, the safetensors/FSDP copies of the same checkpoint 0 (different serialisations of the same tensors are different bytes), the cross-run control 0 — which shows the measurement discriminates rather than being broken — and optimizer state 0.002 % excluding zero blocks; self-dedup 0.000 % throughout. **The document's own second branch therefore fires: per-object keys are affordable, `K_rdom` is retired, and the hardest unsolved problem in the design is removed by measurement rather than solved by engineering.** The consequence the question did not anticipate must be stated with it and is worse: **checkpoints can also not be recomputed** — a `NONDETERMINISTIC` derivation may never be silently rebuilt (`ENTAIL-AGENT-NATIVE-FS.md` §3.4), and non-associative floating-point reduction order makes most GPU training nondeterministic unless pinned (§14 there) — so they are irreducible cost on both axes and **retention is the only remaining lever. Nothing in this document set currently specifies a checkpoint retention policy; that gap replaces this question.**
8. **The fourth failure domain.** A credible cost for a 1–2 drive, 40–80 slot satellite turns domain count into a budget line rather than a fixed three. Three sites cap the code at 1.5× or 3.0× with nothing in between, force a 2-of-3 ciphertext-collusion threshold, and produce a ~3-month zero-margin rebuild window that no amount of drive purchase shortens. **The site count, not the code, is the binding parameter**, and the most likely site-loss event over ten years is an institution withdrawing at a budget cycle.
9. **The consent-withdrawal rate at cohort scale.** Nobody has measured it on a clinical lineage; it sets the rate at which effective capacity decays and the design has no answer if it is high.
10. **Damage-extent distribution on LTO-10**, which decides whether contiguous RS(28,4) is adequate or symbol interleaving is mandatory.

**Opened 2026-09-19 by the measurement pass. Recorded, not solved — these are holes, not work items with known answers.**

11. **Real co-occurrence, mined from an actual request log.** `eval/results/plant_sim.json` states plainly that its cartridge assignment is synthetic. Clustering moves delivered capacity 3.8× — between 11.9 and 45.0 PB/yr — and packing is irreversible on WORM, so mining the log is a **prerequisite for sizing and for the §8.4 packing decision, not a refinement of either.** Nothing currently owns it.
12. ~~**The successor to `obj_ords` on unerasable media (§7.1), and it is time-critical.**~~ **DECIDED 2026-09-19 — §18.3.** `obj_ords` is replaced by `res_ords`, a fixed-length parcel-resolution residency vector under sparse custody-keyed permuted per-volume ordinals, with a `PARITY` class value and `res_gran`/`res_scope` discriminators. What replaces this item is **not** a granularity question but three measurements it *removed* from the critical path (M7, M8, M10 in §18.7) and one it left blocking (M6, the differential disclosure test against the commissioning cartridge).
13. **Per-object HSM destroy-handle volume and convergence time (§12.4).**
14. ~~**Whether a content-derived chunk id (`sid`) should exist at all**~~ **DECIDED 2026-09-19 — §18.4.** `sid` is deleted; chunks are addressed as `(xid, i)`; `xid = HMAC(K_mac, idempotency_key ‖ xorb_seq)`. What replaces this item, and what the question should have asked, is the **metadata plane**: `cid = HMAC(K_mid, canonical body)` and `vid = HMAC(K_mid, canonical(VersionRoot))` are the same defect one layer up under a key that survives every shred, cnode bodies carry `rel` (often MRN-derived, per D-3) so the oracle's inputs are *guessable* rather than requiring possession, and `vid` has a live recompute consumer that `sid` never had. Plus the **manifest whole-file `sha256`**, which is *unsalted* and therefore a **keyless** oracle strictly stronger than `sid` — one guess confirms a file. D-3 already forbids it and nobody applied D-3 to the manifest; `STORAGE-DIRECTION.md`'s own open item 13 — the argument for dropping `sid` — cites that digest as covering integrity. **Cartridge 1 may carry `class = MANIFEST` parcels only under the §18.8 write-path refusal.**

15b. ~~**The GCM IV reservation discipline under per-object keys — the third one-way door.**~~ **DECIDED AND IMPLEMENTED 2026-09-19 — §20, `crypto/SegmentCipher`, 14/14.** Original statement retained: Under `K_rdom` the chunk key was `HKDF(K_rdom, "chunk" ‖ sid)`, unique per chunk, so IV collisions across xorbs were harmless. Under `K_obj` one key covers every chunk of the object — 184,044 invocations for one 12.06 GB weights object — and nothing specifies that the counter-block allocator reserves `n + 1` counters per xorb or that two xorbs sharing a `K_obj` never receive overlapping ranges. IV reuse under AES-GCM is GHASH subkey recovery and tag forgery across the lineage, catalogue cnodes included, permanently, on WORM. **Recovery class: unrecoverable by any mechanism; no version field helps.** D-2's prescribed fix `iv = HKDF(K_meta, volume_id ‖ ordinal ‖ offset)` is additionally **unimplementable** — `volume_id` and `ordinal` are assigned by `seal()` at the site after despool (§4) while encryption happens at origin before spooling (§11.1), and one ciphertext lands at three distinct `(volume, ordinal)` pairs and is then erasure-coded. D-2 was filed as a disclosure defect; the `K_rdom` retirement silently promoted it to a correctness defect and nothing recorded that.
15. **The lease-aggregation unit for small objects (§9.5)**, without which the published 75 s shred window holds only for large-object lineages.
16. **What happens when the media load-cycle budget is exceeded (§14.2)** on a non-clustered workload: no cartridge-retirement plan, no consumable budget, no admission rule denominated in load cycles.
17. **Admission control on retrieval demand.** At 100 TB/day scattered, retrieval alone is 275 % of the plant-year (`eval/results/plant_contention.json`). §8.7 applies a hard quota to *committed bytes*; nothing applies a comparable ceiling to *read demand*, and the measurement says the failure mode is infeasibility rather than slowness — a different refusal from the one currently specified.
18. **Rebuild concentration.** 6,763 drive-hours is 8.6 % of a plant-year but needs ~6 drives continuously for ~47 days. `plant_contention` prices the year, not the window. Both framings must appear together or 8.6 % will be misread as spare capacity.
19. **The durability of a node-local path against a shared one.**
20. **The required sustained spool rate (§8.7).** The ~112 MB/s figure is the drive's speed-match floor; what the spool must sustain is that plus concurrent inbound during a despool wave, and that number has not been derived. Any commissioning refusal written before it is derived would be an invented number, so none is specified. `eval/results/fsync_cost.json` measures *rate* only (339 MB/s vs 8.6 MB/s on one host) and nothing in `eval/results/` measures durability, yet §12.5's `reclaimSemantics` rule and the `durabilityScore`/`accessCost` split both turn on it.

---

## 17. Conformance checklist

A binding conforms iff every item holds. Items marked **[LINT]** are automated and run in CI or at commissioning; the rest are design obligations.

**Format and disclosure**

- [ ] **[LINT]** Every parcel is exactly `PARCEL_BYTES`; `append` refuses anything else.
- [ ] **[LINT]** Padding is CSPRNG output; the last 64 KiB of every sealed parcel is statistically indistinguishable from its head.
- [ ] **[LINT]** No cleartext field on media is a function of plaintext; the commissioning cartridge dump (§6.3) diffs clean against the allowlist, and the lint re-runs at every Bareos upgrade and every migration.
- [ ] **[LINT]** No string reaching Layer 0 matches a lineage, institution, study, subject, modality or date; the submitter refuses outside `^[A-Za-z0-9._/-]{1,64}$`.
- [ ] The locator serialises to exactly 56 bytes, big-endian, with no padding field, verified by round-trip.
- [ ] `leaf_root` never appears outside the fabric — not in an extract certificate, not in a published ledger, not in telemetry crossing a holder boundary.

**Block plane**

- [ ] No SPI method causes a mount except `open`.
- [ ] `append` returns a real ordinal immediately, journalled before the next parcel; a write-intent row exists before the first byte.
- [ ] `seal` compares the origin-supplied root and refuses on mismatch; it never computes the root.
- [ ] `recover` is the mandatory first call in `APPEND` mode.
- [ ] `abandon` writes a tombstone; abandoned extents are charged to capacity and never present as headroom.
- [ ] `retire` is token-verified, journalled, refused while live rows reference the volume, and returns a typed `Erasure` read from the medium's own WORM status.
- [ ] Faults return a typed classification; a (drive, volume) fault histogram exists; exactly one TapeAlert reader; two distinct drives must implicate a volume before retirement.

**Bareos**

- [ ] **[LINT]** `Maximum Block Size` 1–2 MiB on Device and Pool, set before the first label, recorded in MAM and compared at every mount.
- [ ] **[LINT]** `Maximum File Size` = `PARCEL_BYTES`; `Maximum Concurrent Jobs` = 1 on every WORM device.
- [ ] **[LINT]** `Recycle = no`, `AutoPrune = no`, `Purge Oldest Volume = no`, retentions ≥ archive horizon, `Action On Purge` ≠ `Truncate`.
- [ ] **[LINT]** Hardware compression, SD Auto Deflate/Inflate, software compression, PKI data encryption and drive encryption all OFF, drive encryption asserted off by read-back before the first write.
- [ ] **[LINT]** The live pool and device config hash matches the commissioned hash; the submitter refuses on deviation.
- [ ] The plant scheduler is the only submitter to the Director; devices are physically partitioned into tenant and obligation pools.

**Distribution**

- [ ] `place` carries `(stripe_id, frag_i, parcel_ordinal, offset, len)`; DIRECT and DECODE are distinct, specified strategies.
- [ ] Every `loc` row carries `coding_id`; the coding registry is replicated with the catalogue and written into every volume index.
- [ ] Parcels are object-pure **or `pooled(n)` with the three costs of pooling declared and accepted (§8.4 hole)** — this line must name the hole rather than assert purity, which §8.4 rule 1 can no longer guarantee at object granularity; consent-unit runs are interleaved, never cohorted; packing quality is published per version. *(restated 2026-09-19)*
- [ ] Bands are contiguous; local parity is at the end of the band; short bands use RS(j,4).
- [ ] Tape-resident fragments are excluded from availability-driven repair; repair consults the shred journal and refuses on a tombstone; repair has a WAN budget.
- [ ] Degraded commit at 2 of 3 with `DURABILITY_DEBT`, capped, refusing ingest above the cap.
- [ ] `commit` draws against a pledge and a per-day plant byte budget and refuses with the standard `Refusal` shape.
- [ ] Presence is three-valued and includes `EXPORTED{custodian}`.

**Materialisation**

- [ ] `realise` is the only byte-moving verb; four gates in order; Coverage charged leaf-for-leaf and consent-unit-for-consent-unit. *(2026-09-19: "rdom-for-rdom" renamed; the consent unit survives as the counting unit, §9.7.)*
- [ ] The stage holds ciphertext; `spans` is an encrypted chunk; `spans` carries the `vid` binding header.
- [ ] The locus never receives an object content key; the key agent refuses at `shred_epoch ≥ S` and fails closed on staleness; **the lease-aggregation unit is declared and its mint rate published (§9.5 hole)**; the shred window is published, annotated as established for large-object lineages only. *(restated 2026-09-19 — this line must NOT read "leases are per-object", which would certify an open hole as satisfiable.)*
- [ ] Non-deliverable leaves are typed and published at admission; redacted leaves carry the `RedactionRec` digest; no `ENOENT`.
- [ ] `materialisation_policy` is a (lineage × Purpose) grant with `valid_until`, re-evaluated at `realise` and `extend`.
- [ ] Eviction is ephemeral-key destruction with a receipt; reclamation is lazy under pressure, not wall-clock; refcount is per parcel.
- [ ] Every Residency and Receipt carries `rdom_closure_size` and `expected_underivable_by`, **counted in distinct consent units and never in object keys** (§9.7 correction, 2026-09-19).
- [ ] Exactly one reference adapter over `spans` exists and is the conformance test.

**Cryptography**

- [ ] **[D-1]** **[LINT]** The in-xorb chunk table is sharded **by object**, each row-group encrypted under that object's `K_obj`, with only the group count and fixed-quantum group extents under `K_meta`; `sids[n]` is absent from the wire format; `obj_ids[n]` is inside the row-group, never under `K_meta`; **no field under `K_meta` is a function of any object's true length** — group extents are padded to a declared fixed quantum, so neither `lens[n]` nor an offset difference is invertible to an object size. *(Rewritten 2026-09-19 — the previous item was UNSATISFIABLE because it named `rdom` and `K_rdom`. The successor id scheme is now chosen, §18.4, so the item is writable. Removing `sid` narrows D-1 from an equality oracle to a size fingerprint; it does not retire it, and the padding half is blocking — §18.7 M5.)*
- [ ] **[D-2]** The xorb preamble is fixed-length; the IV is derived, not stored; `key_epoch` is sealed.
- [ ] **[D-3]** `ExtractEnum` entry bodies are encrypted under the file's own key; no unsalted plaintext digest exists anywhere; the WORM write path refuses any record containing `rel`, an unsalted digest, a consent-unit identifier **or a content-derived object identifier**. *(restated 2026-09-19)*
- ~~[ ] The `dedup` table is partitioned by rdom.~~ **RETIRED 2026-09-19** — there is no `dedup` table (`eval/results/ckpt_dedup_results.json`) and no `rdom`.
- ~~[ ] **No federation-wide table is keyed by a content-derived CHUNK id (`sid`).** … (`xid`-keyed structures such as `place` are unaffected: `xid` names a xorb, not a chunk, and is a binding, not a dedup key.)~~ **UNSOUND AS WRITTEN, REPLACED 2026-09-19 (§18.4).** The parenthetical exempted `xid` on a property `xid` did not have: `xid = HMAC(K_mac, sid₀ ‖ … ‖ sid_{n−1})` was a keyed hash of a sequence of keyed hashes of plaintext, so `place` — 65.6 M immutable federation-wide rows sharded by `xid` prefix — was precisely the structure the rule forbade, and a reviewer grepping as instructed would have found nothing and certified the design conformant. Replaced by:
- [ ] **[LINT]** **No identifier written to WORM is a function of plaintext under any key derived from `K_L`.** Greppable, and scoped by key lifetime rather than by field name, because every `K_L`-derived key survives every shred. Covers `sid` (deleted), `xid` (`= HMAC(K_mac, idempotency_key ‖ xorb_seq)`, a function of the write intent, not of any bytes — and therefore also stable under the re-coding and repacking §11.3 makes free at migration, so `place` stays immutable and no citation is renamed), the cnode `cid`, the `vid`, the manifest whole-file `sha256`, and any content-derived stripe id. *(added 2026-09-19, §18.4, §13.1 third clause)*
- [ ] `stripe_id` is random or sequential and is **never** content-derived, stated explicitly — it is in the sealed trailer, in every checkpoint entry, in `loc` and in `place`, and no section currently says which it is. *(added 2026-09-19, §18.8)*
- [ ] **[LINT]** The GCM counter-block allocator reserves `n + 1` counters per xorb and no two xorbs that can share one `K_obj` receive overlapping ranges; tested by writing one object across ≥ 2 xorbs in one session and asserting nonce disjointness; the SP 800-38D invocation bound is recomputed for the largest object the archive will hold. **Blocking; recovery class unrecoverable (§16 item 15b, §18.7 M3).** D-2's `iv = HKDF(K_meta, volume_id ‖ ordinal ‖ offset)` is unimplementable as written and must be replaced, not carried forward. *(added 2026-09-19)*
- [ ] Content keys are HSM-wrapped; `redaction.shred` is a destroy-handle operation returning per-site signed receipts; `shred_state` reaches `CONVERGED` before a withdrawal is reported executed; no key-store backup outlives the withdrawal SLO. *(2026-09-19: `K_rdom` is retired; the requirement transfers to per-object keys unchanged in substance, at roughly three orders of magnitude more destroy-handle operations and signed receipts per withdrawal. Whether the KMS path, the convergence protocol and `unconverged_shreds` survive that multiplier is unanalysed — §16 item 13.)*
- [ ] Per-object HSM destroy-handle volume and convergence time are measured (§12.4 hole). *(added 2026-09-19)*
- ~~[ ] The per-cartridge index size and index-mode rebuild time are recomputed at object granularity (§7.1 hole).~~ **DONE 2026-09-19 — §18.2.** Replaced by:
- [ ] **[LINT]** The fragment trailer and every index checkpoint entry are **fixed-length**: `xorbs[1344]`, `res_ords[84]`, `leaf_hashes[12288]` and the scalar fields, with ABSENT sentinels for short fragments and `PARITY` fragments. The commissioning cartridge dump (§6.3) asserts constant trailer length and constant `JobFiles`/`JobBytes` across every job on the cartridge. A variable-length sealed structure makes its own length a cleartext function of the object count, with no key.
- [ ] `class ∈ {DATA, MANIFEST, JOURNAL, PARITY}`; a `PARITY` fragment's `res_ords` is all-ABSENT and its parcel deadness is the conjunction over both data peers, joined on `stripe_id` at rebuild.
- [ ] `res_ords` is a positional `u32[84]`, one slot per data parcel; `res_gran` and `res_scope` are in the sealed half and a reader **refuses to mix granularities or scopes in one join**, exactly as §4's `code_epoch` makes it refuse to mix code epochs.
- [ ] Residency ordinals are `PRP(K_ord(v), i)` over `[0, 2³² − 1)`, never dense, never in write order; `K_ord(v) = HKDF(K_custody_root, "ord" ‖ volume_id)`.
- [ ] The ordinal → residency-unit map is a specified **erasable** custody artefact, ≤ 16,296 rows per volume, never on WORM, with no backup outliving the withdrawal SLO; `redaction.shred` destroys the row's identity field and sets its state to `SHREDDED`, and a rebuild that cannot resolve an ordinal reports `SHREDDED`, never `UNKNOWN`.
- [ ] The index checkpoint carries `xorbs[]`, so §7.3's promise that a rebuild yields the `xid` set is satisfiable on the index path rather than only by a 291-locate trailer pass.
- [ ] The differential disclosure test (§18.7 M6) is run against the commissioning cartridge before the first production write, and re-run at every format epoch and every migration. *(all added 2026-09-19, §18.3)*
- [ ] `K_L` re-wrap reads the live key store, refuses `SHREDDED` rows, and journals the refusal.
- [ ] `K_idx(v)` is derived per volume from the custody root; no fabric-wide index key exists; the volume index is also written into the fabric as a `class = MANIFEST` parcel.
- [ ] Proactive resharing runs on a fixed `key_epoch` boundary; an alarm fires at `t+2`; the annual quorum drill is measured and published; `decryptability_horizon` gates cite-class pins.
- [ ] Digests are SHA-256 (truncated per SP 800-107); WORM signatures are hash-based; KEK wrapping and share transport follow CNSA 2.0.

**Plant**

- [ ] The demand book is written only by `intend`; the wave close time `T` is published.
- [ ] Waves are one restore job per volume with a pre-sorted BSR; no back-seek; no volume mounted twice per window.
- [ ] The coalesce-gap rule (16 GB) and the read-widening rule (`X / (X + 1.06 × 10¹¹)`) are implemented.
- [ ] Deadline-lane mounts are charged against a bounded per-requester budget in loads and robot-seconds.
- [ ] All four conserved resources (drive-seconds, load cycles, robot exchanges, slots) are budgeted, refusable and in the descriptor.
- [ ] Published worst-case deadline latency = remaining wave + one mount cycle; no preemption is promised.
- [ ] Upward disclosure is bucketed: no cartridge identifier, no wave membership, no per-peer load, no serpentine position.
- [ ] Every cost figure carries `basis: MEASURED | MODELLED | ASSUMED`.

---

## 18. The two one-way doors, decided

Two fields are written onto write-once media and are unchangeable for 7–10 years. Both were opened
on 2026-09-19 by `eval/results/ckpt_dedup_results.json`, which retired `K_rdom` by measuring
zero sharing on the dominant population. Both were recorded as holes because neither was designed.
This section designs them, corrects the §7 arithmetic they were argued with, and states what is
still owed.

**Both doors close.** A third, previously unnamed, does not — it is stated in §18.7 and it outranks
both, because its recovery class is *unrecoverable by any mechanism* and it has no version field
that could save it.

### 18.1 The ratio the hole asked for is not the ratio that decides it

The §7.1 hole named *objects-per-domain* and declared it unquantified. That ratio is real — it is
the factor by which cardinality grew when the set went from domains to objects — but it does not
enter the size arithmetic and cannot be measured into the answer, because redaction domains are no
longer a key and no document ever counted them.

What enters the arithmetic is **ρ, the number of residency units resident in one fragment**:

```
F_pay = 84 parcels = 84 GiB = 9.0194 × 10¹⁰ B      (fragment payload; 12 of 96 parcels are local parity)
ρ     = 1 + F_pay / S̄        objects per fragment; the 1 is the boundary-straddling term
```

`ρ` is set by the object-size distribution and by the packer. It needs no domain count, which is why
no document supplies one. It is directly measurable (§18.7 M7), and — this is the point of the
decision below — **the adopted structure does not depend on it.**

### 18.2 The §7 arithmetic, recomputed

Geometry, taken from §3 and denominated in **payload** bytes throughout, because the earlier figures
conflated media bytes with payload bytes:

```
fragments per 30 TB cartridge   = 3.0e13 / (96 GiB)      = 291.04  → 291     GRANULARITY-INVARIANT
data fragments (RS(2,1))        = 291 × 2/3              ≈ 194
cartridge data payload          = 194 × 84 GiB           = 17.50 TB
xorbs per fragment              = 84 GiB / 64 MiB        = 1,344   EXACTLY, by geometry
```

**The largest error in §7.1 was never about granularity.** The stated "~96 B per index entry" omits
`xorbs[]` entirely, while §7.3 promises that a rebuild yields the `xid` set and §7.3's recovery path
requires rebuilding `place : xid → (stripe_id, frag_i, parcel_ordinal, offset, len)` — which *is*
`xorbs[]` inverted. At 1,344 xorbs per fragment and a fixed 32 B entry, `xorbs[]` alone is 43,008 B
per index entry. The "~28 KB per cartridge / one short read" figure was low by ~470× at ρ = 0, before
any question of object granularity arose. That correction stands whichever way Door 1 falls.

**The rejected option — a variable-length per-object set (`obj_ords`), for the record:**

```
entry(ρ) = 56 fixed + 2 coding_id + 43,008 xorbs[] + 12 framing + 2ρ
I(ρ)     = 291 × entry(ρ) = 12.54 MB + 582·ρ bytes per cartridge
t        = O + I/R,   O = 265 s, R = 4.0 × 10⁸ B/s
T_plant  = (240/9) × t = 26.67 × t
```

| ρ (objects/fragment) | S̄ | I per cartridge | index read | plant rebuild |
|---|---|---|---|---|
| 1 | 90.2 GB | 12.54 MB | 31 ms | 1.963 h |
| 10³ | 90.2 MB | 13.12 MB | 33 ms | 1.963 h |
| 2.15 × 10⁴ | 4.19 MB | 25.05 MB | 63 ms | 1.963 h |
| 1.97 × 10⁵ | 459 KB | 127.2 MB | 0.32 s | 1.965 h |
| 1.80 × 10⁶ | 50.1 KB | 1.06 GB | 2.65 s | 1.983 h |
| 1.82 × 10⁷ | 4.96 KB | 10.6 GB | 26.5 s | 2.159 h |

**Where "one short read" fails, stated three ways because the phrase conflates three budgets:**

| Budget | Fails at | i.e. mean object size |
|---|---|---|
| One `Maximum Block Size` block (1–2 MiB) | **ρ = 0** — already false, because of `xorbs[]` | any |
| One locate + one streaming read ≤ 1 % of the mount cycle (1.06 GB) | ρ > 1.80 × 10⁶ | S̄ < 50.1 KB |
| Whole-plant rebuild moves 10 % (10.6 GB) | ρ > 1.82 × 10⁷ | S̄ < 4.96 KB |
| `obj_ords` overtakes `xorbs[]` in the entry | ρ > 2.15 × 10⁴ | S̄ < 4.19 MB |
| `obj_ords` overtakes `leaf_hashes[12288]` in the trailer | ρ > 1.97 × 10⁵ | S̄ < 459 KB |
| A dense per-volume `u32` object ordinal **overflows** | 17.50 TB / S̄ > 2³² | **S̄ < 4,074 B** |

**Two results follow and both are load-bearing.**

1. **The rebuild figures were never index-bound; they are mount-bound.** `T_plant` moves from 1.963 h
   to 2.159 h across seven orders of magnitude of ρ. Granularity cannot move a number that is 99.99 %
   robot, thread and rewind seconds. Two of the three figures the hole ordered recomputed do not move
   at all: **291 fragments per cartridge is pure geometry**, and the rebuild time is insensitive.
   Only the byte figure moves, and it moves for a reason (`xorbs[]`) the hole did not name.
2. **Ordinal width binds before rebuild time does.** A dense per-volume `u32` object ordinal overflows
   at S̄ ≈ 4.07 KB, *below* the 4.96 KB point at which rebuild time first moves 10 %. So the failure
   mode of the fine-grained option is not a slow rebuild; it is a silently wrapped identifier on media
   that cannot be rewritten. Nothing in §7.1 stated the ordinal's width.

### 18.3 DOOR 1 — DECIDED. `obj_ords` is replaced by `res_ords`, a fixed-length parcel-resolution residency vector

**Do not write a set.** Write, in the sealed half of the fragment trailer and of every index
checkpoint entry, a fixed-length vector with one slot per data parcel:

```
res_gran : u8      { ABSENT = 0, OBJECT = 1, POOL_GROUP = 2 }   per volume, in the sealed half
res_scope: u8      { VOLUME = 1 }                               per volume, in the sealed half
res_ords : u32[84] one slot per DATA PARCEL of the fragment, in parcel order
                   value = the residency ordinal of the unit whose bytes occupy that parcel
                   0xFFFFFFFF = ABSENT (unoccupied parcel, short fragment, or PARITY fragment)
```

The **residency unit** is whatever §8.4 declared for the lineage: the object under `packing: pure`,
the pool group under `packing: pooled(n)`. Door 1 therefore *tracks* the §8.4 decision instead of
waiting on it, which is what breaks the sequencing deadlock every analysis of this hole ran into.

**Ordinals are the image of a custody-keyed permutation, not a dense write-order sequence:**

```
res_ord(i) = PRP(K_ord(v), i)        over [0, 2³² − 1), so 0xFFFFFFFF is never an image
K_ord(v)   = HKDF(K_custody_root, "ord" ‖ volume_id)
```

where `i` is the volume-local residency-unit sequence number. The permutation is injective, so
ordinals are unique within the volume; its image is uniform, so neither an ordinal's value nor
`max(ordinal)` is a population count; and it is invertible by exactly the custody quorum that already
unseals `K_idx(v)`, so no new custody domain is created and half the "custody-held ordinal map" is
*derived* rather than stored.

**The guarantee changes and gets stronger.** `DENSE OPAQUE ORDINALS` is retired and replaced by
**`SPARSE OPAQUE ORDINALS, the image of a custody-keyed permutation over a per-volume namespace`**.
The hole worried that a finer ordinal is closer to being an identifier. That was the wrong worry in
two directions: an opaque ordinal's *value* never carried anything, while its **density** and its
**write-order adjacency** did — density made `max(ordinal)` a census and adjacency made co-arrival
inferable. Both are deleted here, and deleting them is free because the structure is no longer
compressed.

**What this buys, in order of how much it decides:**

| Property | Because |
|---|---|
| **The index is a constant.** Entry = 56 + 2 `coding_id` + 2 discriminators + 336 `res_ords` + 43,008 `xorbs[]` = **43,404 B**; **I = 12.63 MB per cartridge** at every object size | The vector is positional, not a set |
| **"One short read" is true by construction**, at 12.63 MB against a 1.06 GB budget — 1.2 % of it | Independent of ρ, of the packer, of the interleave factor |
| **The `u32` width cliff is closed** | Distinct residency ordinals per volume ≤ 194 × 84 = **16,296**, four orders below `u32` |
| **No length channel.** The trailer and every checkpoint entry are constant-length | No padding quantum to size, no per-class quantum to leak, no overflow, no refusal-to-seal |
| **No seal-time refusal exists** | A refusal that fires after 103 GB is on WORM is a rule for destroying media (§11.4), not a bound |
| **Door 1 stops depending on §8.4, on M3 and on §16 item 11** | The structure is the same size under `pure` and under `pooled(n)` |
| **Compactness and unlinkability stop being opposed** | A run-encoded set is cheap only if ordinals are pack-ordered, which encodes packing affinity permanently; a positional vector needs no ordering at all |

**What it costs, stated plainly.** Under `pooled(n)` a parcel holds several residency units and the
vector names the pool group rather than the member, so a **media-only** rebuild marks a parcel dead
only when the whole group is dead. That is not a new loss: §11.2 already declares `live_fraction`
a **bound, not a value** under `pooled(n)`, and §8.4's own hole says `pooled(n)` becomes the default.
Under `pure` packing the vector is exact and loses nothing. The catalogue path is untouched — §11.2's
zero-mount `live_fraction` runs off `loc` plus the catalogue residency map plus the journal, and the
media copy exists only for the catalogue-loss branch of §7.3.

**Parity fragments.** `class` gains a fourth value, **`PARITY`**. A global-parity fragment holds no
objects and its `res_ords` is all-`ABSENT`. A parity parcel is dead iff the corresponding parcels of
both data peers are dead — a conjunction computed at rebuild by joining on `stripe_id`, which a
media-only rebuild already has for every fragment it reads. Its `xorbs[]` is all-`ABSENT` for the
same reason — a parity fragment holds RS symbols, not xorbs — and **its index entry is nevertheless
written at full fixed length**, because an entry whose length depended on `class` would make the
parity-fragment count measurable outside the seal, reintroducing at the checkpoint the very channel
the fixed length exists to delete. Without the enum value the design required a parity fragment to
name objects resident on two other volumes, which per-volume ordinals cannot express and which
nothing in §7.1 had noticed; the alternative readings were worse — carrying `(volume_id, ordinal)`
pairs, which multiplies the index five- to tenfold and reinstates cross-volume linkage, or carrying
nothing, which leaves one third of the plant unjoinable to the journal forever.

**The ordinal map is a specified custody artefact, not an implied one.** Per volume, ≤ 16,296 rows of
`(ordinal → residency unit)`, held in the **erasable** catalogue under the same destroy path as the
key store, never on WORM, never in a backup outliving the withdrawal SLO. `redaction.shred` destroys
the row's identity field and sets its state to `SHREDDED`; the row's *existence* is what a media-only
rebuild needs, and its *identity* is what a withdrawn subject is owed. This satisfies §11.1 rule 4's
custody-first acknowledgement ordering, because neither write blocks acknowledgement, and it satisfies
§12.6's aggregate-only rule, because the surviving artefact is `(volume, PRP-image, SHREDDED)` and
carries no subject, no time and no ordering.

**Migration (§11.3) is unaffected.** `res_ords` is a volume-local label re-minted by `seal()` on the
destination volume, exactly as the trailer, `leaf_root` and `K_idx(v)` are. Nothing outside a volume's
own index and its custody map ever references an ordinal, and the key-destruction journal joins on
the object, never on `(volume, ordinal)`. A generational migration therefore still writes only `loc`.

### 18.4 DOOR 2 — DECIDED. No identifier written to WORM is a function of plaintext

**`sid` is deleted.** `sids[n]` is removed from the xorb wire format. A chunk is addressed
**positionally** as `(xid, i)`; the chunk table already carries `offs[n]` and `lens[n]`, and the
per-chunk AEAD `aad = lineage|xid|i` already binds chunk *i* to position *i* of xorb `xid` with a key.
Nothing requires a chunk to have a name.

```
[ "GFSX" | ver u8 | key_epoch u16 | ehdr_len-FIXED ]                    cleartext preamble (D-2)
[ GCM(K_meta, iv, aad = lineage|xid|"h")        -- iv derivation OPEN, §18.7 M3
    { n, group_count, group_extents[] }         ]                       navigable index only
[ per object, GCM(K_obj, …) { offs[], lens[], obj_id } ]                row-group, per D-1
[ per chunk i: GCM(K_obj[i], iv_base+1+i, aad = lineage|xid|i) bytes ]  PER-CHUNK AEAD, unchanged
xid = HMAC(K_mac, idempotency_key ‖ xorb_seq)                           16 B, per §12.1 truncation
```

**The door was framed too narrowly and the wider question is the one that must be answered.** It is
not *should `sid` exist*; it is **may any WORM-resident identifier be a function of plaintext**.
Deleting `sid` alone closes nothing, because `xid = HMAC(K_mac, sid₀ ‖ … ‖ sid_{n−1})` is
independently committed to media inside the sealed trailer's `xorbs[]` and inside `xorb.place`, and
`K_mac = HKDF(K_L, "sid")` survives every shred exactly as `K_meta` does. A `K_mac` holder with a
candidate 64 MiB xorb confirms possession at whole-xorb granularity — weak against a clinical note,
perfect against the measured dominant population, with IP and provenance consequences of its own.

**So the standing lint is restated by key lifetime rather than by field name**, which makes it
greppable and makes it cover the fields nobody enumerated:

> **No identifier written to WORM may be a function of plaintext under any key derived from `K_L`,
> because every such key survives every shred.**

This covers `sid`, `xid`, the cnode `cid`, the `vid`, the manifest whole-file `sha256` and any
stripe id derived from content, in one formulation. It is added to §13.1 as a **third clause**
(§13.1's second clause survives with `sid` struck from its list) and it **replaces** §17's chunk-id
line, whose parenthetical exempting `xid` ("`xid` names a xorb, not a chunk, and is a binding, not a
dedup key") was **unsound as written** — `xid` was a keyed hash of a sequence of keyed hashes of
plaintext, so `place`, at 65.6 M immutable federation-wide rows sharded by `xid` prefix, was
precisely the structure the rule forbade, and a reviewer grepping as instructed would have found
nothing and certified the design conformant. That is the one live defect this pass found in the
design's *own enforcement mechanism*, and it holds whichever way Door 2 is decided.

**Why `xid` is keyed on the write intent and not on the content, and not on the ciphertext, and not
on a CSPRNG.** Each alternative fails on a different axis and all three failures are permanent:

- *Content-derived* (status quo): a confirmation oracle to every `K_mac` holder for the life of the
  medium, against subjects who have already withdrawn. Unrecoverable.
- *Ciphertext-derived*: **circular.** `xid` is an input to the AAD of every chunk's GCM
  (`aad = lineage|xid|i`), so `xid` must exist before the ciphertext it would be derived from. The
  only escapes are removing `xid` from the AAD — which destroys the chunk-to-xorb binding the
  proposal exists to preserve — or inventing a per-xorb pack-time ciphertext root, which must then be
  readable for a blind rebuild and therefore lands a keyless cross-cartridge ciphertext-equality
  handle in the cleartext preamble. Additionally, any id that is a function of stored bytes is
  **renamed by re-coding**, which §4 says bumps `code_epoch` and §11.3 says is free at migration —
  so it would rewrite `place` (declared immutable, 65.6 M rows), every `xorb.place` journal entry and
  every pinned `ExtractCert`, destroying §2.2's payoff.
- *Random*: loses write idempotency. A retried 64 MiB xorb write after an ambiguous failure produces
  a second xorb with identical content and a different name, on media where §11.2 forbids sub-volume
  reclaim, and two `place` rows now describe one logical object.

`HMAC(K_mac, idempotency_key ‖ xorb_seq)` is deterministic under retry (the idempotency key is drawn
once per write intent and replayed, and §7.1's trailer already carries one), carries no plaintext,
is stable under re-coding and repacking because it is not a function of any bytes, and is
unguessable to a holder. `K_mac` survives; its stated purpose in §12.1 changes from *chunk ids* to
*xorb naming from the write intent*.

**What is given up: nothing measured.** Deduplication was `sid`'s only consumer and
`ckpt_dedup_results.json` measures it at zero — 0 of 184,044 adjacent weight blocks, 0 distant, 0
between the two weight copies inside one checkpoint, 0 cross-run with a control that discriminates,
optimizer 0.002 % excluding zero blocks. On the clinical population no measurement exists in either
direction, so per §16 item 6 that saving is **forgone by decision, not measured absent** — and it was
already forgone, because §12.3's impossibility argument survives its own retirement: under per-object
keys a chunk readable through two object keys is recoverable through two paths and re-encryption is
impossible on WORM. Cross-object dedup is structurally unavailable regardless of what `sid` is.

**What "self-checking rebuild" is worth: nothing, and it should be struck from both sides.** A rebuilt
index can only be checked against the bytes by reading them, which is §7.2's full-sweep mode at 20.8
drive-hours per cartridge. The property cannot be exercised on the 12.63 MB index path at all. The
checks that *are* exercisable there are the trailer AEAD under `K_idx(v)`, `prev_checkpoint_mac` with
monotone `checkpoint_seq`, `leaf_root` over stored ciphertext (keyless, for a blind holder), and the
per-chunk GCM tag under `K_obj` — four independent authentications, none of which uses a chunk id.

### 18.5 Disclosure, permanently, by who holds what

| Holder | Learns, for the life of the medium |
|---|---|
| **One cartridge and a drive, no keys** | Unchanged from §13.2. Structure lengths are constants: the trailer is fixed-length, and a cumulative checkpoint's length is a function of the fragment count only, which §13.2 already books. **Zero new bits.** Had the variable-length set been written, trailer and checkpoint length would have become a cleartext function of the object count — D-2's `ehdr_len` defect reintroduced at two new sites, keylessly, permanently. |
| **One cartridge + that volume's custody quorum** (§12.6 row 2) | The full index, plus, per fragment, **which of its 84 data parcels share a residency unit** — i.e. `min(ρ, 84)` distinct ordinals, at most ~6.4 bits per fragment, capped by geometry. It does **not** disclose an object count, a mean object size, a co-residency partition over the volume's population, a population census, or an arrival order. The fine-grained set would have disclosed all five. |
| **Two cartridges from two sites** | Unchanged: `leaf_root` stripe linkage, already accepted in §12.6. Per-volume scope means the same object carries unrelated ordinals on two volumes, so ordinals add no cross-cartridge, cross-year linkage handle. |
| **After a shred, media only** | Unchanged from §7.3's stated budget: *N opaque 1 GiB parcels in M fragments, some of which are marked dead by ordinal.* The ordinal is the image of a permutation the holder cannot invert, and the catalogue row that resolves it has had its identity field destroyed. The object-granular set would have falsified this budget outright. |
| **The catalogue** | Unchanged: everything but content keys (§12.6). The residency map is a catalogue artefact and dies with the catalogue's destroy path. |
| **Every `K_mac` / `K_meta` holder for thirty years** | **Removed.** Under the status quo: a keyed plaintext-equality oracle at 64 KiB granularity via `sids[n]`, and at ~64 MiB granularity via `xid`, both under keys that no withdrawal destroys, readable by *authorised readers* rather than only by adversaries. After this decision no plaintext-equality test survives anywhere in the data plane. |

**Still open and not claimed as closed:** the metadata plane. `cid = HMAC(K_mid, canonical body)` and
`vid = HMAC(K_mid, canonical(VersionRoot))` are content-derived under `K_mid = HKDF(K_L, "mid")`,
which survives every shred, and cnodes reach WORM as `class = MANIFEST` parcels (§7.3). Cnode bodies
carry `rel`, which §12.2 D-3 states is often MRN-derived — a confirmation oracle whose inputs are
*guessable*, which is a worse class than one requiring possession of the bytes. §18.7 states what
cartridge 1 may carry without foreclosing either resolution.

### 18.6 Recovery cost if each decision is wrong, by class

| Decision | If wrong | Class |
|---|---|---|
| `res_ords` at parcel resolution, where object resolution was needed on the media-only path | Add object resolution on later cartridges under a new `res_gran` value; recover it for existing cartridges from the `class = MANIFEST` in-fabric index copy (§7.4) or from the catalogue | **software change**; unrecoverable only in the compound case (catalogue lost *and* manifest tier lost *and* custody intact), which §7.3 already classifies as unrecoverable by design |
| `res_ords` at parcel resolution, where a 4 B field would have done | 44.2 MB of index per 30 TB cartridge, 1.5 × 10⁻⁴ % of capacity | **nothing to recover** — already paid, and immeasurable |
| Had we written the per-object set and been wrong | A per-object occupancy map, a per-volume object census and an arrival-ordered ordinal space on unerasable media for 7–10 years | **unrecoverable** |
| `res_gran` / `res_scope` discriminators | Readers refuse to mix granularities in one join, exactly as §4's `code_epoch` makes them refuse to mix code epochs | **software change**; their *absence* would have been unrecoverable, because a mixed-granularity join silently marks the wrong parcels dead on the one path that must never be silently wrong |
| `PARITY` class value | Reuses one spare value in a byte already on WORM | **software change**; its absence is **unrecoverable** — one third of the plant could not be joined to the journal |
| `K_ord(v)` lost | Ordinals unresolvable for that volume; dead-marking degrades to a bound | **unrecoverable for that volume**, but it is derived from `K_custody_root` exactly as `K_idx(v)` is, so its loss is the same event §12.5 already prices at ~34 %/decade and does not add a failure mode |
| Deleting `sid`, if a content-derived chunk id is later wanted | Reintroduce on new cartridges under the existing per-xorb `ver` / `key_epoch`; cartridges written without it simply never dedup, at a cost measured at zero on the dominant population and forgone by decision on the other | **software change** |
| Had we kept `sid` and been wrong | A permanent plaintext-equality oracle under two keys that survive every shred, on media that cannot be rewritten, against people who have withdrawn | **unrecoverable** |
| `xid` keyed on the write intent | Affects only new xorbs; `xid` is a stored opaque label and nothing on media re-derives it | **software change** |
| Had `xid` been derived from content or from stored bytes | Re-coding at migration renames every xorb, rewriting `place`, every `xorb.place` entry and every pinned citation | **rewrite cartridges** at best, **unrecoverable** for citations |

**The asymmetry, stated once.** WORM refuses overwrite; it does not refuse append. Resolution can
always be **added** on a later cartridge and can **never** be withdrawn from one already written. So
on every sub-decision the recoverable side is the one that writes the least that still discharges
§7.3's stated guarantee — which is what both doors were decided on.

### 18.7 What must be true before the first cartridge

Checkable statements. A commissioning gate, not a wish list.

**Blocking — the first cartridge may not be written until each is true:**

1. **[M1] The four-term mount cycle is measured on the deployed library**, over ≥ 1,000 exchanges,
   published as a *distribution*, with **locate-to-end-of-data and rewind-from-end-of-data reported
   as separate tails** rather than folded into a single `O`. §7.2's index row is structurally the
   worst-positioned mount in the plant (§18.8) and the planning `O` must not be reused for it.
2. **[M2] A network-fed spool sustains `Maximum Block Size` 1–2 MiB at the drive's speed-match floor
   plus concurrent inbound during a despool wave**, measured on the deployed path, not a node-local
   one (§16 items 2 and 20; `eval/results/fsync_cost.json` measures 8.1–8.8 MB/s on a shared
   filesystem against 339 MB/s node-local on the same host).
3. **[M3] The GCM counter-block allocator reserves `n + 1` counters per xorb and no two xorbs that
   can share one `K_obj` ever receive overlapping ranges.** Demonstrated by a test that writes one
   object across ≥ 2 xorbs in one session and asserts nonce disjointness, plus a recomputation of the
   SP 800-38D invocation bound for the largest object the archive will hold. **This is the third
   one-way door and it outranks the two decided here.** Under `K_rdom` the chunk key was
   `HKDF(K_rdom, "chunk" ‖ sid)`, unique per chunk, so IV collisions across xorbs were harmless.
   Under `K_obj` one key covers every chunk of the object — 184,044 invocations for one 12.06 GB
   weights object — and nothing specifies the reservation discipline. IV reuse under AES-GCM is
   GHASH subkey recovery and tag forgery across the lineage, catalogue cnodes included, permanently,
   on WORM. Recovery class: **unrecoverable by any mechanism, with no version field that helps.**
   §12.2 D-2's prescribed fix (`iv = HKDF(K_meta, volume_id ‖ ordinal ‖ offset)`) is **unimplementable
   and must be rewritten**: `volume_id` and `ordinal` are assigned by `seal()` at the site after
   despool (§4) while encryption happens at origin before spooling (§11.1), and one ciphertext is
   placed at three distinct `(volume, ordinal)` pairs and then erasure-coded.
4. **[M4] The deployed Bareos version's on-media cleartext field list is dumped from a commissioning
   cartridge and diffs clean against the allowlist** (§6.3, §17), and the dump additionally shows
   **constant trailer length and constant `JobFiles`/`JobBytes` across every job on the cartridge**.
   A variable-length sealed structure makes trailer length a cleartext function of the object count
   with no key required; this is the check that it did not happen.
5. **[M5] No field under `K_meta` is a function of any object's true length.** Per D-1 the chunk table
   is sharded by object with row-groups under `K_obj`; `lens[n]` sums to the exact object size and
   per-group offsets are invertible to the same quantity, so **group extents must be padded to a
   fixed quantum** and the padding rule must be stated and tested. Removing `sid` narrows D-1 from an
   equality oracle to a size fingerprint; it does not retire it, and D-1's mitigation remains blocking.
6. **[M6] A differential disclosure test is run against the commissioning cartridge before the first
   production write.** One team receives only §13.2's declared residual channels; a second receives
   the residual plus the proposed sealed structures, over a real packed volume with known ground
   truth; the measured delta in per-subject record-count estimation error and in co-residency
   partition recovery (adjusted Rand index) is published. A non-zero delta refutes the "zero new bits"
   claim in §18.5 while it is still reversible. Re-run at every format epoch and every migration.

**Not blocking — and this is the point of the Door 1 decision.** The following were on the critical
path under a variable-length set and are not under a fixed-length vector. They remain required for
§8.4, §12.4 and §14, and they must be measured before those are settled:

7. **[M7] The residency-unit count per data parcel**, emitted by the packer per sealed fragment over
   one real ingest epoch-day feed, published as a per-lineage-class distribution with its p99 — **not**
   as a mean derived by dividing two totals. §8.4 rule 3 guarantees cartridges are population-segregated
   by design, so a plant-wide mean understates the worst segregated cartridge by the reciprocal byte
   fraction of the small-object population.
8. **[M8] The object-size distribution per lineage class**, a `find`/`stat` walk of
   `<cluster project storage>` on `the HPC cluster`. Available today, unowned, and it is the input
   to §14's capacity model and to §8.4 rule 1's padding arithmetic.
9. **[M9] Objects per consent unit**, from the clinical lineage manifest, as a distribution with its
   tail. It prices §12.4's per-object destroy-handle volume (§16 item 13) and §9.5's lease-aggregation
   unit (§16 item 15) — one measurement, part of three holes.
10. **[M10] Real co-occurrence mined from an actual request log** (§16 item 11). Still a prerequisite
    for §8.4's packing decision and for sizing; no longer a prerequisite for the on-media format.

### 18.8 Corrections this decision forces elsewhere, and what remains owed

**Corrected in place in this document:** §7.1's structure block, entry size and "one short read"
line, and its `class`/`obj_ords` bullet; §7.2's three-mode table — now five modes, including the
end-of-data mount correction, a chain-verified row and the partial-sweep row the table never had;
§7.3's rebuild-yields line and its disclosure budget; §7.4's "~28 KB per cartridge"; §11.2's
`live_fraction` source; §12.1's `K_mac` purpose and the new `K_ord(v)`; §12.2 D-1's `sid'` blinding
requirement and its NARROWED note; §12.3's "this pass does not decide"; §12.6's adversary row 2 and
its `RedactionRec` rule; §13.1, which gains a third clause scoped by key lifetime; §13.2's trailer
and checkpoint rows; §15's re-derivations line; §16 items 12 and 14, plus a new item 15b for the
third door; and the §17 conformance lines for the chunk-id lint (struck as unsound), the D-1 item
(rewritten from UNSATISFIABLE to satisfiable), and the §7.1 recomputation item (replaced by seven
testable lines), plus new items for `stripe_id`, the GCM counter discipline and the differential
disclosure test.

**§7.2's index-mode figure was wrong for a reason unrelated to either door.** MAM points at the
*latest* checkpoint, which §7.1 places at end of data, so the index-mode mount selects the maximum of
both tape-motion terms by construction — the locate runs to the far end of the medium and §3.4's
mandatory rewind is proportional to how far the read drove the head. The planning `O = 265 s` is an
average over targets distributed along the tape and must not be used here.

**Owed, and recorded rather than decided:**

- **The metadata plane's content-derived identifiers.** `cid` and `vid` are the same defect as `sid`
  one layer up, under a shred-surviving key, and `vid` has a live recompute consumer
  (*"recomputed, not trusted"*) that `sid` never had, so the sweep that kills `sid` must not be
  applied to it blindly. **Cartridge 1 may carry `class = MANIFEST` parcels only if no field in them,
  cleartext or sealed under `K_meta` or `K_mid`, is a function of plaintext** — enforced as a
  write-path refusal, per §12.2 D-3's existing invariant extended to the metadata plane. That rule
  forecloses neither resolution.
- **The manifest whole-file `sha256`** is an *unsalted* plaintext digest and therefore a **keyless**
  oracle strictly stronger than `sid` — one guess confirms a whole file. §12.2 D-3 already forbids it
  and nobody applied D-3 to the manifest. It must be applied in the same pass, or deleting `sid`
  closes the smaller hole and leaves the larger one open. Note that `STORAGE-DIRECTION.md`'s own open item 13 —
  the argument for dropping `sid` — cites this digest as covering integrity, so the case for the
  change rests on the thing that defeats it.
- **`stripe_id` must be stated to be random or sequential and never content-derived.** Nothing in §4,
  §7.1 or §8.8 says which it is, and it is in the sealed trailer, in every checkpoint entry, in `loc`
  and in `place`.
- **The catalogue-tier rebuild is priced nowhere.** §7.2 prices reading 240 volume indexes; §7.3
  requires additionally following `class = MANIFEST` parcels to the cnode closure and
  `class = JOURNAL` parcels to the journal chain. A cnode closure is a graph walk on a substrate with
  265 s access latency, so it is not a parallel sweep: at closure depth *d* with perfect per-level
  batching it is *d* × the index-mode figure, and without batching it is unbounded. **A closure walk
  that issues mounts as it discovers references must be refused by construction**, exactly as §8.5
  refuses racing and for the same reason. Manifest bytes per cartridge, discontiguous manifest run
  count and closure depth are unmeasured.
- **§8.4's packing hole is untouched by this decision** and remains open. `res_ords` tracks whatever
  §8.4 declares; it does not separate the packing unit from the shred unit, and nothing here should
  be read as closing that hole.
- **`ENTAIL-AGENT-NATIVE-FS.md` §6.1's causal clause is now false** — *"Content addressing is
  lineage-keyed … so v2 references v1's fragments by the same name"* — and it also carries the
  withdrawn `fragment id H(xid ‖ i)` term. The mechanism survives (v2 references recorded `xid`s
  rather than recomputing them); the justification does not. Its `Chunk { sid = … }` and
  `Xorb { xid = HMAC(K_mac, sid₀ ‖ … ) }` records and `promote`'s "preserves sids and dedupes"
  refusal arithmetic all need the same pass.

### 18.9 The findings ledger

Twelve adversarial reviews across three lenses — permanent leakage, scale and the rebuild path,
irreversibility — were run against four candidate positions. Every FATAL and SERIOUS finding is
listed here with its disposition. **RESOLVED** means the decision above makes it impossible;
**RECORDED** means it is real, open and named with an owner-shaped statement. Nothing is dropped.

| # | Finding | Sev | Disposition |
|---|---|---|---|
| 1 | A run-encoded ordinal set is cheap only if ordinals are pack-ordered, which permanently encodes packing affinity across cartridges — so the cost optimisation and the safety claim were mutually exclusive | FATAL | **RESOLVED.** No set, no encoding, no ordering. The vector is positional and ordinals are a permutation, so compactness and unlinkability stop being opposed (§18.3) |
| 2 | Binding the ordinal→object map under `K_obj` is forbidden by §11.1 rule 4's custody-first acknowledgement ordering — the key dies before the journal is written, so the ordinals can never be enumerated into it | FATAL | **RESOLVED.** The map is an erasable catalogue artefact; the shred destroys its identity field and sets its state. Neither write blocks acknowledgement (§18.3) |
| 3 | "No plaintext-equality test survives anywhere on media" was false: `stripe_id`, the cnode `cid` and the `vid` are plaintext-derived on WORM under `K_L`-derived keys that survive every shred, and none was examined | FATAL | **RESOLVED for the data plane** by the key-lifetime lint (§13.1 third clause, §17). **RECORDED for the metadata plane** with a non-foreclosing rule for cartridge 1 and an explicit `stripe_id` conformance line (§16 item 14, §18.8) |
| 4 | The 96-bit parcel-**dead** bitmap cannot be written: deadness does not exist at seal, and WORM refuses overwrite, so the field is all-zero for its life or requires a mount per cartridge per withdrawal — destroying §11.1's zero-mount forget | FATAL | **RESOLVED.** We write **residency**, which is static and fully known at seal, never deadness. The join to the journal happens at rebuild, which is what §7.1 always specified (§18.3) |
| 5 | A pack-cohort ordinal requires contiguous placement, which is the cohorting §8.4 rule 2 forbids by name on exactly this disclosure ground; and the proposed `n_runs ≤ 16` seal-time refusal could only be satisfied by adopting the forbidden layout | FATAL | **RESOLVED.** No contiguity requirement and no third naming layer. `res_ords` is positional and indifferent to interleaving |
| 6 | A seal-time refusal fires after ~103 GB is irreversibly on WORM (§11.4's `abandon()` path), so it is a rule for destroying media, not a bound | FATAL | **RESOLVED.** The structure is fixed-length and cannot overflow; no seal-time refusal exists |
| 7 | Per-volume write-order ordinals do not survive a generational migration, whose deadline is set by drive-fleet death | FATAL | **RESOLVED.** The ordinal is a volume-local label re-minted by `seal()` at the destination, exactly as the trailer and `K_idx(v)` are; the journal joins on the object, never on `(volume, ordinal)`; §11.3 still writes only `loc` |
| 8 | A ciphertext-derived `xid` is **circular** — `xid` is an AAD input to every chunk's GCM, so it must exist before the bytes it would be derived from | FATAL | **RESOLVED.** `xid = HMAC(K_mac, idempotency_key ‖ xorb_seq)`, a function of the write intent (§18.4) |
| 9 | Any `xid` derived from stored bytes is renamed by re-coding, rewriting `place` (declared immutable, 65.6 M rows), every `xorb.place` entry and every pinned citation — destroying §2.2's payoff | FATAL | **RESOLVED.** The adopted derivation is not a function of any bytes and is stable under re-coding and repacking (§18.4, §18.6) |
| 10 | `obj_ids[n]` — the per-chunk object identifier under `K_meta`, which got *finer* at object granularity — is the per-record withdrawal map, and no position mentioned it | FATAL | **RESOLVED** as a written conformance item: it moves inside the per-object row-group under `K_obj` and never appears under `K_meta` (§12.2 D-1, §17) |
| 11 | A variable-length sealed structure makes trailer and checkpoint length a cleartext function of the object count — D-2's `ehdr_len` defect reintroduced, keylessly, permanently, at the two worst sites | FATAL | **RESOLVED by construction**, not by a padding rule: every field is fixed-length or a fixed-length array (§7.1, §13.2, §17) |
| 12 | `obj_ords` sealed under `K_idx(v)` is a per-object record on WORM under a key §7.4 states in bold is *not* a shred unit — D-1's own defect, un-remedied, in the field being defended | FATAL | **RESOLVED.** `res_ords` carries a bounded co-residency fact (`min(ρ, 84)`, ~6.4 bits/fragment), not a per-object record, and §7.3's disclosure budget survives verbatim (§18.5) |
| 13 | Recording the shred journal in `(volume, ordinal)` space builds a permanent withdrawal register in the one structure §8.6 forbids destroying | FATAL | **RESOLVED.** The journal stays in object space; the `(volume, PRP-image, SHREDDED)` projection is per-volume, permuted and erasable (§18.3, §12.6) |
| 14 | Parity fragments are unrepresentable: `class` has no PARITY value, yet every sealed fragment is required to carry residency, and a parity fragment holds objects resident on two other volumes | FATAL | **RESOLVED.** `PARITY` added to the enum; `res_ords` all-ABSENT; deadness is the conjunction over both peers, joined on `stripe_id` at rebuild (§7.1, §18.3) |
| 15 | Per-object `K_obj` made GCM IV uniqueness a live forgery hazard — 184,044 invocations under one key, no specified counter-reservation discipline — and D-2's prescribed IV derivation is unimplementable | FATAL | **RECORDED, and escalated above both doors** (§16 item 15b, §18.7 M3, §17). Recovery class: unrecoverable by any mechanism |
| 16 | The whole-plant rebuild figure prices the locator tier only; §7.3's catalogue closure is a graph walk on a 265 s-latency substrate and is priced nowhere | SERIOUS | **RECORDED** with the refuse-by-construction requirement for mount-issuing closure walks and the three missing measurements (§7.2 note, §18.8) |
| 17 | "One short read" is not one read: without the registry the `prev_checkpoint_mac` chain must be walked, adding 3 backward quarter-cartridge locates | SERIOUS | **RESOLVED.** §7.2 gains a chain-verified row and registry survival is a stated precondition, not an assumption |
| 18 | The index-mode mount uses the planning `O`, but its target is pinned to end of data, so locate and rewind both take their maxima | SERIOUS | **RESOLVED.** §7.2 restated at `O_EOD` = 295–355 s, 2.19–2.63 h plant; M1 must report the two tails separately |
| 19 | The `512 KiB` threshold was derived against `leaf_hashes`, which is in the trailer only; the rebuild-path structure is the checkpoint entry, where the crossover is elsewhere | SERIOUS | **RESOLVED.** Both crossovers published against the correct structures, with `xorbs[]` counted (§18.2) |
| 20 | No granularity or scope discriminator: a 2033 reader cannot tell a 2027 ordinal universe from a 2029 one, so a mixed-granularity join silently marks the wrong parcels dead | SERIOUS | **RESOLVED.** `res_gran` and `res_scope` in the sealed half; readers refuse to mix, as §4's `code_epoch` already does (§7.1, §17) |
| 21 | §7.4's "~28 KB per cartridge" is unit-wrong by the 1 GiB parcel quantum, and the batching lag is the exposure | SERIOUS | **RESOLVED.** Restated with the parcel floor, the bootstrap-root requirement and the `seal_deadline` lag (§7.4) |
| 22 | A per-class padding quantum is itself a keyless per-volume class fingerprint — the same defect moved, not closed | SERIOUS | **RESOLVED.** One federation-wide constant fixed by geometry; there is no per-class quantum to leak |
| 23 | The recoverability argument was made on the cost axis and applied to a disclosure door; the minimum-commitment option was never priced | SERIOUS | **RESOLVED.** The adopted option *is* the minimum commitment that discharges §7.3, and §18.6 prices every branch by recovery class |
| 24 | "Self-checking rebuild" is a full-sweep-only property, unavailable on the 12.63 MB index path on any derivation, so it should be priced on neither side of Door 2 | SERIOUS | **RESOLVED.** Struck from both sides; the four checks that *are* exercisable are named (§18.4) |
| 25 | Exact object size survives under `K_meta` via `sum(lens[n])` and via invertible group offsets, so removing `sid` narrows D-1 rather than closing it | SERIOUS | **RECORDED as blocking.** Fixed-quantum group extents required (§12.2, §18.7 M5, §17 D-1) |
| 26 | Random `xid` loses write idempotency; a retried 64 MiB write double-writes onto media that cannot be reclaimed | SERIOUS | **RESOLVED.** The derivation is deterministic under retry by construction (§18.4) |
| 27 | Object granularity converts §13.2's declared residual into an object-arrival census, and cardinality as a channel was never considered | SERIOUS | **RESOLVED.** Sparse permuted ordinals delete both the census (`max(ordinal)` is uniform) and the arrival order (§18.3, §18.5) |
| 28 | The MANIFEST tier is WORM too, so "minimum on media, rich in fabric" relocates a permanent copy rather than removing one — and multiplies it by three | SERIOUS | **RESOLVED by not relying on it**: `res_ords` is self-contained on the volume; the manifest copy is the §7.4 redundancy it always was, with its cost corrected |
| 29 | The custody-held ordinal map is specified nowhere, yet the entire opacity guarantee rests on it; at object granularity it becomes a 10⁹–10¹¹-row re-identification database | SERIOUS | **RESOLVED.** Bounded at ≤ 16,296 rows per volume by the data-parcel count, specified as an erasable custody artefact with a destroy path, half of it derived from `K_ord(v)` (§18.3, §17) |
| 30 | The decision was framed as one plant-wide commitment, forcing M1 blocking and the quantum to be guessed before §8.4, M1, M3 and M6 | SERIOUS | **RESOLVED.** `res_gran`/`res_scope` are per-volume declarations and the structure's size is independent of all four, so three measurements leave the critical path (§18.7) |
| 31 | The interval encoding is dominated by roaring's run containers in every regime, and 3.95× worse in the population it claimed to rescue | SERIOUS | **Moot.** No set encoding is adopted |
| 32 | Fragment payload was stated as 96 GiB (media) where 84 GiB (payload) belongs, inflating every resident-object count by the 1.1429× local rate | SERIOUS | **RESOLVED.** All §18 arithmetic is denominated in payload and says so |
| 33 | `ρ = F/S̄` is a lower bound under §8.4 rule 2's mandatory interleaving, and a plant-wide mean understates the worst population-segregated cartridge by the reciprocal byte fraction of the small-object population | SERIOUS | **RESOLVED for the decision** (the structure does not depend on ρ) and **RECORDED for M7**, which is re-specified as a per-fragment emitted count with its p99, never a divided aggregate (§18.7) |
| 34 | §17's chunk-id lint exempted `xid` on a property `xid` did not have, so a reviewer grepping as instructed would certify `place` conformant | SERIOUS | **RESOLVED.** The line is struck as unsound and replaced by the key-lifetime formulation (§13.1, §17) |
| 35 | Door 2's "cost measured at zero" generalises a checkpoint measurement to the clinical population, which §16 item 6 states is unmeasured in either direction | SERIOUS | **RESOLVED.** The record now rests on §12.3's structural impossibility under per-object keys, with the clinical saving stated as *forgone by decision* (§18.4) |
| 36 | The checkpoint omits `xorbs[]` while §7.3 promises the `xid` set, so either the entry is ~470× larger than stated or the index-mode rebuild cannot satisfy §7.3 | SERIOUS | **RESOLVED.** The checkpoint carries `xorbs[]`; the entry and the per-cartridge figure are restated; the alternative (a 291-locate trailer pass at ~3.2 h/cartridge) is named (§7.1, §7.3, §18.2) |
| 37 | No leakage measurement appeared anywhere in the measurement list for a decision whose stated risk is disclosure | SERIOUS | **RESOLVED.** The differential disclosure test is added as a blocking commissioning gate and a recurring lint (§18.7 M6, §17) |
| 38 | Deleting a committed wire-format field is itself the permanent act, and no position said what remains in `sids[n]` | SERIOUS | **RESOLVED.** The post-decision chunk table is written out explicitly (§18.4) |
| 39 | The checkpoint-only pilot's undo — destroy the cartridge — is unusable, because §16 item 7 establishes that checkpoints cannot be recomputed | SERIOUS | **RECORDED.** Any format pilot must retain a live source copy on `the HPC cluster` until the format is ratified, and pilot cartridges must never share a cartridge with production data; both are preconditions, not properties |
| 40 | "For large objects the set gets smaller than the `rdom` set it replaces" is set-theoretically impossible | minor | **Noted.** Every resident object belongs to a resident domain, so the object set is never smaller. The hole's ratio is correct as a *ratio*; it is simply not needed to compute an absolute size (§18.1) |
| 41 | §8.8 requires `coding_id: u16` in every volume index, which §7.1's entry list omits | minor | **RESOLVED.** `coding_id` is in the trailer and in the checkpoint entry, and is counted in the 43,404 B (§7.1, §18.2) |
| 42 | `res_ords`/`obj_ords` is written ~3.5× per fragment (one trailer plus a mean 2.5 cumulative checkpoints), which no media figure accounted for | minor | **RESOLVED.** Media cost is stated at 3.5 × I = 44.2 MB per cartridge, 1.5 × 10⁻⁴ % of capacity (§18.6) |
| 43 | Index size does not change checkpoint survivability — a 28 KB and a 656 MB checkpoint occupy micrometres and millimetres against metre-scale defects — so §7.1's four-checkpoint decision is justified by defect length, not by index size | minor | **Noted and adopted as the reason.** It is a further argument that the size question was never the one that mattered |

---

## 19. The panAtlas binding — document identity, metadata, and where the index lives

*Added 2026-09-19, on the owner's constraint: "this file system will be to support panAtlas which
means that we will have unique document ids and other metadata, everything will be indexed."*

This section exists because that sentence reads, on its face, like a requirement to put
document-resolution identity into the archive's own sealed structures — which would undo §18.3 the
week it was decided. It does not, and the arithmetic that shows why also produces a sharper
statement of the §13.1 lint than §13.1 itself contains. Every size below was measured on
`the HPC cluster` on 2026-09-19 under `<cluster project storage>`; none is modelled.
Reproduce with `eval/sim/IndexResidency.java`.

### 19.1 What panAtlas actually brings, measured

| artifact | bytes | rows | class |
|---|---:|---:|---|
| `doc_ledger_crosswalk.parquet` | 3,027,213,217 | 200,497,968 | source of record |
| `doc_ledger_v5.parquet` | 4,015,419,778 | 178,562,639 | source of record |
| `doc_ledger_v4.parquet` | 2,882,434,954 | 131,739,051 | source of record |
| `master_doc_index.parquet` | 789,013,849 | 89,907,669 | source of record |
| `pmc_doc_pmid_map.parquet` | 523,261,125 | — | source of record |
| `labels_v53/doc_mesh_edges_v53_s{1,2}.npz` | 119,541,898,343 | 5.29 B edges ×2 | derived |
| `labels_v53/knn_exact96/` | 51,786,867,002 | 96-NN of every doc | derived |
| `labels_v53/doc_mesh_labels_v53{,_granular}.npz` | 12,914,971,700 | 2.07 B pairs | derived |
| `labels_v53/doc_ids_e8_order.txt` | 2,543,603,174 | 89.9 M ids | derived |
| **total** | **198,036,273,201** | **200,497,968 docs** | |

**988 bytes of index per document.** *(The vault's "labels_v53 (140 GB)" is stale: the directory
measures 186,798,930,278 B. The `master_doc_index.parquet` discrepancy is not an error — the vault
records the 706,689,139 B pre-promotion backup, the live file is post-promotion.)*

### 19.2 The index is a dataset in the archive, not a structure of the archive

198.04 GB is **185 parcels, 1.93 fragments, 0.66 % of one 30 TB cartridge**. Realising all of it
from cold media is **one mount and 495 s of transfer — 790–850 s, or 13.2–14.2 minutes** — and it
is 0.763 % of the CT corpus it indexes. Warm, it fits on any workstation, so in steady state it is
always resident and the archive holds the durable copy.

That settles "everything will be indexed": it is affordable, and it is affordable *as payload*. The
alternative — resolving the sealed per-cartridge index to documents rather than extents — costs a
residency map of **3.21 GB at a generous-low 16 B/document, 254× the constant 12.63 MB/cartridge
index**, and reinstates precisely the population-dependence that §18.3 spent a one-way door to
remove. **The archive's index stays extent-resolved. panAtlas's document index is an ordinary
sealed object that the archive locates exactly like any other object.** It is self-hosting: the
structure that makes 200 million documents findable is itself a `class = MANIFEST` object, and the
archive's own index needs only to find *it*.

### 19.3 The §13.1 lint, restated as a capability test because panAtlas breaks the old phrasing

§13.1 says "nothing plaintext-derived on unerasable media". That phrasing is **wrong in one
direction and unenforceable in the other**. Wrong, because `leaf_hashes` *are* content hashes and
are legal — they are taken over ciphertext, so after a shred they are hashes of noise.
Unenforceable, because "derived" admits no mechanical test.

panAtlas is what makes the imprecision urgent rather than academic. Its document identity is
`doc_uid = blake2b(raw_text, digest_size=16)`, and the vault records the design intent in as many
words: **"the text itself is the identity."** It is unkeyed. Anyone holding a candidate document
reproduces it. On erasable storage that is a feature, and it is the only reason the corpus is
decontaminable at all — 200,497,968 documents crosswalked, `in_both` 56,779,671. On WORM it is a
permanent membership oracle that no key destruction can reach.

> **The rule, normative.** A field written to unerasable media is legal **iff an adversary holding a
> candidate plaintext and no key cannot reproduce it.**

This is decidable by experiment: run the field's construction twice, once as the honest writer and
once as an adversary with the plaintext and a zero key, and compare bytes. `eval/sim/OracleLint.java`
implements it with both controls and returns 0 unexpected verdicts:

| field | where | verdict |
|---|---|---|
| `xid`, `stripe_id`, `res_ords[i]` | trailer + checkpoint | legal, and content-**independent** under a varied plaintext |
| `leaf_hashes[j]` | trailer | legal — needs the ciphertext, which needs the key |
| `doc_uid` | panAtlas ledgers | **ORACLE** |
| `manifest_hash` | panAtlas dataset registry | **ORACLE** |
| `doc_ids_e8_order` | `labels_v53/`, 2.54 GB of them | **ORACLE** |
| `HMAC(K_idx, doc_uid)` | proposed blinded form | legal |

**All three panAtlas identifier classes are therefore payload-only.** They may live inside an
object encrypted under `K_obj`; they may never appear in — or be an input to — a trailer field, a
checkpoint entry, an ordinal, a volume name, or any Bareos field. §18.4 already makes this
structurally true rather than merely required: `xid` derives from write intent
(`idempotency_key ‖ xorb_seq`) and cannot take a content input. **The lint's job here is
preservation, not repair.**

The blinded form `HMAC(K_idx, doc_uid)` passes, and is the only legal way a panAtlas identifier
reaches media — but it costs the cross-lineage joinability that is `doc_uid`'s entire purpose, since
a `K_idx` that rotates breaks the crosswalk across the rotation. **Keep them in payload.**

Two artifacts deserve naming. `doc_ids_e8_order.txt` is **2.54 GB that is nothing but 89.9 million
unkeyed content hashes** — the highest-density oracle in the estate, and the single file that most
needs never to reach media in the clear. `pmc_doc_pmid_map.parquet` establishes the pattern that
`doc_uid` joins to external identifiers; for PMC that is harmless because PMC is public, and the
same join on the clinical side is to an MRN.

### 19.4 Source of record versus derived: the shreddable surface is 5.7 %

A consent withdrawal must reach the index, and the index is not uniform:

- **Source of record — 11.24 GB, 5.7 %.** The five parquet ledgers. Parquet is row-group
  structured and the format's modular encryption gives per-row-group keys, so **sharding the
  ledgers by redaction domain before sealing makes a withdrawal a key destruction that blanks its
  own rows and nothing else.** This is spec line 961's prescription for the chunk table, applied
  unchanged to a second patient. Sharding must happen **before** seal; after seal there is no rewrite.
- **Derived — 186.80 GB, 94.3 %.** The `.npz` label, edge and neighbour artifacts. **These admit no
  row-level key destruction at all**: an `.npz` is a zip of monolithic arrays and a CSR row cannot
  be blanked without rewriting `indptr`/`indices`/`data`. Shredding one is all-or-nothing across
  89.9 M documents — the same structural defect that refuted D2, at 10⁵× the blast radius.

The resolution is not to make the `.npz` shreddable. It is that **derived artifacts are redacted by
invalidate-and-recompute, not by key destruction** — which is legal only because the recipe is
retained (jobs 219233/219234, `p6_promote.py`, lexicon v5.3, `knn_exact96` by exhaustive search over
the BioClinical-ModernBERT-large vectors). This is Entail's Derivation concept doing real work: the
186.8 GB is a cache of a computation, its `residency: ABSENT` is legal, and its correct response to
a withdrawal is discard-and-rebuild. **The surface that must actually be crypto-shreddable is
11.24 GB, not 198 GB.**

### 19.5 What this adds to §16, and what is not yet answered

1. **M11 — the recomputation cost of the derived 186.80 GB.** §19.4's whole argument rests on
   invalidate-and-recompute being an affordable redaction response, and that is asserted, not
   measured. `knn_exact96` is an exhaustive 96-NN search over the full corpus; if rebuilding it
   costs a week of DGX time then withdrawals are rate-limited by it and the trade must be stated
   rather than assumed. **Blocking for the redaction claim, not for media purchase.**
2. **Redaction-domain cardinality over the ledgers.** Per-row-group shredding needs a domain count.
   At 10⁶ domains the shards are 11 KB against a 1 GiB parcel, which is a granularity mismatch, not
   a design. Unmeasured.
3. **The clinical join is not yet in scope and will be.** `doc_uid` today covers text corpora that
   are predominantly public literature, where withdrawal rights do not attach. The imaging
   element-level overlap **has never been run** (`decontam_exact.json` holds 16 benchmarks, all
   text, zero imaging keys), and the vault scopes it as engineering rather than science. When it
   runs, the same content-addressed identity lands on PHI, and §19.3's rule stops being a
   precaution and starts being the control. **Decide the blinding question before that job runs,
   not after.**

---

## 20. DOOR 3 — DECIDED. The GCM invocation discipline is a counter pair known at origin

*Decided and implemented 2026-09-19. `io.cresco.gfs.crypto.SegmentCipher`, proof
`eval/sim/IvDiscipline.java`, 14/14. This closes §16 item 15b, which was the top blocking item and
the only one whose recovery class was **unrecoverable**.*

### 20.1 The defect was a sentence in shipping code

`CryptoBox.gcmEncryptWithIv` carried the comment *"caller guarantees (key, iv) uniqueness"*, and no
caller ever did. That delegation was harmless while the chunk key was `HKDF(K_rdom, "chunk" ‖ sid)`,
because a distinct key per chunk makes an IV collision across xorbs meaningless. **Retiring `K_rdom`
for per-object keys silently converted a safe comment into an unrecoverable hazard**: one key now
covers every chunk of its object, 184,044 invocations for a single 12.06 GB weights object, with no
allocator, no reservation and no monotonicity anywhere in the tree.

The fix prescribed when the defect was filed as a *disclosure* problem —
`iv = HKDF(K_meta, volume_id ‖ ordinal ‖ offset)` — is **unimplementable**, and that is the whole
difficulty rather than an inconvenience. `volume_id` and `ordinal` are assigned by `seal()` at the
receiving site after despool (§4); encryption happens at the origin before spooling (§11.1); and one
ciphertext then lands at three distinct `(volume, ordinal)` pairs before erasure coding. **An IV may
only be built from what the writer knows before the first byte leaves.**

### 20.2 The construction

```
K_seg = HKDF(K_obj, info = len ‖ "gfs/seg/v1" ‖ len ‖ idempotency_key)
iv    = xorb_seq[64] ‖ chunk_ordinal[32]            // 96 bits exactly, big-endian
aad   = xid ‖ xorb_seq ‖ chunk_ordinal ‖ sha256(plaintext)
```

Three properties, each of which had to be argued separately:

1. **Uniqueness is structural, not probabilistic.** Concatenating two counters is injective, so
   distinct `(xorb_seq, chunk_ordinal)` give distinct IVs — by arithmetic, not by a rule someone
   must remember. Measured at the scale that raised the alarm: **184,044 distinct IVs from 184,044
   invocations, zero collisions.**
2. **No RNG is in the trust path.** This is the reason not to simply keep the random-IV path, which
   is in fact SP 800-38D compliant at this scale and collides with probability ~2·10⁻¹⁹. That number
   is fine right up until a VM fork, a container restored from a snapshot, or a low-entropy boot
   hands two writers the same stream — a documented failure class that a counter cannot exhibit. The
   proof checks both directions: the deterministic path reproduces its ciphertext byte-identically
   from an independently constructed cipher, and the random path does not.
3. **A key per write segment, because counters restart.** `xorb_seq` restarts at zero for each write
   intent, so an appended object or an upload resumed under a fresh idempotency key would replay the
   same counters — the exact collision being prevented. Deriving `K_seg` per idempotency key gives
   each segment its own counter space, and because it derives *from* `K_obj`, **destroying `K_obj`
   still destroys every segment: crypto-shredding granularity is unchanged** and is checked.

### 20.3 The retry rule, which is the remaining sharp edge

A retry re-presenting the **same** content at the same counter is harmless: identical plaintext, key
and IV give identical ciphertext and disclose nothing new. A retry presenting **different** content
at the same counter is the catastrophe. So the plaintext digest is bound into the AAD and checked
against first use *before the cipher is touched*, and a conflicting retry is **refused, never
re-encrypted**. The in-process detector cannot see another process — which is precisely why the
construction must be injective on its own — but it converts a coding error into an immediate
exception instead of an unrecoverable cartridge.

The AAD also binds position, so a chunk lifted from one xorb and replayed into another fails
authentication rather than decrypting into the wrong object. Both the moved-ordinal and the
re-homed-`xid` cases are checked.

### 20.4 Headroom, and one structure removed

| quantity | value |
|---|---:|
| invocations addressable under one segment key | 1.511 × 10²³ |
| invocations for the object that raised the alarm | 184,044 |
| headroom | 8.21 × 10¹⁷ × |
| GCM blocks under one key | 7.54 × 10⁸ |
| birthday term `n²/2¹²⁸` | 1.7 × 10⁻²¹ |

Because the IV is a pure function of two ordinals the trailer already carries, **it is never
stored**: a reader rebuilds it. That removes 12 bytes per chunk from media — 2.2 MB for that one
object — and, more to the point, removes a per-chunk field that would otherwise have been one more
permanent structure to get right on unerasable media.

### 20.5 What remains owed

- **`K_meta` and the catalogue cnodes are on the same hazard and are not yet converted.** §16 item
  15b named them explicitly ("catalogue cnodes included"). `SegmentCipher` covers chunk encryption
  under `K_obj`; the cnode tier encrypts under `K_meta` with its own invocation count and needs the
  same discipline or an explicit argument that its counter space is already injective. **This is now
  the top open crypto item.**
- **The in-process detector is in-process.** Two writers for one object under one idempotency key
  would each believe they own the counter space. The idempotency key is issued per write intent and
  a second writer must therefore hold a second key, but nothing in the SPI *enforces* that, and it
  should — a lease on the idempotency key, refused rather than shared.
- `CryptoBox.gcmEncryptWithIv` remains callable directly. Its comment now names `SegmentCipher` as
  the only sanctioned caller for object data; that is documentation, not a compiler error, and the
  §17 checklist should grow a lint for direct callers.
