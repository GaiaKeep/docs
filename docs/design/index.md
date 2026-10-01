# Design record

The engineering documents behind this site, copied from `GaiaKeep/gfs` `docs/` with a status banner on each. **Where a design document disagrees with the Concepts pages, the Concepts pages and the [Decision log](../roadmap/decisions.md) are current.** These documents are working records: dense, exhaustive and argued in detail.

| Document | Status | What it is |
|---|---|---|
| [Format-aware dedup adapters](FORMAT-ADAPTERS.md) | Current | Audited DICOM, NIfTI and TIFF cut adapters: metadata edits do not rewrite bulk data (shipped in 1.3, 2026-10-01). |
| [Jobs and the API](JOBS-AND-API.md) | Current | Async jobs, striped ingest with a short commit, history, have-checks, extracts and profiles (shipped in 1.3, 2026-10-01). |
| [The replicated core log](CORE-LOG.md) | Current | The Raft core log: record format, group commit, snapshots and failover (shipped in 1.3, 2026-10-01). |
| [Pack container format](PACK-FORMAT.md) | Current | The storage-node container format: fixed blocks, sealed records and repack (shipped in 1.3, 2026-10-01). |
| [Tape simulation](TAPE-SIMULATION.md) | Current | The LTO-class tape simulator and mhVTL test setup behind the tape benchmarks. |
| [From-scratch decision](FROM-SCRATCH-DECISION.md) | Current | The statement of purpose and the decision to remove Bareos (2026-09-20) |
| [Module decisions (measured)](MODULE-DECISIONS.md) | Current | The decisions each component raises, with the measurements behind them |
| [Component definitions](COMPONENTS.md) | Current | Every component of the durable storage core: interface, what its tests must establish, the decision it feeds. |
| [Tenancy and deduplication](TENANCY-AND-DEDUP.md) | Current | Design of record for tenants, collections, dedup domains (NONE, COLLECTION, GROUP, GLOBAL), grants and per-block hashing (2026-09-23) |
| [Block fabric specification](SPECIFICATION.md) | Partly superseded | The write-once block fabric specification, written tape-first |
| [Entail: the agent interface](ENTAIL-AGENT-NATIVE-FS.md) | Partly superseded | The agent-native interface: prospect/realise, Derivations, Coverage, extracts |
| [Storage bindings decision](STORAGE-BINDINGS-DECISION.md) | Mostly current | The one-interface-many-media binding decision and its findings table |
| [Storage direction (history)](STORAGE-DIRECTION.md) | Historical record | The working note that took the design from a tape assessment to the agent-native fabric |
| [Bareos analysis (historical)](BAREOS-RECOMMENDATION.md) | Superseded | Superseded 2026-09-20: Bareos is out. Kept because its licence analysis is what led to that decision, and because its reading of the Bareos source remains accurate. |
| [Tape research brief](TAPE-RESEARCH-PROMPT.md) | Historical record | The research brief for the three-site LTO-10 tier |
| [Storage research brief](RESEARCH-PROMPT.md) | Historical record | The deep-research prompt on federated archival storage. |
| [Prototype system report](SYSTEM-REPORT.md) | Proven (prototype) | How the September prototype works and how we know it works: 59/59 claims |
| [Prototype core principles](CORE-PRINCIPLES.md) | Proven (prototype) | The prototype's principles and architecture (2026-09-17). |
| [Evaluation plan](EVALUATION-PLAN.md) | Proven (prototype) | Every evaluation check with its method, pass criterion and status. |
| [Running the prototype](PROTOTYPE.md) | Proven (prototype) | How to build, run and evaluate the prototype locally. |
| [Prototype results](RESULTS.md) | Proven (prototype) | Functional results: 99/99. |
| [Scale results (full)](SCALE-RESULTS.md) | Proven (prototype) | Full scale and performance tables. |
| [Claims registry](CLAIMS.md) | Proven (prototype) | The mechanical claims check: 59/59. |
| [Original plan (2026-09-13)](global-federated-storage-plan.md) | Historical record | The starting plan: federated sharing with an opt-in durability tier. |
