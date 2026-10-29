# The live tier

!!! info "Status (2026-10-28)"
    **Built and tested** on the `GaiaKeep/gfs` development branch; not yet merged to `main` or released.
    On the HPC test bed it passed its end-to-end checks and its crash cells on build `88f086d6`
    (2026-10-28), and its model-based test runs in every CI run. The final-build runs and the 72-hour soak
    are **in progress**. See [Test results](../built/tests.md#the-live-tier-and-stability-e18-2026-10-28).
    The live tier is what the roadmap called [the caching tier](../roadmap/caching-tier.md).

The durable tier keeps data safe: encrypted, erasure coded, deduplicated, on tape. It is not usable in
place. The **live tier** is every copy of committed data held as **ordinary files** on a **live node**
near compute, readable byte by byte at local-disk speed by any program on that host. It is never counted
toward durability: losing all of it loses nothing.

> "The durable tier is the only thing that is not native." (owner, 2026-10-27)

[![The live tier: an agent publishes a version; the core writes encrypted blocks to the durable tier; the version commits only when its tape copies are verified; the core registers a row, pushes the version over encrypted node streams to a live node, which verifies and places the files and signs an attestation; holds keep a copy; a deletion is journaled with its cause and ends on the node's signed attestation](../assets/live-tier-flow.svg)](../assets/live-tier-flow.svg)

## Two owner decisions shape it

Both were made on 2026-10-27:

- **Live copies are plaintext native files.** Programs read them as they read any file. Encryption ends
  at the live node; the durable tier stays encrypted.
- **No early copy.** Nobody reads a version from the live tier before it commits, the writer included.
  For a durable collection under tape-primary, a version commits when its tape copies are verified.

Because a key shred cannot reach a plaintext file, the core keeps a journaled **inventory** of every live
copy. A copy is registered before any byte moves, and every deletion ends only on the live node's signed
attestation that the files are gone.

## The pieces

| Term | What it is |
|---|---|
| **Live node** | A gfs plugin in the `live` role. It registers with the core like a storage node and is admitted by an operator as a live node. It never joins as a site, so no live copy is ever counted as a durable copy. |
| **Live root** | The directory a live node keeps its copies in. Node scope means the host's local disk. Site scope means a shared, authenticated filesystem mounted on a site's compute hosts. |
| **Live copy** | A committed version, or one path prefix of it, as read-only files. |
| **Workspace** | A writable copy seeded from a committed version, for edits that will be published as a new version. Node scope only. |
| **Row** | The core's journaled record of one copy or workspace at one node: `REALISING`, then `LIVE`, then `DROPPING`, then removed. |
| **Holder, lease, pin** | Who a copy exists for, how long it is wanted, and a named hold that keeps it until a time. |
| **Admission** | A tenant administrator's decision that a collection may be realised at a given node, tied to the node's pinned key. A different key at the same address is a different machine, and the admission lapses. |

The verbs are `core.realise` (the only verb that moves bytes into the live tier), `core.prospect`,
`core.livelist`, `core.livehold`, `core.livedrop`, `core.liveadmit` and `core.livepublish`. The Java and
Python clients expose them all, the command line has `gaiakeep realise | prospect | live …`, and the MCP
server has tools for realise, prospect and the live list.

## Making a copy: `realise`

A realise is an asynchronous job:

1. **Authorise.** The caller must be able to read the collection. The node must be a registered live
   node, answering the core, and admitted for this collection under the key it is pinned with now.
   Every path must pass the native-path rules (no absolute paths, no `..`, no links, no names a
   case-folding filesystem would merge).
2. **Wait for the commit.** While the version is `COMMITTING`, the job waits. It never reads around the
   commit gate.
3. **Hit, join or register, in one step.** A `LIVE` copy that already covers the request is a **hit**: the
   caller becomes a holder and the lease is raised. A copy still being made is joined. Otherwise the
   request must fit the node's budget and the tenant's admission budget; expired rows are evicted,
   earliest expiry first, until it fits, and the row is journaled as `REALISING` before any byte moves.
4. **Stage from tape** where blocks are only on tape, in batches the recall cache can hold.
5. **Push.** The core, the only place that can decrypt, reads the version through its gated read path and
   streams the files to the node over up to 4 node streams (by default), sealed with AES-256-GCM under keys from a
   signed key exchange. No file byte, no path and no digest of plaintext crosses a message broker.
6. **Verify and place.** The node writes into a private staging area, checks every file against a keyed
   MAC the core computed as it read it, fsyncs, moves the tree into place and signs a commit attestation.
   The core journals the row `LIVE` only when the node's keyed root equals the one it computed itself.

A failed or cancelled realise drops its row like any other. After a leader change, the new leader adopts
rows whose job stopped, and only the files the node does not already hold verified are sent again.

**Prospect** answers "what would it take?" without journaling anything: whether the version has committed,
its size, how much is on disk and how much only on tape, which live copies already exist, whether the
request would fit at the node, and a strategy (`present`, `wait-commit`, `copy-from-disk` or
`stage-from-tape`) with an estimated time.

## Keeping a copy: leases, pins and eviction

- A copy gets a **lease**: 7 days by default, at most 90 days. A hit or `livehold op=extend` raises a
  lease and never lowers it.
- A **pin** keeps a copy until a named time and can be renewed. A pinned copy also holds its version
  against routine pruning, so a running job's input is not pruned under it. FORGET, a legal order, a
  destroy or a withdrawal still remove it.
- **Eviction** happens only when a new realise needs the space, earliest expiry first. Pinned rows,
  unexpired rows and workspaces are never evicted.
- Every lease and pin change is also sent to the node, signed. A node that cannot reach the core drops
  rows whose signed expiry has passed.

## Workspaces and publishing

A workspace is seeded from a version and edited in place. `core.livepublish` pulls the change set over a
sealed stream from the node to the core and publishes a new version of the same collection, whose
provenance names the workspace and node. Once that version commits, the workspace is rebased onto it.
Its cost follows the changed files, not the size of the dataset. The writer reads the new version from the
live tier only after the commit, like everyone else.

## Deletion reaches every live copy

Every end of a copy is a **drop**, journaled in the same batch as its cause:

| Cause | What is dropped |
|---|---|
| FORGET or a legal order (including a withdrawal with purge) | every copy and workspace of the collections the record covers |
| Destroying a domain or a tenant | those collections' rows, and any row whose blocks reach a destroyed domain |
| Pruning a version | copies of the pruned version (a workspace seeded from it is kept and flagged) |
| Withdrawing a collection | every row of the collection |
| A grant revoked or expired | rows whose blocks were read through that grant |
| A holder's authority ending (unbound, disabled) | that holder; rows left with no holder |
| An admission withdrawn | the rows it covered at that node |
| Lease expiry, eviction, release, a failed realise, scrub damage | that row |

The rule tested for every trigger: **a `LIVE` row holds only files the core would serve now.**

A drop ends only on the node's **signed attestation** that the row's files and staging are gone.
An answer of "stuck" (something the node cannot delete), or of "absent" for a copy that was `LIVE`, is
never treated as a confirmation: the row is marked **unconfirmed** and an alarm is raised. The lifecycle
record that caused the drops keeps the evidence (counts per node, a Merkle root over the attestations, the
unconfirmed list), and it does not reach `CONVERGED` while any of its rows remain.

A node that does not answer keeps its drops queued and reported overdue; when it comes back it is sent its
drops first. A node also drops every row by itself once it has heard nothing signed from the core for its
offline bound (24 hours by default). An operator can end the rows of a node destroyed out of band; those
rows stay unconfirmed in the evidence. For a deep deletion the node overwrites each file before unlinking
it, and claims that coverage only where the operator attested that the live root has no snapshots.

**The inventory matches the disk.** The node and the core each keep a digest over the node's rows; when they
differ, or the node restarts or comes back, the core reconciles page by page. A row the node lacks is
dropped as missing; a file the core does not list is an orphan and is deleted.

## Reading a copy

Programs on the node read the files directly. A GaiaKeep client on the same host can also read a local
copy instead of streaming: it asks the core for the file's keyed MAC (the core runs the full read check
for that file) and copies the local file only if it proves itself, otherwise it streams as before. The core
authorises and audits each read made through a client. **Reads through the filesystem are governed by the
operating system and are not audited.**

**filerepo** is a client of the live node, never a storage binding. A filerepo repository can be backed by
a live copy or a workspace; a live-backed repository refuses every verb that would serve, write, delete or
sync its files, and `repostate` reports `LIVE`, `WORKSPACE_CLEAN`, `WORKSPACE_DIRTY`, `MIRROR` or
`ONLY_COPY`. filerepo also refuses any file under a live root.

## The node checks its own host

At start and every 30 seconds, a live node checks its host and **fails closed**: while a check fails it
accepts no new copy and reports why.

- The agent's own file service cannot reach the live root or the node's keys.
- No plugin on the agent runs commands or serves files as the agent's user, except a filerepo build that
  refuses live roots: every filerepo instance on the agent must list `repostate`, the verb that came with
  that build.
- The live root and the node's state belong to a dedicated operating-system user. Where compute jobs run as
  that same user, the node must be told so and reports itself as **shared-user, not production**.
- The kernel's link protections are on, or, where the node cannot read them, an operator has attested them.

A node that is still starting, whose own agent has not answered the checks yet, reports them as pending:
`realise` then answers **retryable** (status 11) rather than refused (owner decision 2026-10-28).

## Availability while the core changes

The live tier needs only a quorum of the core (owner decision 2026-10-28). A core peer that is down counts
by its last answer about what it supports, so new copies, extends and pins continue through a core restart
or a site roll. A peer whose last answer shows an older build still blocks them. Drops are never blocked,
because a silent peer must never hold up a legal deletion. See
[Stops, restarts and slow disks](stops-and-restarts.md).

## Limits

- **The operating system is the boundary on the node.** Root, and anyone the operating system lets read
  the live root, can read live copies. Admitting a collection at a node is the tenant administrator's
  decision that this is acceptable there.
- **A drop's evidence is the node's own signed attestation**, made with a key that lives on that host.
- **Some copies are beyond any drop:** copies people make with their own read access, snapshots and
  backups of the live root, network-filesystem client caches, open files until they close, the page cache
  and swap. Each lifecycle record's remanence statement lists them.
- **A partitioned node keeps its files** until it hears from the core or its offline bound passes.
- **A user can make a workspace directory the node cannot delete.** The row is reported stuck and stays
  unconfirmed.
- **The test deployment's live node runs shared-user** (compute jobs there run as the agent's user), and
  says so in its registration and status: it is not a production configuration.
- **Not in this phase:** a mounted filesystem view of versions not yet realised, one site's live copies
  serving another site, standing copies that follow a branch head, path-precise purges of workspaces, and a
  per-open audit on the node. An encrypted live root (per-tenant filesystem encryption keys held by the
  node) would let a key destruction reach the media; it is a deployment option, not built.

## Configuration

| Setting | Default |
|---|---|
| `core_livetier_flows` (node streams per realise) | 4 |
| `core_livetier_lease_ms` / `core_livetier_max_lease_ms` | 7 days / 90 days |
| `core_livetier_probe_ms` (how often the leader asks each live node) | 30 s |
| `core_livetier_drop_overdue_ms` (when a drop is reported overdue) | 10 minutes |
| `gfs_livetier_root`, `gfs_livetier_budget_bytes` | required on the node |
| `gfs_livetier_offline_purge_ms` (drop everything after this long without the core) | 24 hours |
| `gfs_livetier_checks_settle_ms` (start-up window for the host checks) | 120 s |

The full design is in the private `GaiaKeep/gfs` repository (`docs/LIVE-TIER.md`). This page is its
public summary.
