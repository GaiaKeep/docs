!!! info "Status: Proven (prototype)"
    How the September prototype works and how we know it works: 59/59 claims. It describes the erasure-coded prototype shape.

# Cresco Global File System (GFS) — how the system works and how we know it works

*System report, 2026-09-18 (final build). Every number below comes from executed runs on one code state: agent build of 2026-09-17 23:56 (controller `c891854`, library `04809e9`, wsapi `55c3929`) and `io.cresco.gfs` of 2026-09-17 22:44. Evidence files are named in §11. The mechanical claims registry reports 59 of 59 claims proven.*

## 1. Summary

GFS is a federated data-sharing and durability system built as a Cresco plugin. It lets any participant (a cluster, a lab server, a desktop) publish a dataset into a federation index without moving the data, share exactly the files it chooses through project namespaces, and optionally promote data into a durable tier that is encrypted with the owner's keys, erasure-coded, and spread across other institutions' pledged storage so that no single site can read it and no single site loss can lose it.

What is built and proven:

- One plugin bundle, `io.cresco.gfs`, with three roles (index, publisher, storage) on top of the existing Cresco mesh and the existing `filerepo` plugin; nothing in the transport was reinvented.
- A journaled federation index with a log-shipped replica, file-granular publications, projects with owners, delegates and members, and origin-enforced access grants.
- A durability tier: AES-256-GCM per stripe, systematic Reed–Solomon over GF(256), placement solved against a per-dataset survivability profile, blind holders, keyless repair, index-driven audit, and Shamir t-of-n custody of site keys with an approver quorum.
- A reciprocity ledger that turns pledged capacity, declared resiliency class, measured network and observed availability into an entitlement.
- An evaluation harness (functional, scale, multi-region, failure, soak, repeatability, global-restart, plugin-identity, bridge-stability) and a claims registry that marks a documented claim PROVEN only from executed evidence: 59 of 59.
- Four Cresco-side defects or gaps found by this work were fixed in the controller and proven: agents parked after a global-controller restart (W-GFS-6), persisted plugins reloading under a new id (W-GFS-4), same-host regional bridges flapping (W-GFS-5), and no policy for named cross-tenant flows (W-GFS-1). The fixes are on the `1.3` branches and embedded in the agent release.

## 2. The two objectives and the one machinery

1. **Sharing (primary).** Bytes stay where they are; only index entries move. Presence in the index does not mean the data is shared: the index is federation-internal under the data-use agreement, and the public surface is the project. An owner or delegate commits specific files into a project; members see exactly those.
2. **Geographic redundancy (secondary).** Between the participating universities there is essentially no geographic redundancy today. Pledged bulk capacity across sites gives a low-cost durability tier using global erasure coding rather than replicas (10+4 across sites tolerates two whole-site losses at 40 % overhead, versus 200 % for triple replication).

Both objectives run through the same components: one index, one placement engine, one transport. A durable copy is a publication whose destination is a set of blind stores.

## 3. Architecture on Cresco

**Roles.** The bundle's `gfs_roles` setting selects what an instance does.

| role | where it runs | what it does |
|---|---|---|
| index | federation core (primary plus read-only replicas) | registry of nodes, publications, projects, manifests, ledger, custody registry, audit; never sees bytes or keys |
| publisher | beside the `filerepo` instance that catalogs a dataset directory | exports catalog deltas (adds, updates, deletes) with a sequence number; holds the site key; encodes on promote; verifies grants before its filerepo streams a byte; restores |
| storage | any participant that accepted the storage terms | blind block store with a pledge and a declared resiliency class; custody of key shares; scrub; heartbeat; can run repairs |

**Planes.** Control traffic (registration, heartbeats, probes, deltas, project operations, grants, manifests, receipts, custody) rides Cresco `MsgEvent` RPC at the CONTROL QoS tier, which Cresco keeps on isolated sockets and bridge connectors. Bulk traffic (fragments and granted file streams) rides the Cresco dataplane at the BULK tier. Measured effect: control-plane RPC p99 of 0.72 ms while a 444 MB/s fragment flood is running on the same fabric.

