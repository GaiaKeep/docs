!!! info "Status: Proven (prototype)"
    Every evaluation check with its method, pass criterion and status.

# Cresco GFS — Exhaustive Evaluation Plan

*Companion to `CORE-PRINCIPLES.md`. Each check has an id, a method, a pass criterion and a status:*
**RUN** = executed by `run/gfs/gfs_eval.py` on the local 8-node prototype fabric (results in
`run/gfs/results/`), **UNIT** = executed by the standalone codec self-test, **PLAN** = specified, needs
the next phase (multi-host mesh, tenant-namespaced fabric, identity provider, scale data), **INFRA** =
needs the pilot environment. Ids map to the harness sections (E1–E11) plus planned sections (E12–E16).

**Latest results (2026-09-17): functional suite 99/99 (run 5), codec self-test 23/23, and the scale
campaigns (240 sites on one host; 72 sites across 8 bridged regions; 10^6-file index) — see
`RESULTS.md` and `SCALE-RESULTS.md`. Rows marked RUN (SCALE) are executed by `run/gfs/gfs_scale.py`.**

## Methodology

- **Environment.** Local: 1 global (index core) + 7 site agents on one host (`launch_gfs_fabric.sh`),
  sites uky (publisher+storage, server-raid, 24 MiB pledge), uofl (clustered-fs), wku (server-raid),
  murray (desktop-single), eku (usb-single), nku (server-raid, also index replica), morehead
  (desktop-single), each 2 GiB pledge. Next: DGX 8-host mesh (region per site), then WAN emulation
  (`tc netem` latency/loss/bandwidth per site), then the BTSA nine-site pilot.
- **Harness.** Python (`gfs_client.py` over pycrescolib) drives every action through the same public
  Cresco message API a real client uses; Java internals are exercised only through the fabric. Kills
  and restarts use the launcher. Each check records PASS/FAIL + detail to JSON and Markdown.
- **Repeatability.** Fresh fabric per run (`up` wipes node state); deterministic test data (seeded);
  timing budgets are explicit per check; perf numbers are recorded, not asserted, except where a
  floor is stated.
- **Pass policy.** A section passes when every RUN check passes. Phase exit criteria are listed at
  the end.
- **Independence.** Where the harness verifies a cryptographic property it does so from *outside*
  the Java code (reading fragment files off disk, forging tokens, computing SHA-256 locally).

## E1 — Deployment and fabric integration
| id | check | method | pass | status |
|---|---|---|---|---|
| E1.1 | all agents join the global region | `get_agent_list` | 8 present | RUN |
| E1.2 | dataset staged | local files + sha256 | 8 files | RUN |
| E1.3 | bundle uploaded to every agent | `upload_plugin_agent` | is_updated on all | RUN |
| E1.4 | primary index deploys | `add_plugin_agent` roles=index | pluginid | RUN |
| E1.5 | replica index deploys | roles=index, primary=false | pluginid | RUN |
| E1.6 | filerepo on the publisher | configured scan_dir | pluginid | RUN |
| E1.7 | gfs node on all 7 sites | roles per site | 7 pluginids | RUN |
| E1.8 | index answers | `nodeinfo` | status 10 | RUN |
| E1.9 | capability inventory | `getcapabilities` | document returned | RUN |
| E1.10 | fail-closed start | deploy without `gfs_secret` / without `index_addr` | plugin refuses to start, logged | PLAN |
| E1.11 | OSGi reload | remove + re-add gfs instance 20× | no leaked threads/listeners (metrics) | PLAN |
| E1.12 | region-per-site topology | 7 regional controllers federated to a global | E2–E11 pass unchanged | PLAN (multi-host) |

