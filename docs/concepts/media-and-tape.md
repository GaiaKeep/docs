# Media and tape

> "Tape is just one option of many, it is just a block of data."

Tape is one binding among several. It is the extreme case that keeps the abstraction honest:
designing for it surfaced properties that disk alone would never have forced into the model (setup
cost per access, retention enforced by the medium, ordering, the quality of fault evidence). Every
other medium now gets those for free.

## LTO-10 facts that drive the design

| Fact | Value | Basis |
|---|---|---|
| Native capacity, standard LA cartridge | 30 TB | Vendor |
| Native capacity, enhanced PA cartridge | up to 40 TB | Vendor; confirm the *guaranteed* figure for the exact part number |
| Full-height drive rate | 400 MB/s | Vendor |
| Half-height drive rate | 300 MB/s | Derived from Spectra's 32.4 TB/hr for 30 half-height drives |
| Hardware compression | Disabled | We write ciphertext, which does not compress |

All capacities and rates are decimal. An earlier MiB/TiB mix-up overstated rates by 4.9 % and
cartridges by 10 %; it has been corrected in the models.

## The mount cycle

Getting to the first byte on a cartridge that isn't loaded costs four terms, not one:

| Step | Time |
|---|---|
| Robot fetch and insert | ~15 s |
| Load, thread, calibrate | 60–120 s |
| Locate to the first target | 20–90 s |
| *(transfer)* | |
| **Rewind to the beginning of tape**, mandatory before eject | 50–90 s |
| Unload, eject, robot return | ~40 s |

The non-transfer total is **295–355 s** (planning figure 265 s). This is **Modelled, not measured**,
and it is the most consequential unmeasured constant in the design: a 45 % error in it moves
delivered throughput by about 23 %. The rewind term is the one every early model left out.

## Capacity and throughput are different quantities

**Capacity** is how much a library holds: slots × cartridge capacity. **Throughput** is how much
flows through its drives per year. Throughput depends heavily on how data is laid out, because a
drive spends most of its time mounting, rewinding and repositioning:

| Workload | Payload fraction of drive time | Delivered, 9-drive 3-site plant |
|---|---:|---:|
| Scattered reads | ~8 % | 8.9 PB/yr |
| Hot | ~17 % | 18.1 PB/yr |
| Clustered (data read together is stored together) | ~39 % | 40.4 PB/yr |

These figures are **Modelled** by simulation with an error bar of about ±23 %. The arithmetic
ceiling of 96–101 PB/yr assumed an 85 % duty cycle and has been retired. Two things follow:

- **Clustering at write time is worth 4.55×.** Adding drives is worth exactly their number, and
  the benefit stops at the robot. A single accessor saturates at around **14 drives per site** on
  scattered work.
- **Media wear** can bind before drive time does. Cartridges are rated for about 20,000
  load/unload cycles; that figure is an industry round number and needs vendor confirmation. With
  a short batching window, scattered workloads wore cartridges out early. The fix is admission
  control on the batching window, **Built** (`PlantScheduler.admit`). At petabyte scale the problem
  largely disappears, because more cartridges share the same number of mounts: 100 PB of clustered
  data uses about 4.8 % of the ten-year rating.

## What a tape library provides

Raw tape and an embedded management controller: the LumOS REST API, media and drive health
databases (MLM/DLM), and partitioning. **No general-purpose compute, and no file or object
interface.** Bytes move over SCSI to a drive. Every site therefore needs its own host to run the
Cresco agent, the storage software and the spool. Spectra's gateway product (BlackPearl) was
rejected, because it brings its own object model on top of the one this system provides.

## Software: why Bareos is out

**Decided 2026-09-20 on licence grounds.** Bareos is AGPLv3: 979 of 350,751 lines of its core
carry the Affero header, and only two carry LGPL. Plugins, subclasses, vendoring and patching are
all forbidden to a permissively licensed system. The only clean integration drives it at arm's
length, which forces **every byte through a staging area**. The documented way to stream at full
speed without staging is a plugin, and a plugin is exactly the linking case. Streaming is the
point of this system, so that is disqualifying.

**The replacement** drives the Linux `st` and `sg` drivers directly through `ioctl`, and a
syscall boundary doesn't make the program a derivative of the kernel. From Java that means JDK 22+
(Foreign Function & Memory API), JNA, or a small separate C helper; see
[Open questions](../roadmap/open-questions.md) B2.

**The real cost:** Bareos's tools could read a cartridge without our software. Without them, the
on-media format is a one-way door with no fallback, and **an independent reference reader** that
works with no index, no catalogue and no running system becomes a blocking deliverable.

## Other decisions

- **No LTFS and no filesystem on tape**: the system manages its own blocks.
- **Write-once (WORM) media is per cohort**, not required everywhere. See
  [Deletion, retention and repack](deletion-and-repack.md).
- **The Hugging Face Hub protocol cannot represent offline data.** Measured: a file that is sealed
  or offline comes back to the official client as the same "not found in cache" error whether the
  server answers 404, 403 or 503. The system therefore has its own protocol and does not aim for
  Hub client compatibility.
