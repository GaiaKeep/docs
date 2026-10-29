!!! success "Status: Current"
    Erasure coding (ec:2+1, the default for new collections since 2026-10-14), replicas and a single copy, with tape as the primary tier: the design, its milestones and what is built.

# Durability modes: erasure coding, replicas and a single copy, with tape as the primary tier

*Design of 2026-10-02 (branch `wip/durability-modes`, merged into 1.3). It implements the owner's answers of
2026-10-02 (docs/OWNER-ANSWERS-2026-10-02.md): R1/R2/R5/R6, N-DC11, P3/P4, D3, A4, A8 and the standing
rules. It covers OUT-48 (erasure coding by repack) and OUT-91 (tape is the primary durable tier).*

*Status, 2026-10-14 (branch `fix/ec-default`). **`ec:2+1` is the default** (`core_default_redundancy`, and the
built-in `radiology-dicom` and `pathology-wsi` profiles); `replicas:R` and `single` stay per-dataset choices. Built:
N-DC11 (section 2.2); MS1 to MS5 (sections 12, the "done" notes), now including the MS5 integration matrix cells, the
mixed-mode dedup and migration cells, the model and linearizability tests with modes, and an end-to-end cluster test
through the core service (`EcDefaultClusterTest`); the deep scrub on the maintenance scheduler (MS4); the MS7 crash
matrix scenarios for every erasure-coding fault point and for encode on write (section 12, MS7); and, with tape as the
primary tier, the spool pump archiving each failure domain's share (section 9.5), so an `ec` version commits on
VERIFIED like a replicated one. MS6 in part (e70b50a and after): with `core_place_on_deferred=true` placement targets
tape, a VERIFIED tape copy counts, and a durable version commits on VERIFIED (`core_commit_verified`; section 9.4); the
standing HPC deployment runs it. Existing collections keep the mode they were created with: nothing is re-encoded on
upgrade (section 10). Not built: the test-bed decisions (sections 11 and 12, among them E-DM1 and CodecBench on the
HPC), the rest of MS6, and MS7's rebuild of a lost site from tape alone (OUT-101).
Section 13 lists what I am unsure of; 13a what the owner resolved.*

## 0. Summary

- **Three modes, chosen per dataset.** `ec:2+1` (Reed-Solomon RS(2,1), the default for durable data),
  `replicas:R` (R ≥ 2 full copies) and `single` (one copy, only for the `scratch` and `cache` classes).
  Each collection and profile records its mode. A block meets the strongest requirement among the
  collections that reference it.
- **One dedup block is one stripe** (decision DM-1). A block's ciphertext is split into `k` data shares
  and `m` parity shares, one per failure domain. No stripe spans two blocks, so every lifecycle
  operation (gc, forget, deep delete, withdrawal, repack) stays per block, as D3 requires. Repack never
  needs another site. The cost is that a healthy read needs `k` sites, which on tape means `k`
  mounts per small recall instead of one. The tape simulator decides whether that cost is acceptable
  (experiment E-DM1). If it is not, the fallback (DM-1b) is coarse stripes that are re-formed at repack.
- **Encrypt, then encode.** Shares are slices and parity of the sealed block ciphertext (`BlockCodec`).
  No storage node, repair, re-encode or scrub ever needs a key. The block's AEAD tag is checked after
  the shares are reassembled.
- **Encoding has two paths and one share format.** On write, `publish` encodes each block and places its
  shares. In the background, a re-encode job converts blocks between modes. That job is the migration
  path and is the OUT-48 "EC by repack" job. The test bed decides whether new writes encode on write
  or land as replicas first.
- **Durability is counted per failure domain, not per copy.** A block's protection is `f`, the number of
  whole-site losses it survives. Disk and tape copies count. RAM never counts (A4), even when attested.
  A live-tier copy (the HPC cluster) never counts (P3/P4). A tape share counts once its container is VERIFIED.
- **The work is bottom-up**, in milestones MS1-MS7: codec, then records and policy, then the engine's read
  path, maintenance, write paths, tape counting, and finally system tests. Each has its own unit,
  component and integration tests (section 12). MS0 (N-DC11) is done; MS8 is later work.

## 1. The owner's decisions this implements

| Id | Decision (2026-10-02 unless noted) | Consequence here |
|---|---|---|
| R1/R2/R5/R6 | Phase one is three identical sites. The default redundancy is erasure coding across them (RS(2,1)-style, 1.5x, survives the loss of any one site). Durability is a per-dataset policy. All three modes (erasure-coded, three full replicas, single copy) must be supported and tested. | Sections 3 to 6 and 12 |
| N-DC11 | R ≥ 2 for anything durable; R = 1 only for scratch or cache classes | Enforced on this branch (2.2); restated as `f ≥ 1` (3.2) |
| P3/P4 | Tape is primary, not backup. The durable tier alone must recreate any dataset and survive the loss of a whole site. The HPC cluster copy is uncontrolled cache, never counted. | Sections 8 and 9 |
| D3 | The atomic repack unit is the dedup block, never finer | Section 4 (DM-1) |
| D4 | A rewrite is a bit-identical move, or it uses a fresh epoch key; never a mix | Shares move bit-identically (4.4) |
| A4 | RAM never counts toward durability; it is a distinct, vanishing residency | Section 8 |
| A8 | Refuse by default when a policy is unsatisfiable; the plan is accepted before bytes stream | Placement refuses (6.1); writing under-protected is opt-in debt |
| D2 | Group data that dies together onto the same cartridge (retention cohorts) | Tape containers are cohort-pure (9.2) |
| Standing | Expensive tunables are decided by the test bed; build bottom-up | Sections 11 and 12 |

## 2. What is built today

### 2.1 The engine (replication only)

Facts from `StorageEngine`, `ReplicaPlacer`, `RefIndex` and `CompactBlockTable` at `486d774`, before MS6. The tape
bullets describe `core_place_on_deferred=false`; the last bullet says what MS6 changed:

- **Policy.** A collection has `replication` (R, 1-255) and `durability` (`durable` or `cache`).
  A block's requirement is `desired`, a byte in its `BlockTable` record. It is the maximum R over
  everything that ever referenced the block. It is monotone: `raiseDesired` only raises it. Derived
  versions add floors that are computed per pass (`Floors`, OUT-34).
- **Placement** (`ReplicaPlacer`). Hard constraints come first: the site is up and ACTIVE, not excluded,
  not full, and has shown durability (`LocusDescriptor.countsTowardDurability()`: the barrier
  measurably costs time, or the locus is attested). Copies go to distinct failure domains. Choice among
  the admissible sites is rendezvous hashing on the block id, weighted by log10 of the measured write
  rate. A locus with deferred reads or writes (tape) is excluded unless `allowDeferred` is set, which
  only `core.archive` sets. An unsatisfiable request throws `Unsatisfiable` with the refusal counts.
- **Publish** writes R identical ciphertext copies per block. Publishes of at least 8 MiB use a chain
  (the writer sends once and the members forward); smaller ones use a star. It journals an intent before any
  seal, and commits the version only after every copy is sealed.
- **Repair** (`repairInternal`) counts the copies on up, ACTIVE, non-deferred sites, plus those within
  the presume-down grace. A deficit is filled from a verified source onto new failure domains.
  `placeFewer` places what the free domains allow. **Tape copies are never counted, never a source and
  never re-made.**
- **Trim** removes surplus copies after a grace period. It keeps distinct domains first, then the
  fastest sites. A tape copy is never surplus.
- **Scrub** verifies each copy's content digest at its site. Bad copies are kept, uncounted, until
  enough verified copies exist.
- **Census** counts copies per **site** (`upActive < want`), not per failure domain. Archive copies are
  counted separately.
- **declareLost** refuses when a live block would be left with no readable copy. A tape-only survivor is
  "not readable now" and never makes the loss safe.
- **core.archive** copies a collection's live blocks to a tape locus. These copies are additional to R
  and never counted (P3/P4 as built; `ReplicaPlacer.Request.allowDeferred`, the
  `core_place_on_deferred` row in DEFAULT-POLICIES.md).
- **Tape** (`TapeBinding`, `TapeCatalog`). Containers are 1 GiB parcels and LTO-10 only.
  `tape_write_verify FULL` (the default) reads every container back before it is VERIFIED. Under
  SAMPLED or NONE, a container that is not read back is SYNCED, and its copies are reported as
  `PRESENT_CLAIMED`, never verified.
- **Since MS6 (e70b50a, 2026-10-03), with `core_place_on_deferred=true`:** placement may target tape; the spool pump
  (`tapePumpSweep`, a leader job sweep, also kicked at a publish) mirrors every durable collection's blocks to its
  sites' tape through incremental archive runs (scratch and cache classes are never pumped; since 70e3676 it walks
  only versions past each site's watermark, since 2026-10-07 in bounded slices under a core-wide budget, one run per
  tape site); the census counts a landed tape copy toward the block's requirement and reports a tape-only block as
  staged-readable, not unavailable. With `core_commit_verified` (default true) a durable version is readable only once
  every block has a VERIFIED tape copy at its site (9.4). Still as above: trim never removes a tape copy, and repair
  takes no source from tape.

### 2.2 N-DC11, enforced on this branch

Before this branch, a durable collection already needed R ≥ 2 (`R_DURABLE_REPLICATION`, OUT-41). R = 1 was
admitted for `durability=cache`, but in any retention class, including `standard` (kept for ever) or
a class with a floor or a legal hold. That is a durable promise made with one copy. Now:

