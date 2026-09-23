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
| 2026-09-19 | Not for humans: built for agents to store, version and protect data | Owner | In force |
| 2026-09-19 | No filesystem, no LTFS: the system manages its own blocks | Owner | In force |
| 2026-09-19 | Bareos adopted as the tape volume manager | Design | **Superseded** 2026-09-20 |
| 2026-09-19 | Deduplication and content-derived block ids retired (checkpoints share no blocks) | Design | **Superseded**: never owner-approved; reversed 2026-09-23 |
| 2026-09-19 | Content chunking at fixed 64 KiB | Design | **Open again** under the dedup requirement |
| 2026-09-19 | Per-object keys; GCM counter discipline (`SegmentCipher`) | Design | In force for sealed data |
| 2026-09-19 | No plaintext-derived identifier on write-once media | Design | **Becomes policy**: mandatory in sealed domains, relaxed in global |
| 2026-09-20 | Write-once is not hard and fast; things must be removable; group and repack over time | Owner | In force |
| 2026-09-20 | Store petabytes of radiology and pathology imaging | Owner | In force |
| 2026-09-20 | LTO-10 media type (LA 30 TB / PA 40 TB) is a purchase parameter | Owner | In force |
| 2026-09-20 | Start with a Spectra Stack; a few PB at first; replicate while better encoding is developed | Owner | In force |
| 2026-09-20 | 3-way replication across three sites; erasure coding later via repack | Owner + design | In force |
| 2026-09-20 | One general solution across memory, NVMe, spinning disk and tape; the data is raw | Owner | In force |
| 2026-09-20 | Build from scratch, or with permissively licensed libraries only | Owner | In force |
| 2026-09-20 | Bareos removed: its AGPL licence forbids streaming integration; raw SCSI over `st`/`sg` instead | Design, on owner's licence rule | In force |
| 2026-09-20 | Tape is one binding among many: "just a block of data" | Owner | In force |
| 2026-09-23 | Placement uses measured properties; durability fails closed | Design | In force |
| 2026-09-23 | Block-level deduplication is critical | Owner | In force |
| 2026-09-23 | Deduplication configurable from complete isolation to global; tenant = legal entity; collection = versioned dataset with compliance rules; hash every block before storage | Owner | In force; mechanism **Proposed** |
| 2026-09-23 | filerepo = local copies, cache, and publishing new versions; advanced caching tier after durable storage | Owner | In force |
| 2026-09-23 | Code lives in `GaiaKeep/gfs` only; `CrescoEdge/gfs` removed (archived pending deletion) | Owner | In force |
