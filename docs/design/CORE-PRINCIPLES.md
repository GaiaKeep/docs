!!! info "Status: Proven (prototype)"
    The prototype's principles and architecture (2026-09-17).

# Cresco Global File System (GFS) — Core Principles, Architecture, Next Steps

*Status: working design, 2026-09-17. Prototype evaluation: **97/97 checks pass** (`RESULTS.md`). Grounded in `global-federated-storage-plan.md`, the 2026-09-13
design conversation, the filerepo code and audits (`FILEREPO-AUDIT.md`, `CRESCO-DECISIONS.md`), the
tenant-isolation and identity designs (`docs/tenant-isolation-design.md`,
`docs/distributed-identity-trust-design.md`), and the DoD zero-trust/CMMC pivot
(`Zero_Trust_Hardening_Gaps.md`, `Compliance_Roadmap_800-53_CMMC.md`). A running prototype
(`code/gfs`, `run/gfs`) embodies every principle below; see `PROTOTYPE.md` and `EVALUATION-PLAN.md`.*

---

## 0. What we are building

One system, two objectives, one mechanism:

1. **Data sharing (primary).** Any participant (cluster, lab server, desktop) publishes a dataset
   into a federated index and exposes it to collaborators through per-project namespaces. Bytes
   stay where they are, on the contributor's hardware and storage tier of choice.
2. **Geographic redundancy (secondary).** Pledged bulk capacity across sites gives a low-cost,
   low-performance durability tier using global erasure coding rather than replicas.

Both are "index, route and store data at federated locations". Durability is publication whose
destination is blind storage instead of a reader.

**Division of labor (decided):** `io.cresco.filerepo` stays the *file primitive* — it catalogs a
directory (path, SHA-256, size, mtime), serves files inline or by byte-range streaming over the
dataplane, and moves artifacts. The new `io.cresco.gfs` plugin *coordinates*: federation index,
project-scoped access, blind erasure-coded durability, key custody, reciprocity, liveness, repair.
Cresco itself provides the foundation: mesh routing, four-tier QoS with an isolated control plane,
tenant isolation, regional-CA identity, capability inventory, unified health/metrics.

---

## 1. Core principles

Each principle states the rule, why it holds, what it forces in the design, and how the prototype
embodies it.

### P1 — Sharing is the product; durability is a by-product of the same machinery
*Why:* the federation grows on publication, which must cost a contributor nothing. Redundancy is
opt-in and rides the same index/route/store path.
*Design:* one index, one placement engine, one transport. A durable copy is just a publication whose
destination is a set of blind stores.
*Prototype:* `promote` reuses the node registry, the placement solver and the dataplane transport used
for everything else.

### P2 — Bytes stay put; only index entries move
*Why:* no migration, no upload, no copy of clinical data across institutional boundaries just to be
findable.
*Design:* a publisher points filerepo at a directory; gfs exports **batched catalog deltas** (adds,
updates, **deletes**) to the index with a per-dataset sequence number. The index never touches bytes.
*Prototype:* `PublisherEngine.exportOnce()` → `catalogdelta` every few seconds; deletion propagation
closes filerepo's FR-D4 gap at the index layer (filerepo keeps rows for deleted files; the publisher
exports only files that still exist).

### P3 — The index is federation-internal (DUA); projects are the public surface
*Why:* "presence in the index does not mean the data is shared." Sites agree to describe their data;
recipients may not share the index further. Users must see projects, not a global namespace that is
99 percent inaccessible.
*Design:* raw index listing/search is restricted to owners/delegates/federation admins. A **project**
has an owner, delegates and members. A **dataset owner or delegate** commits data — down to the
individual file — into a project. Members see exactly the committed files.
*Prototype:* `listfiles`/`search` are owner/admin-gated; `createproject`, `projectmember`, `commit`,
`projectfiles`, `resolve` implement the authorization matrix (evaluated in E4).

### P4 — Policy is enforced at the origin; the index authorizes, the origin verifies
*Why:* the holder physically has the bytes and can simply say no; a compromised or stale index must not
be able to leak data.
*Design:* `resolve` checks membership + commitment and issues a **short-lived grant** bound to
(user, project, dataset, file, expiry). The origin's gfs verifies the grant independently before its
local filerepo streams a single byte. Fetches are routed by Cresco to the holding site.
*Prototype:* HMAC-SHA-384 grants with a federation secret (stand-in). Production: grants signed with
the regional CA (`MessageSigner`) and client identity bound by mTLS (see §6).

