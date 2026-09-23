# Design record

The engineering documents behind this site, copied from `GaiaKeep/gfs` `docs/` with a status banner on each. **Where a design document disagrees with the Concepts pages, the Concepts pages and the [Decision log](../roadmap/decisions.md) are current.** These documents are working records: dense, exhaustive and argued in detail.

| Document | Status | What it is |
|---|---|---|
| [From-scratch decision](FROM-SCRATCH-DECISION.md) | Current | The statement of purpose and the decision to remove Bareos (2026-09-20) |
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
