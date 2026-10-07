# FUTURE_SOTA — GaiaKeep as a Global Computational Storage Fabric for Autonomous Agents

**Status:** future-state design input · 2026-10-04
**Author:** agent session (Kilo/GLM, for codybum), synthesising the two reference blueprints ("Architectural Evaluation and Strategic Blueprint for Next-Generation Agent-Based Storage Systems" and "Architecture and Governance of Global-Scale Distributed Memory and Dataset Storage for Autonomous Edge Compute Networks"), the verified production state of GaiaKeep, and the filerepo / panAtlas / myAtlas assets.
**Companion documents:** `REMEDIATION-PLAN.md` (MS6 spec, owner decisions), `MAIN.md` (verification campaign), gfs#7/#8 (owner decisions recorded).

---

## 0. Where we are — verified, not aspirational

Everything below is running and was verified by an agent-only campaign (~253 checks) and live drills:

- **Versioned CAS core**: content-addressed blocks (SHA-384, keyed digests — raw hashes never leave the core), cumulative versions, O(1) branching, time-travel reads by vid, diff, deletes.
- **Cryptographic tenancy**: P-384 principal identities, GKT-2 signed request/reply transcripts bound to pinned core keys, role bindings with Forbidden==missing semantics, per-transfer MACs. Hard boundaries — not query filters.
- **Federated durability**: 3-site Raft cores, 3 storage sites, tape tier with a formal recall state machine, site-loss drills (P9), refuse-closed writes, journaled site lifecycle (lost/restore/decommission), repair planner, tamper-evident audit with anchored loss acknowledgement.
- **Agent-native surfaces**: CLI, Python client, 25 MCP tools; extracts with signed Merkle certificates and citations; forget = approvals + time-lock + domain-key crypto-shred.
- **Verified production discipline**: an agent-only campaign found and fixed every defect it could reach; all owner decisions recorded on issues; the fabric runs the reconciled head.

The two reference papers describe building, from scratch, the class of system GaiaKeep already is. The future work is therefore **not** a rebuild — it is (a) finishing the durability milestone (MS6), (b) extending the fabric down to desktops and out to a global semantic layer, and (c) adding the semantic/procedural memory services that the papers argue agents need, **on top of** the verified substrate rather than beside it.

---

## 1. The reframe: a storage-class memory hierarchy for agents

Agents need data "as it sits" — not a single store but a **ladder of storage classes**, each with a formal role in the commit/durability pipeline. GaiaKeep already has every rung; MS6 wires the last transitions.

| Class | Hardware today | GaiaKeep mechanism | Role for agents |
|---|---|---|---|
| **M0 — RAM** | Recall cache on cores (64 GiB default), page cache | `RecallCache` (core_recall_dir), staged recalls | Sub-second reads of recently recalled tape blocks; the "hot" end of rehydration |
| **M1 — NVMe** | `/local` NVMe on compute nodes | Store pledges on node-local NVMe (`pledge_bytes`), scratch-cache collections | Commit landing zone (client returns at disk-R), hot working sets, sandbox branches |
| **M2 — Disk (shared/NFS)** | `/project` durable root | Durable-root store dirs, under-replicated census, repair planner | The durability spool and replica tier; publishes land here |
| **M3 — Tape** | 3 simulated Spectra libraries (LTO-10 spec) | Archive runs, 2-of-3 VERIFIED targets, write_verify FULL | The durable tier: purge-immediately after verify (owner decision), streaming rehydration for reads |
| **M4 — Client** | Desktops, laptops | Kit + MCP; the client's own disk becomes a **rehydration cache** (owner: "eventually rehydrated on the client side, which can serve as a cache") | The edge of the fabric; offline agent operation |

**SOTA additions to the ladder** (from the papers, adapted):

