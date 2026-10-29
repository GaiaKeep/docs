# Operations

*Added to the dashboard on 2026-10-08.*

What an operator watches besides the storage itself: the core's own gauges on every agent, and how much
memory each message broker needs for the traffic that crosses it. Like every page it is read-only.

## Core gauges per agent

One row per Cresco agent whose metric inventory carries the storage core's `gfs.core.*` gauges, read
through the dashboard's mesh poller (not through a core verb):

| Column | Meaning |
|---|---|
| Agent | The agent's address. |
| Raft role / Term / Commit | The core peer's Raft role (`LEADER`, `FOLLOWER`, `PRECANDIDATE` or `CANDIDATE`), its term, and its commit index. |
| Apply lag / Max follower lag | Entries committed but not yet applied on this peer, and, on the leader, the furthest-behind follower. |
| Quorum | The peer's quorum verdict: `OK`, `AT_RISK` (one more loss would lose the majority) or `LOST`. |
| Audit | The audit log's state: `ok`, `lost`, `failed` or `unavailable`. A peer whose audit log lost records can be set to serve only the audit verbs until a system administrator acknowledges the loss. |
| Keys mismatched | Storage nodes whose key no longer matches its pin. |
| Frame drops / Raft bulk dropped | Dataplane frames the core dropped, and bulk Raft traffic dropped by the transport. Both should stay at 0. |
| JVM heap used | The agent's Java heap in use, from its health report. |

The same gauges feed the agent's Felix health check: it is **critical** when the audit log is lost or
failed, the serving gate is closed or the quorum is lost, and a **warning** when the quorum is at risk or a
key does not match its pin. With the mesh poller off, or before the core reports these gauges, the page says
so instead of showing an empty table.

## Broker sizing

How much memory each broker must be allowed so that the windows and budgets of the processes whose frames
cross it never overflow it. The page runs the storage core's own broker-sizing model, fed with the
deployment's budgets from `core.status` (or the model's defaults, marked *model default* where the core
does not report one):

- **Budgets:** the stream, upload, download and Raft batch budgets, each with where it came from.
- **The deployment:** the number of core peers, whether followers serve reads, and the window a flow needs
  for 1 GB/s at 1 ms and at 20 ms round trip.
- **Per broker:** for a single hub broker, and for one regional broker per site when the core peers sit in
  different regions: the bytes in flight, the broker's `memoryUsage` limit it needs (at least 1.25 × in
  flight) and the JVM heap that broker's host needs (at least 512 MiB + 2 × `memoryUsage`), and the matching
  heap setting.

The broker's own memory use is not in the Cresco metric inventory; each agent's heap is in the table above.

## What it does not show yet

The raft log's health (unsynced bytes, sync lag, stuck-disk hand-overs, parked writes) is shown on the
[Overview](overview.md#core-log-raft) from each peer's `core.status`, not here: the core does not yet export
it as gauges.