**Tenant isolation.** Each site is a Cresco tenant (its regional controller and agents carry the site's `tenant_id`, leaf certificates `O=<site>`); the federation core is its own tenant. Every GFS flow is inter-tenant and named: site to core (registry, deltas, manifests, custody registry), core to site (encode, repair, probe instructions), site to site (fragments to blind stores, key shares to custody holders, granted fetches from a client to the origin). The broker policy now supports exactly this as an explicit, configured allow-list of named cross-tenant sinks (`broker_cross_tenant_sinks`, W-GFS-1): the three GFS flows are three rules, a rule never widens READ unless it says so, and nothing else crosses the boundary short of the superuser role. The prototype fabric still runs GFS in one tenant with admission enforced by the GFS layer (member sites only, source identity checked on every ingest); running each site as its own tenant end to end also needs the fragment bus to publish onto the destination tenant's dataplane topic (W-GFS-3, Phase 1).

## 4. How it works, step by step

**Publish.** A Cresco agent points `filerepo` at a directory. `filerepo` scans it, hashes every file with SHA-256 and keeps a Derby catalog. The publisher role reads that catalog, diffs it against what it last exported, and sends batched deltas, including deletions, to the index with a per-dataset sequence number. The index rejects stale deltas; a publisher that restarts adopts the index's sequence. Measured: 50,000 real files are visible in the index 10 s after they appear on disk.

**Share and fetch.** A project has an owner, delegates and members. An owner or delegate commits a dataset, or individual files, into the project. A member calls `resolve` on a file; the index checks membership and commitment and issues a short-lived grant bound to the user, project, dataset, file and expiry. The client opens a dataplane stream to the origin, which verifies the grant independently before its local `filerepo` streams the bytes. The origin returns a per-chunk SHA-256 list with the stream; the client verifies every chunk and re-requests only missing or corrupt byte ranges, so a lost dataplane frame costs one small re-fetch, never a corrupt file. Both the Python client and a Java client built on `clientlib` do this.

**Promote (durability).** The index checks that the caller is an owner or delegate and that the site's reciprocity entitlement covers the object, then solves placement against the survivability profile: one node per failure domain, origin excluded, jurisdiction and allow/deny lists respected, free pledge sufficient, nodes not already holding a fragment of the stripe, best score first. The origin then encrypts each stripe with AES-256-GCM (a per-object data key, IV = object nonce ‖ stripe counter, AAD = object ‖ stripe, so a fragment cannot be swapped between stripes or objects), erasure-codes the ciphertext with RS(k,m), and pushes k+m fragments over the dataplane with receipts. A holder that does not answer within the push timeout is replaced through the index by another holder that still satisfies the policy; the manifest records where bytes really went. The object becomes DURABLE only when the manifest is committed.

**Restore.** With the manifest and the site key (local, or reconstructed from custody), the restorer requests k plus a configurable redundancy of fragments per stripe from the holders, races them with short timeouts and retries slow holders in later rounds, decodes if any data fragment is missing, decrypts, and verifies the SHA-256 of the whole object against the manifest. The harness additionally compares the restored bytes' hash with the original file's hash on every restore.

**Liveness, audit and repair.** Storage nodes heartbeat; the index marks SUSPECT and then LOST after a per-profile grace. Independently, the index asks every holder which of its expected fragments are actually present and marks absent ones MISSING; nodes also scrub their own stores and report corrupt fragments as BAD. The repair planner re-places lost fragment indices on fresh eligible sites and regenerates them from any k surviving fragments of the stripe. Repair operates on ciphertext and never needs a key. If fewer than k fragments survive a stripe, the object is marked LOST with the reason instead of being pretended repairable, and it returns to DURABLE when the holders come back. Measured: a lost holder is detected by the audit in under 122 ms; 40 of 240 sites lost at once led to 85 objects repaired in 27 s with 7 beyond the coding limit by construction.

**Custody of keys.** The site key never leaves the site in the clear; it is Shamir-split t-of-n across storage nodes of n other sites. Reconstruction requires a quorum of institutional approvers; approvals are consumed on issue; holders release shares only against the resulting token; every step is audited. Measured: with exactly t of n holders alive the key reconstructs; with fewer it fails closed.

**Survivability profiles.** Every dataset carries a default profile; a project or a single promote can override it; the index refuses, with the reason, anything the federation cannot satisfy right now. The profile fixes the coding ratio and block size, the failure domain that every fragment of a stripe must be distinct in (`site`, `agent` or `region`), a minimum number of regions, origin exclusion, allow/deny lists, jurisdiction (keep-in-state), a free-space floor, repair grace and fetch redundancy. Placement enforces the profile on promote and on every repair, so an object never drifts out of policy. Measured: 12 of 12 profiles behave as specified on a single-region fabric and on an 8-region bridged fabric.

**Reciprocity.** A node's score is pledge × class weight × availability factor × network factor, where the network factor is capped at "good enough for restore" so fast hardware earns nothing extra on a backup tier. A site's entitlement is the sum of its node scores times the federation ratio; consumption is the fragment bytes stored elsewhere on its behalf, overhead included. The index refuses a promote beyond entitlement.

**Encode geometry.** The manifest must cover the whole file. The encoder pipelines stripes, and a defect (19)
drained that pipeline only on a short final read, so a file whose size was an exact multiple of `k × block_size`
lost its last `stripe_window` stripes from the manifest: the object committed DURABLE and could never be restored,
which the restore's SHA-256 check caught by failing closed. The drain now runs at every exit from the encode loop
and the geometry is asserted (`stripe_count == ceil(size / (k × block))`) before the manifest is committed; the
regression covers four geometries at exact-multiple, one byte under and one byte over.

**Monitoring.** The index is the federation's aggregator, so monitoring needs no fan-out: one read-only action, `storagesummary`, returns the counters (roster liveness split, pledged and used capacity, object health by derived state, repairs in flight, journal position), the roster, the reciprocity ledger and the objects that are not DURABLE (bounded). The index primary also pushes the same map every 10 s as a `gfs_state` beacon on the Cresco dataplane, the same publish/subscribe shape as the controller's route advertisements, so a monitor keeps its view under load without polling. Every instance registers per-role gauges (`gfs.index.*` only on an index, `gfs.store.*` only on a store) into Cresco's metric inventory, which is how the Cresco mesh dashboard (`github.com/CrescoEdge/dashboard`) detects a deployment and finds the index without configuration: its Storage tab appears only while GFS is present. Measured through the dashboard on a 49-node fabric (`gfs_dashboard_check.py`, result `scale_dashboard_20260918-094353.json`): the dashboard detected 51 gfs instances and the index address from the inventory alone; killing the agent that hosts 8 storage sites showed the affected objects not DURABLE 16.2 s after the kill (peak 6), all 8 stores LOST at 26.2 s, and every object DURABLE again at 36.3 s with the 8 stores still LOST; every tab rendered without errors and the poll path stayed healthy while the beacon fed the page.

**Index consistency.** The index has one mutation path: every change is a journal entry that is applied locally and shipped to replicas; replicas are read-only and catch up by log ranges or, when too far behind, by installing a snapshot. The state hash used to compare primary and replica is canonical (sorted keys), so equality is a statement about logical state. The production form is a small Raft group of four core nodes.

## 5. Security model in one paragraph

Holding sites are blind: fragments are ciphertext under the providing institution's key, fragment ids are unlinkable hashes, and a block store records only id, size, hash and owning site. No single site can decrypt alone, and no single site loss can lose a key. Access to shared files is authorized by the index and verified again at the origin, so a compromised or stale index cannot leak data. Grants and custody tokens are HMAC-SHA-384 in the prototype and are to be signed by the regional certificate authority with client identity bound by mutual TLS in production. Algorithms are SHA-256, AES-256-GCM, HMAC-SHA-384, Shamir and RS over GF(256), with a DRBG; the fabric's crypto baseline is FIPS/CNSA. Everything that changes state is audited, and unsatisfiable or unauthorized requests fail closed with a reason.

## 6. How we know it works

Evidence is produced by harnesses that run against a real fabric (real JVMs, real brokers, real filerepo catalogs, real bytes on disk), and every restore is compared with the original file's SHA-256. All rows below were measured on the final build on 2026-09-17/18.

| tier | what it does | result |
|---|---|---|
| Functional E1–E11 (7 sites) | deploy; registry, liveness, probes, scores; publication deltas incl. deletes; project authorization matrix; grants enforced at origin; promote/restore; blind-holder entropy checks; repair without key; index-driven audit; custody quorum; entitlement; replica convergence | 99 of 99 checks pass (82.6 s) |
| Scale, single region | 240 storage instances on 12 agents; transport sweeps; durability sweep 1 MiB–1 GiB at 3:2, 6:3, 10:4; node scale; 12 survivability profiles; passive-failure tolerance; storm (40 sites lost); repeatability ×3 | all measured, see §7; 12/12 profiles; storm healed in 27 s |
| Scale, multi-region (fixed bridges) | 8 same-host regional controllers with their own brokers bridged to the global, 72 sites; bridge-stability count; transport; policy; tolerance; durability; storm with `domain=region` | 0 bridge flaps in a 150 s window (was 191 per region); 12/12 profiles; cross-region push 576 MB/s, get 648 MB/s; bridged client fetch 129.7 MB/s with 0 re-fetched chunks; region storm: 49 degraded, 0 beyond m, healed in 12 s |
| Failure F1–F8 (240 sites) | repairer dies mid-repair; source holder dies mid-repair; corrupt bytes served; custody holders lost to exactly t and below; index primary restart; publisher restart; beyond-m loss and return; mixed load during a storm | F1 healed by another node in 78 s; F2 healed in 33 s; F3 86 fragments corrupted, restore verified in 0.55 s, index marked 86 BAD, repaired; F4 reconstructs with 3 of 5, fails closed with 0; F5 index answering in 9.9 s, all 240 nodes back in 34 s unattended, durable layout preserved, replica equal, promote and restore work after; F6 publisher back in 0.1 s, restore and fetch work; F7 five agents killed, 9 LOST and 1 DURABLE reported, LOST restore refuses, all DURABLE after return; F8 16 of 16 promotes succeed at p50 1.01 s while two agents die and repairs run |
| Global-controller restart ×3 (240 sites) | kill and restart the index core's controller and broker; no manual agent restarts allowed | all 12 agents back in ≤ 44.2 s on every run, per-agent reconnect ≤ 3.6 s, zero stuck-connection log lines, promote and restore work after each (also 3/3 on the previous build, and 2/2 on a 4-agent fabric) |
| Plugin identity (W-GFS-4) | deploy a storage plugin without a pinned id, kill and restart its agent | JVM pid changed, the same node id came back UP in 17.2 s, no new id appeared |
| Soak, 20 min | mixed promote/restore/fetch with a random agent killed every ~90 s and restarted 30 s later | 484 operations (195 promotes, 195 restores, 94 fetches), 13 kills, error rate 0.0 %, all objects DURABLE at the end, index RSS 944 → 993 MB |
| Java client under load | 256 MiB verified fetches during the soak | 5 of 5 verified, median 395 MB/s (quiet fabric: 393 MB/s) |
| Claims registry | every documented claim evaluated mechanically from result files | 59 of 59 PROVEN (`CLAIMS.md`, 2026-09-18 00:27) |

## 7. Measured performance

Single host (14-core Apple silicon, 36 GB); all nodes share the loopback network, so these are compute, broker and protocol ceilings, not WAN numbers.

| path | measurement |
|---|---|
| Reed–Solomon, native, one thread, 256 KiB blocks | 3:2 834 MB/s; 6:3 568 MB/s; 10:4 423 MB/s; 20:6 282 MB/s (worst-case decode equals encode) |
| Reed–Solomon 10:4, 14 threads | 3,872 MB/s encode (4,216 MB/s in the earlier run) |
| AES-256-GCM per stripe | 3,389 MB/s encrypt, 3,472 MB/s decrypt at 2.5 MiB stripes |
| Fragment push, node to node | 577 MB/s peak (512 KiB frames, 32 concurrent); get 429 MB/s |
| Control RPC under a 444 MB/s flood | p99 0.72 ms |
| Promote (encrypt, encode, place) | 233–291 MB/s for 256 MiB–1 GiB objects |
| Restore (fetch, decode, decrypt, verify) | 254–393 MB/s |
| Java client verified fetch, 256 MiB | median 393 MB/s quiet, 395 MB/s during the soak; 5 of 5 verified |
| Python client fetch | 144 MB/s |
| Holder loss detected by audit | < 122 ms |
| Storm, 40 of 240 sites lost | 85 objects repaired in 27 s; control p99 0.5 ms during the storm |
| Index, 1,000,000 files (core-sized replica) | ingest 143,444 files/s; 1,811 MB heap; resolve p99 0.4 ms at 5,398 resolves/s from 16 clients; replica converged in 14.2 s |
| Placement solve and promote at 240 sites | 3 ms; index at 19 % of one core under 240 heartbeats |
| Global-controller restart | index answering 8–10 s; 240 nodes re-registered in 32–44 s |
| Cross-region (8 bridged regions) | push 576 MB/s, get 648 MB/s; control p99 0.71 ms under flood; bridged client fetch 129.7 MB/s |
| filerepo publication, 50,000 files | visible in 10 s (4,929 files/s including scan, hashing, catalog and export) |

## 8. Defects found by the evaluation and what was done

Eighteen defects and harness weaknesses were found and fixed during the campaigns; the full list is in `RESULTS.md`. The ones that matter for the design:

- **Agents did not reconnect after the global controller restarted (Cresco controller, W-GFS-6).** The loss recovery began with a client shutdown that waited on an unfair lock held by control-plane senders while each of them sat in a 20 s failover reconnect; with 20+ senders the shutdown starved for minutes and re-discovery of the restarted broker (which carries a new certificate) never started. Fixed: a fair, bounded sender lock with a non-blocking shutdown; dead failover transports are disposed before any JMS close; the inbound message path holds a message at most 20 s instead of spinning forever. Proven by nine global restarts across three fabrics with every agent back unattended.
- **Same-host regional bridges flapped every ~7 s (Cresco controller, W-GFS-5).** Every peer bridge was built to `<peer ip>:discovery_port_remote`, which on one host with several regional brokers is the global's broker; the remote-name check failed, the path was declared lost and re-discovered. Fixed: discovery replies advertise the responder's bound broker port and bridges and agent channels use it. Proven: 0 flaps in 150 s across 8 regions, previously 191 per region.
- **Persisted plugins reloaded under a fresh id (Cresco controller, W-GFS-4).** A restart minted `plugin-<uuid>` unless the deploy pinned an id, so anything keyed by region:agent:plugin saw a new node. Fixed: a persisted plugin restarts under its own id. Proven by the identity check.
- **No way across the tenant boundary except superuser (Cresco controller, W-GFS-1).** Implemented named cross-tenant sinks as a configured allow-list that never widens READ unless it says so; unit-tested (4/4) in the controller build.
- **Correlated placement.** A top-k placement put every object on the same best-scored sites, so one storm marked everything LOST; placement is now weighted-random by score and free capacity (236 of 240 sites used).
- **Holder loss invisible to the holder.** A node whose fragment and sidecar were both deleted had nothing to scrub; the index now audits holders for expected fragments.
- **Replica state hash after a snapshot install.** The same logical state serialized in two map orders; the hash is now canonical.
- **Publisher sequence after restart.** Deltas were rejected as stale; the publisher adopts the index's sequence.
- **Survivability domain versus real failure unit.** On a topology where 20 sites share a host, `domain=site` let one host loss exceed m. This is not a code defect; it is why the domain is configurable per dataset (`agent` or `region` where hosts or sites are shared).

## 9. Limits of the evidence and what is not built yet

- All measurements are on one host. Multi-host and WAN numbers are the next venue (the DGX mesh).
- The index runs as a primary with log-shipped replicas; the Raft group is designed, not built.
- Hierarchical (local-parity) codes are represented by the local resiliency class in scoring; full local parity groups are a roadmap item.
- Grants and custody tokens use a federation secret; regional-CA signatures and mTLS binding of the client identity are the production form. Site keys are files with 0600 permissions; production is PKCS#11/HSM/KMS.
- S3 and FUSE gateways are not built; access is programmatic through the Python and Java clients.
- Cresco items still open from this work: W-GFS-2 per-tenant fair scheduling (routing plan W6) and W-GFS-3, the fragment bus publishing onto the destination tenant's dataplane topic (needs a dataplane publish-to-tenant API). W-GFS-1, 4, 5 and 6 are fixed and proven.

## 10. Next steps

1. Run the campaigns across real hosts on the DGX mesh to obtain WAN-shaped numbers and to exercise regional brokers on separate machines.
2. Land W-GFS-3 and run each site as its own tenant end to end with the cross-tenant sink rules, then re-run the tenant-isolation checks live.
3. Replace the federation secret with regional-CA signed grants and approver signatures; move site keys to an HSM/KMS.
4. Raft for the index core; local parity groups for in-site repair.
5. An S3-compatible gateway on the granted-fetch path, then a FUSE convenience mount.
6. Pilot with the nine-site pathology sharing effort under the data-use agreement.

## 11. Where the code and evidence are

- Plugin, docs and harness: `github.com/CrescoEdge/gfs` (branch `1.3`; `docs/` and `eval/`).
- Storage tab of the Cresco mesh dashboard: `github.com/CrescoEdge/dashboard` (`master`; `code/dashboard` in the workspace, `./run.sh start`, self-detects GFS from the metric inventory, pushed `gfs_state` beacon with `storagesummary` poll fallback).
- Cresco controller fixes: `github.com/CrescoEdge/controller` commits `4995b31` (W-GFS-6) and `c891854` (W-GFS-1/4/5), on `1.3` and `phase0-crypto-baseline`; agent release `github.com/CrescoEdge/agent` `1.3` commit `19a7018` embeds them; matching `library`, `filerepo`, `clientlib`, `wsapi`, `repo`, `pycrescolib` `1.3` branches.
- Result files: `run/gfs/results/*.json` (campaign 6 stream preserved as `campaign6-final-proof-monitor.log`); generated reports `SCALE-RESULTS.md` and `CLAIMS.md`; design `CORE-PRINCIPLES.md`; plan `EVALUATION-PLAN.md`; defect log `RESULTS.md`; local build and run `PROTOTYPE.md`.
