!!! success "Status: Current"
    The LTO-class tape simulator and mhVTL test setup behind the tape benchmarks.

# Tape on simulated devices: the in-JVM simulator, mhVTL, and the tape benchmark

Owner direction 2026-09-30: benchmark and test the tape path end to end on simulated tape devices. Two
kinds exist, and they answer different questions:

| | In-JVM simulator (`io.cresco.gfs.tape.sim`) | mhVTL (`eval/tape/mhvtl`, Lima VM `gfs-tape`) |
|---|---|---|
| What it is | cartridges as directories, drives and a robot with an LTO-9-class time model | the Linux virtual tape library: real `/dev/nst*`, `/dev/sg*`, a SCSI medium changer |
| Exercises | the binding, the catalogue, the crash rules, faults, **mechanics** (mount, locate, rewind, streaming, shoe-shining) | the **real device path**: st writes and reads, mt positioning, mtx for the robot, raw SCSI (READ POSITION, LOG SENSE, MAM, SECURITY PROTOCOL IN) through this node's own command set over `sg_raw` |
| Timing | modelled (SIMULATED), deterministic, run on a scaled clock | real wall time, but mhVTL has **no mechanical model** (no load, locate or streaming delays) |
| Where | every JUnit run, the bench on any host | the Lima VM only (test infrastructure; GPL; never in the code or its dependencies) |

## 1. The simulator's model (defaults, `tape_sim_profile=lto9`)

Every figure is configurable (`tape_sim_*`, below) and none is a measurement.

| Figure | Default | Config key |
|---|---|---|
| Robot move, slot to drive and back | 8 s each way | `tape_sim_robot_ms` |
| Load to ready | 15 s | `tape_sim_load_ms` |
| Unload | 15 s | `tape_sim_unload_ms` |
| Rewind | 3 s + 94 s x the distance from BOT (97 s from the end) | `tape_sim_rewind_max_ms` |
| Locate | 2 s settle + 100 s x the fraction of the tape travelled (a full-length locate about 102 s) | `tape_sim_locate_full_pass_ms`, `tape_sim_locate_settle_ms` |
| Read retry reposition | 5 s | `tape_sim_reposition_ms` |
| Native streaming | 400 MB/s | `tape_sim_stream_bytes_per_sec` |
| Speed matching floor | 177 MB/s | `tape_sim_min_stream_bytes_per_sec` |
| Drive buffer | 1 GiB | `tape_sim_buffer_bytes` |
| Backhitch (one buffer underrun, or a restart after a synchronous filemark) | 3 s | `tape_sim_backhitch_ms` |
| First byte at mid-tape (robot + load + locate) | about 75 s | derived |
| Whole mount cycle at mid-tape | about 148 s | derived |

`tape_sim_profile=simplant` restores the tape spec's M1 figures (robot 15 s, load 90 s, a 172 s full pass at
0.6, rewind 50-90 s, unload 25 s, reposition 40 s: first byte about 157 s, cycle about 265 s). A simulated
node's descriptor figures (first byte p50/p95, cycle, stream rate, reposition) follow its profile unless
`tape_first_byte_*` etc. are set, with basis SIMULATED.

**Streaming and shoe-shining.** The tape runs at the host's feed rate clamped to [177, 400] MB/s (speed
matching). Records arrive into the buffer; the host waits only while the buffer is full. A record that
arrives after the buffer drained finds the tape stopped: it costs a 3 s backhitch before streaming resumes.
A writer below 177 MB/s therefore stops the tape again and again (shoe-shining): its drive-time streaming
rate collapses toward the feed and the drive's repositions (wear) grow. A synchronous filemark (immed=0, the
binding's per-container durability barrier) stops the tape too: the next write pays one backhitch (counted
as a sync stop, not a shoe-shine). Arrival times are the host's wall clock by default; a benchmark can feed
a synthetic timeline (`SimDrive.arrivals`) to model a host of any rate deterministically.

