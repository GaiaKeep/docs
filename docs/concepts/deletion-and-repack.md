# Deletion, retention and repack

> "There will be things we absolutely need to remove. We will absolutely group, but also repack
> tapes over time." (owner, 2026-09-20)

Write-once storage is **not** a plant-wide rule. It applies per cohort, to data that must be
immutable, such as cited extracts, audit records and research-integrity snapshots. Everything else
is rewritable and repacked over time.

## Two ways to forget

| | Key destruction | Physical erasure |
|---|---|---|
| Works on | Any medium | Depends on the medium |
| How fast | About **75 s** | Milliseconds on NVMe; **years** on tape (the repack or migration cycle) |
| What it does | Makes the data unreadable everywhere, in every version | Returns the capacity |
| Status | **Built** (1.3): per-object and per-domain keys, `core.destroykey`, forget, destroying a domain or a tenant | Retention and reclaim **Built** in the binding; deep delete overwrites pack containers before unlinking (**Built**, 2026-10-02) |

The two differ in speed by about six orders of magnitude, so they are separate operations with
separate records. Key destruction is the forget for privacy. Physical erasure is how capacity comes
back. Neither replaces the other.

Under the deduplication model, a block in a shared domain can be referenced by several
objects, so destroying one object's key can't remove it. Forgetting in a shared domain means
**reference counting**, then physically removing blocks nobody references.

## Live copies: deletion has to reach unencrypted files

A key destruction makes durable data unreadable everywhere, but it cannot reach a file on a
[live node](live-tier.md): live copies are the version's files, unencrypted, by owner decision (2026-10-27). So the core keeps a
journaled inventory of every live copy, and every deletion becomes a **drop** journaled in the same batch as
its cause: FORGET, a legal order, a withdrawal, a destroy, a pruned version, the end of a grant or of the
authority that made the copy, lease expiry, eviction or release.

- A drop ends only on the live node's **signed attestation** that the files are gone. A node that cannot
  delete something reports it stuck; the row stays **unconfirmed** and raises an alarm.
- The lifecycle record keeps the evidence (counts per node, a Merkle root over the attestations, the
  unconfirmed list) and does not reach `CONVERGED` while any of its live copies remain.
- A **deep** deletion overwrites each file before unlinking it, and the node claims that coverage only where
  its operator attested that the live root has no snapshots.
- A pin holds a version against routine pruning, never against FORGET, a legal order, a destroy or a
  withdrawal.
- Some copies are beyond any drop: copies people made with their own read access, snapshots and backups of
  the live root, client caches, the page cache and swap. The record's remanence statement lists them.

**Status:** **Built** and tested (2026-10-28, development branch). On the HPC test bed a withdrawal of a
collection with a live copy ended on the node's attestation with no file left (end-to-end check f1); the
FORGET check (f2) waits for a second approver to be eligible. On a local fabric (2026-10-28) a FORGET
converged in 11 s with its path in no live copy and in none of 1,088 audit records. The chaos stage checks
this after every cycle as invariants I3 and I4 (every end attested; a forgotten path in no live copy and no
audit record in clear). See
[Test results](../built/tests.md#the-live-tier-and-stability-e18-2026-10-28).

## Retention: built

Every binding has `retain(extent, until)`, which can only extend a floor, and `reclaim`, the only
way to remove data, which refuses while a floor stands. Each locus declares how the promise is kept:

| Enforcement | Meaning |
|---|---|
| `MEDIUM_ENFORCED` | The medium physically can't be rewritten (WORM) |
| `SOFTWARE_ENFORCED` | The software refuses, and nothing below it does |
| `NONE` | The locus can't hold data under a retention requirement |

A compliance document may claim only what the locus declares.

## Repack economics

Reclaiming a 40 TB cartridge means reading its live data, writing it elsewhere and recycling the
cartridge. The cost depends almost entirely on how much of it is still live:

| Live fraction | Hours | TB reclaimed | TB per drive-hour |
|---:|---:|---:|---:|
| 5 % | 3.0 | 38.0 | 12.8 |
| 15 % | 8.5 | 34.0 | 4.0 |
| 50 % | 28.0 | 20.0 | 0.7 |

That is an **18× swing** (Modelled). Data that expires together must therefore be written together.
The write path needs a **retention class** alongside the read-affinity hint it already carries.

## Two tensions, both decided by the owner (2026-10-02)

**Privacy interleaving works against reclamation grouping.** Mixing different subjects' data in
each container hides who is in a cohort, but then nothing ever expires as a whole unit. At a 1 %
yearly withdrawal rate, an interleaved container takes **39 to 98 years** to reach the point where
repacking pays. **Decided (D2): group.** Data that dies together goes onto the same cartridge, so volumes
die whole; privacy rests on encryption, keyed block ids and sealed metadata, and interleaving is kept only
for a class whose regulation requires it. **Built** (2026-10-02): a tape volume holds one retention cohort
(the class and a year bucket of its floor), and a fully dead volume is recycled from the beginning of the
tape.

**Rewrites must preserve the encryption inputs.** The IV is rebuilt by the reader from the block's
position counters. A repack that renumbers blocks without re-keying makes every block fail
authentication, and the read path would report that failure as a **lawful redaction**. **Decided (D4),
normative:** a rewrite is either a bit-identical move of the ciphertext or uses a fresh epoch key, never a
mix. The repack unit is the deduplication block, never finer (D3).

## Other items

- **Repack granularity:** decided (D3): the deduplication block, never finer, so pinned citations keep
  their positions.
- **Whether tape drives can usefully skip dead regions:** a test-bed parameter (D9). The repack cost
  model differs 3.77× between the two answers; plan for the worst case until it is measured.
- **Destroying write-once cartridges** is an attested two-person act. At a 10 % yearly removal rate on
  240 cartridges, that is one every 15 days. Who performs it is open (D7), and physically destroying real
  cartridges is not built.
- **Garbage collection** as a budgeted, refusable standing obligation: decided (D8: on by default, and
  repack refused for a volume more than 50 % live) and built with the scheduled maintenance passes.
