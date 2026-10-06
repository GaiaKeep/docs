# Benchmarks

The measurements behind release 1.3. **HPC** means the multi-host runs on the HPC cluster: 4 nodes,
the secured build, signed requests and strict node-key pinning. **In-process** means a single JVM on
one Mac, which is useful for comparing before and after, not as absolute numbers. Raw results are
under `eval/results/` in the repository.

## Transport foundation (HPC)

The first multi-host run found the transport, not the storage engine, was the bottleneck. These
fixes came first:
- the broker's socket buffers now use kernel autotuning;
- the broker's TLS transport was fixed;
- more send lanes;
- storage-node traffic moved to windowed, acknowledged streams;
- QoS per traffic class.

| Measure | Before | Shipped build |
|---|---|---|
| Storage-node stream, 1 flow, 4 MiB frames | 62–82 MB/s | 699–776 MB/s |
| Storage-node streams, 4 flows | collapsed | 2,147–2,437 MB/s |
| Storage-node streams, 8 flows | collapsed | 2,152–2,424 MB/s |
| Fetch from one site, 4 flows, 1 MiB frames | | 2,416 MB/s |
| Retransmits | | 0 |
| Control-plane p99 under full storage-node load | | 16 ms |
| Control-plane p99 during an 8 GB, 3-copy ingest | | 34.5 ms (max 52 ms) |

**Signing, per-stream MACs and integrity digests** cost storage nodes 0.6–0.9 extra CPU-seconds per
GB, with no measurable throughput loss: it was within the run-to-run spread. Before the security
layer was merged, one flow measured 802 MB/s through the hub and 1,208 MB/s over the dynamic mesh's
direct agent-to-agent links; 4 flows measured 2.3 GB/s and 3.1 GB/s.

## Ingest (HPC)

Ingest is a striped multi-part upload over 8 flows, with a short commit, at R=3 (three copies on
three sites).

| Size | Ingest | Read back (byte-identical) | Longest single request |
|---|---|---|---|
| 2 GB | 133 MB/s | 300 MB/s | ≤ 18 s |
| 8 GB | 146–148 MB/s | 289–304 MB/s | 18.0 s |
| 16 GB | 159 MB/s | 284 MB/s | ≤ 18 s |

**Before 1.3,** an 8 GB publish was one synchronous request that took 28–37 s. Now no request runs
past 20 s. The 8 GB run on the shipped build used two core peers, with no leader change during the
ingest.

## Replication topology

**Chain replication:** the writer sends each block once, and every hop forwards it with a signed
receipt. **Star:** the writer sends every copy itself.

| Setting, R=3 | Star | Chain | Chain / star |
|---|---|---|---|
| HPC, through the hub | 234 MB/s | 254 MB/s | 1.09× |
| HPC, dynamic mesh | 245 MB/s | 261 MB/s | 1.06× |
| In-process, no network limit | 140 MB/s | 258 MB/s | 1.84× |
| In-process, 1,000 MB/s network per host | 290 MB/s | 720 MB/s | 2.48× |
| In-process, 400 MB/s network per host | 126 MB/s | 264 MB/s | 2.10× |
| In-process, 3 regions, one shared 125 MB/s uplink each | 56 MB/s | 114 MB/s | 2.04× |
| In-process, 3 regions, one 125 MB/s link per region pair | 112 MB/s | 141 MB/s | 1.26× |

- **The writer's egress** is 1× the data with chain, against 3× with star.
- **On the HPC cluster the gain is small** because publishing there is limited by the engine, not by the
  network: R=1 publishes at the same 250–270 MB/s. Chain is the default for publishes of 8 MiB or
  more.

**Hashing once per hop** sped up the storage-node paths (in-process):

| Path | Before | After |
|---|---|---|
| Fetch, 1 flow | 2.3 GB/s | 20.0 GB/s |
| Fetch, 4 flows | 8.8 GB/s | 31.5 GB/s |
| Write, 1 flow | 6.9 GB/s | 11.7 GB/s |

## Format-aware deduplication

These numbers come from measurements on real de-identified imaging. Only counts and sizes left the
cluster; no images did.

| Change to the file | Plain 1 MiB content-defined chunking | With the format adapter |
|---|---|---|
| DICOM de-identification, new data per instance | 470 KB | 4.0 KB |
| Whole-slide image description edit | 2.87 MB | 1.1 KB |
| NIfTI header edit | 2.10 MB | 352 B |

**Have-check:** the client works out which blocks the core already holds before it uploads.

| Re-upload | Bytes sent |
|---|---|
| 1,000 real de-identified DICOM instances (542 MB), HPC, with the format adapter | 4,257 B per instance: **0.79 %** |
| The same, with plain 1 MiB chunking | 503,277 B per instance: 92.8 % |
| Unchanged re-upload | 0 |
| 32 synthetic CT instances (16.8 MB), in-process | 26,720 B: 0.16 %, 601× less than plain chunking |

**Client-side cutting:**

| Measure | Pure Python | Native fast path |
|---|---|---|
| Content-defined chunking loop | 14.4 MB/s | 1,877 MB/s |
| Whole cut (read, format cut, chunk, block and file hashes) | 4.4 MB/s | 701.5 MB/s |

A 2 GiB file is cut at 644 MB/s, with a peak memory of 142 MiB. The fast path and the pure-Python
path give identical cuts on 84 conformance cases and 1,200 fuzzed inputs.

Within a single imaging corpus, deduplication across different studies is about zero at every block
size. The win is in edits and re-uploads of the same data.

