!!! success "Status: Current"
    The Raft core log: record format, group commit, snapshots and failover (shipped in 1.3, 2026-10-01).

# The storage core's metadata log

*2026-09-26. Package `io.cresco.gfs.core.log`. Covers OUT-08, OUT-13 (core), OUT-04 (core), OUT-14,
OUT-35, OUT-40 and OUT-53.*

The storage core no longer journals through the prototype federation index. Every batch of engine
deltas is an entry in the core's own log, replicated to the core peers with Raft, and acknowledged
to the client only once a majority of peers has it on disk.

## On disk (`core_log_dir`)

| File | Contents | Written by |
|---|---|---|
| `core-log.header` | magic, format, cluster id, key-check value, MAC | once, atomically |
| `raft-state` | current term, vote, this directory's raft state id, whether the peer votes (N18), MAC | temp, fsync, rename, directory fsync |
| `seg-<first index>.log` | segment header (first index, term and MAC before it, header MAC), then records | append, one `force` per group commit |
| `snap-<last index>.snap` | engine snapshot at that index, its term and chain MAC, payload SHA-384, MAC | temp, fsync, rename, directory fsync |
| `imported-index.marker` | the one-time legacy import, MAC'd | once |

A record is `magic | fmt | len | term | index | batch | hmac16 | payload | mac`, with
`mac_i = HMAC-SHA-384(k_log, fmt|term|index|mac_(i-1)|payload)`. The 16-byte header MAC covers the
header fields and `mac_(i-1)`, so a length is authenticated before it is used. `batch` is the first
index of the record's group commit (one write and one `force`); everything before it was forced
before the record was written. It is local to the peer and outside the chain, so peers' chain values
stay equal.
`k_log = HKDF-SHA-384(master, "gfs/core/log-mac/v1")`. Equal chain values at an index mean equal
logs up to that index, on any peer.

## Recovery fails closed

- The directory's fsync barrier is probed with the storage nodes' own probe (`FsBinding.commission`,
  five unanimous rounds). If it is not proven, the core refuses to start unless
  `core_log_durability_attested=true`.
- A wrong master key is refused by the key-check value before anything is read.
- Every record's framing, MAC, chain and index continuity is verified. An incomplete or
  unverifiable record in the last segment is a torn tail unless a verifiable record of a **later**
  group commit follows it. A group commit that was never forced may reach the disk in any order
  (later pages written, an earlier one zero-filled), so records of the bad record's own group commit
  after it prove nothing; a later group commit was written only after this one was forced, so it
  proves corruption. A torn tail is truncated from the bad record, synced, logged and counted
  (`core.status` → `log.torn_*`). A record counts as verifiable if its header MAC checks against the
  bytes before it, against the chain value expected there, or against the value a damaged
  predecessor's own bytes compute to.
  A segment header is forced before any record is written, so a bad header with bytes after it is
  corruption, never a torn creation.
- Anything else refuses to start with the file, offset and index: mid-log corruption, a bad MAC
  followed by valid records, a gap, a chain break, a snapshot that fails its MAC or disagrees with
  the log, an unknown format number.
- Installing a leader's snapshot that replaces the log deletes the replaced segments newest first,
  syncing the directory after each, so a crash leaves a prefix of the old log that recovery
  recognises (it disagrees with the snapshot) and finishes discarding. A gap after a snapshot is
  therefore always lost data, and refuses.
- An entry the engine cannot apply (an unknown delta from a newer release) halts the core, naming
  segment, offset and index. A halted core serves nothing.

## Master-key rotation (OUT-25)

`k_log` and `k_raft` are HKDF-SHA-384 from one master key, so each pair is bound to that key's id
(`kid`). A peer holds the log keys of every master kid it holds (`core_master_key_file` plus
`core_master_key_previous_files`).

- **The header names the kid.** `core-log.header` carries the kid the log is keyed under, that kid's
  key-check value, and `rekeyedAt`, the last index written under an earlier kid. A header naming a
  kid the peer does not hold refuses to start and names it.
- **Every file is MAC'd under one kid** and verified under the held kid that authenticates it. A
  segment's records are under its header's kid. Recovery refuses an earlier kid where only the
  header's may be: a segment starting after `rekeyedAt`, any segment after one under the header's
  kid, a snapshot past `rekeyedAt`. A file under a retired kid that is put back, or forged by someone
  holding the retired key, is refused rather than replayed.
- **Re-key in place.** When a peer starts with a current kid its log is not keyed under,
  `CoreLog.rekey` rewrites the header (new kid, `rekeyedAt` = the last index), rolls a new segment that
  continues the MAC chain under the new kid, and rewrites the raft state and marker. Each step is
  crash-safe; an interrupted re-key finishes on the next start. History is not rewritten: the chain
  value at `rekeyedAt` is the same, and later records chain from it under the new kid.
