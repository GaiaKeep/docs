# Status at a glance

Every component with its label: **Proven**, **Built**, **Designed**, **Proposed** or **Open**
(see the [home page](../index.md) for definitions). Updated 2026-09-23 (night) at `GaiaKeep/gfs` `f055e07`.

!!! success "Durable storage core: on the fabric, every byte on the dataplane"
    **No file byte travels in a control message.** Clients stream over GKT, a reliable transfer on the
    Cresco dataplane: every chunk hashed and checked, a sliding window, selective acknowledgements and
    retransmission, RAM bounded per flow. Files move as several parallel flows, assembled on local disk.
    The index and the storage nodes exchange bodies as dataplane frames of up to 16 MiB. The engine
    streams with bounded memory, runs concurrently, and reads media directly.

    Tests: 324/324 unit tests, and 61/61 on a live fabric (crash, restart, node loss, replica agreement).

    Measured leg by leg on one Mac (7 JVMs, one SSD):

    | Leg | Result |
    |---|---|
    | Transport between index and storage nodes | ~300 MB/s per flow; ~1.0–1.2 GB/s inbound across 5 nodes |
    | Client upload | 420–490 MB/s |
    | Engine read on the index | up to ~700 MB/s |
    | Engine publish, 1 MiB blocks | 368 MB/s at R=1; 126–147 MB/s at R=3 |

    Five defects were found by these tests and fixed:

    - concurrent appends losing blocks: data loss;
    - a window counted in chunks exhausting the heap;
    - lost frames stalling reads;
    - three extra disk round trips per block read;
    - a thread leak.

    Decisions: [Module decisions](../design/MODULE-DECISIONS.md). The block-size decision is open for the owner.

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
| Replication with repair, scrub, trim and failure-domain placement | **Proven** on the fabric | 180-cell matrix; live: node killed, reads survive, repair restores |
| Erasure coding reached by repack | **Designed** | |
| Versions, runs, branches, extracts, citations | **Proven**: commits journaled and replicated through the index | JournalReplayTest; live F3, F5, F8 |
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