**The library.** N drives (`tape_sim_drives`, 2), M slots (`tape_sim_slots`, 16) and cartridges
(`tape_sim_cartridges`, 8; `tape_sim_worm_cartridges`; `tape_sim_capacity_bytes`, 64 GiB), one robot whose
moves are charged to the drive they serve. Time runs `SCALED` (sleeps the modelled time divided by
`tape_sim_time_scale`, paced by debt so sub-millisecond operations are not rounded up) or `INSTANT` (no sleep;
the modelled time is only accounted). Cartridges are directories, so a simulated host restart keeps them.

**Faults** (`SimFaults`, each consumed as it fires): medium error at (cartridge, lbn); deferred write error at
the next synchronous filemark; short write; silent corruption on write (any byte of a record); silent
corruption of a stored record; unit attention and position lost; drive fault and cleaning required (next
command); **a drive that dies after N records** (its buffer is lost, every command then fails with HARDWARE
ERROR, the cartridge stays in it until the robot pulls it); early warning at a chosen byte count; end of
medium; WORM overwrite; a foreign cartridge; a MAM epoch bumped by "another host"; power cut (every drive
buffer dropped).

## 2. mhVTL (the real device path)

`eval/tape/mhvtl/README.md` has the VM (Lima `gfs-tape`, Ubuntu 24.04 aarch64, kernel 6.8), the mhVTL commit,
the emulated library (STK L700 + two IBM ULT3580-TD9 = LTO-9 drives, cartridges GFS000L9..GFS007L9 of 4 GiB),
what was verified, and what does not work (mhVTL keeps a 512 KiB transfer cap unless built with the flag
setup.sh passes; no mechanical timing; no real encryption). `setup.sh` installs and configures it
idempotently; `fresh-media.sh` recreates blank cartridges and waits (restarting mhVTL up to three times) until
both drives are registered again; `run-bench.sh` runs the bench. Devices are named by unit serial
(`tape_st_drives=sn=GFSDRV11:auto,sn=GFSDRV12:auto`, `tape_st_changer=sn=GFSLIB10`) and resolved in sysfs
(VPD page 80h) at each start: after an mhVTL restart the /dev numbers change and udev's by-id links were seen
to come back incomplete.

The binding reaches mhVTL through `core_store_binding=tape-st` (dev mode only; test infrastructure):
`StTapeDrive` (records on the no-rewind st node, mt for positioning, and this node's own SCSI command set
over `sg_raw` for READ POSITION, LOG SENSE 31h, MAM and SECURITY PROTOCOL IN) and `MtxChanger`. What st
imposes and how it is absorbed is in docs/TAPE-FORMAT.md §6.

## 3. The benchmark (`TapeBench`, JSON into eval/results/bench/, gated by eval/bench_gate.py)

```
# the simulator (any host), about 10-15 min at the default 20x clock:
java -cp "target/classes:target/test-classes:$(cat target/cp.txt)" io.cresco.gfs.tape.bench.TapeBench --backend sim
# mhVTL, inside the VM:
limactl shell gfs-tape bash -lc 'cd <worktree> && bash eval/tape/mhvtl/run-bench.sh'
python3 eval/bench_gate.py eval/results/bench/tape-<backend>-<date>.json
```

Sections: archive throughput (one write session = one drive, then a session per drive: containers are spooled
first and released together, so the drives are measured, not this host's pace of producing data; on the
simulator per-drive and aggregate rates are the drives' modelled busy time, with and without the one-off robot
and mount); recall latency, first byte and full, from a cold library and with the cartridge mounted (model time
on the simulator: exact); batching (one ticket for many extents across cartridges, against one ticket each);
recalls per hour under a mixed workload (four closed-loop readers while a writer archives, one modelled hour
on the scaled clock); shoe-shining (the binding's own spool-fed writes, and a synthetic writer fed at 600,
250, 150, 50 and 20 MB/s). Every recalled extent is checked byte for byte. `bench_gate.py` fails a run on any
wrong byte, a write anywhere but EOD, a batching speedup below 1, a failed mixed recall, (simulator) a spool-fed
binding streaming under the drive's 177 MB/s floor or with more than one backhitch per GiB, (simulator) a
mounted recall not faster than a cold one, or a large drop against a baseline. (The binding feeds the drive
from its local spool as fast as the spool reads: the spool disk must read faster than the drive's
speed-matching floor, or the drive shoe-shines. A run on a loaded host showed it: one backhitch, streaming
held at 249 MB/s.)

