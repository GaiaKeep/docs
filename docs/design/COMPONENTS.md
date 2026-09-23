!!! success "Status: Current"
    Every component of the durable storage core: interface, what its tests must establish, the decision it feeds.

# Components of the durable storage core

*2026-09-23. **Status: all eleven components built and tested — 203 tests, 0 failures; results and the decisions they raise in `MODULE-DECISIONS.md`.** The build plan the owner ordered: define every component, build each one with
exhaustive module tests, make decisions module by module from measured results, then integration-test
the assembled engine across the option matrix. Design of record: `TENANCY-AND-DEDUP.md`,
`SPECIFICATION.md` §20, `ENTAIL-AGENT-NATIVE-FS.md` §3 and §6.*

All new code is under `io.cresco.gfs.core`. It is plain Java (JDK 21, no records, because the
ClassIndex processor breaks CI) with no dependencies beyond the JDK. That keeps it testable without
a Cresco fabric and lets the same code run inside the plugin. Tests are JUnit 5 under `src/test/java`
(test scope only; never shipped).

## The components

| # | Component | Package | Responsibility | Module decision it feeds |
|---|---|---|---|---|
| C1 | Chunker | `core.chunk` | Split a byte stream into blocks: fixed, content-defined (Gear), keyed content-defined | Default chunker and target size per mode |
| C2 | Block hash | `core.block` | Hash every block before storage; SHA-256 or SHA-384 | Confirm SHA-384 as the default |
| C3 | Tenancy and policy | `core.tenancy` | Tenants, collections, dedup domains, grants; enforce sealed, withdrawal-sensitive, mode and grant rules | Accept the policy defaults |
| C4 | Key ring and KDF | `core.block` | Tenant root keys; HKDF-SHA-384 derivation of domain, block and boundary keys | — |
| C5 | Block codec | `core.block` | Seal and open a block per mode: block id, per-block key, GCM; NONE via `SegmentCipher` | Accept per-mode identity and key rules |
| C6 | Reference index | `core.refs` | Reference counts, pins and replica locations per block; what is reclaimable | Refcount semantics |
| C7 | Versioning | `core.version` | File entries, runs, version roots, branches with compare-and-set, extracts and citation ids | Version identity form |
| C8 | Replica placement | `core.place` | Choose R loci under constraints: distinct failure domains, fail-closed durability, capacity; explicit unsatisfiability | Placement defaults |
| C9 | Loci | `extent` | `ExtentBinding` implementations: `FsBinding` (exists), `MemBinding` (new: volatile RAM locus) | — |
| C10 | Storage engine | `core.engine` | Publish, read with verification, compose, grants and augment, withdraw, site loss, repair, scrub; all I/O **through `ExtentBinding`** | — |
| C11 | Integration matrix | `src/test` | The assembled engine across every option combination and failure scenario | Which combinations become supported configurations |

## What each module test must establish

**C1 Chunker.** Chunks reassemble to the input exactly, for every size including empty and one
byte. Output is deterministic. Every chunk respects the minimum and maximum except the last.
Boundaries survive insertion and prepend (content-defined) and don't (fixed). Keyed chunking
differs from unkeyed and is stable per key. The streaming chunker matches the in-memory chunker.

**C2 Block hash.** Known-answer tests for both algorithms. Lengths are 32 and 48 bytes. Hashing is
deterministic.

**C3 Tenancy.** The full matrix of tenant flags (sealed, withdrawal-sensitive, public-reference opt-in)
× dedup mode × grant direction (same tenant, cross tenant, into sealed, out of sealed, out of NONE,
from GLOBAL) produces exactly the allowed or refused outcome in `TENANCY-AND-DEDUP.md`. Defaults for
withdrawal terms are applied. A mode can't change after creation.

**C4 Keys.** Derivations are deterministic, separated by domain and by label, and length-prefixed so
labels can't collide. Different tenants get different domain keys.

**C5 Codec.** For each mode:
- **Shared modes converge:** the same plaintext gives the same block id and ciphertext.
- **Domains are separated:** the same plaintext in two keyed domains gives different ids and
  ciphertext.
- **GLOBAL** ids equal the raw hash.
- **NONE never converges.**
- Opening verifies authentication and binds the block id to the content, so tampered ciphertext or a
  mismatched id is refused.
- The confirmation-oracle rule holds: without the key, a guessed plaintext can't be matched to a
  keyed-mode id.

**C6 References.** Adding and removing are idempotent per holder. A block becomes reclaimable exactly
when it has no holders and no pins. A pin prevents reclamation. Randomised sequences agree with a
reference model.

**C7 Versioning.**
- Later runs shadow earlier ones, and tombstones delete.
- A commit is refused unless it names the current head (compare-and-set).
- Branches are independent.
- A version id is deterministic from its content.
- Extract selectors are deterministic, and citation ids are stable and change when the set changes.

**C8 Placement.**
- R copies land on distinct failure domains.
- Loci that can't show durability are refused unless attested.
- Capacity is respected, and excluded loci are never chosen.
- An unsatisfiable request fails with a reason that counts what was refused and why.
- The choice is deterministic for a given seed.

**C9 MemBinding.** It passes the same contract checks as `FsBinding`. It declares itself volatile, so
its barrier evidence is ABSENT, and wiping it models losing it.

**C10 Engine.** Every published version reads back byte-identical and verified. Unchanged files
carry forward by reference. Deletes work. Composing GLOBAL datasets stores zero new blocks.
Augmenting another tenant's data stores only changed blocks. Withdrawal reclaims exactly the
unreferenced blocks. Losing R−1 sites leaves every version readable, and repair restores R copies.
Corruption is found by scrub and repaired.

**C11 Integration matrix.** The C10 scenarios run across dedup mode × chunker × hash algorithm ×
replication factor × locus type, plus the policy scenarios that must be refused. Every cell is
recorded: pass or fail, logical and physical bytes, and the dedup ratio.

## Measurements for module-level decisions

`ModuleMeasurements` writes `eval/results/modules/*.json`, summarised in `MODULE-DECISIONS.md`:

- chunker × workload (append, insert, prepend, overwrite, whole-file change) → blocks retained and throughput;
- SHA-256 vs SHA-384 throughput;
- codec throughput per mode;
- engine publish and read throughput per mode and replication factor.

## Not in this build

These are deliberately deferred, with the reason:

- **Tape binding over raw SCSI** needs hardware and the JDK decision (B2).
- **Quorum commit through the federation index across hosts.** The in-process version log uses
  compare-and-set; wiring into the Cresco index is the next stage.
- **`prospect` cost model.**
- **Packing blocks into containers**, and with it pin amplification.
- **The caching tier** (after durable storage).
- **Erasure coding** (later, by repack).
- **The metadata-key IV discipline (S1).** Version roots and manifests are in-process objects here and
  are not yet written to media.
