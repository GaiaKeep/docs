# Running the tests

Everything below lives in `GaiaKeep/gfs` (a private repository). It needs JDK 21 and
Maven; the fabric campaigns also need the Cresco `run/` layout and `pycrescolib`.

## Build

```bash
mvn -o clean package bundle:bundle -DskipTests   # → target/gfs-1.3-SNAPSHOT.jar (OSGi bundle)
mvn -q dependency:build-classpath -Dmdep.outputFile=cp.txt
```

## Unit-level harnesses (no fabric)

Each is a standalone program in `eval/sim/` that prints each check and exits non-zero on failure.

```bash
CP="target/classes:$(cat cp.txt)"
javac -cp "$CP" -d /tmp/sim eval/sim/BarrierTest.java
java  -cp "$CP:/tmp/sim" BarrierTest
```

| Harness | What it proves | Last result |
|---|---|---|
| `BindingTest` | The extent binding: two-stage writes, retention floors that survive restart, refusing `reclaim` | 23/23 |
| `BarrierTest` | Barrier classification against the three measured hosts; a live probe; fail-closed rules | 13/13 |
| `IvDiscipline` | Per-object key counter discipline at 184,044 encryptions; refusing conflicting retries; no random generator in the trust path | 14/14 |
| `OracleLint` | The confirmation-oracle rule, with positive and negative controls | 0 unexpected |
| `IndexResidency` | panAtlas index sizing against the tape geometry | reproducible figures |
| `PlantHarness`, `PlantContention`, `MediaLife` | Tape plant throughput, contention and media wear | results in `eval/results/` |

## Source lints

```bash
python3 eval/wire_contract.py
```

This checks that every field a storage node sends at registration is committed and applied by the
index. It fails on the tree before `2842891`, naming the three dropped fields. **Run it after
touching registration.**

## Fabric campaigns (the prototype)

Copy or symlink `eval/` to `run/gfs/` in a Cresco workspace. Results land in `run/gfs/results/`.

| Script | Runs |
|---|---|
| `launch_gfs_fabric.sh up` then `gfs_eval.py` | Functional suite E1–E11 (99 checks, ~80 s) |
| `core_fabric_check.py` | Storage core on a live fabric: 61 checks, including every dedup mode, the replica hash, a killed node, the index killed -9 and a halt between seal and commit. Run with `IXMX=2048M GXMX=4096M` |
| `core_throughput.py` | Throughput leg by leg (`TP_PHASES=A,B,C`): node transport, client upload, publish and read at R=1 and R=3, and pipelined ingest |
| `core_frame_sweep.py` | Frame size, broker persistence and batch size for the node leg |
| `gkt.py` | Python GKT client (the dataplane transfer protocol): `CoreClient`, `MultiClient`, `ingest` |
| `launch_gfs_scale.sh up 240`, `run_scale_all.sh` | 240-site scale tiers |
| `launch_gfs_regions.sh up 8`, `run_scale_regions.sh` | Multi-region bridged fabric |
| `run_failure_final.sh` | Failure tier F1–F8 and global restart ×3 |
| `run_final_proof.sh` | The full final campaign |
| `gfs_claims.py` | Rebuilds the claims registry from the results (59/59) |
| `run_dashboard_proof.sh` | Dashboard Storage tab proof (D1) |

!!! warning "Campaign gotchas"
    Never stage a new agent jar while a campaign runs; restarts pick it up mid-run. The launcher's
    `restart` does not kill the old process, so always make sure it is dead first. macOS has no
    `timeout` or `setsid`.

## Smoke test and benchmark (new)

```bash
eval/gfs-core.sh smoke                 # 25 end-to-end checks on real disk sites; exit 0 or 1
eval/gfs-core.sh smoke /tmp/x mem      # the same in RAM
eval/gfs-core.sh bench --size-mb 256   # primitives, publish/read, versioning, repair, scrub -> eval/results/bench/*.json
```

Both are classes in the bundle (`io.cresco.gfs.core.tools.Smoke`, `Bench`), so they run on any
deployment host with the bundle and its two runtime jars (gson, io.cresco:library). On a shared
filesystem that can't prove its fsync barrier, the smoke test **fails closed** unless `--attest`
is given.

## Continuous integration

CI runs on the HPC cluster as batch jobs, never on GitHub Actions (owner decision 2026-10-02; the workflow
is deleted and Actions is off). A poll job every 10 minutes reads the heads of `main` and `1.3` and submits a
run for any head that has no result yet; the run posts *pending*, then *success* or *failure* with a one-line
summary, to GitHub as a commit status. Each run works on one compute node (CPU only) and runs every step; a
step is skipped only when one it needs failed, so one run reports everything:

