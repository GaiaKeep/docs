!!! info "Status: Proven (prototype)"
    Full scale and performance tables.

# GFS scale and native performance results

*Generated 2026-09-18 00:27 from `run/gfs/results/`. Host: 14-core Apple silicon, 36 GB, single machine; all nodes share the loopback network, so numbers are compute/broker/protocol ceilings, not WAN numbers.*

## Headline

- **Durability data path:** encode 233–291 MB/s, restore 254–393 MB/s for 256 MiB–1 GiB objects; every restore hash-verified; every lost holder detected by audit in < 122 ms and regenerated without keys
- **Transport:** fragment push peak 577 MB/s node→node; control-plane RPC p99 0.72 ms while a 444 MB/s flood runs (isolation holds); client fetch 143.7 MB/s
- **Index:** 1,000,000 files ingested at 143,444 files/s, 1811 MB heap, resolve p99 0.4 ms at 5398 resolves/s; replica converged=True (lag 14.2 s)
- **Federation size:** 240 sites on one host; placement solve + promote 3 ms; index 19 % of one core under heartbeats
- **Storm:** 40 of 240 sites lost at once → 85 objects repaired in 27.2 s, 7 beyond m (coding limit), control p99 0.5 ms during the storm

## Native codec (no fabric)

| bench | parameters | result |
|---|---|---|
| env | cores=14, threads=14, target_mib=512, jvm=21.0.5 |  |
| rs | k=3, m=2, block=64 KiB, overhead=1.67 | encode_mb_s=793.3, decode_worst_mb_s=784.9 |
| rs | k=3, m=2, block=256 KiB, overhead=1.67 | encode_mb_s=833.9, decode_worst_mb_s=855.8 |
| rs | k=3, m=2, block=512 KiB, overhead=1.67 | encode_mb_s=822.0, decode_worst_mb_s=845.2 |
| rs | k=3, m=2, block=1024 KiB, overhead=1.67 | encode_mb_s=813.5, decode_worst_mb_s=836.2 |
| rs | k=4, m=2, block=64 KiB, overhead=1.5 | encode_mb_s=847.5, decode_worst_mb_s=720.8 |
| rs | k=4, m=2, block=256 KiB, overhead=1.5 | encode_mb_s=852.5, decode_worst_mb_s=851.0 |
| rs | k=4, m=2, block=512 KiB, overhead=1.5 | encode_mb_s=836.0, decode_worst_mb_s=838.7 |
| rs | k=4, m=2, block=1024 KiB, overhead=1.5 | encode_mb_s=840.9, decode_worst_mb_s=841.9 |
| rs | k=6, m=3, block=64 KiB, overhead=1.5 | encode_mb_s=570.4, decode_worst_mb_s=563.3 |
| rs | k=6, m=3, block=256 KiB, overhead=1.5 | encode_mb_s=568.0, decode_worst_mb_s=568.0 |
| rs | k=6, m=3, block=512 KiB, overhead=1.5 | encode_mb_s=563.0, decode_worst_mb_s=559.9 |
| rs | k=6, m=3, block=1024 KiB, overhead=1.5 | encode_mb_s=561.8, decode_worst_mb_s=561.5 |
| rs | k=10, m=4, block=64 KiB, overhead=1.4 | encode_mb_s=428.3, decode_worst_mb_s=426.4 |
| rs | k=10, m=4, block=256 KiB, overhead=1.4 | encode_mb_s=423.2, decode_worst_mb_s=425.7 |
| rs | k=10, m=4, block=512 KiB, overhead=1.4 | encode_mb_s=423.0, decode_worst_mb_s=422.1 |
| rs | k=10, m=4, block=1024 KiB, overhead=1.4 | encode_mb_s=423.2, decode_worst_mb_s=422.4 |
| rs | k=20, m=6, block=64 KiB, overhead=1.3 | encode_mb_s=286.6, decode_worst_mb_s=284.8 |
| rs | k=20, m=6, block=256 KiB, overhead=1.3 | encode_mb_s=282.1, decode_worst_mb_s=282.9 |
| rs | k=20, m=6, block=512 KiB, overhead=1.3 | encode_mb_s=280.5, decode_worst_mb_s=282.1 |
| rs | k=20, m=6, block=1024 KiB, overhead=1.3 | encode_mb_s=281.4, decode_worst_mb_s=281.0 |
| rs_parallel | k=10, m=4, block=256 KiB, threads=14 | encode_mb_s=3872.2 |
| aes_gcm | stripe_bytes=768 KiB | encrypt_mb_s=209.2, decrypt_mb_s=3411.2 |
| aes_gcm | stripe_bytes=2560 KiB | encrypt_mb_s=3389.1, decrypt_mb_s=3472.1 |
| aes_gcm | stripe_bytes=5120 KiB | encrypt_mb_s=3482.7, decrypt_mb_s=3499.8 |
| aes_gcm_parallel | threads=14 | encrypt_mb_s=24232.5 |
| sha256 |  | mb_s=2318.9 |
| shamir | n=9, t=5 | split_us=60.2, combine_us=5.9 |
| datapath_encode_1thread | k=10, m=4, block=512 KiB | mb_s=308.5 |