The campaign's tier T6 runs all of it: `T6.junit.tape`, `T6.bench.sim` (env junit) and `T6.bench.mhvtl`
(env lima-tape, `--allow-vm`).

## 4. Results (2026-09-30, this Mac: Apple Silicon; the VM gfs-tape for mhVTL)

### 4.1 Simulator (eval/results/bench/tape-sim-2026-09-30.json; SIMULATED, LTO-9-class model, clock 20x)

| Measure | Result | Basis |
|---|---|---|
| Archive, one write session (one drive), 1 GiB in 4 containers of 256 MiB | 23.3 MB/s effective; 46.2 MB/s leaving out the one-off robot + mount (23 s); tape streaming 384 MB/s | drive busy time (model) |
| Archive, a session per drive (2), 2 GiB | 46.5 MB/s aggregate (2 x 23-24); 91.6 MB/s steady state; each drive streamed 394-396 MB/s, split 1050 / 1119 MB | drive busy time (model) |
| Recall, cold library (4 extents, cartridges in slots) | first byte p50 28.9 s (p90 29.3 s); full p50 31.4 s | model, the busiest drive |
| Recall, cartridge mounted | first byte p50 3.1 s (p90 3.2 s); full p50 8.0 s | model |
| Batching, 24 extents on 2 cartridges | one ticket 36.0 s (2 mounts, 7 locates) against one ticket each 114.3 s (2 mounts, 24 locates): **3.2x** | model |
| Recalls per hour, 4 readers + an archiving writer (1.3 GB archived meanwhile), 2 drives | 325 per hour, 0 failed or wrong; latency p50 6.7 s, p90 19.0 s | scaled clock (host overhead included; varied 192-490 with host load) |
| Shoe-shining, the binding (spool-fed, 2 GiB) | 0 underruns, streaming 394.9 MB/s | model |
| Shoe-shining, a synthetic writer at 600 / 250 / 150 / 50 / 20 MB/s (512 MiB) | 0 / 0 / 1 / 3 / 8 underruns; tape streaming 399 / 250 / 89 / 45 / 20 MB/s | model |

Reading the archive rows: a session pays one robot + mount (23 s), and at 256 MiB containers the fixed
cost of each container (the synchronous filemark, and under FULL the LOCATE back for the read-back) is
several times its 0.64 s of streaming: the steady state here is about 47 MB/s per drive. Two sessions double
the aggregate: the drives are independent. For larger containers and the three `tape_write_verify` modes, see
§4.3: the model's own fit gives 143.5 MB/s per drive with FULL at 16 GiB containers (an earlier hand estimate
here said about 190), because the LOCATE back before each read-back grows with the container's length.

### 4.2 mhVTL (eval/results/bench/tape-mhvtl-2026-09-30.json; MEASURED on the VM, no mechanical model)

| Measure | Result |
|---|---|
| Archive, one write session, 512 MiB (3 containers) | 21.1 MB/s, including the FULL read-back verify of every container, over st/mt/mtx and sg_raw |
| Archive, a session per drive (2), 1 GiB (5 containers) | 40.0 MB/s aggregate (the two drives in parallel) |
| Recall, cold (robot move by mtx, load, label check, locate by mt, 4 extents of 8 MiB) | first byte p50 4.3 s (p90 7.4 s); full p50 11.0 s |
| Recall, cartridge mounted | first byte p50 3.2 s (p90 4.4 s); full p50 13.3 s |
| Batching, 24 extents on 2 cartridges | one ticket 55.4 s against one ticket each 82.0 s: **1.5x** (2 mounts either way) |
| Recalls per hour, 4 readers + an archiving writer (302 MB archived meanwhile) | 1,875 per hour, 0 failed or wrong; latency p50 6.8 s, p90 14.2 s |

