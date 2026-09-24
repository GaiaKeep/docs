!!! success "Status: Current"
    The decisions each component raises, with the measurements behind them: 203 tests, 0 failures (2026-09-23).

# Module-level decisions

*2026-09-23. Every component in `COMPONENTS.md` is built and tested: **203 tests pass, 0 fail**
(83 module and engine tests, and a 120-cell integration matrix). The measurements below are from
`ModuleMeasurementsTest` and `IntegrationMatrixTest`, with raw data in `eval/results/modules/`. Host:
14-core Apple silicon, JDK 23, single machine. Every rate is a ceiling for this machine, not a
deployment figure, and macOS fsync is about 8× costlier than Linux node-local fsync
(`eval/results/fsync_cost.json`).*

Each decision is labelled **D-Cn-k** after its component. Where I have a recommendation it is marked
**Rec**, and accepting it is a valid answer.

## Status of every decision

Every decision below now runs on its recommended default. **These are adopted defaults, not owner
approvals:** each one is reversible, and each one stays open until the owner confirms or overrides it.

| Decision | Running default | Where it lives | Reversible by |
|---|---|---|---|
| D-C1-1 default chunker | `cdc:65536:8192:131072` | `ChunkerSpec.DEFAULT_CDC` | per-domain `chunker` at creation (existing domains keep theirs) |
| D-C1-2 16 KiB CDC per collection | offered, not default | any `cdc:` spec is accepted per domain | policy |
| D-C1-3 reject 256 KiB CDC | not a default; still accepted if asked | policy | policy |
| D-C2-1 default hash | SHA-384 (CNSA) | `BlockHash.DEFAULT` | per-domain `hash` at creation |
| D-C5-1 keyed ids | HMAC-SHA-384, 96 hex | `BlockCodec` | new domains only (ids are permanent) |
| D-C6-1 reference storage at scale | holder sets, in memory, journaled | `RefIndex` + journal | open: needs a decision before petabyte scale |
| D-C8-1 site weighting | `log10(measured write rate)` | `ReplicaPlacer` | code constant |
| D-C10-1 trim | surplus kept through a grace period, never below R | `StorageEngine.trim` | `grace_ms` per call |
| D-C10-2 sync at seal | one barrier per write per site | `FsBinding.seal` | built |
| D-C10-3 batched streaming reads | window of 64 blocks per site | `StorageEngine.readWindow` | field |
| D-C11-1 minimum replication | R ≥ 1 enforced; R=3 used everywhere tested | `PolicyEngine` | open: R ≥ 2 for durable collections is not yet enforced |
| D-C11-2 supported configurations | all tested combinations (now 180 cells incl. remote) | `IntegrationMatrixTest` | — |

## Summary of verdicts

| Component | Tests | Verdict |
|---|---|---|
| C1 Chunker | 18 | Correct at every size; content-defined chunking behaves as measured on edits |
| C2 Block hash | part of 6 | Known answers pass; SHA-384 is 1.67× slower than SHA-256 here |
| C3 Tenancy and policy | 7 (40+ matrix cells) | Every rule enforced; every refusal names its rule |
| C4 Keys | part of 6 | Derivations separated by tenant, domain and purpose; destroying a root destroys its keys |
| C5 Block codec | 10 | Shared modes converge, keyed domains separate, tampering refused, oracle rule holds |
| C6 References | 5 | Idempotent; agrees with a reference model across 50,000 random operations |
| C7 Versioning | 5 | Shadowing, tombstones, compare-and-set, stable ids and citations |
| C8 Placement | 7 | Constraints enforced, unsatisfiability explained, deterministic and weighted |
| C9 Bindings | 9 | Contract holds for RAM and filesystem. **Found and fixed:** MemBinding returned FAILED instead of REFUSED for a missing extent |
| C10 Engine | 16 | Every owner case and failure passes (below) |
| C11 Integration | 120 | Every option combination passes the full lifecycle |

**C10 behaviours verified end to end:**
- Composing public datasets stores **zero** blocks.
- A second tenant publishing the same public bytes stores **zero** blocks.
- Augmenting another tenant's 2 MB file with a 500-byte insert stores **1–4 blocks**.
- A revoked grant blocks reads immediately.
- Sealed tenants are refused references and grants in both directions, and copy public data in.
- Withdrawal honours PIN, COPY and BREAK, and reclaims exactly what nothing else references.
- R−1 site losses leave every version readable, and repair restores R copies.
- A corrupt replica is read around, and scrub repairs it.
- Durability fails closed on unattested RAM.
- A refused commit leaves only reclaimable garbage.
- Keyed domains never record a raw content hash.