## Topology

- 12 site agents × 20 storage instances = **240 sites** (+ publisher site + index core + replica); deploy 27.3 s; all registered in 3.0 s

## Transport (dataplane fragment frames + control receipts, node → node)

| op | frame | concurrency | MB/s | frames/s | p50 ms | p99 ms | failed |
|---|---|---|---|---|---|---|---|
| push | 64 KiB | 1 | 59.5 | 952 | 0.9 | 2.5 | 0 |
| push | 64 KiB | 8 | 158.5 | 2536 | 2.9 | 10.5 | 0 |
| push | 64 KiB | 32 | 159.8 | 2557 | 5.7 | 50.8 | 0 |
| push | 256 KiB | 1 | 160.8 | 643 | 1.4 | 2.5 | 0 |
| push | 256 KiB | 8 | 386.8 | 1547 | 5.0 | 11.2 | 0 |
| push | 256 KiB | 32 | 375.9 | 1504 | 10.1 | 26.0 | 0 |
| push | 512 KiB | 1 | 225.6 | 451 | 2.0 | 3.6 | 0 |
| push | 512 KiB | 8 | 470.2 | 940 | 7.9 | 27.9 | 0 |
| push | 512 KiB | 32 | 576.8 | 1154 | 12.7 | 36.7 | 0 |
| get | 256 KiB | 1 | 86.3 | 345 | 1.7 | 6.0 | 0 |
| get | 256 KiB | 8 | 375.6 | 1502 | 5.0 | 12.2 | 0 |
| get | 256 KiB | 32 | 429.1 | 1716 | 8.9 | 18.6 | 0 |

| control-plane RPC (probe round trip) | p50 ms | p99 ms | max ms |
|---|---|---|---|
| idle | 0.26 | 0.36 | 7.59 |
| during a 512 KiB × 32-way fragment flood (444 MB/s) | 0.26 | 0.72 | 1.43 |

Client access path (grant → origin → filerepo streamfile → wsapi → Python client, verified per chunk): 256 MiB in 1.78 s = **143.7 MB/s** (sha256 ok=True; {'rounds': 1, 'refetched_chunks': 0, 'corrupt_chunks': 0, 'missing_chunks': 0, 'verified': True}; includes stream setup; Python-client bound)

## Durability data path (promote → encode → blind placement; restore; audit-detected keyless repair)