- **The next snapshot retires the old kid.** While `kids_in_use` (core.status `log`) lists a kid
  other than the header's, the snapshot pass takes a snapshot every 10 s; once one lies past
  `rekeyedAt`, compaction deletes the old kid's segments and snapshot. `core.rotatemaster` reports
  `log_kids_in_use` and a `retirable_kids` that accounts for the log as well as the roots.
- **Raft messages** are MAC'd under the sender's current kid and verified under any held kid, so the
  rotation rolls through the peers one restart at a time, provided every peer holds the new kid
  (as a previous key) before any peer makes it current. A peer that does not hold it cannot follow;
  its raft status shows "MAC fails under every held master kid".
- **Different peers may be keyed under different kids** during the rotation. Chain values then differ
  between peers for the same entries, so a snapshot install to such a follower replaces its log
  instead of keeping the matching suffix: slower, never wrong.

Tested: CoreLogTest (re-key in place, reopen, old kid retired after the snapshot, a forged old-kid
snapshot refused, an interrupted re-key finished) and CoreServiceClusterTest (three peers restart
after a rotation, rotatemaster, snapshots, restart with the old key retired; a peer without the new
kid is refused with the reason).

## Replication (Raft)

- Peers: `core_peers`, the `region:agent:plugin` of every core peer including this one. Absent, the
  index primary is a cluster of one (quorum 1), which is how existing single-index deployments keep
  working. An index replica (`index_primary=false`) without `core_peers` refuses to run a core: as a
  cluster of one it would elect itself and serve an empty core, and later join the primary's cluster
  with a different history. Storage nodes accept `x.*` from every address in `core_peers` and
  `core_index_addrs`.
- Every message carries a digest of the sender's `core_peers` (order-free). Peers configured with
  different peer lists refuse each other's messages rather than count different quorums; changing
  `core_peers` means restarting every peer with the new list (there is no joint consensus).
- **Divergent histories halt.** Every append carries the leader's chain values at `prevIndex` and at
  its last entry. A follower whose term matches at an index but whose chain value differs holds a
  history written by another cluster (a peer that once ran alone, a log copied from elsewhere): it
  halts, naming segment, offset and index, instead of accepting entries on top of it.
- Pre-vote, randomized election timeout in `[core_election_timeout_ms, 2x)`, heartbeat
  `core_heartbeat_ms`. A peer that has heard from a leader within the timeout ignores vote requests.
- The leader writes a proposal to its log and sends it at once, and syncs its log on a thread of its own: the
  raft monitor is never held while the medium syncs, so heartbeats, acknowledgements and status go on during a
  slow fsync (an ingest's writes on the same disk made one take ~3 s on the HPC cluster, 2026-10-01, and the leader, its
  monitor held, sent no heartbeat, counted no acknowledgement and stepped down). Its own copy counts toward a
  commit only once synced (`durable_index` in status). A follower still syncs before it answers; a follower's
  stall shorter than `core_election_timeout_ms` is ridden out.
  A leader that cannot reach a majority within the timeout steps down.
- Commit counts only entries of the current term, from a majority's fsync. A new leader serves only
  after its term's no-op is committed and applied.
- **Non-voters (N18).** A peer whose log is empty, or whose directory has no `raft-state` of its own
  (a wiped or replaced disk), starts as a non-voter (`raft.voter: False`, persisted). It grants no
  vote, and it says so in every answer, so the leader does not count its copy toward commit: it may
  have acknowledged entries its lost disk held, and an empty log would grant any candidate. It
  becomes a voter (persisted, `raft.promotions`) once an append leaves its log equal to the leader's
  through the leader's last index, or through a commit point of the leader's own term, and only if
  that append names the peer's own process incarnation (R1, raft message format 3: a peer refuses
  another format's messages, so every core peer is upgraded together). The leader names
  the incarnation it last heard from, and only while it holds its lease: an append sent to the
  process before a restart or a wipe (a delayed or duplicated copy that the new process's empty
  replay window cannot recognise) promotes nothing, and neither does a deposed leader. Until it can
  vouch for a non-voter, the leader sends it heartbeats but no entries: an empty peer stays empty (it
  may still consent) rather than hold entries it was not promoted by, which in a cluster just formed by
  consent would leave no peer able to elect a leader once the first one falls. An empty
  non-voter only consents: a consent counts toward an election that every peer joins (or the bootstrap
  majority above), never toward a majority. `core_raft_voter_override=<its raft.state_id>` makes a
  non-voter vote when an operator has established that nothing committed depends on what it lost.
- A follower whose log is behind the leader's snapshot (empty, new, wiped) is sent the snapshot.
  A follower that restarted (a new process incarnation) or rejects entries it had acknowledged
  (a truncated tail, a wiped directory) stops counting toward the quorum until it confirms them again.