### P5 — Holding sites are blind
*Why:* dodges the DUA minefield — a fragment at Murray State does not imply Murray State can read it;
legally the federation uses them as a blind block store.
*Design:* **encrypt first with the providing institution's key, then chunk, then erasure code.**
Fragment ids are unlinkable hashes; the block store records only id, size, hash and owning site for
accounting. **Repair and re-encode operate on ciphertext and never need a key.**
*Prototype:* AES-256-GCM per stripe (IV = object nonce ‖ stripe counter, AAD = object ‖ stripe), a
per-object DEK wrapped under the site KEK; RS(k,m) over GF(256). Evaluated by entropy/marker tests
(E6) and repair-without-key (E7/E8).

### P6 — No single site can decrypt alone, and no single site loss can lose a key
*Why:* if keys never leave the originating institution, a fire leaves perfectly redundant fragments and
no way to read them.
*Design:* the site KEK is Shamir-split (t of n) across storage nodes of n *other* sites; reconstruction
requires a **quorum of institutional approvers** and is audited; custody nodes release shares only
against that authorization. Key re-establishment on a rebuilt site is a first-class operation.
*Prototype:* `custodyplan/custodyput/custodyregister`, `approvereconstruct` → `reconstructauth` →
`custodyget`; approvals are consumed on issue (E9).

### P7 — Hierarchical redundancy: local class inside a site, global parity across sites
*Why:* flat wide-area erasure coding makes every in-site failure a WAN reconstruction. Local codes
handle the common failure; global parity handles whole-site loss (Azure LRC / Facebook f4 shape).
*Design:* the declared **local resiliency class** (USB drive … clustered file system) is the local
tier; the federation stripe places **k+m fragments on k+m distinct sites**. 10+4 across sites ≈
two-site tolerance at 40 % overhead vs 200 % for triple replication.
*Prototype:* placement = one node per site, best score first; local tier is represented by the class
weight in scoring. Full LRC (local parity groups) is a roadmap item (§7).

### P8 — Reciprocity: backup entitlement equals contribution, scored, not raw
*Why:* solves the free-rider problem; a petabyte on a 100 Mb link is not useful; hyperfast NVMe earns
nothing on a backup tier.
*Design:* `score = pledge × class_weight × (0.5+0.5·availability) × (0.5+0.5·net_factor)` with
`net_factor = min(1, measured/cap)`; **entitlement = Σ site scores × ratio**; consumed = fragment
bytes stored elsewhere on the site's behalf (overhead included). Class is **per agent**, not per site.
Availability is observed (heartbeats), network is probed, class claims are kept honest by scrub.
*Prototype:* `ledger`, `listnodes` scores; `promote` refuses beyond entitlement (E10).

### P9 — Participation is a contract
*Why:* a laptop can be a client; it cannot be a storage node.
*Design:* two tiers — **client** (publish, browse, commit, fetch) and **storage node** (intended 24/7,
registered class, monitored; sustained unavailability lets the federation re-encode affected stripes
elsewhere — a stated feature, not an automatic surprise).
*Prototype:* liveness UP → SUSPECT → LOST; after a grace period auto-repair re-places fragments onto
an eligible site; when none exists the object is explicitly DEGRADED "awaiting an eligible site"
(E7). Notification/"nagging" pipeline is roadmap.

### P10 — Cresco is the foundation; GFS adds coordination, not transport
*Why:* mesh routing, QoS and isolation already exist and are proven; re-implementing them would be
worse and unmaintained.
*Design:* control traffic (registry, deltas, grants, manifests, receipts) is EXEC RPC on the
**CONTROL tier with its own sockets**; bulk (fragments, file streams) is on the **dataplane (BULK
tier)** so a restore can never starve liveness or control. Discovery, addressing, health, metrics and
the capability inventory are Cresco's.
*Prototype:* `FrameBus` (fragment frames on the dataplane, selector `gfs_to='<node>'`), filerepo
`streamfile` for file access, `getcapabilities`/`getmetrics`/Felix health checks wired.

