# Test results

Results for release 1.3 (`GaiaKeep/gfs` `1.3`, `8461e1a`, 2026-10-01). Every number here comes from
an executed run whose output is recorded in the repository (`eval/results/`) or in the CI run logs. The
[last section](#the-live-tier-and-stability-e18-2026-10-28) covers the live tier and the stability work on
the development branch, measured on 2026-10-28.

## Continuous integration

For release 1.3 the GitHub workflow ran on every push, on `ubuntu-24.04` with 4 vCPUs, with the result for
`8461e1a` listed against each step. Since 2026-10-02 CI runs on the HPC cluster instead, as batch jobs, and
GitHub Actions is not used ([Running the tests](harnesses.md#continuous-integration)).

| Step | Result |
|---|---|
| Core unit and integration suite (JUnit 5) | **2,188 tests, 0 failures, 0 errors, 0 skipped**, in 29 min |
| Java client suite, including the Python client run against the Java core | **50 tests, 0 failures** |
| Python client suite, including Java interop | green (90 passed; 5 skipped are hardware or live-fabric only) |
| Java↔Python transfer-protocol conformance (golden vectors) | required, never skipped: green |
| Wire-contract lint (rules R1–R8: registration, core verbs, node verbs, signing) | **0 violations** |
| Eval tooling tests | 34 tests green |
| Transport defaults check | green |
| Release jar build and publish | published |

**Flaky-test policy.** A test that fails is re-run up to twice. A test that passes only on a re-run
is listed by name in the run summary as flaky, so it is never hidden; one that fails all three times
fails the build. The run for `8461e1a` had **no flaky tests**.

## The core suite by area

These counts are from the CI run above:

| Area | Test classes | Tests | What it covers |
|---|---:|---:|---|
| Storage engine | 30 | 508 | publish, dedup, versions, repair, scrub, trim, recovery, reclaim, withdrawal |
| Core service (RPC surface) | 75 | 437 | every verb: auth, jobs, ingest, transfers, follower reads, chain replication, failover |
| Crash matrix | 2 | 156 | a crash injected at every registered maintenance and write step, in 4 loss modes |
| Index (prototype journal) | 6 | 122 | journal, replication and its history chain |
| Replicated core log (Raft) | 9 | 112 | elections, lease, pre-vote, snapshots, compaction, non-voter catch-up, simulation |
| Key custody | 7 | 86 | key sources, PKCS#11, rotation, key splitting |
| Lifecycle | 10 | 70 | forget, prune, destroy, retention, legal hold, quorum |
| Storage-node protocol | 7 | 59 | signed node requests, term fencing, pinning |
| Transfer protocol (GKT) | 6 | 57 | windows, acknowledgements, loss, reordering, duplication |
| Authentication and audit | 7 | 57 | signed requests, roles, replay, audit chain |
| Power loss | 10 | 52 | power cuts on page-cache models of every log and store |
| Blocks, placement, refs, versions, tenancy | 20 | 150 | block codec, placement rules, counted references, policy engine |
| Format adapters and chunkers | 8 | 54 | DICOM, NIfTI, TIFF cut rules, content-defined chunking, conformance |
| Tape | 7 | 67 | binding, catalogue, deferred reads, simulator, SCSI path, benchmark |
| Pack and block stores | 8 | 66 | containers, repack, power loss, independent reference reader |
| Metadata encryption | 4 | 19 | sealed partitions, keyed ids, sealed snapshots, wire |
| Model-based engine tests | 3 | 16 | random operation sequences against a reference model |
| Other (jobs, API, tools, crypto, util) | 19 | 100 | |

## Beyond the unit suite

| Campaign | Result |
|---|---|
| **Power-cut campaigns** (page-cache model) | Core log and index journal: 600 histories each, all three cut modes, about 750 cuts inside recovery per log. Pack store: 1,500 rounds with 7,043 cuts in work and 1,851 in recovery. Earlier engine campaign: 720 histories and 3,720 cuts. **No acknowledged write lost** in the final runs; every defect found on the way was fixed first. |
| **Real power cuts** | 200/200 LazyFS rounds and 30/30 VM power-offs, all clean. |
| **Crash matrix** | 153 crash points by 4 loss modes, plus a live version that arms a crash point on a running fabric. |
| **Model-based testing** | Every CI run plays 220 seeds of 60 operations against a reference model; the long run plays 5,000 × 150. Six engine defects were found this way and fixed. |
| **Chain chaos test** | 1,118 publishes under 1,107 injected kills, partitions and delays: every acknowledged version intact. |
| **Two-sided network partition** | The minority leader acknowledges nothing, and after healing no acknowledged write is lost. |
| **Live fabric check, single host** | 61/61 (prototype fabric), then the secured build on the merged code. |
| **Live fabric check, HPC** (secured: signed requests, strict node-key pinning, sealed keys) | **88/88** on the shipped build. It covers crash mid-publish, recovery, reconcile, failover and replica agreement. |
| **Simulated tape, end to end** | Archive, lose the disk copies, recall and read back byte-identical. Also covered: recall ordering, concurrent recalls on two drives, a drive dying mid-write, failover with a recall outstanding, and scrubbing from tape. Run on the simulator and on virtual tape drives (mhVTL). |
| **WAN emulation** (netem, 5 sites) | 30 ms round trip passes at every loss level, with BBR congestion control. 80 ms is partly passing; see [Benchmarks](benchmarks.md). |
| **Adversarial reviews** | Two rounds over the merged code, by area: authorization, durability, replication, transport and data path. Every finding was reproduced with a test before being fixed. |

## Framework (Cresco) validation

| Check | Result |
|---|---|
| No silent message loss | 40/40 two-node runs delivered 800/800 messages, with every drop counter 0. The previous jar lost messages in 2 of 35 runs. |
| Tunnel integrity under load (SHA-256 checked) | 10/10 runs intact, including a late-starting target. The previous jar truncated silently. |
| Speed suite under heavy load | 10/10 runs |
| Secrets in logs and exported config | none found in any log, store or reply |

## The live tier and stability (E18, 2026-10-28)

> "Make sure this is highly tested and there are good test and evaluation and chaos testing and cases. This
> system must be stable." (owner, 2026-10-28)

E18 of the evaluation plan is the gate before the much larger FABRIC test: the live tier's unit tests, the
model-based test, the crash cells, the chaos cases and the end-to-end checks must pass **on the same build**,
and a 72-hour soak must meet its criteria. The results below are from the development branch, measured on
2026-10-28. **The final-build runs and the 72-hour soak are in progress**; their results will be added when
they exist.

**Invariants**, checked after every step of the model-based test, every chaos cycle, and hourly in the soak:

| | Invariant |
|---|---|
| **I1** | Inventory = disk: every file under a live root belongs to a row the core lists there, and every `LIVE` row's files are all there. No plaintext without a row. |
| **I2** | No early copy: no row of a version leaves `REALISING`, and no byte lands on a node, before the version commits, for anyone. |
| **I3** | Every end is attested: every drop ends in a node-signed attestation within its bound, or the row stays listed as unconfirmed with its cause. Never silently gone. |
| **I4** | Legal deletion reaches copies: after a FORGET or a legal order of a path, no live copy and no audit record names it in clear. |
| **I5** | Budgets: no node holds more than its budget, no tenant more than its admission. |
| **I6** | Core health: one serving leader, quorum, every acknowledged write reads back byte for byte, and the state hash agrees across peers. |

| Id | Check | Where, when | Result |
|---|---|---|---|
| LT-U1 | Live-tier unit and cluster tests (about 250) | every CI run | green; CI on the merged tree of the first four milestones: 3,052 tests |
| LT-M1 | Model-based random test: seeded sequences of publishes, realises, holds, drops, workspace edits and publishes, withdrawals, FORGETs, legal orders, grants, node partitions and restarts, leader kills and hand-overs, and crash points, on a 3-peer core with two live nodes; I1–I6 after every step | every CI run: 24 seeds × 100 steps (4–5 min); a nightly 300 × 200 and a weekly 10,000-seed size as cluster batch jobs, submitted by hand so far | in every CI run; a failing seed is shrunk and replays exactly. It found a product bug: after a leader change, realises in flight failed for any collection whose grant had ever ended (fixed, with a regression test) |
| LT-X1 | The six live-tier crash cells (node: mid-write, after fsync, mid-drop; core: after registering, mid-push, after the attestation) | HPC validation deployment, build `88f086d6` | **6/6 pass**: each halted at its point and recovered with no operator action, 8 of 8 checks each, in 34–69 s. To repeat on the final build |
| LT-E1 | End-to-end checks of the live node on the test deployment | HPC test deployment, build `88f086d6` | **14 PASS, 0 FAIL, 1 SKIP** in 30 minutes (below) |
| LT-C1 | Chaos with live load: hub restart, agent restart, site roll, live node kill | local fabric, 1.5 h | live node kills recovered in 39–45 s, a hub restart in 38 s; I1–I6 held in all 19 checks. The site roll and store restart failed on that workstation's fsync-barrier probe (a nearly full disk), not on the live tier. HPC: in progress |
| LT-C2 | Stalls (SIGSTOP of the leader, a follower, the live node, 2–20 s) | local fabric | follower stalls of 2.8–17.7 s: no election; a 13.2 s leader stall: one election; live node stalls of 3.8–15.6 s: no effect beyond their window |
| LT-C3 | Planned stop of the leader with jobs running | local fabric, 0.5 h, 2026-10-28 | **PASS**: 10 stops, no halted log, next leader serving 0.726–0.740 s after the signal, processes out in 3.34–3.86 s, **0 failed client calls**, 1,260 acknowledged writes all read back. HPC: in progress |
| LT-C4 | Memory pressure beside a core | local fabric | a 768 MiB hog for 31–86 s beside a leader or a follower: no election in 3 cycles |
| LT-C5 | A live node out of budget or out of disk mid-realise | local fabric | **PASS**: an admission lowered below a 24 MiB realise failed it cleanly (`quota`, with its arithmetic) in 3 s; a filled live root failed it retryable in 3 s; I1 and I5 held. A root removed underneath and clock skew are not injected yet |
| LT-S1 | 72-hour soak: chaos every 2–4 h, live churn throughout; canary ≥ 99.9 %, no spontaneous election, no invariant violation, flat memory and open files | HPC test deployment | **in progress**. A 58-minute local mini-soak had no spontaneous election, no violation in 14 invariant checks and flat memory and open files, but the canary succeeded in 34 of 35 rounds (one read waited past 180 s for its tape commit): fail on that criterion |
| LT-B1 | Realise benchmark | HPC test deployment, build `88f086d6` | see [Benchmarks](benchmarks.md#live-tier-realise-hpc-2026-10-28) |

### The end-to-end checks on the test deployment (LT-E1)

Build `88f086d6`, 2026-10-28, every signed request and reply sealed:

| Check | Result |
|---|---|
| g: host checks, link-protection registration and its evidence | PASS (3 checks) |
| a: realise a fresh committed version | PASS: 17 files, 21.6 MB at the node, equal to `core.get`'s bytes (SHA-384 on both sides), in 1.0 s after a 110 s commit |
| b: no early copy, by the version's own writer | PASS: no row and nothing at the node while it was committing (14 looks), then the committed bytes |
| c: `livelist` and `prospect` agree with the node | PASS |
| d: `livehold` extend raises the lease | PASS |
| e: `livedrop`: dropping, then gone after the node's attestation, no file left | PASS |
| f1: withdrawal of a collection with a live copy | PASS: dropped on the node's attestation, none unconfirmed, no file left |
| f2: FORGET evidence in the lifecycle status | SKIP: it needs a second tenant administrator bound at least 7 days |
| h: filerepo: a live-backed repository reports `LIVE`, refuses serving, refuses a file under the live root; filerepo keeps a copy live as the node | PASS (4 checks) |
| i: a site taken down during a 2 GB realise | PASS: the realise ended DONE, the canary stayed green, the core healthy again |

### What the chaos stage injects and judges

The chaos stage runs a deployment under continuous write, read and tape-archive load, plus live-tier churn
(publishes, realises, early realises of versions still committing, extends, pins, drops, workspace publishes,
withdrawals, FORGETs), and injects faults at seeded random times: hub restarts, core leader and follower
restarts, store and tape restarts, site rolls, live node kills, process stalls, planned stops of the leader,
memory pressure and a full live node. After every cycle it checks recovery, unavailable and
under-replicated blocks, failure counters that keep growing, I1–I6 from outside the system, and an election
ledger in which any spontaneous election in a quiet window is a violation. It takes a deployment's endpoints
and operator commands, never a host path, so it runs unchanged on a workstation fabric, the HPC test
deployment and a FABRIC slice.

**What it found on 2026-10-28** (each fixed, with regression tests): a planned stop of a core peer failed
5–36 client calls and ended in a forced kill after 60 s; a stop could interrupt a log write and halt the
leader instead of handing over; while any core peer was down, the live tier refused to extend or pin copies;
and a live node's first seconds after a restart refused realises instead of answering retryable.