| object | (k,m) | block | stripes | overhead | encode MB/s | time-to-DURABLE s | restore MB/s | restore ok | lost frags | audit ms | detect+repair s (job s) | repaired |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 MiB | (3,2) | 256 KiB | 2 | 1.67 | 71.4 | 0.52 | 76.9 | True | 2 | 44 | 0.55 (0.012) | True |
| 1 MiB | (3,2) | 512 KiB | 1 | 1.67 | 62.5 | 0.52 | 90.9 | True | 1 | 49 | 0.56 (0.009) | True |
| 1 MiB | (6,3) | 256 KiB | 1 | 1.50 | 66.7 | 0.52 | 90.9 | True | 1 | 47 | 0.56 (0.013) | True |
| 1 MiB | (6,3) | 512 KiB | 1 | 1.50 | 83.3 | 0.52 | 66.7 | True | 1 | 45 | 0.56 (0.009) | True |
| 1 MiB | (10,4) | 256 KiB | 1 | 1.40 | 40.0 | 0.52 | 66.7 | True | 1 | 45 | 0.56 (0.013) | True |
| 1 MiB | (10,4) | 512 KiB | 1 | 1.40 | 43.5 | 0.52 | 71.4 | True | 1 | 46 | 0.56 (0.013) | True |
| 16 MiB | (3,2) | 256 KiB | 22 | 1.67 | 190.5 | 0.52 | 296.3 | True | 22 | 40 | 0.56 (0.121) | True |
| 16 MiB | (3,2) | 512 KiB | 11 | 1.67 | 129.0 | 0.51 | 156.9 | True | 11 | 44 | 0.55 (0.11) | True |
| 16 MiB | (6,3) | 256 KiB | 11 | 1.50 | 172.0 | 0.51 | 258.1 | True | 11 | 46 | 0.56 (0.139) | True |
| 16 MiB | (6,3) | 512 KiB | 6 | 1.50 | 197.5 | 0.51 | 266.7 | True | 6 | 51 | 0.57 (0.126) | True |
| 16 MiB | (10,4) | 256 KiB | 7 | 1.40 | 179.8 | 0.52 | 170.2 | True | 7 | 41 | 0.56 (0.131) | True |
| 16 MiB | (10,4) | 512 KiB | 4 | 1.40 | 155.3 | 0.52 | 205.1 | True | 4 | 42 | 0.56 (0.138) | True |
| 64 MiB | (3,2) | 256 KiB | 86 | 1.67 | 211.9 | 0.52 | 288.3 | True | 86 | 40 | 0.56 (0.47) | True |
| 64 MiB | (3,2) | 512 KiB | 43 | 1.67 | 193.9 | 0.51 | 263.4 | True | 43 | 49 | 0.56 (0.422) | True |
| 64 MiB | (6,3) | 256 KiB | 43 | 1.50 | 228.6 | 0.51 | 273.5 | True | 43 | 40 | 0.56 (0.51) | True |
| 64 MiB | (6,3) | 512 KiB | 22 | 1.50 | 244.3 | 0.51 | 306.2 | True | 22 | 42 | 0.55 (0.445) | True |
| 64 MiB | (10,4) | 256 KiB | 26 | 1.40 | 245.2 | 0.52 | 242.4 | True | 26 | 43 | 1.07 (0.519) | True |
| 64 MiB | (10,4) | 512 KiB | 13 | 1.40 | 237.9 | 0.51 | 246.2 | True | 13 | 54 | 0.57 (0.462) | True |
| 256 MiB | (3,2) | 256 KiB | 342 | 1.67 | 233.4 | 1.54 | 350.2 | True | 342 | 54 | 2.15 (1.849) | True |
| 256 MiB | (3,2) | 512 KiB | 171 | 1.67 | 278.3 | 1.02 | 392.6 | True | 171 | 53 | 2.11 (1.815) | True |
| 256 MiB | (6,3) | 256 KiB | 171 | 1.50 | 256.5 | 1.03 | 340.0 | True | 171 | 57 | 2.67 (2.156) | True |
| 256 MiB | (6,3) | 512 KiB | 86 | 1.50 | 290.6 | 1.03 | 347.8 | True | 86 | 51 | 2.1 (1.859) | True |
| 256 MiB | (10,4) | 256 KiB | 103 | 1.40 | 256.3 | 1.02 | 362.6 | True | 103 | 60 | 2.65 (2.071) | True |
| 256 MiB | (10,4) | 512 KiB | 52 | 1.40 | 248.5 | 1.52 | 277.7 | True | 52 | 58 | 2.11 (1.852) | True |
| 1024 MiB | (10,4) | 256 KiB | 410 | 1.40 | 252.3 | 4.59 | 296.9 | True | 410 | 122 | 8.86 (8.405) | True |
| 1024 MiB | (10,4) | 512 KiB | 205 | 1.40 | 270.8 | 4.07 | 253.5 | True | 205 | 99 | 7.99 (7.695) | True |

