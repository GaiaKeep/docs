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