## Transport robustness (in-process)

| Defect fixed | Before | After |
|---|---|---|
| Acknowledgement traffic after one lost frame (32 MiB of 4 KiB extents) | 6.0× the data | 0.002× |
| Download state, 64 GiB file in 4 KiB chunks | 197 MB of heap | 17 KB |
| Upload verification blocking the stream listener (256 MiB upload) | 3.4 s stall | 0 ms |
| Java client upload sender state, 8 flows of maximum parts | 1.5 GiB | 420 KiB |

## Storage-node pack containers (in-process, 4 KiB extents)

| Measure | One file per extent | Pack containers |
|---|---|---|
| Publish, 100,000 extents | 571 extents/s | 4,585 extents/s (8×) |
| Random verified read, 100,000 extents | 3,673 /s | 7,308 /s (2×) |
| Start-up, 100,000 extents | 1.74 s | 0.35 s |
| Random verified read, 1,000,000 extents | 1,322 /s | 156,011 /s |
| Start-up, 1,000,000 extents | 509 s | 0.84 s |
| Files on disk, 1,000,000 extents | 2,000,000 | 8 |

## Tape (simulated)

The simulator models an LTO-9-class drive: 15 s load, locate time by distance, 400 MB/s streaming
with speed matching, and a shoe-shine penalty. **mhVTL** provides virtual drives driven through the
real Linux tape device path.

| Measure | Simulator (modelled time) | mhVTL (measured) |
|---|---|---|
| Archive, 1 drive | 23.3 MB/s (46.2 without the first mount) | 21.1 MB/s |
| Archive, 2 drives | 46.5 MB/s | 40.0 MB/s |
| Recall first byte, p50: cold / already mounted | 28.9 s / 3.1 s | 4.3 s / 3.2 s |
| Recalls per hour, mixed with archiving | 325, 0 failed | 1,875, 0 failed |
| Speed-up from batching recalls | 3.2× | 1.5× |
| Shoe-shining on our spool-fed writes | none: streaming at 395 MB/s | not modelled |

- **These archive rates use small 256 MiB test containers.** Each container pays a fixed stop at its
  synchronous filemark, which is several times the time spent streaming it. Larger containers raise the rate;
  see the next table.
- **A writer that underfeeds the drive** shoe-shines: in the simulator, 50 MB/s gave 3 stops per
  512 MiB.

### Read-back after writing

By default every container written to tape is read back and checked before its copies count. Since
2026-10-01 this is a setting:
- **full** reads back every container (the default);
- **sampled** reads back the first container of each session, then 1 in 10;
- **none** reads back no container.

A container that is not read back is still checked when its data is read later, so a bad record is
never returned to a reader; it is only found later. Its copies are reported as unverified.

| Containers | Full | Sampled | None | None vs full |
|---|---|---|---|---|
| Simulator, 256 MiB | 39.2 MB/s | 41.8 MB/s | 41.9 MB/s | 1.07x |
| Simulator, 1 GiB | 87.6 MB/s | 123.6 MB/s | 129.0 MB/s | 1.47x |
| Simulator, 16 GiB (fitted from the two sizes, not run) | 143.5 MB/s | 319.5 MB/s | 370.2 MB/s | 2.58x |
| mhVTL, 256 MiB (measured) | 286.5 MB/s | 512.3 MB/s | 565.2 MB/s | 2.0x |
| mhVTL, 1 GiB (measured) | 281.7 MB/s | 440.0 MB/s | 508.8 MB/s | 1.8x |

- **On the simulator,** read-back matters little at 256 MiB, because the fixed stop per container
  dominates. At the 16 GiB production size it is most of a container's drive time.
- **mhVTL has no tape mechanics,** so its gap is the cost of our own checking code. That code first ran at
  150–240 MB/s on the test VM (full: 111.9 and 163.2 MB/s), below an LTO-10 drive's 400 MB/s. It now checks
  the data as it reads and checks the container structure in parallel, at about 630 MB/s: on real hardware
  the drive, not our code, sets the pace.
- **In every run,** each recalled byte matched, and nothing was written anywhere but the end of the data.

## Wide-area links (emulated)

These runs use 5 sites in one VM with netem latency and loss, a striped ingest, and comparison
against a LAN reference measured in each run.

| Round-trip time | Result |
|---|---|
| 0.2 ms | passes at every loss level |
| 4 ms | passes up to 1 % loss |
| 30 ms | **passes at every loss level** with BBR congestion control: goodput 0.63–1.15 of LAN |
| 80 ms | ingest holds 0.55–0.67 of LAN; range reads 0.25–0.57; fails at 1 % loss |

- **Host congestion control matters most.** At 1 % loss and 40 ms one way, one TCP connection
  carried 37 MB/s with BBR and 0.5 MB/s with CUBIC. Hosts on WAN links should run BBR.
- **Inbound sharding helps.** Spreading an agent's inbound dataplane over 5 shards raised
  storage-node throughput into the core at 80 ms from 60 to 160 MB/s.
- **Long-RTT reads are open work:** reads over links of 80 ms and more still need deeper read-ahead,
  or reads spread across replicas.

## Framework (Cresco)

| Measure | Result |
|---|---|
| Message delivery, 2 nodes, 40 cold-start runs | 800/800 every run, 0 drops |
| Tunnel integrity, 32 MiB, SHA-256 checked, under load | previous jar: 4/5 intact, and 0/5 with a late target. New: 5/5 and 5/5 |
| Speed suite under heavy load (load average 88–204) | 10/10 runs pass |
