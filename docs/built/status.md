# Status at a glance

Every component with its label: **Proven**, **Built**, **Designed**, **Proposed** or **Open**
(see the [home page](../index.md) for definitions). Updated 2026-09-23 at `GaiaKeep/gfs` `b616948`.

!!! success "Durable storage core: built and tested"
    All eleven components are built under `io.cresco.gfs.core` (in-process, all I/O through `ExtentBinding`): **203 tests, 0 failures**, including a 120-cell integration matrix. Decisions with their measurements: [Module decisions](../design/MODULE-DECISIONS.md).

## Foundation

| Component | Status | Evidence |
|---|---|---|
| Cresco mesh transport, identity, tenant isolation | **Proven** | Cresco 1.3; control RPC p99 0.72 ms during a 444 MB/s flood |
| Cresco fixes found by this work (W-GFS-1, 4, 5, 6) | **Proven**, shipped in the Cresco 1.3 agent | [The prototype](prototype.md) |
| `io.cresco.gfs` plugin, roles index, storage and publisher | **Proven** | 99/99 functional checks |
| Journaled federation index with a read-only replica | **Proven** | 10⁶ files; replica state hash identical |
| Publication by delta, including deletes | **Proven** | E3 |
| Projects, owners, delegates, members; grants enforced at the origin | **Proven** | E4, E5 |
| Monitoring: dashboard Storage tab, pushed state beacon | **Proven** | D1 |

## Durable storage

| Component | Status | Evidence / note |
|---|---|---|
| Encrypt-then-erasure-code across sites, blind holders, keyless repair, scrub | **Proven** (prototype shape) | E6–E8, storm tests |
| Shamir t-of-n site-key custody with an approver quorum | **Proven** | E9 |
| Reciprocity ledger (entitlement follows contribution) | **Proven** | E10 |
| Real fsync durability barrier in the block store | **Built** | `dd6328a`; measured cost |
| Replication with repair, scrub and failure-domain placement (in-process engine) | **Built**, 120-cell matrix | R−1 site loss survivable in every cell |
| Erasure coding reached by repack | **Designed** | |
| Versions, runs, branches, extracts, citations | **Built** (in-process; quorum commit via the index is next) | VersionTest, engine tests |
| Derivations | **Designed** | |
| Tenant / collection / deduplication domain model, grants | **Built** | PolicyEngineTest (every rule), engine owner cases |
| Per-block hashing and domain-dependent block identity and keys | **Built** | BlockCodecTest; oracle rule holds end to end |
| Chunkers: fixed, content-defined, keyed content-defined | **Built** and measured | content-defined 64 KiB recommended (D-C1-1) |

## Placement and media

| Component | Status | Evidence / note |
|---|---|---|
| `ExtentBinding` interface and filesystem binding | **Built** | BindingTest 23/23 |
| New engine does all I/O through the interface | **Built** | the prototype's live plugin path still calls the store directly |
| Placement from measured write rate | **Built**, on the live placement path | `2842891`; wire-contract lint |
| Fail-closed durability barrier in placement | **Built**, on the live placement path | `fc5d81b`; BarrierTest 13/13 |
| Retention floors and refusing `reclaim` | **Built** | `a3b7d0f` |
| Properties with a recorded basis; media labels banned from placement | **Proposed** | A1, A2 |
| Tape plant simulator and mount scheduler | **Built** | `SimPlant`, `PlantScheduler` |
| Media-life admission rule | **Built** | `a3b7d0f` |
| Raw SCSI tape binding (`st`/`sg`) | **Designed** | Bareos removed |
| Independent on-media reference reader | **Designed**; blocking before media | |
| RAM binding (`MemBinding`) | **Built**, contract-tested | |
| Raw NVMe and raw disk bindings | **Designed** | |

## Security

| Component | Status | Evidence / note |
|---|---|---|
| Counter discipline for per-object keys (`SegmentCipher`) | **Built** (no production caller yet) | IvDiscipline 14/14 |
| Confirmation-oracle lint | **Built** | OracleLint, both controls |
| Live encode path key/IV use | **Verified safe** | fresh key per encode, stripe counter |
| Site key wrap: random IV, no rotation | **Known issue**, minor | Fix proposed |
| Metadata key (`K_meta`) IV discipline | **Open**, blocking before media | To be redone under the dedup model |

## Hardware

| Item | Status |
|---|---|
| Tape library: Spectra Stack first, Cube later | **Decided** (owner) |
| LTO-10 LA or PA media | **Proposed**: PA, subject to WORM availability and price |
| Sites: three, 3-way replication | **Decided** (owner, sites chosen later) |
| Per-site host (1U, NVMe spool, HBA) | **Proposed** |
| Mount cycle measured on a real drive | **Open**, blocking before media |

## Caching tier

| Item | Status |
|---|---|
| filerepo as the local cache and publisher of new versions | **Decided** (owner); basic materialisation **Built** on filerepo branch `phase0-crypto-baseline` |
| Advanced caching tier | **Designed**, deliberately **after** durable storage; see [The caching tier](../roadmap/caching-tier.md) |
