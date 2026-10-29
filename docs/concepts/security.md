# Security and cryptography

## Model

- **Encrypt at the origin.** Data is encrypted before it leaves the writer. Storage sites hold
  ciphertext and no content keys.
- **Keys follow the data's policy.** Sealed data uses unique, tenant-protected keys. Shared and
  public domains derive a key per block so that identical blocks can deduplicate (see
  [Tenants, collections and deduplication](tenancy-and-dedup.md), **Proposed**).
- **Approved algorithms only.** AES-256-GCM, SHA-256, HMAC-SHA-384 and HKDF, with the platform's
  secure random generator. The DoD/DoW hardening direction requires FIPS/CNSA, and CNSA calls for
  SHA-384 as the hash; switching is an [open decision](../roadmap/open-questions.md).
- **Tenant isolation comes from Cresco**: tenant-namespaced messaging, broker authorization, and
  named cross-tenant flows (W-GFS-1, shipped in the Cresco 1.3 controller).

## Proven in the prototype

| Mechanism | Evidence |
|---|---|
| Per-object data key, AES-256-GCM per stripe, wrapped under the site key | E6: fragments on disk are ciphertext, no key material on holders |
| A holder with manifest access but no key cannot restore | E6.13 |
| Repair needs no keys | E7, E8 |
| Site key held in **Shamir t-of-n custody** at other sites; reconstruction needs an approver quorum; approvals are single-use | E9 (3-of-5; 2 holders dead still reconstructs, 3 dead fails closed) |
| Access grants signed and enforced **at the origin**; forged, tampered, expired and garbage grants refused | E5.6–E5.9 |

## Built since

**The counter discipline for per-object keys** (`SegmentCipher`, **Built**, 14/14 checks). AES-GCM
fails catastrophically if one key ever encrypts two different messages under the same IV: the
authentication key can be recovered and tags forged, and on write-once media that can't be
repaired. One large object puts **184,044 encryptions** under a single key, so uniqueness has to be
guaranteed by construction:

```
K_seg = HKDF(K_obj, length-prefixed("gfs/seg/v1", write_id))
iv    = xorb_seq (64 bits) ‖ chunk_ordinal (32 bits)
```

The IV is built from two counters the writer owns before any data leaves. It needs no random
generator and never has to be stored. Each write gets its own derived key, so a resumed upload
can't replay counters. A retry with different content at a spent counter is **refused**, never
re-encrypted. This becomes the implementation for sealed data. It has no production caller yet.

**The confirmation-oracle rule** (`OracleLint`, **Built**). A field written to shared or
write-once storage is safe only if someone holding a guessed plaintext **and no key** cannot
reproduce it. Hashes over ciphertext pass; an unkeyed hash of plaintext fails, because it lets
anyone confirm a guess. Under the proposed dedup model the rule is **mandatory for sealed domains**
and **relaxed for the global domain**, where plain content hashes are the point.

## Verified safe

The live encode path (`DurabilityEngine`) makes a **fresh data key for every encode** and uses the
stripe index as the counter. It reads each file sequentially, so each (key, stripe) pair is used
exactly once. Repair rebuilds fragments from ciphertext and never re-encrypts.

## The live tier: plaintext by decision

The [live tier](live-tier.md) puts committed versions on live nodes near compute as **plaintext native
files** (owner decision, 2026-10-27: "the durable tier is the only thing that is not native"). That moves
part of the security boundary, so the rest of the design is built around it. **Built** and tested
(2026-10-28, development branch).

- **Decryption stays in the core.** Storage nodes stay blind and hold ciphertext only. The core decrypts a
  committed version and sends it to the live node over node streams sealed with AES-256-GCM per frame, under
  keys from a signed ECDH P-384 exchange (HKDF-SHA-384), with an HMAC-SHA-384 per file. **No file byte, path
  or digest of plaintext crosses a message broker**; a test captures every frame and message during a
  realise and a workspace publish and finds none.
- **Signed both ways, sealed end to end.** Every live verb is a signed, sealed request. Every request to a
  live node is signed by the core's leader, and every reply by the node's pinned key, including the
  attestations that end a deletion.
- **Who decides where plaintext may go.** Only a tenant administrator may admit a collection at a node; a
  system administrator may only withdraw an admission, since that role grants no data access. An admission
  is tied to the node's pinned key and lapses if the key changes.
- **A narrow node principal.** A live node may hold a principal of its own whose only right is to realise, at
  itself, the collections a tenant administrator bound it to. Every other verb refuses it.
- **File permissions fail closed.** Copies are read-only, owned by the agent's user, in a group from the
  node's mapping; with no mapping they are owner-only.
- **The node checks its host** at start and every 30 s and accepts no new copy while a check fails (see
  [The live tier](live-tier.md#the-node-checks-its-own-host)).

What this cannot do, stated plainly: on the node, the operating system is the boundary. Root, and anyone
the operating system lets read the live root, can read live copies, and reads through the filesystem are not
audited. Copies people make with their own access are beyond any deletion. An encrypted live root, with
per-tenant keys held by the node, is a deployment option and is not built.

**Restarts are authenticated too.** A storage node's departure notice is signed and bound to its current
boot; a notice from an earlier boot, delayed or replayed, is ignored
([Stops, restarts and slow disks](stops-and-restarts.md#a-storage-node-restarted-under-writes)).

## Known issues and open items

| Item | Severity | Status |
|---|---|---|
| **Site key wraps every object's key with a random IV**, is never rotated, and nothing counts wraps against the NIST 2³² limit for random IVs. The wrap's authenticated data is the key id only, so a wrapped key can be moved into another object's manifest; stripe authentication then fails, so it confuses rather than leaks | Minor | Fix proposed: derive a one-time wrapping key per object from the site key and object id, and bind the object id |
| Metadata key (`K_meta`) and catalogue nodes need an IV discipline; many concurrent writers share one long-lived key | Blocking before media | **Open**; the proposal was withdrawn because it assumed deduplication was retired. To be redone under the dedup model (S1) |
| Idempotency keys should carry a lease, so two writers can never share a counter space | Before media | Open (S2) |
| Direct calls to the low-level encrypt function should fail a lint | Minor | Open (S3); the benchmark reuses IVs across threads under a throwaway key |
| Hardware key custody (HSM) for key destruction | Before production | Open (S4) |
| Whether file names and sizes must be hidden from site operators | Before production | Open (S11) |
| Per-request, audited credentials for agents: scope and issuer | Before production | Open (S8) |

Library-level (BlueScale) drive encryption is **declined**. The data is already ciphertext, and a
second layer would only add a key-custody dependency.