What these measure: the software path and the Linux device stack against a library that answers at once.
Every positioning step is a process (mt, mtx, sg_raw) of tens of milliseconds, which dominates the small-data
rows; mhVTL itself streams 190-310 MB/s with dd (eval/tape/mhvtl/README.md). A mounted recall is not faster
than a cold one here because mhVTL has no load or robot time to save; the simulator carries that difference
(3.1 s against 28.9 s).

Every recalled extent in both runs matched byte for byte; no write went anywhere but the medium's EOD.

### 4.3 Write verify: FULL, SAMPLED, NONE (2026-10-01; `TapeBench --verify-sweep`)

`tape_write_verify` (owner decision 2026-10-01: an option, default FULL) chooses which containers are read
back after they are written: FULL every one; SAMPLED the first of each session and then 1 in
`tape_write_verify_sample_every` (10); NONE none. One write session on one drive, fresh media for every phase;
afterwards extents from the first and last containers are recalled and compared byte for byte, SYNCED copies
included. Every phase: bytes verified, no write anywhere but EOD.

Simulator (eval/results/bench/tape-verify-sim-2026-10-01.json; SIMULATED, LTO-9-class model, clock 1x and 20x
give the same figures: drive busy time is the model's):

| Containers | FULL | SAMPLED | NONE | NONE / FULL |
|---|---|---|---|---|
| 256 MiB x 10 | 39.2 MB/s (steady 59.7) | 41.8 (66.0) | 41.9 (66.2) | 1.07x |
| 1 GiB x 10 | 87.6 (108.0) | 123.6 (168.5) | 129.0 (178.6) | 1.47x |
| 16 GiB, fitted (not run) | 143.5 | 319.5 | 370.2 | 2.58x |

The fit is a straight line through the two sizes' steady-state seconds per container (FULL: 2.6 s fixed and
7.3 s per GiB; NONE: 3.3 s and 2.7 s per GiB). At 256 MiB the read-back barely matters: a container not
read back pays a backhitch after its synchronous filemark instead (3 s), while under FULL the read and the
LOCATE stop the tape anyway. At production sizes the read-back is most of a container's drive time.

mhVTL (eval/results/bench/tape-verify-mhvtl-2026-10-01.json; MEASURED wall clock on the VM, no mechanical model):

| Containers | FULL | SAMPLED | NONE | NONE / FULL |
|---|---|---|---|---|
| 256 MiB x 10 | 111.9 MB/s | 409.1 | 505.2 | 4.5x |
| 1 GiB x 6 (two cartridges: early warning at 4 GiB) | 163.2 | 299.6 (2 read back: one per session) | 501.1 | 3.1x |

mhVTL has no tape mechanics, so its gap was our own software: the read-back copied the container to a scratch
file and read that again for the pack check, about 150-240 MB/s on this 4-vCPU VM, slower than an LTO-10 drive
streams (400 MB/s). Fixed the same day: the records stream into SHA-384 as they are read, and the pack check
runs on the spool (proved byte-identical by that digest) while the medium is read
(eval/results/bench/tape-verify-mhvtl-2026-10-01-overlap.json):

| Containers | FULL before | FULL now | SAMPLED | NONE | NONE / FULL now |
|---|---|---|---|---|---|
| 256 MiB x 10 | 111.9 MB/s | 286.5 | 512.3 | 565.2 | 2.0x |
| 1 GiB x 6 | 163.2 | 281.7 | 440.0 | 508.8 | 1.8x |

The read-back now checks at about 630 MB/s on the VM (1 GiB: 6.4 GB in 10 s more than NONE), above what the
drive streams: on real hardware the drive, not the verify code, sets FULL's pace.
