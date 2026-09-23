# Since the prototype

From 2026-09-18 to 2026-09-23 the work turned from "federated sharing with a durability tier"
toward **durable, versioned storage for agents across every medium**. This page records what was
built, what was measured, and what was found and fixed. The commits are in `GaiaKeep/gfs`, branch
`1.3`.

## Code built

| What | Commit | Status |
|---|---|---|
| Real fsync durability barrier in `BlockStore` (fsync the bytes, atomic rename, fsync the directory) | `dd6328a` | **Built**; cost measured |
| `ExtentBinding` interface and `FsBinding`, with measured commissioning | `db29849` | **Built**, 23/23 |
| Tape plant simulator (`SimPlant`) and mount scheduler (`PlantScheduler`) | `3902da0`, `5d97055` | **Built** |
| Four-term mount cycle including rewind-to-start; the two harnesses reconciled | `5d97055` | **Built** |
| Media-life admission rule; retention `retain`/`reclaim` with declared enforcement | `a3b7d0f` | **Built** |
| Binding wired into gfs; placement scored on measurement | `0c4c33d` | Wiring was broken; fixed in `2842891` |
| Counter discipline for per-object keys (`SegmentCipher`) | `ba18bdd` | **Built**, 14/14 |
| panAtlas index sizing and confirmation-oracle lint | `7e949d4` | **Built** |
| LTO-10 media type as a purchase parameter (LA 30 TB / PA 40 TB) | `29ad996` | **Built** |
| Measured placement wired end to end; unmeasured nodes no longer outrank measured ones; registration lint | `2842891` | **Built**, on the live placement path |
| Fail-closed durability barrier in placement | `fc5d81b` | **Built**, 13/13, on the live placement path |

## Found and fixed

These are worth knowing because each looked finished and wasn't.

- **Measured placement had never run.** Every node sent its measured rate and the index read it
  back, but the step in between dropped it, so every node scored as unmeasured. And the scoring
  paid nodes **not** to measure: unmeasured 0.7 against a measured slow node's 0.05. Fixed, and
  `eval/wire_contract.py` now guards that path.
- **The durability flag was hardcoded to "yes"** and read by nothing. Replaced by a measured
  classification that fails closed.
- **The block store had no durability barrier.** A write could be reported stored and still be lost
  in a crash. Fixed, with measured cost: 0.74 ms per fragment on Linux node-local storage.
- **A tape mover with no measurements reported itself as millisecond-class**, the most optimistic
  answer from the least information. Now reports "unmeasured".
- **The 95th-percentile latency was the median times two**: a number with no measurement behind
  it. Now measured.
- **A capacity figure was off by a unit.** 400 MiB/s and 30 TiB were used where LTO-10 is 400 MB/s
  and 30 TB, inflating rates by 4.9 % and cartridges by 10 %. Corrected everywhere.
- **The mount-cycle model left out the mandatory rewind before eject.** Now included.
- **Two plant simulations disagreed by 1.3×**, because one hardcoded stale rates from the other.
  Reconciled.

## Decisions made

See the [Decision log](../roadmap/decisions.md). In short: agents not humans; raw blocks, no
filesystem; one placement engine for every medium; Bareos removed on licence grounds; replication
first; write-once media per cohort, with repack; Spectra Stack first; permissive licences only;
block-level deduplication across a configurable isolation-to-global range.

## Design documents written

`STORAGE-DIRECTION.md`, `ENTAIL-AGENT-NATIVE-FS.md`, `SPECIFICATION.md` (the write-once block
fabric), `STORAGE-BINDINGS-DECISION.md`, `BAREOS-RECOMMENDATION.md` (now historical),
`FROM-SCRATCH-DECISION.md`, and research briefs for the tape tier and open storage problems. See
the [Design record](../design/index.md), which lists the parts of each that have been superseded.