Parallel promotes: 8 × 64 MiB at (6,3): 8 done in 2.05 s = **249.2 MB/s aggregate**

## Index scale (synthetic publisher, paged deltas of 2000)

| files | ingest files/s | index heap MB | index RSS MB | listfiles(2000) p50 ms | commit * ms | projectfiles(2000) p50 ms | resolve p50 / p99 ms | resolve/s (16 clients) | replica lag s | replica hash equal |
|---|---|---|---|---|---|---|---|---|---|---|
| 100000 | 123736 | 138 | 813 | 14 | 0.6 | 14 | 0.4 / 0.8 | 5413.7 | 2.8 | True |
| 250000 | 142501 | 304 | 1489 | 15 | 0.4 | 23 | 0.2 / 0.4 | 5322.2 | 3.7 | True |
| 500000 | 142749 | 1018 | 2770 | 13 | 0.3 | 20 | 0.2 / 0.4 | 5396.9 | 6.5 | True |
| 1000000 | 143444 | 1811 | 5536 | 22 | 0.3 | 45 | 0.2 / 0.4 | 5397.7 | 14.2 | True |

## Real publication through filerepo (scan + SHA-256 + Derby catalog + delta export)

| files | time to visible s | files/s |
|---|---|---|
| 20000 | 10.1 | 1971 |
| 50000 | 10.1 | 4929 |

## Node scale

- **240 sites** registered (241 UP); listnodes p50 5 ms; ledger p50 5 ms; promote (10,4) RPC incl. placement solve p50 3 ms; index CPU 19 % under 240 heartbeats / 3 s; index RSS 725 MB

## Repair storm

- 100 × 16 MiB objects at (10,4) policy `None` promoted in 5.3 s (302.4 MB/s aggregate)
- placement spread: 236 of 240 sites hold fragments; max 14 objects on any one site (mean 5.93); largest single agent share 0.093
- killed 2 agents = **40 sites lost** (17 % of the federation at once), detected in 16.1 s; fragments lost per object mean 2.18 max 7 (hist {'0': 8, '1': 27, '2': 28, '3': 23, '4': 7, '5': 5, '6': 1, '7': 1})
- 85 objects DEGRADED and repairable; **7 beyond m=4 (LOST, by design unrecoverable without the sites returning)**
- every repairable object DURABLE again in **27.2 s** (3.13 objects/s), healed=True
- control-plane RPC p99: baseline 0.5 ms → during storm 0.5 ms; index CPU after 253.85999999999999 %

## Survivability policies (per data domain) — single-region fabric

9/9 profiles behaved as specified

| profile | policy | (k,m) | expected | result | placement satisfied | pass |
|---|---|---|---|---|---|---|
| site-distinct-default | `{"domain": "site"}` | (3,2) | accept | 10 encoding | True | True |
| agent-distinct | `{"domain": "agent"}` | (3,2) | accept | 10 encoding | True | True |
| agent-distinct-unsatisfiable | `{"domain": "agent"}` | (12,2) | refuse | 7 survivability policy not satisfiable: n=14 distinct agent do |  | True |
| allowed-sites-only | `{"allowed_sites": ["site-000", "site-001", "site-002", "site-003", "site-004", "site-005"]}` | (3,2) | accept | 10 encoding | True | True |
| allowed-sites-too-few | `{"allowed_sites": ["site-000", "site-001", "site-002"]}` | (3,2) | refuse | 7 survivability policy not satisfiable: n=5 distinct site doma |  | True |
| denied-sites | `{"denied_sites": ["site-000", "site-001", "site-002", "site-003", "site-004", "site-005", "site-006", "site-007", "site-008", "site-009"]}` | (3,2) | accept | 10 encoding | True | True |
| jurisdiction-KY | `{"allowed_state_codes": ["KY"]}` | (3,2) | accept | 10 encoding | True | True |
| jurisdiction-unsatisfiable | `{"allowed_state_codes": ["ZZ"]}` | (3,2) | refuse | 7 survivability policy not satisfiable: n=5 distinct site doma |  | True |
| dataset-default (4,3) agent-distinct | `{}` | (,) | accept | 10 encoding | True | True |