- **One copy needs a cache in a single-copy class.** `PolicyEngine.createCollection` refuses R = 1 unless
  the durability is `cache` **and** the retention class is `scratch` or `cache`
  (`Collection.SINGLE_COPY_CLASSES`, rule `single-copy-scratch-or-cache`). The message names the fix.
- **Profiles follow the same rule.** `Profile.of` (`core.profile op=create`) refuses a single-copy profile
  outside those classes. The built-in `scratch-cache` profile (R = 1, cache, class `scratch`) already
  complies.
- **Changing the class.** `LifecycleEngine.assignClass` and a `RETENTION_OVERRIDE` proposal both refuse to
  move a one-copy collection into any other class (`PolicyEngine.checkClassChange`). This holds even
  when the move strengthens retention. No other path changes a collection's copies or durability after
  creation.
- **Replay is unchanged.** `restoreCollection` and `Profile.fromRecord` do not re-apply the rule, so a
  journal written before it still replays, which is the engine's standing rule.

## 3. The three modes as per-dataset policy

### 3.1 The policy value

A collection's **redundancy** is one of:

| Mode | Spelling | Shares per block | Overhead | Site losses survived (`f`) | Who may use it |
|---|---|---|---|---|---|
| Erasure-coded | `ec:k+m`, phase one `ec:2+1` | `k + m`, one per failure domain | `(k+m)/k`, 1.5x | `m` | durable (the default) or cache |
| Replicas | `replicas:R`, R ≥ 2 | R full copies, one per domain | Rx | `R − 1` | durable or cache |
| Single copy | `single` | 1 | 1x | 0 | cache in class `scratch` or `cache` only (N-DC11) |

`f` is the policy's promise: losing any `f` whole failure domains leaves every block readable. N-DC11
in these terms is **durable ⇒ f ≥ 1**. The existing `replication` parameter stays as an alias:
`replication=R` means `replicas:R`, and `replication=1` means `single`. Today's journals and clients
are therefore unchanged.

- **The default.** A new collection that names no redundancy (nor `replication`) gets `core_default_redundancy`,
  **`ec:2+1`** since 2026-10-14 (it was `replicas:3` until encode on write was proven end to end). Rules in effect:
  - A deployment with fewer than three failure domains cannot place `ec:2+1`: a write of a block that needs a share
    per domain is refused (A8, `too-few-failure-domains`), never silently downgraded. The collection is still created
    `ec:2+1`; such a fabric names `redundancy` per collection (`replicas:2`) or sets the key. (A block under
    `core_ec_min_block_bytes` keeps m+1 = 2 full copies and needs two domains.)
  - With a domain only *down* (not missing), the write continues with fewer shares as recorded debt that repair pays
    (`core_place_min_shares`, default -1: as `core_place_min_copies`; never fewer than k). This is the owner's first
    question of 2026-10-07, built as recommended and the default in effect.
  - While `core_api_deltas` is off (a rolling upgrade from a build older than the ec deltas, OPERATIONS §13), an `ec`
    default resolves to `replicas:3` (`CoreService.UPGRADE_DEFAULT`), what every earlier build gave, and the reply's
    `redundancy` names it: an ec collection journals `colRedundancy`, which such a peer cannot apply. Collections made
    in that window stay `replicas:3` until a `core.redundancy op=set` moves them. An explicit `redundancy=ec:2+1` is
    refused in the window (status 7, `redundancy-needs-api-deltas`).
- **Recording.** The mode is a new journaled delta, `colRedundancy [collection, spelling]`, written in the
  same batch as the `collection` delta. The `collection` delta stays byte-identical, so existing
  journals and their hashes are unchanged. A collection without the delta is `replicas:R` (or `single`
  at R = 1). Profiles record a new `redundancy` key in their record JSON, and a record without it means
  `replicas:<replication>`.
- **Changing the mode.** `core.redundancy op=set` is journaled. It is refused when it would take a durable
  collection below `f = 1`. It raises or lowers block requirements, and the re-encode job (5.2) does
  the work. Every change is a change of policy, never an in-place relabel of stored shares.
- **Built-in profiles.** `radiology-dicom` and `pathology-wsi` are `ec:2+1` since 2026-10-14 (owner, 13a; their
  records carry `replication` 2, the full-copy form, and `redundancy` ec:2+1). Existing collections keep the record
  they were created with (`collProfile`), so those made under the three-copy records stay `replicas:3`. (A profiled collection journals `collProfile`, a wave-2
  delta, so profiles are refused while `core_api_deltas` is off, as before.)

### 3.2 A block referenced by collections in different modes

Deduplication means one block can serve collections in different modes, such as a GLOBAL public block
or a GROUP domain. The block meets the strongest requirement, under a total order:

```
single  <  ec:2+1  <  replicas:2  <  replicas:3  <  ...
order by (f, full copies wanted): equal f, a collection that asked for full copies gets them
```

`ec:2+1` and `replicas:2` both give `f = 1`. A collection that asked for full copies (for example, for
one-site reads) pays for them and gets them. Phase one has one erasure code, so `ec:k+m` with
different `k` never has to be compared. When R7 adds a second code, the order is extended explicitly.

**What changes in the engine.** `desired` is monotone today. Lowering a requirement, as when a
collection moves from `replicas:3` to `ec:2+1` or when the only `replicas:3` referencer is forgotten,
needs the requirement to be **recomputed** from the live referencing collections. The engine already
does this for derived versions (`Floors`). The block record keeps the last computed requirement, and a
policy change bumps an epoch that triggers recomputation, as `floorsEpoch` does now.

*As built:* a mode change recomputes by its own delta (`colRedundancySet`); a referencer withdrawn or dropped lowers
nothing by itself, and trim lowers it only with `core_lower_on_drop` (default off), by a journaled `reqLower`
(MS5 status, 2026-10-15).

## 4. How an EC stripe maps onto dedup blocks

### 4.1 Decision DM-1: one dedup block is one stripe

```
C      = BlockCodec ciphertext of one dedup block (AEAD sealed; |C| = plaintext + 16)
L      = ceil(|C| / k)
D_0..D_{k-1} = C ‖ zero pad to k·L, cut into k slices of L bytes      (data shares; systematic)
P_0..P_{m-1} = RS(k,m) parity over D                                   (parity shares)
share i     → a distinct failure domain; extent id = extentId(domain, block) + "_s" + i
```

The padding is never stored as such. Decoding trims to `|C|`, which follows from the block record's
length and the codec's fixed overhead. The extent id stays within the 128-character store limit:
`b_` + a token of at most 16 + `_` + a 96-character keyed id + `_s` + 3 digits is at most 120 (as built: `_s`,
not `~s`, because every store accepts only `[A-Za-z0-9_-]` in an extent id).

**Why DM-1:**

1. **D3 holds by construction.** Every operation that decides liveness or moves bytes decides per dedup
   block: reference counting, gc, forget, withdrawal (PIN, COPY or BREAK), deep delete and repack. No
   stripe ties a dead block to a live one, so nothing is retained for a neighbour's parity. Nothing is
   re-encoded because another block died.
2. **Repack is local to a site.** A site's tape volume holds share `i` of many blocks. Repacking it copies
   the live share records bit-identically (D4) into new containers. No other site is mounted and no
   bytes cross the WAN. Under stripes that span blocks or containers, every repack would have to
   re-form stripes across all three sites.
3. **Tenancy isolation needs no rule.** A block's shares depend only on that block, so a sealed tenant's
   data is never parity for anyone else's. A domain-pure container stays domain-pure.
4. **It fits the engine as built.** The `RefIndex` key, placement, repair, trim, scrub, intents and
   landing are all per block today. "A copy" becomes "a share (full, or index `i`)". Encode-on-write
   needs no accumulation buffer, no stripe-formation latency and no `seal_deadline`. That suits the
   streaming ingest (parts processed as they land).

**What it costs (stated plainly):**

- **No DIRECT read.** SPECIFICATION §8.3 called the one-site, one-mount DIRECT read "the single largest
  cost saving in the design". Under DM-1, every healthy read fetches `k` = 2 shares from 2 sites. On
  disk, that puts about half the block on the WAN for every read. On tape, it means **two mounts per
  small recall instead of one** (the drive-seconds roughly double for recalls far below a parcel). For
  large sequential restores the drive-seconds are about equal, because each site reads half, and the
  two sites stream in parallel.
- **More records.** Each block becomes `k + m` records, each about `|C|/k` bytes. At the 1 MiB CDC target,
  each share is about 512 KiB, which is fine. At small blocks (format adapters emit kilobyte-sized
  header blocks), the per-record overhead dominates. The small-block rule (4.3) handles that.
- **Repair amplification.** Rebuilding one share reads `k` shares, about one block's worth.

### 4.2 The alternative kept open: DM-1b (stripes re-formed at repack)

Stripes over whole blocks, or over whole containers (1 GiB parcels), as in SPECIFICATION §3 and §8. The
data shares are whole blocks or containers stored at one site, so DIRECT reads return. D3 can still be
honoured, because repack decides per block and re-forms new stripes from the live blocks. The price:

- A dead block's bytes stay until its stripe is re-formed.
- Repack, forget and deep delete need cross-site re-encoding: WAN bytes, and mounts at every member site.
- Cohort and domain purity becomes a placement rule rather than a property.
- A stripe table is needed: stripe → members, and block → stripe.

