!!! danger "Status: Superseded"
    **Superseded 2026-09-20: Bareos is out.** Kept because its licence analysis is what led to that decision, and because its reading of the Bareos source remains accurate.

# THE RECOMMENDATION — Bareos as the volume manager

**Status:** Recommendation, for adoption into `SPECIFICATION.md` §2.3, §6 and §13.
**Scope:** Layer 0 of STELE — the boundary between our parcels and the medium.
**Verified against source, not documentation:** `bareos/bareos` at `f5adb7e` (master) and
`markh794/mhvtl` at `59f32ee`, both cloned locally. Every claim below marked **[src]** was checked
in the tree at the cited file and line. Claims marked **[rig]** are unverified and are listed in §9.

---

## 1. The decision

**Adopt Bareos as the volume manager. Adopt mhvtl as the rig, from day one, behind Bareos and
beside it. Build no `gfs-mover`.**

Not "test rig only", and not "reject". The three-way question is malformed in one specific way, and
naming the error is what settles it: the debate asked whether Bareos can *be* `gfs-mover`. It cannot
— `gfs-mover` was specified as a process holding `CAP_SYS_RAWIO` behind a fixed CDB allowlist, and
Bareos is three daemons and a relational database sitting three orders of magnitude above a CDB. But
the correct response is not to reject Bareos; it is to notice that under the owner's division
`gfs-mover` **is deleted rather than replaced**, and that what survives in its place is not a mover
at all.

### The argument that settles it

The prior design's own residual said it plainly: *"we are trading a decade of field hardening for a
write path of one function and a read path of one function."* `SPECIFICATION.md` ~~§5.6~~ **§2.3, with
the deletion-cost row *The tape block layer* in §15** *(citation corrected 2026-09-19: `SPECIFICATION.md`
§5 contains only §5.1–§5.4; there is no §5.5, §5.6 or §5.7)*, then costed
that trade honestly at ~1,600 lines for the tape volume, and identified which lines carry the risk:

- **~200 lines** of early-warning to programmable-early-warning end-of-medium handling;
- **~400 lines** of sense-key / ASC / ASCQ classification and reposition-after-error.

Those two — 600 of 1,600 lines — are the ones whose failure mode is *silent data loss*, and they are
the only two we had no way to test before hardware arrives. The owner's division puts exactly those
two on Bareos's side of the line. That is not a coincidence and it is not a compromise: it is the
division a competent reading of our own line-count table would have produced anyway.

And the things that must stay ours all sit *above* a file abstraction, which means Bareos cannot
touch them:

- **A parcel is one Bareos file, exactly `PARCEL_BYTES`, always.** Bareos stores bytes under a name
  we choose; it never inspects them.
- **The fragment trailer and the index checkpoints are parcels too.** The AEAD sealing, the Merkle
  tree, the MAC'd checkpoint chain — all of it is payload to Bareos.
- **The locator is ours**, and it never contains a Bareos coordinate (§4).

The second half of the argument is the one the prior design could not answer and this one can.
§4.2's standing obligation — a versioned published on-media format specification and a maintained
reference reader, for the thirty-year life of the medium, with no standards body to inherit it — was
the design's worst unanswered weakness. `bls`, `bextract` and `bscan` are that reader, they are
catalogue-free (**[src]** `bextract` links `Bareos::LibSD`, `Findlib`, `Lib`, `CLI11` and **not**
`Bareos::Cats`, `core/src/stored/CMakeLists.txt:145`), and they are maintained by somebody else. We
still publish a spec for the STELE structures *inside* the files, which is a few hundred lines of
format description rather than a tape driver. That is a strictly smaller permanent obligation.

### What replaces `gfs-mover`, precisely

Not one process. Two things, and the containment is better than the allowlist it replaces:

1. **Bareos** (`bareos-dir` + `bareos-sd` + `bareos-fd` + PostgreSQL, local to the plant) owns
   drives, changer, reservation, block framing, filemarks, end-of-medium, sense classification,
   volume labelling.
2. **`gfs-probe`** — a small, non-root, read-mostly helper with a **five-opcode allowlist**:
   `INQUIRY`, `LOG SENSE` (pages 0x0C, 0x31, 0x02, 0x03), `MODE SENSE`/`MODE SELECT` on enumerated
   pages, `READ ATTRIBUTE`/`WRITE ATTRIBUTE`, `SECURITY PROTOCOL IN`. It runs **only between jobs**,
   on a drive Bareos is not holding.

   `WRITE(6)`, `WRITE FILEMARKS`, `LOCATE(16)`, `READ(6)`, `MOVE MEDIUM`, `READ`/`REPORT ELEMENT
   STATUS`, `PERSISTENT RESERVE IN/OUT`, `FORMAT MEDIUM` and `ERASE` are **not reachable opcodes in
   any process we write**. The old design's twenty-row allowlist shrinks to five, and the process
   that could destroy a cartridge stops existing in our codebase.

### What we are deliberately not doing

- **No `bextract` on the hot path.** It *can* drive an autochanger — `AcquireDeviceForRead` calls
  `AutoloadDevice` (**[src]** `core/src/stored/acquire.cc:334`) — and that is precisely why it must
  not. The changer lock is a process-local rwlock on the Autochanger resource (**[src]**
  `core/src/stored/autochanger.cc:393-430`), so a `bextract` that autoloads is a **second changer
  initiator** with no lock between it and `bareos-sd`. §6 already rules that two schedulers issuing
  `MOVE MEDIUM` to one robot is a correctness failure. `bextract` is a recovery and proof tool, run
  against a released drive, never concurrently with the SD.
- **No Bareos plugin of any kind**, and specifically not `scsicrypto-sd` or `scsitapealert-sd` (§5,
  §6).
- **No use of Bareos's job scheduler.** Its `Priority` mechanism is structurally unusable for us
  (§3, finding G-3).
- **No recycling, pruning, migration, copy or virtual-full**, ever.

---

## 2. The Layer 0 contract

One interface, three implementations (`BareosVolume`, `SimVolume`, and later `PosixVolume` for the
directory case). It sits *under* STELE's **ten** block-plane calls (`open`, `close`, `recover`, `append`, `seal`, `abandon`, `read`, `prove`, `index`, `retire`) and changes none of them. *(Corrected 2026-09-19: "eleven" was wrong — `SPECIFICATION.md` §5.1 is headed "The SPI — ten calls" and enumerates exactly ten. A reader implementing against this contract would have looked for a call that does not exist.)*

```java
package io.cresco.stele.vol;

/** One volume = one cartridge. Never spans. All calls are against a LOADED medium. */
public interface VolumeMover {

    VolumeCapabilities capabilities();          // declared, read by the planner, never inferred

    // ---- inventory and attachment: the CHANGER IS NOT OURS ----
    Inventory   inventory();                    // barcode -> element; no mount; cheap
    Attach      attach(String barcode, Mode mode);   // asks the volume manager to load+claim
    void        detach(Attach a);                    // release; post-condition is declared

    // ---- write: staging is the boundary; nothing touches a drive until commit ----
    void        stage(Attach a, long ordinal, ByteBuffer parcel);  // exactly PARCEL_BYTES or refuse
    Commit      commit(Attach a);               // THE barrier. One fragment. Blocks to terminal.
    void        discard(Attach a);              // staged bytes dropped; medium untouched

    // ---- read: one fragment, contiguous, in ascending media order ----
    Fetch       fetch(Attach a, ReadSet parcels, Path sink);

    // ---- recovery: never on a hot path ----
    Survey      survey(String barcode, SurveyDepth d);   // LABELS | SESSIONS | FULL

    // ---- health: read-mostly, between jobs only ----
    MediumHealth health(Attach a);              // gfs-probe: LOG SENSE, TapeAlert, MAM, crypto state
}

final class VolumeCapabilities {
    String  moverKind;            // BAREOS | SIM | POSIX
    String  containerFormat;      // "bareos-BB02" | "stele-raw" | "sim-1"
    String  versionPin;           // exact volume-manager version this adapter was written against
    Order   ordering;             // EXACT | MONOTONIC_FORWARD | ARBITRARY
    Evidence faultEvidence;       // NATIVE_SENSE | LOG_PARSE | INFERRED | NONE
    Cancel  cancelPostcondition;  // UNLOAD_AND_FRONTIER | TERMINATE_ONLY
    Grain   eventGranularity;     // PER_PARCEL | PER_FRAGMENT
    Tri     reservationCapable, senseVisible, modeSelectCapable,
            mamWriteCapable, encryptionAssertCapable, costDecomposable;   // YES | NO | UNMEASURED
    long    parcelBytes, maxCommitBytes;
}
```