## Survivability policies (per data domain) — multi-region fabric

12/12 profiles behaved as specified

| profile | policy | (k,m) | expected | result | placement satisfied | pass |
|---|---|---|---|---|---|---|
| site-distinct-default | `{"domain": "site"}` | (3,2) | accept | 10 encoding | True | True |
| agent-distinct | `{"domain": "agent"}` | (3,2) | accept | 10 encoding | True | True |
| agent-distinct-unsatisfiable | `{"domain": "agent"}` | (9,2) | refuse | 7 survivability policy not satisfiable: n=11 distinct agent do |  | True |
| region-distinct | `{"domain": "region"}` | (3,2) | accept | 10 encoding | True | True |
| min-regions-4 | `{"domain": "site", "min_regions": 4}` | (3,2) | accept | 10 encoding | True | True |
| region-distinct-unsatisfiable | `{"domain": "region"}` | (8,2) | refuse | 7 survivability policy not satisfiable: n=10 distinct region d |  | True |
| allowed-sites-only | `{"allowed_sites": ["site-000", "site-001", "site-002", "site-003", "site-004", "site-005"]}` | (3,2) | accept | 10 encoding | True | True |
| allowed-sites-too-few | `{"allowed_sites": ["site-000", "site-001", "site-002"]}` | (3,2) | refuse | 7 survivability policy not satisfiable: n=5 distinct site doma |  | True |
| denied-sites | `{"denied_sites": ["site-000", "site-001", "site-002", "site-003", "site-004", "site-005", "site-006", "site-007", "site-008", "site-009"]}` | (3,2) | accept | 10 encoding | True | True |
| jurisdiction-KY | `{"allowed_state_codes": ["KY"]}` | (3,2) | accept | 10 encoding | True | True |
| jurisdiction-unsatisfiable | `{"allowed_state_codes": ["ZZ"]}` | (3,2) | refuse | 7 survivability policy not satisfiable: n=5 distinct site doma |  | True |
| dataset-default (4,3) agent-distinct | `{}` | (,) | accept | 10 encoding | True | True |

## Passive-failure tolerance — single-region fabric

- encode under loss: 12 × 64 MiB promotes started, holder agent `n12` killed at 0.4 s (8 objects had a fragment planned there): **12/12 completed** in 22.3 s with 44 fallback placements; 5 DURABLE
- restore with a dead holder: 5/5 verified restores, [8.67, 0.51, 4.61, 0.51, 0.51] s each (raced fetch)
- victim back in 10.2 s; all objects DURABLE 10.2 s after return

## Passive-failure tolerance — multi-region fabric

- encode under loss: 12 × 64 MiB promotes started, holder agent `rctl-08` killed at 0.4 s (10 objects had a fragment planned there): **12/12 completed** in 39.8 s with 67 fallback placements; 5 DURABLE
- restore with a dead holder: 5/5 verified restores, [4.6, 0.51, 0.51, 0.51, 4.6] s each (raced fetch)
- victim back in 10.2 s; all objects DURABLE 10.2 s after return

## Java client access path (clientlib, verified stream, 256 MiB × 5)

| condition | ok/reps | MB/s min | median | max | re-fetched chunks |
|---|---|---|---|---|---|
| quiet fabric | 5/5 | 32.1 | 393.2 | 413.0 | 363 |
| during the 20-min soak with random kills | 5/5 | 28.8 | 395.3 | 409.6 | 554 |