**Experiment E-DM1 decides between them.** It runs on the tape simulator (TAPE-SIMULATION.md, LTO-10
profile, three sites, several drives and cartridges) using the P2 fixtures (very many small files;
bulk). It measures drive-seconds and mounts per recall, per whole-dataset restore and per repack, plus
WAN bytes per read, for DM-1, DM-1b and `replicas:3`. DM-1 is built first because everything in MS1-MS5
carries over to DM-1b: the codec, the share format, survivability and the policy. Only the mapping and
the stripe table would change.

### 4.3 Small blocks

A block below `ec_min_block_bytes` is stored as `replicas:(m+1)` instead of being coded. For `ec:2+1` that
means two full copies: the same `f = 1`, at 2x on a few kilobytes rather than three records of a few
bytes each. The block's record says which form it took. Provisional value: 64 KiB. **Test bed:** per-record
overhead on disk and tape (PACK-FORMAT §12 measured 0.88 % at 64 KiB extents), against the share of
corpus bytes held in small blocks for the P2 fixtures.

### 4.4 Integrity without per-share digests in the index

- **At the site, without a key.** Each share is appended with its own SHA-256, as copies are today
  (`ExtentBinding.append(..., sha256)`), and the container record carries a SHA-384. Scrub verifies
  each share where it lies.
- **End to end.** Reassembled shares must open under the block's AEAD (`BlockCodec.open`). A wrong share
  fails the tag. With more than `k` shares available, the reader tries other `k`-subsets (three at
  most for RS(2,1)), finds the bad share, marks it bad (E4) and reports it.
- **Nothing is added to the index.** Storing `k + m` digests in the `BlockTable` would cost about 96 bytes
  more per record, more than doubling today's 75. The site digest plus the AEAD give the same
  detection.

## 5. Where encoding happens

### 5.1 On write

`store()` encodes each block once and places share `i` on the domain chosen for index `i`. The
placement request becomes indexed (5.3). Each share goes to its own site (a star of shares). The
writer sends `(k+m)/k` = 1.5x the block, where the replicated chain sends 1x and the replicated star
sends Rx. A chain variant is possible: forward `C` and let each member derive its own share. That
needs no key, but it puts the encoding on the storage nodes and sends the whole block over every hop,
so it is a test-bed variant, not the default.

### 5.2 By the re-encode job

A background job converts a block between forms. Its steps are the repair path:

1. Fetch one verified full copy, or any `k` verified shares.
2. Decode and encode as needed.
3. Write the missing shares under an intent, and land them.
4. Trim the old form, but only once the new form meets the requirement.

It serves:

- **migration** of existing replicated data (section 10);
- **mode changes** (`core.redundancy op=set`) in either direction;
- **GLOBAL and dedup promotions**, when a block gains a referencer that wants full copies;
- an optional **land-then-encode** ingest policy: write `replicas:2` (f = 1 at commit), encode later.

It is sliced and throttled like repair and trim (`Slice`, `Throttle`), resumable by cursor, and crash
safe through intents and fault points (`FaultPoints.REENCODE_*`).

### 5.3 Which is the default for new writes

Provisional: **encode on write** for `ec` collections. It writes the fewest bytes everywhere: 1.5x,
against 2x landing + 1.5x encoding + reclaiming 2x under land-then-encode. It is never less protected
at commit (f = 1 either way). **Test bed:** ingest MB/s per client at 80 ms RTT against the N-WAN target
(150 MB/s), WAN bytes per committed byte, spool write amplification, and time until the version is
VERIFIED on tape.

Placement for shares extends `ReplicaPlacer.Request` with `shares = k + m` and an index per target, and
keeps the same hard constraints and rendezvous weighting. Share `i` goes to the `i`-th site in
rendezvous order, so roles rotate across blocks (SPECIFICATION §8.2), and read and degraded-mode load
spread evenly.

## 6. Behaviour per mode

### 6.1 Write

| | replicas:R | ec:k+m | single |
|---|---|---|---|
| Shares placed | R full copies, distinct domains | `k + m` shares, distinct domains, by index | 1 full copy |
| Commit | every copy sealed | every share sealed | the copy sealed |
| Too few domains | refused (A8) | refused (A8) | refused if no admissible site |

Writing under-protected (fewer domains than the mode needs) is never the default (A8). It is an
explicit caller opt-in that records a visible debt, which repair pays down. With `ec:2+1`, two of three
shares can be decoded but survive no loss, so that is debt, not durability.

### 6.2 Read

| | replicas:R | ec:k+m | single |
|---|---|---|---|
| Healthy | one copy, best first, one hedge (today) | the `k` data shares, concatenated; no decode | the copy |
| Degraded | the next copy | any `k` shares, decode | refused: `DataUnavailable`, never wrong bytes |
| Bad share | skipped and reported | subset retry isolates it (4.4) | detected by AEAD, refused |
| Tape only | staged, never a mount on a user read (today) | the same, `k` sites staged in parallel | the same |

Hedging on disk asks for one extra share when the slowest of the `k` is late (`k + 1` in flight at most).
**There is no hedging on tape**: a cancelled tape read still costs the mount (SPECIFICATION §8.5). The
planner picks the `k` shares deterministically: mounted volumes first, then queue depth, then WAN cost.

### 6.3 Repair

| | replicas:R | ec:k+m | single |
|---|---|---|---|
| Deficit | `R − counted copies` | missing indices among counted shares | none: nothing to repair from |
| Source | one verified copy | any `k` verified shares (or one full copy) | — |
| Work | copy | decode, re-encode the missing indices | report the lost or bad copy |
| Target | a free failure domain | a free domain, one per index | — |

A single-copy block whose copy is lost or bad is reported. Its owner regenerates it, because it is a
cache, and repair never adds a second copy. Tape-resident shares are repaired **only on positive
evidence**: a failed read check, a TapeAlert or a scrub result. Absence or a timeout is never enough,
because a 265-1,400 s medium reads every transient as a loss (SPECIFICATION §8.6). Repair from tape is a
staged, budgeted job (drive-seconds and WAN bytes), never inline.

### 6.4 Trim, scrub, gc and forget

- **Trim** counts per failure domain. The surplus is: a second share of the same index; full copies of an
  `ec` block once its shares meet the requirement at VERIFIED or sealed state; replicas beyond R; and,
  once tape counts, disk shares whose tape share in the same domain is VERIFIED. That last case is
  evicted by spool pressure, not by trim (9.3).
- **Scrub** verifies every share's digest at its site. A **deep scrub** of `ec` blocks fetches all `k + m`
  shares and recomputes the parity, under a budget and at a cadence the test bed sets. Tape scrub is
  `core.archiveverify` (today).
- **gc and forget** act on the block, so every share goes together. QUICK DELETE (key destruction) is
  unchanged, because shares are ciphertext. DEEP DELETE forces reclamation of every container holding a
  share of the block, which on tape means a repack of those volumes. That repack is local to each site
  under DM-1.

### 6.5 Site loss, drain and restore

- **declareLost** counts per block whether the survivors still decode: a full copy, or at least `k`
  distinct indices. It refuses when they do not, as today. With tape counted, a block whose surviving
  shares are on tape is **recoverable, not lost**. The refusal therefore separates "no survivor"
  (refused) from "survivors on tape only". The second is allowed with a staged repair plan and its
  drive-second estimate attached.
- **drain** moves each share to a free domain and keeps its index. **restore** (DEFAULT-POLICIES, decision
  M3) is unchanged: a restored site returns LOST and holds nothing the index forgot.
- **Rebuilding a whole site (R5)** under `ec:2+1` reads `k` = 2 shares per lost share, about 1x of the
  lost site's payload from each of the two survivors. Under `replicas:3` it reads 1x from one survivor.
  The test bed prices this (repair window, R9 is still open).

## 7. Recording shares in the RefIndex and BlockTable

| Today | With modes |
|---|---|
| `BlockRecord.sites`: the sites holding a copy | each entry also carries its **share index**: `FULL`, or `0..k+m−1` |
| `BlockRecord.desired`: copies wanted (byte, monotone) | `desired` keeps its meaning for replicas; a new byte, **`scheme`** (0 = replicas; otherwise a code id → `(k, m)`; as built the ids are a fixed table in code, `Redundancy.scheme()`, and an `ec` requirement keeps `desired` = m+1), and the requirement is recomputable (3.2) |
| `locations`: site → opaque location | `(site, index)` → location (one site may hold two shares while a drain or re-encode runs) |
| `sites` delta: `domain \t block \t site` lines | unchanged (full copies); a share is a line of the new split op `shares`, `domain \t block \t site \t index` (as built, 2026-10-07: an older build ignores extra columns, so a fourth `sites` column would be read as a full copy; an unknown op stops it instead) |

- **CompactBlockTable cost.** One byte per record for `scheme` and one byte per inline site slot for the
  index (four slots): about 5 bytes on today's ~75, so about 80. Spill handling (more than four sites,
  named holders) is unchanged. At 10^9 blocks that is about 5 GB more heap, which strengthens the case
  for N-DC6 (the on-disk BlockTable with a caching layer, before any core passes ~100 TB).
- **Hash and wire compatibility.** A record with only `FULL` shares and scheme 0 hashes exactly as today,
  so existing journals and snapshots keep their metaHash (pinned by `MetaHashGoldenTest`). As built, the
  new journal records are two wave-2 ops, `colRedundancy` and `shares`, which an older build refuses
  (it stops, fail closed), and two `blk` snapshot fields, which an older build ignores and then refuses
  the snapshot at its hash check. None of them is written while no collection is `ec` and no block holds
  a share, so a cluster that creates no `ec` collection journals exactly what 1.3 did. A rolling upgrade
  keeps `core_api_deltas=false` until every peer runs this build (OPERATIONS §13), which also refuses
  `ec` collections; the row is in DEFAULT-POLICIES.md (`core_default_redundancy`).