### P11 — Tenant isolation is mandatory and explicit
*Why:* "operations at one site must not affect another" and the DoD/CUI hardening make isolation
non-negotiable. Cross-site flows are the *point* of a federation, so they must be named and allowed,
never implicit.
*Design:* **each participating site is a Cresco tenant** (`tenant_id`, cert DN `O=<site>`, regional CA);
**the federation core is its own tenant** (`gfs-federation`); every GFS cross-site flow is an
**inter-tenant flow** admitted by policy: site → core (register, deltas, manifests), core → site
(encode/repair instructions), site → site (fragments to blind stores, custody shares, granted fetches).
Per-tenant QoS fairness keeps one site's bulk from degrading another's control plane.
*Prototype/gap:* Cresco's shipped tenant namespacing (`T.<tenant>.*`) denies cross-tenant traffic unless
the principal is a superuser; it has **no inter-tenant flow allow-list yet**. The prototype therefore
runs the fabric in one tenant and enforces site admission in the GFS layer (`federation_members`,
site stamped and verified on every ingest, node identity taken from the message source). §6 specifies
the Cresco work item that makes P11 real at the broker.

### P12 — Fail closed, approved crypto, everything audited
*Why:* the zero-trust pivot: no "fabric membership = trusted" escape hatch; FIPS/CNSA algorithms only.
*Design:* gfs refuses to start without a federation secret or an index address; unknown sites, unknown
nodes, spoofed sources, forged/expired/tampered grants and unauthorized custody requests are refused
with explicit statuses; privileged actions are journaled as audit entries.
*Prototype:* SHA-256, HMAC-SHA-384, AES-256-GCM, DRBG; no MD5 anywhere in gfs. (BouncyCastle-FIPS
module validation is a fabric-wide roadmap item.)

### P13 — One mutation path for the index; stronger consistency than the bulk tier
*Why:* the manifest index is the crown jewels: object → stripe layout → fragment locations → key
reference → policy. It must be replicable and auditable.
*Design:* every change is a typed mutation committed through one path (apply → journal → ship to
replicas); replay of the journal reproduces the state; replicas converge by log shipping; the audit
trail *is* the log. Raft over four core nodes replaces primary/replica log shipping in production.
*Prototype:* `IndexEngine.commit/apply`, `gfs-index.jsonl` journal, replica catch-up via `logsince`,
`statehash` convergence check (E11).

### P14 — Unit of publication is a dataset directory; the index is file-granular
*Why:* BTSA experience: raw information (native directory structure, location, metadata, hashes) is
what collaborators need, and commitment must reach the individual file. It "gets big quickly", so the
index must be built for deltas, batching, pagination and replication from day one.
*Design:* dataset = a published root; files keyed by relative path; deltas carry only changes;
listings paginate; manifests reference files by (dataset, relpath) and are invalidated (STALE/
ORPHANED) when the source changes or disappears.

---

## 2. Architecture

```
                 ┌──────────────────────── federation core (tenant gfs-federation) ────────────────────────┐
                 │  index primary ── log shipping ──► index replica(s)      (Raft x4 in production)         │
                 │  registry · publications · projects · manifests · ledger · custody quorum · audit       │
                 └───────▲──────────────────────────────▲───────────────────────────────▲──────────────────┘
      CONTROL tier       │ register/heartbeat/probe     │ catalogdelta, manifestput     │ resolve → grant
      (EXEC RPC)         │                              │ encode/repair instructions    │
                 ┌───────┴───────┐              ┌───────┴────────┐               ┌──────┴───────┐
                 │ storage node  │              │ publisher      │               │ client        │
                 │ (site B)      │◄─ fragments ─│ (site A)       │── grant ────► │ (any device)  │
                 │ blind store   │  dataplane   │ filerepo scan  │  fetch ►      │ pycrescolib   │
                 │ custody share │   BULK tier  │ site KEK       │ streamfile ►  │ /S3/FUSE later│
                 │ scrub         │              │ encode/restore │  dataplane    │               │
                 └───────────────┘              └────────────────┘               └───────────────┘
```

### 2.1 Roles (one bundle, `gfs_roles` selects)
- **index** — core node. Primary or replica. Never sees bytes or keys.
- **publisher** — runs beside a filerepo instance that catalogs the dataset root; exports deltas;
  holds the site KEK; encodes on promote; enforces grants at the origin; restores.
