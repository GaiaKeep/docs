!!! success "Status: Current"
    Design of record for tenants, collections, dedup domains (NONE, COLLECTION, GROUP, GLOBAL), grants and per-block hashing (2026-09-23). Every owner-unmade choice is a policy setting with a default.

# Tenancy, collections and deduplication — design of record

*2026-09-23. Written on the owner's direction; supersedes the parts of `SPECIFICATION.md` and
`ENTAIL-AGENT-NATIVE-FS.md` listed in §10. Every choice the owner has not made explicitly is a
**policy knob with a stated default**, never a constant, so that no point on the
isolation-to-global spectrum is closed off.*

## 1. Requirements (owner, verbatim)

> "We can't paint ourselves into a corner here in terms of what might be configurable per tenant or
> collection/data. There are some tenants where we must keep things completely isolated and there
> will be other situations where we not only need to deduplicate across data collections, it will
> be expected."

> "A public dataset A is combined with public dataset B to form dataset C. We must be able to
> reconstitute dataset C without storing any additional data."

> "Tenant A owns dataset A and B and we augment dataset A and dataset B, we only need to store the
> modifications under our tenant while referencing the original datasets."

> "For high security operations, nothing is shared outside the tenant, no exceptions."

> "We must be able to configure the most secure and most open cases possible, from complete
> isolation to global deduplication."

> "A tenant is a group, org, or some legal entity and a collection/dataset is a dataset that is
> versioned and has rules for storage compliance per the collection."

> "We will need to think about the data that exists and hash it per block prior to storage, this way
> we know based on our needs and configurable policies."

And, earlier the same day: **block-level deduplication is critical.** A mode that provides no
deduplication, with unique and protected keys, must also exist.

## 2. Entities

```
Tenant {
  tenant_id            opaque
  legal_name, contacts
  sealed: bool                     -- §6: nothing crosses the tenant boundary, in or out
  withdrawal_sensitive: bool       -- §7: restricts which dedup modes its collections may use
  default_collection_policy
  keys: tenant root key (custodied; see §8)
}

Collection {                       -- "a dataset that is versioned and has rules for storage compliance"
  collection_id        opaque
  tenant_id
  domain_id                        -- the dedup domain this collection writes into (§3)
  policy {
    replication, placement constraints, retention class, WORM requirement,
    compliance tags (DUA, IRB, CUI, PHI ...),
    chunker                        -- fixed by the domain, recorded here for clarity
  }
  versions → runs → blocks         -- unchanged from the versioning design
}

DedupDomain {
  domain_id            opaque
  mode: NONE | COLLECTION | GROUP | GLOBAL
  owner_tenant_id                  -- absent for GLOBAL
  members[]                        -- collections (COLLECTION: exactly one; GROUP: any of the owner's)
  hash_alg                         -- fixed at creation; default SHA-384 (§5)
  chunker                          -- fixed at creation (§4)
  key: K_dom                       -- absent for NONE and GLOBAL
}

Grant {                            -- permission to reference another domain's blocks
  grant_id, from_domain, to_collection
  scope: WHOLE_DOMAIN | COLLECTION_VERSION(set) | BLOCK_SET
  on_withdrawal: PIN | BREAK | COPY  -- §6.3
  expires, approvals
}
```

A collection belongs to exactly one tenant and writes into exactly one domain. It may **read** other
domains only through grants.

## 3. The four modes

| Mode | Deduplicates with | Block identifier | Block key | Raw hash persisted | Owner's case |
|---|---|---|---|---|---|
| **NONE** | nothing | random, per write | unique per object (`SegmentCipher`) | only inside the encrypted object manifest | "does not provide dedup; the key must be unique and protected" |
| **COLLECTION** | its own versions | `HMAC(K_dom, H)` | `HKDF(K_dom, "blk" ‖ H)` | the domain's index partition only | version-to-version reuse |
| **GROUP** | every member collection (a tenant, or a named group within one) | `HMAC(K_dom, H)` | `HKDF(K_dom, "blk" ‖ H)` | the domain's index partition only | "deduplicate across data collections" |
| **GLOBAL** | everyone | `H` itself | `HKDF(H, "gfs/global/v1")` | the global index | "public A + public B → C" |

`H` is the raw hash of the block's plaintext, computed for every block before storage in every mode
(§5). The modes differ only in what `H` is allowed to become.

- **NONE** is the most isolated setting: identical blocks are stored separately, and no stored value
  lets anyone, including an administrator holding every key but one, test whether two objects share
  content.
- **COLLECTION** and **GROUP** allow deduplication among holders of `K_dom`. A holder of `K_dom` can
  tell that two blocks in the domain are equal; nobody else can.