## E2 — Node registry, liveness, probing, scoring
| id | check | method | pass | status |
|---|---|---|---|---|
| E2.1 | registration | `listnodes` | 7 UP | RUN |
| E2.2 | site/class recorded | compare config | equal | RUN |
| E2.3 | network probe | probe_mbps > 0 | all | RUN |
| E2.4 | class ordering of score | equal pledges, classes | clustered > server > desktop > usb | RUN |
| E2.5 | availability | ratio of heartbeats | > 0.8 | RUN |
| E2.6 | SUSPECT→LOST timing | kill node, sample states | LOST after lost_ms (+ sweep): 12–20 s measured | RUN |
| E2.7 | non-member site refused | register with site=foo | status 6 | PLAN |
| E2.8 | spoofed node id | message with forged src | ignored: identity from cert-bound src | PLAN (needs D4 signing) |
| E2.9 | availability decay | node down 50 % of window | availability ≈ 0.5, score halves | PLAN |
| E2.10 | probe under load | probe during a saturating restore | RTT within control-plane SLO (isolation) | PLAN |

## E3 — Publication and catalog consistency
| id | check | method | pass | status |
|---|---|---|---|---|
| E3.1 | dataset visible with all files | `listdatasets` | file_count = 8 | RUN |
| E3.2 | hashes equal local sha256 | `listfiles` | all equal | RUN |
| E3.3 | availability state per file | `listfiles` | ONLINE | RUN |
| E3.4 | non-owner cannot list raw index | `listfiles` as outsider | status 6 | RUN |
| E3.5 | non-admin cannot search | `search` | status 6 | RUN |
| E3.6 | admin search works | `search` | 5 hits | RUN |
| E3.7 | modify + add + delete propagate | edit files, poll | delta within 60 s | RUN |
| E3.8 | rename | rename a file | old rel deleted, new rel added, object STALE/ORPHANED handled | PLAN |
| E3.9 | nested dirs / unicode / long paths | fixtures | preserved | PLAN |
| E3.10 | large catalogs | 100k, 1M files | 10^6 files ingested at ~150k files/s (paged deltas of 2000); index heap 1.2–1.8 GB at 1.85 M files; real filerepo publication 50k files in 10 s | RUN (SCALE) |
| E3.11 | publisher restart | restart uky-pub | re-publish idempotent, seq continues, no duplicate rows | PLAN |
| E3.12 | index restart | restart global | journal replay = same state (statehash), publishers re-register | PLAN |
| E3.13 | stale/duplicate delta | replay old seq | ignored | PLAN |
| E3.14 | source changed after promote | edit promoted file | manifest → STALE, file object cleared | PLAN |
| E3.15 | source deleted after promote | delete promoted file | manifest → ORPHANED, ledger no longer charges | PLAN |

## E4 — Projects and the authorization matrix
| id | check | pass | status |
|---|---|---|---|
| E4.1 | owner creates project | ok | RUN |
| E4.2 | owner adds member | ok | RUN |
| E4.3 | owner adds project delegate | ok | RUN |
| E4.4 | outsider self-add | 6 | RUN |
| E4.5 | dataset owner commits files | ok ×3 | RUN |
| E4.6 | dataset delegate commits | ok | RUN |
| E4.7 | project member (not dataset delegate) commits | 6 | RUN |
| E4.8 | outsider commits | 6 | RUN |
| E4.9 | commit uncataloged path | 9 | RUN |
| E4.10 | member sees exactly committed files | 4 | RUN |
| E4.11 | outsider lists project | 6 | RUN |
| E4.12 | outsider's project list empty | [] | RUN |
| E4.13 | full matrix: {owner, project delegate, member, dataset delegate, admin, outsider} × {create, add member, add delegate, commit, uncommit, list, resolve, promote, getmanifest, delegate dataset} | table of expected statuses | PLAN (extend harness) |
| E4.14 | commit "*" (whole dataset) | all files visible; later-added files appear | PLAN |
| E4.15 | uncommit revokes | resolve → 6 after uncommit; outstanding grants expire | PLAN |
| E4.16 | dataset delegate removal | delegate can no longer commit | PLAN |

