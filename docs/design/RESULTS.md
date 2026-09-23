!!! info "Status: Proven (prototype)"
    Functional results: 99/99.

# GFS prototype — evaluation results (2026-09-17)

**Latest functional run (run 6, 19:39): 99/99 checks in 80 s** on the tolerance/policy build (adds E8.5/E8.6 index-audit checks). Original run 3 record follows; scale campaigns at the end.


**97/97 checks passed in 80 s** on a fresh 8-JVM fabric (1 global index core + 7 site agents on one
host). Raw record: `run/gfs/results/gfs_eval_20260917-145144.{md,json}`; node logs in
`run/gfs/logs/`. Codec self-test: 23/23 (RS(3,2)/(4,2)/(10,4)/(2,1) every ≤m loss pattern, Shamir,
AES-GCM, tokens).

## What is proven (by section)
| section | proven |
|---|---|
| E1 | bundle uploaded to 8 agents; index, replica, filerepo and 7 gfs nodes deployed from the client; capability inventory answers |
| E2 | 7 nodes registered/UP; classes recorded; network probed; score ordering clustered > server-raid > desktop > usb; availability ≈ 1 |
| E3 | dataset visible with 8 files and matching SHA-256 in 2 s; per-file availability; raw index gated by DUA rules; modify+add+**delete** propagate as one delta in 2 s |
| E4 | 12 authorization checks: owner/delegate/member/outsider behave as specified; member sees exactly the 4 committed files |
| E5 | grant → origin → dataplane stream (8 MiB, SHA-256 verified) and inline fetch; forged, tampered, expired and garbage grants refused **at the origin** |
| E6 | promote → 5 fragments on 5 distinct non-origin sites; 11 stripes × 5, overhead 1.67×; every fragment present with matching hash; on-disk fragments are ciphertext (entropy > 7.9), plaintext marker absent everywhere; no key material on holders; restore verified; a holder with manifest access cannot decrypt |
| E7 | two **data-shard** holders killed → LOST in 12 s → DEGRADED → restore succeeds with RS decode on all 11 stripes → auto-repair regenerates 11 fragments onto the spare site in 9 s without keys → the second lost index is explicitly "awaiting an eligible site" → returning site keeps its identity and the object is DURABLE again in 3 s |
| E8 | on-disk corruption detected by scrub → BAD → in-place regeneration → DURABLE in 3 s; hash matches again |
| E9 | KEK custodied 3-of-5 on other sites; approvals gated to registered approvers; quorum required; holders refuse shares without authorization; approvals consumed; KEK destroyed → restore fails closed → restore at another site with the quorum token rebuilds the KEK from 3 shares → origin re-establishes its key; audit trail complete |
| E10 | ledger: consumed = fragment bytes stored elsewhere; holders' stored-for-others > 0; entitlement from the scoring formula; promote within entitlement accepted, beyond it **refused**; network factor capped |
| E11 | replica converged to the primary's sequence with an identical state hash; MeasurementEngine gauges; audit; filerepo functional regression 10/10 with gfs deployed |

## Performance (8 MiB object, k=3 m=2, 256 KiB blocks, loopback)
| metric | value |
|---|---|
| encode (encrypt + RS + 55 fragment pushes over the dataplane) | 0.181 s ≈ 44 MB/s |
| restore, all data shards present | 0.181 s ≈ 44 MB/s |
| restore with 2 sites down (11 stripes RS-decoded) | 0.183 s |
| repair of one lost site (11 fragments regenerated, no key) | 0.19 s compute; 9 s end-to-end incl. grace + planner cadence |
| loss detection (heartbeat 3 s, lost after 15 s) | 12.1 s |
| scrub → repaired | 3 s |
| publication visible / delta propagation | 2 s / 2 s |
| client stream fetch (8 MiB through wsapi, incl. 1 s stream setup) | 5.6 MB/s wall (≈16 MB/s transfer) |
| RS(3,2) encode, single thread, pure Java | 850 MB/s |

## Defects found and fixed during the evaluation (kept as a record)
1. **Fragment gets timed out (run 1).** `fetchFragment` registered a future, the dataplane listener
   completed and removed it, and the caller then created a second future and waited on that. Fix:
   callers hold the future they registered. Pushes were unaffected because they register once.
2. **Frame/RPC ordering race (run 2, 40 s encodes).** A frame landing between the parked-check and the
   future registration was parked unseen. Fix: registration and delivery are atomic under one lock.
