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
