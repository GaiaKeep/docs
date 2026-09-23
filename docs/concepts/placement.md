# Placement and loci

A **locus** is any place a copy of a block can live: a RAM arena, an NVMe device, a disk shelf, a
tape library, a shared filesystem. The placement engine decides which loci receive which copies.
The owner's rule is that **the medium does not matter** to callers or to policy. What matters is a
set of measured properties.

## One interface for every medium

Every locus implements `ExtentBinding`. Its omissions are deliberate:

- **No synchronous read that returns bytes.** A synchronous read is possible on disk and impossible
  on tape, so the interface doesn't offer one. Reads are planned and then delivered.
- **No `delete`.** Removal goes through `reclaim`, which refuses while a retention floor stands.
- **No `list` or scan.** The catalogue lives in the index, not in the medium.
- **Two-stage writes.** `append` produces a provisional reference; `seal` makes it durable.

| Piece | Status |
|---|---|
| `ExtentBinding` interface, `LocusDescriptor` | **Built** |
| `FsBinding` (filesystem) with retention floors that survive restarts | **Built**; 23/23 checks |
| New storage engine does all I/O through the interface | **Built** (the prototype plugin's own path still calls the store directly) |
| RAM binding (`MemBinding`) | **Built**, contract-tested |
| Tape, raw NVMe and raw disk bindings | **Designed** |

## Measure, don't declare

A locus's properties come from a **commissioning probe** run when the node starts, not from a
configuration file or a media label. The reason was measured on the same Linux host, with the same
code and the same declared class:

| Where the store's root pointed | Write rate |
|---|---|
| Node-local disk | **339 MiB/s** |
| Shared project filesystem | **8.1–8.8 MiB/s** |

That is a 40× difference, invisible to every declared field. Placement uses the measurement.

!!! success "Fixed 2026-09-20 (`2842891`): measured placement had never run"
    The node sent its measured rate at registration, and the index read it back when applying the
    registration, but the method in between never copied it into the commit. Every node therefore
    scored as unmeasured. Worse, an unmeasured node scored **0.7** while a *measured* slow node
    scored 0.05, so declining to measure made a node 14× more attractive than measuring it honestly.
    Both are fixed. A source lint, `eval/wire_contract.py`, now checks that every field a node sends
    at registration survives into the index.

### Durability is measured and fails closed

**Built and on the live placement path** (`fc5d81b`). A copy counts toward an object's durability
only where the node could show that its durability barrier (fsync) actually does work. The probe
writes the same data with and without the barrier and compares the rates:

| Measured locus | Ratio | Evidence | Durable copies? |
|---|---|---|---|
| DGX node-local disk | ×3.72 | Barrier costs time | Yes |
| macOS APFS (full fsync) | ×17.97 | Barrier costs time | Yes |
| DGX shared project filesystem, 2026-09-19 (one pass) | ×0.94 | Indeterminate | Refused |
| DGX shared project filesystem, 2026-09-23 (5 rounds, unanimous) | costs time every round | Barrier costs time | Admitted |
| RAM-backed storage | ≈×1, fast | Absent | **Refused** |

A ratio near 1 on slow storage has two explanations the timing can't tell apart: the barrier is a
no-op, or a network round trip hides it. Such a node therefore can't hold durable copies unless an
operator sets `gfs_durability_attested=true`. That setting is always reported as an attestation,
never as a measurement. Timing also can't prove that data survives a power loss; only a power-loss
test can show that.

!!! note "Correction (2026-09-23, DGX jobs 221777 and 221810)"
    A single timing pass proved unreliable: on dgx-03 it classified one of four identical node-local
    directories INDETERMINATE (the first site probed ran on a cold JVM). The probe now warms up, runs
    five rounds in alternating order, and counts a locus durable only if **every** round agrees. With
    that probe the DGX shared project filesystem measured **COSTS_TIME** unanimously (13–14 MiB/s),
    contradicting the earlier ×0.94. So it may be admitted. Its real cost is speed: 10–18× slower
    than node-local storage.

!!! warning "Operational consequence"
    On the DGX, storage nodes default to a directory under `~/cresco/nodes/…`, which is on the
    shared network filesystem. The robust probe now admits it, but it is 10–18× slower than
    node-local storage, so point `store_dir` at node-local storage. If a probe run there comes back
    inconsistent, those nodes are refused durable copies, and placement logs why.

## Where placement is heading

**Proposed** (awaiting owner decision, [questions A1–A14](../roadmap/open-questions.md)):

- **Record how every property was obtained.** Every value carries its basis: `MEASURED`,
  `ATTESTED`, `MODELLED`, `DEFAULT` or `UNMEASURED`.
- **Media labels become telemetry**, illegal as inputs to placement.
- **Properties still to add**: per-access setup cost (a tape mount, a disk seek, nothing for RAM);
  whether the medium can be removed and stored offline; whether it survives power loss; how finely
  and how fast space can be reclaimed; and wear, in the medium's own unit (tape load cycles, SSD
  drive-writes-per-day, disk power-on hours).
- **Latency as a measured distribution** rather than buckets. Today's "milliseconds" bucket spans
  RAM (~100 ns), NVMe (~100 µs) and disk (~10 ms), five orders of magnitude.
- **Policy as constraints plus scoring**, from a small fixed set of predicates. For example: three
  copies, at least one on write-once media, at least one with millisecond first byte, at least one
  removable, all in distinct failure domains.
- **Conserved resources checked separately**, not traded in one currency. A single drive-hour
  budget is how the design once missed that tape cartridges wear out before the drives do.