- **storage** — blind block store (pledge, class); custody of key shares; scrub; heartbeat; can run
  repair and restore (restore only with key access or a quorum token).
- **client** — the Python SDK (`run/gfs/gfs_client.py`); S3/FUSE gateways are later surfaces.

### 2.2 Planes
| Traffic | Mechanism | Tier |
|---|---|---|
| registry, heartbeats, probes, deltas, project ops, grants, manifests, receipts, custody | `MsgEvent` EXEC RPC | CONTROL (priority 7, isolated sockets/bridge) |
| fragments (put/get), file streams to clients | dataplane BytesMessages (`FrameBus`, filerepo `streamfile`) | BULK (priority 1, persistent, data bridge connectors) |

### 2.3 Data model (index)
`NodeRec` (site, roles, class, pledge, used, liveness, probe, score) · `DatasetRec` (site, owner,
delegates, publisher node, filerepo, root, seq, files: relpath → hash/size/mtime/object) ·
`ProjectRec` (owner, delegates, members, commits: (dataset, relpath|*) by whom) · `Manifest`
(object, dataset/relpath, site, size, sha256, k, m, block, key_id, wrapped_dek, nonce, policy,
placement[i]→node, stripes[s].frags[i] → id/node/sha256/size/status, state) · `CustodyRec`
(key_id, site, t, n, holders, approvals) · ledger (derived from nodes + manifests).

### 2.4 Flows
1. **Publish/export:** filerepo scans → gfs reads the catalog → diff → `catalogdelta(seq)` → index.
2. **Commit/resolve/fetch:** owner commits (dataset, relpath) into a project → member `resolve` →
   grant + origin → client opens a dataplane stream → origin verifies grant → filerepo `streamfile`.
3. **Promote:** index checks owner/delegate, entitlement, solves placement (distinct sites, exclude
   origin, keep_in_state, capacity, score) → `encode` at origin → per stripe: GCM encrypt → RS → n
   frames on the dataplane + `putfragment` receipts → `manifestput` → DURABLE.
4. **Restore:** manifest (authorized) → KEK (local or reconstructed) → any k fragments per stripe →
   RS decode if needed → GCM decrypt → SHA-256 verify.
5. **Liveness/repair:** heartbeats → SUSPECT/LOST; after grace, planner re-places lost fragment
   indices on a fresh eligible site and regenerates from k (no key); BAD fragments (scrub) are
   regenerated in place; if no site is eligible the object is DEGRADED with an explicit reason.
6. **Custody:** publisher splits KEK t-of-n to n other sites; approvers reach quorum → token →
   holders release shares → KEK rebuilt (in memory, or persisted to re-establish a site).
7. **Replication:** every commit is shipped to replicas; replicas catch up by `logsince`.