- **GLOBAL** is for public data. Anyone holding a candidate plaintext can confirm it is stored,
  which is harmless for public data and is exactly what makes cross-tenant deduplication work.

### 3.1 Why per-block keys, and why this settles the IV question for shared modes

In COLLECTION, GROUP and GLOBAL every block's key is derived from its own content hash, so **a key
encrypts exactly one plaintext, ever**. Identical blocks produce identical ciphertext, which is the
deduplication; different blocks use different keys. The GCM nonce-reuse hazard that `SegmentCipher`
exists to prevent can't arise for data blocks in these modes. The IV is a fixed constant and nothing
needs to be coordinated. This was the property of the pre-2026-09-19 `K_rdom` design, and it
returns here.

NONE keeps `SegmentCipher` (`SPECIFICATION.md` §20) unchanged, because per-object keys cover many
chunks and need the counter discipline.

## 4. Chunking

Deduplication finds identical blocks only if identical content is cut at identical boundaries, so
**the chunker is a property of the domain**, fixed at creation and recorded:

| Chunker | Use | Why |
|---|---|---|
| `cdc(gear, 64K target, 8K–128K)` | **default for GLOBAL, GROUP, COLLECTION** | Survives insertions and prepends (measured: 99.85 % of blocks retained versus 0.1–50 % for fixed blocks, `eval/results/cdc_largefile.json`) |
| `keyed-cdc(K_bnd)` | **default for sealed tenants' shared modes** | Block-size sequences fingerprint known files; keying the boundary function under a tenant key stops that |
| `fixed(64K)` | allowed per domain; default for NONE | Cheapest, and adequate for appends and whole-file changes |

This **reopens** the 2026-09-19 decision to chunk content at a fixed 64 KiB (`ENTAIL-AGENT-NATIVE-FS.md`
§2). That decision was made when deduplication had been retired; it no longer stands as a global
rule.

## 5. Hashing every block

- `H = hash_alg(block plaintext)`, computed for every block in every mode before anything is stored.
- **Default `hash_alg = SHA-384`**, following CNSA as required by the DoD/DoW hardening direction.
  The algorithm is recorded per domain and fixed at the domain's creation, so it can differ between
  domains but never within one. `H` also serves as the integrity check on every read.
- **Where `H` may go** is the whole security model:
  - GLOBAL: `H` is the block id; it is public.
  - COLLECTION / GROUP: `H` is stored only in the domain's own index partition, readable only by
    principals holding the domain's grant. Everything outside it sees `HMAC(K_dom, H)`.
  - NONE: `H` is stored only inside the object's encrypted manifest. It never appears in any index.
  - A **sealed** tenant's partitions live in a tenant-private index partition; no raw `H` from a
    sealed tenant is ever sent to a shared or global index.

This is the `§19.3` confirmation-oracle rule of `SPECIFICATION.md`, restated per mode rather than
globally. The rule still holds everywhere; only what it forbids differs by mode.

## 6. References and grants

### 6.1 Composition without new storage (owner case 1)

Public A and public B are in GLOBAL. Dataset C is a new collection whose version manifest lists
A's and B's block ids. **C stores nothing but its manifest**, a few kilobytes of metadata. Reading
C resolves each id in the global domain.

### 6.2 Augmenting another tenant's data (owner case 2)

Our collection `A′` writes into our own domain. Tenant A issues a grant from its domain to `A′`,
scoped to dataset A's version. `A′`'s manifest references A's blocks as `(domain_A, bid)` and our
new or changed blocks as `(domain_ours, bid)`. Because block keys are per block, the grant delivers
**exactly the keys of the granted blocks**, not `K_dom`. Tenant A's other data stays unreadable to us.

### 6.3 When the referenced data is withdrawn

Each grant states its term, chosen at issue:

| `on_withdrawal` | Effect | Default for |
|---|---|---|
| `PIN` | The referenced blocks are pinned and can't be physically reclaimed while referenced | GLOBAL (public data) |
| `COPY` | At withdrawal the referencing collection receives a re-encrypted copy of the blocks it uses, in its own domain | cross-tenant grants |
| `BREAK` | The referencing version becomes unreadable and says so; the dependency was declared up front | allowed on request |

### 6.4 Sealed tenants (owner case 3)

`sealed: true` on a tenant enforces, at the index and not by convention:

- its collections may use only NONE, COLLECTION or GROUP (its own), never GLOBAL;
- it can issue no grants out and accept no grants in;
- **default: public data enters by copy only, never by reference**, so there is no outward
  dependency and no signal of which public blocks it uses. A sealed tenant may opt into
  read-by-reference of GLOBAL data (`sealed_allow_public_reference`); the default is off;
- none of its raw hashes leave its private index partition.