## C1: chunker

32 MiB base, five edit workloads. Figures are blocks retained / new bytes that must be stored:

| Chunker | MB/s | Append 1 % | Insert 0.1 % | Prepend 0.1 % | Overwrite 20×4 KiB | 10 small inserts |
|---|---:|---|---|---|---|---|
| `fixed:65536` | 6,059 | 98.8 % / 328 K | 49.9 % / 16.0 M | **0.0 % / 32.0 M** | 96.1 % / 1.3 M | **9.0 % / 29.1 M** |
| `fixed:16384` | 8,819 | 99.0 % / 328 K | 49.9 % / 16.0 M | 0.0 % / 32.0 M | 99.0 % / 336 K | 9.1 % / 29.1 M |
| **`cdc:65536:8192:131072`** | 878 | 98.7 % / 442 K | **99.6 % / 161 K** | **99.6 % / 51 K** | 96.0 % / 1.9 M | **98.1 % / 606 K** |
| `cdc:16384:4096:65536` | 505 | 99.0 % / 355 K | 99.7 % / 70 K | 99.9 % / 46 K | 98.5 % / 729 K | 99.4 % / 279 K |
| `cdc:262144:32768:1048576` | 870 | 97.4 % / 570 K | 99.1 % / 423 K | 98.2 % / 229 K | 87.4 % / 6.2 M | 90.1 % / 4.4 M |
| `keyed-cdc:65536:…` | 869 | 98.9 % / 393 K | 99.8 % / 117 K | 99.6 % / 146 K | 96.1 % / 1.9 M | 98.1 % / 811 K |

In the integration matrix's version-2 workload, content-defined chunking reused **73 %** of blocks
against **54 %** for fixed blocks.

- **D-C1-1: default chunker.** **Rec: `cdc:65536:8192:131072`.** After a single insertion, fixed
  blocks have to store 100× more new data than content-defined ones, and after several small
  insertions about 50× more. It runs at 878 MB/s on one thread, which is 2.2× an LTO-10 drive.
- **D-C1-2: offer 16 KiB content-defined chunking per collection** for text-heavy collections with
  frequent small edits. It stores 2–3× less on edits, but produces 3.1× more blocks, so more index
  and reference entries, and runs at 505 MB/s. **Rec: allowed as a per-domain option, not the
  default.**
- **D-C1-3: reject 256 KiB content-defined chunking.** Scattered overwrites store 3.3× more than at
  64 KiB. **Rec: don't offer it.**
- Keying the chunker costs nothing measurable (869 against 878 MB/s). The sealed-tenant default
  stands.

## C2: block hash

| Hash | MB/s, one thread | Id bytes |
|---|---:|---:|
| SHA-256 | 3,008 | 32 |
| SHA-384 | 1,805 | 48 |

The hash choice has **no effect on deduplication** (reuse was 51.6 % with either across all 120
cells).

- **D-C2-1: default hash.** **Rec: keep SHA-384** (CNSA). It is 1.67× slower, but still 4.5× an
  LTO-10 drive on one thread. **Re-measure on the deployment host's CPU:** this laptop has SHA-256
  hardware acceleration, and the gap on an x86 server may be different.

## C5: codec

| Mode | Seal MB/s | Open and verify MB/s |
|---|---:|---:|
| NONE | 1,808 | — |
| COLLECTION | 1,180 | 1,131 |
| GROUP | 1,071 | 1,060 |
| GLOBAL | 1,179 | 1,229 |

Shared modes cost about 35 % more than NONE because they hash every block. That is the price of
deduplication and is well above media rates.

- **D-C5-1: keyed block ids are always HMAC-SHA-384**, 48 bytes (96 hex characters), even in a
  SHA-256 domain; GLOBAL ids are the domain's own hash. **Rec: keep it.** Ids stay uniform across
  keyed domains, and the keyed part is CNSA regardless of the content hash chosen. The alternative
  is to follow the domain's hash, which saves 16 bytes per id in SHA-256 domains.

## C6: reference index

- **D-C6-1: how references are stored at scale.** Today each block holds a *set of holder names*,
  so every operation is idempotent and the index agrees with a reference model across 50,000 random
  operations. That design is correct but can't be the representation at 10⁹ blocks: a string per
  reference, in memory. **Rec: keep the set semantics, store them as a counted table plus an
  append-only holder log in the federation index,** and design this before the index integration
  stage. This is `TENANCY-AND-DEDUP.md` §12 item 3, now blocking the next stage.

