# Running the tests

Everything below lives in [`GaiaKeep/gfs`](https://github.com/GaiaKeep/gfs). It needs JDK 21 and
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

Every push to `GaiaKeep/gfs` runs `.github/workflows/test.yml`: the full suite (324 tests at `e3d7b46`,
including the 180-cell integration matrix, of which 60 cells run over the remote protocol, and both smoke runs), the wire-contract lint, the
command-line smoke test, and a small benchmark. Results are uploaded as a build artifact.