## E5 — Access path (routed to origin, enforced at origin)
| id | check | pass | status |
|---|---|---|---|
| E5.1 | member resolve → origin + grant | ok | RUN |
| E5.2 | 8 MiB fetch over dataplane, sha256 verified | equal; MB/s recorded | RUN |
| E5.3 | inline fetch of a small file | equal | RUN |
| E5.4 | outsider resolve | 6 | RUN |
| E5.5 | uncommitted file resolve | 6 | RUN |
| E5.6 | forged grant at origin | 6 | RUN |
| E5.7 | tampered claims at origin | 6 | RUN |
| E5.8 | expired grant at origin | 6 | RUN |
| E5.9 | garbage grant at origin | 6 | RUN |
| E5.10 | grant replay window | reuse within TTL allowed (documented); single-use option | PLAN |
| E5.17 | verified streaming | origin per-chunk SHA-256; missing/corrupt chunks re-requested by range | RUN (SCALE transport, both topologies) |
| E5.11 | grant for dataset A presented to publisher B | 6 | PLAN (second publisher) |
| E5.12 | byte-range fetch | start/len honoured | PLAN |
| E5.13 | 32 concurrent fetches | all verified; p99 latency | PLAN |
| E5.14 | 1 GiB fetch | streamed with bounded memory | PLAN |
| E5.15 | origin offline, DURABLE_ONLY | resolve reports DURABLE_ONLY; restore-through-read from a gateway | PLAN (Phase 5) |
| E5.16 | filerepo actions bypass | direct `streamfile`/`getfile` to the origin filerepo without a grant must be refused | PLAN (FR-D1 authz) |

## E6 — Durability tier correctness
| id | check | pass | status |
|---|---|---|---|
| U1 | RS(k,m) reconstructs from every ≤ m loss pattern for (3,2),(4,2),(10,4),(2,1) | 240 trials | UNIT |
| U2 | RS refuses k-1 shards | throws | UNIT |
| U3 | Shamir t-of-n recovers, t-1 does not | ok | UNIT |
| U4 | wrap/unwrap, wrong KEK fails, GCM tamper detected | ok | UNIT |
| U5 | token verify / forged / wrong secret | ok | UNIT |
| E6.1 | outsider cannot promote | 6 | RUN |
| E6.2 | owner promotes | ok | RUN |
| E6.3 | placement on 5 distinct non-origin sites | ok | RUN |
| E6.4 | encode job DONE | ok; MB/s recorded | RUN |
| E6.5 | DURABLE at index | ok; seconds recorded | RUN |
| E6.6 | 11 stripes × 5; overhead ≈ 1.67 | ok | RUN |
| E6.7 | every fragment present with manifest hash | all | RUN |
| E6.8 | fragments are ciphertext (entropy > 7.9) | all | RUN |
| E6.9/10 | plaintext marker absent from every holder's bytes | 0 hits | RUN |
| E6.11 | no KEK material on holders | none | RUN |
| E6.12 | restore at origin, sha256 equal, no decode needed | ok | RUN |
| E6.13 | holder with manifest access but no key cannot restore | FAILED "no key material" | RUN |
| E6.14 | manifest denied to outsider | 6 | RUN |
| E6.15 | AAD binding: swap two fragments between stripes/objects | decryption fails, restore FAILED | PLAN |
| E6.16 | IV uniqueness | assert nonce ‖ stripe unique per DEK across all objects | PLAN (static analysis + fuzz) |
| E6.17 | policy jurisdiction | `allowed_state_codes` honored; unsatisfiable refused with reason | RUN (SCALE policy) |
| E6.18 | capacity exhaustion | pledge too small → node excluded; store refuses beyond pledge | PLAN |
| E6.19 | promote of 0-byte and 1-byte files | manifest with one stripe; restore equal | PLAN |
| E6.20 | large object (4 GiB) | streaming encode, bounded memory, resumable | PLAN |
| E6.21 | k+m > available domains | refused with reason (site/agent/region domains, allow-lists) | RUN (SCALE policy) |
| E6.23 | survivability profiles | 12 profiles: domain=site/agent/region, min_regions, allow/deny sites, jurisdiction, dataset default | RUN (SCALE policy, 12/12 both topologies) |
| E6.22 | duplicate promote | refused "already durable" | PLAN |

