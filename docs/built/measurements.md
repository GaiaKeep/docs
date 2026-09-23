# Measurements

Each result is labelled **Measured** (from a run, with its artifact) or **Modelled** (derived by
simulation or arithmetic). Artifacts are in `GaiaKeep/gfs` under `eval/results/`.

## Storage behaviour

| Question | Result | Basis |
|---|---|---|
| What does the fsync barrier cost? | Linux node-local: 339 MiB/s with the barrier, 0.74 ms per 256 KiB fragment. macOS: ~8× slower (full flush) | Measured (DGX dgx-03, laptop); `fsync_cost.json` |
| Does storage location matter more than its declared class? | Shared project filesystem **8.1–8.8 MiB/s**, node-local **339 MiB/s**: a **40×** gap between identically described nodes | Measured; `fsync_cost.json` |
| Can timing show whether a barrier reaches storage? | Barrier cost ratio: node-local ×3.72, macOS ×17.97, shared filesystem ×0.94. It proves the barrier *works* in the first two; the shared filesystem can't be judged | Measured; `BarrierTest` |

## Deduplication and chunking

| Question | Result | Basis |
|---|---|---|
| Do successive model checkpoints share blocks? | **Zero** of 184,044 blocks of weights; optimizer state 0.002 % | Measured; `ckpt_dedup_results.json` |
| Do successive versions of a changing dataset share blocks? | 14.7–47.9 % of chunks shared between versions of a source tree | Measured; `cdc_measure.json` |
| Does content-defined chunking beat fixed blocks? | After an insert or prepend: **99.85 %** retained vs **0.1–50 %** for fixed blocks. Appends and overwrites: fixed does as well or slightly better | Measured; `cdc_largefile.json` |

!!! warning "Don't generalise from checkpoints"
    On September 19 the checkpoint result was used to drop deduplication entirely. That was the
    worst-case workload. Versioned datasets are the case that matters, and the owner has confirmed
    block-level deduplication is a requirement.

## Protocols

| Question | Result | Basis |
|---|---|---|
| Can the Hugging Face Hub client work with offline or sealed data? | No. Whether the server answers 404, 403 or 503 (with Retry-After), the client reports the same "not in local cache" error | Measured; `eval/hf_gateway.py` |

## Tape

| Question | Result | Basis |
|---|---|---|
| Mount cycle | 295–355 s non-transfer (four terms, including rewind to start) | **Modelled**; needs a real drive |
| Delivered throughput, 9-drive 3-site plant | 8.9 / 18.1 / 40.4 PB/yr (scattered / hot / clustered), about ±23 % | Modelled; `plant_contention.json` |
| Share of drive time spent moving data | 8.5 % scattered, 17.4 % hot, 38.8 % clustered | Modelled; `plant_sim.json` |
| Sustainable over ten years of media life | 6.4–40.4 PB/yr: load-cycle wear caps scattered workloads below the drive-time figure | Modelled |
| Media wear at petabyte scale | 100 PB clustered: ~4.8 % of the ten-year load-cycle rating | Modelled; `media_life.json` |
| Robot limit | A single accessor saturates at ~14 drives per site on scattered work | Modelled |
| Moving 3 PB from replication to erasure coding | 5,556 drive-hours, ~19 days on 12 drives | Modelled |

## panAtlas

| Question | Result | Basis |
|---|---|---|
| How big is the panAtlas index estate? | 198.04 GB over 200,497,968 documents (988 B/document); 11.24 GB source records, 186.80 GB derived | Measured on the DGX, 2026-09-19 |
| What does it cost to bring back from tape? | One mount plus 495 s of transfer, **13.2–14.2 min** | Modelled; `IndexResidency` |

## Codec throughput (single host)

SHA-256 2,318.9 MB/s; AES-GCM decrypt ~3,411 MB/s per thread; Reed–Solomon (10,4) 423 MB/s on one
thread and 3,872 MB/s on 14. See [Scale results](scale.md).

## Still unmeasured, and what each blocks

| Measurement | Blocks |
|---|---|
| The mount cycle, as a distribution, on a real drive | Every tape throughput figure; the media purchase |
| LTO-10 minimum streaming speed before the drive stalls and repositions ("shoe-shining") | Spool size |
| Whether a drive can usefully skip dead regions | The repack cost model (3.77× apart) |
| The real size of the imaging estate (~1.55 PB, from slides) | Sizing: 92.6 % of the basis |
| Consent-withdrawal rate | Repack and retention planning |
| A real request log | Co-occurrence clustering |
| Power-loss test on site hosts | Proof that data survives power loss |
| Recompute cost of panAtlas derived data | Withdrawal by recomputation |