- **Class-aware placement**: `ReplicaPlacer.Request` gains a storage-class hint (`hot | warm | durable`), so an agent can ask for NVMe-resident staging vs durable spool placement at publish time. The placer already scores by weighted rendezvous and excludes quarantined sites — the hint is a policy filter, not a rewrite.
- **Down-tiering as a first-class operation**: MS6's purge sweep generalises to a **demotion pipeline** (M1 → M2 → M3) and a **promotion pipeline** (`core.stage` → M0/M1) — both journaled, both visible in the census, both bounded by per-tenant budgets (the staging caps already exist).
- **TTL storage classes**: scratch/cache collections already exist; add TTL expiry to branches and ephemeral collections so agent *threads* (the papers' `thread_id`) get automatic cleanup — the fourth isolation dimension without any new enforcement machinery.

---

## 2. Isolation, rethought: four scopes are already three-and-a-half

The papers mandate four nested scopes: `tenant_id / user_id / agent_id / thread_id`, enforced at the storage kernel (RLS or banks). GaiaKeep's mapping — with the hard/soft distinction the papers draw — is:

| Paper scope | GaiaKeep today | Enforcement class | Gap |
|---|---|---|---|
| `tenant_id` | tenant + domain + role bindings + Forbidden==missing | **Hard** (key identity; the core refuses what the bindings do not name) | — |
| `agent_id` | principal (every agent is a principal with its own key; the campaign's dedicated least-privilege test principal proved enforcement) | **Hard** | — |
| `thread_id` | branch / scratch collection / upload id | **Soft** (no TTL) | **Add branch TTL + ephemeral collections** — scratch-cache policy is the container; expiry is a maintenance-sweep addition |
| `user_id` | delegated: a principal *is* the acting identity; human sub-identity rides in audit (`by`) | Soft | Add user sub-principals only when a real multi-user tenant appears — do not build unused machinery |

The papers' core failure mode — "a single omitted filter tag leaks Tenant A's context into Tenant B's session" — **cannot occur** in GaiaKeep: there is no un-scoped query surface. `Forbidden == missing` means an unscoped ask returns nothing, not everything. That property is worth defending in the roadmap: **no verb is ever added that spans tenants** (the campaign verified "no verb lists every collection of a tenant").

---

## 3. The semantic layer: panAtlas and myAtlas as global references

The papers argue agents need a semantic layer (bi-temporal facts, write-time resolution, provenance). The owner already operates two:

- **panAtlas** — the federated semantic reference: NSF OKN's 42 RDF graphs mirrored as independent agents (~28.1 B triples, proven exact per-endpoint), the Wikipedia layer of record (7.23 M articles, evidence-classed links, verified vectors), the CLM decision-engine dataset (562 k rows, registered), medicine-first markdown fact-graphs on git-backed panatlas.net.
- **myAtlas** — the personal knowledge vault (this session's memory), git-backed, lint-governed, deploy-managed.

**The reframe: the atlas is the semantic layer; GaiaKeep is its durability substrate. The two papers' "bi-temporal knowledge graph with write-time resolution" is not a new database — it is panAtlas + GaiaKeep composed.**

- **Bi-temporality for free**: a git-backed fact-graph already carries system time (commit) and valid time (assertion content + pav:version, as OKN mirroring does). Snapshot a panAtlas/myAtlas state into a GaiaKeep version and you get **point-in-time atlas reads, O(1) atlas branching for agent hypothesis work, and diffable knowledge evolution** — the papers' temporal-graph query model, over infrastructure that exists.
- **Write-time resolution**: the git model *is* write-time state resolution (a working tree supersedes; history is immutable). The semantic resolver the papers want (contradiction → supersede, not append) is a **lint/merge policy** on the atlas side plus an ingestion service on the GaiaKeep side — not a new graph database.
- **Provenance lineage**: panAtlas facts carry human refs and evidence classes; GaiaKeep adds extract certificates (Merkle proofs binding leaves to versions) and the audit chain. Derived-artifact → source lineage = git blame + extract citation + audit `by`/`ts`. The papers' cascading-erasure requirement is met by **domain-key crypto-shred** (destroy the domain key; every encrypted block in the scope becomes unrecoverable — stronger than row deletion) plus the lineage graph for non-encrypted derived artifacts.
- **Agent access**: agents already read atlases via MCP (the OKN mirroring is agent-per-graph). The roadmap adds: atlases as GaiaKeep tenants, atlas snapshots as scheduled versions, and the pre-flight state surface (#7/#8) extended so an agent can ask "where does this atlas live, how fresh, what would rehydration cost" **before** requesting it.

---

## 4. FileRepo, incorporated — it already is the dataset-publication layer

**Filerepo is not a candidate to evaluate; it is live code to adapt.** GFS already runs the adaptation: a co-located filerepo catalogs a dataset directory (`path/sha256/size/mtime`), `PublisherEngine` exports batched catalog deltas (adds/updates/deletes) to the federation index, origin grants are enforced **before filerepo streams a byte**, and the index holds the publication as `IndexState.DatasetRec` — site, owner, filerepo endpoint, root, `delegates[]`, sequence, per-file `FileRec` (hash, objectId, availability) — with a **dataset-level survivability profile**. The block store deliberately did *not* reuse filerepo's whole-file `get()`/`clearRepo` model (`FsBinding` documents the measured rationale: a synchronous whole-file get is "expressible here and impossible on tape"), but the **catalog-delta + grant-gated streaming + survivability-profile** model was kept and is the dataset-publication fabric today.

What P-FABRIC therefore does is **extend the existing DatasetRec federation**, not build a new one:

| Extension | What changes | Why |
|---|---|---|
| Presence classes on `DatasetRec` | `delegates[]` and the filerepo endpoint gain a presence class (cluster / server / desktop-intermittent) | A desktop that sleeps is **absent**, not LOST — its catalog deltas persist, its pledge releases. (This is also why agent-freeze did not trip SUSPECT in the T2 drills: the lifecycle tracks the fabric, not a process.) |
| `FileRec.hash` → CAS linkage | The catalog's sha256 joins to the GFS block id space | Publish becomes: catalog delta + ingest — duplicate files deduplicate for free, and every cataloged file becomes a citable version |
| Grant objects carry purpose + TTL | Origin grants (already enforced before byte one) gain scope metadata | Desktop pushes from coffee shops get the same Forbidden==missing semantics as cluster peers |
| Chunk-verified resumable transfer for large datasets | filerepo streaming gains GFS's verified-chunk path for the M1→M2 hand-off | Whole-file `get()` stays dropped — the campaign proved chunked byte-exact transfer, and whole-file get is the failure mode the papers warn about |
| `survivability` profile ↔ MS6 | The dataset-level survivability profile is where the 2-of-3 tape target and the purge policy attach **per dataset** | The hook already exists in `DatasetRec`; MS6 fills it |

**The generalised insight stands, sharpened:** the global fabric is a federation of filerepo catalogs with grant-gated byte movement and survivability profiles — desktops, servers, and clusters differ only in presence class and pledge. The papers' "edge compute network" is an adaptation of running code, not a new architecture.

---

## 5. The global fabric topology

Three presence classes, one namespace, refuse-closed durability everywhere:

| Class | Hardware | Runs | Durability role | Presence |
|---|---|---|---|---|
| **Cluster** | HPC-class + tape libraries | Core raft peers, stores, tape nodes, dashboard, atlases | Raft quorum, durable spool, MS6 tape tier | Permanent, pledged, attested |
| **Server** | Lab/department machines | Store peers (NVMe/disk pledges), catalog exporters, compute-to-data targets | Replica + staging tier | Pledged; SUSPECT→LOST lifecycle as today |
| **Desktop** | Workstations, laptops | Kit + MCP client, catalog exporter, optional opportunistic store (no durability pledge) | Client cache; **source of raw data** (the datasets agents train/evaluate on arrive here first) | Intermittent — delta-sync on connect |

Governance carries over unchanged and that is the point: **the same keys, bindings, refuse-closed rules, and audit chains govern a laptop and a tape library.** A desktop agent authenticating from a coffee shop gets the same Forbidden==missing semantics as a cluster peer. The papers' "zero-trust edge" is achieved by *not special-casing the edge*.

**Raw data → atlas flow (the autonomous-operation loop):**

1. Desktop agent creates a dataset (raw capture, training/eval data) → publishes to its collection (commit at disk-R; MS6 upgrade moves it to tape asynchronously).
2. Agent publishes catalog deltas (filerepo model) → the global namespace sees the dataset.
3. Agent works on the atlas (panAtlas/myAtlas) referencing the dataset via GaiaKeep citations (`gfs:1r:<vid>#<extract>`), so **every training/eval set a fact-graph depends on is itself a versioned, durable, citable object**.
4. Eval results publish back as new versions; the audit chain ties agent → dataset-version → result-version.
5. Erasure (GDPR/owner request) = domain-key shred + atlas retraction, with the audit entry as the compliance proof.

This closes the papers' biggest gap — "agents re-plan from scratch because raw data and provenance are not durable" — with components that exist.

---

## 6. Semantic and procedural memory: the SOTA service layer

Built **on** the substrate (not beside it), phased after the fabric tiers:

1. **Atlas state service** (first): expose atlas/dataset state (the pre-flight surface from #7/#8): per-version locality, freshness, recall cost, and catalog presence. Agents estimate before they commit to a recall. Design input already recorded by the owner (streaming rehydration, client-side cache).
2. **Bi-temporal fact store** (the papers' core ask): facts as versions in atlas collections; write-time supersession (new version supersedes; history immutable — exactly the GaiaKeep model); point-in-time reads by vid; contradiction resolution = the atlas lint/merge policy executing at ingest. This gives agents the state-trajectory semantics the papers formalise as `M_t = (D_t, S_t, P_t)` — with `P_t` implemented as GaiaKeep policy objects, not database rows.
3. **Procedural memory**: workflow traces stored as first-class versions (a "procedure" is a version whose content is a schema-validated execution trace), citable and reusable — the papers' observation that agents discard successful workflows is solved by giving workflows the same version/citation/erasure machinery as datasets.
4. **Consolidation/compaction**: the papers' reversible-compaction idea lands as **extract discipline** — raw payloads referenced by content-addressed URIs (already how GaiaKeep works), with schema-constrained summarisation performed by agents using atlas facts, versioned like everything else.

---

## 6a. The memory-framework taxonomy, positioned (from the governance blueprint)

The second reference blueprint classifies the agent-memory ecosystem into five architectural classes and asks which to build. The integration answer is positional: **GaiaKeep is the durability, versioning, isolation, and provenance substrate each of these frameworks assumes but does not provide** — and the MCP surface is the seam. What follows is the taxonomy with GaiaKeep's role stated per class; it is positioning, not a build list (the service layer in §6 is where the substrate gains agent-facing semantics).

| Framework class (examples) | Its memory model | What it lacks that GaiaKeep provides | Integration shape |
|---|---|---|---|
| **Vector-fact extraction** (Mem0) | LLM-extracted facts in vector stores; append-only, resolution deferred to retrieval ranking | Durable versioned storage under the vectors; write-time supersession; hard tenancy; provenance lineage for erasure | Facts reference citable versions (`gfs:1r:<vid>#<extract>`); the append-then-rank model keeps its store, gains supersession and erasure from the substrate |
| **Temporal knowledge graph** (Zep / Graphiti) | Bi-temporal nodes/edges with validity intervals in a graph DB | The graph itself is not durable or versioned; tenancy is namespace-level | Graph snapshots as versions (point-in-time graph reads, O(1) branching for hypothesis work); edges citing dataset versions |
| **Virtual tiered memory** (Letta) | Context window as RAM; core/recall/archival blocks in Postgres + pgvector | Single-server durability; no federated tiering; agent-OS coupling (the anti-goal) | Archival blocks land in GaiaKeep collections; the paging contract maps to stage/pre-flight; no runtime lock-in taken |
| **Code/doc knowledge graphs** (Cognee) | Graphs derived from repos and documents | Provenance to source commits; durability; multi-tenant isolation | Derived graphs as versions citing source versions — lineage is the substrate's native property |
| **Biomimetic multi-network** (Hindsight) | World facts / experiences / entity summaries / evolving beliefs, with hard isolation banks | The banks' durability and erasure guarantees; belief states as versioned, diffable objects | Belief revision = new versions superseding old (immutable history); bank isolation = tenant hard boundaries; belief erasure = crypto-shred |
| **Context-layer engines** (Meterless / H-MEM) | Four-engine tiered context with bounded carryover and a microkernel runtime contract | A durability substrate with storage classes and recall economics | The storage-class ladder (§1) is the backing store; pre-flight state tells the harness what a recall costs before committing |

Two conclusions the taxonomy sharpens. First, **none of these frameworks solves durability, federation, or regulated erasure** — they all assume a storage layer that behaves like GaiaKeep already does; that is the substrate's market position and why the roadmap layers semantics ON the fabric rather than competing with them. Second, the **hard/soft isolation doctrine** (§2) is the report's strongest claim and GaiaKeep's strongest proof: frameworks that rely on soft tags leak; the substrate cannot leak because there is no un-scoped surface. GaiaKeep does not build a memory framework; it is the layer that makes any of them safe to run.

## 7. Attestation and confidentiality (the tier-1 differentiator)

- **Now**: pinned core keys, GKT-2 bound transcripts (request **and** reply signed), end-to-end encryption, per-transfer MACs, refuse-closed IntegrityErrors. The client *already* refuses unkeyed/unattested answers — the haveopen defect proved the fail-closed posture works.
- **Next (tier-1 SOTA):** add a **remote-attestation step to the GKT handshake** — the core presents a signed attestation (confidential-compute GPUs such as the H100 are real hardware for this) before the session key derives. Session-key reuse after one attestation matches the papers' performance pattern and the existing handshake shape.
- **Regulatory posture**: attestation + crypto-shred + audit chain = the compliance story (GDPR Art. 17/32, EU AI Act) stated in cryptographic rather than contractual terms — the papers' "contractual trust → hardware-enforced protection" transition.

---

## 8. Roadmap (sequenced, tied to the issue ledger)

| Phase | Contents | Gates |
|---|---|---|
| **P-MS6 (now)** | #7/#8: placement counting, `core_place_on_deferred`, async 2-of-3 tape upgrade, automatic purge, StageRequired read path | `TapeEndToEndTest` + T5 harness assertions; campaign re-run |
| **P-STATE** | Pre-flight locality/state verb; thread-TTL + ephemeral collections; dashboard capability flag | Campaign asserts state-before-transmit; TTL sweep test |
| **P-ATTEST** | GKT remote-attestation hook (H100 CC); refuse-closed on attestation failure | IntegrityError on bad attestation; perf budget measured |
| **P-FABRIC** | extend the **live** DatasetRec federation (filerepo-adapted: presence classes, FileRec→CAS linkage, purpose+TTL grants, survivability↔MS6) | Desktop→cluster delta sync byte-exact; no un-scoped namespace |
| **P-ATLAS** | panAtlas/myAtlas as tenants; scheduled atlas snapshots; pre-flight surface for atlases | Snapshot → time-travel → crypto-shred drill on an atlas scope |
| **P-MEM** | Bi-temporal fact store + procedural memory on the substrate | Write-time supersession test; lineage cascade test; erasure drill |

---

## 9. Anti-goals (what we deliberately will not build)

- **No agent-OS runtime lock-in** — the kit stays MCP-first and harness-agnostic (the papers' Letta critique is correct and we avoid it by construction).
- **No soft-partition tenancy** — no verb ever spans tenants; no metadata-tag-only isolation.
- **No interactive-tape reads as the primary model** — reads stream/rehydrate per the owner's model; StageRequired + pre-flight state is the contract.
- **No RLS-in-a-SQL-sense** — the key/role boundary is the kernel boundary; adding a database layer would weaken it.
- **No unscoped namespaces, ever** — Forbidden==missing stays.

---

## 10. Sources

- Two owner-supplied reference papers (agent storage blueprints; competitive analysis of Mem0, Zep/Graphiti, Letta, Hindsight, Cognee, Redis Agent Memory, Oracle AI Database; lakeFS/Delta/Iceberg/Bacalhau/DVC/CAS comparisons; TEE/MemTrust attestation architecture).
- Verified production state: `MAIN.md`, `REMEDIATION-PLAN.md` (this directory), gfs#1–#11 (GitHub), myAtlas `project-cresco-gfs.md`.
- FileRepo: `PublisherEngine.java` (catalog-delta federation, grant-gated streaming), Cresco library filerepo (directory mirror, heartbeat index), vault reference on BlockStore limits.
- panAtlas/myAtlas: vault `project-panatlas`, `org-nsf-open-knowledge-network`, `project-wikipedia-world-view`, `project-clm-decision-engine`; `panatlas/cresco` deployment on the HPC cluster.
