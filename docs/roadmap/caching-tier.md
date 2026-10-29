# The caching tier, now the live tier

!!! success "Status (2026-10-28)"
    **Built and tested** as [the live tier](../concepts/live-tier.md), on the `GaiaKeep/gfs` development
    branch: not yet merged to `main` or released. It passed its end-to-end checks and crash cells on the HPC
    test bed (build `88f086d6`, 2026-10-28); the final-build runs and the 72-hour soak are in progress. The
    roadmap scheduled this tier after the durable storage core; that order held.

## What changed from the plan

> "The actual storage will be tightly versioned datasets, which can be recreated anywhere, and when
> they are live, they are considered a cache, either versioned or unversioned." (owner)

The role is the one planned: the durable, versioned store is the source of truth, and every live copy is a
cache of a named version (a **live copy**) or unversioned work in progress (a **workspace**) until it is
published. Three owner decisions fixed what was open:

- **Native files** (2026-10-27). Live copies are unencrypted native files: "the durable tier is the only
  thing that is not native". The core therefore keeps a journaled inventory of every copy so that deletion
  can still reach them.
- **No early copy** (2026-10-27). Nobody, the writer included, reads a version from the live tier before it
  commits.
- **filerepo's role** (2026-09-23, confirmed in the build). filerepo makes and manages local copies and
  publishes new versions, as a client of the live node, never as a storage binding. Its earlier
  `phase0-crypto-baseline` commit was not merged: its idea (never wipe the only copy; report a repository's
  state by comparison) was rebuilt on filerepo's main line.

## The plan, as built

| Planned | As built |
|---|---|
| Materialise a version or extract to a locus, streamed and verified block by block | `core.realise` to a live node: pushed over sealed node streams, every file verified by the node, placed atomically. Extracts are not a realise source yet. |
| Delta materialisation: bring a cache from version *n* to *n+1* | Files the node already holds, verified, in another copy of the same collection are linked instead of sent; a retried realise sends only what is missing. A copy that follows a branch head is **not in this phase**. |
| Leases on residency | Leases (7 days by default, 90 at most), extends, pins and holders. |
| Eviction that respects leases and never evicts an only copy | Eviction only at admission, earliest expiry first; pinned, unexpired and workspace rows never evicted. A live copy is never an only copy: the durable tier always holds the version. |
| Publish-back, including branch and merge | `core.livepublish` publishes a workspace's changes as a new version of its own collection (on the base version's branch unless it names one), then rebases the workspace. Merging is not built. |
| Placement from measured locus properties | Admission and budgets per node and per tenant; placement across live nodes by measured properties is not built. |
| Coherence: a cache always knows its version | Every row names its version; a `LIVE` row holds only files the core would serve now, and the node's keyed root must match the core's. |
| Audit: what was materialised where, for whom, under which grant | Every live verb is audited, with paths as keyed tags so a FORGET's redaction reaches them; every drop ends on a signed attestation kept in the lifecycle record. Reads through the filesystem are not audited. |

`repostate` reports `LIVE`, `WORKSPACE_CLEAN`, `WORKSPACE_DIRTY`, `MIRROR` or `ONLY_COPY` (the plan had
`CACHE`, `CACHE_WITH_UNCOMMITTED` and `ONLY_COPY`), and `clearrepo` still refuses an only copy without force.

## Still open

- Merge to `main` and a release, after the final-build runs of the
  [evaluation plan's E18 gate](../built/tests.md#the-live-tier-and-stability-e18-2026-10-28) and the 72-hour
  soak.
- A mounted filesystem view of versions not yet realised; one site's live copies serving another; standing
  copies that follow a branch head; path-precise purges of workspaces; a per-open audit on the node.
- An encrypted live root as a deployment option.
- The live tier's realise throughput: 192–206 MB/s on 4 flows on the test bed, well below the node leg
  measured earlier (see [Benchmarks](../built/benchmarks.md#live-tier-realise-hpc-2026-10-28)).