## 8. What counts toward durability

A share counts toward a block's `f` when **all** of these hold:

1. **Its medium is durable.** The locus shows a barrier that costs time, or it is attested. The new
   fail-closed rule: **a volatile medium never counts, attested or not (A4)**. RAM has barrier evidence
   `ABSENT` today, but `durabilityAttested` overrides that. `countsTowardDurability()` will refuse any
   locus that declares itself volatile (the A5 property "volatility on power loss"). Unit tests that use
   `MemBinding` as a durable site will say so with a `simulatedDurable` flag, as `TapeBinding` does
   with `simulated`, so a test fixture can never become a production loophole.
2. **It is not a live-tier copy.** The **live tier** (named 2026-10-27; earlier "the cache tier") is every
   copy of committed data held as native files where it can be read directly, byte by byte, at local-disk
   speed: a live node's copies near compute and the workspaces seeded from them, which filerepo presents as
   directories (docs/LIVE-TIER.md). Live copies are plaintext: the owner decided on 2026-10-27 that the
   durable tier is the only tier that is not native. They are never counted: the durable tier alone must
   recreate any dataset. The HPC cluster copy is uncontrolled live tier (P3/P4). A live node registers with the
   `live` role, never joins as a site, and a locus flagged `live` is refused by `countsTowardDurability()`
   and by placement even when attested. The disk share a site keeps after its tape share is VERIFIED is not
   live tier: it is durable-tier ciphertext (under `ec`, a single share) in the same failure domain as the
   tape share (correction of 2026-10-27; 5907a88f had listed it as live tier). (Unrelated: the `cache`
   retention class of a collection, data that can be regenerated, keeps its name.)
3. **Its write is complete.** On disk, the share is sealed past the barrier. On tape, its container is
   VERIFIED under `tape_write_verify FULL` (the default). Under SAMPLED or NONE, a SYNCED container
   counts too, because that is what choosing those modes means, but it is reported as *claimed*, never
   *verified*. The census shows both.
4. **It is not suspect** (scrub found it bad), and its site is ACTIVE or DRAINING, not LOST.

**Counting is per failure domain.** A site's disk spool and its tape library are one failure domain.
Two shares there survive a media fault but not a site loss. A block's `f` is the largest number of
domains whose loss leaves it decodable: a full copy, or at least `k` distinct indices. With at most
about eight domains per block, `f` is computed exactly by enumerating subsets and cached per share
pattern. **Census** reports blocks by `f` against their requirement (under-protected, at target,
surplus) instead of today's per-site `upActive < want`. RAM residency appears as its own vanishing
state (A4).

## 9. Tape as the primary tier

### 9.1 What changes from today

Today a tape copy is an extra (`core.archive`): placement never chooses tape, repair never counts it, and
trim never removes it. Under P3/P4 the durable tier is the tape at each of the three sites:

- **Placement may target tape for durable shares** (`ReplicaPlacer.Request.allowDeferred` for durable
  placement; `core_place_on_deferred` becomes `true` when MS6 lands). A share lands first on its site's
  disk spool, which is fast, counts once sealed, and lets the publish commit. It is then written to that
  site's tape by a spool pump.
- **Once the tape share is VERIFIED**, it counts. The disk share in the same domain adds nothing to the count,
  because a failure domain counts once (section 8), and the spool may evict it (9.3). Trim does not.