## E7 — Failure injection and repair
| id | check | pass | status |
|---|---|---|---|
| E7.1 | pick 2 victims, 1 spare | ok | RUN |
| E7.2 | index marks LOST | seconds recorded | RUN |
| E7.3 | object DEGRADED | ok | RUN |
| E7.4 | restore with 2 sites down; RS decode on all stripes | sha256 equal | RUN |
| E7.5 | auto-repair re-places a lost index on the spare | ok; seconds recorded | RUN |
| E7.6 | 11 regenerated fragments present | ok | RUN |
| E7.7 | second lost index explicitly DEGRADED awaiting a site | reason contains "awaiting" | RUN |
| E7.8 | returning site → DURABLE again | ok | RUN |
| E7.9 | all UP | ok | RUN |
| E7.10 | > m losses | objects beyond m marked LOST explicitly (8/100 when 17 % of sites vanish at once) | RUN (SCALE storm) |
| E7.11 | loss during encode | holder killed mid-encode: every encode completes via fallback placement (12/12, 52–69 fallbacks), audited | RUN (SCALE tolerance) |
| E7.12 | restore with a dead holder | raced multi-round fetch completes and verifies (5/5) | RUN (SCALE tolerance) |
| E7.13 | index restart mid-repair | in-flight repair re-planned after replay | PLAN |
| E7.14 | repairer loss mid-repair | repair re-dispatched to another node; idempotent fragment ids | PLAN |
| E7.15 | network partition (bridge down) | SUSPECT not LOST until lost_ms; no repair storm; heals on reconnect | PLAN (multi-host) |
| E7.16 | repair storm | 40 of 240 sites lost at once: 83–88 objects repaired in 15–79 s, control p99 < 1 ms | RUN (SCALE storm) |
| E7.17 | orphan cleanup | fragments left on a returned site after re-placement are garbage-collected | PLAN |

## E8 — Integrity (scrub)
| id | check | pass | status |
|---|---|---|---|
| E8.1 | scrub detects corruption | bad id reported | RUN |
| E8.2 | index marks BAD → DEGRADED | ok | RUN |
| E8.3 | auto-repair in place → DURABLE | ok | RUN |
| E8.4 | on-disk fragment matches again | ok | RUN |
| E8.5 | fragment deleted outright (data + sidecar) | index-driven audit marks MISSING → repaired in place | RUN (E8.5/E8.6 + SCALE durability) |
| E8.6 | malicious holder returns garbage on getfragment | hash check rejects; restore uses another fragment | PLAN |
| E8.7 | periodic scrub cadence by class | usb scrubbed more often than clustered-fs | PLAN |
| E8.8 | scrub cost | 10 GiB store scrub time, IO throttled | PLAN |

## E9 — Key custody
| id | check | pass | status |
|---|---|---|---|
| E9.1 | KEK custodied t=3/n=5 | ok | RUN |
| E9.2 | holders on 5 distinct non-origin sites | ok | RUN |
| E9.3 | reconstruct refused with 0 approvals | 6 | RUN |
| E9.4 | non-approver cannot approve | 6 | RUN |
| E9.5 | first approval 1/2 | ok | RUN |
| E9.6 | refused below quorum | 6 | RUN |
| E9.7 | holder refuses share without valid authorization | 6 | RUN |
| E9.8 | quorum → token | ok | RUN |
| E9.9 | approvals consumed | 6 | RUN |
| E9.10 | KEK destroyed at origin | ok | RUN |
| E9.11 | restore without key fails closed | FAILED | RUN |
| E9.12 | restore at another site with token (3 of 5 shares) | sha256 equal | RUN |
| E9.13 | origin re-establishes KEK (persist) | ok | RUN |
| E9.14 | audit records approvals/issue/reads/denials | ok | RUN |
| E9.15 | t-1 holders online | reconstruction fails with count | PLAN |
| E9.16 | token expiry / wrong key id / wrong op | 6 | PLAN |
| E9.17 | key rotation | new KEK, new custody round, old objects still restorable | PLAN |
| E9.18 | approver signatures instead of index-minted token | holders verify approver keys | PLAN (Phase 2) |
| E9.19 | HSM-backed KEK | PKCS#11 provider | PLAN (Phase 6) |

