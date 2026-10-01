# Status at a glance

Every component is labelled **Proven**, **Built**, **Designed**, **Proposed** or **Open**; the
[home page](../index.md) defines them. Updated **2026-10-01**, after [release 1.3](release-1-3.md):
`GaiaKeep/gfs` `1.3` at `8461e1a`, with CI green on 2,188 core tests. Details are in
[Test results](tests.md) and [Benchmarks](benchmarks.md).

!!! success "Release 1.3: the durable storage core, validated on the DGX"
    The secured build passes the live fabric check **88/88** on the DGX cluster. That build has
    signed requests, strict node-key pinning and sealed keys. An 8 GB ingest at three copies runs at
    146 MB/s and reads back at 289 MB/s, byte-identical. No request takes more than 20 s. A
    de-identified DICOM re-upload sends 0.79 % of its bytes.

## Foundation

| Component | Status | Evidence |
|---|---|---|
| Cresco mesh transport, identity, tenant isolation | **Proven** | Cresco 1.3 |
| Dataplane for data, MsgEvent for control, QoS per traffic class | **Proven** | DGX: 0.7 GB/s per flow, 2.1–2.4 GB/s on 4–8 flows, control p99 16 ms under load |
| Framework fixes: no silent message loss, tunnel integrity, secret redaction | **Proven**, shipped in CrescoEdge 1.3 | 40/40 loss-proof runs; 10/10 tunnel integrity runs |
| Replicated core: Raft log, lease, pre-vote, snapshots, non-voter catch-up | **Proven** | 112 tests, power-cut campaigns, failover in the DGX fabric check |

## Durable storage

| Component | Status | Evidence / note |
|---|---|---|
| Storage engine: versions, branches, dedup domains, repair, scrub, trim, reclaim | **Proven** | 508 engine tests, model-based testing, crash matrix |
| Ingest: striped parts, then a short idempotent commit; resumable uploads | **Proven** | DGX 2–16 GB ingest, every request ≤ 18 s |
| Async jobs with signed events on the dataplane | **Built** and tested | job failover and idempotency tests |
| Chain replication with signed per-hop receipts | **Proven** | DGX: chain ≥ star on hub and mesh; chaos test 1,118 publishes clean |
| Follower reads with read-your-writes | **Built** and tested | follower-read and partition tests |
| Blocks of at least 1 MiB; chunker and policy per dataset; named profiles | **Proven** | |
| Format-aware dedup (DICOM, NIfTI, TIFF) with client-side have-check | **Proven** | real data on the DGX: 0.79 % of bytes sent on re-upload |
| Pack containers on storage nodes | **Built** and measured | 8× publish, sub-second start-up at 10⁶ extents; 1,500-round power-cut campaign |
| Lifecycle: forget, prune, destroy, retention, legal hold | **Built** and tested | 70 lifecycle tests |
| Erasure coding reached by repack | **Designed** | |

## Placement and media

| Component | Status | Evidence / note |
|---|---|---|
| Placement from measured write rate; fail-closed durability barrier | **Built**, on the live path | |
| Tape software path: deferred reads with tickets, archive, stage, verify | **Built** and tested on simulated drives | simulator and mhVTL virtual drives, end to end through the core |
| Raw SCSI tape on a real drive | **Designed** | needs hardware |
| Mount cycle measured on a real drive | **Open**, blocking before media | |

## Security

| Component | Status | Evidence / note |
|---|---|---|
| Signed requests (ECDSA P-384), tenant-scoped roles, tamper-evident audit | **Proven** | DGX fabric check, all requests signed |
| Key custody: file, environment, PKCS#11; master-key rotation window | **Built** and tested | 86 key-custody tests |
| Signed, encrypted storage-node traffic; pinned node keys; term fencing | **Proven** | DGX with strict pinning |
| Client transfer key exchange bound to the request | **Proven** | conformance in Java and Python |
| Metadata encryption: sealed partitions, keyed ids, sealed snapshots | **Built** and tested | |
| Adversarial reviews of the merged code | Done twice | every finding reproduced, fixed and regression-tested |

## Hardware

| Item | Status |
|---|---|
| Tape library: Spectra Stack first, Cube later | **Decided** (owner) |
| Sites: three, 3-way replication | **Decided** (owner, sites chosen later) |
| WAN hosts: BBR congestion control | **Recommended** (measured: 37 vs 0.5 MB/s at 1 % loss) |
| LTO-10 media, per-site hosts | **Proposed** |

## Caching tier

| Item | Status |
|---|---|
| Advanced caching tier | **Designed**, deliberately **after** durable storage; see [The caching tier](../roadmap/caching-tier.md) |
