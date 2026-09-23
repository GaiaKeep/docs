# Tenants, collections and deduplication

!!! info "Status"
    The owner set the **definitions** and the **requirement** (2026-09-23). The **dedup domain**
    mechanism below is **Proposed** and awaiting approval, along with the five decisions at the end.

## Definitions (owner)

**Tenant**
: A group, organisation or other legal entity. A tenant owns collections and holds keys.

**Collection** (dataset)
: A versioned dataset with its own rules for storage and compliance. It belongs to exactly one
  tenant.

## The requirement (owner)

> "We must be able to configure the most secure and most open cases possible, from complete
> isolation to global deduplication."

Block-level deduplication is **critical**. It must be configurable per tenant and per collection,
and the design must not close off any point on the spectrum:

- **Public dataset A plus public dataset B form dataset C.** C must be reconstructable without
  storing any additional data.
- **A tenant builds on another tenant's datasets.** When our tenant augments dataset A and dataset
  B, which tenant A owns, we store only our modifications, under our tenant, and reference the
  originals.
- **High-security operations.** Nothing is shared outside the tenant, with no exceptions.
  Deduplication across the boundary is impossible by design.
- **Every block is hashed before storage**, so policy can decide what to do with it given what
  already exists.

## The proposed mechanism: the deduplication domain

Neither tenant nor collection alone can answer "who deduplicates with whom", so a third concept is
proposed. A **dedup domain** is the set of data whose identical blocks may be stored once. Each
collection's policy places it in exactly one domain:

| Domain | Deduplicates with | Block identifier | Block key | Where the raw block hash may go |
|---|---|---|---|---|
| **Sealed** | Nothing outside the tenant | Keyed under the tenant key | Unique; tenant-protected | Nowhere outside the tenant |
| **Collection** | Its own versions | Keyed under the collection key | Derived per block | The collection's index |
| **Tenant** or named group | Every collection in the tenant or group | Keyed under the domain key | Derived per block | The tenant's index |
| **Global** | Everyone (public data) | Plain content hash | Derived from content | The global index |

The raw hash of each block is always computed. What changes between domains is **what that hash is
allowed to become**. For public data it becomes the global identifier. For sealed data it never
leaves the tenant; only a keyed form is recorded. This keeps "hash everything" safe: a raw hash in a
shared index would let anyone test whether a sealed tenant holds a file they already have.

### How the owner's three cases map

1. **Public A + public B → C.** All three are in the global domain. C is a version manifest that
   points at A's and B's blocks. The only new storage is that manifest, a few kilobytes.
2. **Augmenting another tenant's datasets.** Our collection references tenant A's blocks under a
   grant and stores only changed blocks, in our own domain. Each block has its own key, so tenant A
   can grant exactly the blocks of dataset A without releasing its whole domain key.
3. **High-security tenant.** Every collection is sealed. There are no outbound or inbound
   references, and no raw hash leaves the tenant. Deduplication still works within the tenant.

### Consequences

- **Chunking must match within a domain.** Identical content only produces identical blocks if it
  is cut at the same boundaries. Global deduplication therefore needs one fixed, public chunking
  method. Sealed tenants should use a chunker keyed to the tenant, because the sequence of block
  sizes alone can fingerprint a known file.
- **Some September 19 decisions are reversed or become policy-dependent.** Those decisions removed
  content-derived block identifiers and deduplication and banned content-derived identifiers on
  storage media. They remain mandatory in sealed domains and are relaxed in shared and global
  domains. The per-object key discipline built on September 19 (`SegmentCipher`) remains the
  implementation for sealed data. See the [Decision log](../roadmap/decisions.md).
- **Deleting shared data needs reference counting.** A block in a shared domain can't be destroyed
  by destroying one object's key, because others may reference it. See
  [Deletion, retention and repack](deletion-and-repack.md).

!!! note "Chunking needs re-deciding"
    The design record switched content chunking to **fixed 64 KiB blocks** on September 19. That
    decision predates the owner's deduplication requirement. Measured: content-defined chunking
    keeps **99.85 %** of blocks shared after an insertion or prepend, against **0.1–50 %** for fixed
    blocks. Fixed blocks do as well on appends and whole-file changes. Which method, or which
    method per domain, is an [open question](../roadmap/open-questions.md).

## Decisions awaiting the owner

1. **When a referenced dataset is withdrawn** by its owning tenant, what happens to datasets that
   reference it: its blocks stay pinned, the referencing dataset breaks (and says so), or the
   referenced blocks are copied at withdrawal? *Proposed: a term of each grant, pinned by default
   for public data, copied for cross-tenant grants.*
2. **May a sealed tenant read public data by reference**, or must it copy it in? *Proposed: copy in
   only.*
3. **Block hash function: SHA-256 or SHA-384?** The DoD requirements call for CNSA, which specifies
   SHA-384. *Proposed: SHA-384 for all new code.*
4. **Can a collection change domain after creation**, for example sealed → global when a dataset is
   released? *Proposed: yes, as a publish action that re-encrypts and re-identifies; never an
   in-place relabel.*
5. **Withdrawal inside a shared domain**: when a subject withdraws, their references are removed,
   but an identical block survives if anyone else references it. Acceptable, or should
   withdrawal-sensitive data be barred from shared domains?
