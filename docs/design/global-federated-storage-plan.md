!!! note "Status: Historical record"
    The starting plan: federated sharing with an opt-in durability tier.

# Global Federated Storage — Working Plan

*Cresco-based statewide (and potentially national) data sharing with an opt-in durability tier. Draft from 2026-09-13 discussion.*

## 1. Objectives

1. **Data sharing (primary).** Any participant in Kentucky — cluster, lab server, desktop — can publish a dataset into a federated index and expose it to collaborators through per-project namespaces. Data never moves; it stays on the contributor's hardware and storage tier of choice.
2. **Geographic redundancy (secondary, same machinery).** Between the participating universities there is essentially no geographic redundancy for most data today. Pledged bulk capacity across sites provides a low-cost, low-performance durability tier using global erasure coding rather than replicas.

Both objectives are served by the same capability: indexing, routing, and storing data at federated locations.

Basis: BTSA — the existing nine-site international pathology data sharing effort — and the federated pathology imaging work. Possible broader national effort or product.

## 2. Existing Cresco capabilities to build on

- Mesh networking across sites and networks
- Policy and message routing, in-band (message passing) and external
- Multitenancy: operations at one site do not affect another
- **File repo**: indexes local files at a location and synchronizes files between locations

## 3. Architecture

### 3.1 Publication
A Cresco agent points file repo at a directory. The dataset becomes visible in the federation index. Bytes stay put; only index entries propagate.

### 3.2 Federation index (core nodes)
- Distributed across core servers — probably four, operated by the federation
- Holds raw information: native directory structure, location, metadata, MD5 hashes
- File changes batched and replicated between cores
- Governed by a DUA among participating sites: sites agree to provide information about their data; recipients may not share the index further
- Presence in the index does **not** mean the data is shared

### 3.3 Projects / repositories (the public surface)
- A user creates a project and adds delegates; multiple people may be responsible for a project
- Users uniquely identified via InCommon, ORCID, or similar
- A dataset owner (or delegate) commits specific data — down to the individual file — to a project
- Permissions are project- and group-based
- The world sees individual projects, not a global namespace that is 99 percent inaccessible

### 3.4 Access
- Presented programmatically: S3 or other API-based storage first, FUSE mount points as a convenience
- Fetches are routed by Cresco back to the holding site; policy enforced at origin
- Index carries availability state per file; project commitment can optionally promote a file into durable pledged storage so the project does not depend on a single host being awake

### 3.5 Durability tier
- Opt-in per dataset
- Sites pledge a fraction of bulk capacity (e.g. ~25 percent)
- Encrypt with the **providing institution's keys**, then chunk, then erasure code — holding sites are blind block stores and cannot read what they hold
- Hierarchical erasure coding preferred over flat: local codes handle in-site failure, global parity handles whole-site loss (e.g. 10+4 across sites ≈ two-site tolerance at ~40 percent overhead vs 200 percent for triple replication)
- Placement is a policy solve: no two fragments of a stripe on one site, respect pledge capacity, respect legal constraints (e.g. keep-in-state), prefer network headroom
- Manifest index (object → stripe layout, fragment locations, key reference, policy) needs stronger consistency than the bulk tier (Raft over a small set of nodes)
- Performance is not a concern on this tier; encryption cost is acceptable

### 3.6 Key custody
- Shamir threshold sharing across a mesh of system-maintained nodes; quorum of sites can reconstruct, no single site can decrypt alone (same pattern as Vault unseal keys)
- Reconstruction authorization is policy: quorum of institutional representatives, or automatic trigger on verified site loss with audit trail

### 3.7 Reciprocity ledger
- A participant's backup quota equals what they contributed in storage or paid into the system
- Contribution value is a scoring function, not raw capacity:
  - capacity
  - declared local resiliency class at device registration (USB drive with no redundancy … server-grade clustered file system), each with its own durability measurement
  - measured network connectivity, weighted toward read-out/recovery bandwidth
  - observed performance and availability over time (active writes, file system monitoring, periodic scrub of fragments with hash verification)
- Performance capped at "good enough for restore": hyperfast NVMe earns no extra credit on a backup tier; a petabyte on a 100 Mb link is not useful
- **Node class is assigned per agent, not per site**

## 4. Participation tiers

| Tier | Requirements | Notes |
|---|---|---|
| Client | Any device, including laptops | Can publish, browse, commit, fetch |
| Storage node | Terms of service: intended to be internet-connected 24/7; registered resiliency class | Hardware bar deliberately low — a volume under a desk qualifies if generally reachable |

Storage node terms include: the system monitors and aggressively nags on downtime; if a durable node remains unavailable and the operator does not respond, the federation may take action to make the affected data available elsewhere (re-encode affected stripes). This is a stated feature of the agreement, not an automatic action.

## 5. Open questions

- Unit of publication (directory / dataset with manifest / object) — decides index granularity; file-granular across the Commonwealth gets big quickly
- Exact erasure coding ratio and hierarchical scheme
- Who adjudicates key reconstruction, and the escrow role of CPE or the federation
- Convergent encryption (cross-site dedupe) vs. equality leakage — likely not for clinical data

## 6. Context: Pure Storage evaluation (same session)

Pure was assessed as fast local storage with a fleet manager (Fusion, ActiveCluster, Portworx), not a federated or computational storage answer. FlashBlade//EXA uses in-kernel pNFS over RDMA with GPUDirect support and no vendor client. Possible fit only as a low-touch bulk tier under self-built fast storage. It does not address the federation problem above.
