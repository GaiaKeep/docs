# panAtlas

panAtlas is a reference atlas for multimodal evaluation across every domain of knowledge. Medicine is
where its holdings run deepest today, but it is not a medical atlas. It is a provenance-first knowledge
graph linking concepts, datasets, models, training curricula and benchmarks, and a distributed system on
[Cresco](https://crescoedge.github.io/docs/): each registered dataset is managed by its own Cresco plugin at
the site that holds it. It is a primary intended user of this storage system: every document has a unique
id and metadata, and everything is indexed. Its own documentation is at
[thepanatlas.github.io/docs](https://thepanatlas.github.io/docs/), and
[Storage on GaiaKeep](https://thepanatlas.github.io/docs/distributed/storage/) describes this binding from its
side.

## The index is a dataset, not a structure of the store

**Measured 2026-09-19** on the HPC cluster:

| Part | Size | Share |
|---|---:|---:|
| Source-of-record ledgers (5 parquet files) | 11.24 GB | 5.7 % |
| Derived labels, edges and nearest neighbours | 186.80 GB | 94.3 % |
| **Total** | **198.04 GB** | 200,497,968 documents, 988 B each |

That is 185 one-GiB parcels, **0.66 % of a single 30 TB cartridge**, and **13–14 minutes** to bring
back from cold tape with one mount (timing Modelled). "Everything indexed" is therefore cheap, as
long as the index is **stored as an ordinary versioned dataset**. The alternative, a per-document
index inside the store's own on-media structures, would be 254× larger per cartridge and would
scale with the document count.

## Document identity and the oracle rule

panAtlas identifies each document by `doc_uid = blake2b(raw_text, 16 bytes)`, an **unkeyed** hash
of the text. That is intentional: it makes about 200 million documents (200,497,968 in the ledger crosswalk) traceable across corpus versions
and checkable for training contamination. It also means anyone holding a candidate document can
confirm whether it is in the corpus.

- **In the design of record** (§19.3), `doc_uid`, `manifest_hash` and `doc_ids_e8_order.txt`
  (2.54 GB of nothing but unkeyed content hashes) are **payload only**. They may appear inside
  encrypted objects, never in on-media structures.
- **Under the dedup model (built in 1.3)**, that rule becomes policy. Public literature, which is most of
  today's text corpus, could sit in the global domain, where plain content hashes are expected.
  Clinical data can't.

!!! warning "GaiaKeep's side is settled; keying `doc_uid` is panAtlas's decision ([X1](../roadmap/open-questions.md))"
    X1 was answered on 2026-10-02: GaiaKeep mints its own identifiers and never relies on external keys. The
    contamination check has so far run only on text (16 benchmarks, all text, no imaging keys). Before an imaging
    version runs, panAtlas has to decide whether to key `doc_uid`, which would break the cross-version crosswalk
    whenever the key rotates, because the same unkeyed hash would otherwise be computed over protected data.

## Withdrawal

- **Parquet ledgers**: sharded by redaction domain *before* storage, so a withdrawal destroys one
  shard's key and blanks only those rows.
- **Derived arrays** (`.npz`): a row can't be blanked without rewriting the whole array. The
  correct response is **invalidate and recompute**, which works because the recipe is kept (jobs
  219233/219234, `p6_promote.py`, lexicon v5.3). What recomputing costs is **unmeasured**; the
  exhaustive nearest-neighbour search is the expensive part.

## A good first dataset

There is no single hero dataset: the first real data is several fixtures of different sizes and shapes
([P2](../roadmap/open-questions.md), answered 2026-10-02), and the panAtlas index is among the candidates. It's small,
its sizes are measured, and it exercises identity, versioning and the identifier rules without
needing tape.
