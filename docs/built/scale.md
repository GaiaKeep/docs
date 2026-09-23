# Scale results

Generated 2026-09-18 from the scale campaigns. **One host** (14-core Apple silicon, 36 GB), all
nodes on loopback: these are compute, broker and protocol ceilings, not wide-area figures. Full
tables are in [SCALE-RESULTS.md](../design/SCALE-RESULTS.md).

## Headline

| Area | Result |
|---|---|
| Federation size | **240 sites** on one host; solving placement and promoting takes 3 ms; the index uses 19 % of one core under heartbeats |
| Index | **1,000,000 files** ingested at **143,444 files/s**; 1,811 MB heap; resolve p99 **0.4 ms** at 5,398 resolves/s; replica converged with an identical hash |
| Durability data path | Encode **233–291 MB/s**, restore **254–393 MB/s** for 256 MiB–1 GiB objects; every restore hash-verified |
| Loss detection and repair | Every lost holder found by audit in **< 122 ms** and regenerated without keys |
| Transport | Fragment push peaks at **577 MB/s** node to node; client fetch 143.7 MB/s |
| Isolation | Control-plane RPC p99 **0.72 ms** while a 444 MB/s fragment flood runs |
| Storm | **40 of 240 sites** lost at once → 85 objects repaired in **27.2 s**; 7 objects beyond the code's tolerance reported, not hidden; control p99 0.5 ms during the storm |
| Multi-region | 72 sites across 8 bridged regions |

## Codec, with no fabric

| Operation | Rate |
|---|---|
| Reed–Solomon (10,4), 14 threads | 3,872 MB/s encode |
| Reed–Solomon (10,4), one thread | 423–425 MB/s |
| AES-256-GCM decrypt | ~3,400 MB/s per thread; 24,232 MB/s encrypt on 14 threads |
| SHA-256 | 2,318.9 MB/s |
| Shamir split / combine (n=9, t=5) | 60 µs / 6 µs |

## Durability data path by object size

Representative rows (full grid in the design record):

| Object | Code | Encode MB/s | Restore MB/s | Detect + repair |
|---|---|---:|---:|---:|
| 64 MiB | (10,4) | 245.2 | 242.4 | 1.07 s |
| 256 MiB | (3,2) | 278.3 | 392.6 | 2.11 s |
| 1 GiB | (10,4) | 270.8 | 253.5 | 7.99 s |

## Index scale

| Files | Ingest files/s | Heap MB | Resolve p50 / p99 ms | Replica equal |
|---:|---:|---:|---|---|
| 100,000 | 123,736 | 138 | 0.4 / 0.8 | yes |
| 250,000 | 142,501 | 304 | 0.2 / 0.4 | yes |
| 1,000,000 | 143,444 | 1,811 | 0.4 p99 | yes |

The replica must be sized like the core: a 1 GB replica ran out of memory at 10⁶ files.