3. **Repair planner gave up on partial placement (run 1).** With one spare site and two lost indices it
   repaired nothing. Fix: repair what can be placed, report the rest as "awaiting an eligible site".
4. **Replica divergence (run 2).** The replica ran its own liveness sweep and committed local
   `node.state` mutations, so its sequence outran the primary and shipped entries were dropped while
   sequence numbers still matched. Fix: replicas are read-only; liveness/probe/repair run only on the
   primary; `commit()` refuses on a replica.
5. **Node identity changed on agent restart (run 2).** A persisted plugin reloads with a fresh
   plugin id unless `inode_id` is set, so a returning site looked like a new node. Fix: the SDK pins
   `inode_id` (`gfs-<site>-<roles>`) — a Cresco-level finding recorded as W-GFS-4 in the principles.
6. **Launcher never exited.** `( cd && java … & )` left a bash parent per JVM holding the pipe. Fix:
   `exec` the JVM.
7. **Harness:** E7 must kill data-shard holders to exercise decoding; E11.3 string check.

## Re-run
```bash
cd run && ./gfs/launch_gfs_fabric.sh up && ./venv/bin/python -u gfs/gfs_eval.py; ./gfs/launch_gfs_fabric.sh down
```


---

# Scale and native performance campaigns (2026-09-17, same day, later)

Full tables: `SCALE-RESULTS.md` (generated from `run/gfs/results/`). Harness: `run/gfs/gfs_scale.py`
with launchers for 12 agents × 20 storage instances (**240 sites**) and for **8 regional controllers
as sites with bridged brokers** (72 sites). Host: 14 cores, 36 GB, loopback network, so these are
compute/protocol ceilings, not WAN numbers.

## Native codec (pure Java, no fabric)
| primitive | single thread | 14 threads |
|---|---|---|
| Reed-Solomon (3,2) / (6,3) / (10,4) / (20,6), any block 64 KiB–1 MiB | 820 / 565 / 425 / 283 MB/s encode; decode-worst within 2 % | 4.2 GB/s at (10,4) |
| AES-256-GCM | 3.4–3.5 GB/s encrypt and decrypt (2.5 MiB stripes) | 25 GB/s |
| SHA-256 | 2.35 GB/s | |
| Shamir 5-of-9 on a 32-byte key | split 60 µs, combine 6 µs | |
| full data path (encrypt + RS(10,4) + fragment hashes) | 305 MB/s | |

## Fabric data path (240 sites)
- **Transport:** fragment push 507–563 MB/s node→node at 512 KiB × 8–32 in flight, get 409 MB/s; control-plane RPC p50 0.26 ms / p99 0.4 ms idle and **p99 0.5–1.1 ms while a 500+ MB/s fragment flood runs** (isolation holds). Client access path with per-chunk verification: 256 MiB at 137–143 MB/s through the Python client.
- **Durability:** encode 210–300 MB/s and restore 280–530 MB/s for 64 MiB–1 GiB objects at (3,2)/(6,3)/(10,4), every restore hash-verified; 8 parallel 64 MiB promotes at 250–330 MB/s aggregate; 100 × 16 MiB objects DURABLE in 5 s.
- **Repair:** a holder's fragments deleted outright are detected by the index audit in 60–200 ms and regenerated without keys: 1 GiB (205–410 fragments) back to DURABLE in 7.6–8.8 s.
- **Federation size:** 240 sites deploy in 28 s and register in 3 s; listnodes 5–6 ms, ledger 3 ms, promote with a (10,4) placement solve 5–7 ms, index at ~22 % of one core under 240 heartbeats per 3 s.
- **Storm:** 40 of 240 sites (17 %) killed at once with weighted-random placement (236–239 sites in use, no agent above 9 %): 83–88 objects DEGRADED and all repaired in 15–79 s; 5–8 objects beyond m=4 as the coding math predicts for a loss that large; control-plane p99 unchanged (< 1 ms).
- **Index scale:** synthetic publication of 10^5–10^6 files at 140–157k files/s (paged deltas of 2000); 1.85 M files in 1.2–1.8 GB heap on the 6 GB core; listfiles page 12–33 ms; resolve p50 0.2 ms, p99 0.4 ms at 5.4–6.6k resolves/s from 16 clients; replica converged with an identical state hash at every size (lag 2–8 s) when sized like the primary. Real filerepo publication: 20k files visible in 5 s, 50k in 10 s.
- **Survivability policies:** 12/12 profiles behaved as specified on both topologies (site/agent/region domains, min_regions, allow/deny sites, jurisdiction, dataset default, unsatisfiable refused with reason).
- **Passive-failure tolerance:** holder agent (20 sites) killed 0.25 s into 12 × 64 MiB encodes → **12/12 complete** in 21 s with 35 audited fallback placements; restores with the holder still dead 5/5 verified (0.5 s, one 4.6 s raced round); all objects DURABLE 9 s after the holder returned. Region-distinct policy turns a whole-region loss into exactly one lost fragment per object (0 beyond m).

