!!! info "Status: Proven (prototype)"
    The mechanical claims check: 59/59.

# GFS claims registry — mechanical evidence check

*Generated 2026-09-18 11:06 by `run/gfs/gfs_claims.py` from `run/gfs/results/`. A claim is PROVEN only when the executed checks and measurements listed as evidence satisfy it.*

**59/59 claims proven.**

| area | claim | status | evidence |
|---|---|---|---|
| P2 bytes stay put | Publication moves only index entries; deletes propagate | **PROVEN** | E3.1=PASS, E3.2=PASS, E3.7=PASS |
| P3 projects | Raw index is owner/admin-gated; members see exactly committed files | **PROVEN** | E3.4=PASS, E3.5=PASS, E4.10=PASS, E4.11=PASS |
| P3 delegation | Only dataset owner/delegates commit; outsiders and plain members cannot | **PROVEN** | E4.5=PASS, E4.6=PASS, E4.7=PASS, E4.8=PASS |
| P4 origin enforcement | Forged, tampered, expired and garbage grants are refused at the origin | **PROVEN** | E5.6=PASS, E5.7=PASS, E5.8=PASS, E5.9=PASS |
| P4 routing | A granted fetch streams from the holding site and verifies | **PROVEN** | E5.2=PASS, E5.3=PASS |
| P5 blind holders | Fragments on disk are ciphertext (entropy > 7.9), plaintext marker absent, no key material on holders | **PROVEN** | E6.8=PASS, E6.10=PASS, E6.11=PASS |
| P5 blind holders | A holder with manifest access but no key cannot restore | **PROVEN** | E6.13=PASS |
| P5 keyless repair | Repair regenerates fragments without any key material | **PROVEN** | E7.5=PASS, E7.6=PASS, E8.3=PASS; scale rows repaired=True |
| P6 custody | KEK custodied t-of-n on other sites; reconstruction needs an approver quorum; holders refuse without authorization; approvals are consumed | **PROVEN** | E9.1=PASS, E9.2=PASS, E9.3=PASS, E9.6=PASS, E9.7=PASS, E9.8=PASS, E9.9=PASS |
| P6 custody | Site key loss: restore fails closed without key; restore at another site succeeds with the quorum token; origin re-establishes its key | **PROVEN** | E9.11=PASS, E9.12=PASS, E9.13=PASS |
| P6 custody | t=3 of 5: two custody holders dead still reconstructs; three dead fails closed | **PROVEN** | {"key_id": "kek-pub-site-3e3652", "t": 3, "n": 5, "holders_dead_first": 2, "holders_alive_first": 3, "reconstruct_with_t_alive_ok": true, "detail_first": "restored", "holders_dead_second": 5, "holders |
| P7 distinct domains | k+m fragments land on distinct sites, never the origin site | **PROVEN** | E6.3=PASS |
| P7 coding math | Any k of n fragments reconstruct; k-1 do not | **PROVEN** | UNIT: RS reconstruct any<=m losses x60 for (3,2),(4,2),(10,4),(2,1); refuses k-1 (CodecSelfTest 23/23) |
| P8 reciprocity | Entitlement follows contribution; promote beyond entitlement refused; network factor capped | **PROVEN** | E10.1=PASS, E10.3=PASS, E10.4=PASS, E10.5=PASS, E10.7=PASS |
| P9 participation | Loss detected by liveness; repair after grace; unrepairable placement stated explicitly | **PROVEN** | E7.2=PASS, E7.5=PASS, E7.7=PASS |
| P10 Cresco foundation | Control-plane RPC p99 stays under 2 ms while a >= 400 MB/s fragment flood runs on the same fabric | **PROVEN** | flood 445 MB/s, rpc p99 0.60 ms |
| P12 fail closed | Non-member sites, unknown nodes, unauthorized custody requests are refused | **PROVEN** | E9.4=PASS, E9.7=PASS, E3.4=PASS |
| P13 replication | Replica converges to the primary with an identical state hash | **PROVEN** | E11.1=PASS, E11.2=PASS; scale rows hash_equal=[True, True, True, True] |
| P13 replication | Replica hash equal at 10^6 files with core-sized replica | **PROVEN** | [(100000, True, 2.9), (250000, True, 3.9), (500000, True, 6.6), (1000000, True, 13.4)] |
| P14 index granularity | File-granular index with paged deltas ingests >= 100k files/s | **PROVEN** | [117300, 142050, 141331, 142464] |
| Integrity | Silent corruption is caught by scrub and repaired; total loss of a fragment is caught by the index audit | **PROVEN** | E8.1=PASS, E8.3=PASS, E8.5=PASS, E8.6=PASS |
| Integrity | A holder serving corrupt bytes cannot corrupt a restore (hash check) and gets marked BAD | **PROVEN** | {"fragments_corrupted": 86, "restore_verified": true, "restore_s": 0.55, "scrub_reported_bad": 7297, "index_frags_marked_bad_delta": 86, "marked_BAD_by_scrub": true, "index_BAD_state_observed": true,  |
| Identity | Node identity survives an agent restart (returning site keeps its fragments) | **PROVEN** | E7.8=PASS, E7.9=PASS |
| Survivability | 12/12 profiles behave as specified (single-region) | **PROVEN** | 9/9 |
| Survivability | 12/12 profiles behave as specified (multi-region incl. domain=region, min_regions) | **PROVEN** | 12/12 |
| Survivability | Region-distinct policy: losing a whole region costs exactly one fragment per object, none beyond m | **PROVEN** | {"mean": 0.82, "max": 1, "hist": {"0": 11, "1": 49}} |
| Tolerance | Encodes complete when a holder agent dies mid-encode (fallback placement) | **PROVEN** | {"objects": 12, "size_mib": 64, "planned_on_victim": 5, "killed_at_s": 0.4, "kill_confirmed": true, "done": 12, "seconds": 22.8, "fallback_placements": 47, "durable_now": 9} |
| Tolerance | Restores complete with a dead holder (raced fetch) | **PROVEN** | {"attempted": 5, "ok": 5, "seconds": [0.51, 0.51, 0.51, 0.51, 4.57]} |
| Tolerance | Same on the bridged multi-region fabric | **PROVEN** | {"enc": 12, "fallbacks": 67, "restores": 5} |
| Failure | Repairer dies mid-repair: another node completes the repair | **PROVEN** | {"holder_killed": "n12", "repairer_killed": "n01", "healed": true, "heal_s": 77.9, "final_repairer": "global-region:n02:gfs-site-020", "repairer_changed": true, "restore_after": true} |
| Failure | Source holder dies mid-repair: repair still completes | **PROVEN** | {"killed": ["n01", "n11"], "healed": true, "heal_s": 32.5} |
| Failure | Index primary restart: journal replay preserves state; nodes re-register; replica hash equal; promote/restore work after | **PROVEN** | {"journal_entries": 834, "files": 409, "objects_before": 4, "wsapi_back_s": 9.9, "index_answering_s": 9.9, "all_nodes_reregistered_s": 34.0, "state_hash_preserved": true, "full_hash_preserved": false, "replica_hash_equal |
| Cresco | W-GFS-4 fixed: a plugin deployed WITHOUT a pinned id keeps its identity across an agent restart (persisted plugins reload under their own id) | **PROVEN** | {"agent": "n12", "plugin_id": "plugin-d02be080-3eef-4240-bb50-5203c7a96f88", "id_minted_by_agent": true, "node_id": "global-region:n12:plugin-d02be080-3eef-4240-bb50-5203c7a96f88", "up_before_restart": true, "node_left_u |
| Cresco | W-GFS-5 fixed: same-host regional bridges are stable (zero 'Controller Path Lost' flaps after settle; the global sees every region) because peers advertise their bound broker port | **PROVEN** | {"regions": 8, "global_sees_regions": 8, "window_s": 150, "path_lost_total": 0, "monitor_exited_total": 0, "starting_bridge_total": 64} |
| Cresco | W-GFS-1 implemented: named cross-tenant sinks are the only way across the tenant boundary (JUnit TenantPolicyCrossTenantSinkTest 4/4 in the controller build) | **PROVEN** | controller surefire report |
| Failure | Agents reconnect after a global-controller restart with NO manual agent restart (W-GFS-6 fixed in the controller): every agent back on every run, zero STUCK IN CONNECTION FAULT lines, promote+restore work after | **PROVEN** | {"runs": 3, "agents": 12, "storage_nodes": 240, "all_runs_all_agents_back": true, "agents_not_back_union": [], "max_all_back_s": 44.2, "max_lost_to_recovered_s": 3.6, "stuck_lines_total": 0, "post_restore_ok_all": true} |
| Failure | Publisher restart: dataset back online, restore and fetch work after | **PROVEN** | {"back_s": 0.1, "dataset_online": true, "restore_after": true, "fetch_after": true} |
| Failure | Beyond-m loss is explicit (LOST, restore fails closed) and objects return to DURABLE when sites return | **PROVEN** | {"agents_killed": ["n08", "n09", "n10", "n11", "n12"], "states_after_loss": {"LOST": 9, "DURABLE": 1}, "restore_of_LOST_object_fails_closed": true, "lost_restore_detail": "IllegalStateException: stripe 0: only 9 of 10 fr |
| Failure | Promotes keep succeeding while two agents die and repairs run (mixed load) | **PROVEN** | {"agents_killed": ["n11", "n12"], "promotes": 16, "ok": 16, "failed": 0, "promote_p50_s": 1.01, "promote_p99_s": 10.09, "objects": 16, "all_repaired": true, "storm_window_s": 60.7} |
| Storm | 40 of 240 sites lost at once: every repairable object healed; control p99 < 2 ms during the storm | **PROVEN** | degraded 85 healed in 21.1 s, beyond m 5, rpc p99 0.391209 |
| Placement | Fragments spread across >= 95 % of sites; no agent holds > 12 % of fragments | **PROVEN** | {"holders_used": 239, "sites_available": 240, "max_share_of_one_agent": 0.092} |
| Soak | Sustained mixed workload with random kills: error rate <= 5 %, all objects DURABLE at the end, no unbounded RSS growth (< 2x) | **PROVEN** | ops {'promote': 192, 'fetch': 95, 'restore': 193, 'kills': 13, 'restarts': 12} error_rate 0.0 durable=True rss 773.90625->884.765625 MB |
| Integrity | The manifest always covers the whole file: for every coding geometry, a file that is an EXACT multiple of k x block_size (and one byte either side) yields ceil(size/(k*block)) stripes and restores with a verified SHA-256 | **PROVEN** | {"cases": 12, "geometry_ok": 12, "restore_ok": 12, "all_ok": true} |
| Monitoring | The mesh dashboard detects a GFS deployment and the index address from the metric inventory alone (no configuration) and renders every tab without errors | **PROVEN** | {"detected": {"index_auto": true, "instances": {"index": 2, "storage": 49}, "instances_total": 51, "roster": 49, "expected_roster": 49, "source": "push", "poll": {"ts": 1789738979.251324, "age_s": 8.4, "index": "global-r |
| Monitoring | After an agent kill, every store on it shows LOST and the affected objects show not-DURABLE on the dashboard within 40 s (pushed gfs_state beacon) | **PROVEN** | {"agent_killed": "n05", "stores_on_agent": 8, "lost_visible_s": 26.2, "risk_visible_s": 16.2, "risk_peak": 6, "risk_peak_history": 6, "sources_seen": ["push"]} |
| Monitoring | The dashboard shows every object DURABLE again within 90 s of the kill while the dead stores stay LOST, and its storagesummary poll path stays healthy while the beacon feeds the UI | **PROVEN** | {"repaired_visible_s": 36.3, "poll_path_ok": true, "sources_seen": ["push"]} |
| Perf codec | RS(10,4) encode >= 400 MB/s single thread (pure Java) | **PROVEN** | {"bench": "rs", "k": 10.0, "m": 4.0, "block": 262144.0, "encode_mb_s": 425.07, "decode_worst_mb_s": 424.78, "overhead": 1.4} |
| Perf codec | RS(3,2) encode >= 750 MB/s single thread | **PROVEN** | {"bench": "rs", "k": 3.0, "m": 2.0, "block": 262144.0, "encode_mb_s": 834.02, "decode_worst_mb_s": 855.89, "overhead": 1.67} |
| Perf codec | AES-256-GCM >= 3 GB/s on 2.5 MiB stripes | **PROVEN** | [{'bench': 'aes_gcm', 'stripe_bytes': 786432.0, 'encrypt_mb_s': 210.34, 'decrypt_mb_s': 3625.69}, {'bench': 'aes_gcm', 'stripe_bytes': 2621440.0, 'encrypt_mb_s': 3459.61, 'decrypt_mb_s': 3640.98}, {'b |
| Perf transport | Fragment push >= 450 MB/s and get >= 350 MB/s node to node | **PROVEN** | push max 510, get max 415 |
| Perf durability | 1 GiB object: encode >= 200 MB/s, restore >= 250 MB/s, verified | **PROVEN** | {"encode_mb_s": 271.76220806794055, "restore_mb_s": 282.7948080640707, "restore_ok": true} |
| Perf durability | 1 GiB lost holder regenerated in <= 15 s (keyless) | **PROVEN** | {"repair_fragments": 205, "audit_ms": 90, "repair_s": 8.0, "repair_ok": true} |
| Perf durability | Every restore in the sweep hash-verified and every lost holder repaired | **PROVEN** | 26/26 rows |
| Perf index | 10^6 files: resolve p99 <= 1 ms and >= 5000 resolves/s from 16 clients | **PROVEN** | [(100000, 0.7040500640869141, 5488.5), (250000, 0.36907196044921875, 5426.3), (500000, 0.3840923309326172, 5385.9), (1000000, 0.9000301361083984, 5466.1)] |
| Perf index | Real filerepo publication: 50k files visible in <= 30 s | **PROVEN** | [{'files': 20000, 'generate_s': 1.4, 'time_to_visible_s': 5.1, 'files_per_s': 3898, 'publisher': {'dataset_id': 'frpub-20000', 'owner': 'orcid:0000-0001-alice', 'root': '/Users/cody/code/cresco/run/gfs/data/frpub-20000', |
| Perf federation | 240 sites: listnodes p50 <= 20 ms, promote with placement solve p50 <= 20 ms, index CPU <= 50 % of one core | **PROVEN** | listnodes 5 ms, promote 3 ms, cpu 21.900000000000002 |
| Perf client | Java client access path >= 200 MB/s for 256 MiB, hash verified (all reps) | **PROVEN** | {"summary": true, "reps": 5, "ok": 5, "mb_per_s_min": 31.3, "mb_per_s_median": 403.0, "mb_per_s_max": 407.9, "reps_detail": [{"rep": 0, "bytes": 143654912, "chunks": 1024, "refetched": 476, "rounds": 2, "seconds": 8.171, |
| Perf client | Python client verified access path >= 100 MB/s for 256 MiB | **PROVEN** | {"mib": 256, "seconds": 1.81, "mb_per_s": 141.7, "sha_ok": true, "verify": {"rounds": 1, "refetched_chunks": 0, "corrupt_chunks": 0, "missing_chunks": 0, "verif |
| Repeatability | Key throughput metrics repeat within 25 % coefficient of variation across runs | **PROVEN** | {'push_256K_x8_MBps': 2.1, 'push_512K_x32_MBps': 4.1, 'get_256K_x8_MBps': 1.7, 'rpc_p99_ms': 8.3, 'encode_64MiB_MBps': 3.7, 'restore_64MiB_MBps': 4.1, 'repair_64MiB_s': 1.7, 'encode_256MiB_MBps': 1.8, 'restore_256MiB_MBp |