## C8: placement

- **D-C8-1: how much faster sites are favoured.** Placement weight is `log10(measured write rate)`.
  With a 375× speed difference, the test requires the fast site to take between 52 % and 90 % of single-copy placements, and it passes. The exact share wasn't recorded. An
  unmeasured site never outranks a measured one (tested). **Rec: keep the logarithmic weight;** a
  linear weight would put almost everything on the fastest site and concentrate failure risk.

## C10: engine findings

The engine is correct in every tested behaviour, and the measurements show where it is slow.
Publish and verified read of one 32 MiB file across 4 sites:

| Locus | Replication | Publish MB/s | Read MB/s |
|---|---:|---:|---:|
| RAM | 1–3 | 111–236 | 74–174 |
| Filesystem | 1 | 4.8–6.0 | 31–34 |
| Filesystem | 3 | **1.6–2.0** | 30–36 |

- **F-C10-1: extra copies are never trimmed.** When a site is down, repair re-replicates elsewhere to
  get back to R copies; when the site returns, the block holds more than R copies and nothing removes
  the surplus. Measured: at R=2 an average of **9.9 blocks per cell** were over-replicated after sites
  returned. **D-C10-1: trim policy.** **Rec:** keep the surplus through a grace period (a returning
  site may fail again), then trim back to R, never below, preferring to keep copies in distinct
  failure domains with the best measured health.
- **F-C10-2: filesystem publish is slow because it syncs to disk per block, serially.** `FsBinding`
  fsyncs on every `append`, and the engine writes to each site in turn. On macOS that is about 6 ms
  per 64 KiB block per copy. **D-C10-2.** **Rec:** move the sync to `seal()` (one barrier per write
  batch), which is what the interface's two-state write exists for, and write to sites in parallel.
  I expect this to improve filesystem publish by more than 10×; I'll measure after the change.
- **F-C10-3: reads go block by block through a staging file.** Each block is enqueued, written to a
  staging file, read back and deleted, and completion is polled. **D-C10-3.** **Rec:** request every
  block of a file from a site in one call, and add a streaming read path to the interface, as the
  "stream" requirement calls for.
- **F-C10-4: the engine is single-threaded** (its public methods are synchronized). That is correct
  and simple, and concurrency comes with the index integration stage. It is recorded, not proposed
  for now.

## C11: which configurations are supported

All 120 cells pass: every mode × {fixed, content-defined, keyed content-defined (keyed modes)} ×
{SHA-256, SHA-384} × R ∈ {1, 2, 3} × {RAM, filesystem}.

| Replication | Read with one corrupt copy | Read after scrub | Fewest copies after scrub |
|---|---|---|---|
| R=1 | 0 / 40, **refused, never wrong** | 0 / 40 | 0 for the corrupted block |
| R=2 | 40 / 40 | 40 / 40 | 2 |
| R=3 | 40 / 40 | 40 / 40 | 3 |

With R=1, corruption is **detected and refused**, never returned as data. Nothing is left to repair
from.

- **D-C11-1: the minimum replication policy.** **Rec: R ≥ 2 for any collection that counts as
  durable**, with R=1 permitted only for explicitly declared caches or recomputable derived data. The
  design of record is R=3.
- **D-C11-2: supported configurations.** **Rec:** declare all 120 tested combinations supported, with
  the defaults: content-defined 64 KiB, SHA-384, R=3. Keyed content-defined chunking is the default
  in sealed tenants.

## What comes next, once these are decided

1. Engine performance: D-C10-2 (sync at seal, parallel site writes) and D-C10-3 (batched and
   streaming reads), re-measured.
2. Over-replication trim (D-C10-1).
3. Reference storage at scale (D-C6-1), then wiring the engine into the federation index for quorum
   commit across hosts. That is the next integration stage.
4. Metadata-key IV discipline (S1), before any media is written.

## Update 2026-09-23 (afternoon): findings fixed, smoke test, benchmark, CI

The recommended defaults for D-C10-1, D-C10-2 and D-C10-3 were adopted and built. They stay
configurable. **208 tests, 0 failures**, on this machine and on CI.