## Repeatability (3 runs)

| metric | mean | stdev | min | max | CV % |
|---|---|---|---|---|---|
| push_256K_x8_MBps | 425.95 | 12.65 | 417.58 | 440.51 | 3.0 |
| push_512K_x32_MBps | 563.53 | 34.55 | 532.34 | 600.68 | 6.1 |
| get_256K_x8_MBps | 377.97 | 15.36 | 361.46 | 391.85 | 4.1 |
| rpc_p99_ms | 0.38 | 0.04 | 0.35 | 0.42 | 11.2 |
| encode_64MiB_MBps | 263.05 | 3.79 | 259.11 | 266.67 | 1.4 |
| restore_64MiB_MBps | 309.09 | 13.84 | 299.07 | 324.87 | 4.5 |
| repair_64MiB_s | 0.59 | 0.01 | 0.59 | 0.6 | 1.0 |
| encode_256MiB_MBps | 266.45 | 7.81 | 259.63 | 274.97 | 2.9 |
| restore_256MiB_MBps | 295.7 | 13.78 | 281.63 | 309.18 | 4.7 |
| repair_256MiB_s | 2.14 | 0.01 | 2.13 | 2.14 | 0.3 |
| encode_1024MiB_MBps | 267.03 | 4.98 | 263.99 | 272.78 | 1.9 |
| restore_1024MiB_MBps | 292.16 | 18.77 | 270.54 | 304.4 | 6.4 |
| repair_1024MiB_s | 9.35 | 2.42 | 7.94 | 12.15 | 25.9 |
| listnodes_p50_ms | 2.24 | 0.04 | 2.21 | 2.28 | 1.6 |

## Failure benchmarks (agent-distinct placement unless noted)