- **Reads** of tape-only blocks are staged (today's `DeferredRead` and `stage`). Under `ec:2+1`, the `k`
  shares are staged from two sites in parallel.

### 9.2 Containers on tape

Each site's tape holds only that site's share index for each block, in domain-pure containers grouped
by retention cohort (D2: volumes die whole and tape is reclaimed). Containers stay 1 GiB parcels
(PACK-FORMAT §11). R6, the intra-volume RS(j, 4) over parcels from SPECIFICATION §3.2 and §8.1, is a
separate, later layer (MS8). It repairs a media defect with zero WAN bytes and zero extra mounts, and it
never counts toward site survivability.

### 9.3 The spool

Spool residency after VERIFIED is a **test-bed parameter**: evict at once, or keep the newest versions on
disk, which serves reads without a tape stage. Data kept usable for compute belongs in the live tier
(docs/LIVE-TIER.md), not the spool. Eviction is refused for any share whose tape share is not VERIFIED (or
SYNCED, under the non-default verify modes).

### 9.4 Commit, and "synchronously committed at every location" (V1)

(For a coded block, "a VERIFIED tape copy" is the tape tier's ability to give the block back: k distinct shares on
tape; section 9.5.)

The owner decided (13a, "Commit point"): a durable dataset commits only when its copies are VERIFIED on tape; the
disk spool is staging, never a counted copy. As built (e70b50a, 5aa7706; replicas today, shares once EC lands): the
publish or §1a commit seals every copy on its sites' disk spools, kicks the spool pump, and answers `commit_job`, a
job that ends when every block of the version has a VERIFIED tape copy at its site. Until then the version is
COMMITTING: `core.get` answers status 16 before any stream opens, and reads through the engine are gated the same
way; stage, repair and verify are not. The state is derived from the references, never journaled, so a new leader
re-derives it. The clients await it (OUT-102: by default a read that meets 16 follows the commit job through
`core.job`, or reads again with back-off, for up to 30 minutes; the MCP tools wait a bounded time and then answer
`status: committing`). Commit latency is the tape write window plus verification: on the standing deployment
(`tape_write_max_age_ms` 2 min) a version is readable about 2 minutes after its put. Measured on the simulator with
the standing settings (LTO-9 timing, `tape_write_verify` FULL, the 60 s idle unload), a lone 4 KiB seal was VERIFIED
170-186 s after it reached the tape node: the 120 s window, then a remount each time (robot 8 s, load 15 s, label
check 3 s, space to EOD 2 s; the 60 s idle unload was shorter than the window, so the volume was always unloaded by
then), the write and the read-back of its container (2 MiB: one data record and the tail; containers are not
padded, TAPE-FORMAT §2). Since OUT-110 (2026-10-15, `tape_unload_hold_for_writes`) a drive keeps the OPEN volume of
queued writes until their session and lingers 10 minutes (or the window, if longer) after one, so the remount is
gone: about window + 12 s (table below).

**The `tape_write_max_age_ms` trade-off (owner input; simulator, standing settings, `TapeWriteHoldTest#tapeWriteMaxAgeTradeOff`).**
One 4 KiB write every 3 minutes (the canary) for an hour, two drives, a clock at 40x: the latencies carry the host's
own time 40 times (about 4-5 s here; at 200x the 120 s rows read 152 s and 180 s), so at real time expect about
128 s with the hold and about 151 s without it for the 120 s window (extrapolated, not measured at 1x). Mounts,
sessions and drive time do not depend on the scale.

| `tape_write_max_age_ms` | sessions/h | 1.3 (no hold): mounts/h, drive busy s/h, seal to VERIFIED median | with the hold: mounts/h, drive busy s/h, seal to VERIFIED median |
|---|---|---|---|
| 30 s | 20 | 19, 1,080, 64 s | 0, 164, 43 s |
| 60 s | 20 | 20, 1,144, 99 s | 0, 158, 73 s |
| 120 s (standing) | 20 | 20, 1,138, 157 s | 0, 149, 133 s |
| 300 s | 10 | 10, 583, 334 s | 0, 96, 310 s |
| 900 s (code default) | 4 | 4, 256, 585 s | 0, 60, 558 s |

A write a minute, with the hold: 30 s window 60 sessions/h, 421 s drive busy, median 40 s; 120 s window 24
sessions, 241 s, median 74 s; 900 s window 4 sessions, 141 s, median 520 s; 0 mounts in each.

What the window buys now. Read-after-write is about the window plus one session (~12 s here: the label check's
rewind, space to EOD, the records and a filemark, the locate back and the read-back). With the hold it no longer
buys fewer mounts (0 at every window up to the linger), and it never buys container fill: every seal is its own
container (2 MiB on tape for a 4 KiB write at any window; a session takes several containers but merges none). It
buys fewer sessions, about 7.5 s of drive time each (the canary at 120 s: 149 s of drive time an hour, 4% of one
drive; at 30 s: 164 s), and fewer label checks and filemarks. Not measured here and [HW]: the label check rewinds to
BOT and spaces back to EOD each session, a few seconds near BOT but up to about 200 s on a nearly full LTO-10
cartridge, which would make short windows cost far more drive time late in a volume's life (OUTSTANDING OUT-110).
The 120 s standing value is not wrong; with the hold, 30-60 s would bring read-after-write under about a minute at
a few minutes of drive time an hour. Defaults unchanged: the code's 900 s, the standing deployment's 120 s. Every commit route starts the pump at once and names
the commit job (core.publish, core.compose since 2026-10-15 (inline and from its job), and the §1a core.commit both
inline and when its job ends after the RPC answered `committing`); until 2026-10-15 the §1a commit did neither, so its versions waited for the next 60 s job sweep and
the standing canary read each new version a near-constant 176.7 s after writing it (its 3-minute round locked to
that sweep).

### 9.5 Shares on tape (built 2026-10-14)

With `core_place_on_deferred=true`, encode on write places a coded block's shares on the sites' disk spools, one per
failure domain of the collection's placement group, as without tape. The spool pump then archives to each site's tape
**the share its own failure domain holds** (else the lowest index no tape holds yet, else any index a readable disk
holder has: a deterministic rule, so a new leader's pump chooses the same), sourced from that disk holder (or a
PRESENT_VERIFIED tape holder of the same index), and landed by a `shares` line: never a full copy of a coded block.
The tape tier therefore holds one share per domain, 1.5x for `ec:2+1`, as section 9.2 asks. A version commits once
the tape tier alone can give every block back: a full copy, or k distinct shares, on deferred sites
(`mirroredOnTape`). The census and repair count a VERIFIED tape share per failure domain like a disk one; archive
verification checks a tape share under its own extent id. A block under `core_ec_min_block_bytes` keeps full copies
and is archived as one. With every disk copy gone and one site's library away, the data is staged from the other two
tapes and read byte for byte (`EcTapePrimaryTest`). Before this, a coded block was never archived (the pump looked for
a full copy on its disk holders, which hold shares), so an `ec` version under tape-primary stayed COMMITTING for good.

## 10. Migration of existing replicated data

- **Nothing changes silently.** Existing collections keep their recorded policy (`replicas:R`, or `single`
  for scratch caches), because the absence of `colRedundancy` means exactly that. Switching the default to `ec:2+1`
  (2026-10-14) changes what *new* collections get; no existing collection, profile record or block is re-encoded by an
  upgrade, and repair keeps their blocks as full copies (`EcDefaultClusterTest`, the replicas:3 collection beside the
  default one). The state hashes of everything an older build journaled are unchanged (`MetaHashGoldenTest`, and the
  cross-version replay probe `HashCompatProbe`).
- **Moving to EC** is an operator action, `core.redundancy op=set to=ec:2+1`, per collection or per profile
  cohort. It is journaled, audited, and refused if it would take durable data below `f = 1`.
- **The re-encode job** (5.2) converts each block whose requirement changed. It reads one verified full
  copy, writes the missing shares, lands them, and trims full copies **only after** the shares meet
  the requirement. During conversion the block's `f` is the maximum of both forms, so protection never
  dips.
- **Copies already on tape.** Extra copies from `core.archive` become dead space once the full copies
  are trimmed. They are reclaimed by tape repack under D8 (budgeted GC; volumes above 50 % live are
  refused for repack).
- **Cost.** Per block: read 1x, write 1.5x, reclaim Rx. T5's estimate was about three weeks of
  background drive time at 3 PB. The test bed measures it, and it is scheduled, not a project.

## 11. Parameters the test bed decides

Each has a provisional value and is resolved by measurement, never by declaration (standing rule).

| Parameter | Provisional | Decided by |
|---|---|---|
| Stripe mapping: DM-1 or DM-1b | DM-1 | E-DM1 on the tape simulator (4.2) |
| `ec_min_block_bytes` | 64 KiB | per-record overhead against the small-block byte share of the P2 fixtures |
| Encode on write, or land as `replicas:2` and encode later | encode on write | ingest MB/s at 80 ms RTT, WAN bytes, spool amplification, time to VERIFIED |
| Shares by star, or by chain with node-side encoding | star | the same frame and flow sweeps as `core_replication` |
| Codec implementation (GF(256) log tables; split-nibble tables; FFM or the Vector API) | log tables (about 1.6 GB/s per core for RS(2,1) on an M3 Max; 13, item 8) | CodecBench at 1 MiB and 4 MiB blocks on the HPC cluster and site hosts, all cores, against the rebuild rate |
| The generator (on-media format) | systematic Vandermonde as built: RS(2,1) parity is `3·d0 + 2·d1`, not XOR | fixed in MS1 before any share is written: an all-ones first parity row (plain XOR for `m = 1`) is a different code and a different scheme id, chosen only if the measurement wants it |
| Read hedging for `ec` on disk | one extra share when late | p99 read latency on three sites |
| Deep-scrub cadence and budget | monthly (`core_deep_scrub_period_ms`, 30 days), on the shared maintenance throttle | failure campaigns |
| Repair budgets (drive-seconds, WAN bytes) | as repair today | R9 (repair window) and site-loss campaigns |
| Spool residency after VERIFIED | evict under pressure only | spool size against the hot set |
| The code beyond phase one (R7: RS(3,1) at four sites, ...) | RS(2,1) | when a fourth domain exists |

## 12. Milestones, bottom-up

Every milestone ends with its tests green and its performance decision recorded, before the next one
starts. Tests named here are new unless marked.

**MS0. N-DC11 (done on this branch).** `PolicyEngineTest.oneCopyOnlyForAScratchOrCacheClass`,
`RetentionTest.aOneCopyCollectionStaysScratchOrCache`, `PolicyProfileTest` and `CoreServiceAuthTest`
(the core.collection and core.profile refusals), and the model test's expectation (`Ops.CreateCollection`).

**MS1. The codec and the share format (unit, one node).**
- *Build:* `BlockShares` (core side, `io.cresco.gfs.core.ec`) over the existing
  `io.cresco.gfs.codec.ReedSolomon` and `GF256` (section 12.1). It splits, pads and encodes one block's
  ciphertext, decodes from any `k` shares (trimming to the recorded length), remakes lost shares
  bit-identically for repair, and checks a complete set for a deep scrub.
- *Unit tests:*
  - every erasure pattern for every `(k, m)` with `k + m ≤ 12` (the codec), and for the block codes
    RS(2,1), RS(3,1), RS(4,2), RS(3,3), RS(5,3) and RS(1, m); RS(2,1) and RS(4,2) at dedup-block sizes
    (256 KiB, 1 MiB, 4 MiB);
  - every length from 0 to `3k`, and lengths around every power of two;
  - any changed byte in any share, padding included, is detected by the consistency check;
  - any `k` rows of the generator are invertible (exhaustive for `n ≤ 12`);
  - field axioms for GF(256);
  - systematic property: the data shares equal the input;
  - a property test with seeded random inputs and erasures.
- *Component performance decision:* CodecBench encode and decode MB/s per core at 1 MiB and 4 MiB for
  RS(2,1), on the HPC cluster and the site hosts. Decide the generator, which is part of the on-media format: as
  built, or one whose parity is plain XOR for `m = 1`. Decide any acceleration (licence filter: shipped
  code must be open and commercially permissible). The generator is fixed before any share is
  written.
- *Done on this branch:* `BlockShares`, `BlockSharesTest` and `ReedSolomonTest`, which cover every item
  above, plus a first single-thread measurement (13, item 8). Since 2026-10-07 (branch `fix/ec`):
  `BlockSharesTest.seededPropertyTest` (random `k` in 1..8 and `m` in 0..4, lengths at the padding edges and
  up to 70 KB, random erasures up to `m`, corrupted shares; `-Dgfs.prop.seed`, `-Dgfs.prop.cases`);
  `everyKSubsetOfTheGeneratorIsInvertible`, which proves MDS on the generator matrix itself for every code with
  `k + m <= 16` (131,038 subsets) and samples codes up to 255 shares; `BlockShares.decodeChecked`, the subset
  retry of 4.4 (a block is returned only once it authenticates, and then every present share that differs from
  its re-encoding is named bad, exactly, whatever `m` is); and CodecBench's `block_shares` cells (RS(2,1) and
  RS(3,1) at 1 MiB and 4 MiB blocks: encode, healthy and degraded read, parity repair, deep scrub, and encode on
  every thread; `CodecBench <mib> <threads> ec` runs only these).
- *The generator decision (2026-10-07):* **kept as built.** The systematic Vandermonde construction is MDS (proved
  above), so no Cauchy or XOR construction is needed for correctness. Plain XOR parity for `m = 1` stays a
  test-bed option only: it would be a different code, so it would get a new scheme id, never replace this one.
  Still to do: CodecBench on the HPC cluster and the site hosts (`java -cp gfs.jar io.cresco.gfs.bench.CodecBench 256 <cores> ec`).

**MS2. Policy, records and survivability (unit).**
- *Build:* the `Redundancy` value (parse, order, `f`); `colRedundancy` and the profile `redundancy` key
  (journal, replay, snapshot, facts hash); `core_default_redundancy`; N-DC11 restated as `f ≥ 1`;
  requirement recomputation (3.2); `BlockTable` share index and `scheme` (`CompactBlockTable`, spill,
  cuts, snapshot, replay); the survivability calculator.
- *Unit tests:*
  - `PolicyEngineTest` and `PolicyProfileTest` cells for all three modes;
  - `CompactBlockTable` round trips with shares, including after a cut, and copy-on-write;
  - metaHash unchanged for `FULL`-only records (old journal goldens);
  - the survivability calculator against brute force for every share pattern on up to 8 domains;
  - replay of a pre-modes journal (`JournalReplayTest`).