## Multi-region (bridged brokers, 8 regions)
Works end to end but the same-host region↔global bridges flap (a documented Cresco same-host
limitation, "Controller Path Lost" every ~7 s per region): cross-region push peaks 441–499 MB/s and
RPC p99 stays 2–4 ms under flood, but promotes/restores/repairs pay 5–20 s stalls per flap and a
region-loss storm healed in 12 min instead of seconds. GFS finished every operation correctly
through fallback and retry; the multi-host DGX mesh is where bridged numbers will be clean (W-GFS-5).

## Defects found and fixed by the scale campaigns
1. **Correlated placement**: top-k by score put every object on the same sites → weighted random spread.
2. **Undetectable holder loss**: scrub cannot see a fragment whose data and sidecar are both gone → index-driven fragment audit (`hasfragments`, MISSING state).
3. **Network work on the liveness timer**: the first audit sweep blocked liveness for minutes when a region flapped → sweeps on a pool with short per-holder budgets; repair dispatch parallel.
4. **Replica memory**: retained log held live maps; 10^6 files OOM'd a 1 GB replica → compact JSON retention, snapshot install, core-sized replicas.
5. **Slow replica catch-up**: 500 entries per 5 s → 5000-entry pages drained continuously.
6. **Client stream loss across bridges**: a dropped dataplane frame produced an incomplete file → verified streaming with per-chunk hashes and range re-fetch.
7. **No tolerance of a flapping holder in the data path**: pushes and fetches now race/fallback/retry with bounded timeouts; failed repairs report back and are re-planned.
8. **Unpaged listings and one-message deltas** at 10^5+ files → pagination and paged deltas.
9. Launcher/harness: JVMs must be `exec`'d; kills verified by PID; stdout line-buffered.

10. **Publisher sequence restart (found by failure benchmark F2/F6):** after a publisher restart its
    delta sequence restarted at zero and the index rejected every page as stale, so new files stayed
    invisible until the counter caught up → the publisher now adopts the index's sequence on
    re-publish and resyncs on a stale reply.
11. **Policy must match the real failure unit:** with `domain=site` on a topology where 20 sites share
    a host, one host loss took 4 of 9 fragments and the object was (correctly) marked beyond
    tolerance. Host-loss benchmarks therefore run with `domain=agent`; this is the survivability
    configuration doing its job, and the reason it must be configurable per data domain.
12. **Cresco agents stuck after a global restart (failure benchmark F5):** killing and restarting the
    index core's controller left several directly-attached agents in `STUCK IN CONNECTION FAULT`
    (their storage nodes LOST) for minutes or until the agents were restarted. Root cause found in the
    controller: the loss re-init's `ActiveClient.shutdown()` starved behind control-plane senders
    that each hold the sender lock for a ~20 s failover (re)connect, so re-discovery of the restarted
    broker never started (one agent self-recovered after 6 min 45 s). Fixed in the controller
    (W-GFS-6): fair, bounded sender lock + non-blocking sender shutdown; dead failover transports
    disposed before any JMS close; `msgIn` bounded (20 s) instead of spinning forever. The failure
    tier still reports any agent that stays down (`agents_stuck_in_connection_fault_after_global_restart`),
    which must be empty on the fixed jar.
13. **Soak error rate was a harness artefact (campaign 4, 11.4 %):** 39 of 54 errors were
    `survivability policy not satisfiable: n=14 distinct agents` — the soak drew the (10,4) profile
    with `domain=agent` on a 12-agent fabric, which can never place 14 agent-distinct fragments. The
    soak now bounds k+m to the fabric (agents − 2, one may be dead). Not a system defect: the index
    correctly refused an unsatisfiable policy instead of placing two fragments on one failure unit.
