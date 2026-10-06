# Remaining work

The order is deliberate: **durable storage first, then the caching tier, then scale-out**. Pieces
that looked finished and had never run end to end produced most of this month's defects, so each
phase ends with an end-to-end proof rather than unit tests alone.

## Phase 0: decisions (now)

Nothing in phase 1 can be specified exactly until these are answered. See
[Open questions](open-questions.md).

- [x] **Tenant / collection / deduplication domain** model: design of record written 2026-09-23; open choices are policy settings with defaults
- [x] **Chunking**: a per-domain setting (content-defined by default)
- [x] Redo **S1**, the metadata-key IV discipline, under the dedup model
- [ ] Choose the **first consumers** and the **first dataset** (P1, P2); proposed: the panAtlas index
- [ ] Decide whether the **HPC copy is kept** after archiving (P3); this decides whether two sites could ever suffice
- [x] **Hash function**: SHA-384 by default, fixed per domain
- [ ] **Java toolchain** for raw SCSI: JDK 22+, JNA or a C helper
- [ ] Record-the-basis locus properties and banning media labels from placement (A1, A2)

## Phase 1: durable storage core

!!! success "Shipped as release 1.3 (2026-10-01)"
    The durable storage core is built, tested and validated on the HPC cluster: 2,188 automated tests green
    in CI, and the secured live fabric check 88/88 on the HPC cluster. It covers per-tenant authorization on
    every verb, a Raft-replicated core with journal compaction, striped ingest with a short commit,
    chain replication, format-aware dedup and pack containers. See [Release 1.3](../built/release-1-3.md).

    Remaining in this phase:

    - faster reads over long round trips (80 ms and more): deeper read-ahead, or reads spread across replicas;
    - fewer spurious retransmits on slow links whose queues outlast the retransmit timer;
    - the tape items below that need a real drive.

**Goal:** an agent publishes a versioned dataset into a collection under policy; three sites each
hold a verified copy; one site is lost; the exact version is reconstructed and streamed elsewhere,
hash-verified, with no human action.

**Placement and bindings**

- [x] Route the live write and read paths through `ExtentBinding`; nothing depends on the current direct path
- [ ] Locus properties with a recorded basis; media labels as telemetry only
- [ ] Remaining locus properties: per-access setup cost, removability, volatility, reclaim granularity and latency, wear in native units
- [ ] Policy as constraints plus scoring; explicit behaviour when a policy can't be satisfied
- [x] HPC storage nodes moved to node-local `store_dir`

**Blocks and governance**

- [x] Tenant, collection and dedup-domain records in the index; per-collection policy
- [x] Hash every block before storage; derive block identity and key per domain
- [x] Sealed-domain encryption on `SegmentCipher`; shared and global domains on per-block derived keys
- [x] Grants and cross-collection / cross-tenant references, with withdrawal terms
- [x] Reference counting for shared blocks

**Versioning**

- [x] Versions, runs and branches with quorum commit
- [x] Extracts with deterministic selectors, citation ids, and pin-amplification refusal
- [ ] Streaming `realise` with per-block verification; `prospect` with costed options

**Redundancy**

- [x] 3-way replication across three sites, with the existing loss detection, repair, scrub and audit reused
- [x] Retention classes at write time; garbage collection as a budgeted, refusable obligation
- [x] Repack with the rewrite rule (preserve counters and copy bit-for-bit, or re-key)

**Tape (in parallel, gated by hardware)**

- [ ] Measure the mount cycle, rewind and the minimum streaming speed ("shoe-shine" floor) on the Stack
- [x] Raw SCSI tape binding over `st`/`sg`: built and tested against virtual drives (mhVTL)
- [ ] The same binding on a real drive
- [ ] Specify the on-media format and write the **independent reference reader** (blocking before any real cartridge)

**Security (before media)**

- [x] Metadata-key IV discipline (S1, redone under the dedup model)
- [x] Idempotency-key lease (S2); lint banning direct low-level encrypt calls (S3)
- [ ] Per-object wrapping key for the site-key wrap

## Phase 2: the advanced caching tier

After durable storage is complete. See [The caching tier](caching-tier.md).

## Phase 3: scale-out

- [ ] Erasure coding reached by repack (RS(3,1) across four sites uses 11.1 % less media than RS(2,1) across three)
- [ ] Raw NVMe, raw disk and RAM bindings
- [x] Global deduplication for public data across tenants
- [ ] Moving computation to data (`realise` with a remote locus), integrated with SLURM
- [ ] Hardware key custody (HSM) and a FIPS 140-3 validated module for DoD fielding
- [x] Multi-host deployment on the HPC cluster (hub and dynamic mesh) and wide-area emulation
- [ ] Partner sites

## Carried from the prototype

- [ ] W-GFS-2: per-tenant fair scheduling in Cresco
- [ ] W-GFS-3: storage frames published to another tenant's dataplane topic (needs a Cresco dataplane API extension)
- [ ] filerepo audit items FR-D1, D3, D4, D6 and D7