| Finding | Fix | Before | After (same Mac) |
|---|---|---|---|
| F-C10-2: one fsync per block, sites written serially | `BlockStore.stage` / `commitStaged`: syncs run in parallel at `seal`, one directory sync per batch, sites sealed in parallel | disk publish at R=3: 1.6–2.0 MB/s | **46–78 MB/s** |
| F-C10-3: reads staged one block at a time | `readTo(OutputStream)`: windowed, one request per site per window, parallel across sites, authenticated per block, per-block fallback | verified disk read: 30–36 MB/s | **230–380 MB/s** |
| New (found by the benchmark): repair one block at a time | Plan first, one fetch per source site, one sealed write per target site, all in parallel | 72 copies/s | **~1,400–1,600 copies/s** |
| F-C10-1: surplus copies never trimmed | `trim(graceMs)`: after the grace period, down to R and never below, distinct failure domains first | never | tested; idempotent |
| New: a long domain id made every block unwritable (stores cap ids at 128 characters) | Block names hash long or unusual domain ids | — | tested |

**Versioning with deduplication (benchmark).** Ten successive versions of a file, each with a 0.1 %
insertion: the deduplicating modes stored **0.01 of the logical bytes** published, NONE stored **3.0**
(R=3).

### Decision D-C2-1, answered by an x86 host

The CI runner (Azure, Linux x86-64, 2 cores) measured **SHA-256 at 1,365 MB/s and SHA-384 at
613 MB/s**, a **2.2×** gap against 1.67× on Apple silicon. SHA-384 is still above one LTO-10 drive
(400 MB/s) on a single core, with less headroom than the laptop suggested. Hashing parallelises per
block, so a many-core server has room to spare. The recommendation to keep SHA-384 stands, now on
x86 evidence. The DGX run (job 221777) adds a server-class x86 figure.

### A measurement correction: JIT warm-up

The benchmark's first codec figure (269 MB/s) was a measurement artifact, not a regression. The
codec seals at **103 MB/s cold** and reaches **~1,100 MB/s after ~3,000 seals (~200 MB)** in the
same JVM, and JDK 21 and 23 are identical once warm. The benchmark now warms up the primitives and
the whole engine path before measuring, and reports steady state (1,043 MB/s), because a storage
server runs warm. The first ~200 MB after a process starts are slower, and that should be expected
after every restart.

### Tools

- `eval/gfs-core.sh smoke [dir] [fs|mem] [--attest]` runs 25 checks end to end on real sites and
  exits 0 or 1. It passes 25/25 on disk (3.4 s) and in RAM (0.5 s), and runs in every build.
- `eval/gfs-core.sh bench [...]` measures primitives, publish and read, versioning, repair and scrub,
  and writes JSON to `eval/results/bench/`.
- Both are classes in the bundle (`io.cresco.gfs.core.tools`), so they run on any deployment host.
- CI (`.github/workflows/test.yml`) runs the suite, the wire-contract lint, the smoke test and a
  small benchmark on every push, and uploads the results. The first run passed.

## Update 2026-09-23 (evening): on DGX servers

The smoke test and benchmark ran on DGX compute nodes via SLURM: job 221777 on dgx-03, then job
221810 on dgx-01 after the fixes below. Logs and JSON are in `eval/results/bench/dgx/`. Both are
x86-64 with 32 cores, JDK 21.

**Two defects the server found, both fixed:**

1. **The durability probe was a single timing pass.** On dgx-03 it classified one of four identical
   node-local directories INDETERMINATE and the other three COSTS_TIME: the first site probed ran on
   a cold JVM. The probe now warms up, runs five rounds alternating which pass goes first, and counts
   a locus durable only when **every** round agrees (`classifyRounds`). The per-round ratios are kept
   for audit. On dgx-01 all four node-local sites came back unanimous, and the smoke test passed
   25/25.
2. **The engine was CPU-bound on one thread.** On x86 each core is slower at this work (SHA-384
   718 MB/s, codec ~545 MB/s), and every block was hashed and encrypted serially. Per-block work now
   runs across cores, with the decisions that touch shared state kept sequential and in order.
   Domain keys are memoised, and the memo is cleared when a root is installed or destroyed.

**Correction:** with the unanimous probe, the DGX **shared project filesystem measured COSTS_TIME**
(13–14 MiB/s), contradicting the one-pass ×0.94 from 2026-09-19. It is admitted; its real cost is
speed, 10–18× slower than node-local storage.

**dgx-01, node-local disk (job 221810):**