### 2.5 Cryptography
| Purpose | Algorithm | Notes |
|---|---|---|
| Content/fragment hashes | SHA-256 | filerepo catalog hashes are SHA-256 (phase-0 facade) |
| Stripe encryption | AES-256-GCM, 96-bit IV = nonce4 ‖ stripe64, AAD = object ‖ stripe | per-object DEK; stripes independently authenticated; swapping fragments across stripes/objects fails decryption |
| Key wrapping | AES-256-GCM(KEK, DEK), AAD = key_id | KEK never leaves the site (prototype: 0600 file; production: PKCS#11/HSM/KMS) |
| Custody | Shamir over GF(256), t of n | Vault-style; shares held by other sites' storage nodes |
| Erasure code | systematic RS(k,m) over GF(256), Vandermonde-normalised | 850 MB/s encode single-thread on the dev host |
| Tokens | HMAC-SHA-384 over JSON claims (prototype) | production: regional-CA signatures via `MessageSigner`; approver signatures for custody |
| Randomness | DRBG | |

### 2.6 Placement (the constraint solve)
Candidates = storage nodes that are UP, at federation-member sites, not the origin site (unless policy
allows), matching `keep_in_state`, with free pledge ≥ stripes × shard length, not already holding a
fragment of the same stripe. One node per site (best score). Sort by score, take n. Fewer than n →
refuse with an explicit reason. Repair uses the same solve with the surviving sites excluded.

### 2.7 Scoring
`class_weight`: usb-single 0.4 · desktop-single 0.6 · server-raid 0.9 · clustered-fs 1.0.
`availability` = heartbeats received / expected since registration. `net_factor` = min(1, probed
throughput / cap) where cap is "good enough for restore". Read-out (recovery) bandwidth is what the
probe measures; ingest speed is deliberately not rewarded.

---

## 3. How it leverages Cresco and filerepo

| GFS need | Cresco / filerepo mechanism | Status |
|---|---|---|
| Local catalog with hashes, change detection | filerepo scan → Derby catalog (SHA-256) | shipped |
| Serve bytes to a client anywhere in the mesh | filerepo `streamfile` (dataplane, any size), `getfile` (inline) | shipped |
| Move bulk without starving control | 4-tier `MsgQoS`, isolated `ControlPlaneSender`, split bridges | shipped |
| Address a plugin instance anywhere | `getGlobalPluginMsgEvent` + RPC | shipped |
| Discover what a node can do | `@CrescoAction` capability inventory | shipped; gfs annotated |
| Health + metrics | Felix HC + MeasurementEngine → `gethealthinventory`/`getmetricinventory` | shipped; gfs wired |
| Node identity | regional-CA leaf certs, mTLS binding | shipped (flags) — gfs will read identity from cert-bound src |
| Tenant isolation | `tenant_namespacing`, `TenantPolicy`, superuser | shipped, but **no inter-tenant flow policy** (§6) |
| Multi-site mesh | region per site federated to a global; proven 28/64-node meshes | shipped |
| Plugin distribution | `upload_plugin_agent` → repo cache → `add_plugin_agent` | shipped (used by the prototype) |

## 4. Gap analysis — filerepo as-is vs. GFS

| Capability | filerepo today | GFS requirement | Where it lives now |
|---|---|---|---|
| Publication identity (dataset, owner, delegates, site) | none (a `filerepo_name`) | required | gfs publisher config + index |
| Index propagation | full directory sync to subscribers (replica) | deltas to core index, no bytes | gfs `catalogdelta` |
| Deletion propagation | never (FR-D4) | required | gfs publisher (exports only existing files); FR-D4(b) still recommended in filerepo |
| Per-caller authorization | none (FR-D1) | grants at origin; project ACLs | gfs `resolve`/`fetch`; FR-D1(b) still required for filerepo's own actions |
| Availability state per file | none | ONLINE / DURABLE_ONLY / UNAVAILABLE | index (node liveness + manifests) |
| Encryption / erasure coding / placement | none | required | gfs durability engine + index placement |
| Key custody | none | required | gfs custody (Shamir + quorum) |
| Reciprocity | none | required | index ledger |
| Streaming protocol robustness | best-effort, no terminal frame (FR-D6) | needed for WAN | gfs verifies size+sha256 per fragment; filerepo FR-D6(b) recommended |
| Bulk on the dataplane | sync pulls over control plane (FR-D7) | bulk on BULK tier | gfs fragments on the dataplane; FR-D7(b) recommended for filerepo sync |

## 5. Decisions taken in the prototype (and their production form)

| Topic | Prototype | Production |
|---|---|---|
| Identity of users | opaque ids (ORCID-style strings) trusted from the client | InCommon/ORCID federated login → signed assertions bound to the client's mTLS identity |
| Grant/authorization tokens | HMAC with a federation secret | regional-CA signed by the index; approvers sign custody approvals with their own keys, holders verify signatures (no index-mintable token) |
| Site KEK | file in plugin data dir | HSM / KMS (PKCS#11), never on disk in clear |
| Index durability | JSON-lines journal + log-shipped replica | Raft across 4 core nodes; snapshots; SQL/KV backing |
| Sites as regions/tenants | one region, one tenant, site admission in gfs | region + tenant per site; inter-tenant flow policy at the broker |
| Fragment transport | one dataplane frame per fragment (≤ 512 KiB block) | same, plus batching/pipelining and larger blocks once frame limits are lifted |
| Encoding | whole-file at promote, in-memory per stripe (streaming read) | same streaming loop; multi-threaded stripes; resumable jobs |

## 6. Tenant isolation — the explicit mapping

**Deployment model.** Site *S* = Cresco tenant *S* (its regional controller and agents carry
`tenant_id=S`, leaf certs `O=S`). The federation core (index nodes) = tenant `gfs-federation`.
All GFS flows are inter-tenant and fall into three named classes:

| Flow | From → To | Destination (namespaced) |
|---|---|---|
| F1 site → core | publisher/storage → index (register, heartbeat, deltas, manifests, custody registry) | `T.gfs-federation.<region>_<agent>` inbox |
| F2 core → site | index → publisher/storage (encode, repair, probe) | `T.<S>.<region>_<agent>` inbox |
| F3 site → site | encoder → blind store (fragments), publisher → custody holders (shares), client → origin (granted fetch) | `T.<S2>.<region>_<agent>` inbox + `T.<S2>.global.event` dataplane |

**Cresco gap (work item W-GFS-1, "inter-tenant flow policy"):** `TenantPolicy` today allows a
principal only its own `T.<tenant>.*` subtree; superuser is all-or-nothing. GFS needs a broker-level
allow-list of *named cross-tenant sinks*: e.g. `gfs-federation → T.*.<gfs inbox>` and `T.<S1> →
T.<S2>.<gfs inbox>` only for the gfs plugin destination, distributed with the trust bundle
(the mechanism the identity design already uses for CA bundles). Until then the fabric runs GFS in one
tenant and the GFS layer enforces admission (member sites only, source identity checked on every
ingest). **W-GFS-2:** per-tenant fair scheduling (routing plan W6) so one site's bulk cannot degrade
another's control latency. **W-GFS-3:** dataplane topics per tenant already exist under namespacing;
the `FrameBus` selector must be tenant-qualified when W-GFS-1 lands.

## 5a. Survivability is a property of the data domain (configurable)

Every dataset carries a default **survivability profile**; a project or a single promote can
override it; the index refuses, with the reason, anything the federation cannot satisfy right now.
Precedence: index default → dataset default (`setsurvivability`, owner/delegate) → promote policy.

| key | meaning | default |
|---|---|---|
| `k`, `m`, `block_size` | coding ratio and stripe block | 3, 2, 256 KiB |
| `domain` | the failure domain every fragment of a stripe must be distinct in: `site` (institution), `agent` (host), `region` (Cresco region = site broker) | `site` |
| `min_regions` | minimum distinct regions across a stripe (geographic spread on top of `domain`) | 0 |
| `exclude_origin` | never place on the publishing site | true |
| `allowed_sites` / `denied_sites` | allow-list / deny-list of holder sites (DUA, contracts) | none |
| `allowed_state_codes` | jurisdiction (keep-in-state, keep-in-country) | none |
| `keep_in_state` | shorthand: holders share the origin's state code | false |
| `min_free_ratio` | do not place on nearly full pledges | 0 |
| `repair_grace_ms` | how long a holder may be LOST before re-placement (the terms-of-service grace) | index default |
| `fetch_redundancy` | extra fragments raced on restore (slow-link tolerance vs. bandwidth) | 1 |

The placement solve enforces these on promote **and** on every repair/fallback, so an object never
silently drifts out of its policy. `placementpreview` answers "is this profile satisfiable today?"
without moving bytes. Measured: 12/12 profiles behave as specified on both topologies (E12/SCALE).

## 5b. Passive-failure tolerance (what the data path does when things flap)

- **Push with fallback:** a holder that does not answer within `push_timeout_ms` (5 s, 2 tries) is
  replaced through the index (`replaceholder`) by another holder that still satisfies the policy;
  the manifest records where bytes really went and the swap is audited. Encodes and repairs finish
  under a mid-flight site loss (measured: 12/12 with 52–69 fallbacks on a flapping multi-region host).
- **Raced, multi-round fetch:** restore and repair request `k + fetch_redundancy` fragments per
  stripe with a short timeout; slow or dead holders lose the race and are retried in later rounds
  with backoff (`fetch_rounds`); only "no such fragment" is permanent.
- **Repair never blocks on a plan:** partial placements are repaired immediately; a failed repair
  reports back (`repairfailed`) and is re-planned at once.
- **Verified client streaming:** the origin returns per-chunk SHA-256 with every granted stream; the
  client verifies each chunk and re-requests exactly the missing or corrupt byte ranges, so a lost
  dataplane frame costs one small re-fetch, never a corrupt file.
- **Index-driven fragment audit:** the index asks every holder which of its expected fragments are
  present (parallel, short budget) and marks the absent ones MISSING → repair; catches losses a
  holder-side scrub cannot see. Network-heavy sweeps never share the liveness timer thread.
- **Liveness is the only trigger for re-placement**, with per-policy grace; objects beyond `m` losses
  are marked LOST explicitly rather than pretended repairable.

## 6a. Findings from the prototype that change the plan

- **Plugin identity is not stable across an agent restart unless pinned.** A persisted plugin reloads
  under a fresh id unless the deploy config carries `inode_id`. GFS keys nodes, placements, custody
  holders and audit entries by `region:agent:plugin`, so identity must be pinned (the SDK now does) and,
  in production, derived from the cert-bound node identity. → **W-GFS-4**: stable plugin identity in
  Cresco's plugin admin (persist and reuse the id by default).
- **Index replicas must be strictly read-only.** Any locally originated mutation (a liveness sweep on
  second-hand heartbeats) forks the log while sequence numbers still line up. Raft in Phase 3 removes
  the primary/replica asymmetry; until then only the primary runs liveness, probing and repair.
- **Bulk frames and control RPCs are unordered relative to each other.** Data on the BULK tier can
  land before or after the CONTROL-tier message that describes it; every receiver must park and claim
  atomically. FR-D6's terminal frame + length/hash in filerepo would give the same guarantee to file
  streams.
- **Auto-repair must be partial-progress.** With one spare site and two lost indices, repair the one
  you can and state the other explicitly (P9), never wait for a perfect plan.
- **Top-k placement correlates failure.** Strict best-score placement put every object on the same
  best sites; one two-agent outage exceeded m for every object. Placement is now weighted random
  across all eligible domains (spread measured: 236–239 of 240 sites used, no agent above 9 %).
- **Never do network work on the liveness timer.** The first audit sweep ran on the timer thread; a
  flapping region turned its 30 s timeouts into minutes without loss detection.
- **Same-host multi-region bridges flap** (the region-federation design's duplex reverse-leg
  limitation, "Controller Path Lost" every ~7 s per region). GFS completes every operation through
  fallback and retry at a latency cost; the multi-host mesh is the venue for clean bridged numbers.
  → **W-GFS-5**: bridge stability/backoff under bulk on the Cresco side. **Root cause found and fixed
  (2026-09-17):** the flapping was not bulk pressure but a fixed remote port — every peer bridge was
  built to `<peer ip>:discovery_port_remote`, which on one host with several regional brokers is the
  global's broker; the remote-name check failed, the path was declared lost and re-discovered every
  ~7 s. Discovery replies now advertise the responder's bound broker port and bridges/agent channels
  use it. Multi-host peers on the default port are unchanged.
- **Publisher restarts must resync the delta sequence** (found by F2/F6): the index owns the
  sequence; a publisher adopts it on re-publish and on any stale reply.
- **The survivability domain must be the real failure unit.** Twenty sites on one host with
  `domain=site` let one host loss exceed m; that is not a defect of the code but the reason the
  domain is configurable per dataset (`agent`/`region` where hosts or sites are shared).
- **Agents did not always reconnect after the global broker restarted** (found by failure benchmark
  F5): after killing and restarting the global controller, several directly-attached agents stayed in
  `STUCK IN CONNECTION FAULT` and their gfs nodes went LOST for minutes, or until the agents themselves
  were restarted. **Root cause (Cresco controller, from the agent logs):** the loss event's re-init
  begins with `ActiveClient.shutdown()`, whose `ControlPlaneSender.shutdown()` took an unfair monitor
  that every control-plane sender also takes while it *(re)connects* — and a (re)connect on a
  `failover:` URI parks for ~20 s (5 attempts × 5 s). With 20+ plugin heartbeat/ping/watchdog senders
  each holding the lock 20 s, shutdown starved (6 min 45 s on one agent) and re-discovery of the
  restarted broker (which has a new certificate) could not start. Meanwhile every plugin thread that
  sent a message spun in `ControllerEngine.msgIn` ("STUCK IN CONNECTION FAULT", one ERROR/s/thread).
  **Fixed in the controller (W-GFS-6):** (1) `ControlPlaneSender` uses a fair lock with bounded waits
  (`controlplane_lock_wait_ms`, 5 s) and a non-blocking `shutdown()` (closed flag; senders fail fast;
  a connect in flight releases what it built); (2) dead failover transports are disposed *before* any
  JMS close so consumer/session/connection teardown cannot park on a reconnect
  (`ActiveClient.disposeIfDead/closeConnectionFast`, also used by `AgentConsumer.shutdown`);
  (3) `msgIn` holds a message at most `msgin_fault_wait_ms` (20 s) then drops it with one error line,
  and never holds locally-addressed messages. GFS handles the aftermath (re-registration, audit,
  repair) as before. Proof: failure benchmark F5 re-run on the fixed agent jar (`SCALE-RESULTS.md`).
- **Core nodes must be sized alike.** A replica co-located on a 1 GB agent OOM'd at 10^6 files while
  the 6 GB primary held 1.85 M files in 1.2–1.8 GB heap; replica on a 4 GB host converged in 8 s.

## 7. Next steps (ordered)

**Phase 0 — prototype (done, this repo).** Everything in §1–§2 runs locally on an 8-node fabric;
`EVALUATION-PLAN.md` records what is proven and what is planned.

**Phase 1 — Cresco foundation work GFS depends on**
1. ~~W-GFS-1 inter-tenant flow policy~~ (implemented 2026-09-17: `broker_cross_tenant_sinks`, unit-tested) + W-GFS-3 tenant-qualified FrameBus (P11, Phase 1: needs a dataplane publish-to-tenant API); ~~W-GFS-4 stable plugin identity~~ (fixed: persisted plugins reload under their own id); ~~W-GFS-5 bridge stability~~ (fixed: advertised broker ports); ~~W-GFS-6 agent reconnection after a controller restart~~ (fixed, proven 3×). Remaining Cresco item: W-GFS-2 per-tenant fair scheduling (routing plan W6).
2. FR-D1(b)/D3 per-message authorization PEP/PDP on filerepo actions (`clearrepo`, `putjar`,
   `removefile`, `streamfile`) — the origin must refuse anything that is not a verified gfs grant.
3. FR-D6(b) streamfile terminal frame + total length/hash; FR-D7(b) filerepo sync over the dataplane.
4. D4 `MessageSigner` into MsgEvent so grants/approvals/manifests are signed, not HMAC'd.
5. FR-D4(b) deletion propagation inside filerepo (gfs already compensates at the index).

**Phase 2 — identity.** InCommon/ORCID login at the client; cert-bound user assertions; approver
key registry for custody; admin roles from the fabric's RBAC seam (AC-3/AC-6).

**Phase 3 — index hardening.** Raft over 4 core nodes; snapshots + compaction; pagination and
secondary indexes for 10^7–10^8 files; per-dataset export quotas; measurement at scale (E13).

**Phase 4 — durability at scale.** Hierarchical LRC (local parity per site + global parity);
streaming encode of TB objects with resumable jobs; fragment batching/pipelining; policy vocabulary
(keep-in-state, jurisdiction, min sites); scrub scheduling proportional to class; "nag" pipeline and
ToS state machine (P9).

**Phase 5 — access surfaces.** S3-compatible gateway on wsapi (buckets = projects) with range reads
over `streamfile`; FUSE mount as convenience; DURABLE_ONLY fallback restore-through-read.

**Phase 6 — operations & compliance.** Dashboards from `getmetricinventory`; audit export; ledger
statements; DUA workflow; control traceability (AC-3/4/6, AU-2/3/10, IA-2/3, SC-8/12/13/28, SI-7,
CP-9/10) into the SSP.

**Phase 7 — pilot.** BTSA nine-site pathology sharing on the real mesh (region per site), restore
drills, and the reciprocity model with real pledges.

## 8. Open questions (with a recommendation)

| Question | Recommendation |
|---|---|
| Unit of publication | Directory-as-dataset with file-granular index (P14); manifests per dataset are an optional summary later. |
| Erasure ratio / hierarchy | Start RS(10,4) across sites for the federation tier (two-site tolerance, 40 % overhead); add LRC local groups in Phase 4. Prototype uses k=3, m=2 on six sites. |
| Who adjudicates key reconstruction | quorum of institutional approvers (2 of 3 in the prototype); the federation council as escrow-of-last-resort with its own approver key. Approvals must be signed, consumed on use, and audited. |
| Convergent encryption for cross-site dedupe | No for clinical data (equality leakage). Per-object random DEKs (as built). |
| Sites as regions vs agents | Regions (one regional controller per site) in production; the prototype attaches sites as agents to one global for size. |
