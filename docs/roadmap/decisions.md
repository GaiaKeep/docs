# Decision log

Decisions in date order. **Superseded** entries are kept so readers of the design record can see
what changed and why.

| Date | Decision | By | Status |
|---|---|---|---|
| 2026-09-13 | Federated sharing with an opt-in durability tier; data stays where it is; filerepo is the file primitive, a new gfs plugin coordinates | Owner | Foundation of the prototype |
| 2026-09-17 | Tenant isolation is mandatory; cross-site flows must be explicit | Owner | In force |
| 2026-09-18 | Tape (Spectra Cube) assessed as a backend; an S3 front end recommended | Design | **Superseded**: no S3/Hugging Face compatibility; own protocol |
| 2026-09-18 | Programmatic, two-phase access for agents; per-request audited credentials | Owner | In force |
| 2026-09-18 | Reads versioned, writes quorum-confirmed; extracts are point-in-time versions | Owner | In force |
| 2026-09-19 | Do not adopt the Hugging Face protocol: its client can't represent offline data (measured) | Design | In force |
| 2026-09-19 | Not for humans: built for agents to store, version and protect data | Owner | **Refined** 2026-10-02: agents stay primary; rich human dashboards wanted |
| 2026-09-19 | No filesystem, no LTFS: the system manages its own blocks | Owner | In force for the durable media; **refined** 2026-10-27: the live tier gives programs a real file system of a committed version's files near compute |
| 2026-09-19 | Bareos adopted as the tape volume manager | Design | **Superseded** 2026-09-20 |
| 2026-09-19 | Deduplication and content-derived block ids retired (checkpoints share no blocks) | Design | **Superseded**: never owner-approved; reversed 2026-09-23 |
| 2026-09-19 | Content chunking at fixed 64 KiB | Design | **Superseded** 2026-09-23: per-domain chunker |
| 2026-09-19 | Per-object keys; GCM counter discipline (`SegmentCipher`) | Design | In force for sealed data |
| 2026-09-19 | No plaintext-derived identifier on write-once media | Design | **Becomes policy**: mandatory in sealed domains, relaxed in global |
| 2026-09-20 | Write-once is not hard and fast; things must be removable; group and repack over time | Owner | In force |
| 2026-09-20 | Store petabytes of radiology and pathology imaging | Owner | In force |
| 2026-09-20 | LTO-10 media type (LA 30 TB / PA 40 TB) is a purchase parameter | Owner | In force |
| 2026-09-20 | Start with a Spectra Stack; a few PB at first; replicate while better encoding is developed | Owner | In force |
| 2026-09-20 | 3-way replication across three sites; erasure coding later via repack | Owner + design | **Superseded** 2026-10-02: erasure coding is the default |
| 2026-09-20 | One general solution across memory, NVMe, spinning disk and tape; the data is raw | Owner | In force |
| 2026-09-20 | Build from scratch, or with permissively licensed libraries only | Owner | In force |
| 2026-09-20 | Bareos removed: its AGPL licence forbids streaming integration; raw SCSI over `st`/`sg` instead | Design, on owner's licence rule | In force |
| 2026-09-20 | Tape is one binding among many: "just a block of data" | Owner | In force |
| 2026-09-23 | Placement uses measured properties; durability fails closed | Design | In force |
| 2026-09-23 | Block-level deduplication is critical | Owner | In force |
| 2026-09-23 | Deduplication configurable from complete isolation to global; tenant = legal entity; collection = versioned dataset with compliance rules; hash every block before storage | Owner | In force |
| 2026-09-23 | Design of record: four dedup modes (NONE, COLLECTION, GROUP, GLOBAL), sealed tenants, grants with withdrawal terms, per-block keys in shared modes; unmade choices become policy with defaults ([TENANCY-AND-DEDUP](../design/TENANCY-AND-DEDUP.md)) | Design, on owner direction | In force |
| 2026-09-23 | Fixed 64 KiB content chunking | Design | **Superseded**: chunker is a per-domain setting |
| 2026-09-23 | filerepo = local copies, cache, and publishing new versions; advanced caching tier after durable storage | Owner | In force; built as the [live tier](../concepts/live-tier.md) (2026-10-28) |
| 2026-09-23 | Code lives in `GaiaKeep/gfs` only; `CrescoEdge/gfs` removed (archived pending deletion) | Owner | In force |
| 2026-10-02 | Phase one is three identical sites; the default redundancy is erasure coding across them (RS(2,1)-style, 1.5x, survives any one site); durability is per-dataset policy, and all three modes (erasure-coded, three replicas, single copy for scratch or cache only) are supported and tested | Owner | In force; built, `ec:2+1` the default since 2026-10-14 |
| 2026-10-02 | Tape is the primary durable tier, not a backup: the durable tier alone must recreate any dataset and survive the loss of a site; the HPC cluster copy is uncontrolled cache | Owner | In force; built on simulated tape (2026-10-03/04): placement targets tape and a verified tape copy counts |
| 2026-10-02 | Classes can be marked WORM (keep-forever records; never human-subject data); tape volumes are grouped by retention cohort so they die whole | Owner | In force; built (2026-10-02, extended 2026-10-08) |
| 2026-10-02 | A legal order to delete always wins: a multi-stage approved path overrides WORM, retention floors and citation pins; maximum-retention classes; quick and deep delete; a withdrawn cited version keeps a stub and gains an alternate version | Owner | In force; built (2026-10-02, extended 2026-10-08); physically destroying real cartridges is still open |
| 2026-10-02 | One configurable crypto facade across GaiaKeep and Cresco, aligned by FIPS level; drive hardware encryption is a setting (default declined); logical block protection (CRC32C) adopted on tape | Owner | In force; built in part: one fabric-wide crypto policy (2026-10-16), the drive-encryption setting, CRC32C on the tape simulator |
| 2026-10-02 | Expensive tunables (tape block size, error recovery, fencing) are decided by the simulation and the test bed, never by declaration; hardware is bought once simulation gives confidence | Owner | In force |
| 2026-10-02 | Rich human dashboards: where data is and how it is working, down to the block, location and tape type | Owner | In force; a read-only [storage dashboard](../dashboard/index.md) is built; controls and further views to build |
| 2026-10-02 | The documentation is licensed CC BY 4.0 | Owner | In force |
| 2026-10-02 | Erasure coding uses one dedup block per stripe (keeps block-level dedup and keeps repack, forget and scrub within a site); a fixed stripe width with placement groups so it scales to more sites; the default stripe shape is confirmed by simulation before any hardware | Owner | In force; built (one stripe per block, placement groups); the simulation of the stripe shape's read cost is open |
| 2026-10-02 | A durable dataset's ingest is committed only when its copies are verified on tape; the disk staging area never counts as a durable copy; the client submits and then awaits the commit job | Owner | In force; built (a commit job, reads answer `COMMITTING` until then) |
| 2026-10-02 | Phase one is done when, on three simulated sites with many drives and tapes, any dataset is recreated byte-identically from the durable tier alone after a site is destroyed and rebuilt from tape, with the durable-tier suite passing exhaustively | Owner | The finish line for the prototype |
| 2026-10-02 | The large-imaging profiles (radiology, pathology) default to erasure coding once the engine lands; full replicas remain selectable per dataset | Owner | In force; built (2026-10-14) |
| 2026-10-02 | Scale is a correctness gate: if something does not work at scale, it is not a reasonable solution. No design may need a full scan of the data or the audit, or grow its per-operation cost with sites, datasets or blocks; enforcement goes by index or cursor | Owner | In force; standing rule |
| 2026-10-02 | A legal order is proposed by a system administrator and needs at least two distinct approvers, one of them a system administrator, then a 24-hour lock | Owner | In force; built |
| 2026-10-02 | A collection's maximum retention may be extended or removed, but only through the approved override path (tenant and system administrators), never by an ordinary change | Owner | In force; built |
| 2026-10-02 | An ordinary deletion of data a published citation includes is allowed: the citation keeps a verifiable stub where the data was and points to an alternate version without it | Owner | In force; built |
| 2026-10-25 | `main` is the development branch of every repository; `1.3` is the release branch and moves only by fast-forward to a `main` commit whose CI passed | Owner | In force |
| 2026-10-27 | The caching tier is now called the live tier: committed data as native files near compute, never counted toward durability | Design, on the owner's decisions | In force; built |
| 2026-10-27 | Live copies are unencrypted native files: "the durable tier is the only thing that is not native". The core keeps a journaled inventory so that every deletion reaches them | Owner | In force; built |
| 2026-10-27 | No early copy: nobody, the writer included, reads a version from the live tier before it commits | Owner | In force; built |
| 2026-10-27 | filerepo is a client of the live node, never a storage binding; its unmerged `phase0-crypto-baseline` commit is rebuilt on filerepo's main line instead of merged | Default taken under the owner's delegation | In force; built |
| 2026-10-28 | The live tier needs only a quorum of the core: a core peer that is down counts by its last answer, so copies, extends and pins continue through a core restart or a site roll; drops are never blocked | Owner | In force; built |
| 2026-10-28 | A live node still starting, whose host checks wait only for its own agent, answers retryable rather than refused | Owner | In force; built |
| 2026-10-28 | Stability before scale: the system is highly tested (tests, evaluation, chaos cases) and proven stable on the HPC cluster before a much larger FABRIC scale test | Owner | In force; the E18 gate, in progress |