## E10 — Reciprocity ledger
| id | check | pass | status |
|---|---|---|---|
| E10.1 | consumed = fragment bytes stored elsewhere | > 13 MB | RUN |
| E10.2 | holders' stored_for_others > 0 | ok | RUN |
| E10.3 | entitlement from formula | 15–22.6 MB | RUN |
| E10.4 | promote within entitlement | ok | RUN |
| E10.5 | promote beyond entitlement refused | 6 | RUN |
| E10.6 | headroom shrinks | ok | RUN |
| E10.7 | network factor capped | ≤ 1 | RUN |
| E10.8 | ledger after repair | consumed unchanged; stored moves from lost to new site | PLAN |
| E10.9 | ledger after delete/orphan | charge released | PLAN |
| E10.10 | false class claim | usb registered as clustered → scrub failures reduce effective score | PLAN |
| E10.11 | paid-in credits | manual credit entry → entitlement | PLAN |
| E10.12 | fairness across sites | no site can consume another's headroom | PLAN |

## E11 — Index consistency, replication, observability, regression
| id | check | pass | status |
|---|---|---|---|
| E11.1 | replica converges (seq) | equal | RUN |
| E11.2 | replica statehash equals primary | equal | RUN |
| E11.3 | MeasurementEngine gauges | present | RUN |
| E11.4 | audit retrievable | ok | RUN |
| E11.5 | filerepo functional regression | 10/10 | RUN |
| E11.6 | journal replay determinism | restart primary; statehash equal before/after | PLAN |
| E11.7 | replica promotion | kill primary; replica becomes primary; nodes re-home | PLAN (Phase 3) |
| E11.12 | replication at scale | replica converges at 10^6 files (hash equal, lag 8 s) when sized like the primary | RUN (SCALE index) |
| E11.8 | journal corruption | truncated last line tolerated; corrupted middle detected | PLAN |
| E11.9 | snapshot + compaction | state equal after compaction | PLAN |
| E11.10 | Raft ×4 | linearizable manifests under partition | PLAN (Phase 3) |
| E11.11 | health inventory | `gethealthinventory` shows gfs OK/WARN/CRITICAL correctly (kill index → WARN on nodes) | PLAN |

## E12 — Security and tenant isolation (zero trust)
| id | check | pass | status |
|---|---|---|---|
| E12.1 | site admission fail-closed | storage node refuses fragments/shares from a non-member owner site | PLAN (add to harness: second publisher with site=foo) |
| E12.2 | tenant-namespaced fabric | with `tenant_namespacing=true`, site tenants cannot reach each other's inboxes/topics except via the flow policy (W-GFS-1) | PLAN (Phase 1) |
| E12.3 | federation core tenant | core cannot read site dataplane topics beyond gfs sinks | PLAN |
| E12.4 | per-tenant QoS | one site's restore flood does not raise another site's control RTT beyond SLO | PLAN (W6) |
| E12.5 | message signing | forged src on `manifestput`/`catalogdelta` rejected by signature | PLAN (D4) |
| E12.6 | crypto inventory | static scan: only SHA-256/384, AES-GCM, HMAC-SHA-384, DRBG, RSA-3072/P-384 | PLAN (CI check) |
| E12.7 | secrets in logs | grep logs for KEK/DEK/share/grant material | none | PLAN |
| E12.8 | fuzz message params | malformed JSON/ids/sizes | no exceptions leak, statuses only | PLAN |
| E12.9 | data-at-rest on holders | fragments are ciphertext (E6.8) — and the index journal/manifests encrypted at rest | PLAN (SC-28) |
| E12.10 | filerepo direct access | origin filerepo refuses non-gfs callers | PLAN (FR-D1) |

