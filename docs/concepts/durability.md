# Durability and redundancy

## Phase one: erasure coding across three sites

**Decided by the owner (2026-10-02); the default since 2026-10-14.** Phase one is three identical sites,
and the default redundancy for durable data is erasure coding across them. It replaces the first plan of
2026-09-20 (three full replicas, erasure coding later by repack), which is kept below as history.

- **Three modes, chosen per dataset.** `ec:2+1` (Reed–Solomon RS(2,1): two data shares and one parity
  share, one per site) is the default for a new collection and for the built-in radiology and pathology
  profiles. `replicas:R` (R ≥ 2 full copies) and `single` (one copy, only for the scratch and cache
  classes) stay per-dataset choices. A block meets the strongest requirement among the collections that
  reference it.
- **About 1.5× raw storage per usable byte, and any one site can be lost.** Durability is counted per
  failure domain: a block's protection is the number of whole-site losses it survives. Disk and tape
  shares count; a tape share counts once its container is verified. RAM and live-tier copies never count.
- **One deduplication block is one stripe.** A block's ciphertext is split into shares, so every lifecycle
  operation (garbage collection, forget, deep delete, withdrawal, repack) stays per block, and repack never
  needs another site. The cost: a healthy read needs two sites, which on tape means two mounts for a small
  recall instead of one.
- **Encrypt, then encode.** Shares are slices and parity of the sealed block ciphertext, so no storage
  node, repair, re-encode or scrub ever needs a key.
- **Existing collections keep their mode.** Nothing is re-encoded on upgrade. Moving a collection is an
  explicit, audited operator action (`core.redundancy op=set`): repair re-encodes its blocks in place,
  without its protection ever dipping, and trim reclaims the full copies.
- **A fabric with fewer than three failure domains refuses an `ec:2+1` write** rather than downgrading it.
  With one of three sites down, coded writes continue as recorded debt that repair settles when it returns.

### What is built and what is open

**Built and tested** (2026-10-08 to 2026-10-16): the codec, the records and policy, the share read path,
repair, trim, scrub and deep scrub of shares, encode on write, mode changes in both directions, and, with
tape as the primary tier, the archive of each site's share, so a coded version commits once its tape
shares are verified. The evidence: integration-matrix cells for every deduplication mode and chunker,
model-based and linearizability tests with modes, a three-peer cluster test through the core service, a
coded dataset read back byte for byte from any two of the three tapes with every disk copy gone, and all
15 erasure-coding crash cells passing on a live local fabric. The long model campaign found and fixed
several engine faults on the way, among them two data-safety faults.

**Open:** codec and read measurements on the HPC cluster and the site hosts; the tape-simulator
experiment on the read cost of one stripe per block; the erasure-coding crash cells with three core peers
and on packed stores; rebuilding a lost site from tape alone with coded blocks; an intra-volume code on
tape and codes for a fourth site (later work); and the owner's call on whether a block may drop to a weaker
mode once its stronger referencer is gone (off by default). See the design record,
[Durability modes](../design/DURABILITY-MODES.md).

### Why three sites, not two or four

| Sites | Majority for index commits | Site failures tolerated |
|---:|---:|---:|
| 2 | 2 | **0**: no tie-break is possible |
| 3 | 2 | 1 |
| 4 | 3 | 1: the same as three, at a third more site cost |
| 5 | 3 | 2 |

Two sites can't form a quorum. Two is survivable only if the source copy (for example on the HPC cluster)
is kept, and a small witness VM breaks ties. That is an [open question](../roadmap/open-questions.md) (P3).

### What a site holds, and serving from an isolated site

Under `ec:2+1` each site holds one share of every coded block, half the block's size (two data shares and
one parity share across the three sites): never a complete copy, and only ciphertext. Collection discovery, version lookup and downloads are served
by the core's replicated log, and the core serves only while a majority lease holds
([The replicated core log](../design/CORE-LOG.md)). An isolated site's shares are intact and durable,
but its API is not serving while the site is disconnected; reads that need the core wait for quorum.
Serving objects from an isolated site without the core is **not built**. The
[live tier](live-tier.md) does not do it either: live copies are read where they sit, and one site's
live copies serving another site is not in its first phase.

### History: the first plan, replication first (2026-09-20, superseded)

The first plan was 3-way replication across three sites, with erasure coding reached later by repacking.
Its reasons were that every site would hold a complete copy, so repair would be a copy rather than a
reconstruction, and that a lost site could be rebuilt anywhere. Under the prototype's earlier
cross-site code a lost site's pieces could not be re-placed on the surviving sites, because each site may
hold only one piece of a stripe. The owner chose erasure coding as the default on 2026-10-02 (about half
the media of three replicas), with full replicas kept as a per-dataset choice, and one stripe per
deduplication block so that repack stays within a site. The modelled cost of migrating 3–5 PB from
replicas to a code by tape repack (8–13 PB of tape movement, about 19–32 days on 3 drives at each of 4
sites) no longer applies to new data, which is coded on write.

## Live copies never count

A copy on a [live node](live-tier.md) is an unencrypted copy of the version's files near compute, made for speed, and it is never a
durable copy:

- A live node never becomes a site, so no live copy is ever recorded as a copy of a block, and no census,
  repair, trim, placement or commit check sees one.
- Placement refuses a live locus even when it is attested, so a misconfiguration cannot make a live root
  count.
- The disk copy a site keeps after its tape copy is verified is durable-tier ciphertext, not live tier.

Losing every live copy loses nothing: each can be made again from the durable tier.

## Restarts are not failures

Durability also depends on what happens while the system is restarted. A planned stop of a core peer hands
the leadership over without failing client calls; a storage node restarted under writes announces its stop
and the core places writes elsewhere; a slow disk never costs the leadership, and a stuck one hands it over
only to peers shown healthy. See [Stops, restarts and slow disks](stops-and-restarts.md) (built and tested
2026-10-28; test-bed runs in progress).

## What the prototype proves

The September prototype implemented **cross-site erasure coding**, and it is proven on one host
(a historical record: the prototype path was retired on 2026-10-08).
See [The prototype](../built/prototype.md) for the evidence.

- Encrypt, then Reed–Solomon across distinct sites (RS(3,2) in the functional suite; RS(10,4)
  benchmarked); never on the origin site.
- **Blind holders**: stored fragments are ciphertext (entropy > 7.9 bits/byte), with no key
  material on any holder.
- **Keyless repair**: lost fragments are regenerated from surviving ciphertext without any keys.
- **Scrub**: on-disk corruption is detected, regenerated in place, and the object is durable again
  within about 3 s.
- **Storm**: 40 of 240 sites lost at once; 85 objects repaired in 27.2 s; 7 objects beyond the
  code's tolerance were reported rather than hidden.
- Detection and repair need no human action, and an object whose placement can't be repaired is
  reported explicitly.

The storage core rebuilt these mechanisms (loss detection, repair, scrub and audit) for its own block
store, first with replicas and since 2026-10-14 with `ec:2+1` coding by default. The prototype's storage
path itself was retired on 2026-10-08.

## Open items

- Required repair window after losing a site (hours, days or weeks).
- Whether cloud is acceptable as a temporary rebuild target for clinical data.
- Whether a block may drop to a weaker mode once the collection that needed the stronger one is gone
  (built, off by default, awaiting the owner).
- Codes for a fourth site, and an intra-volume code on tape, are later work.