- *Done on branch `fix/ec` (2026-10-07):*
  - `core.ec.Redundancy`: canonical spellings only (`single`, `replicas:R`, `ec:k+m` with k 2..8 and m 1..4;
    `replicas:1` is spelled `single`), `f`, the 3.2 order (f, then full copies, then fewer data shares),
    `strongest`. **Scheme ids are a fixed table in code, not a journaled one:** id = 1 + (k-2)*4 + (m-1) for the
    systematic Vandermonde code as built (`ec:2+1` is 1, `ec:3+1` is 5), ids 29..255 free for another construction.
    An `ec` requirement records its id with `desired` = m+1, its full-copy form. `RedundancyTest`.
  - Policy: `PolicyEngine.createCollection(.., Redundancy, ..)` records the full-copy form as `replication`
    (the `collection` delta keeps its form) and, for `ec`, a `colRedundancy [collection, spelling]` delta in the
    **same journal batch** (a batch hook, `onChangeAll`); `replicas:R` and `single` record nothing new. N-DC11 is
    `f >= 1` for durable. The delta is wave-2: refused before anything changes while `core_api_deltas` is off
    (`redundancy-needs-api-deltas`). Replay (`restoreRedundancy`) refuses a redundancy whose full-copy form is
    not the recorded replication. The policy digest adds `|<spelling>` only to a recorded one. Snapshots carry
    it in their own phase after the collections. The profile record gains `redundancy` only when the replication
    does not say it (built-in records unchanged). `core.collection` and `core.profile op=create` take
    `redundancy` (with `replication` as its alias; both given must agree), `core_default_redundancy` (default
    `replicas:3`), and the collection listing and replies show it. `RedundancyPolicyTest`, `PartitionerTest`.
  - Records: `BlockRecord.scheme` and `BlockRecord.shares` (site -> index; absent is `FULL`), in
    `CompactBlockTable` as lazily allocated page arrays (a full-copy page pays nothing) and the side maps past
    four sites; `raiseRequirement` by the 3.2 order, `setRequirement` (a recomputation, may lower); new digest
    facts `e` and `i` only for non-default values. The adopt paths carry the collection's requirement packed in
    the int that carried a copies count (a count below 256 is scheme 0, so replicas collections are unchanged).
    **Shares are journaled by a new split op `shares` (lines domain, block, site, index), not a fourth column of
    `sites`:** an older build ignores extra columns and would record a share as a full copy, while an unknown op
    makes it stop (fail closed). The `blk` snapshot delta gains fields 9 (scheme) and 10 (shares) only for
    non-default records. One site holds one thing of a block: recording another index there is refused (the
    "two shares at one site during a drain" case of section 7 is not built; MS4 decides it).
    `CompactBlockTableShareTest`; `MetaHashGoldenTest` pins the block-table and engine content digests of a
    full-copy history to the values gfs 1.3 6139767 computes, so existing data hashes and replays unchanged.
  - The requirement through an epoch: `StorageEngine.requirement(domain, block)` is the record's requirement
    raised by the derived-version floors, recomputed per `floorsEpoch`, which `colRedundancy` now bumps too.
    Lowering a recorded requirement needs the referencing collections of a block; the engine keeps counts, not
    holders, so it is MS5's re-encode job (see 13, item 9).
  - `core.ec.Survivability`: f of a block from its counted holdings (domain, full or index) and k, exact against
    brute force (`SurvivabilityTest`, every one-holding pattern on up to 8 domains for RS(2,1), random
    multi-share patterns), cached per share pattern, with the minimal fatal domain sets.
  - `core.place.PlacementGroups` and `SharePlacer` (13a): groups of k+m distinct domains from seeded
    permutations of the domain set; an object is pinned to a group by rendezvous on its key, its share roles
    fixed per object, so a healthy read of one object is k domains (k mounts) at 3, 6 and 12 sites while load
    spreads across objects; the next whole group takes a block when a member is down; debt (`minCopies`, never
    below k, only for "down") as `core_place_min_copies` does for replicas. `PlacementGroupTest`. Not yet
    called by the engine: encode-on-write (MS5) is its first caller.

**MS3. The engine's read path (component).**
- *Build:* `readBlock` for shares (data first, decode, AEAD, subset isolation of a bad share, hedging on
  disk only); `fetchMany` by share; staging of `k` shares from tape.
- *Component tests:* MemBinding and FsBinding sites with absent, corrupt, slow and tape-only shares, and
  every subset; a bad share is never served and is always reported.
- *Performance decision:* read MB/s and p99 for `ec:2+1` against `replicas:3` on three local sites; the
  hedge rule.

- *Done on branch `fix/ec` (2026-10-07), in part:* `core.ec.ShareReader` (engine-independent: data shares first and
  concatenated, the next untried share on absence, failure or timeout, a k+1 hedge when the slowest is late,
  `decodeChecked` subset isolation, every bad share named, never wrong bytes) and its wiring into
  `StorageEngine.readBlock`: a block whose record names a code reads its full copies first (one site), then its
  shares (`readShares`, own read pool, CORRUPT reported per bad share). Share extents are
  `extentId(domain, block) + "_s" + i` (`shareExtentId`); the ciphertext length is the block length plus the GCM tag.
  `ShareReaderTest` (every absent/failing/corrupt pattern for RS(2,1), RS(3,1), RS(2,2); slow shares with and without
  a hedge; two holders of one index; random RS(4,2) mixtures) and `ShareReadEngineTest` (blocks re-encoded by hand on
  three RAM sites: healthy, each site down, a corrupt share reported, refused when fewer than k good shares are left,
  replay and snapshot).
- *Done 2026-10-08 (the rest):* staging from tape: a coded block with fewer than k shares readable from disk answers
  `DeferredRead` (never a mount on a user read), and `core.stage` plans exactly the missing shares from deferred
  holders of other indices, data shares first, one per site; staged shares are read from the recall cache like any
  holding. The read-ahead window asks each coded block's k data shares and concatenates them; anything missing or
  wrong falls to the per-block path. Share extent ids are `<extentId>_s<i>` (every store accepts only
  `[A-Za-z0-9_-]`). `EcReadPathTest`. First measurement (this Mac, three RAM sites, 32 MiB files, the engine's full
  read path): ec:2+1 about 0.9 GB/s and replicas:3 0.8-1.1 GB/s, p99 per file 38 ms against 30-54 ms: no read cost
  at RAM speed; the decision belongs to the HPC cluster and site hosts with real latency (hedge rule unchanged: one extra
  share when the slowest is late).

**MS4. Maintenance per share (component).**
- *Build:* repair (rebuild index `i` from any `k`; `placeFewer` by index); trim per failure domain; scrub
  and deep scrub; census by `f`; declareLost, drain and restore for shares; fault points for re-encode and
  share repair.
- *Component tests:*
  - repair after every single-share and double-share loss pattern;
  - trim never takes a block below its requirement while a requirement rises concurrently (the existing
    `MaintenanceSafetyTest` cases for shares);
  - declareLost refusals with survivors on disk, on tape, and none;
  - crash cells for every new fault point (`FaultPoints`, as `RecoverLiveIntentTest` and the power
    harness drive them).
- *Done 2026-10-08 (component level, `EcMaintenanceTest`):* blocks whose record names a code are maintained apart
  from the replica paths (which count copies). Repair rebuilds every index no counted domain holds from any k
  digest-checked shares (no key) or a full copy, onto a free domain, under an intent whose site tokens name the share
  (`site~s<i>c<code>`), recorded by `shares`; trim removes duplicate indices and the form a requirement no longer
  needs, each released only if what stays meets it; scrub checks each share's own extent and reclaims a bad share once
  the rest still decode; `deepScrub` recomputes the parity (and with m >= 2 locates and reclaims the bad share); the
  census counts coded blocks by f (`codedBlocks`, `underReplicated` when f is short); declareLost counts decodable
  survivors (`LastCopies` when they do not decode); drain moves shares; intents, gc and orphan cleanup name share
  extents. Fault points `share.repair.{intent,sealed,landed}`, with crash cells. Every single-share loss is repaired,
  a double loss of ec:2+1 reported unrecoverable (never wrong bytes). Not built: re-encoding between two codes; a site
  holding two shares of one block (refused).
