!!! info "Status: Proven (prototype)"
    How to build, run and evaluate the prototype locally.

# GFS prototype — how to build, run and evaluate it locally

The prototype is a new Cresco plugin (`code/gfs`, bundle `io.cresco.gfs`) plus a local launcher,
a Python SDK and an evaluation harness under `run/gfs/`. It runs an 8-JVM fabric on one host and
executes the runnable sections of `EVALUATION-PLAN.md` end to end.

## Layout
```
code/gfs/                          plugin source (Maven, OSGi bundle; see code/gfs/README.md)
run/gfs/gfs.jar                    built bundle staged for upload
run/gfs/launch_gfs_fabric.sh       up | down | status | restart <agent> | kill <agent>
run/gfs/gfs_client.py              SDK over pycrescolib (deploy, RPC, dataplane fetch, jobs)
run/gfs/gfs_eval.py                evaluation harness (E1–E11), writes run/gfs/results/
run/gfs/logs/                      per-node logs + eval logs
run/gfs/data/uky-pathology/        generated test dataset (publisher root)
run/gfs/restore/                   restore targets
```

## Topology
| agent | role(s) | site | class | pledge |
|---|---|---|---|---|
| global-controller | index primary (federation core) | — | — | — |
| uky-pub | publisher + storage (filerepo watches the dataset) | uky | server-raid | 24 MiB |
| s-uofl | storage | uofl | clustered-fs | 2 GiB |
| s-wku | storage | wku | server-raid | 2 GiB |
| s-murray | storage | murray | desktop-single | 2 GiB |
| s-eku | storage | eku | usb-single | 2 GiB |
| s-nku | storage + index replica | nku | server-raid | 2 GiB |
| s-morehead | storage | morehead | desktop-single | 2 GiB |

All agents attach to the global region directly (case 6). Production maps each site to its own
region and tenant (see `CORE-PRINCIPLES.md` §6).

## Build
```bash
cd code/gfs
JAVA_HOME=/opt/homebrew/Cellar/openjdk@21/21.0.5/libexec/openjdk.jdk/Contents/Home \
mvn -o clean package bundle:bundle -DskipTests
cp target/gfs-1.3-SNAPSHOT.jar ../../run/gfs/gfs.jar
```
The agent uber-jar is unchanged; the bundle is uploaded to each agent's repo cache by the client.

## Run
```bash
cd run
./gfs/launch_gfs_fabric.sh up            # ~90 s: global + 7 agents, clean state
./venv/bin/python gfs/gfs_eval.py        # deploys everything, runs E1–E11, ~8 min
./gfs/launch_gfs_fabric.sh down
```
Use the SDK interactively:
```python
from gfs_client import Gfs, dz
g = Gfs()
idx = "global-region:global-controller:<pluginid>"
print(dz(g.call(idx, "listnodes"), "nodes"))
print(dz(g.call(idx, "ledger"), "ledger"))
```

## Dashboard (storage monitoring)

The Cresco mesh dashboard (`code/dashboard`, `github.com/CrescoEdge/dashboard`) grows a **Storage** tab whenever
the mesh it polls carries a GFS deployment; nothing is configured. Detection comes from the `gfs` metric group
every instance registers into `getmetricinventory` (per role: `gfs.index.*` on an index, `gfs.store.*` on a
store), which also yields the index's exact address. Detail is one read-only RPC to the index (`storagesummary`)
every 10 s, and the index primary pushes the same map as a `cresco_msg_type='gfs_state'` dataplane beacon
(`gfs_beacon_period_ms`, default 10000; `gfs_beacon_at_risk` 100; `gfs_beacon_nodes_max` 1000) which the
dashboard prefers while fresh.

```bash
CRESCO_HOST=localhost code/dashboard/run.sh start        # http://localhost:8900/  (log: code/dashboard/dashboard.log)
run/venv/bin/python code/dashboard/verify_render.py http://localhost:8900/ --expect-storage   # headless check + screenshots
curl -s localhost:8900/api/storage | python3 -m json.tool | head -40                          # the storage model
```

The tab shows federation capacity (used / pledged), node liveness (UP / SUSPECT / LOST with time in state),
object health (DURABLE / DEGRADED / LOST), repairs in flight, the per-site reciprocity ledger, the objects that
are not DURABLE (with holders up vs k) and the full roster; the Overview rings every agent that hosts stores.
Kill an agent (`run/gfs/launch_gfs_scale.sh kill n05`) and watch its stores go LOST, the affected objects go
DEGRADED and come back DURABLE after repair.

