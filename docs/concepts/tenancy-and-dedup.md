# Tenants, collections and deduplication

!!! success "Status: design of record (2026-09-23)"
    The owner set the definitions and the requirement. The mechanism below is the design of record
    ([TENANCY-AND-DEDUP.md](../design/TENANCY-AND-DEDUP.md)). Every choice the owner has not made
    explicitly is a **policy setting with a default**, never a constant, so no point on the spectrum
    is closed off. It is **not built yet**.

## Definitions (owner)

**Tenant**
: A group, organisation or other legal entity. A tenant owns collections and holds keys.

**Collection** (dataset)
: A versioned dataset with its own rules for storage and compliance. It belongs to exactly one
  tenant.

**Dedup domain**
: The set of data whose identical blocks may be stored once. Every collection writes into exactly
  one domain and may read others only through **grants**.

## The requirement (owner)

> "We must be able to configure the most secure and most open cases possible, from complete
> isolation to global deduplication."

Block-level deduplication is **critical**. At one end, some tenants share nothing outside
themselves, with no exceptions. At the other, public datasets combine with no new storage.

## Four modes

| Mode | Deduplicates with | Block id | Block key | Raw hash kept |
|---|---|---|---|---|
| **NONE** | nothing | random | unique per object | only inside the encrypted manifest |
| **COLLECTION** | its own versions | keyed hash | derived per block | the domain's own index |
| **GROUP** | every collection in the group (a tenant or a named subset) | keyed hash | derived per block | the domain's own index |
| **GLOBAL** | everyone: public data | plain content hash | derived from the content | the global index |

**Every block is hashed before storage in every mode** (default SHA-384, per CNSA). What that hash is
allowed to become is the whole security model. For public data it is the identifier. For NONE it
appears only inside the encrypted manifest, so no stored value lets anyone test whether two objects
share content.

In the three shared modes, each block's key is derived from that block's own hash. **A key therefore
encrypts exactly one plaintext, ever.** Identical blocks produce identical ciphertext, which is the
deduplication, and the encryption IV hazard can't arise for data blocks. NONE keeps the per-object
counter discipline (`SegmentCipher`).

## The owner's three cases

1. **Public A + public B → C.** A and B are GLOBAL. C's manifest lists their blocks. **C stores
   only its manifest**, a few kilobytes.
2. **Augmenting another tenant's datasets.** Our collection writes into our own domain and
   references tenant A's blocks under a grant. The grant hands over exactly the keys of the granted
   blocks, not tenant A's domain key. We store only our changes.
3. **High-security tenants.** A tenant marked **sealed** may use only NONE, COLLECTION or its own
   GROUP. It can't issue or accept grants, none of its raw hashes leave its private index partition,
   and by default it brings public data in by **copying, never by reference**.

## Settings and defaults

| Setting | Default |
|---|---|
| Mode for a new collection | COLLECTION |
| Hash algorithm (fixed per domain) | SHA-384 |
| Chunker (fixed per domain) | content-defined; keyed to the tenant for sealed tenants; fixed 64 KiB for NONE |
| On withdrawal of referenced data | `PIN` for public data, `COPY` for cross-tenant grants, `BREAK` on request |
| Sealed tenant reading public data | copy only (can be opted into reference) |
| Withdrawal-sensitive tenants (consent-governed clinical data) | NONE or COLLECTION only |
| Changing a collection's mode | a publish action that re-encrypts into a new collection; never a relabel |

## Forgetting

| Mode | Forget one object | Forget the whole domain |
|---|---|---|
| NONE | destroy the object's key; instant | destroy each key |
| COLLECTION / GROUP | remove its references; blocks reaching **zero references** are reclaimed | destroy the domain key; instant |
| GLOBAL | remove references; unreferenced, unpinned blocks are reclaimed | not applicable |

Withdrawal-sensitive tenants are restricted to NONE and COLLECTION by default, so no other collection
can ever hold a reference to their blocks.

## What this reverses

It reverses the September 19 retirement of deduplication and of content-derived block ids. The ban
on plaintext-derived identifiers becomes a per-mode rule, and the fixed 64 KiB chunking decision
gives way to a chunker per domain. The measurement that model checkpoints share no blocks still
stands; it means checkpoint collections may choose NONE. It never showed that datasets don't
deduplicate. See the [Decision log](../roadmap/decisions.md).

## Still open

- The metadata-key IV discipline (S1), to be redone on this model before any media is written.
- How a grant delivers per-block keys at scale.
- Where reference counts live at 10⁹ blocks.
- Whether a GROUP can span tenants by agreement (a consortium), or only through grants.
- Chunker parameters, measured on real imaging and text.
