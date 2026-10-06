# Test results

Results for release 1.3 (`GaiaKeep/gfs` `1.3`, `8461e1a`, 2026-10-01). Every number here comes from
an executed run whose output is recorded in the repository (`eval/results/`) or in the CI run logs.

## Continuous integration

The GitHub workflow runs on every push. It ran on `ubuntu-24.04` with 4 vCPUs, with the result for
`8461e1a` listed against each step:

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
