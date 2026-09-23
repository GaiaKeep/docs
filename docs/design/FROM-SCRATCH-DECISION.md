!!! success "Status: Current"
    The statement of purpose and the decision to remove Bareos (2026-09-20). Current.

# The system, stated — and why Bareos is now disqualified

*Decision recorded 2026-09-20, on the owner's statement of purpose.*

## 1. What this is

> "The entire point of this system is to be ready to stream versioned datasets wherever they need
> to go. This once again is not for humans, it is for agents and to be used by agents."
>
> "Programmatic, versioned, resilient, secure, and distributed."
>
> "We likely need to resolve these issue and have a general solution that works across local memory,
> nvme, spinning disk, tape… it does not matter and the data is raw."
>
> "We can do a crazy new global file system from fucking scratch… or at least using libraries with
> permissible commercial licenses."

Five adjectives, and each one is a constraint with teeth:

| | what it means here | where it stands |
|---|---|---|
| **Programmatic** | No filesystem, no human interface. `prospect` returns costed feasibility; `realise` is the one verb that moves bytes. An agent plans against cost and then commits. | designed (Entail §9) |
| **Versioned** | `VersionRoot` names immutable content-addressed runs. An *extract* is a first-class citable, pinnable GC root. Read is versioned; write is quorum-confirmed. | designed |
| **Resilient** | 3-way replication across 3 sites now; erasure coding later, reached by repack. Repair is a copy, not a reconstruction. | decided 2026-09-20 |
| **Secure** | Encrypt at origin under per-object keys; GCM counter discipline structural, not delegated; no plaintext-derived identifier on media. | §20 landed, 14/14 |
| **Distributed** | The Cresco mesh is the substrate, already proven at 240 sites. | shipped |

And one noun that carries more weight than it looks: **stream**. Not mount, not download, not
materialise-then-open. A byte stream with backpressure, addressed by version, resolved at request
time to whichever locus is cheapest — RAM, NVMe, spinning disk or tape. **It does not matter, and
the data is raw.**

## 2. Why that disqualifies Bareos

`BAREOS-RECOMMENDATION.md` §6 established the licence facts by counting, not by inference:
**979 of 350,751 lines of `core/src` carry the Affero header and exactly two carry LGPL.** There is
no LGPL interface layer to plan around. Forbidden outright: importing `python-bareos`; any SD, FD or
Dir plugin; subclassing an SD backend; vendoring any source; editing the shipped `mtx-changer`;
patching for any reason; writing rows into its PostgreSQL schema.

Only one band is clean — running stock daemons at arm's length and driving them over the console
socket. That band was accepted when the goal was "manage volumes." It is not acceptable now, and
the reason is in the recommendation's own words:

> **The cost this imposes, stated plainly: the licence forecloses the efficient integration.** The
> documented way to stream at native speed without staging is an FD plugin, and that is precisely
> the linking case. So every byte is written to staging and read back over the FD→SD socket.

**The one thing this system exists to do — stream — is the thing the licence forbids doing
efficiently.** Every byte takes a mandatory round trip through staging, which is simultaneously a
new single point of loss (A-1) and unmeasured (rig item R-11). That is not a tax worth paying for a
volume manager whose catalogue we demote to a cache, whose retention engine we fence off, and whose
on-media format we did not choose.

A fifty-institution deployment also exports an AGPL compliance posture to every institution
(A-ζ) — people under data-use agreements who did not sign up for it.

**Decision: Bareos is out of the design of record.** `BAREOS-RECOMMENDATION.md` is retained as the
analysis that produced this, not as a recommendation.

## 3. What replaces it, and why it is licence-clean

Drive the Linux `st` and `sg` drivers directly: `ioctl` on `/dev/nstN` for the drive and `/dev/sgN`
for the media changer. SCSI stream commands (`WRITE`, `READ`, `LOCATE`, `REWIND`, `SPACE`,
`WRITE FILEMARKS`), `LOG SENSE` for drive health, MAM for cartridge attributes.

**The syscall and `ioctl` boundary is not GPL derivation.** A userspace program that calls the
kernel through its documented interface is not a derivative work of the kernel — the settled and
explicitly stated position. So raw SCSI is clean where linking to Bareos is not.

Getting there from Java, in order of preference:

1. **JDK 22+ Foreign Function & Memory API.** No dependency at all — it is in the JDK. We are on
   **JDK 21**, where FFM is still preview, so this requires a toolchain bump. *Cleanest option;
   the bump is the only cost.*
2. **JNA** — dual Apache-2.0 / LGPL-2.1, so take the Apache option. Already in the Cresco stack.
   Carries the known `OSHI-JNA-is-an-Error` failure mode.
3. **A small C helper as a separate process** speaking a trivial protocol over a pipe. Full
   licence isolation regardless of what it links. The fallback if 1 and 2 both disappoint.

## 4. What this costs, honestly

Dropping Bareos is not free, and the largest loss is not the code:

- **`bls` / `bextract` / `bscan` are a catalogue-free reference reader.** Today, a cartridge can be
  read by software we did not write, which is a genuine disaster-recovery property. Losing it means
  **our on-media format must be independently documented and we must write and maintain our own
  reference reader** — one that works with no index, no catalogue and no running system. That
  obligation is now load-bearing and belongs in the blocking list.
- **Error recovery and drive quirks.** Bareos has decades of accumulated handling for sense codes,
  retries, end-of-media, and vendor deviations. We inherit all of it as our own work.
- **The changer script, bootstrap records, and position management** become ours.

What we get back: no AGPL anywhere; no second catalogue to keep reconciled; no retention and
recycling engine to fence off; exact control of block placement and `LOCATE`; and **streaming at
native speed with no mandatory staging round trip** — the property the whole design is for.

## 5. Licence position of the rest of the stack

`io.cresco.gfs` is **Apache-2.0** (`pom.xml`). Felix, ActiveMQ, Derby, Netty, Jackson, Guava, Jetty,
Micrometer are Apache-2.0 or dual permissive; Bouncy Castle is MIT-derived; OSHI is MIT. With Bareos
removed, **nothing in the stack carries a copyleft obligation.**

`mhvtl` (GPL) remains usable for *testing only* — it is a kernel module on a test host, never
shipped and never linked.

## 6. What must be decided next

1. **Toolchain: JDK 21 → 22+** for FFM, or accept JNA. Blocks the tape binding's implementation.
2. **The on-media format becomes a one-way door with no vendor fallback.** With Bareos gone, nothing
   else can read our cartridges. The format specification and the independent reference reader are
   now the same blocking item.
3. **The mount cycle measurement is unchanged and still first.** It does not care which software
   issues the SCSI commands.
