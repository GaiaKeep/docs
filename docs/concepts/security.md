# Security and cryptography

## Model

- **Encrypted end to end.** Bytes travel from a client to the core in transfers encrypted per request,
  and the core encrypts every block before it reaches a storage node. Storage nodes hold ciphertext and no
  tenant keys; repair, re-encoding and scrub never need a key.
- **Keys follow the data's policy.** Sealed data uses unique, tenant-protected keys. Shared and public
  domains derive a key per block so that identical blocks can deduplicate (see
  [Tenants, collections and deduplication](tenancy-and-dedup.md), **Built** in 1.3). Tenant roots are
  journaled only wrapped under the master key.
- **Approved algorithms, one policy.** AES-256-GCM, HMAC-SHA-384, HKDF-SHA-384, ECDSA and ECDH P-384, and
  SHA-384 for new formats (a few existing formats keep SHA-256 until a versioned format moves them). Since
  2026-10-16 one fabric-wide crypto policy covers GaiaKeep and Cresco: `cnsa1` by default, or `fips140-3`,
  with any exception allowed explicitly.
- **Zero trust, fail closed.** Every request is signed by a principal, authorised against tenant-scoped
  roles (the system administrator has no data access) and recorded in a tamper-evident audit log before
  its reply is released.
- **Tenant isolation comes from Cresco** as well: tenant-namespaced messaging, broker authorisation, and
  named cross-tenant flows.

## Built

Release 1.3 (2026-10-01), **Proven** on the HPC fabric check:

- signed requests (ECDSA P-384), tenant-scoped roles and a tamper-evident audit log;
- signed and encrypted storage-node traffic, with pinned node keys and fencing of a deposed leader by its
  Raft term;
- client transfers keyed per request, with the key exchange signed by the core and bound to the request;
- key custody from a file, the environment or PKCS#11, and master-key rotation behind an operator window;
- metadata encryption: sealed partitions, keyed identifiers and sealed snapshots.

Built since, each tested:

- **One IV discipline for every encryption** (2026-10-15). Every AES-GCM IV is made inside one crypto
  module, by a construction recorded for each call site (a counter, a sequence, or a key that seals once),
  and a lint fails the build on any other. The per-object counter discipline for sealed data
  (`SegmentCipher`) is the construction for `NONE` blocks.
- **At-rest encryption of the core log and the audit log** (2026-10-08), under per-epoch file keys wrapped
  under the master key; off by default (`core_at_rest_encryption`).
- **Sealed requests** (2026-10-15): a client can seal every parameter of a core request to the peer, and the
  peer seals its reply. Whether sealing becomes mandatory is an open owner decision.
- **The fabric-wide crypto policy** (2026-10-16), and the drive-encryption setting for tape (refused by
  default).
- **WORM classes and legal orders** (2026-10-02, extended 2026-10-08): a legal order needs two approvers,
  one a system administrator, and a 24-hour lock, and reaches write-once data by destroying its key where
  the key is destroyable.

## History: what the prototype proved

The September prototype's storage path was retired on 2026-10-08. What it proved remains on record
([The prototype](../built/prototype.md)): fragments on disk were ciphertext with no key material on the
holders (E6); repair needed no keys (E7, E8); a site key in Shamir 3-of-5 custody reconstructed with two
holders dead and failed closed with three (E9); and forged, tampered, expired and garbage access grants
were refused at the origin (E5.6–E5.9). Its site key, which wrapped every object's key with a random IV,
went with it.

## The live tier: unencrypted files by decision

The [live tier](live-tier.md) puts committed versions on live nodes near compute as **unencrypted native
files** (the version's real files, any type, byte for byte, in an ordinary directory tree) (owner decision, 2026-10-27: "the durable tier is the only thing that is not native"). That moves
part of the security boundary, so the rest of the design is built around it. **Built** and tested
(2026-10-28, development branch).

- **Decryption stays in the core.** Storage nodes stay blind and hold ciphertext only. The core decrypts a
  committed version and sends it to the live node over node streams sealed with AES-256-GCM per frame, under
  keys from a signed ECDH P-384 exchange (HKDF-SHA-384), with an HMAC-SHA-384 per file. **No file byte, path
  or digest of file content crosses a message broker**; a test captures every frame and message during a
  realise and a workspace publish and finds none.
- **Signed both ways, sealed end to end.** Every live verb is a signed, sealed request. Every request to a
  live node is signed by the core's leader, and every reply by the node's pinned key, including the
  attestations that end a deletion.
- **Who decides where unencrypted copies may go.** Only a tenant administrator may admit a collection at a node; a
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

## Open items

| Item | When it is needed | Status |
|---|---|---|
| Metadata-key IV discipline (S1) and idempotency-key leases (S2) | Before media | **Built**: the IV discipline above; a `NONE` object is sealed only under its idempotency lease |
| Direct calls to the low-level encrypt function fail a lint (S3) | | **Built** (2026-10-15) |
| Hardware key custody (HSM) (S4) | Before production | **Decided** (owner 2026-10-02): software keys behind a swappable interface in phase one, an HSM later; PKCS#11 is built |
| Whether file names and sizes must be hidden from site operators (S11) | Before production | **Built** in part: sealed metadata partitions and keyed identifiers; the rest of metadata encryption is open |
| Per-request, audited credentials for agents: scope and issuer (S8) | Before production | **Open** |
| A FIPS 140-3 validated module for fielding | Before fielding | **Open**: the `fips140-3` policy and a FIPS test profile exist; validation does not |

Library-level (BlueScale) drive encryption is **declined** by default (owner 2026-10-02): the data is
already ciphertext. It is a setting that a deployment's compliance rules can switch on.
