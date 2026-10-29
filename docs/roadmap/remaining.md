# Remaining work

The order is deliberate: **durable storage first, then the live tier (the caching tier of earlier plans),
then scale-out**, with a stability gate before the large-scale test. Pieces
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
hold a verified share or copy; one site is lost; the exact version is reconstructed and streamed elsewhere,
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
- [x] `realise` to a live node, every file verified; `prospect` with commit state, size, tape-only bytes, fit and a strategy (the live tier, 2026-10-28, development branch)

**Redundancy**

- [x] 3-way replication across three sites, with the existing loss detection, repair, scrub and audit reused
- [x] Erasure coding `ec:2+1`, one stripe per dedup block, the default for new collections since 2026-10-14; `replicas:R` and `single` per dataset; mode changes in place (`core.redundancy op=set`)
- [x] Coded blocks with tape as the primary tier: each site's share archived, a coded version commits on VERIFIED
- [ ] Erasure coding measured on the HPC cluster and site hosts; its crash cells with three core peers and on packed stores; a lost site rebuilt from tape with coded blocks
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
- [x] ~~Per-object wrapping key for the site-key wrap~~: the site key went with the prototype path, retired 2026-10-08

## Phase 2: the live tier

The advanced caching tier of earlier plans, built as [the live tier](../concepts/live-tier.md) on the
development branch (2026-10-28). See [The caching tier, now the live tier](caching-tier.md).

- [x] Journaled inventory, its feature gate, and the guards that keep live copies from ever counting
- [x] `realise`, `prospect`, holds (lease, extend, pin), drops, admissions; sealed node streams; the live node's store
- [x] Every deletion trigger reaches live copies and ends on a signed attestation, with evidence in the lifecycle record
- [x] Clients (Java, Python, command line, MCP), local copies first, workspaces published as new versions
- [x] filerepo as a client of the live node; a live node on the test deployment; the dashboard's Live tier page
- [x] Tested: about 250 unit and cluster tests, the model-based test in every CI run, the end-to-end checks and crash cells on the HPC test bed (2026-10-28)
- [ ] The E18 gate on the final build, and the 72-hour soak (**in progress**)
- [ ] Merge to `main` and a release
- [ ] Realise throughput: 192–206 MB/s on 4 flows is well below the node leg; where the time goes is not yet measured
- [ ] A realise staged from tape, measured on the test bed
- [ ] A FORGET end to end on the test bed (it needs a second tenant administrator bound for 7 days)
- [ ] The two chaos faults not injected yet: a live root removed underneath a node, and node clock skew

## The stability gate before the FABRIC test

> "This system must be stable. Once we prove it on [the HPC cluster], we will move to a much larger scale
> FABRIC test." (owner, 2026-10-28)

The gate (evaluation plan E18): the live tier's unit tests, the model-based test, the crash cells, the chaos
cases LT-C1 to LT-C5 and the end-to-end checks pass **on the same build**, and a 72-hour soak meets its
criteria. That build and its configuration are what the FABRIC test deploys. See
[Test results](../built/tests.md#the-live-tier-and-stability-e18-2026-10-28).

- [x] Planned stops: a stopping peer refuses with directions and hands over; no client call fails (local, 2026-10-28)
- [x] A slow disk never costs the leadership; a capped unsynced backlog; a stuck disk hands over only to healthy peers
- [x] A write survives a store restarted under it; a signed departure notice fenced to the node's boot
- [ ] The chaos stage with live load on the HPC test bed, including planned stops there (**in progress**)
- [ ] The 72-hour soak (**in progress**)
- [ ] A call not safe to send twice, sent to a peer at the instant its process exits, still gets no reply; a `request_id` on the remaining verbs that lack one would close it

## Phase 3: scale-out

- [ ] Codes for a fourth site (RS(3,1) across four sites uses 11.1 % less media than RS(2,1) across three), and an intra-volume code on tape
- [x] RAM binding (`MemBinding`)
- [ ] Raw NVMe and raw disk bindings
- [x] Global deduplication for public data across tenants
- [ ] Moving computation to data (`realise` with a remote locus), integrated with SLURM
- [ ] Hardware key custody (HSM) and a FIPS 140-3 validated module for DoD fielding
- [x] Multi-host deployment on the HPC cluster (hub and dynamic mesh) and wide-area emulation
- [ ] Partner sites

## Carried from the prototype

- [ ] W-GFS-2: per-tenant fair scheduling in Cresco
- [ ] W-GFS-3: storage frames published to another tenant's dataplane topic (needs a Cresco dataplane API extension)
- [ ] filerepo audit items FR-D1, D3, D4, D6 and D7