## E13 — Performance and scale
| id | metric | method | target / record | status |
|---|---|---|---|---|
| E13.1 | encode MB/s vs block size (256K/512K), k/m (3,2 / 6,3 / 10,4), sizes 1 MiB–1 GiB | sweep | 210–300 MB/s at ≥ 64 MiB; codec ceiling 420–850 MB/s single thread | RUN (SCALE) |
| E13.2 | restore MB/s, all-data vs decode path | same | 280–530 MB/s; decode path 0.18 s per 8 MiB | RUN (SCALE) |
| E13.3 | fetch MB/s vs filerepo baseline (566 MB/s at 128 MiB) | 128 MiB | ≥ 80 % of baseline | PLAN |
| E13.4 | repair time per lost site for 1 GiB | | 205–410 fragments regenerated in 7.3–8.4 s | RUN (SCALE) |
| E13.5 | index op latency at 10^5, 10^6 files | listfiles/resolve p50/p99 | resolve p50 0.2 ms, p99 0.4 ms at 10^6; 6.6k resolves/s from 16 clients | RUN (SCALE) |
| E13.6 | delta throughput | 100k changed files | < 60 s to converge | PLAN |
| E13.7 | concurrent promotes | 8 × 64 MiB; 100 × 16 MiB | 250–330 MB/s aggregate; 100 objects DURABLE in 5 s | RUN (SCALE) |
| E13.8 | 64-node DGX mesh | E1–E11 | pass | PLAN |
| E13.9 | WAN emulation | 30 ms/50 ms/1 % loss per site | throughput model; repair completes | PLAN |
| E13.10 | control-plane isolation under bulk | RPC p99 during a 32-way 512 KiB flood | 1.1 ms at 539 MB/s (single broker); 4.2 ms across bridges at 377 MB/s | RUN (SCALE transport) |

## E14 — Operations
| id | check | status |
|---|---|---|
| E14.1 | Felix health for gfs per role (index seq, registered, store writable) | RUN (implicit) / PLAN (assert via `gethealthinventory`) |
| E14.2 | metric inventory across the mesh includes gfs gauges (per role: `gfs.index.*` on an index, `gfs.store.*` on a store) | RUN (D1: the dashboard detects the deployment and the index address from the inventory alone) |
| E14.7 | live storage monitoring: mesh dashboard Storage tab fed by `storagesummary` + the pushed `gfs_state` beacon | RUN (D1) |
| E14.3 | capability inventory lists gfs actions with params | RUN (E1.9) |
| E14.4 | ToS nag pipeline: downtime → notification → escalation → re-encode | PLAN (Phase 4) |
| E14.5 | operator runbooks: add site, retire site, rotate key, promote replica | PLAN |
| E14.6 | ledger statements per site per month | PLAN |

## E15 — Compliance traceability (NIST 800-53 rev5 / CMMC L2)
| control | GFS evidence | status |
|---|---|---|
| AC-3, AC-6 | project ACLs, owner/delegate checks, origin grant verification (E4, E5) | RUN |
| AC-4 | site admission + inter-tenant flow policy (E12.1–E12.3) | PLAN |
| AU-2/3/10/12 | audit journal of privileged actions (E9.14), signed events (D4) | RUN / PLAN |
| IA-2/3 | ORCID/InCommon identities, cert-bound nodes | PLAN |
| SC-8 | mTLS hops + dataplane frames hashed | RUN (hash) / PLAN (mTLS on) |
| SC-12/13 | AES-256-GCM, SHA-256/384, DRBG, Shamir custody (U1–U5, E6, E9) | RUN |
| SC-28 | fragments ciphertext at rest (E6.8); index/journal at rest | RUN / PLAN |
| SI-7 | scrub + hash verification on every fetch (E8) | RUN |
| CP-9/10 | restore drills incl. site loss and key loss (E7, E9) | RUN |

## E16 — Pilot readiness (BTSA, nine sites)
| id | check | status |
|---|---|---|
| E16.1 | DUA workflow: site onboarding → federation_members update → first publication | INFRA |
| E16.2 | InCommon login → project membership → fetch | INFRA |
| E16.3 | S3 gateway acceptance with a real tool (aws cli / boto3) against a project bucket | INFRA |
| E16.4 | quarterly restore drill from pledged capacity at two sites | INFRA |
| E16.5 | reciprocity statement accepted by site representatives | INFRA |