## 7. Forgetting and reference counting

| Mode | Forgetting one object | Forgetting everything in the domain |
|---|---|---|
| NONE | destroy the object's key, instant (`SPECIFICATION.md` §11, §12) | destroy each object key |
| COLLECTION / GROUP | remove the object's references; blocks whose **reference count** drops to zero are physically reclaimed | destroy `K_dom`, instant |
| GLOBAL | remove references; blocks with zero references are reclaimed; public blocks under a `PIN` stay | not applicable |

A block that is still referenced by someone else survives one object's deletion. For content that is
genuinely identical this is correct, not a leak: the surviving reference holds the same bytes.
**Tenants with `withdrawal_sensitive: true`** (consent-governed clinical data, by default) may only
use NONE or COLLECTION, so no other collection can hold a reference to their blocks. This is the
default resolution; the owner can widen it per tenant.

Reference counts are part of the index's replicated state. They are updated in the same quorum
commit as the version that adds or drops a reference.

## 8. Keys

```
tenant root key (per tenant, custodied t-of-n)
 └─ K_dom = HKDF(tenant root, "dom" ‖ domain_id)              COLLECTION, GROUP
     ├─ bid   = HMAC(K_dom, H)
     └─ K_blk = HKDF(K_dom, "blk" ‖ H)        IV: constant
 └─ K_obj  per object (NONE), random, wrapped                  SegmentCipher counter discipline
 └─ K_bnd  = HKDF(tenant root, "bnd" ‖ domain_id)              keyed CDC, sealed tenants
GLOBAL:  K_blk = HKDF(H, "gfs/global/v1")                     no secret; public data
```

The metadata key (`K_meta`, catalogue nodes) becomes per domain: `K_meta = HKDF(K_dom, "meta")`.
Its IV discipline is still **open** (question S1, to be redone on this model before any media is
written).

## 9. Changing a collection's mode

A collection's domain is fixed at creation. Moving data between modes, for example releasing a
sealed dataset publicly, is a **publish action**: it re-hashes, re-identifies and re-encrypts into a
new collection in the target domain. It is never an in-place relabel, because every block id and key
depends on the mode.

## 10. What this supersedes

| Document | Section | Was | Now |
|---|---|---|---|
| `SPECIFICATION.md` | §12.3 | Dedup table retired; "there is now no dedup" | Dedup per domain mode |
| `SPECIFICATION.md` | §18.4 | `sid` deleted; no content-derived chunk id may exist | Content-derived ids exist per mode: raw `H` in GLOBAL, `HMAC(K_dom, H)` in COLLECTION/GROUP, none in NONE |
| `SPECIFICATION.md` | §19.3 | No plaintext-derived identifier on media, globally | The same rule, applied per mode (§5) |
| `SPECIFICATION.md` | §20 | Per-object keys everywhere | Per-object keys (`SegmentCipher`) in NONE; per-block keys in shared modes (§3.1) |
| `ENTAIL-AGENT-NATIVE-FS.md` | §2 rows on chunking and `K_rdom` | Fixed 64 KiB content chunking; `K_rdom` retired by the checkpoint measurement | Chunker per domain (§4); per-block keys return for shared modes |
| `STORAGE-DIRECTION.md` | dedup and redaction-domain sections | Dedup restricted to within a redaction domain | Replaced by §3 and §7 |

The checkpoint measurement (`eval/results/ckpt_dedup_results.json`: zero shared blocks between
checkpoints) still stands as a **measurement**. It shows that model checkpoints gain nothing from
deduplication, and such collections may choose NONE. It was never evidence that datasets don't
deduplicate.

## 11. Defaults, in one place

| Knob | Default | Where set |
|---|---|---|
| Mode for a new collection | COLLECTION | collection creation |
| Mode for a new collection in a sealed tenant | COLLECTION | tenant policy |
| Mode for a withdrawal-sensitive tenant | NONE or COLLECTION only | tenant policy |
| `hash_alg` | SHA-384 | domain creation |
| Chunker | `cdc`; `keyed-cdc` in sealed tenants; `fixed` for NONE | domain creation |
| Grant `on_withdrawal` | `PIN` for GLOBAL, `COPY` for cross-tenant | grant issue |
| Sealed tenant reading public data | copy only | tenant policy |

## 12. Still open

1. The metadata-key IV discipline (S1), on this model.
2. How a grant delivers per-block keys at scale: a key bundle per version, or derivation on request by
   the granting tenant's key service.
3. Reference-count storage at 10⁹ blocks: in the index heap, or in a sharded store beside it.
4. Whether GROUP domains may span tenants by mutual agreement (a consortium), or only by grants.
5. The chunker parameters, measured on real imaging and text corpora rather than a source tree.
