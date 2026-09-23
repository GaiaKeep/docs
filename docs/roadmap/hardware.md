# Hardware and procurement

## Decided

- **Start with a Spectra Stack**, not a Cube. The first library doubles as the instrument that
  measures the constants every throughput figure depends on.
- **A few petabytes to start**, replicated, while distribution and encoding mature. The eventual
  store is petabytes of radiology and pathology imaging.
- **Three sites** with 3-way replication.

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

## Sizing, 3-way replication across three sites

About 3.43× raw per usable byte (three copies × RS(28,4) inside each volume):

| Usable | Per site, PA 40 TB cartridges | Per site, LA 30 TB cartridges |
|---:|---|---|
| 2 PB | 57 cartridges, 70 slots | 76 cartridges, 80 slots |
| 3 PB | 86 cartridges, 90 slots | 114 cartridges, 120 slots |
| 5 PB | 143 cartridges, 150 slots | 191 cartridges, 200 slots |

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