- *Done 2026-10-14 (deep scrub on the scheduler):* a `DEEP_SCRUB` pass of the maintenance scheduler
  (`core_deep_scrub_period_ms`, default 30 days, the provisional monthly cadence; `core.maint op=run pass=deep_scrub`),
  resumable by cursor and paced by the shared maintenance throttle (each block's k+m share reads paid before any lock).
  Its walk is the block table's `CODED` filter: a page of records holding no share is skipped whole and a full-copy
  record is never materialized, so a pass costs the coded blocks, not the table (scale rule). Gauges
  `deep_scrub.last_end_ms`, `deep_scrub.inconsistent`. `MaintenanceSchedulerTest.theSchedulerDeepScrubsTheCodedBlocksOnlyAndLocatesABadShare`.

**MS5. Write paths and mode changes (integration).**
- *Build:* encode-on-write in `publish` and `compose` (star of shares; chain variant behind a flag); the
  re-encode job (sliced, throttled, resumable); `core.redundancy`; small-block replication (4.3).
- *Integration tests:*
  - `IntegrationMatrixTest` cells: {NONE, COLLECTION, GROUP, GLOBAL} × chunkers × {`ec:2+1`,
    `replicas:3`, `single`} × {RAM, filesystem};
  - mixed-mode dedup (one GLOBAL block referenced from `ec` and `replicas:3` collections);
  - migration of a `replicas:3` corpus to `ec:2+1` under concurrent publishes and gc;
  - the model test (`EngineModel`) extended with modes and `core.redundancy`; the linearizability test.
- *Performance decision:* encode on write against land-then-encode (5.3); star against chain.
- *Done 2026-10-08 (component level, `EcMaintenanceTest`, `EcModeChangeTest`):* encode on write in `store()` (every
  publish path) for an ec collection while `core_api_deltas` is on (`core_ec_encode_on_write`, default true): one
  share per failure domain of the collection's placement group (the object pinned to a group is the collection), a
  star of shares (the chain is not used for ec collections). Small blocks (`core_ec_min_block_bytes`, 64 KiB) keep
  m+1 full copies. Owner question 1, as recommended: with sites down only, `core_place_min_shares` (default -1: as
  `core_place_min_copies`) places at least that many shares, never fewer than k, and the rest is debt repair pays.
  Re-encode is a repair (`core_ec_reencode`, default true): an ec block held as full copies is encoded, a coded block
  whose requirement became full copies is decoded, and a site holding the other form is converted in place (the new
  extent sealed, then one batch unrecords the old form and records the new, and the intent naming both reclaims the
  old), so f never dips, also at three sites; fault points `reencode.{intent,sealed,landed}`, with crash cells.
  `core.redundancy op=get|set` (`colRedundancySet`, wave-2): the collection's positions move class and each of its
  blocks takes the strongest class still referencing it, raised or lowered (owner question 2, as recommended: position
  references counted per requirement class, derived and unhashed, a map kept only for blocks referenced under two
  classes, rebuilt from the holds at a snapshot install; named holders keep their class by name). Not built: the
  integration matrix cells, mixed-mode GLOBAL dedup under concurrent publishes and gc, the model and linearizability
  tests with modes, and the test-bed decisions; so the default stays `replicas:3`.
- *Done 2026-10-14 (integration, branch `fix/ec-default`):*
  - `IntegrationMatrixTest`: `lifecycleEc` (every dedup mode x 64 KiB chunker x locus RAM, file, packed and remote:
    encode on write, one site holding shares lost and read around, its indices rebuilt on the fourth domain, the
    surplus trimmed when it returns, a corrupt share read around and scrubbed, deep scrub, journal replay; dedup
    asserted per block as for replicas), `lifecycleEc1M` (the 1 MiB default chunkers on 8-48 MB files, RAM and file),
    `mixedModeDedup` (GROUP and GLOBAL: one block referenced from an ec:2+1 and a replicas:3 collection is three full
    copies, the second publish writes nothing; once the replicas:3 referencer is withdrawn the block keeps three
    copies: a dropped reference never lowers a requirement by itself, only a journaled change does (a mode change, or
    with `core_lower_on_drop` trim's `reqLower`, below), so an old journal replays as written; over-protected, never
    under), and `aReplicatedCorpusMigratesToEcUnderConcurrentPublishesAndGc`.
  - The model (`EngineModel`, `OpGenerator`): every third two-copy collection is ec:2+1 (no draw of its own, so
    collections of both modes share GROUP and GLOBAL domains), a `SetRedundancy` op (`core.redundancy op=set`), and the
    invariants count a coded block by its distinct shares (availability from any k good shares, declareLost by what
    still decodes, the on-disk census by share extent ids). `EngineLinearizabilityTest` runs with collection B ec:2+1 in
    the domain it shares with A.
  - Through the core service (`EcDefaultClusterTest`, three Raft peers, §1a ingest): the default, site loss and
    core.repair, core.redundancy to replicas:3 and back, a leader failover, a replicas:3 collection untouched beside
    it; the rolling-upgrade window; and a two-domain fabric refusing an ec write.
  - The default switched: `core_default_redundancy=ec:2+1`, the imaging profiles ec:2+1 (section 3.1).
  - Two engine fixes the model with modes found. (1) **Share repair never builds on a bad share**: a share drained off
    a site was rebuilt from the first k readable shares, one of which had rotted on its medium (a direct read does not
    check the at-rest digest), so the new share was wrong while its own digest vouched for it and no two shares decoded.
    Repair now fetches every present share, checks the rebuild against the others, and where they disagree (or only k
    are present) takes the k-subset whose decoding opens under the block's key (a NONE domain, which has no key at
    the core: a two-thirds majority when m >= 2, else the k present shares as they are); a share that differs is
    reported CORRUPT, reclaimed and rebuilt in the same pass; a full-copy source must open too. (2) **Placement at
    more domains than k+m**: with four domains a whole placement group could be inadmissible (one member down or
    draining) while three domains were up, and the write was refused; `SharePlacer` now places on the object's own
    ranking of the admissible domains before debt or refusal. (3) With the stripe disagreeing, a share that fails its
    own site's content check is dropped before anything else (a NONE domain with m = 1 has nothing else to go on).
    (4) A drain with no free failure domain left (k+m+1 domains, one draining) has a second holder of an index (a site
    back after repair rebuilt its share elsewhere) take the missing index in place. (5) **A read with two holders of
    one index** never tried the second after the first (rotted) one failed to open: `ShareReader` now reads one holder
    per index at a time, keeps a second holder's share as a spare, and swaps it in after a failed open (the holder it
    replaces is reported bad). (6) **Repair with exactly k shares and no key to check them** (or a key check that
    fails) content-checks each share at its site first and never builds on one that fails; a full copy used as the
    source of a re-encode in a domain with no key at the core is content-checked the same way (a rotted single copy
    was encoded into consistent but wrong shares). (7) **A block stored again**
    (its recorded holdings no longer give it back) avoids sites holding another form of it (a site holds one thing of
    a block): with no domain to spare such a write is refused, never recorded over the stale holding. (8) **Repair
    against a stale page**: a holding another pass converted since the page was read was taken as absent and its new
    form unrecorded (data loss under concurrent maintenance, seen in the cluster test); repair now reads the record as
    it is and never infers absence for an extent id it did not ask about. A dropped reference never lowers a
    requirement by itself (only a journaled change does, so old journals replay as written): with
    `core_lower_on_drop` off (the default) the block stays over-protected until a mode change (see the 2026-10-15
    entry below for the gated lowering). Regressions in `model-regressions/ec-*.json`.
  - **One pass converges (fix/ec-converge, 2026-10-15).** The long campaign (`EngineModelLongTest`, tag model-long,
    1,500 seeds of 150 operations) failed about 2 % of seeds (29 to 33 of 1,500 in five runs on 1.3 f8c0e13) on `INV-LIFECYCLE` "a
    sliced pass did not end where an unsliced one does" for SCRUB, REPAIR or TRIM: a second identical pass over coded
    blocks still did work. The invariant already covered coded blocks (no exemption); each cause is fixed in the engine,
    never by running a pass twice: (1) **trim** released the last shares of a block re-encoded to full copies and left
    its surplus full copy to the next pass: the block is trimmed as a full-copy block in the same slice, as its record
    now stands; (2) **repair** re-encoded a block to full copies and left its copy on a draining site to the next pass:
    the converted block goes through the full-copy repair (drain) in the same slice; (3) **scrub** reclaimed a bad share
    (or a bad full copy of a block being encoded) only after repair, while its site, often the only one of its failure
    domain, was excluded as a target: a coded block's bad holdings settle before repair when the verified holdings
    decode it, and a block settled after repair is repaired again in the same slice; (4) **repair** skipped a holding
    found bad before (by a scrub or a read) but kept it recorded, blocking its domain: with the stripe in hand from
    trusted holdings it is reclaimed and its site may take what the block owes; (5) **repair** read one holder per
    index, so a bad first holder made the block unrecoverable until a later pass: second holders stand in. Two
    data-safety faults found on the way (both on 1.3 too, rarer than the convergence ones and load-dependent, as which
    holder a read tries first decides whether a corrupt share is already known): (6) a stripe rebuilt from a full copy
    was never compared with the shares present, and the re-encode then replaced the full copy in place next to a
    corrupt share, leaving a block that no longer decoded: shares that differ from the full copy's stripe are
    condemned, targets in new domains are written first, and an in-place replacement goes ahead only if what is known
    good, with what landed and the in-place forms, still decodes; (7) shares condemned while no stripe could be trusted
    were reclaimed anyway, leaving a live block with no holding at all: they are kept (suspect), as a scrub keeps a bad
    copy its block cannot do without. After: 0 failures over the 1,500 seeds in each of 12 campaign runs of the final
    code (18,000 seed runs; two under a second campaign's load, two with `core_lower_on_drop` off), and 0 convergence failures over seeds 20001-21500 and 30001-31500 (the one
    failure left there, seed 20344 `INV-REF` named holders of a relocation, was outside maintenance: an ended grant
    re-checked after a restart released copies a still-active scoped grant kept, fixed 2026-10-24 on fix/known-defects;
    the same run over seeds 10001-15000 found seeds 11927 and 14252, where the model asked k shares on ACTIVE sites
    with fewer active failure domains than k: the invariant now counts a draining site's share as §8 does). Regressions: `model-regressions/ec-one-pass-*.json`, `ec-inplace-over-unchecked-share-30422.json`. The
    sliced-pass invariant now names each block a second pass changed (before, after the sliced pass, after the second)
    and what the sliced pass did; `-Dgfs.model.trace=true` prints every failed seed's trace.
  - **Over-protection, gated (`core_lower_on_drop`, 2026-10-15).** A block an ec:2+1 collection shares with a
    replicas:3 collection stayed at replicas:3 once the replicas:3 collection was withdrawn. With `core_lower_on_drop`
    on, trim lowers such a block to the strongest class still referencing it (the per-class reference counts of §3.2:
    O(1) per block, decided and applied under the engine's monitor, so no commit that raises it interleaves),
    journaled by the wave-2 delta `reqLower` (domain, block, packed requirement; routed to the domain's partition);
    repair then converts the form and trim reclaims the surplus, as after a mode change. Three gates: the key (default
    off: an owner decision, as `core_audit_archive`), `core_api_deltas`, and every voting peer answering the feature
    `rlow1` (an older build halts on `reqLower`; OPERATIONS §13.3). A dropped reference itself still changes nothing,
    so older journals replay as written and every hash is unchanged while the key is off. `EcModeChangeTest`
    covers off, api off, on, once only, re-encode, replay and snapshot install; the model runs with it on
    (`-Dgfs.model.lower=false` for off).
  - **Left as it is: a lost block stored again over its stale share.** With two sites declared lost by force and only
    three failure domains left, storing again a coded block whose recorded holdings no longer decode it is refused
    (UNAVAILABLE) rather than written over the stale share a third domain's site still holds (rule 7 above;
    `ec-restore-lost-block-few-domains-10725.json`). Writing over it needs the publish path to unrecord the stale
    holding and record the new share in the commit's batch, and a binding contract for an append over an extent id the
    site already holds (the same index), which no binding states today. The refusal is safe (fail closed, nothing
    recorded wrongly) and the caller can retry once a domain returns or after a drain; not built.

**MS6. Tape counts (integration). Partly built (e70b50a and after, see the status at the top): durable placement
onto tape through the spool pump, counting VERIFIED, and the commit-on-VERIFIED gate, with
`TapeEndToEndTest#tapePrimaryPumpMirrorsCountsAndGatesCommitUntilVerified`. Left, as e70b50a lists them: the spool
eviction policy, repair from tape sources, and declareLost with tape survivors; and the other items below
(SYNCED counted as claimed, the A4 volatile-medium rule and `simulatedDurable`, the `cache` locus role).**
- *Build:* durable placement onto tape loci through the spool; counting VERIFIED (and SYNCED under the
  non-default modes, as claimed); spool eviction; staged repair from tape on positive evidence only;
  declareLost with tape survivors; the A4 volatile-medium rule and the `simulatedDurable` test flag; the
  `cache` locus role.
- *Integration tests:*
  - the tape simulator and mhVTL (`TapeEndToEndTest`, `TapeFailoverTest`, new cells): a publish counts
    only after VERIFIED;
  - SYNCED counts as claimed under NONE;
  - RAM never counts even when attested;
  - a live-tier copy never counts;
  - repair never fires on a tape timeout.

**MS7. System tests (three simulated identical sites, several drives and tapes each).**
- *Done 2026-10-14 (crash matrix):* `CrashScenarios` drives `share.repair.{intent,sealed,landed}` (a site holding shares
  down, repair rebuilding its indices) and `reencode.{intent,sealed,landed}` (replicas:3 to ec:2+1, then back, each
  re-encode cut) in every cut mode (process kill, power loss, prefix, reorder); the `publish.*` points cut an ec:2+1
  publish (encode on write) too; `trim.reclaimed` and `scrub.reclaimed` add a round of surplus and corrupt shares. The
  base world of every scenario has an ec:2+1 collection (64 KiB fixed blocks coded, tails as two full copies). The
  oracle counts a coded block by its distinct shares (O6) and the census by share extent ids (O5). Recovery leaves no
  lost or wrong data and no open intent. `FaultPointsLintTest` lists no EC point as pending.
- All three modes end to end, from the Java and Python clients.
- **Loss of a whole site and its rebuild from the durable tier alone (P3/P4)**: every dataset recreated
  bit-identically from tape, with no HPC copy.
- Media defects.
- A rolling upgrade across the wire-format change.
- **E-DM1 decided** (4.2).
- Failure campaigns as in eval/ (crash matrix, failover, chaos) with modes.
- Then the HPC cluster runs.

**MS8. Later.** R6 intra-volume RS(j, 4) over parcels on tape; R7 codes when a fourth domain exists;
DM-1b, if E-DM1 calls for it.

### 12.1 What MS1 starts from

The repository already has a Reed-Solomon codec: `io.cresco.gfs.codec.ReedSolomon` and `GF256`, written in
house for the prototype path (`DurabilityEngine`). It uses pure JDK code, no third-party licence, the
primitive polynomial 0x11d, and the Backblaze construction: a Vandermonde matrix multiplied by the
inverse of its top `k` rows, so the code is systematic. That construction is MDS for `k + m ≤ 255`,
because any `k` rows of a Vandermonde matrix with distinct points are independent, and multiplying by an
invertible matrix keeps them so. It had no unit tests; `ReedSolomonTest` now covers it, including the
exhaustive erasure patterns up to twelve shards and a pinned generator. MS1 reuses it rather than writing
another. It
lives in a package the prototype path also uses, so retiring the prototype (N-PROTO) must leave
`io.cresco.gfs.codec` in place.

## 13a. Resolved by the owner (2026-10-02)

- **Stripe shape (was 13.1/13.2):** DM-1 is the default and is built now; the shape stays a policy knob and the
  default is confirmed by the E-DM1 tape-sim sweep before hardware. Placement groups (an object pinned to a fixed
  n-site subset) are built from the start so 3->6->12 sites is a config change: a read stays ~k mounts and load
  spreads. DM-1 is required regardless, because block-level dedup needs the block to be the stripe unit.
- **Commit point (was 13.4):** a durable dataset commits only when its copies are VERIFIED on tape. The disk spool
  is staging, never a counted copy. This needs the async commit job and the two-phase client protocol (MS6 brings
  it forward; see the milestones). Commit latency is minutes-to-hours by design.
- **Imaging profiles (was 13.3):** `radiology-dicom` and `pathology-wsi` default to `ec:2+1` when EC lands.
- **Phase-one done:** the acceptance sentence in OWNER-ANSWERS-2026-10-02 (recreate byte-identical from the durable
  tier alone after a site is destroyed and rebuilt from tape, suite exhaustive).

## 13. What I am unsure of

1. **The DIRECT-read cost of DM-1.** Two mounts per small tape recall instead of one is a real loss on a
   mount-bound plant, and SPECIFICATION §8.3 rated DIRECT reads highly. I chose DM-1 for D3 and
   operational simplicity, and E-DM1 is the gate. If the owner wants DIRECT reads regardless, DM-1b is
   the design, and its repack and forget become cross-site operations.
2. **Whether a per-site share of a block is "finer than the dedup block" under D3.** I read D3 as
   "repack never splits or partially moves a dedup block". Each site's share of a block is moved whole
   and only together with the block's liveness decision, so I believe DM-1 honours it. If the owner
   meant "every site holds whole dedup blocks", DM-1 is ruled out and DM-1b is forced.
3. **The built-in profiles.** Resolved (13a): `radiology-dicom` and `pathology-wsi` are `ec:2+1` (2026-10-14). No
   separate `durable-ec` profile: the default itself is ec:2+1.
4. **The commit point under tape-primary.** I propose commit at `f` on durable disk spool (9.4), with tape
   asynchronous. If "the durable tier alone" means nothing is committed until it is VERIFIED on tape,
   commit latency becomes hours, and the client protocol needs an async commit job.
5. **The small-block threshold** interacts with the format adapters, which cut kilobyte header blocks so
   that metadata edits stay small. Replicating those blocks is cheap in bytes but changes how their
   records are counted. The value and the rule are a test-bed call.
6. **N-DC11's reach.** I tied one copy to the `scratch` and `cache` retention classes **and**
   `durability=cache`. A user-defined class (for example, a 30-day "derived" class) cannot hold a single
   copy. It must use `cache` (whose TTL `core.retention op=define` may strengthen) or keep two copies.
   That is the strict reading of "R = 1 only for scratch or cache classes". Two narrower points stay
   open: redefining the built-in `cache` class with a floor is still allowed, and a legal hold on a
   one-copy collection is deliberately not refused, because a legal obligation overrides storage
   rules.
7. **Memory.** About 5 bytes more per block record (7) adds to the heap concern that N-DC6 already
   addresses.
8. **The codec's speed on the target hosts.** The existing codec does a log-table multiply per byte. A first
   single-thread measurement on this Mac (Apple M3 Max, JDK 21.0.5, `BlockShares` at 1 MiB and 4 MiB
   blocks) gave about 1.6 GB/s for RS(2,1) encode and degraded decode, 0.8 GB/s for RS(4,2) encode, and
   memory speed for a healthy decode, which is a concatenation. CodecBench (now with RS(2,1) and RS(3,1)
   cells) gave about 1.6 GB/s per core at 256 KiB to 2 MiB shares, and about 10.9 GB/s for RS(2,1) encode
   on 8 threads. That is well above one client's N-WAN target per core. It is not yet measured on the
   HPC or the site hosts. Section 11 keeps the acceleration question open until CodecBench runs there.
9. **Lowering a block's requirement (MS5; built as recommended 2026-10-08, see MS5; the default in effect).** The block table keeps reference counts, not holders, so when a
   collection moves to a weaker mode the engine cannot tell which other collections still reference a block
   without walking runs. Options: a sliced, cursor-resumed walk of the changed collection's runs that
   recomputes each block from every referencing run (a scan proportional to the data the change touches, plus
   finding the other referencers), or a small per-block count of references by redundancy class kept next to
   `refs` (a few bytes per record, O(1) to lower). I lean to the second; it is an owner and engineering call.
10. **Writes with a site down under `ec:2+1` (owner question, 2026-10-07; built as recommended 2026-10-08, see MS5; the default in effect: `core_place_min_shares=-1`).** With one of three sites down, should
   an `ec:2+1` write continue with two shares as recorded debt (readable, f = 0 until repair adds the third,
   as `core_place_min_copies` does for replicas), or be refused? Recommended: continue as debt behind a key,
   default as the deployment's `core_place_min_copies` (the standing deployment runs 2 of 3). `SharePlacer`
   implements both; the key is wired with encode-on-write (MS5).