| Step | What it checks |
|---|---|
| `core` | the module, engine, integration-matrix and conformance suite, including the live tier's model-based test at its CI size (24 seeds × 100 steps); a failing test is re-run up to twice, and one that passes only on a re-run is listed as flaky |
| `install`, `javaclient`, `pyclient` | the Java and Python clients against the core, each with the other's interop required |
| `lint` | the wire-contract lint |
| `evaltests` | every evaluation-tooling test, including the chaos stage's planner, judges and invariant checks, and the real-core ones against three real core peers |
| `docs` | the operator documentation checked against the code (configuration keys and verbs) |
| `transport`, `smoke`, `bench`, `benchgate` | the transport defaults, the command-line smoke test, a small benchmark and its gate |

**Branches.** Since 2026-10-25 `main` is the development branch of every repository. `1.3` is the release
branch: nothing is pushed to it directly, and a release moves it by fast-forward (`eval/ci/promote.sh`) to a
`main` commit whose CI passed.

## Added for the live tier and stability (2026-10-28)

All of these take a deployment's endpoints and its operator commands, never a host path, so the same tools
run on a workstation fabric, on the HPC test deployment and on a FABRIC slice.

| Harness | What it does | How to run |
|---|---|---|
| Live-tier model test (LT-M1) | Seeded random sequences of live-tier and core operations against a real 3-peer core with two live nodes, checking invariants I1–I6 and the authority rules after every step; a failing seed is shrunk and replays exactly. A lossy mode drops, duplicates and reorders the core-to-node protocol's messages (safety only) | `LiveModelTest`; `-Dgfs.livemodel.seeds=N`, replay with `-Dgfs.livemodel.replay=<file>` or `seed:<n>:<steps>`; `-Dgfs.livemodel.loss=0.05`; the nightly as a sharded batch job (`eval/ci/cluster/livemodel.sbatch`) |
| Chaos stage with live load | Hours of seeded faults under write, read, archive and live-tier load: hub, core, store and tape restarts, site rolls, live node kills, stalls, planned stops, memory pressure, a full live node; judges recovery, repair, invariants I1–I6 from outside and an election ledger; a soak mode with the 72-hour criteria | `eval/chaos.py local --live-node` (a private workstation fabric) or `eval/chaos.py attach` (an existing deployment); `--kinds`, `--soak`; `eval/live_invariants.py` checks I1–I6 once |
| Fault tools | SIGSTOP stalls whose resume is always sent, a bounded memory hog, process statistics | `eval/node_fault.py` with `stall`, `memhog` or `procstat` |
| Live-tier crash cells (LT-X1) | The six `livetier.*` crash points, on a validation deployment beside the standing one (they halt processes) | `eval/crash_matrix.py --point livetier.node.write …` |
| Live end-to-end checks (LT-E1) | Realise, no early copy, list and prospect, extend, drop, withdrawal and FORGET evidence, filerepo, host checks, and a site-loss drill during a realise | `standing.sh live-check` (`eval/cluster/standing_live_check.py`) |
| Realise benchmark (LT-B1) | Cold realises at 1, 4 and 8 flows from disk (or from tape, disruptively), and a warm hit, cross-host, bytes verified | `standing.sh livebench` (`eval/cluster/livebench.py`) |
| Planned-stop tests | A real cluster with a peer stopped under load; the clients' redirect and safe-resend rules in Java and Python | `PlannedStopClusterTest`, the clients' `PlannedStopTest` and `test_planned_stop.py` |

## Added in release 1.3

| Harness | What it does | How to run |
|---|---|---|
| Crash matrix | Crashes the core at every registered fault point, in 4 loss modes, and checks recovery against an oracle | `CrashMatrixTest`; live on a fabric with `eval/crash_matrix.py` |
| Model-based engine tests | Random operation sequences checked against a reference model, shrinking any failure to a minimal case | `EngineModelTest`; `-Dgfs.model.seeds=N`, replay with `-Dgfs.model.replay=<file>`; long run under the `long` tag |
| Power-cut harness | A page-cache model of the file system, cut at every file call in three modes (lose all, prefix, reorder) | `*PowerLossTest`; the 600-history runs are under the `long` tag |
| Chain chaos and partition tests | Kills, partitions and delays during chain replication, checked by a durability and linearizability oracle | `ChainChaosTest`, partition tests |
| WAN grid | 5 sites in a Linux VM with netem round-trip time and loss; striped ingest compared with a LAN reference | the campaign WAN cells |
| Simulated tape | An LTO-class drive and library simulator; mhVTL virtual drives driven through the real Linux tape device path | tape tests; `eval/tape/mhvtl/` |
| HPC live harness | The secured multi-host fabric: sealed keys per node, strict node-key pinning, signed requests | `eval/cluster/live.sh <label> <jar> [check\|bench\|all]` |
| Benchmark gate | Fails CI when a benchmark result falls below 0.4× its baseline, or dedup regresses | `eval/bench_gate.py` |
