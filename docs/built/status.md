# Status at a glance

Every component is labelled **Proven**, **Built**, **Designed**, **Proposed** or **Open**; the
[home page](../index.md) defines them. Updated **2026-10-01**, after [release 1.3](release-1-3.md):
`GaiaKeep/gfs` `1.3` at `8461e1a`, with CI green on 2,188 core tests. The [live tier](#live-tier) and
[core stability](#core-stability) sections are updated to **2026-10-28**: that work is on the development
branch, not yet merged or released. Details are in [Test results](tests.md) and [Benchmarks](benchmarks.md).

!!! success "Release 1.3: the durable storage core, validated on the HPC cluster"
    The secured build passes the live fabric check **88/88** on the HPC cluster. That build has
    signed requests, strict node-key pinning and sealed keys. An 8 GB ingest at three copies runs at
    146 MB/s and reads back at 289 MB/s, byte-identical. No request takes more than 20 s. A
    de-identified DICOM re-upload sends 0.79 % of its bytes.

## Foundation

| Component | Status | Evidence |
|---|---|---|
| Cresco mesh transport, identity, tenant isolation | **Proven** | Cresco 1.3 |
| Dataplane for data, MsgEvent for control, QoS per traffic class | **Proven** | HPC: 0.7 GB/s per flow, 2.1–2.4 GB/s on 4–8 flows, control p99 16 ms under load |
| Framework fixes: no silent message loss, tunnel integrity, secret redaction | **Proven**, shipped in CrescoEdge 1.3 | 40/40 loss-proof runs; 10/10 tunnel integrity runs |
| Replicated core: Raft log, lease, pre-vote, snapshots, non-voter catch-up | **Proven** | 112 tests, power-cut campaigns, failover in the HPC cluster fabric check |

## Durable storage

| Component | Status | Evidence / note |
|---|---|---|
| Storage engine: versions, branches, dedup domains, repair, scrub, trim, reclaim | **Proven** | 508 engine tests, model-based testing, crash matrix |
| Ingest: striped parts, then a short idempotent commit; resumable uploads | **Proven** | HPC 2–16 GB ingest, every request ≤ 18 s |
| Async jobs with signed events on the dataplane | **Built** and tested | job failover and idempotency tests |
| Chain replication with signed per-hop receipts | **Proven** | HPC: chain ≥ star on hub and mesh; chaos test 1,118 publishes clean |
| Follower reads with read-your-writes | **Built** and tested | follower-read and partition tests; both clients (Python and Java) |
| Blocks of at least 1 MiB; chunker and policy per dataset; named profiles | **Proven** | |
| Format-aware dedup (DICOM, NIfTI, TIFF) with client-side have-check | **Proven** | real data on the HPC cluster: 0.79 % of bytes sent on re-upload |
| Pack containers on storage nodes | **Built** and measured | 8× publish, sub-second start-up at 10⁶ extents; 1,500-round power-cut campaign |
| Scrub by container: each sealed container verified whole in one sequential read, rate-limited and resumable; the core's content check answered from a fresh pass | **Built** and tested | a damaged container is named, and its bad copies are still found and repaired one by one |
| Lifecycle: forget, prune, destroy, retention, legal hold | **Built** and tested | 70 lifecycle tests |
| Erasure coding reached by repack | **Designed** | |

## Placement and media

| Component | Status | Evidence / note |
|---|---|---|
| Placement from measured write rate; fail-closed durability barrier | **Built**, on the live path | |
| Tape software path: deferred reads with tickets, archive, stage, verify | **Built** and tested on simulated drives | simulator and mhVTL virtual drives, end to end through the core; read-back after writing is a setting (full, sampled or none), benchmarked |
| Tape operations: cartridges disabled, exported, imported; a stuck cartridge's hold released; TapeAlert and encryption checked at every mount | **Built** and tested on simulated drives | lessons from CERN's tape archive (CTA) |
| Recall order from an LTO locate-cost model (CERN's measured model) | **Built**; measured on the simulator only | 31 % less simulated drive time for a recall across wraps; real drives need the end-of-wrap query, so they keep ascending order until tested on hardware |
| Raw SCSI tape on a real drive | **Designed** | needs hardware |
| Mount cycle measured on a real drive | **Open**, blocking before media | |

## Security

| Component | Status | Evidence / note |
|---|---|---|
| Signed requests (ECDSA P-384), tenant-scoped roles, tamper-evident audit | **Proven** | HPC fabric check, all requests signed |
| Key custody: file, environment, PKCS#11; master-key rotation window | **Built** and tested | 86 key-custody tests |
| Signed, encrypted storage-node traffic; pinned node keys; term fencing | **Proven** | HPC with strict pinning |
| Client transfer key exchange bound to the request | **Proven** | conformance in Java and Python |
| Metadata encryption: sealed partitions, keyed ids, sealed snapshots | **Built** and tested | |
| Adversarial reviews of the merged code | Done twice | every finding reproduced, fixed and regression-tested |

## Hardware

| Item | Status |
|---|---|
| Tape library: Spectra Stack first, Cube later | **Decided** (owner) |
| Sites: three, 3-way replication | **Decided** (owner, sites chosen later) |
| WAN hosts: BBR congestion control | **Recommended** (measured: 37 vs 0.5 MB/s at 1 % loss) |
| LTO-10 media | **Decided** (owner, 2026-10-01: LTO-10 only, no older media) |
| Per-site hosts | **Proposed** |

## Live tier

The caching tier of earlier plans, built as [the live tier](../concepts/live-tier.md). Development branch,
2026-10-28; the final-build runs of the E18 gate and the 72-hour soak are **in progress**.

| Component | Status | Evidence / note |
|---|---|---|
| Journaled inventory of live copies; the feature gate; guards that keep live copies from ever counting | **Built** and tested | inventory, gate and never-counted tests; about 250 live-tier unit and cluster tests in CI |
| `realise`, `prospect`, holds (lease, extend, pin), drops, admissions | **Proven** on the HPC test bed | end-to-end checks 14 PASS, 0 FAIL, 1 SKIP (build `88f086d6`, 2026-10-28) |
| No early copy, the writer included | **Proven** on the HPC test bed | no row and no file while the version was committing (14 looks), then the committed bytes |
| Sealed node streams (AES-256-GCM); nothing in plaintext over a broker | **Built** and tested | wire-confinement test captures every frame and message |
| Deletion reaches every live copy and ends on a signed attestation | **Proven** for a withdrawal on the HPC test bed; FORGET tested on a local fabric | a FORGET converged in 11 s with its path in no live copy and no audit record (local, 2026-10-28); FORGET on the test bed waits for an eligible second approver |
| Inventory matches the disk; reconciliation, orphans, adoption after a leader change | **Built** and tested | invariant I1 after every chaos cycle and every model step |
| Crash recovery at the six live-tier crash points | **Proven** on an HPC validation deployment | 6/6 cells, 8/8 checks each, recovered in 34–69 s with no operator action (2026-10-28) |
| Workspaces published as new versions (`core.livepublish`) | **Built** and tested | publish tests; cost follows the changed files |
| Live host checks; filerepo's guard verb | **Proven** on the HPC test bed | check g: host checks ok, link protection attested, evidence re-gathered on the node |
| Clients: Java, Python, command line, MCP; local copies first | **Built** and tested | conformance vectors both clients and the core check |
| filerepo as a client of the live node | **Proven** on the HPC test bed | live-backed repository reports `LIVE`, refuses serving and files under the live root |
| Model-based test of the live tier and the core (LT-M1) | **Built**, in every CI run | 24 seeds × 100 steps per run; a 300 × 200 nightly as a batch job on the cluster, submitted by hand so far |
| Realise throughput | **Built**; measured, and open work | 84.5 MB/s on 1 flow, 192–206 MB/s on 4 flows, well below the node leg; see [Benchmarks](benchmarks.md#live-tier-realise-hpc-2026-10-28) |
| The test deployment's live node | **Built**, test configuration only | it runs shared-user (compute jobs run as the agent's user) and reports itself as not production |

## Core stability

Development branch, 2026-10-28. See [Stops, restarts and slow disks](../concepts/stops-and-restarts.md).

| Component | Status | Evidence / note |
|---|---|---|
| A slow disk never costs the leadership; disk work off the raft lock's hot paths | **Built** and tested | follower stalls of 2.8–17.7 s caused no election (local fabric, E18 LT-C2) |
| A cap on the unsynced backlog (64 MiB); a stuck disk hands over only to peers shown healthy | **Built** and tested | raft stall tests; ordered waiting proposals |
| A planned stop hands over and fails no client call; `outcome_unknown`; safe resends | **Built** and tested | 10 planned stops, 0 failed calls, hand-over 0.726–0.740 s (local fabric, E18 LT-C3, 2026-10-28); HPC test bed in progress |
| The process exits on SIGTERM; the stop is bounded; a new instance never shares the old one's files | **Built** and tested | processes out by themselves in 3.34–3.86 s (was killed at 60 s) |
| A write survives a store restarted under it (rolling upgrade) | **Built** and tested | store-restart tests; HPC test bed in progress |
| A signed, boot-fenced departure notice from a stopping store | **Built** and tested | an earlier boot's notice, delayed or replayed, is ignored |
| Memory pressure beside a core | **Built** and tested | a 768 MiB hog for 31–86 s caused no election (local fabric, E18 LT-C4) |
| The 72-hour soak (E18 LT-S1) | **Open**: in progress | a 58-minute local mini-soak held every invariant but missed the canary criterion once (a tape commit past 180 s) |

## Continuous integration

CI runs on the HPC cluster as batch jobs, never on GitHub Actions (owner decision 2026-10-02): every head of
`main` and `1.3` is tested and the result posted as a commit status. Since 2026-10-25 `main` is the development
branch and `1.3` moves only by fast-forward to a `main` commit whose CI passed. CI on the live tier's merged
tree (its first four milestones) ran green with 3,052 tests on 2026-10-28. See [Running the tests](harnesses.md#continuous-integration).