- **Lease.** The leader serves (reads and writes) only while a majority answered a request it sent
  less than ¾ of an election timeout ago. A follower refuses votes for a full election timeout after
  hearing from a leader, and for one timeout after it starts, so a leader cut off by a partition or a
  long pause stops serving before another can be elected. Timers, heartbeats and the lease run on
  each host's monotonic clock (`System.nanoTime`), so a stepped wall clock cannot stretch a lease;
  clock rates are assumed within 25 %. Only message freshness reads the wall clock. Only answers
  from peers that kept their term count toward the lease (R1): voters, and a non-voter process that
  granted or consented to this leadership. A wiped peer restarts at term 0 and follows any leader
  that reaches it, even one a newer term deposed, so its answers cannot show that no newer leader
  exists: a leader paused through an election and answered only by a wiped peer holds no lease.
- **Destructive maintenance asks the lease.** The live leader's engine checks, before each copy it
  destroys (gc, withdrawal, trim, scrub, intent cleanup), that it still holds its lease; otherwise
  the operation stops. A withdrawal is committed before the copies it frees are destroyed. The
  residual window (one reclaim already in flight when the lease lapses) is closed by the storage
  nodes: every `x.*` carries the term its signer was elected leader in (`RaftNode.leaderTerm`, not
  the newer term a deposed leader may have heard of), and a node refuses a term below the highest it
  has seen, kept in its `x-term` file across restarts (N17).
- **Read barrier.** A read verb (`core.head`, `core.get`, `core.list`, `core.benchread`) first waits
  until every change applied before it is committed, and fails if one is not: a read never shows
  a change that may yet be lost.
- The leader's engine applies deltas to memory before journaling (unchanged); the journal append
  blocks until the batch commits, `core_commit_timeout_ms`, or lost leadership. A failure fences
  the engine, the peer steps down, and the engine is rebuilt from snapshot plus committed log.
  The rebuild (a full replay) runs off the raft lock, so the peer keeps voting and acknowledging;
  entries committed meanwhile are replayed into the new engine before it is swapped in, the peer
  serves nothing until then, and sites that joined meanwhile are added to it.
- Messages (`core.raft.msg`) carry HMAC-SHA-384 under `k_raft = HKDF(master, "gfs/core/raft-auth/v1")`,
  the cluster id, sender and recipient, a wall-clock send time checked against a freshness window
  (`core_raft_freshness_ms`, 120 s), and a per-sender sequence number: forged, altered, misaddressed
  and replayed messages are refused. Hosts whose clocks differ by more than the window cannot talk;
  `core.status` → `raft.stale_refusals` and `raft.last_clock_skew_ms` show it.
- Entry payloads over 64 KiB and every snapshot chunk travel on the dataplane as FrameBus bodies,
  with their SHA-384 inside the MAC'd header. An append carries at most `core_raft_batch_bytes` of
  entries (at least one, at most 8192; a larger single entry is split across frames); snapshots
  move in chunks of that size. Values above the codec's 64 MiB chunk limit are clamped, with a warning.
- **One bulk message per follower.** The leader keeps at most one append-with-entries or snapshot
  chunk per follower in the transport and resends nothing to it until the transport reports that
  message sent or dropped; the resend timer starts then. A message the transport has held for
  20 election timeouts is presumed lost (`raft.bulk_stuck`). The transport's bulk lane is also
  bounded by bytes (`max(16 MiB, 2 x core_raft_batch_bytes + 1 MiB)` per peer;
  `raft.transport_bulk_dropped`), and header-only messages (votes, heartbeats, answers) use their
  own lane, so a slow body transfer never delays a heartbeat. While a transfer is slow the leader
  sends plain heartbeats, which keep the follower following and the lease alive.
- Only the leader serves `core.*`. Every peer answers `core.status` and `core.metahash` with role,
  term, leader and commit index. A follower answers anything else with status `12` and `core_leader`.
  `eval/gkt.py:call_leader` follows that redirect, one retry per redirect, bounded.

## Compaction

At a consistent cut the engine's snapshot deltas are written as a snapshot and the segments it
covers are deleted. The cut holds the engine's lock and the policy and key-ring locks (their changes
are made outside the engine's lock and journaled by hooks), and a cut is discarded if anything
reached the log meanwhile (`log.cuts_discarded`). A follower does not snapshot its engine under the
raft lock: it replays its snapshot and committed log into a scratch engine off the lock and
snapshots that, so it keeps answering appends and votes while it compacts. Automatic after
`core_log_snapshot_bytes` of entries (jittered up to +25 % per peer, so peers do not compact
together), on demand with `core.snapshot` (any peer compacts its own log; the request is signed for
that peer, `audience` = its `peer_audience`, so it cannot be replayed on another). `core.snapshot` goes
through per-verb authorization (only `core.status` and `core.metahash` do not) and is rate-limited
to one taken snapshot per `core_snapshot_min_interval_ms` (status `14`, TOO_SOON, otherwise), because a
leader's cut stalls writers. Replay loads the newest snapshot, then the entries
after it. Measured in `ReplicatedCoreTest.replayTimeOfALargeLog` (one Mac, JDK 21): 2,000 entries
holding 200,000 block deltas, 36.5 MB of log, replay in 0.4-0.5 s; from a 36.3 MB snapshot,
0.35-0.55 s.