Five design decisions, each doing specific work.

1. **One `commit` = one fragment = one Bareos job = 96 parcels + one trailer.** This is the single
   most important mapping in the document. It bounds the crash blast radius to one fragment, bounds
   session-label leakage to one timestamp per fragment, and preserves the contiguity that is our RAO
   substitute. It also matches STELE's own torn-tail cost exactly, so adopting Bareos changes the
   crash economics **not at all** (§8, F-A).

2. **`stage` returns no position, and does not need to.** STELE §1.2(1) already made the correction
   that dissolves the whole `addressAtAppend` argument: *"the locator is discovered at a durability
   barrier, never predicted… a locator that was not returned by a successful `seal` does not
   exist."* `STORAGE-BINDINGS-DECISION.md` §3/§4's `append` returning a provisional ref from `READ
   POSITION` is **superseded**, and that supersession is a correction to the older document, not a
   concession to Bareos.

3. **Every capability is declared and tri-state.** `UNMEASURED` is a legal value that schedules
   pessimistically and appears on a list somebody works through. A capability surface with no way to
   say *"we have not measured this"* gets a plausible default written into it, and a planner then
   schedules against a guess that looks like a fact. No adapter may run in production with an
   `UNMEASURED` field.

4. **`faultEvidence` is mandatory.** A Bareos-backed adapter answers `LOG_PARSE` and may never
   answer `NATIVE_SENSE`. STELE's `Result<T>{senseKey, asc, ascq, atOrdinal}` degrades *visibly*
   rather than being quietly fabricated (§3).

5. **`versionPin` is in the capability surface, not in a config file.** Our entire fault
   classification is string-matching against `bareos-dir` job-log text, which is not an API, is not
   versioned and is localisable. The adapter refuses to start against a Bareos it was not written
   for (§8, S-K).

### Five reversibility rules, all cheap, all in the first build

- **R1 — `containerFormat` is a property of the cartridge, recorded at commissioning, and no
  cartridge is ever written in two formats.** `capabilities().formatsReadable` gates every attach; a
  mover that cannot read a cartridge's format refuses rather than mounting it.
- **R2 — the STELE parcel head, trailer and checkpoints are written *inside* the payload, never in
  the container's framing.** Twenty-four cleartext bytes per parcel (`magic | ordinal | flags |
  crc32`), the AEAD trailer, and the MAC'd checkpoint chain are opaque to Bareos. This is what
  converts "Bareos is the only thing that can read this cartridge" into "Bareos is the *easiest*
  thing that can read this cartridge", and it is what makes the decision reversible rather than
  permanent.
- **R3 — nothing in our ledger is ever read back from Bareos's catalogue.** Bareos is write-mostly
  to us (§4).
- **R4 — we never write Bareos's PostgreSQL schema directly.** Recovery goes through `bconsole` or
  through a fresh cartridge; populating another program's relational schema is both a version-skew
  landmine and the one place the arm's-length licensing story thins (§6).
- **R5 — we author our own `Changer Command` from scratch**, against the documented five-verb
  interface (`loaded`, `load`, `unload`, `list`, `slots`). We never edit Bareos's shipped
  `mtx-changer` (§6). This rule also buys a scheduling property: see §3.

---

## 3. Guarantees no Bareos-backed implementation can ever make

These are structural. No configuration fixes them, and each is stated with what we do instead.

| # | Guarantee lost | Evidence | What we do instead |
|---|---|---|---|
| G-1 | **SCSI Persistent Reserve on the changer and every drive LUN.** §6's fencing ladder has no top rung: reservation is `bareos-sd` process memory, dies with the process, binds no second host on a shared fabric. | `grep -rni "persistent reserve" core/src` returns **nothing**. The entire raw-SCSI surface is `scsi_lli.cc` (410 lines), `scsi_crypto.cc`, `scsi_tapealert.cc`. **[src]** | **Single-host-per-changer becomes an operational rule, not a mechanism.** Risk row 18 moves from *Prevent* to *Prevented by deployment*. Fencing is enforced where it can be: on epoch loss the scheduler stops submitting, and the device nodes are revoked from the SD's group so a retry fails with `EACCES` rather than reaching the medium. Takeover is a STONITH story, and it must be written. |
| G-2 | **The read-error recovery policy** — at most one same-drive retry, then rebuild from local parity *on the pass in progress*, bounded in drive-seconds not attempts (risk row 12, called "the honest justification for owning the path"). | Bareos's retry behaviour inside a job is its own and is not expressible at that granularity. | Local-parity reconstruction moves from *during the pass* to *after the error*, costing **one extra mount in the rare case**. Set the device wait timeouts low so a marginal cartridge fails fast rather than consuming a drive. Already recorded in `SPECIFICATION.md` §2.3 as the whole price. |
| G-3 | **Lane priority.** The target priority is taken from the **first running job**, mixed priority requires *every* running job to allow it and admits only strictly-higher priorities, and a mismatch sets `JS_WaitPriority` and **breaks** the walk. | **[src]** `core/src/dird/jobq.cc:456-500`. Defaults: `Priority` 10, `AllowMixedPriority` false (`dird_conf.cc:346-347`). | **Every tape job carries the same `Priority`, `AllowMixedPriority = yes` everywhere, and Bareos's scheduler is declared deliberately unused.** All five lanes, the deadline ordering, the coalescing window and the obligation reserve live in our scheduler, upstream of submission. A config lint fails the plant if any two Job resources differ in `Priority`. |
| G-4 | **Preemption at any granularity.** There is no yield point and no drive-second budget. | Priority affects only queued jobs, never running ones. | Preemption is fragment-atomic by construction (one commit = one job). `cancel` = `cancel jobid` → poll to terminal → hash staging → `release storage` → our own re-inventory. **Worst-case latency to free a drive is one mount**, and it is carried explicitly in every plan's `estWallP95`. Every obligation job is exactly one cartridge, never longer. |
| G-5 | **Structured sense data.** `Result.senseKey/asc/ascq` has no source; `Fault` must be inferred from job-log text. | No structured per-record error surface. | Fault *localisation* is unaffected, because it was never from sense in the first place: the parcel ordinal comes from our own bookkeeping and the authoritative check is the Merkle leaf. What degrades is **classification** — and classification is what the `(drive, medium)` fault histogram needs. `gfs-probe` reads `LOG SENSE` 0x02/0x03/0x0C and TapeAlert between jobs and writes straight into the histogram, which is where §5.3 put it anyway. `faultEvidence = LOG_PARSE` is declared, and the policy branches on it: with `LOG_PARSE` we do **zero** retries and go straight to parity, because a retry whose failure we cannot classify spends drive-seconds to learn nothing. |
| G-6 | **Recommended Access Order.** Bareos follows bootstrap-record order. | — | Mitigated, not solved, by contiguity: a fragment is 103.1 GB contiguous on one volume by construction. Recorded as a costed trade. |
| G-7 | **A mutable surface on the cartridge**, if MAM write is unavailable through the helper. | mhvtl defines `WRITE_ATTRIBUTE 0x8d` (`include/common/mhvtl_scsi.h:133`) but **does not dispatch it** in `usr/spc.c`. **[rig]** on real hardware. | The index-checkpoint pointer must then be found by reading the last checkpoint rather than by a MAM read at load. Cost: one locate plus a short read instead of zero tape motion. If real drives accept `WRITE ATTRIBUTE` from the helper between jobs, we recover the cheap path. **Rig item R-14.** |
| G-8 | **Suppression of commit time on the medium.** | Volume label `write_btime = GetCurrentBtime()` (**[src]** `label.cc:488`); session SOS and EOS labels `SerBtime(GetCurrentBtime())` (**[src]** `label.cc:580`); `jcr->Job` is composed as `<name>.%Y-%m-%d_%H.%M.%S_%02d` (**[src]** `dird/job.cc:1505`) and is serialised into every session label. None is configurable. | This is the one permanent disclosure. §5 states its exact shape and who must sign it off. |

---

## 4. The two-catalogue posture

**"Ours authoritative, theirs derived via `bscan`" is the wrong shape. The correct posture is three
tiers, and Bareos's catalogue is the bottom one.**

| Tier | Holds | Rebuilt by | Cost |
|---|---|---|---|
| **1. Placement ledger (ours)** | `locator → (volume, stripe, fragment)`, the volume registry | Journal + replicas | — |
| **2. On-media index checkpoints (ours)** | `{ordinal, parcels, leaf_root, stripe_id, fragment_i}` + the per-session join record, AEAD-sealed under `K_vol`, at ¼, ½, ¾ and EOD | One locate, one short read | seconds |
| **3. Bareos catalogue** | `Media`, `Job`, `JobMedia`, `File`, `Path` | `bscan` — a **full-volume read**, ~20.8 h per 30 TB cartridge at 400 MB/s | last resort only |

**Why this is sound and the two-tier version is not.** `bscan` does not rebuild *our* facts; it
rebuilds *Bareos's*. Tier 2 is what makes media-only rebuild real, it is ours, it is encrypted, and
it costs seconds rather than a drive-day. A posture that leans on `bscan` is leaning on a 21-hour
recovery on the conserved resource, in exactly the circumstance the tier exists for.

### The join rule, which is the load-bearing part

The tier-2 checkpoint gains one small per-session record so that a read is synthesisable with **no
Bareos catalogue at all**:

```
session_join { VolSessionId, VolSessionTime, first_ordinal, first_FileIndex, parcel_count }
```

From that, a bootstrap record is a pure function of the locator's `ordinal`. Two rules make it
survive:

- **Key on `(VolumeName, VolSessionId, VolSessionTime, VolFile, VolBlock, FileIndex)` and never on
  `JobId`.** `VolSessionId` and `VolSessionTime` live in the BB02 block header on the medium;
  `JobId` is a catalogue-assigned integer that `bscan` renumbers. A locator keyed on `JobId` dies
  the first time the catalogue is rebuilt.
- **One parcel = one file = one `FileIndex`, monotone within a session.** This is what makes the map
  affine, and it is also what makes error localisation per-parcel.

Note a fact that makes `VolSessionTime` safe to record: it is **not a timestamp of the write**. It
is the storage daemon's process start time — **[src]** `core/src/stored/stored.cc:283`,
`vol_session_time = (uint32_t)daemon_start_time`, assigned once per SD run at `job.cc:133`. It is
therefore constant across every block and every session that SD writes. The claim that every block
header carries a second-resolution clock, giving 10⁷–10⁸ timestamps per cartridge, is **false**; it
is one value repeated. This materially shrinks the leakage surface and it is checkable in an hour
(**rig item R-7**).

### Reconciliation, by case

- **Crash mid-commit.** Our journal holds a write-intent row before the first byte. On restart, for
  the open intent: `llist jobid=` → status `T` means pull `list jobmedia`, read back the trailer,
  verify, then the locators exist. Anything else means **the fragment does not exist**: no locator
  was ever returned, nothing above believes it durable, the media is charged as dead tape
  (`unreclaimableTombstoned`) and the fragment is rewritten elsewhere. Cost: at most 103.1 GB, 0.34 %
  of a cartridge, roughly $1.50 of media. **This is STELE's torn-tail cost, unchanged.**
- **Volume written but not catalogued.** Tier 2 already has it. Bareos's view is repaired by `bscan`
  into a scratch database on `tmpfs`, or simply by starting a fresh cartridge — on WORM that costs
  tape, not data.
- **Bareos catalogue lost entirely.** Reads are unaffected (`bextract` needs no catalogue). Writes
  do not resume until `update slots` has re-inventoried and every volume with `VolStatus = Append`
  has been set `Used`; we start a fresh cartridge. **WORM converts the worst two-catalogue failure
  into a capacity charge**, which is the strongest structural argument for the posture.
- **Our ledger lost.** Tier 2 from every cartridge: one locate and one short read each, not `bscan`.
- **After a restore.** Nothing to reconcile; restores do not mutate media.

### What Bareos's catalogue holds that the medium does not

`VolStatus`, `InChanger`, `Slot`, and volume error and mount counts are catalogue-only, and they are
generated *by failures*, so no "we never enable that feature" containment covers them. **Mirror
every `VolStatus` transition and every health reading into our ledger at job completion.** Then stop
calling their catalogue derived and call it what it is: a second authority over a small enumerated
set of facts that we replicate. An honest two-authority posture over five fields is defensible; a
false one-authority posture is how the media-health record gets lost.

**Also: the Bareos catalogue is derived in *content* but load-bearing in *availability*.** Every job
start inserts rows and every job end writes file attributes, so a stalled or vacuuming PostgreSQL
delays a mount. It is a plant-critical component, it is sized and tuned as one, and its health is in
the plant predicate.

---

## 5. The disclosure contract

**Established from source. This section is the one that must be right before the first WORM
cartridge, because it cannot be corrected afterwards.**

### What Bareos writes in the clear

- **Volume label, once per cartridge:** `Id` ("Bareos 2.0 Immortal"), `VerNum`, `label_btime`,
  `write_btime`, `VolumeName`, `PrevVolumeName`, `PoolName`, `PoolType`, `MediaType`, `HostName`,
  `LabelProg`, `ProgVersion`, `ProgDate` — **[src]** `label.cc:480-506`.
- **Block header, every block:** `CheckSum`, `BlockSize`, `BlockNumber`, `"BB02"`, `VolSessionId`,
  `VolSessionTime` (the SD start time — see §4).
- **Session labels, SOS and EOS, once per commit:** `JobId`, a real wall-clock btime, `PoolName`,
  `PoolType`, `JobName`, `ClientName`, the unique `Job` string **with an ASCII date in it**,
  `FileSetName`, `JobType`, `JobLevel`, `FileSetChecksum`; EOS adds `JobFiles`, `JobBytes`,
  start/end file and block, `JobErrors`, `JobStatus` — **[src]** `label.cc:558-600`.
- **One attribute record per file:** the **fully qualified filename** plus 13 base64 `stat` fields
  including `st_dev`, `st_ino`, `st_nlink`, `st_rdev`, `st_blksize`, `st_blocks` — **[src]**
  `core/src/lib/attribs.cc:55-80`.

### The contract — eight conditions, all enforced, not conventions

1. **The on-media filename is a 128-bit CSPRNG nonce, never a content address.** This is the one
   correction that nobody would find by inspection and it is not optional. Our content identifiers
   are `sid = HMAC(K_mac, chunk)` and `xid = HMAC(K_mac, sid_0‖…)` with `K_mac = HKDF(K_L, "sid")`
   (`STORAGE-DIRECTION.md`, *Structures → Keys* and the xorb wire format), while crypto-shredding
   destroys **the object's key** and **never** `K_L` *(2026-09-19: was "destroys `K_rdom`"; `K_rdom`
   is retired by `eval/results/ckpt_dedup_results.json`. **The conclusion is unchanged and the nonce
   filename remains non-optional**, because the shred never destroys `K_mac` or `K_L`, so any
   content-derived name remains computable by anyone who ever holds `K_L`. The reasoning is
   granularity-independent. Line-number citations into `STORAGE-DIRECTION.md` are replaced by section
   names, because that file has been edited and the numbers no longer resolve.)*. A content-addressed
   name on WORM is therefore a **confirmation oracle that survives the erasure it documents,
   forever**, computable by anyone who ever holds `K_L`. The
   design already applies exactly this reasoning to `leaf_salt` (`STORAGE-DIRECTION.md:1218-1226`).
   The nonce costs nothing: the locator is `(volume_id, ordinal)` and the bootstrap record is
   synthesised from the session join, so **the filename is load-bearing for nothing**. The
   nonce→ordinal map lives in the tier-2 checkpoint, sealed, on erasable-by-key terms.
   *This correction is mover-independent and applies to LTFS and to any raw-SCSI design too.*
2. **Every parcel is exactly `PARCEL_BYTES`.** Already `SPECIFICATION.md` §3.1, enforced as a hard
   refusal in `stage`. This makes `DataSize`, `st_size`, `st_blocks` and `JobBytes` constants.
3. **Staging is one flat directory with a constant path prefix.** No per-commit, per-fragment,
   per-lineage, **per-object** or per-redaction-domain path component — the *whole path* is written.
   *(2026-09-19: `per-object` added to the existing forbidden list rather than as a new rule. The list
   enumerates the design's granularities and per-object is now one of them; an object id on WORM is
   exactly the oracle condition 1 exists to prevent, whether or not the id is content-derived.)*
4. **The whole `stat` buffer is normalised** before commit: fixed epoch for atime/mtime/ctime, one
   uid/gid, fixed mode, a dedicated filesystem so `st_dev` is constant. `st_ino` **cannot** be
   pinned; it is a weak write-order channel already visible from `FileIndex`, and it is accepted
   explicitly rather than listed among the pinned fields.
5. **`Signature` is absent from every FileSet.** The shipped examples set `Signature = XXH128`
   (**[src]** `core/src/defaultconfigs/bareos-dir.d/fileset/*.conf.in:6`), which would put a
   per-file ciphertext digest on the medium as its own stream — a permanent cross-corpus linkage
   token and a second integrity authority competing with our Merkle root. Never start from a shipped
   example FileSet; write ours from an empty file.
6. **No ACLs, no extended attributes, no software compression, no sparse handling, no FD-side PKI.**
   `PKI Encryption`, `PKI Keypair`, `PKI Master Key` and `PKI Signatures` are **forbidden by package
   absence, not by configuration**: they write wrapped content-encryption keys onto the medium and
   put key material at a blind holder, which is the blind-holder invariant failing silently. The
   plant health predicate asserts the plugin directory is empty.
7. **`PoolName`, `PoolType`, `MediaType`, `JobName`, `ClientName`, `FileSetName` are fixed opaque
   constants.** Never per-dataset, per-project, per-cohort or per-institution. A FileSet name that
   encodes a cohort defeats crypto-shredding permanently.
8. **The SD host's OS hostname is an opaque per-site identifier, set before the first `label`.**
   `HostName` is `gethostname()` with no directive anywhere (**[src]** `label.cc:544`). It is written
   at *commissioning*, by an operator running `label barcodes` — a different command at a different
   time from the one that configures jobs — so it sits outside every job-level control. One cartridge
   labelled on a correctly-named host before this discipline exists is a permanent disclosure of the
   holding institution, and it travels with the cartridge on export.

**Delete the shipped `BackupCatalog` job.** **[src]** `core/src/defaultconfigs/bareos-dir.d/job/
BackupCatalog.conf.in` ships by default and backs up the Director's PostgreSQL dump as an ordinary
file. On a WORM pool that dump lands on unerasable media as one plaintext artefact containing every
filename, every `LStat`, every Job and every Volume. A blind holding site must never be a backup
client of itself. Delete the resource; do not disable it.

### The residue, and the one condition we cannot meet

Under all eight conditions the medium discloses: *the barcode, fixed opaque pool/job/client/fileset
strings, the Bareos version strings, an opaque site identifier, N blobs of exactly 1 GiB, per-commit
byte and file counts (constants), physical positions, and a wall-clock commit time per fragment at
second resolution — in binary and again as an ASCII date string.*

Everything there is structure except the last, and the last is the LTFS addendum's **condition 3**,
which that addendum declared *non-negotiable*. **Bareos cannot meet it, and neither can LTFS.**

The test to apply is the one `ENTAIL-AGENT-NATIVE-FS.md:594` already established: a timestamp on
WORM is acceptable when *what it timestamps is de-linkable by key destruction*. Under condition 1 a
session label timestamps a set of **nonce-named, constant-size** blobs. After destruction of the
objects' keys *(2026-09-19: was "After `K_rdom` destruction"; retired, rename only — the
de-linkability test is unchanged)* nothing links them to a subject, a cohort or a dataset. The residue therefore discloses **when a
site received ciphertext, never what** — and the exposure is a per-fragment ingest-campaign profile,
at second resolution, permanent.

My assessment is that this is acceptable. **It is not mine to accept.** It is a permanent concession
on unerasable media, it is a declared non-negotiable being waived, and it must be signed off
explicitly by the constraint holder before the first WORM cartridge. The available partial
mitigation — mix redaction domains within a fragment, and commit on a fixed cadence with padding
commits so write times track the schedule rather than the ingest — trades directly against
cartridge-atomic expiry (`TAPE-RESEARCH-PROMPT.md` §1(e)) and must be costed, not assumed.

**Note 2026-09-19:** the partial mitigation (mixing within a fragment) is **no longer a free-standing
option**. Per-object keys force `pooled(n)` packing anyway — `SPECIFICATION.md` §8.4 rule 1's
½-parcel-per-run padding becomes ruinous at object granularity, recorded there as an open hole — so
this mitigation is partly taken **by default**, and its trade against cartridge-atomic expiry must
now be costed as part of that packing decision rather than separately. The concession, the
assessment, the statement that **it is not mine to accept**, and the requirement for explicit sign-off
by the constraint holder before the first WORM cartridge all stand unchanged.

Two smaller items for the same allowlist: **`PrevVolumeName` must always be empty** (a non-empty
value means a fragment spanned two cartridges, which §7 forbids, and it writes a permanent
cross-cartridge link); and `LabelProg`/`ProgVersion`/`ProgDate` permanently stamp the writing
software and build date, which is a supply-chain disclosure on a cartridge that leaves the site.

---

## 6. The licensing boundary

**Verified, not inferred:** `core/src` is **350,751 lines**; **979** files carry the Affero header
and **exactly two** carry LGPL (`core/src/lib/bsys.cc`,
`core/src/win32/compat/include/sys/mtio.h`). **There is effectively no LGPL interface layer. Do not
plan around one.**

| Band | Verdict |
|---|---|
| Run stock `bareos-dir`/`bareos-sd`/`bareos-fd` from distribution packages as separate OS processes; drive them over the Director console socket (`bconsole` in `.api 2`, or the protocol directly); author our own config, FileSets, Pools, bootstrap records and changer script | **Arm's length.** Separate address spaces, documented protocols, no linking, no Bareos code shipped. §13's network clause attaches to *modified* versions; unmodified Bareos run internally conveys nothing. |
| Import `python-bareos` | **Forbidden.** It is AGPLv3 and importing is linking. It costs us nothing to avoid — we are a Java bundle and `bconsole` is a subprocess. |
| Any SD, FD or Dir plugin (C or Python), any SD backend subclass, vendoring any Bareos source | **Forbidden.** `core/LICENSE` grants additional permissions only for OpenSSL and Windows VSS linking, and states that plugins must be AGPLv3-compatible. There is no plugin exception. |
| **Editing Bareos's shipped `mtx-changer`** | **Forbidden — and this is the trap.** It is a Bareos-supplied program, its documentation invites adaptation, and every real deployment edits it. An edited copy is a modified version of the Program, and §13 then obliges a source offer to remote users — across fifty institutions under data-use agreements who did not sign up for it. **We write our own changer script from scratch** (rule R5). |
| Patching Bareos for any reason | **Forbidden.** This is the rule that breaks under pressure, at 2 a.m., during a recovery — which is exactly when it is load-bearing. Make it mechanical: packages come from a distribution only, no Bareos source tree on any plant host, and a deploy-time lint that fails if anything under the Bareos scripts or plugin directories differs from the package. |
| Writing rows into Bareos's PostgreSQL schema | **Forbidden** (rule R4). Not linking, but it is the coupling counsel will ask about, and it is a version-skew landmine exercised only during disasters. |

**The cost this imposes, stated plainly:** the licence forecloses the efficient integration. The
documented way to stream at native speed without staging is an FD plugin, and that is precisely the
linking case. So every byte is written to staging and read back over the FD→SD socket. That
interacts with A-1 (staging as a new single point of loss) and it is unmeasured — **rig item R-11**.

**For counsel, before deployment and before the first export:** (a) does forking `bconsole` and
`bextract` with files on disk constitute mere use; (b) does distributing a container image
containing stock Bareos packages alongside our code create obligations beyond offering Bareos's
source; (c) does an institution running unmodified Bareos as part of a system we specified and
configured incur any §13 exposure, and what must the DUA template say. **`BAREOS` is a registered
trademark**; nothing we ship may carry a Bareos-like name or imply endorsement.

---

## 7. Configuration that is load-bearing, not cosmetic

Every item below is a **refusal at startup**, read back through `show storage` / `show job`, not a
file we hope is right.

**Volume targeting — one Pool per cartridge, and get the mechanism right.** One Pool, one Media row,
`Maximum Volumes = 1`, `Maximum Volume Jobs = 0` (**unset**), `Recycle = no`, `AutoPrune = no`,
`Volume Retention` effectively infinite, `Label Media = no`, no Scratch pool reachable.
**`Maximum Volume Jobs = 1` is a trap**: `next_vol.cc:235` refuses a volume once `VolJobs` reaches
it, so `=1` retires a 30 TB cartridge after one fragment. The `Maximum Volumes = 1` rule also means
**there is nothing to span to**, so an end-of-medium overshoot fails the job instead of splitting a
fragment across two cartridges.

**Concurrency — four counters, all defaulting to 1** (**[src]** `dird_conf.cc:134, 225, 252, 342`).
The Job-resource limit counts per job *name*, so a single `gfs-commit` template silently serialises
the whole plant. Therefore: **one Job resource per drive**, one Director `Storage` resource per
Device, Device `MaximumConcurrentJobs = 1` (keep the default — it is what makes block interleaving
on WORM structurally impossible), Director/Client MCJ = drives + margin, `AllowDuplicateJobs = yes`
asserted rather than inherited, `RescheduleOnError = no` and `RescheduleTimes = 0` asserted (a
reschedule writes a second copy of a fragment to WORM with our ledger unaware).

**Zero-depth queueing.** At most one outstanding job per Device. Our scheduler owns the standing
intent queue, the coalescing window, wave formation and deadline ordering, and calls `run` only
after it has decided which cartridge mounts next on which drive. Bareos's queue is then empty and
its priority arbitration is unreachable code (`jobq.cc:455` guards on `!waiting_jobs->empty()`).
**Cost: no pipelining** — the next mount cannot begin until the previous job terminates. That is a
real drive-second tax on the conserved resource and it is **rig item R-9**.

**The changer lock is ours to shape.** `LockChanger` is held across the entire
`RunProgramFullOutput` of the load command, plus the unload of the previously-loaded volume and of
any other drive holding the wanted slot (**[src]** `autochanger.cc:194-287`). So per library, robot
access serialises. **Because we author `Changer Command` (R5), we control what is inside that
lock**: our script returns as soon as `mtx load` returns, and never waits for drive-ready. Then only
the robot move serialises and the three load-to-ready waits overlap. If instead the lock spans
load-to-ready, mount capacity becomes a scalar independent of drive count and the third drive per
site stops paying for itself. **This is the single most consequential scheduling measurement on the
rig — R-8, and it runs first.**

**`Prefer Mounted Volumes` is a Director *Job* directive, default true** (**[src]**
`dird_conf.cc:336`), not an SD Device directive. Under one Pool per cartridge with one outstanding
job per device it is inert; set it explicitly on evidence rather than inheriting it, and note the
documented alternative (`no`) carries a vendor-acknowledged deadlock warning.

**Timeouts.** `MaximumChangerWait`, `MaximumOpenWait`, `MaximumRewindWait` all default to **300 s**
(**[src]** `stored_conf.cc:182-187`) — longer than a mount, and Bareos's failure idiom under
contention is to *block and ask an operator* at three unattended sites. Tune all three below one
mount, and add our own **submission watchdog**: if a job has not reached a running state within
`estWallP95`-derived bound, cancel it and synthesise the named refusal ourselves. Bareos will not
produce `Refusal.retryAfterEpochMs`; we must.

**`Maximum File Size = 1073741824`**, set explicitly to align Bareos's filemark cadence to the
parcel boundary (the default is already 1,000,000,000 — **[src]** `stored_conf.cc:191`). A filemark
per parcel is *good* here: it is what makes `VolFile` positioning cheap.

**`AlwaysOpen`** defaults on, and `unmount` is a **sticky administrative state**. Mount/unmount
state is scheduler-owned and journalled, with a crash-recovery pass that reconciles `status storage`
against the journal on start; "device administratively unmounted with no open ticket" is a CRITICAL
plant predicate, because nothing else will notice a self-inflicted one-third outage.

**Obligation reserve by physical partition.** Bareos cannot express a reserve as a *fraction* of
drive-seconds, only as whole dedicated devices. At three drives per site the minimum expressible
reserve is 33 % or nothing. So the reserve is enforced in our scheduler as a submission-rate
invariant over a rolling window, with device pinning available as a coarse backstop. This must be
stated, because a published reserve that is neither a fraction nor a device is a promise with no
mechanism.

---

## 8. Findings: resolution

Every FATAL and SERIOUS class raised across the four positions and twelve attacks.
**R** resolved · **A** accepted cost · **G** gated on the rig · **C** the finding is factually wrong.

### Corrections — findings refuted from source

| | Claim | Verdict |
|---|---|---|
| C-1 | Every block header carries a second-resolution write clock; 10⁷–10⁸ timestamps per cartridge; "one `#ifdef`" would not fix it | **C.** `VolSessionTime` is the SD *process start time*, constant for that SD run — `stored.cc:283`, `job.cc:133`. One value repeated, not a clock. The real timestamps are one per volume label and two per commit. |
| C-2 | mhvtl stops at LTO-8/LTO-9, so nothing LTO-10-specific is testable | **C.** At `59f32ee`, `Media_LTO10` and `Media_LTO10P` are present (`usr/vtllib.c:1692-1693`), as are `PERSISTENT_RESERVE_IN/OUT` (`usr/spc.c:1034`), `READ_ATTRIBUTE` (`:1050`), `LOG SENSE` TAPE_CAPACITY page with live remaining-capacity (`usr/mhvtl_log.c:389-397, 703-715`), settable programmable early warning (`usr/mode.c:611-614`), WORM mode-page behaviour and SPIN/SPOUT (`usr/ssc.c:925-944`). |
| C-3 | `Prefer Mounted Volumes` is an SD Device directive | **C.** Director Job resource, default true — `dird_conf.cc:336`. The correction cuts *toward* Bareos: it is settable per dispatch. |
| C-4 | `append` cannot return a real address, so the write receipt collapses and crash loss grows ~150× | **C.** Superseded by `SPECIFICATION.md` §1.2(1): the locator is discovered at the barrier, never predicted. The crash unit is the fragment under both designs, and the cost is identical (§4). The finding is against the older document, not against Bareos. |
| C-5 | `bextract` cannot drive an autochanger, so an imported cartridge has no read path | **C**, and the true finding is worse: it *can* (`acquire.cc:334`), which makes it a second changer initiator. Resolved by never running it concurrently with the SD (§1). Import is handled by `bconsole` volume registration plus a bootstrap-record restore — **rig item R-13**. |

### Fatal and serious — resolved

| | Finding | Disposition |
|---|---|---|
| F-A | Crash mid-write orphans WORM bytes with no recoverable locator | **R** — one commit = one fragment; a locator that no `commit` returned does not exist; the orphan is charged as dead tape at 0.34 % of a cartridge. Identical to STELE's torn-tail cost. |
| F-B | The Bareos job is simultaneously the crash unit, the localisation unit, the batching unit and the overhead unit, and positions assumed opposite settings | **R** — the knob is set, once, at the fragment: 96 parcels + trailer, one job. Localisation is per-parcel by Merkle leaf, not per-job. Crash loss is one fragment. Batching is within the job. |
| F-C | Two changer initiators (`bextract` + SD, or a helper issuing `MOVE MEDIUM`) | **R** — exactly one changer initiator: `bareos-sd`. `gfs-probe`'s allowlist excludes `MOVE MEDIUM` and `READ`/`REPORT ELEMENT STATUS`. Inventory comes from `status slots`. `bextract` runs only against a released drive. |
| F-D | Changer serialisation converts the conserved resource from drive-seconds to changer-seconds | **R, conditional on R-8** — the lock spans our own changer script, which returns on robot-move completion. Measured first on the rig; if the shape is wrong, the third drive per site loses its justification and the plant arithmetic is re-derived. |
| F-E | Priority is unusable; a low-priority scrub blocks a deadline-bearing read on *idle* drives | **R** — uniform priority, `AllowMixedPriority = yes` everywhere, Bareos's scheduler declared unused, lanes enforced before submission (G-3). |
| F-F | `bscan`-rebuildability and a plaintext on-media index are the same property, so adopting Bareos inverts risk row 17 | **R** — tier 2 is ours and encrypted; `bscan` is demoted to last resort and its 20.8 h/cartridge price is published. The medium is self-describing **to the key-holder**, not to its possessor. |
| F-G | A content-addressed on-media filename is a confirmation oracle that survives the shred | **R** — CSPRNG nonce (§5, condition 1). Mover-independent; applies equally to LTFS and to the raw-SCSI design. |
| F-H | Bareos writes key material to the medium (FD PKI / `scsicrypto-sd`), creating a second custody domain at a blind holder | **R** — forbidden at *package* level, asserted by the plant predicate; `SECURITY PROTOCOL IN` read back by `gfs-probe`. Consistent with `SPECIFICATION.md` §6.1, row "Bareos PKI data encryption; drive encryption (`scsicrypto` / library-managed) → **OFF**, asserted by read-back" *(citation corrected 2026-09-19: there is no §5.7)*. |
| F-I | The shipped `BackupCatalog` job puts the whole plaintext catalogue on WORM | **R** — resource deleted, and a `bextract` of every file record is part of the pre-flight diff, not just a label dump. |
| F-J | Shipped FileSets set `Signature`, creating a second unerasable integrity domain | **R** — absent from every FileSet; build lint over the config tree; never start from a shipped example. |
| F-K | Pruning/recycling can purge a volume we consider durable, and the protection is a config string | **R, with the honest caveat** — `Recycle = no`, `AutoPrune = no`, infinite retention, `Maximum Volumes = 1`, asserted at startup. **WORM is the only capability-level backstop**, and it is why the durable path is WORM-only. |
| F-L | End-of-medium spans to the next volume, splitting a fragment | **R** — `Maximum Volumes = 1` means there is nothing to span to; `Maximum Volume Bytes` set below measured capacity as a backstop; `gfs-probe` reads `LOG SENSE` 0x31 between jobs and the scheduler refuses to open a fragment that will not fit (`SPECIFICATION.md` §3.1 — "every parcel is exactly `PARCEL_BYTES = 1073741824` … enforced as a hard refusal in `append`" — with §3.2's short-band rule, "a band shorter than full gets `j =` its actual data-parcel count"; *citation corrected 2026-09-19: there is no §5.7*; pad, never truncate); `PrevVolumeName` empty is asserted after every commit. |
| F-M | TapeAlert has three racing readers; `Alert Command` fires after device release so flags cannot be attributed to a (cartridge, drive) pair | **R** — exactly one reader: `gfs-probe`, between jobs, with the cartridge identity the scheduler already knows. `Drive Tape Alert Enabled` off and the plugin not installed. Writes straight into the `(drive, medium)` fault histogram of `SPECIFICATION.md` §5.3. |
| F-N | `cancel` has no defined post-condition; the SD may hold a drive our scheduler believes free | **R** — `cancelPostcondition = TERMINATE_ONLY` is declared; the adapter implements cancel as terminate → poll to terminal → hash staging → `release storage` → re-inventory, and verifies release before re-scheduling. |
| F-O | No push channel; `Ticket` state and the projected window are inferred from polled log text | **R** — `RunScript` with `RunsWhen = Before/After` (Director-side, no plugin, licensing-clean) pushes job-start and job-end edges. `MOUNTING → STREAMING` stays inferred and is declared so. `queuePosition` is **our** pre-submission position and says nothing about Bareos. |
| F-P | Version skew: fault classification is string-matching an unversioned surface on a daemon we must patch and may not modify | **R** — `versionPin` in the capability surface; the adapter refuses to start on a mismatch; a contract test per parsed command and per matched log string runs in CI against the rig; upgrades are scheduled plant maintenance, per site, never two sites in one window if cartridges move between them. |
| F-Q | Export/reimport double-counts durability credit and has no epoch reconciliation | **R** — import is a **reconciliation, never a restoration**: every fragment enters `PRESENT_CLAIMED`, is diffed against current placement, and a fragment whose stripe was repaired during transit is admitted as a redundant copy carrying **no** durability credit. Custody travels in MAM where writable, else in the sealed trailer. No object's independent-copy count may exceed its distinct-stripe count. |
| F-R | The plant's failure idiom is "ask the operator"; waiting-on-storage maps to a state the caller reads as progress | **R** — `MaxRunTime`/`MaxWaitTime` on every Job, the submission watchdog, and waiting-on-storage maps to `PLANT_DEGRADED`, never `MOUNTING`. |
| F-S | Bareos's catalogue is in the mount path although the posture calls it derived | **R** — stated explicitly: derived in content, load-bearing in availability; sized, tuned and health-checked as a plant-critical component (§4). |
| F-T | `run` is not idempotent; a lost JobId after submission leaves an orphan that could duplicate a fragment on WORM | **R** — a scheduler-generated ticket id goes in the job `Comment`, and crash reconciliation scans `list jobs` by that key, never by time. An ambiguous `run` is never retried before a scan. |

### Accepted costs

- **A-α — We do not own the retry policy.** Risk row 12 is surrendered; local-parity reconstruction
  moves from *during the pass* to *after the error*, at one extra mount in the rare case.
- **A-β — Permanent second-resolution commit time on unerasable media**, in binary and as an ASCII
  date. Waives a declared non-negotiable. **Requires the constraint holder's explicit sign-off**
  (§5).
- **A-γ — No RAO.** Mitigated by contiguity, recorded as a costed trade.
- **A-δ — Zero-depth queueing forfeits pipelining.** Precision over **GB per drive-hour**, chosen
  deliberately; the tax is the inter-job dead time charged against a **78,840 drive-hour
  plant-year**, measured at R-9 and re-opened if it is large. *(RESTATED 2026-09-19: this line
  previously read "precision over **utilisation**", which concedes something that is not a good —
  utilisation is an inverted objective, and the reactive plant shows higher utilisation precisely
  because it burns drive-seconds on mounts; `eval/results/plant_sim.json`.)*
- **A-ε — Three processes plus a database, not one.** The architecture is less tidy than
  "`gfs-mover` is one process", and the operational surface is four services per site with their own
  config languages, TLS and upgrade cadence.
- **A-ζ — Fifty-institution deployment exports an AGPL compliance posture** we can specify but not
  enforce on sovereign partner sysadmins. Bound it where it can be bound: distribution packages
  only, no source trees on plant hosts, drift is a compliance event.
- **A-η — `st_ino` is unpinnable**, and the pool-per-cartridge design means ~94 Director config
  resources per site with reloads contending against multi-hour jobs (**R-12**).

### Gated

- **G-α — Single-host-per-changer** replaces Persistent Reserve. The STONITH procedure is owed
  before any two-host site exists.
- **G-β — MAM write** (G-7), gated on R-14.
- **G-γ — The drive-ready placement in the changer lock** (F-D), gated on R-8.

---

## 9. The test plan

### The prerequisite, which is the long pole

**One dedicated x86-64 Linux host with root and ~2 TB of scratch.** mhvtl is an out-of-tree kernel
module needing matching kernel headers and a rebuild on every kernel update. The development machine
is macOS; the full-tunnel VPN hijacks the vmnet subnet, so local VMs are not a reliable fallback; and
the DGX cluster is SLURM with no root and no kernel-module rights. **Ask for the host now, not when
tape hardware is ordered.** mhvtl also ships a TCMU transport (`usr/transport_tcmu.c`) which relies
on in-tree `target_core_user` rather than an out-of-tree module — try that first, as it removes the
kernel-module build from the critical path.

**Rig as code from day one:** a repo with the pinned kernel, the pinned mhvtl commit, the pinned
Bareos version, the library definition and the whole Bareos configuration, rebuildable from nothing
by one script. Cartridge backing files are regenerated, never preserved. Named owner. The suite runs
in CI on every adapter commit, so a broken rig fails a build instead of quietly ceasing to produce
evidence.

### Order

**B0 — today, on macOS, no Linux, no Bareos: `SimVolume` and the fault injector.**
Implement the §2 contract over a directory tree and move the fault injector *to the mover boundary*.
This is the single best change available this week and it is true regardless of the Bareos decision:
today the fake lives *inside* the binding (`SimTapeBinding` + `FakeDrive`), so simulation and
reality differ at a seam that is not the seam anything will later swap, and every result is evidence
about a code path that gets replaced. At the mover boundary, the simulated and real plants differ in
exactly one component.

Inject mounts at the four-term cycle `O = 265 s` *(2026-09-19: was 90 s — `SPECIFICATION.md` §3.4
identifies the single-term 90 s figure as the error every candidate design made, and `O` is the
highest-leverage unmeasured constant in the programme)*, 40 s repositions, medium errors at a
position, deferred errors, torn tails,
short writes, unit attention mid-sweep, early warning mid-fragment. Add the two cases nothing
currently tests: **a degrading drive** (rising error counters, a TapeAlert flag on one drive and not
another for the same cartridge, sustained rate falling through the speed-matching floor) and
**contention** (three drives, three lanes, a deadline-bearing read arriving behind a 20-hour scrub),
run against **two dispatchers behind the same contract** — one ideal, one with Bareos semantics
(single priority band, monotonic-forward ordering, four concurrency caps, job-granular cancel, no
cross-job coalescing). Measure **GB per drive-hour (headline)**, bytes-per-mount, deadline miss rate, obligation drive-seconds
delivered, and time-to-first-byte behind a running scrub.

**Baseline to beat, from the plant simulation (2026-09-19, `eval/results/plant_sim.json`): 653.3
GB/drive-hour and 111.1 GB/mount on a clustered workload with batching and media-ordering; 172.3 and
13.3 scattered; 68.1 and 4.0 for a reactive dispatcher.** A Bareos-shaped dispatcher that lands near
the reactive figures **has failed even if every job completes**. Note the simulation's own limits,
which are exactly what this rig exists to cover: it models **retrieval only — no write path, no
scrub, repack or repair contention**, its cartridge assignment is synthetic, and its mount cost is
Gaussian about 90 s against a reported bimodal 60–120 s and against `SPECIFICATION.md` §3.4's
`O = 265 s`. **Scrub-versus-deadline contention is first observed on this rig, not in the
simulation.**

*Proves:* the contract is implementable; the scheduler degrades explicitly; whether Bareos-shaped
dispatch costs us anything we care about — **before the hardware request**, on the machine we have.

**B1 — half a day on the Linux host: mhvtl alone, by hand, no Bareos.**
`sg_inq`, `sg_logs`, `mtx status`, `mt status`. Establish what the emulator actually does before
either adapter depends on it. *Proves:* which of the twenty risk rows the rig can exercise at all.

**B2 — Bareos ≥ 23.1.0 plus mhvtl.** One library, three drives, ~20 slots, one WORM cartridge and
one rewritable, one Pool per cartridge, opaque everything. Run R-1 through R-14 below, **in that
order** — R-1, R-8 and R-2 first, because each can kill the design.

**B3 — the differential.** Corrupt one block in a backing file. Read with the Bareos adapter and
with `gfs-probe` + `bls`. Record where Bareos, our adapter and mhvtl **disagree about what the device
did**; any disagreement means one of the three is wrong, and that is the finding. This is the only
experiment in the programme that extracts signal about mhvtl from mhvtl.

### What mhvtl validates, and what it does not

**Validates:** command grammar and framing; positioning arithmetic; the changer state machine; the
volume and session label bytes (the entire §5 disclosure contract, at byte level); the
bootstrap-record synthesis and catalogue-free read; `bscan` round-trip and `VolSessionId`/
`VolSessionTime` survival; our recovery logic; Bareos configuration behaviour under contention;
Persistent Reserve semantics (present in `usr/spc.c`, so the fencing question is at least
*shaped* on the rig even though we do not use PR in production); programmable early warning as a
settable value; WORM mode-page behaviour.

**Does not validate, and cannot:** deferred write errors (sense response 71h/73h attributed to no
command); `pos_unknown` after a bus reset; real backhitch and shoe-shining; **WORM *firmware*
enforcement** as opposed to an emulator flag; vendor-specific sense; the achievable `PEWS` maximum
on the procured drive; `WRITE ATTRIBUTE` (undispatched in mhvtl); the LTO-9/10 first-load media
initialisation (40 min–2 h, which exceeds every Bareos timeout); and — most importantly — **anything
about time**. mhvtl has no tape; it has a file. **No number from this rig belongs in the cost
model.** `A-2` ("every tape `estWall` is a declared guess until measured") is untouched by everything
above, and every `estWall` stays `basis: MODELLED` until real hardware.

**Is mhvtl-alone-against-our-own-SCSI the better rig?** It would test more of the twenty-row risk
register — but under this decision we are not writing the code those rows describe, so there is
nothing to test. The comparison is moot, and that is itself a mark in favour of the decision: a rig
is worth what it tests of the thing we will keep, and behind Bareos it exercises our scheduler, our
locator, our staging, our ledger, our disclosure contract and our reconciliation against an
independently written initiator that does not share our reading of the SCSI spec.

**The hardware gate is unchanged.** No WORM cartridge is written until a real drive passes on
rewritable media, with an independently written reference reader opening the result **on a different
drive**.

---

## 10. Rig checklist — what must be true before we commit

Each is a falsifiable statement. A **NO** on R-1, R-2 or R-8 re-opens the decision.

| | Statement | Kills |
|---|---|---|
| **R-1** | A job can be bound to one named cartridge non-racily via one Pool with one Media row, `Maximum Volumes = 1` and `Maximum Volume Jobs` unset; and with the target volume set `Used`, `Full`, `Error` and absent in turn, **the job fails rather than improvising** (no Scratch pull, no auto-label, no recycle). | the whole mapping |
| **R-2** | `bls -v` and a `bextract` of every file record on a written cartridge, diffed against a literal allowlist, show **no field we did not intend** — and `HostName`, the `Job` date string, `write_btime`, `PrevVolumeName` and the 13 `stat` fields read exactly as §5 predicts. | the disclosure contract |
| **R-3** | A bootstrap record synthesised **from our own session-join record alone**, with the Bareos catalogue dropped entirely, restores the fragment via `bextract`; every parcel rehashes; the Merkle root matches. | tier-2 independence |
| **R-4** | `bscan` into an empty catalogue preserves `VolSessionId` and `VolSessionTime` **exactly**, while renumbering `JobId`. | the locator keying rule |
| **R-5** | A WORM cartridge labels correctly on this Bareos version, in one write, and a second label attempt is refused by the drive rather than wedging the cartridge. | WORM operation |
| **R-6** | With compression off and CSPRNG padding, media bytes consumed per fragment are deterministic and equal to `96 × PARCEL_BYTES` plus framing, across ten fragments. | capacity accounting |
| **R-7** | `VolSessionTime` is identical in every block header and every session label written by one SD run, and changes only when the SD restarts. | confirms C-1 |
| **R-8** | With our own `Changer Command`, three simultaneous mounts on three drives from three distinct cartridges reach STREAMING in **materially less** than three times the single-mount wall clock. | the third drive per site |
| **R-9** | Inter-job dead time at queue depth 1 — from job *N* reaching `T` to job *N+1* issuing its first robot command — is small relative to a mount. | zero-depth queueing |
| **R-10** | Three jobs submitted at once against three Storage resources actually run at once (`status director`), with all four concurrency counters raised. | the concurrency config |
| **R-11** | Staging write amplification and throughput through the FD→SD socket at the parcel rate are within budget, with `Spool Data` explicitly decided and measured both ways. | A-1 / the licence tax |
| **R-12** | `configure add` of the 250th Pool plus a Director reload is safe **while a multi-hour job is running**. | cartridge commissioning |
| **R-13** | A cartridge this Director never wrote can be adopted — volume registration through `bconsole`, `update slots`, then a bootstrap-record restore — **without `label`**, and without a second changer initiator. | export/import (S-26) |
| **R-14** | `gfs-probe` can issue `LOG SENSE` 0x31, `MODE SENSE`, `SECURITY PROTOCOL IN` and `READ`/`WRITE ATTRIBUTE` on `/dev/sg*` **between jobs**, and receives valid data; and TapeAlert flags reach exactly one consumer. | G-5, G-7, F-M |
| **R-15** | Killing `bareos-sd` mid-job leaves a state our adapter classifies correctly: either locators exist and verify, or the fragment does not exist and its media is charged as dead tape. **Zero unaccounted bytes.** | F-A |
| **R-16** | A read failure at a known position is attributed to exactly one parcel ordinal by Merkle leaf, independent of anything Bareos reports. | G-5 |

---

## 11. Open questions for the owner

1. **Sign-off on A-β.** Second-resolution commit time per fragment, permanent, on unerasable media,
   in binary and as an ASCII date. This waives a condition previously declared non-negotiable. It is
   a governance decision, not an engineering one, and it must be recorded before the first WORM
   cartridge. The same decision applies to LTFS, so taking it once settles both.
2. **The LTFS addendum.** `TAPE-RESEARCH-PROMPT.md` (2026-09-19) recommends reversing the LTFS
   rejection, for the same reason that carries most weight here — a standard discharges the
   format-and-reader obligation. Bareos discharges it too, and more cheaply, because it needs no
   vendor LE extension to work on WORM and no stale-until-eject index. **If Bareos is adopted, the
   LTFS addendum should be closed as superseded**, with LTFS retained only as `Step 7`'s on-demand
   export conversion. That should be stated explicitly rather than left as two live recommendations.
3. **Single-host-per-changer.** G-1 makes it a deployment rule. If any site will ever have two hosts
   on one fabric, the STONITH procedure is owed now.
4. **Counsel, on the three licensing questions in §6**, before deployment and before the first
   export — not before the rig.

---

## 12. Normative corrections to the dependent documents

- `STORAGE-BINDINGS-DECISION.md` §3/§4: **`append` returning a provisional ref with its real address
  is superseded** by `SPECIFICATION.md` §1.2(1). The locator is discovered at the barrier. F-8's
  resolution changes accordingly.
- `STORAGE-BINDINGS-DECISION.md` §8 row 1: the 4 KiB plaintext symbol header carrying *extent id*,
  *payload hash* and *write epoch* is **superseded** by `SPECIFICATION.md` **§7.1's** 24 cleartext bytes per parcel (`magic "STELE\0\2" | parcel ordinal u32 | flags u8 | crc32`), cross-referenced to §13.2's permanence inventory *(citation corrected 2026-09-19: there is no §5.5)*.
  The superseded form carries the confirmation-oracle defect of §5 condition 1 in our *own* format,
  and it is the reason that correction is mover-independent.
- `STORAGE-BINDINGS-DECISION.md` §1, §8 row 20, §10 Step 5 and Step 6: **`gfs-mover` is deleted**,
  along with rows 2–9, 11, 15, 16 and 20, which become *configure and assert*. Step 5 and Step 6 are
  replaced by §9 above. `gfs-probe` and its five-opcode allowlist replace the fourteen-opcode one.
- `STORAGE-BINDINGS-DECISION.md` §10 Step 4: the fault injector moves from inside `SimTapeBinding`
  to the `VolumeMover` boundary.
- `TAPE-RESEARCH-PROMPT.md` Addendum: see §11.2.

**Added 2026-09-19, from the cross-document coherence pass — corrections this list did not previously carry:**

- `STORAGE-BINDINGS-DECISION.md` **§6 fencing item 1** was missed entirely by this list. It rests the
  whole fencing hierarchy on SCSI Persistent Reserve, which §1 here makes unreachable and
  `SPECIFICATION.md` §2.3 lists under *Deleted outright*, and items 2–4 are all keyed to it.
  Authority becomes operational — one changer initiator (`bareos-sd`, F-C) and one submitter to the
  Director — and **multi-host fencing becomes an open hole** (§11.3 above says the STONITH procedure
  "is owed now"; it exists in no document).
- `SPECIFICATION.md` **§5.2 and the §17 conformance checklist** both still said "`append` returns the
  real ordinal immediately", contradicting this document's §2 barrier and that document's own §1.2(1)
  and §4. The correction above was aimed only at `STORAGE-BINDINGS-DECISION.md` §3/§4 and missed that
  `SPECIFICATION.md` carries the same construct in its own normative SPI. Corrected there.
- `STORAGE-BINDINGS-DECISION.md` **§8 row 15's `commission(barcode)`** is deleted with `gfs-mover`,
  which leaves `SPECIFICATION.md` §5.4's **WORM-status-at-commissioning read unassigned**. Bareos
  commissioning is `label barcodes` and reads no WORM status; `gfs-probe`'s `MODE SENSE` makes the
  read possible but nothing owns it.
- **Citations into `SPECIFICATION.md` §5.5, §5.6 and §5.7 were phantoms** — that document's §5
  contains only §5.1–§5.4. All four such citations in this file are retargeted above (§2.3 + §15,
  §7.1, §6.1, §3.1/§3.2).
- **"STELE's eleven block-plane calls" was wrong**; there are ten. Corrected in §2.


---

## 13. The disclosure inventory, read from source (2026-09-19)

Verified against `bareos/bareos` cloned on a DGX node, `core/src/stored/label.cc`. **The disclosure
is materially larger than §3's G-8 stated**, which named only commit time. `CreateVolumeLabel` and
the session label together serialise the following *in the clear* onto the medium.

**Volume label, once per volume** — `label.cc:481-504`:

| field | line | controllable? |
|---|---|---|
| `Id`, `VerNum` | 481, 483 | no — Bareos's own format identity |
| **`label_btime`** | 487 | **no** |
| **`write_btime`** | 489 | **no** |
| `VolumeName`, `PrevVolumeName` | 495-496 | **yes** — make opaque |
| `PoolName`, `PoolType`, `MediaType` | 497-499 | **yes** — make opaque |
| **`HostName`** | 501 | partly — the writing host's name; settable per deployment |
| `LabelProg`, `ProgVersion`, `ProgDate` | 502-504 | no — Bareos's identity and build date |

**Session label, once per job session** — `label.cc:575-604`:

| field | line | controllable? |
|---|---|---|
| `BareosId`, `BareosTapeVersion` | 575-576 | no |
| `JobId` | 579 | no — a monotonic counter, leaks ordering and volume |
| **commit time** `SerBtime(GetCurrentBtime())` | 582 | **no** |
| `pool_name`, `pool_type` | 585-586 | yes — make opaque |
| `job_name` (base) | 587 | yes — make opaque |
| **`client_name`** | 588 | yes — **but see below** |
| `jcr->Job` — composed with `%Y-%m-%d_%H.%M.%S` (`dird/job.cc:1506`) | 591 | no — carries a second timestamp |
| **`fileset_name`** | 592 | yes — make opaque |
| `JobType`, `JobLevel` | 593-594 | no |
| **`fileset_md5`** | 596 | no — a digest of the fileset definition |
| `JobFiles`, `JobBytes`, Start/End Block, Start/End File | 599-604 | no — leaks parcel count and volume shape |

**This applies to file devices identically.** `WriteNewVolumeLabelToDev` calls `CreateVolumeLabel`
unconditionally (`label.cc:388`); the `IsTape()` branches at 348 and 361 concern open mode and
rewind, not label content. So a file-backed rig reproduces the on-media disclosure exactly, and the
question is testable without tape hardware.

### What this changes

The mitigable fields are all *strings we choose* — volume, pool, job, fileset and client names — and
the four LTFS-era conditions apply unchanged: make them opaque, content-addressed, carrying no
dataset, project, subject, modality or institution.

**`client_name` is the one that escalates this from a privacy nuisance to a governance problem.** In
a federation of independent institutions under a data-use agreement, the client is the *contributing
institution*. Written in the clear to unerasable media, it is permanent institutional attribution
that survives every crypto-shred — the fact that institution X contributed to this cartridge cannot
be withdrawn. It must be opaque from the first label written, because a cartridge labelled otherwise
is not correctable.

**The irreducible residue, after every mitigation:**

1. `label_btime` and `write_btime` on each volume;
2. a commit timestamp in every session label, plus a second inside `jcr->Job`;
3. `HostName` of the writing host (reducible to an opaque name by deployment, not by configuration);
4. Bareos's own version and build date;
5. `fileset_md5`, a digest of the fileset definition;
6. `JobFiles`, `JobBytes` and block extents — the parcel count and shape of each write.

Items 1, 2 and 6 are the ones that matter. Fixed-size padded parcels quantise 6 to little. **Nothing
reduces 1 and 2**: commit time reaches WORM in the clear, correlates with acquisition time for
clinical data, and survives the erasure it documents. That is the sign-off, and it is now specified
precisely enough to be signed off or refused.