## E17 — Failure benchmarks, soak, repeatability, claims (executed by `gfs_failure.py` / `gfs_claims.py`)
| id | check | pass | status |
|---|---|---|---|
| F1 | repairer dies mid-repair | another node completes; object DURABLE | RUN |
| F2 | source holder dies mid-repair | repair completes from remaining sources | RUN |
| F3 | holder serves corrupt bytes | restore verifies via other fragments; scrub marks BAD; repaired | RUN |
| F4 | custody holders lost | reconstruct works with exactly t alive; fails closed below t | RUN |
| F5 | index primary restart | journal replay, all nodes re-register, state hash preserved, replica equal, promote/restore after | RUN |
| F6 | publisher restart | dataset online, sequence resynced, restore + fetch after | RUN |
| F7 | beyond-m loss then return | LOST explicit, restore fails closed, DURABLE after sites return | RUN |
| F8 | mixed load during a storm | ≥ 90 % promotes succeed, all repaired | RUN |
| F9 | global-controller restart ×3 (`globalrestart --runs 3`) | every agent re-registers on its own (no manual restart), zero `STUCK IN CONNECTION FAULT` lines, promote+restore work after each restart (W-GFS-6 fixed in the Cresco controller) | RUN |
| S1 | 20-min soak with random kills | error rate ≤ 5 %, all DURABLE at end, RSS < 2× | RUN |
| R1 | repeatability ×3 | throughput CV ≤ 25 % | RUN |
| J1 | Java clientlib verified fetch | 5/5 verified quiet and under soak load; median ≥ 200 MB/s quiet | RUN |
| C1 | claims registry | every documented claim PROVEN by executed evidence (`CLAIMS.md`) | RUN |
| I1 | plugin identity across an agent restart (W-GFS-4) | a plugin deployed without a pinned id comes back under the same id after a real JVM restart | RUN |
| B1 | same-host bridge stability (W-GFS-5) | 8 bridged regions on one host: zero `Controller Path Lost` events in a 150 s settle window | RUN |
| G1 | encode geometry (`gfs_encode_geometry_check.py`) | for 8+3, 6+3, 4+2 and 10+4: a file that is an EXACT multiple of k x block_size, and one byte either side, yields `ceil(size/(k*block))` stripes and restores with a verified SHA-256 (defect 19) | RUN |
| D1 | dashboard storage monitoring (`gfs_dashboard_check.py`) | GFS + index auto-detected from the metric inventory, every tab renders (playwright), an agent kill shows its stores LOST and objects not DURABLE on the dashboard within 40 s, all objects DURABLE again within 90 s, poll path healthy while the beacon feeds the UI | RUN |

**Executed 2026-09-18 on the final build** (`run_final_proof.sh`, `run_cresco_fix_proof.sh`, `run_failure_final.sh`):
F1–F9, S1 (0.0 % errors), R1, J1 (5/5 at 393–395 MB/s), I1 (same id back in 17.2 s), B1 (0 flaps), D1 (`run_dashboard_proof.sh`:
GFS + index auto-detected, not-DURABLE objects visible 16.2 s after the kill, 8 stores LOST at 26.2 s, all DURABLE again at 36.3 s,
8 tabs / 0 render errors), G1 (12/12 geometries complete and verified after defect 19 was fixed) and C1
(**59 of 59 claims proven**) all pass; functional E1–E11 99/99 on the same build.

## Phase exit criteria
- **Phase 0 (this prototype):** all RUN checks pass; perf recorded; codec UNIT tests pass.
- **Phase 1:** E12.1–E12.5 pass on a tenant-namespaced, mTLS-enabled multi-region fabric; E5.16/E12.10 pass.
- **Phase 3:** E11.6–E11.10 pass; E13.5 at 10^7 files.
- **Phase 4:** E6.20, E7.10–E7.17, E13.1–E13.4 at target sizes; LRC hierarchy evaluated against RS on WAN emulation.
- **Pilot:** E16 complete with signed drill reports.