| Mode | R | Publish MB/s | Verified read MB/s | Stored / logical (10 versions) | Repair copies/s |
|---|---:|---:|---:|---:|---:|
| NONE | 1 | 175 | 361 | 1.0 | — |
| NONE | 3 | 103 | 420 | 3.0 | 2,397 |
| COLLECTION | 1 | 140 | 380 | 0.00 | — |
| COLLECTION | 3 | 74 | 367 | 0.00 | 2,234 |
| GROUP | 3 | 76 | 380 | 0.00 | 2,464 |
| GLOBAL | 3 | 77 | 380 | 0.00 | 2,336 |

Against dgx-03 before the CPU fix, deduplicating-mode publish went from ~100 to **131–140 MB/s** at
R=1, and verified reads from 226–241 to **367–383 MB/s**. At R=3 the limit is now the disk syncs
(74–77 MB/s). In RAM on the same CPU, publish reaches 152–227 MB/s at R=1 and reads 396–472 MB/s.

**D-C2-1 on a server:** SHA-384 **718 MB/s** against SHA-256 **1,765 MB/s** per core, a **2.5×** gap
on x86 (1.67× on Apple silicon, 2.2× on the CI runner). Per core, SHA-384 is 1.8× one LTO-10 drive,
and hashing now runs across cores. **The recommendation to keep SHA-384 stands**, now on
server-class evidence, but it costs 2.5× on x86.

**What limits a single stream now:** content-defined chunking runs single-threaded per file at
~600 MB/s on x86. That is the next ceiling above one LTO-10 drive (400 MB/s). Several files publish in
parallel; one very large file does not yet.

## Update 2026-09-23 (night): the core on the fabric

The three outstanding items are closed or explicitly handed back.

**1. The engine runs across hosts, with agreement.** The storage core now runs inside the federation
index (`coresvc/CoreService`). The index is its journal and its replication.

- **One apply path.** Every persistent change is a `Delta` applied through `StorageEngine.apply`. That
  one function runs live, on replay after a restart, and on every replica, so the three cannot
  diverge.
- **Journaling.** Each operation's changes go out as one `core.batch` through the index's commit path.
  The batch is forced to disk before the operation returns, then shipped to the replicas.
  `statehash` now carries `core_hash`; snapshots carry the core too.
- **Storage nodes.** The index reaches them through `RemoteBinding`: the unchanged `ExtentBinding`
  contract over Cresco RPC. Each node serves its own `FsBinding` through `ExtentServer`, and only to
  the index that owns it.
- **Crash safety.** Before any seal, the blocks and sites a write is about to create are journaled as
  an *intent*. Recovery reclaims every copy an intent names that the index never recorded.
- **Tenant roots.** They leave memory only wrapped under `core_master_key`. Without that key the core
  does not start.

Evidence:
- JUnit 294/294. `JournalReplayTest` 12/12: replay and snapshot give an identical hash; a crash
  between seal and commit leaves no orphans; a refused seal cleans up; no root in the clear. The new
  REMOTE locus runs the binding contract and all 60 extra integration-matrix cells over the protocol.
- Live Cresco fabric, 9 JVMs, `eval/core_fabric_check.py`: **61/61**
  (`eval/results/core_fabric_20260923-180417.json`). Covered:
  - all four dedup modes, and v2 of a 3.5 MB file stores 234 KB at R=3;
  - cross-tenant GLOBAL dedup stores 0 blocks, and compose stores 0 bytes;
  - a grant-derived publish stores only the addition;
  - a sealed tenant is refused by rule;
  - the replica's hash equals the primary's;
  - no plaintext on any disk;
  - a storage node killed: every read survives, repair and trim work;
  - the index killed -9: the replayed hash equals the pre-crash hash, and dedup survives the restart;
  - the index halted between seal and commit: 1,128 sealed orphans are reclaimed from the journaled
    intent, leaving 1,125 files on disk = 1,125 recorded copies.

Found live and fixed:
- **A dead node stalled liveness.** The core's one timer thread blocked on an RPC to it. Fix: liveness
  sync gets its own thread, a timed-out node is quarantined at once, and control calls time out at 10 s.
- **An index restart marked every node LOST.** Replayed `last_seen` values were stale. That would
  also start the prototype's repair storm. Fix: each node gets a full grace window from start.
- **Control messages are capped at 1 MiB** by the websocket. Bulk bytes now arrive by chunked
  `core.upload`, and reads are ranged: `core.readrange` fetches only the covering blocks.