## Recorded capability demo

```bash
run/gfs/run_dashboard_demo.sh     # AGENTS=12 SITES=4 OBJECT_MIB=256 STORM_OBJECTS=12 NO_GLOBAL_RESTART=1 to vary
run/venv/bin/python run/gfs/gfs_demo_report.py    # joins the driver's numbers with what the dashboard displayed
```

One command: fresh 12-agent fabric, 48 sites deployed, durable objects seeded, dashboard (re)started, then a headless
browser records the dashboard, rotating to the tabs each phase is about (and scrolling the long ones) with an on-screen
caption and a spoken narration track, while `gfs_dashboard_demo.py` runs: baseline; fragment push and get between two agents; control-
plane RPC latency under a 600 MB fragment flood; a 256 MiB promote (encrypt → RS 10+4 → 14 sites) and restore;
four parallel 64 MiB promotes; a verified client fetch; a Cresco stunnel through the mesh carrying the restored
file; an agent kill (LOST → DEGRADED → keyless repair) and return; a two-agent storm over 20 fresh objects and
return; a global-controller restart with self-reconnecting agents. Output `code/dashboard/video/dashboard.mp4`
and the per-phase numbers in `run/gfs/results/scaleDEMO_demo_*.json`.

Placement in the demo is **one fragment per agent** (`{"domain": "agent"}`), not merely per site: an agent hosts
several sites here, so site-distinct placement lets one agent's death take more than `m` fragments of a stripe —
correctly reported as LOST and refused, but not what the demo is showing. With agent-distinct placement and a
12-agent fabric, losing one or two agents costs at most one fragment per agent, well inside the coding margin.
`gfs_demo_report.py` joins the driver's measurements with the dashboard's own retained history (via the recorder's
`timeline.json`), so each phase is reported with the throughput and object health the screen actually showed.

Two operational notes learned the hard way. **Run the whole wrapper for a clean artifact**: re-recording against a
fabric that already carries objects from an earlier demo mixes coding geometries, and objects promoted with tighter
headroom then sit in the "not DURABLE" table when an agent is killed. And the demo sizes its coding so that
`k + m <= usable_agents - 3`, because a repair needs an eligible agent that does not already hold a fragment of that
stripe — at `k + m == usable` the index correctly reports "awaiting an eligible site" instead of repairing.

## What the harness does (in order)
E1 upload + deploy (index, replica, filerepo, 7 gfs nodes) → E2 registry/liveness/probes/scores →
E3 publication + delta propagation (modify/add/delete) → E4 project authorization matrix →
E5 origin-enforced access (stream + inline, forged/tampered/expired grants) → E6 promote/encode/
blind placement/restore → E7 kill two holder sites, degraded restore, auto-repair to the spare
site, site return → E8 corrupt a fragment on disk, scrub, in-place repair → E9 custody quorum, key
loss and reconstruction at another site, key re-establishment → E10 reciprocity ledger and
entitlement refusal → E11 replica convergence, metrics, audit, filerepo regression.

## Scale and performance campaigns
```
run/gfs/launch_gfs_scale.sh up N       N site agents (n01..nNN) + global core; AXMX/GXMX env
run/gfs/launch_gfs_regions.sh up R     R regional controllers as sites (bridged brokers) + publisher agent
run/gfs/gfs_scale.py <tier>            deploy | transport | nodes | policy | tolerance | durability | index | filerepo | storm | report
run/gfs/run_scale_all.sh               240-site campaign (12 agents × 20 instances), all tiers
run/gfs/run_scale_regions.sh           multi-region campaign (SCALE_TAG=REGIONS)
run/gfs/run_scale_4.sh                 index replication at 10^6 files with core-sized replica
run/gfs/results/                       scale_*.json, scaleREGIONS_*.json, codec_bench.jsonl
```
`java -cp run/gfs/gfs.jar io.cresco.gfs.bench.CodecBench 512 14` runs the native codec bench.
The report generator writes `cresco_global_file_system/SCALE-RESULTS.md`.

## Results
See `run/gfs/results/gfs_eval_<timestamp>.md` (latest run summarized in `RESULTS.md` here).
