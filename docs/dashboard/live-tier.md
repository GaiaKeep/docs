# Live tier

*Added 2026-10-28. The page works against a core built with the live tier (the gfs development branch; see
[The live tier](../concepts/live-tier.md)).*

The live tier's copies, the live nodes that hold them and the rows of the core's inventory: unencrypted copies
of the files of committed versions (any type, byte for byte) near compute, which never count toward durability. Like every page, it is read-only and
every datum comes from a signed core verb under a named profile's role.

![The Live tier page: tiles for live nodes, copies, bytes held, realising, drops overdue, shared-user nodes, realise jobs and live-tier alarms; the live-node table with the core's probe, what a new realise would be answered, host checks (one node still settling after a restart), budgets and host classes; one page of the core's inventory of live rows](../assets/dashboard/live-tier.png)

A core whose `core.status` has no `livetier` block shows **"live tier not enabled"** and is asked nothing more.

## The tiles

From `core.status` `livetier`, every 10 s in the background (no role needed):

| Tile | Meaning |
|---|---|
| **Live nodes** | Live nodes that answer the leader's probe, of those registered. Amber when any is not answering. |
| **Copies** | Live copies, with the number of workspaces beneath. |
| **Bytes held** | Bytes the inventory counts at live nodes: planned bytes of copies being made (`REALISING`), `LIVE` copies, and copies being dropped (`DROPPING`). |
| **Realising** | Copies being made now, with the number being dropped. |
| **Drops overdue** | Drops not attested within the overdue bound (10 minutes by default), with the number of **unconfirmed** rows. Red when either is not zero: these are unencrypted copies the core cannot yet prove gone. |
| **Shared-user nodes** | Live nodes whose compute jobs run as the agent's own user. Amber, labelled *not production*. |
| **Realise jobs** | Realise jobs running on the leader, and how many requests a copy already there answered (hits). Shown when the leader's own `gfs.livetier.core.*` gauges reach the dashboard. |
| **Live-tier alarms** | Alarms the leader raised since it started: unconfirmed drops, stuck rows, changed node identities, missing or damaged rows. Amber when not zero. |

## Live nodes

One row per live node, from the paged node registry (`core.node op=list`, the records whose roles include
`live`, 500 per page, read as observer, auditor or system-admin, every 30 s):

| Column | Meaning |
|---|---|
| Node / Domain | The node's address and the failure domain (site) it sits beside. |
| Core probe | `UP` or `DOWN`, as the leader last heard the node's signed liveness answer, and for how long. |
| New rows | What a realise at this node would be answered now, by the core's own rules: `accepted`, or the status and rule. A retryable answer (status 11, for example while the node's host checks settle) is shown in blue; a refusal in red. Admission per collection is not shown. |
| Agent gauges | Whether the node's own `gfs.livetier.*` gauges reach the dashboard through the Cresco mesh poller. |
| Budget / Used / Budget left / Free on disk | The node's budget for live copies, the bytes its rows hold, what is left, and the free space on its live root. |
| Copies / Workspaces | From the node's own gauges. |
| Shared user | `dedicated`, or `shared user · not production`. |
| Link protection | `read` when the node can read the kernel's link protections itself; `attested by operator` when an operator attested them because the node cannot read them. |
| Scope | `node` (local disk) or `site` (a shared, authenticated filesystem, with whether the operator attested it). |
| Host checks | `ok`; `settling` (blue) while a starting node's own agent has not answered yet, when a realise there answers retryable; or the failing checks (red), when the node accepts no new copy. |
| Orphans | Files at the node that no row lists, waiting for the reconciliation pass to delete them. |
| Pinned / Admitted | Whether the node's key is pinned, and which principal admitted it and when. |

A fact the core does not serve is shown as "—", never guessed, with a note saying so. When the mesh poller is
off the page says that the gauge columns have no source.

## Live rows

One page of the inventory (`core.livelist`, 100 rows per page by row id, cached 15 s). A picker above the
table chooses whose rows to show:

- **a node**: every row at that node, read as observer, auditor or system-admin. Selections are shown as
  **keyed path tags**, because these roles may not see paths;
- **a tenant**: that tenant's rows at every node, read under the tenant's own tenant-admin profile, which sees
  each selection as its **path prefix**.

| Column | Meaning |
|---|---|
| Row | The row id (`lt_…`). |
| Node | Where the row lives (in the tenant view). |
| Collection / Version | The collection and a short form of the version id. |
| Selection | The prefix of the version the row holds, a path tag, or *withheld* when the core gives this profile neither. Empty means the whole version. |
| Mode | `copy` or `workspace`. |
| State | `REALISING`, `LIVE` or `DROPPING`. |
| Size / Files | Bytes and files in the row. |
| Lease end / Expiry | When the lease ends (a workspace has none), and the effective expiry including pins. |
| Pinned / Holders | Whether a pin holds the row, and how many principals hold it. |
| Drop | For a dropping row: the reason (`lc`, `withdraw`, `grant`, `expired`, `release`, …), and an `overdue` or `unconfirmed` mark. |

Under the table: the page's totals (rows, bytes, files, pinned rows, rows by state) and a link to the next
page. The dashboard shows a selection exactly as the core sent it to the profile that asked, and adds no path
the core withheld.

The page also says what the core does not report and is therefore not shown: whether the live tier's
feature gate is open, awaited or blocked, each workspace's pending change checks, and who set each pin.

## On the Overview page

The [Overview](overview.md) carries a **Live tier** tile (copies, live nodes up of registered, bytes held,
drops overdue) that links here. Drops overdue and unconfirmed drops are health **issues**. Live nodes not
answering, shared-user nodes, and a node whose host checks are settling or failing are **notes**: a live
node holds no durable data.
