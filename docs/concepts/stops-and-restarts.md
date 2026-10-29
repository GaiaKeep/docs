# Stops, restarts and slow disks

!!! info "Status (2026-10-28)"
    **Built and tested** on the `GaiaKeep/gfs` development branch (the integration of the raft-stall,
    store-roll and clean-stop work); not yet merged to `main` or released. The planned-stop case passes on a
    local fabric with a live node (E18 LT-C3, 2026-10-28). The same runs on the HPC test bed, on the final
    build, and the 72-hour soak are **in progress**. See
    [Test results](../built/tests.md#the-live-tier-and-stability-e18-2026-10-28).

> "Make sure this is highly tested and there are good test and evaluation and chaos testing and cases.
> This system must be stable. Once we prove it on [the HPC cluster], we will move to a much larger scale FABRIC
> test." (owner, 2026-10-28)

A storage system is restarted far more often than it fails: upgrades, configuration changes, a batch
scheduler ending a job. This page describes what the core guarantees in those moments: a planned stop of a
core peer, a storage node restarted under writes, and a disk that is slow or stuck. The chaos stage found
the defects behind most of it (see [Test results](../built/tests.md)).

## A planned stop of a core peer

[![A planned stop of the core's leader: the stopping peer refuses requests with status 12, naming the other peers; admitted requests finish; it hands the leadership to the most caught-up voter, which serves about 0.73 s after the signal; clients retry at the new leader; the old peer lingers 3 s and exits](../assets/planned-stop.svg)](../assets/planned-stop.svg)

When a core peer is stopped on purpose (a restart, an upgrade, the plugin removed):

1. **It refuses at once, with directions.** From the stop's first moment the peer refuses every request
   except raft traffic with status 12 and `stopping=true`. The refusal names the leader once the peer knows
   one other than itself, the other core peers, and a `retry_after_ms`. Nothing new runs there.
2. **It lets admitted requests finish**, for at most 3 seconds.
3. **A leader hands over.** It takes no new proposals and sends `TIMEOUT_NOW` to its most caught-up voter,
   which is elected without waiting for an election timeout. A write refused meanwhile does not cut the
   hand-over short.
4. **Every stopping peer retires.** A retired peer appends, applies and installs nothing more and never
   campaigns, but until its transport stops it still answers vote requests (so the peer it handed over to
   can be elected even when it needs that vote) and answers the new leader's appends with what it holds.
5. **It lingers** for 3 seconds answering its refusal, so clients that call it then are sent on, and then
   exits. The whole stop is bounded: the core's share at 10 seconds, the plugin's at 25 seconds. The process
   exits on SIGTERM by itself.

A stop that outlives its bound never shares its files with a new instance: each instance and each core log
holds its directories with an operating-system lock until its stop has really ended. A new instance waits
up to 60 seconds for them, and otherwise refuses to start (fail closed; start it again).

### What clients do

The Java and Python `CoreClient` follow the refusal to the leader it names, or to another core peer, and ask
again within the call's own time limit. They resend a request **only when that is safe**:

- a read, a request keyed by a `request_id`, or a live-tier extend, pin or unpin may be sent again;
- a job that a leader change cut (it ends `FAILED interrupted`, retryable) is submitted again under its
  `request_id`, and asked again after `retry_after_ms` if the new leader answers busy (status 11);
- a write whose leadership ended under it answers status 12 with **`outcome_unknown=true`**: the next leader
  decides whether it happened, and a client that cannot resend it safely raises `OutcomeUnknown` rather
  than guessing.

**Open:** a call that is not safe to send twice, sent to a peer at the instant its process exits, still gets no
reply (a timeout, as for a crash). The linger narrows that window; a `request_id` on the remaining verbs
that lack one would close it.

**Measured** (local fabric with a live node, 2026-10-28, E18 LT-C3): 10 planned stops of the leader, each
process out by itself in 3.34–3.86 s, the next leader serving 0.726–0.740 s after the signal, no halted
log, no spontaneous election, **0 failed client calls** counting every call that overlapped a stop, and
1,260 acknowledged writes all read back. Before the fix, on the same harness: every process was killed after
60 s and 5–36 client calls failed per stop. On the HPC test bed: in progress.

## A storage node restarted under writes

[![A storage node restarted under writes: the stopping store refuses new writes and sends a signed departure notice bound to its boot; the leader counts its site down for new work at once and places writes on the other sites, committing on two; the store's new boot registers, is counted up once verified, and repair restores the third copy](../assets/store-restart.svg)](../assets/store-restart.svg)

A rolling upgrade restarts storage nodes one at a time while clients keep writing.

- **The store says it is leaving.** A storage node that stops on purpose first refuses new writes (signed,
  retryable, marked draining) and sends every core peer a **signed departure notice**.
- **The notice is fenced to the node's boot.** Every registration names the node's boot, and the core
  takes a node's current boot from the node's own verified answers, which cannot be replayed. A notice
  counts only if it is the newest registration from that node, signed after the one on record, and names
  the current boot. A notice from an earlier boot, delayed or replayed, is ignored.
- **The core acts at once.** The leader counts the site down for new work immediately, without the usual
  quarantine, fails over the writes open on that node and reads from the other copies. When the node's new
  boot registers and its description verifies, it is up again. Without a new boot, after 120 s the node is
  judged by its silence again.
- **Writes are placed again.** A write whose store stops answering, restarts under it, says it no longer
  holds the write, or refuses as stopping is undone and written again under the collection's rules. When no
  other store may take it, the write waits only for a store that failed under that very write or announced
  its stop: at most 30 s and 4 failed stores per episode, and 120 s per upload, then it fails, retryable. A
  store that is simply down fails such a write at once.
- **Repair catches up.** On the test deployment (three sites, at least two copies to commit) a write during a
  store's restart commits on two sites, repair restores the third copy once the store is back, and later
  writes go to all three.

Nothing about this is journaled, so old and new builds can run together during the roll; an older core
ignores the notice and judges the node by its silence, as before.

## A slow disk never costs the leadership

The test deployment's shared storage has stalled for 9.7 s and 14.6 s at a time. Before this work, a stall
like that could cost an election, and a disk that hung made the leader hold every proposal in memory until
it ran out of heap.

- **No disk work on the hot path under the raft lock.** Heartbeats, votes and the followers' answers share
  one lock with proposals. A new entry is staged in memory; the log's own sync thread writes, encrypts and
  fsyncs it. The leader counts its own copy toward a commit only once that sync returns, and a follower
  acknowledges only what it has synced.
- **A slow disk only makes writes wait.** The leader keeps leading and serving lease reads, the followers
  keep hearing it, and commits resume as soon as the storage answers.
- **The unsynced backlog is capped** at 64 MiB by default (`core_raft_max_unsynced_bytes`). A proposal that
  would pass the cap waits for the sync, first come first staged, and the leader answers new writes status 11
  with `retry_after_ms` meanwhile. Memory stays bounded however long the disk takes.
- **A stuck disk hands over, but only to healthy peers.** The leader calls its disk *stuck* only when one
  write or fsync has not returned for 30 s (`core_raft_stuck_sync_ms`); a disk that is merely slow is never
  treated as stuck. A stuck leader hands its leadership over only when the followers **shown healthy**
  (answering, and making entries durable on their own disks) form a quorum by themselves. Otherwise, for
  example when every peer shares the stalled storage, it rides the stall out. No peer holds back a
  campaign because its own disk lags: with no leader, liveness wins.
- **A stall report names the cause.** A peer whose raft tick runs late, whose lease lapses while it leads, or
  whose oldest staged record waits too long for its write logs one `STALL` warning a minute, with the
  thread holding the lock and the memory and I/O pressure of the host.

**What the core log guarantees across a crash.** An entry is durable once the log's durable index passes it,
and only then is it acknowledged or counted. After a process kill or a power cut, the log holds every
durable entry, then at most a prefix of what was being written: nothing reordered, altered or invented. The
power-cut campaigns hold the log to this (see [Test results](../built/tests.md)).

**Measured** (local fabric, 2026-10-28, E18 LT-C2 and LT-C4): follower stalls of 2.8–17.7 s caused no
election; a leader stall of 13.2 s caused one, as a stall above the election timeout should; a memory hog of
768 MiB beside a leader or a follower for 31–86 s caused none. On the HPC test bed: in progress.

## The live tier during restarts

The live tier needs only a quorum of the core (owner decision 2026-10-28). A core peer that is down counts
by its last answer about what it supports, so new copies, lease extensions and pins continue through a core
restart or a site roll. Drops are never held up by a silent peer. A live node that is still starting
answers retryable rather than refused. See [The live tier](live-tier.md#availability-while-the-core-changes).

## Settings

| Setting | Default | What it bounds |
|---|---|---|
| `core_stop_drain_ms` | 3 s | admitted requests finishing on a stopping peer |
| `core_stop_max_ms` | 10 s | the core's whole stop: drain, hand-over and waits |
| `gfs_stop_max_ms` | 25 s | the plugin's whole stop |
| `gfs_stop_linger_ms` | 3 s | answering the stopping refusal after the core stopped |
| `gfs_start_wait_ms` | 60 s | a new instance waiting for an old one's directories |
| `core_raft_transfer` | on | leadership hand-over on step-down and stop |
| `core_raft_max_unsynced_bytes` | 64 MiB | the raft log's unsynced backlog |
| `core_raft_stuck_sync_ms` | 30 s | when a leader calls its disk stuck |
| `core_write_retry_ms` / `core_write_retry_total_ms` / `core_write_retries` | 30 s / 120 s / 4 | placing a write again after a store failed under it: per episode, per upload, failed stores per episode |
| `core_site_departure_max_ms` | 120 s | how long a departure notice keeps a store out of service |
