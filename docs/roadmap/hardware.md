# Hardware and procurement

## Decided

- **Start with a Spectra Stack**, not a Cube. The first library doubles as the instrument that
  measures the constants every throughput figure depends on.
- **A few petabytes to start.** The eventual store is petabytes of radiology and pathology imaging.
- **Three identical sites**, with erasure coding `ec:2+1` as the default redundancy (owner 2026-10-02;
  the default since 2026-10-14). Full replicas stay a per-dataset choice. The first plan (2026-09-20)
  was three full replicas; see [Durability](../concepts/durability.md).

## Library facts

Supplied by Spectra for the **Cube**; figures for the **Stack** are still needed.

| | Spectra Cube |
|---|---|
| Slots | 50–1,670, in steps of 10 |
| Native capacity (LTO-10) | Up to 66.8 PB, which is 40 TB per slot and implies PA media |
| Drives | Up to 30 half-height or 16 full-height |
| Throughput | Up to 32.4 TB/hr native (30 half-height LTO-10 drives, i.e. 300 MB/s each) |
| Form | 42U standalone frame |
| Compute | **None**: a management controller only (LumOS REST API) |

## Sizing, `ec:2+1` across three sites

Each site holds one share of every coded block: half the usable data, so about 1.5× raw per usable byte
across the three sites. An intra-volume code on tape such as RS(28,4) is later work; with it, about 1.71×.
Cartridges per site (**Modelled**: arithmetic only, no slot rounding):

| Usable | PA 40 TB | LA 30 TB | PA, with RS(28,4) in each volume | LA, with RS(28,4) in each volume |
|---:|---:|---:|---:|---:|
| 2 PB | 25 | 34 | 29 | 39 |
| 3 PB | 38 | 50 | 43 | 58 |
| 5 PB | 63 | 84 | 72 | 96 |

The first plan's three full replicas with RS(28,4) inside each volume (about 3.43×) needed about twice the
PA column with RS(28,4): 57, 86 and 143 PA cartridges per site.

Throughput scales with drive count only up to the robot: about 14 drives per site on scattered
work. Laying data out so it is read together is worth 4.55× and costs nothing.

## Media: LA or PA

PA holds 1.33× per cartridge and per licensed slot, so it is cheaper per TB whenever its price
premium is under 33 %. Above about 132 PB logical, LA can't reach the target within four frames at
all. **Proposed: PA**, unless write-once media is offered only in LA for the cohorts that need it,
or the premium exceeds 33 %.

## Each site also needs a host

The library has no compute. Each site needs a server to run the Cresco agent, the storage software
and the spool. Proposed: a modest 1U machine with 8–16 cores, 64–128 GB RAM, a SAS HBA (or FC, or a
Spectra Swarm 40 GbE bridge), and 2–4 TB of NVMe spool. The spool size depends on LTO-10's minimum
streaming speed, which is not yet known.

## Questions for Spectra

1. Stack: slots per module, drive bays per module, maximum modules, and **whether one robot serves
   the whole stack**
2. The **guaranteed** native, uncompressed, decimal capacity of the PA part number, not "up to"
3. Whether LTO-10 is offered half-height
4. Write-once LTO-10 availability and price premium, for both LA and PA
5. Is Capacity-on-Demand a licence key on installed slots, or a field hardware install?
6. Can drives be added after purchase?
7. Load/unload cycle ratings for cartridges and drives, in writing
8. Mount cycle breakdown as a distribution: pick, load, locate, **rewind to start (is it
   mandatory?)**, unload
9. Minimum sustained streaming speed before the drive stalls ("shoe-shines")
10. SCSI Persistent Reservation support, for multi-host fencing
11. Robot exchange rate
12. Itemised pricing, and whether a minimal unit (1–2 drives, 40–80 slots) can be bought as a
    rebuild target or extra failure domain