14. **Replica state hash compared unequal after a snapshot install (campaign 4 index tier):** the
    primary's maps are hash-ordered, a replica that installed a snapshot rebuilds insertion-ordered
    maps, and `statehash` serialized the same logical state in two orders. The hash is now canonical
    (every JSON object emitted with sorted keys), so primary/replica equality is a statement about
    logical state, independent of map implementation or history.
15. **F3 corrupted nothing (campaign 5):** the harness looked up the store directory of the *first*
    gfs instance on the holder's agent, not the holder itself (every instance has its own store), so
    the bit-flip missed and "BAD marked" was a coin flip. F3 now asks the holder node for its store
    and uses the index's cumulative `frags_marked_bad` counter as durable evidence (the BAD state
    itself is transient because the repair sweep replaces the fragment). Campaign 6: scrub reported
    the corrupt fragments, the index marked 98 BAD, restore verified, repaired.
16. **Persisted plugins reloaded under a fresh id (Cresco, W-GFS-4):** `StaticPluginLoader` re-added a
    persisted plugin without `inode_id`, so the agent minted `plugin-<uuid>` and anything keyed by
    region:agent:plugin saw a new node. Fixed in the controller: a persisted plugin restarts under its
    own id. Proof: `gfs_identity_check.py` (deploy without a pinned id, restart the agent, same node id
    comes back UP, no new id appears).
17. **Same-host regional bridges flapped every ~7 s (Cresco, W-GFS-5):** a peer bridge was always built
    to `<peer ip>:discovery_port_remote`; with several regional brokers on one host (distinct ports)
    that is the global's broker, the remote-name check failed, the path was declared lost and
    re-discovered ("Controller Path Lost" 191× per region in the 8-region campaign). Fixed in the
    controller: discovery replies advertise the responder's bound broker port and bridges (and agent
    IO channels) use it; bridge groups are keyed host:port when the port is non-default. Multi-host
    peers on the default port are unchanged. Proof: bridge-flap count after settle on the 8-region
    fabric, then the full multi-region tier re-run on the fixed build.
18. **No way across the tenant boundary except superuser (Cresco, W-GFS-1):** `TenantPolicy` allowed a
    principal only its own `T.<tenant>.` subtree. Implemented named cross-tenant sinks
    (`broker_cross_tenant_sinks = "src->dst[:write|read|any]; …"`): an explicit, configured allow-list
    that never widens READ unless it says so; the GFS flows (site→core inbox, core→site inbox,
    site→site fragment topic) are expressible as three rules. Unit-tested (4/4) in the controller
    build; a live two-tenant GFS fabric is Phase 1 work (W-GFS-3 tenant-qualified fragment bus).

## Final campaigns on the final build (2026-09-17 22:52 → 2026-09-18 00:33)

- **Campaign 6** (`run_final_proof.sh`, 12 agents / 240 sites, then a 4-agent core-sized fabric, then the 7-site
  functional fabric): codec, transport, Java client, node scale, policy 12/12, tolerance, durability sweep,
  repeatability ×3, storm, 3× global restart (all agents back ≤ 48 s), 20-min soak at 0.0 % errors, filerepo
  publication, index to 10^6 files with the replica hash equal at every size, functional E1–E11 99/99. Its
  failure tier crashed at F5 (`fail/f5.bin not indexed in 300 s`) after the publisher had exported the delta;
  the index log had been truncated by the restart, so the launcher now appends logs and `wait_indexed`
  prints diagnostics; the tier was re-run in campaign 8 and passed. (The functional launcher also wiped the
  campaign log; it now removes only its own logs, and the campaign stream is kept in
  `results/campaign6-final-proof-monitor.log`.)
- **Campaign 7** (`run_cresco_fix_proof.sh`): embeds controller `c891854` (W-GFS-1/4/5) into the agent;
  4-agent fabric: 2× global restart (all back ≤ 52 s); 8 same-host regions: **0 bridge flaps in 150 s**
  (was 191 per region), then the full multi-region tier on the fixed bridges (policy 12/12, cross-region push
  576 MB/s, get 648 MB/s, bridged client fetch 129.7 MB/s with 0 re-fetched chunks, region storm healed in 12 s).
- **Campaign 8** (`run_failure_final.sh`, 240 sites): plugin identity check (same id back in 17.2 s after a
  real JVM restart), F1–F8 all pass (F5: answering 9.9 s, 240 nodes back 34 s, durable layout preserved,
  replica equal), 3× global restart record (≤ 44.2 s, ≤ 3.6 s per agent, 0 stuck). **Claims registry: 55/55.**

