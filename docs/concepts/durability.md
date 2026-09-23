# Durability and redundancy

## Phase one: three copies, three sites

**Decided by the owner (2026-09-20).** Start with a few petabytes, replicate while better
distribution and encoding are developed.

- **3-way replication across three sites.** Every site holds a complete copy.
- **Intra-volume Reed–Solomon RS(28,4)** stays on each medium to repair media defects locally.
  Combined, that's about **3.43×** raw storage per usable byte.
- **Erasure coding across sites comes later**, reached by repacking the data. It isn't a separate
  project.

### Why three sites, not two or four

| Sites | Majority for index commits | Site failures tolerated |
|---:|---:|---:|
| 2 | 2 | **0**: no tie-break is possible |
| 3 | 2 | 1 |
| 4 | 3 | 1: the same as three, at a third more site cost |
| 5 | 3 | 2 |

Two sites can't form a quorum. Two is survivable only if the source copy (for example on the DGX)
is kept, and a small witness VM breaks ties. That is an [open question](../roadmap/open-questions.md) (P3).

### Why replication first

What replication buys at this scale costs very little. At 3 PB usable it needs 143 more LTO-10
cartridges in total than the best erasure code would:

- **Every site is independently readable.** One site can serve any object with no cross-site
  reads and keep running if disconnected.
- **Repair is a copy**, not a reconstruction.
- **A lost site can be rebuilt anywhere**: a new site, a rented rack, disk, or cloud. Under the
  earlier cross-site code, a lost site's pieces could not be re-placed on the surviving sites at
  any capacity, because each site may hold only one piece of a stripe. The documented recovery plan
  was literally "procure a site".

The trade-off: each site holds a **complete** encrypted copy rather than a fragment. The copy is
still unreadable without keys, but a compromised site yields all of the ciphertext rather than a
third of it.

### Getting to erasure coding later

Moving from replication to erasure coding is a repack: read one replica, re-encode, write, and
erase the other replicas.

| Usable data | Tape movement | Drive-hours | On 3 drives × 4 sites |
|---|---:|---:|---:|
| 3 PB | 8.0 PB | 5,556 | ~19 days |
| 5 PB | 13.3 PB | 9,259 | ~32 days |

It is background work, and the choice of encoding stays reversible.

## What the prototype proves

The September prototype implemented **cross-site erasure coding**, and it is proven on one host.
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

These mechanisms (the loss detector, repair loop, scrub and audit) carry over to the replicated
design. Only the coding changes.

## Open items

- Required repair window after losing a site (hours, days or weeks).
- Whether cloud is acceptable as a temporary rebuild target for clinical data.
- Whether replication factor is per-collection policy: derived data that can be recomputed may
  need fewer copies.
- Which erasure code returns later: RS(2,1) across three sites or RS(3,1) across four. RS(3,1)
  uses 11.1 % less media for the same one-site tolerance.