| scenario | result |
|---|---|
| F1_repairer_dies_mid_repair | {"holder_killed": "n12", "repairer_killed": "n01", "healed": true, "heal_s": 77.9, "final_repairer": "global-region:n02:gfs-site-020", "repairer_changed": true, "restore_after": true} |
| F2_source_dies_mid_repair | {"killed": ["n01", "n11"], "healed": true, "heal_s": 32.5} |
| F3_corrupt_fragment_served | {"fragments_corrupted": 86, "restore_verified": true, "restore_s": 0.55, "scrub_reported_bad": 7297, "index_frags_marked_bad_delta": 86, "marked_BAD_by_scrub": true, "index_BAD_state_observed": true, "repaired": true} |
| F4_custody | {"key_id": "kek-pub-site-3e3652", "t": 3, "n": 5, "holders_dead_first": 2, "holders_alive_first": 3, "reconstruct_with_t_alive_ok": true, "detail_first": "restored", "holders_dead_second": 5, "holders_alive_second": 0, "below_t_fails_closed": true, "detail_second": "IllegalStateException: only 0 of  |
| F5_index_restart | {"journal_entries": 834, "files": 409, "objects_before": 4, "wsapi_back_s": 9.9, "index_answering_s": 9.9, "all_nodes_reregistered_s": 34.0, "state_hash_preserved": true, "full_hash_preserved": false, "replica_hash_equal": true, "promote_restore_after": true, "agents_stuck_in_connection_fault_after_ |
| F6_publisher_restart | {"back_s": 0.1, "dataset_online": true, "restore_after": true, "fetch_after": true} |
| F7_beyond_m_then_return | {"agents_killed": ["n08", "n09", "n10", "n11", "n12"], "states_after_loss": {"LOST": 9, "DURABLE": 1}, "restore_of_LOST_object_fails_closed": true, "lost_restore_detail": "IllegalStateException: stripe 0: only 9 of 10 fragments reachable", "all_durable_after_return": true, "recover_s": 0.0} |
| F8_mixed_load_storm | {"agents_killed": ["n11", "n12"], "promotes": 16, "ok": 16, "failed": 0, "promote_p50_s": 1.01, "promote_p99_s": 10.09, "objects": 16, "all_repaired": true, "storm_window_s": 60.7} |

## Global-controller restart × 3 — agent reconnection with NO manual agent restart (W-GFS-6 fix)

- 12 agents / 240 storage nodes; **all agents back on every run = True** (agents not back: []); slowest full re-registration 44.2 s; slowest agent lost→recovered (from agent logs) 3.6 s
- `STUCK IN CONNECTION FAULT` log lines across all agents and runs: **0**; promote+restore after every restart = True

| run | wsapi back (s) | index answering (s) | all agents back (s) | max lost→recovered (s) | STUCK lines | msgIn held / dropped | post restore ok |
|---|---|---|---|---|---|---|---|
| 1 | 9.9 | 9.9 | 32.1 | 3.1 | 0 | 0 / 0 | True (0.51 s) |
| 2 | 7.9 | 7.9 | 44.2 | 3.6 | 0 | 1 / 0 | True (0.53 s) |
| 3 | 9.9 | 10.0 | 44.2 | 3.6 | 0 | 0 / 0 | True (0.53 s) |

## Cresco-side fixes proven on this build (W-GFS-4 stable plugin identity, W-GFS-5 advertised broker ports)

- **W-GFS-4:** storage plugin deployed on `n12` WITHOUT a pinned id (agent minted `plugin-d02be080-3eef-4240-bb50-5203c7a96f88`); JVM killed and restarted (pid 49868 → 50345, restarted=True); node left UP on kill=True; **same node id back UP after restart = True** in 17.2 s; new ids that appeared: []
- **W-GFS-5:** 8 regional controllers on one host, each with its own broker port, bridged to the global; 150 s settle window after deploy: **`Controller Path Lost` events = 0**, broker-monitor connect failures = 0, bridges started = 64, global sees 8 of 8 regions (the pre-fix campaign logged 191 path-lost events per region)

## Soak (20 min, random agent kill every ~90 s, restart after 30 s)

- ops {'promote': 195, 'fetch': 94, 'restore': 195, 'kills': 13, 'restarts': 12}; objects 195; **error rate 0.0**; all DURABLE at end = True
- throughput p50/min/max: {'promote_MBps': {'p50': 3.5, 'min': 0.3, 'max': 24.4}, 'fetch_MBps': {'p50': 7.0, 'min': 0.8, 'max': 49.6}, 'restore_MBps': {'p50': 30.8, 'min': 0.3, 'max': 118.5}}
- RSS: index 944.15625 → 993.453125 MB, publisher 672.15625 → 785.5 MB
- errors (first): []

## Multi-region topology (every site = its own regional controller + broker, bridged to the global)

- 9 regions × 8 storage instances = 72 sites; deploy 12.2 s; all registered in 3.0 s
- cross-region fragment push peak 576 MB/s (512 KiB × 8), get peak 648 MB/s; RPC p99 idle 2.3505 ms → under flood 0.709667 ms
- client fetch 256 MiB across the bridge (verified stream): 129.7 MB/s, sha ok=True, {'rounds': 1, 'refetched_chunks': 0, 'corrupt_chunks': 0, 'missing_chunks': 0, 'verified': True}

| object | (k,m) | block | encode MB/s | restore MB/s | restore ok | detect+repair s | repaired |
|---|---|---|---|---|---|---|---|
| 16 MiB | (3,2) | 512 KiB | 57.8 | 262.3 | True | 0.55 | True |
| 16 MiB | (5,2) | 512 KiB | 1.5 | 124.0 | True | 31.74 | True |
| 256 MiB | (3,2) | 512 KiB | 21.4 | 208.1 | True | 2.62 | True |
| 256 MiB | (5,2) | 512 KiB | 141.4 | 183.8 | True | 2.2 | True |

- storm at (5,2) policy `{"domain":"region"}`: 60 objects, 1 region(s) killed = 8 sites; detected 16.1 s; 49 degraded, 0 beyond m; healed=True in 12.2 s; RPC p99 baseline 1.1 → storm 3.6 ms; spread max 56 objects/site over 8 sites