## Exhaustive benchmark campaign (see `SCALE-RESULTS.md` sections and `CLAIMS.md`)
- Repeatability: transport, encode/restore/repair (64 MiB–1 GiB) and index latency repeated 3×
  with mean/stdev/min/max and coefficient of variation.
- Failure benchmarks F1–F8: repairer dies mid-repair; source holder dies mid-repair; a holder serves
  corrupt bytes; custody holders lost down to t and below t; index primary restart (journal replay,
  re-registration, replica equality, promote/restore after); publisher restart; beyond-m loss then
  return; continuous promotes while two agents die.
- Soak: 20 minutes of mixed promote/restore/fetch with a random agent killed every ~90 s and
  restarted 30 s later; error rate, throughput percentiles, RSS trend, final durability.
- Java clientlib access path (verified stream) on a quiet fabric and during the soak.
- `CLAIMS.md`: every claim in these documents mapped to the executed checks and measured values,
  evaluated mechanically by `run/gfs/gfs_claims.py`; anything without evidence is marked UNPROVEN.

## Monitoring: dashboard Storage tab (2026-09-18)

The Cresco mesh dashboard (`github.com/CrescoEdge/dashboard`) gained a Storage tab that exists only while a GFS
deployment is visible in the metric inventory. Changes on the GFS side: gauges registered per role (`gfs.index.*`
only on an index, `gfs.store.*` only on a store) so the inventory identifies the index; `storagesummary` (stats,
roster, reciprocity ledger, objects not DURABLE, replicas pulling the journal with their lag) in one read-only
RPC; `listobjects` filters (`state`, `not_state`, `site`, `dataset_id`, `limit`) so a monitor never pulls every
manifest; a `gfs_state` dataplane beacon from the index primary every `gfs_beacon_period_ms` (10 s) that the
dashboard prefers while fresh. Proof (`gfs_dashboard_check.py`, `scale_dashboard_20260918-094353.json`, 6 agents /
49 stores / 8 objects): index and 51 instances auto-detected; after killing the agent with 8 stores the dashboard
showed not-DURABLE objects at 16.2 s (peak 6), all 8 stores LOST at 26.2 s, every object DURABLE again at 36.3 s;
poll path healthy throughout; playwright render check 8 tabs / 0 errors. Claims registry: 58/58.

## Defect 19 — the encoder dropped its in-flight stripe window when the file size was an exact multiple of the stripe size (2026-09-18)

**Found by** the recorded capability demo: a 256 MiB object promoted at k=8, m=3, block 512 KiB committed as DURABLE,
and its restore failed with `IllegalStateException: restored content hash mismatch`.

**What happened.** `DurabilityEngine.runEncode` pipelines stripes: stripe *s* is encrypted and coded while up to
`stripe_window` earlier stripes are still being pushed, and the window is drained when the loop sees a *short* read
(`boolean last = got < stripeBytes`). If the file size is an exact multiple of `k × block_size` the final read is a
FULL stripe, so `last` is false; the next iteration reads `got == 0` and took `if (got == 0 && s > 0) break;` —
leaving the window undrained. Those stripes' fragments had already been pushed to holders, but the stripes were
never appended to the manifest. 256 MiB / (8 × 512 KiB) = exactly 64 stripes, `stripe_window` was 6, and the
manifest recorded 58. The object then read DURABLE while six stripes of data were unreachable.

**Why the campaigns missed it.** Every ratio used in the functional and scale sweeps (3+2, 6+3, 10+4 at 256 KiB and
512 KiB blocks, sizes 1/16/64/256/1024 MiB) produces a partial final stripe, so `last` was always true. The 8+3
geometry, chosen by the demo to fit a 12-agent fabric, was the first exact multiple ever encoded.

**Blast radius.** Encode only; repair, restore and the index are unaffected. Nothing corrupt is ever returned: the
restore verifies the SHA-256 of the whole object against the manifest and fails closed. The damage is a durable-tier
object that cannot be restored while the index reports it DURABLE.

**Fix.** The drain is now a single helper called at *every* exit from the encode loop, including the exact-multiple
EOF path, and the manifest geometry is asserted before it is committed: `stripe_count` must equal
`ceil(size / (k × block))` or the encode fails (`encodefailed`) instead of committing a short manifest.

**Regression.** `gfs_encode_geometry_check.py` promotes, for each of several geometries, files that are an exact
multiple of the stripe size and one byte either side, checks the manifest stripe count against the geometry and
restores every object with a full SHA-256 verify.