**Throughput through the fabric is low, and the cause is known.** One Mac running 9 JVMs, R=3:
engine publish 15–18 MB/s and engine read 59–78 MB/s. Bytes travel base64-encoded inside
control-plane MsgEvents. In-process on the same machine the engine does 568–604 MB/s. The fix is to
move the extent data onto the Cresco dataplane (FrameBus), as the prototype's fragment path does.
That is the next performance item.

**2. A single large file no longer caps at one core.**
- Parallel content-defined chunking is byte-identical to sequential (proven in `ChunkerTest`), and the
  whole-file hash overlaps the rest of the work.
- `MemBinding` usage is O(1): `describe()` had summed every stored extent on every placement call.
- One 1 GiB file publishes at **568–604 MB/s** (was 186).

**3. Decisions.** The table at the top records every decision as an adopted, reversible default, not
an owner approval. Two remain open and matter at scale: **D-C6-1** (reference storage) and
**D-C11-1** (enforce R ≥ 2 for durable collections).

Known limits, stated plainly:
- Core RPCs have no per-tenant authorization yet. Anyone holding the Cresco service key can call
  `core.*`, and tenant-level authorization is an open question.
- Per-block metadata is journaled at roughly 130 bytes per block, about 2 MB per GiB. Journal
  compaction exists only as snapshot install.
- The index keeps retained log entries in memory.

## Update 2026-09-23 (late): the data path, measured leg by leg

**No file byte travels in a control message.** Clients stream over GKT, a reliable transfer on the
Cresco client dataplane (per-chunk sha256, sliding window, selective acknowledgements, retransmit).
The index and the storage nodes exchange bodies as FrameBus dataplane frames, and a lost frame
retries the idempotent exchange. The engine streams with bounded memory, runs concurrently, and
reads directly from media that can (`readNow`).

Measured on one Mac: 7 Cresco JVMs of 512 MB heap each, sharing one SSD, R as stated
(`eval/core_throughput.py`, `eval/results/core_throughput_*.json`).

| Leg | Result |
|---|---|
| Index ↔ node, pure transport (no disk, no crypto) | ~300 MB/s per flow at ≥4 MiB messages; 540–580 MB/s multi-flow to one node; ~550 MB/s out / 1.0–1.2 GB/s in across 5 nodes |
| Client → index upload (8 flows × 1 MiB chunks, 16 MiB in flight per flow) | 420–490 MB/s, 0 retransmits |
| Engine read on the index (no client leg), 1 MiB blocks | 256–395 MB/s on 1 flow; 590–705 MB/s on 4–8 flows |
| Engine publish, 1 MiB blocks | **368 MB/s at R=1**, **126–147 MB/s at R=3** |
| Engine publish, 64 KiB blocks | 97 MB/s at R=1, 54 MB/s at R=3 |
| Client download to a local file (Python client, 8 flows) | 230–263 MB/s: the client leg, not the engine, is the limit |

Findings, all fixed and covered by tests:
- **Data loss.** Concurrent appends to one write dropped entries on the disk binding, so blocks behind
  a committed version were never sealed.
- **RAM.** An in-flight window counted in chunks, not bytes, exhausted a 512 MB heap. Windows are now
  a byte budget, enforced by both ends.
- **Stalls.** Lost non-persistent frames stalled reads for 15 s each; they now cost a retry.
- **Wasted I/O.** Every block read made three extra disk round trips through sink directories, and
  every seal re-read what it had just staged.
- **A thread leak** in the engine and disk-binding pools.
- **The "1 MiB cap"** was the Python websockets default `max_size`, not the server (which allows 1 GiB)
  or the broker (128 MiB). The pycrescolib dataplane now accepts 64 MiB.

**Decision for the owner: D-C1-1 block size.** 1 MiB content-defined blocks publish about 3× faster
than 64 KiB (368 against 97 MB/s at R=1) and cut per-block metadata 16×. The cost: an edit stores
about 1–2 MiB instead of about 64–128 KiB. For petabytes of imaging, 1 MiB is the recommended default.
It is available per domain today (`chunker=cdc:1048576:262144:4194304`); the global default is
unchanged pending the owner's confirmation.

Next:
- Pipelined ingest (publish while parts arrive). End-to-end ingest today is upload then publish:
  196 MB/s at R=1, 98–113 MB/s at R=3.
- A Java client measurement of downloads.
- Physical R=3 on separate hosts: three copies on one laptop SSD is not a deployment figure.
