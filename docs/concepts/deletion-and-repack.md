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
| Status | **Designed**; per-object keys proven in the prototype (E9) | Retention and reclaim **Built** in the binding |

The two differ in speed by about six orders of magnitude, so they are separate operations with
separate records. Key destruction is the forget for privacy. Physical erasure is how capacity comes
back. Neither replaces the other.

Under the proposed deduplication model, a block in a shared domain can be referenced by several
objects, so destroying one object's key can't remove it. Forgetting in a shared domain means
**reference counting**, then physically removing blocks nobody references.

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

## Two tensions that must be decided before any data is written

**Privacy interleaving works against reclamation grouping.** Mixing different subjects' data in
each container hides who is in a cohort, but then nothing ever expires as a whole unit. At a 1 %
yearly withdrawal rate, an interleaved container takes **39 to 98 years** to reach the point where
repacking pays. Grouping lets containers expire whole but reveals the cohort. This is a
per-data-class decision ([D2](../roadmap/open-questions.md)).

**Rewrites must preserve the encryption inputs.** The IV is rebuilt by the reader from the block's
position counters. A repack that renumbers blocks without re-keying makes every block fail
authentication, and the read path would report that failure as a **lawful redaction**. The rule a
rewrite must follow: either preserve the counters and copy ciphertext bit-for-bit, or issue a fresh
epoch key. Never one without the other ([D4](../roadmap/open-questions.md)).

## Other open items

- Repack at whole-fragment granularity or finer. Finer renumbers positions and breaks pinned
  citations unless designed for.
- Whether tape drives can usefully skip dead regions. The repack cost model differs 3.77× between
  the two answers, and it is unmeasured.
- Destroying write-once cartridges is an attested two-person act. At a 10 % yearly removal rate on
  240 cartridges, that is one every 15 days. Who performs it?
- Garbage collection as a budgeted, refusable standing obligation: **Proposed**.