## Migration from the index journal

When the core log is empty and this peer was the prototype index primary (`index_primary=true`),
the `core.batch` lines in `gfs-index.jsonl` are replayed once into an engine and written as the
log's base snapshot (index 1, term 1), and `imported-index.marker` records it. The import never
repeats. The index keeps the old lines and applies nothing for them.

The import refuses (and the core does not start) when the journal holds a `snapshot` line: the index
writes one when a replica installs the primary's state, and the core state before it then lived only
in that dump, so the journal holds a partial core. Import from the peer whose journal holds every
`core.batch` line, or set `core_legacy_import=skip` to start without importing. It also refuses when
the importing peer is not the first in `core_peers`.

**Bootstrap rule.** A peer whose log is empty never campaigns unless it is the first peer listed in
`core_peers`, so an empty or wiped peer cannot win against peers that hold state. List the old
index primary first when turning a single index into a replicated core. A brand-new cluster (every
peer a non-voter, below) forms once every peer is up: empty peers consent to an election every peer
joins. With `core_raft_bootstrap=true` on the first listed peer's first start it forms with a
majority; remove the setting once the core has formed.

## Config keys

| Key | Default | |
|---|---|---|
| `core_log_dir` | `<plugin data>/core-log` | put on node-local storage (OUT-40) |
| `core_log_durability_attested` | `false` | skip the barrier probe; an operator attestation |
| `core_log_snapshot_bytes` | 268435456 (256 MiB) | entries between automatic snapshots |
| `core_peers` | this peer only (index primary); refused on an index replica | comma list of every core peer, this one included, identical on every peer |
| `core_cluster_id` | `gfs-core` | stored in the header and in every message |
| `core_commit_timeout_ms` | 15000 | a batch not committed by then fences the leader |
| `core_election_timeout_ms` | 6000 | randomized to up to twice this; the leader's check-quorum window; lease = 3/4 of it |
| `core_heartbeat_ms` | 250 | |
| `core_raft_batch_bytes` | 4194304 (4 MiB) | bound on one append and one snapshot chunk |
| `core_site_probe_ms` | 3000 | the leader's own liveness probe of each storage node |
| `core_site_probe_timeout_ms` | 5000 | a site that does not answer by then is quarantined |
| `core_legacy_import` | `auto` | `skip` starts without the one-time import (`auto` or `skip`) |
| `core_raft_freshness_ms` | 120000 | largest tolerated clock skew between core hosts; older messages are refused |
| `core_raft_bootstrap` | `false` | the first listed peer's first start forms a new core with a majority of empty peers (N18) |
| `core_raft_voter_override` | none | this peer's own `raft.state_id`: vote although it lost its raft state (N18, OPERATIONS §5.3) |
| `core_snapshot_min_interval_ms` | 60000 | least time between two on-demand snapshots taken |

## Evidence

JUnit: `CoreLogTest` (torn tails, refusals, compaction, install), `RaftCodecTest` (forged,
altered, replayed, stale, misaddressed, oversized, unknown format), `RaftSimTest` (deterministic
simulation: elections, majority commit, failover, partitioned old leader, catch-up by entries and by
chunked snapshot, and randomized faults over 300 and 200 rounds checking election safety, log
matching, leader completeness, state machine safety and that every acknowledged entry reaches every
peer, with power losses in the middle of writes that tear the unforced bytes of a group commit in any
order; separate-cluster histories halting; a stepped wall clock; a skewed peer; a slow link),
`CrescoRaftTransportTest` (lanes, byte bound, done reporting), `ReplicatedCoreTest` (real engines: failover byte-identical, rejoin, compaction across
restarts, fencing, legacy import on one and three peers, apply refusal, policy and key-ring changes
racing compaction, rebuild off the raft lock, lease and read barrier), `CoreServiceTest` (serving,
redirects, refusals), `CoreServiceClusterTest` (three `CoreService` peers over the production
transport's encoding on an in-process fabric: election, redirect, a 1.5 MB entry in frames, failover
within the randomized election timeout, rejoin, a wiped peer caught up by snapshot frames, forged,
replayed and malformed `core.raft.msg`). The live harness `eval/core_failover_check.py` (three
peers, five storage nodes) is written and not yet run on the fabric.
