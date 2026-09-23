!!! warning "Status: Partly superseded"
    The agent-native interface: prospect/realise, Derivations, Coverage, extracts. **Superseded in part:** it assumes erasure coding across three tape domains (phase 1 is now replication), fixed 64 KiB chunking and retired deduplication (both reopened by the owner's dedup requirement).

# Entail

**An agent-native global file system.**

*Design specification, v1. Supersedes the interface decisions in `docs/STORAGE-DIRECTION.md`. Its **cryptographic and index decisions are inherited only as amended by `STORAGE-DIRECTION.md`'s own later sections**, and its **physical and Layer-0 decisions are superseded by `SPECIFICATION.md` and `BAREOS-RECOMMENDATION.md`** — this document does not restate them and must not be read as ratifying them. Where this document names a mechanism `STORAGE-DIRECTION.md` has since retired, the retirement wins and the reference is a defect to be fixed, not an inheritance. (Corrected 2026-09-19: the previous blanket clause — "inherits its physical, cryptographic and index decisions unchanged" — silently re-imported retired mechanisms into the agent-facing design of record.)*


> **Provenance of this document.** Produced 2026-09-19 by a 21-agent design pass: five independent
> first-principles designs (planning-first, compute-mobility-first, provenance-first,
> containment-first, workload-derived), each attacked on novelty, hostile scale at 10⁵ agents, and
> physics; then three critics on the whole set looking for shared blind spots; then synthesis.
> **Four designs reached synthesis — the containment-first design ("Witness") was lost to repeated
> schema-validation failure**, so its perspective is represented only through the critics and the
> containment lens applied to the others. Read §13 first: the unsolved list is the honest part.

---

## 1. Thesis

Entail is a federated store whose only callers are autonomous agents. It is built on **~50 participating institutions sharing three blind, erasure-coded tape failure domains**, plus a disk tier at the participants, across one state, over a mesh that already places computation and measures every link. *(CORRECTED 2026-09-19: previously "~50 blind, erasure-coded, mostly-tape holding sites". The design of record is fifty participants over **three** tape failure domains — `TAPE-RESEARCH-PROMPT.md` §1(d), `SPECIFICATION.md` §8.1/§8.2.)*

Two primitives make it different from every existing storage system. A third change — a subtraction — makes them coherent.

**Primitive 1 — the Derivation: a citable object whose identity is its recipe, and whose byte-residency is a decision the fabric makes and revises.**

Every other system in this class names bytes that must exist in order to be named. Entail names *entailed* bytes. `residency: ABSENT` is a legal, permanent, citable state. An agent registers `derive(inputs, transform, params)` — an O(1) journal entry, no bytes, no drive time — and immediately has a name it can cite, delegate, budget against, share and plan over. Whether that name is currently backed by stored bytes is a scheduling property, not an identity property.

This is an inversion, not an optimisation. The ancestors (Nix derivations, Bazel actions, Spark RDD lineage, Vesta, dbt, materialised-view maintenance) treat recomputation as a *build* or *fault-tolerance* mechanism in a world where storage is cheap and compute is dear. Here the cost structure is reversed and the reversal is physical: storage on this substrate is monotonic, un-erasable, legally entangled and reclaimable only by whole-cartridge rewrite, while decode and compute run at 3.4–24 GB/s against a tape path that delivers single-digit MB/s for selective reads. On this substrate, **entailment-first is the correct default storage policy for derived data**, and the determinism class of a transform is what decides which derivatives may be silently discarded. No existing system treats it that way.

The consequence that matters most: at 10⁵ agents the dominant object population is not ingest, it is agent-produced derivatives — tokenised shards, embeddings, resampled imaging, filtered cohorts, feature tables, checkpoints, evals, and derivatives of those, at 10–100× the source corpus per year with a useful life of days. Every design that treats that output as ordinary stored data ends the archive inside a year, and agents facing the bill route around the fabric entirely — which is where provenance, containment and redaction actually die. The Derivation is the only primitive that lets an agent keep its work inside the governed fabric without paying permanent capacity for it.

**Primitive 2 — Coverage: a conserved, monotone union that bounds disclosure across fan-out, caching and time.**

Every budget in a storage system is a sum. Disclosure is a union. The two differ in exactly the ways that matter here:

- A sum is defeated by caching. Once a set is warm, re-reading it costs nothing physical, so a budget denominated in drive-seconds or WAN bytes imposes no bound at all on reading warm data.
- A sum is defeated by fan-out. Offline capability attenuation can conserve *narrowing* but cannot conserve a *quantity* — a parent minting 10⁴ children each "≤ 1 TB" is monotone by the letter and unbounded in fact. This is a theorem about unobserved minting, not a flaw in any particular token format.
- A sum scores "reread the same 500 records 10⁶ times" and "read 10⁶ distinct records once" identically. The second is the attack.

A union has none of those weaknesses: it is monotone, idempotent (so double-counting is harmless and no distributed counter is needed), and unaffected by where the bytes came from. Entail maintains, per **Purpose** and across its entire delegation tree, the union of leaves actually delivered, enumerated or aggregated over — and charges byte delivery, metadata enumeration and statistical answers into the same union. "How much of what you are allowed to see have you in fact taken" becomes a budget line checked at admission, not a forensic query.

The ancestor is ASSAY's delivery bitmap, used forensically. Promoting it to a prospective invariant, and unifying byte reads with catalogue reads in one currency, is new.

**The subtraction — there is no read verb.**

Exactly one verb moves bytes: `realise`. Its argument is a Derivation, which names an already-frozen input set, a content-addressed transform and a typed output contract. Fetching a local copy is `realise` with the identity transform and an output contract the size of the input. Moving computation to the data is the same verb with a small output contract and a different locus. One planner prices both, one union bounds both, one receipt proves both, and the fetch-versus-ship decision becomes a strategy selection inside one call rather than an architectural fork.

Subtractions age well; expensive mechanisms bet on their own estimator and rot. Entail therefore deliberately **does not** make its planner binding. A signed, reservable quote across sovereign institutions has been built (SRM space tokens, Globus GARA, Maui advance reservations, SHARP), run at ~150 institutions over tape, and retreated from, because reservation semantics could not be honoured consistently and clients learned to ignore the estimates. On a medium where mount latency is bimodal at 30–120 s, intra-cartridge sweep dominates mount by 50×, and one library loss saturates the plant for weeks, a truthful binding number is not implementable. What Entail returns instead is a **decidable feasibility boundary, a cost interval with a per-term basis, the binding constraint, and concrete offered rewrites** — plus a real queue with a visible position. That interface remains useful when the estimator is useless, which is the regime the physics guarantees.

*(The name: to entail is both to necessitate and, in the legal sense, to bind an estate so it cannot be freely alienated. Both readings are intended.)*

---

## 2. What the substrate forces

Stated once, not re-argued. These are inputs, not choices.

| Fact | Consequence for the interface |
|---|---|
| Content is chunked at **fixed 64 KiB** (**CDC retired for content 2026-09-19**, `eval/results/cdc_largefile.json`; retained for sorted metadata runs), packed into xorbs (≤64 MB, ≤8192 chunks); ~~erasure-coded at the xorb~~ — the erasure unit is parcel/band/fragment/stripe, `SPECIFICATION.md` §3 | **Unchanged and load-bearing.** The collectable, pinnable, activatable unit is the xorb, never the file. Selection orthogonal to packing amplifies catastrophically: a uniform 0.1 % sample pins `1-(1-0.001)^1024` = 64 % of a lineage's xorbs; 1 % pins >99.99 %, at N = 1 extract. *This consequence is a property of PACKING, not of deduplication, and survives the dedup retirement in full.* |
| Drives, not cartridges, are the concurrency limit; **the non-transfer mount cycle is `O = 265 s` planning / 355 s pessimistic, four terms** (`SPECIFICATION.md` §3.4; ~~a mount is 30–120 s~~ stated the load term as if it were the cycle); serpentine sweep within a cartridge costs 20–60 s per reposition and dominates | The cost unit is **sweep-adjusted drive-seconds**, not mounts. Scan beats seek above roughly 0.5 % selectivity, so "read everything and filter" is frequently the cheap plan and the fabric must say so. **Flagged, not resolved (2026-09-19): "the cost unit is drive-seconds, not mounts" is in tension with the measurement.** The reactive plant spends 95 % of drive time on mount and reposition, and batching — which acts on mount *count*, 1,996 mounts down to 72 — is worth 9.4× in GB per drive-hour (`eval/results/plant_sim.json`). Mounts are not a negligible term. This row needs its own pass against that harness. |
| One fragment per failure domain; `k` of `n` to decode; fragments are `size/k` | No site holds the data. Assembling `k` fragments costs one object's worth of bytes wherever you decode, so for cold data **recall cost is invariant under fetch-versus-ship**. Locality is not inherited from placement; it is manufactured by activation and held as a lease. |
| ~50 sites share one 100 G state core | Cost is not a pairwise link matrix. A `k`-way fan-in is bounded by the destination uplink and by shared-segment residual. The federation has a daily byte budget on the order of 10² TB. |
| WORM media; reclamation is a whole-cartridge rewrite — **20.8 drive-hours of read pass per 30 TB cartridge plus the write of the live fraction (~24–27 drive-hours at a ~60 % live fraction); plant-wide 1.9 % of the plant-year at 85 % dead, 6.5 % at 50 % dead** (MEASURED 2026-09-19, `eval/results/plant_contention.json`; ~~~25 drive-hours~~ was the third distinct value for this quantity in the document set) — GC on the WORM tier is off by default | unchanged: the archive is monotonic on tape, permanent capacity is the scarcest thing an agent can spend, and citable extracts per lineage per year is a first-class capacity input. |
| Redaction is key destruction, not fragment destruction (D2 retired: `auto_repair` regenerates destroyed fragments in seconds; a xorb packs ~64 unrelated subjects) | Consent withdrawal = **destroy the object keys of the consent unit** *(2026-09-19: was "destroy `K_rdom`")*. Zero mounts, zero bytes moved, exact blast radius, immediate in every version and every pinned extract. |
| ~~`K_rdom` already decouples the shred unit from the packing unit~~ — **RETIRED 2026-09-19 by measurement** (`eval/results/ckpt_dedup_results.json`): adjacent checkpoints of a real run share **exactly zero** 64 KiB blocks of weights, distant zero, the two weight copies inside one checkpoint zero, cross-run control zero, optimizer state 0.002 % excluding zero blocks. With no sharing there is no shared key, **per-object keys are affordable and per-object crypto-shredding is restored**, and `K_rdom`, its `HKDF(K_rdom, "chunk" ‖ sid)` chain, its compactible shred store, the within-domain dedup restriction and the declare-`rdom_rule`-at-ingest trap are retired with it. This was the hardest unsolved item in the design and the measurement removed it rather than solving it | **The redaction domain remains the governance atom — only the key mechanism is retired.** It demotes from a KEK to a catalogue-side label naming which object keys are destroyed together, and every place that *counts* domains must keep counting domains. The shred unit and the packing unit no longer need decoupling because the shred unit and the addressing unit now coincide — but see `SPECIFICATION.md` §8.4 and §9.5, where that coincidence opens two holes. |
| Salted redactable Merkle roots | A published citation is not a confirmation oracle; a redaction proves a leaf redacted while the root still verifies; destroying the object's key destroys the salt *(2026-09-19: was `K_rdom`; rename only)*, so the identifier does not survive the erasure it documents. |
| Repair of one site is **6,763 drive-hours = 8.6 % of the plant-year** (MEASURED 2026-09-19, `eval/results/plant_contention.json`) — long in **duration** (~7 weeks at zero global coding margin) but modest in **drive-hours** — and it is **WAN-bound, not drive-bound** | **CORRECTED: retrieval is the scarce resource, not obligation.** This row previously read "Repair of one library is 10⁴–10⁵ drive-hours … the fabric's own obligations are the largest consumer of the scarce resource". The measured figure is below the stated low end and 15× below the high end, and the conclusion is inverted: all standing obligations together are **8.5 %** of the plant-year, while retrieval alone is **73 % clustered and 275 % scattered at 100 TB/day**. Repair remains a reserving tenant — because its drive-hours are *concentrated* into a rebuild window, not because they are large — and the capacity the fabric must ration is agent reads, whose cost is fixed at write time by placement. |
| Index proven at 10⁶ files, in-heap; LSM sharded by prefix for xorb/place/loc/lease/shred/dedup | Nothing agent-facing may be O(files) in the index. Runs, XorbSets and in-xorb chunk tables carry the weight. |
| Custody is Shamir `t`-of-`n` with no resharing; at n=12, t=7, 5 %/yr share loss, ~34 % of ten-year-old citations become undecryptable | Key rot, not media rot, is the ten-year failure. Decryptability horizon is a published metric. |

---

## 3. Nouns

Fields are given exactly. `▢` = substrate-only, never named by an agent. Ids are raw 16-byte values in the index, not hex strings.

### 3.1 Substrate

```
▢ Chunk      { sid = HMAC(K_mac, plaintext), len, obj_id, xid, cidx }
             -- 2026-09-19: `rdom` -> `obj_id` (K_rdom retired). `xid` and `sid` BOTH stay:
             --   xid is the chunk's reference to its containing xorb and nothing retires it;
             --   sid is retained pending the deliberate, WORM-permanent decision recorded at
             --   STORAGE-DIRECTION's xorb wire format.
▢ Xorb       { xid = HMAC(K_mac, sid_0‖…‖sid_{n-1}), k, m, local_group_id, shard_len,
               chunk_count, obj_set (roaring), tier: DISK|TAPE,
             -- obj_set inherits the SPECIFICATION 7.1 scale hole: it is the same set that
             -- sizes the on-media index, and object cardinality is far above domain cardinality.
               state: OK|REDACTED|LOST, contiguity_class, created_seq, created_term }
▢ Fragment   { frag_id = H(xid‖i), i, holder_site, media_class, vsn, tape_position,
               sha256, bytes, retain_until, last_verified, state: OK|BAD|MISSING }
▢ LocalGroup { lg_id, locus, xids, parity_frags }        -- D10 restored; see §6.3
```

Xorb wire format, IV construction (32-bit session id ‖ 64-bit counter from a durably reserved block), per-chunk AEAD under ~~`HKDF(K_rdom, "chunk"‖sid)`~~ **the object's key `K_obj`** *(2026-09-19, `eval/results/ckpt_dedup_results.json`)*, and the in-xorb encrypted chunk table are unchanged from the substrate specification.

### 3.2 Content and governance

```
Lineage {
  lineage_id, key_id, key_epoch, custody_ref
  head_v, head_vid, head_seq, head_term, version_count, file_count, byte_count
  k, m, chunk_avg, pack_policy, local_group_policy
  -- ~~rdom_rule: "lineage" | "subject" | "<field>"   -- declared at ingest~~
  -- RETIRED 2026-09-19 (eval/results/ckpt_dedup_results.json): per-object keys are the only
  -- mode, so there is nothing to declare and no one-way door. What replaces it is a non-key
  -- label used only to group object keys for a single destroy:
  consent_unit: "subject" | "<field>"                 -- catalogue label; no key material
  tape_affinity: RETENTION | ACCESS                   -- resolves the cartridge-grouping conflict
  catalog_visibility: INDEX_READABLE | CUSTODIAN_ONLY
  materialisation_policy { allowed_loci[], allowed_jurisdictions[], require_attestation }
  provenance_policy { accepted_classes[], require_author_attestation }
  declared_splits[]                                    -- e.g. train/val/test; physically separated
  branches{}, tags{}, gc_epoch, shred_epoch
}

RedactionDomain (rdom) {                              -- GOVERNANCE RECORD ONLY, 2026-09-19:
                                                      -- names a set of object keys destroyed
                                                      -- together; carries no key material; can be
                                                      -- regrouped at any time. `key_epoch` struck.
  rdom_id, lineage_id, rule_value, ~~key_epoch~~,
  state: LIVE | SHREDDED, ordered_seq, executed_seq, authority, approver_set, sigs[]
  -- state/ordered_seq/executed_seq/authority/approver_set/sigs ALL STAND: that is the audit
  -- record, and SPECIFICATION 11.1 requires a 2036 reader to distinguish an audited erasure
  -- from media loss, and forbids laundering a breach as a redaction. The audit must survive
  -- the data.
}

Version (VersionRoot cnode) {
  lineage, v, parent_v, parent_vid, branch, term, seq, ts, by,
  runs[ { cid, xset_cid, lvl, rseq, min_rseq, max_rseq, lo, hi, n, tomb, bytes } ],
  fc, bc, ux_hll_cid, cd = merkle(runs[]), cod { k, m, chunk_avg, key_epoch, fmt }, cmp
}

FileEntry (inside a ManifestRun) {
  rel, file_ord, flags, size, sha256(plaintext), mtime, rdom,
  author { institution, actor_chain_digest, attest_cid },
  provenance_class: INSTRUMENT | CURATED | AGENT_DERIVED | EXTERNAL | QUARANTINED,
  nspans, spans[ { xid, cidx, nchunks, bytes } ]  OR  span_root
}
```

`file_ord` is new and load-bearing: a dense, never-reused per-lineage ordinal stamped at first commit. It is 4 bytes at ingest and it is what makes Coverage a roaring bitmap rather than a distributed set.

`rel` is an **ordered locality key**, not a namespace. There is no directory, no `ls`, no prefix walk. Prefix predicates are admissible because runs are sorted by `rel` and pruning is cheap — the hierarchy is a physical clustering artefact, honestly named, not a browsing affordance restored under another word.

### 3.3 Naming a set

```
Cut {                                   -- resolves cross-lineage extracts
  cut_id, members[ { lineage_id, v, vid, index_seq, term } ], declared_at, reserved_until,
  quorum_cert, note: "declared consistent cut; component versions may differ in wall clock
                      by each lineage's commit cadence"
}

FrozenSet {                             -- the substrate's Extract, extended
  fset_id = sha256(canonical(FrozenSetCert minus sigs))
  cut_id, selector { grammar_v, kind, expr, seed?, limit?, order }, class: cite|run|scratch
  ordinal_space { n_leaves, leaf = (lineage, file_ord, span_block?) }
  root_pub (salted redactable Merkle), leaf_salt_cid, enum_cid, xorbset_cid
  resolved { file_count, byte_count, chunk_count, xorb_count, pin_bytes, amplification }
  state: RESERVED | PINNED | RELEASED | EXPIRED | PARTIALLY_REDACTED
  pinned_until, parent_fset, issued_to_purpose, idem_key, index_seq, quorum { signers[], sigs[] }
}
```

Selector grammar is closed, versioned, total and deterministic: `prefix`, `glob`, `list-digest`, `attr` over run-entry fields, `span(rel, lo, hi)`, `author_in`, `provenance_class_in`, `sample(seed, n)`, `all`. Relative and context-dependent terms are rejected at parse time; `limit` requires an explicit `order`; `sample` uses a named PRF over `(seed, leaf)`.

`span(...)` is the restoration of sub-file access. It resolves at freeze time into a frozen ordinal range, so a 512×512 tile of a gigapixel slide, or a CRAM range, is still a frozen, citable, coverage-charged, receiptable set. Removing byte ranges as "a human affordance" is wrong: ranged access is forced by physics, and the dominant machine access patterns in this corpus are sub-file.

Citation form: `gfs:1c:<cut>#<fset_id>` (cite class), `1r` (run, TTL), `1s` (scratch). The class is in the identifier because a reader of a paper does not hold the body.

### 3.4 The new core

```
Transform {
  transform_id = H(canonical{image_cid, entry, contracts, determinism, resources})
  image_cid                     -- THE IMAGE IS STORED IN THE FABRIC, not referenced in a registry
  entry, params_schema
  determinism: BITWISE | STATISTICAL{seed_params, tolerance, env_class} | NONDETERMINISTIC
  resources { cpu, mem_gb, gpu_class, walltime_s }
  input_contract  { accepts[], access_mode: STREAM|RANDOM, passes }
  output_contract { kind: ROWS{schema, min_cell, no_row_level, max_rows}
                        | ARTEFACT{media_type, max_bytes, review_class}
                        | MODEL{arch, max_params, review_class} }
  rdom_rule: PRESERVE | MIX | CERTIFIED_DEIDENT{certifier, cert_ref}
  network_policy: DENY_ALL (no exception)
  attestation { required: NONE|TDX|SEV_SNP, measurement }
  approvals[]                   -- quorum approval for a review_class, where required
  retention = union of retentions of Derivations citing it
}

Derivation {
  derivation_id = H(canonical{ inputs[], transform_id, params, codec, env_class })
                  -- NOT a hash of the output
  inputs[]        : fset_id | derivation_id           -- a DAG closed under the fabric
  declared_shape  { est_bytes, est_leaves, output_schema }
  rdom_closure    : the set (or derived domain) of contributing redaction domains
  dua_closure     : join (most restrictive) of inputs' governance
  provenance_class: AGENT_DERIVED (always), author { purpose_id, task_id, actor_chain_digest }
  residency       : ABSENT | PARTIAL{ordinal ranges} | RESIDENT{residency_ids[]} | PINNED{until}
  build_model     : fleet-accumulated { compute_s_per_input_GiB, out_bytes_per_in_GiB,
                                        peak_mem, n_observations, p50/p90 }
  rebuildable     : { feasible, cost_interval, input_closure_shape, blocking_reason, evaluated_at }
  last_built      : { receipt_id, at, actuals }
  state           : DECLARED | LIVE | STALE_BY_SOURCE | UNREBUILDABLE
}
```

Three fields carry weight.

`transform.image_cid` is stored, not referenced. Every prior design named an `image_digest` against an external registry that will not exist in 2036; a recipe whose image is gone is worthless. Image retention is bound to the union of retentions of the Derivations that cite it.

`determinism` is the mechanism, not a caveat. Only `BITWISE` derivations may be evicted and silently rebuilt, because rebuilding preserves identity; that is where the capacity win lives (tokenisation, filtering, projection, resampling, format conversion — the bulk of derivative volume). `STATISTICAL` and `NONDETERMINISTIC` derivations may **never** be silently rebuilt, because a rebuild changes the bytes under a citation; the fabric either keeps them or refuses with `NOT_REBUILDABLE_TO_SAME_BYTES` and requires an explicit re-cite. "May I throw these bytes away?" becomes a checkable property.

`rdom_rule` on the transform decides taint semantics, and the distinction maps exactly onto what transforms do. *(Naming note, 2026-09-19: this `rdom_rule` — `PRESERVE | MIX | CERTIFIED_DEIDENT` on a Transform — is a **different field** from the retired `Lineage.rdom_rule` (`"lineage" | "subject" | "<field>"`), which selected key granularity and is gone. This one selects derivative taint semantics, no measurement bears on it, and it survives unchanged. The name collision is noted rather than fixed, because renaming an agent-facing interface field is design.)*

- **PRESERVE** — a row-wise transform. Each output leaf inherits its input leaf's **consent unit**. One withdrawal kills one subject's derived rows *(but see the §14.10 hole: under `K_rdom` that death was **cryptographic and structural**; under per-object keys it becomes a **catalogue obligation**)*.
- **MIX** — an aggregate. The output gets a derived key that is **derived and never stored**: `K_derived = HKDF(K_obj_1 ‖ … ‖ K_obj_j, "derived"‖derivation_id)` over the contributing objects' keys *(2026-09-19: was `HKDF(K_rdom_1 ‖ … ‖ K_rdom_j, …)`)*. Destroying any contributing key makes the derived key underivable, so AND-survival is structural rather than procedural, costs zero storage, and reaches derivatives on write-once media. **This is the one part of the `K_rdom` construction that survives its retirement, because it never depended on key *sharing*, only on key *destruction*.**

  > **HOLE OPENED 2026-09-19, RECORDED NOT FILLED.** Per-object keys can in principle serve this role, but **the closure is then over OBJECTS rather than over domains**, and the closure size, its enumeration cost, the stability of the contributor enumeration order (`j` is now an object list and the concatenation is order-dependent), and what happens when one contributing object's key is destroyed years later are all unspecified. `rdom_closure`, `rdom_closure_size` and `expected_underivable_by` on every Residency and Receipt depend on this, as does §14.9's replay arm distinguishing a consent withdrawal from a nondeterministic transform. **Note the counting rule that must not drift:** `|rdom_closure|` in the `derive` threshold and the half-life arithmetic at §14.11 count **consent units**, not object keys (`SPECIFICATION.md` §9.7) — if `j` silently follows key granularity the hazard is over-stated by the objects-per-subject ratio. **This is the one place where retiring `K_rdom` takes away more than it gives back, and §12 claims this extension as one of this document's genuinely new contributions and as the closure of the laundering hole. No replacement is proposed here.**
- **CERTIFIED_DEIDENT** — a certified de-identification transform breaks the closure, with the certifier and the approver quorum on the record.

### 3.5 Residency, locus, plant

```
Residency {
  residency_id, subject: fset_id | derivation_id, locus, shape: STREAM{order}|RANDOM|SHARDED{n,i}
  state: PLANNING | STAGING | PARTIAL | READY | EXPIRING | RELEASED
  wave_frontier, bytes_staged, bytes_total, undeliverable_cid
  avail_until (monotone-raised only), refcount, attachers[purpose_id], eviction_class
  payer_ledger { first_payer, attach_credits[] }
}

Locus {
  locus_id, site, institution, mesh_agent,
  compute { cpu, mem, gpu_class, gpu_free }, stage { total, free, pinned, pressure },
  sandbox_kinds[], attestation { tee, measurement } | NONE,
  jurisdiction_tags[], permitted_dua_classes[], accepted_transform_classes[],
  local_groups[]                                  -- lineages this locus can decode alone
}

ScarcitySchema {                                  -- versioned; agents read it, never hard-code it
  schema_v, terms[ { name, unit, conserved: bool, reservable: bool, description } ]
}
-- v1 terms: sweep_drive_seconds@library, mounts, core_bytes@segment, stage_byte_days@locus,
--           gpu_seconds@locus, index_ops, quorum_ops, pin_bytes, coverage_leaves,
--           rdoms_touched, review_units

Calendar {
  as_of, schema_v,
  per_library { drives, residual_fraction, reserved_for_obligations, queue_depth_bucket,
                projected_waves[ { window, cartridge_group, intents_coalesced } ] },
  segments[ { segment_id, capacity, committed, residual } ],
  federation_daily_byte_budget,
  obligations[ { kind: REPAIR|SCRUB|GC|REDACT_COMPACT|MEDIA_MIGRATION,
                 scope, share_held, projected_completion } ],
  durability_debt { lineages_degraded, projected_repair_window }
}
```

Everything an agent reads from the Calendar is **bucketed and epoch-batched**: queue depth as a bucket, not a number; no cartridge identifiers; no per-peer instantaneous load. A truthful cost model is an oracle over physical layout and over other institutions' current activity, and that oracle is a cross-tenant covert channel and a targeting map. The planner keeps the detail; the agent gets derived bounds.

### 3.6 Principals, planning, work

```
Purpose {                                -- THE PRINCIPAL. Not the agent.
  purpose_id, authority { kind: IRB|DUA|PROTOCOL|OPERATIONS, ref }, approver_quorum_cert,
  scope { cut_constraint?, selector_predicate, rdom_scope, provenance_classes[] },
  window { not_before, not_after },
  loci { allowed[], jurisdictions[] }, output_review_class,
  caps { coverage { leaves, bytes, rdoms, fraction_of_scope },
         differencing { queries_per_leaf },
         physical { sweep_drive_seconds, core_bytes, stage_byte_days, gpu_seconds,
                    pin_bytes, index_ops },
         structural { max_token_depth, max_fanout, max_concurrent_jobs } },
  pledge_draws[ { institution, entitlement, consumed } ],
  revocation_points[]
}

Task {                                   -- the durable work object; agents are transient
  task_id, purpose_id, parent_task, opened, state,
  derivation_graph[], intents[], jobs[], coverage_contribution
}

Token {                                  -- attenuable capability; CEILINGS, never balances
  purpose_id, task_id, parent_token_hash, actor_identity, depth, fanout_budget,
  caveats[ narrower_selector | shorter_ttl | lower_ceilings | locus_subset
           | transform_subset | sink_subset ],
  revocation_point, not_after, sig
}

Coverage {                               -- the conserved union
  purpose_id,
  per_lineage { roaring bitmap over file_ord },         -- exact, ~125 KB dense at 10^6 files
  per_lineage_spans { roaring over (file_ord, 1 MiB block) },
  rdoms_touched (roaring over rdom ordinals),
  differencing (count-min over leaf -> distinct predicates evaluated),
  totals { leaves, bytes_delivered, bytes_staged }, caps, state
}

Prospectus {                             -- ADVISORY. Never binding, never reserving.
  prospectus_id, target, purpose_id, token_fingerprint, issued_at, index_seq,
  scarcity_schema_v, cost_model_v, advisory: true,
  verdict: ADMISSIBLE | ADMISSIBLE_IF[precondition] | REFUSED,
  shared_cost { ... },                   -- invariant across strategies (the recall)
  strategies[ { id, kind: DELIVER | COMPUTE_AT | HYBRID | ENTAIL | ATTACH,
                locus, differentiating_cost{...}, horizon { p50, p90 } as intervals,
                preconditions[], rejected_because? } ],
  binding_constraint: COVERAGE | DIFFERENCING | PLEDGE | PLANT | STAGE | CUSTODY
                    | MATERIALISATION_POLICY | REVIEW | PROVENANCE | UNREBUILDABLE
                    | SAMPLE_ORTHOGONAL_TO_PACKING | DEGRADED_PLANT,
  rewrites[ { description, target_prime, delta_cost, delta_horizon } ],
  calendar_position { lane, queue_position, projected_window, coalesces_with },
  evidence[ { term, basis: MEASURED|MODELLED|ASSUMED|UNKNOWN, observed_at,
              model_error_p50, model_error_p90 } ],
  signature
}

Intent {                                 -- standing demand; the fabric's scheduling input
  intent_id, purpose_id, task_id, target, horizon { earliest, latest },
  policy { priority_lane: CLINICAL|INTERACTIVE|BATCH|BACKGROUND,
           on_infeasible: WAIT|DEGRADE{max_subsample_declared}|WITHDRAW },
  coalesce_key, state: OPEN|SCHEDULED|RUNNING|SATISFIED|WITHDRAWN|REFUSED,
  position, projected_window, coalesced_with[]
}

Job {
  job_id, target, sink, purpose_id, task_id, token_fingerprint, prospectus_id,
  state: QUEUED|PLACED|STAGING|RUNNING|PARTIAL|DRAINING|DONE|CANCELLED|REFUSED|ABANDONED,
  residency_id?, wave_frontier, undeliverable[ { leaves, reason, authority } ],
  actuals { per scarcity term }, revised_horizon, consumed_set_root, receipt_id
}

Sink { kind: RESIDENCY{locus} | STREAM | DERIVATION{derivation_id} | ASSERTION,
       contract = the Transform's output_contract, destination_policy_check }
```

`Offer` (the fabric proposing rather than responding):

```
Offer { offer_id, kind: RESIDENCY_ATTACH | IMMINENT_WAVE | COALESCE | REPACK_WINDOW,
        subject, window, cost_interval, expires }
```

### 3.7 Evidence

```
Receipt {
  receipt_id, job_id, purpose_id, task_id, actor_chain[], token_fingerprint, prospectus_id,
  target { cut_id, fset_id | derivation_id }, transform_id, params_digest, image_cid,
  consumed_set_root,                     -- Merkle over leaves actually delivered
  coverage_delta_digest, bytes_delivered, bytes_staged, actuals{},
  output { digest, kind, review_outcome? }, attestation_quote?,
  holder_epoch_proofs[ { holder, epoch_head, inclusion_proof } ],
  locus_sig, started, ended, outcome, epoch_id, leaf_index
}

Checkpoint { epoch_id, receipt_tree_root, version_log_root, holder_epoch_heads[],
             cross_sigs[≥3 institutions], published_off_fabric, worm_refs[] }

Assertion {                              -- the promoted catalogue answer
  assertion_id, question (canonical), cut_id, index_seq, staleness_bound,
  answer, disclosure_control { min_cell, quantisation, suppressed },
  coverage_delta_digest, basis, signer, sig
}

FabricAttestation {                      -- what an AGENT gets when auditing the FABRIC
  subject, quorum_certs[], index_seq, staleness_bound, replica_divergence_report,
  pop_samples[ { site, sampled_at, fragments_challenged, passed } ],
  custody_health { t, n, live_shares, last_reshare_epoch, decryptability_horizon },
  plant { degraded_lineages, obligations_in_flight }
}
```

---

## 4. Verbs

38 verbs in eight groups. Every one is published through the existing `@CrescoAction` capability inventory, so the tool catalogue is generated rather than written. **Every verb takes a token. There is no free tier.**

### 4.1 Catalogue — governed, metered, receipted

| Verb | Signature |
|---|---|
| `capabilities` | `(token) -> Capabilities { verbs[], scarcity_schema_v, cost_model_v, selector_grammar_v, limits, calibration, contract_v }` |
| `describe` | `(lineage_id, token) -> LineageDescriptor { schema summary, rdom_rule, declared_splits, tape_affinity, materialisation_policy, provenance_policy, versions{head,tags}, custody_health, my_purposes[], my_coverage }` |
| `versions` | `(lineage_id, since?, limit, token) -> [VersionRef]` |
| `diff` | `(v_a, v_b, selector?, token) -> Delta { added, removed, changed, bytes_new, runs_changed }` — O(changed); returns **aggregate counts only** unless the caller's Purpose already covers the leaves |
| `ask` | `(question, token) -> Assertion` — `question ∈ COUNT | EXISTS | HIST{field,bins} | QUANTILE | DISTINCT | KNN_CANDIDATES{vector,k}` over a `Cut` + selector |
| `enumerate` | `(fset_id, cursor, n, token) -> Page<Member{lineage, rel, size, sha256, rdom, provenance_class, author}>` |

`ask` and `enumerate` are the honest replacement for "there is no enumeration surface". Enumeration exists — every prior design shipped a paginated list and called it something else — and it is governed: scoped by predicate containment, charged into Coverage leaf-for-leaf, charged against the differencing budget, subject to minimum cell size and quantisation, and receipted as an `Assertion`. An aggregate over a set folds that whole set into the union, which correctly makes a corpus-wide COUNT expensive in the only currency that bounds disclosure, and which destroys the *breadth* half of a differencing attack by construction. The *depth* half is bounded by `caps.differencing.queries_per_leaf`, maintained as a count-min sketch.

The catalogue is data derived from plaintext, and treating it as free metadata is how every design in this space leaks. What Entail does **not** solve: index nodes serving `INDEX_READABLE` lineages hold `K_meta`, which reveals the path tree and chunk ids to institutions that may not read the content. `CUSTODIAN_ONLY` lineages restrict catalogue service to custodian institutions at the cost of catalogue latency and availability. See §12.

### 4.2 Freezing — naming a set

| Verb | Signature |
|---|---|
| `cut` | `(members[{lineage_id, v|tag}], token) -> Cut` — two-phase; reserves every named version as a GC root before returning |
| `freeze` | `(cut_id, selector, class, idem_key, token) -> FrozenSetRef{fset_id, state: RESERVED, job_id}` |
| `compose` | `(op, inputs[fset_id], params, token) -> FrozenSetRef` — `op ∈ UNION|INTERSECT|MINUS|SPLIT{seed,ratios}|STRATIFY{field,n,seed}|SAMPLE{seed,n}` |
| `shape` | `(fset_id | derivation_id, token) -> Shape` |
| `resolve_citation` | `(citation, token) -> { cert, redaction_chain_head, index_seq, staleness_bound, availability }` |

`freeze` is asynchronous by construction (reserve → enumerate → build `ExtractEnum` with spans inlined → compute both roots → check amplification → apply retention at bucket granularity → custodians independently re-materialise and sign → `PINNED`). It is charged (`index_ops`, `pin_bytes`) and idempotent on `idem_key`, so retries do not double the pinned capacity. `scratch` and `run` classes live in the LSM with a TTL; only `cite` class enters heap.

`shape` returns a **bound**, not a number:

```
Shape { leaves, bytes, xorbs, sites,
        contiguous_runs, wraps_touched, swept_bytes { lo, hi },
        sweep_drive_seconds { lo, hi, basis },
        residency_coverage[ { locus, fraction, expires } ],
        pin_amplification, pack_alignment: ALIGNED|PARTIAL|ORTHOGONAL,
        verified_fraction, evidence_age }
```

Exact refinement is available as a priced job, never as a free synchronous call: computing an exact physical footprint for an arbitrary predicate means expanding leaves to chunks to xorbs to cartridge positions, and a verb that does unbounded work proportional to the data it describes cannot be free.

`compose(SAMPLE)` is **refused by default** with `SAMPLE_ORTHOGONAL_TO_PACKING` and the `1-(1-p)^c` arithmetic attached. Uniform random sampling is adversarial to any storage system whose packing unit exceeds its record — permanently, on every medium with a block — and offering it as the remedy when a plan is infeasible, as three of the prior designs did, is exactly backwards. It is admissible only when the split was declared at ingest so the shards are physically separated, or when accompanied by a priced `repack`.

### 4.3 Entailment

| Verb | Signature |
|---|---|
| `register_transform` | `(image_bytes|image_ref, entry, contracts, determinism, resources, rdom_rule, attestation_req, token) -> Transform` |
| `derive` | `(inputs[], transform_id, params, declared_shape, idem_key, token) -> Derivation` |
| `entail` | `(derivation_id, token) -> Entailment { rebuildable, cost_interval, input_closure_shape, blocking_reason, decays_at }` |
| `pin` | `(derivation_id, until, class, token) -> Derivation` |
| `evict` | `(derivation_id, token) -> Derivation` — residency changes; **identity and citation survive** |
| `promote` | `(derivation_id, lineage_id, branch, token) -> Job` — turn a derivative into curated, versioned state |

`derive` is O(1): one journal entry, no bytes, no drive time, no quorum. It deduplicates by construction, which is what collapses the thundering herd: 10⁴ agents that write the same recipe write the same `derivation_id` and attach to one job. ~~Content addressing of *work* does for the herd what content addressing of *bytes* does for storage~~ — no join primitive, no refcount race, no first-payer free-rider problem.

> *2026-09-19: **the mechanism survives and is untouched by the dedup retirement.** `derive` content-addresses WORK — identical recipes produce one `derivation_id` and one job — which is unaffected by the finding that identical BYTES essentially never recur (`eval/results/ckpt_dedup_results.json`). **The struck analogy is now false and is corrected:** content addressing of work collapses the herd; content addressing of bytes was measured and does not, which is why it was retired for content and kept only for metadata cnode identity. Recipe dedup is if anything MORE valuable now: with checkpoints neither deduplicable nor recomputable, the 40 TB-working-set-as-names result (§14.4) is the only thing standing between twelve variants and twelve copies.*

`entail` is live and decaying. Rebuildability degrades as inputs sink to tape, scatter across cartridges, lose a local group, or have a contributing **object key** shredded *(2026-09-19: was `K_rdom`; rename only)*. `blocking_reason` is one of `INPUT_UNREBUILDABLE`, `INPUT_REDACTED`, `TRANSFORM_IMAGE_LOST`, `NONDETERMINISTIC`, `PLANT_DEGRADED`, `CUSTODY_BELOW_THRESHOLD`.

Invalidation needs no new machinery: inputs are named, so a redaction marks every dependent `UNREBUILDABLE` transitively and flags every resident dependent for shredding, and a corrected source marks dependents `STALE_BY_SOURCE`, by walking a DAG the index already holds.

### 4.4 Planning — advisory, metered, never reserving

| Verb | Signature |
|---|---|
| `prospect` | `(target, constraints{deadline?, caps?, loci?, require_strategies[]?}, token) -> Prospectus` |
| `calendar` | `(scope, horizon, token) -> Calendar` |
| `offers` | `(token) -> [Offer]` |

`prospect` costs `index_ops` and is rate-limited per Purpose. It performs **no quorum round and no cross-institution RPC**: custody liveness comes from a cached, signed beacon, and link/plant state from the epoch-batched Calendar. A planning verb that reflects load onto fifty third parties' custody services is a free amplifier, and a planning verb that signs with a quorum makes the cheapest call in the API invoke the most expensive mechanism in the substrate.

### 4.5 Scheduling — the standing relationship

| Verb | Signature |
|---|---|
| `intend` | `(target, horizon, policy, token) -> Intent` |
| `intent_status` | `(intent_id, token) -> Intent` |
| `withdraw_intent` | `(intent_id, token) -> {}` |

Tape scheduling is an offline problem: the optimal mount plan is computed over the *whole set* of pending requests, and adding one request changes the plan for all of them. Every prior design converted a batchable request into a scheduled one at the moment of claim, which is how 10⁵ individually-serpentine-optimal passes become a cartridge-exchange storm. `intend` is the primitive that lets the fabric learn tomorrow's demand curve today and coalesce it into one pass per cartridge group per window. It is also what makes "no, but at 03:00, and here is your position" expressible — every prior design could only refuse instantaneously and terminally.

### 4.6 Realisation — the only bytes

| Verb | Signature |
|---|---|
| `realise` | `(target, sink, draw, token) -> Job \| Refusal{constraint, arithmetic, rewrites[], retry_after}` |
| `job_status` | `(job_id, token) -> Job` |
| `open` | `(job_id, cursor, max_bytes, token) -> { frames[], next_cursor, eof, frontier, lease_expires }` |
| `attach` | `(residency_id, token) -> Job` |
| `extend` | `(job_id \| residency_id, seconds, token) -> Lease \| Refusal` |
| `release` | `(residency_id \| job_id, token) -> Receipt` |
| `cancel` | `(job_id, token) -> Receipt` |
| `repack` | `(fset_id \| derivation_id, target_affinity, token) -> Job` |
| `localise` | `(lineage_id \| fset_id, locus, token) -> Job` — build a local reconstruction group |

`realise` admits against four gates in order, and the refusal names which bound: **Coverage** (union + differencing), **Pledge** (the institution's entitlement, per contributing institution), **Plant** (residual after the fabric's reserved obligations), **Policy** (materialisation loci, jurisdiction, provenance class, output review class, custody threshold). It then enqueues into a lane and returns a position and a projected window. It does not reserve drive-seconds; held-but-unused physical capacity is billed continuously as byte-days and lane-seconds, so abandoning is never cheaper than releasing and hoarding is self-limiting.

`open` is the only streaming read, flow-controlled by the consumer, delivered in physically optimal order unless the sink pinned an order, resumable by cursor — with the cursor scoped to the job's read set and an explicit `REPLANNED` transition if a holder is lost mid-stream.

`attach` is the herd primitive at the byte layer, complementing `derive` at the work layer. Concurrent `realise` calls on the same `(target, locus)` coalesce into one `Residency` with a joiner list; the first payer is credited as joiners attach, and a late joiner pays a bounded join fee — neither nothing (which invites free-riding and a deadlock-by-politeness equilibrium on cold data) nor everything.

`localise` restores hierarchical LRC (D10), which the earlier designs dropped. Without it, `COMPUTE_AT` saves only the egress leg (~10 % of input bytes at k=10), because one-fragment-per-failure-domain means no site can decode alone. With a local group at a designated compute locus, that locus decodes alone and shipping computation genuinely moves zero input bytes. This is the difference between the fetch-versus-ship decision being real and being rhetoric.

### 4.7 Writing — curated state

| Verb | Signature |
|---|---|
| `open_branch` | `(lineage_id, from_version, token) -> Branch` |
| `stage` | `(branch_id, entries[{rel, source, ~~rdom_hint~~, author, provenance_class, pack_hint}], token) -> StageReport{new_bytes, ~~dedup_ratio~~, ~~rdom_assignment~~, placement_preview, future_read_cost}` |
| `commit` | `(branch_id, parent_v, token) -> Version \| Conflict{head, conflicting[{rel, sha256}]}` |
| `tag` | `(lineage_id, v, name, token) -> Tag` |

> *2026-09-19: `dedup_ratio` is **RETIRED** (`eval/results/ckpt_dedup_results.json`) — it would return ~0 on every call, and a constant field teaches agents to ignore the report. `rdom_assignment`, and `rdom_hint` on the input side, are **RETIRED with `K_rdom`**. **What `stage` should report in their place is NOT decided here:** the sharing that actually occurs is whole-file reuse at 13.4–47.9 % on real version history against a 0.8 % mean marginal contribution from chunk-level CDC (`eval/results/cdc_measure.json`), and per-object key assignment has to be reported somehow — but naming and shaping agent-facing interface fields is design, not reconciliation, and is recorded as open.*

The write path is admitted and billed exactly like the read path — `stage` draws `stage_byte_days`, `index_ops` and pledge entitlement, and any ingest-time extractor is a registered `Transform` under an output contract, so the write path cannot be used as an unpriced GPU farm or as a sequencer denial of service.

`pack_hint` is mandatory rather than advisory for lineages with declared splits. **MEASURED 2026-09-19 (`eval/results/plant_sim.json`, `eval/results/plant_contention.json`): co-occurrence clustering is worth 3.8× in GB per drive-hour on top of batching and media-ordering (172.3 → 653.3), and it moves delivered plant capacity from 11.9 PB/yr to 45.0 PB/yr. It is not an optimisation; it is the difference between the plant working and being oversubscribed 2.75× at 100 TB/day.** Clustering is also effectively irreversible — re-clustering costs ~19 fabric-days per PB *(basis unstated in this document and unmeasured; the plant harnesses price scrub, repack, migration and rebuild, not re-clustering — the figure is left as written rather than replaced with a differently unattributed one)* — so the single most consequential decision in the system cannot sit on the path of least resistance. `stage` returns `future_read_cost` for the declared read class, which is the only moment at which that cost can be cheaply influenced.

### 4.8 Governance and evidence

| Verb | Signature |
|---|---|
| `request_purpose` | `(authority, scope, window, caps, loci, review_class) -> Purpose \| Pending{have, need}` |
| `attenuate` | `(token, caveats) -> token` — **offline, no round trip, monotone downward, depth- and fanout-bounded** |
| `revoke` | `(revocation_point, token) -> { invalidated_points[] }` |
| `coverage` | `(purpose_id, token) -> Coverage` |
| `order_redaction` | `(lineage_id, rdom, authority, approver_sigs, token) -> RedactionRec` |
| `receipts` | `(filter, cursor, token) -> Page<Receipt>` |
| `verify` | `(citation \| receipt_id \| derivation_id, mode: LOCAL\|WITH_CHECKPOINT, token) -> VerificationReport` |
| `attest` | `(subject, token) -> FabricAttestation` |
| `challenge` | `(fset_id \| lineage_id, sample_n, token) -> ProofOfPossession` |

`attenuate` narrows scope offline, as it must — verification belongs off the hot path and sub-agents must never share credentials. It does **not** partition quantity, because it cannot: quantity is drawn online at admission against the Purpose. Tokens carry ceilings; the Purpose carries the balance. `max_token_depth` and `max_fanout` are offline-checkable and monotonically non-increasing, so a 10⁴-deep chain is invalid rather than merely expensive to verify.

`attest` and `challenge` are the verbs no prior design had: provenance built for a third party auditing the *agent*, never for an agent auditing the *fabric*. An autonomous agent that cannot establish that what it just read is what the fabric claims has no basis for anything it does afterwards. `challenge` lets it demand sampled proof-of-possession from holders directly.

---

## 5. How an agent plans

### 5.1 What it gets, and what it does not

The agent does not get a price it can rely on. It gets:

1. **A feasibility boundary.** `ADMISSIBLE` / `ADMISSIBLE_IF` / `REFUSED` with the binding constraint named. This is decidable and cheap — coverage, pledge, plant residual, policy and custody threshold are all index-resident facts — and it is robust to the cost model being wrong.
2. **A cost interval with a per-term basis and the model's own historical error.** `MEASURED` (with sample age), `MODELLED` (from this library's last N passes, with p50/p90 error), `ASSUMED`, `UNKNOWN`. Prior art: the Network Weather Service, which published its forecasters' error for exactly this reason. Entail's only addition is that the basis is labelled *per term inside a retained artefact*, so an auditor can later see which terms were guesses.
3. **Concrete offered rewrites.** This is the actual product of planning on this substrate. The gap between a naive and a good plan is 30–100×, an agent has no way to learn that from outside, and a system that silently accepts a 3 %-selectivity recall and delivers it in 2.8 hours teaches nothing. A refusal that reads *"your selector sweeps 85 % of the region at 12 MB/s effective; take `SCAN_AND_FILTER` at the locus for the same drive-seconds and a tenth the core bytes"* teaches the physics, and that instruction gets *more* valuable as agents get better at reading explanations.
4. **A position in a published queue**, with the fabric's own obligations visible as committed load.

### 5.2 The cost model, exactly

- Headline term is **sweep-adjusted drive-seconds**, per library: `queue_bucket + mounts × mount_latency + (max_wrap − min_wrap) × wrap_traverse + swept_bytes / rate`. Mount count is reported but is not the unit; on serpentine LTO it is under 1 % of a scattered pass.
- **Horizon is the k-th order statistic**, not a sum of means: `E[max of k]` over per-library `(queue + mount + sweep + stream)` distributions, with an explicit correlation term keyed to shared drivers (a repair wave, a GC wave, a concurrent large residency). With k = 10 on U(30,120) mounts, the expected max is 112 s, not 75 s; queue waits compound multiplicatively because every library must have a free drive.
- **The WAN is a shared-segment model, not a pairwise matrix.** Transfer cost is `max( bytes/dest_uplink, bytes/min_segment_residual, max_h((bytes/k)/bw(h)) )`. Fifty sites each measuring 10 Gb/s pairwise do not collectively have 500 Gb/s; they have one core. The Calendar publishes a federation daily byte budget so an agent planning a 500 TB scan learns it is asking for days of the state's entire archive bandwidth *before* it commits.
- **The fabric's obligations are a reserving tenant.** Each library publishes a non-tradeable reserved fraction for repair, scrub, proof-of-possession, GC and redaction compaction, sized from the measured repair window for one library loss. Agent admission is against the residual; `DEGRADED_PLANT{reason, until}` is a first-class refusal an agent can act on. Without this, either repair starves behind reserved agent work and durability silently degrades, or repair preempts and every horizon in the fabric is wrong for weeks. Preemption, where it happens, is **cartridge-atomic only** — preempting mid-sweep costs a second mount and makes the herd worse.

### 5.3 Fetch versus ship, stated honestly

The `Prospectus` prints the **shared cost** above the strategy comparison, because for cold, tape-resident, k-of-n data the recall is identical under every strategy. Decoding at the consumer costs the same bytes as decoding anywhere else, minus a hop. The three prior designs that made this comparison their centrepiece were comparing a term that does not vary.

What actually varies:

| Strategy | Differentiating cost | Wins when |
|---|---|---|
| `DELIVER` | `output_bytes = input_bytes` of core; `stage_byte_days` at the caller's locus | Reuse across many passes and the agent's locus may hold plaintext |
| `COMPUTE_AT` | `image_cid` transfer + `gpu_seconds@locus` + `output_bytes` of core | `output/input ≪ 1`; or plaintext may not leave; or a local group exists (`localise`) so input bytes are zero |
| `ATTACH` | join fee only | A residency already covers the target at a permitted locus — **the dominant win, and the reason residency is the real lever** |
| `ENTAIL` | rebuild cost against `build_model` | The target is a `BITWISE` derivation whose inputs are warmer or cheaper than its stored bytes |
| `HYBRID` | filter at the sites holding the bulk; deliver the remainder | Selectivity is high and spread is wide |

The genuine axis is therefore **materialise-once-and-reuse versus stream-and-discard, and where** — a residency question, not a storage-versus-compute question. `ENTAIL` as a fourth strategy is the leg no prior design had: *have no bytes at all, and rebuild.* For a `BITWISE` derivation whose inputs are already warm, it is routinely the cheapest option in every term including permanent capacity.

The agent applies its own utility — reuse expectation, deadline value, and its own risk tolerance for a `STATISTICAL` rebuild — because those are its private information and the fabric declines to guess them. The `Prospectus` is retained and is cited by the `Receipt`, so the rejected strategies with their costs survive the decision. That retention is the one part of the quote apparatus worth keeping: an agent cannot be cross-examined later, so its justification must be a by-product of admission rather than a narrative it generates afterwards.

### 5.4 Calibration

`build_model` accumulates per `derivation_id` and per `transform_id` across the whole fleet. Every execution contributes `compute_s_per_input_GiB`, `out_bytes_per_in_GiB` and `peak_mem`. This is the correct lifetime for the measurement: prior designs measured per agent, per request, and discarded it. At 10⁵ agents it is measuring once instead of 10⁵ times.

Cold-tape calibration probes are **refused**. A uniform 1 % sample of a tape-resident extract touches essentially every cartridge the full read touches and costs ~27 % of it, then dismounts, so the real run pays the mounts again — calibrate-then-commit on cold data costs ~1.27× the job it was meant to de-risk, and the cheap alternative (one contiguous cartridge) is correlated with subject, modality and ingest epoch, which is exactly what the measurement must not be. Calibration runs on warm or already-resident sub-extents, or as an in-run first-wave measurement with a `re-prospect` checkpoint that costs zero extra mounts.

---

## 6. Versioning and citation

### 6.1 Structure

Unchanged from the substrate: a `VersionRoot` naming an ordered list of immutable, content-addressed `ManifestRun`s, shadowed by highest `rseq`, so a commit writes one new run plus a ~6 KB root and references every unchanged run by name. Commits are O(changed files) and O(1) quorum rounds at any dataset size. `rseq` lives in the root, not in the run body, so a rebase is a pointer edit rather than a federation-wide re-encode. Diff is O(changed) via `min_rseq`/`max_rseq`. Run boundaries are cut by a keyed content-defined boundary function so successive extracts pinned days apart continue to share most of their runs.

Content addressing is lineage-keyed (`sid = HMAC(K_mac, chunk)`, `xid = HMAC(K_mac, sid₀‖…)`, fragment id `H(xid‖i)`), so v2 references v1's fragments by the same name on the same holders, bit-identical — no re-encode, and critically no tape rewrite.

### 6.2 The citable name

A citation is `gfs:1c:<cut_id>#<fset_id>`, where `fset_id = sha256(canonical(cert minus sigs))` over a closed, versioned, deterministic selector plus the resolved enumeration root.

**This is the RDA Working Group on Data Citation recommendation (Rauber, Asmi, van Uytvanck, Pröll, 2015), implemented.** Version and timestamp the data, persist and normalise the query, hash the query, hash the sorted result set, mint a PID over the pair, verify by hash comparison rather than by re-execution. It is a decade-old published standard in exactly this domain, it is implemented in several research repositories, and three of the four prior designs claimed it as novel. Entail's additions over RDA are three and are small: quorum notarisation instead of a repository's word, custodians who independently re-materialise and recompute the root before signing, and the salted redactable root.

Per-file version ids are insufficient because the reproducible unit is the *set*: they let you re-fetch a file and never let you re-derive which files the cohort contained, nor check the set for completeness.

`Cut` resolves cross-lineage extracts, which the substrate recorded as unresolved. It is honestly not a global serialisable snapshot — it is a *declared* cut that records each lineage's `(v, vid, index_seq, term)` under one federation-level two-phase reservation, so every component version becomes a GC root before enumeration begins. Components may differ in wall clock by each lineage's commit cadence, and the cert says so.

### 6.3 Pinning, amplification, and the anti-sampling rule

`freeze` computes `pin_bytes / byte_count` and **refuses above the policy threshold (default 4×), offering `repack` instead** — rewrite the selected chunks into fresh contiguous xorbs and pin those. Mandatory, not advisory: the collectable unit is the xorb, so a uniform 0.1 % sample pins 64 % of the lineage's xorbs indefinitely, at N = 1, on media where GC is off by default.

Retention is applied at **retention-class bucket** granularity, not per fragment (per-fragment is 1.4×10⁸ calls per PB pinned, ~39 h at 1000/s). The honest consequence, stated in the contract: the lock defends a coarse superset of the citation.

A pin guarantees **existence, never residency**. An expired residency lease reverts its xorbs to sealed.

### 6.4 Reproduction after redaction

Redaction is `redaction.order` (institutional approver quorum, authority recorded) → `redaction.shred`, destroying the wrapped **object-key rows for every object in the consent unit** *(2026-09-19: was "the wrapped `K_rdom` row"; retired by `eval/results/ckpt_dedup_results.json`)*. Zero mounts, zero bytes moved, zero cartridges retired, exact blast radius — now the object rather than the domain — immediate in every version and every pinned extract.

The salted redactable root means the extract still verifies, every surviving leaf still proves inclusion in O(log n), redacted leaves return a signed attestation instead of bytes, and the extract moves to `PARTIALLY_REDACTED`. Because the salt is encrypted under the object's key, destroying that key destroys the salt *(2026-09-19: was "the redaction domain's key … `K_rdom`"; rename only)* — so the retained `rel` (often MRN-derived) plus digest stop being a disclosure that a named subject withdrew. The identifier does not survive the erasure it documents.

For derivatives, `rdom_closure` does the work described in §3.4. A `MIX` derivative's key is derived from the concatenation of contributing domain keys and never stored, so one withdrawal makes it underivable — permanently, everywhere, including on WORM, including inside an `ABSENT` derivation that would otherwise have been silently rebuilt.

Reproducibility of redacted content is permanently and visibly broken. That is the correct outcome under a withdrawal regime and it is stated rather than hidden.

---

## 7. Provenance

### 7.1 What a third party checks

1. **Recompute the frozen set.** From `(cut, selector, enumeration)` — all in the record — recompute `fset_id` and `root_pub`. The cohort is proven to be what the record says without trusting the record.
2. **Check the cut.** Every component `VersionRoot` carries an epoch-fenced quorum certificate; `vid == HMAC(K_mid, canonical(root))` is recomputed, not trusted; `cd == merkle(runs[])`.
3. **Check what was delivered, not what was permitted.** `consumed_set_root` is a Merkle root over the leaves actually handed to the token, extended incrementally and checkpointed on each frame boundary. Partial delivery produces a **derived frozen set**, not a caveat — an agent that trained on 970,000 of 1,000,000 files cites the 970,000.
4. **Check the receipt's inclusion** against a per-epoch Merkle tree head, cross-signed by ≥3 independent institutions, published off-fabric, with the root sealed to WORM.
5. **Check the holders independently.** Each holder signs one per-epoch tree head over everything it served; the receipt carries inclusion proofs covering ≥k fragments per xorb. Serving is corroborated by parties who cannot decrypt what they served and have no incentive aligned with the reader. **Prior art: Storj's signed bandwidth orders, in production, with the same erasure coding and the same blindness; ISO/IEC 13888 non-repudiation-of-receipt; proofs of retrievability (Juels–Kaliski 2007, Ateniese 2007).** The narrow claim that survives is the aggregation: a receipt is valid iff independently WORM-committed per-epoch holder heads cover ≥k shares of every xorb, at O(1) signatures per holder per epoch rather than O(k × xorbs) per lease. A residency-served read is covered by a two-hop chain — the staging locus signs a stage attestation naming the residency, which chains to the holder attestations gathered by the lease that created it. Without that, warm-set reuse, the fabric's most common and most valuable case, would be the one case with no corroboration.
6. **Check the transform.** `transform_id`, `image_cid` (stored in the fabric, therefore still resolvable), `params_digest`, and for attested loci the quote. `BITWISE` derivations verify by re-execution and hash comparison; `STATISTICAL` derivations verify by tolerance against the declared `env_class` and the report says so explicitly; `NONDETERMINISTIC` output is attested as to *what was read*, never as to what it means.
7. **Check the fabric.** `attest` returns quorum certs, the index sequence and staleness bound the answer was served at, replica divergence, proof-of-possession samples, and custody health. Every read RPC returns its `index_seq` and a staleness bound, and a replica beyond that bound **fails closed** rather than serving: a citation resolved against a partitioned replica that does not yet know the extract exists makes "I trained on extract E" unfalsifiable.

### 7.2 Receipt privacy on write-once media

Only the **commitment** goes to WORM — `{receipt_id, prev_epoch_head, H(payload), timestamp, signature}`. The payload (frozen-set id, consumed-set root, rdom-linked fields) stays in the index encrypted under a key in the shred store. Shredding that key de-links the WORM entry: the tamper-evidence chain still verifies and the association is gone. Putting the payload on WORM creates a permanent, unerasable record of exactly the association consent withdrawal exists to destroy, and makes audit queries a tape mount.

### 7.3 The honest limit

A receipt proves what was *delivered*, not what the agent subsequently did with it. Provenance ends at the materialisation boundary. That boundary is meaningful for a stateless caller and decays in value as readers stop forgetting: for a resident agent, "what did it read" is answered by its weights. The durable investment is therefore the boundary **policy** (§8.6), not the boundary record.

---

## 8. Containment

Nine bounds. None is a detector — when the normal workload is an agent issuing millions of operations, volume carries no signal at all.

**8.1 One byte-moving verb, and it takes a frozen set.** `realise`'s target is an immutable `fset_id` or `derivation_id`. A prompt injection mid-run cannot widen a scope that is a hash of an already-enumerated set; widening means a new `freeze` under a Purpose. To be clear about what this does *not* buy: the agent authors the selector, so this is an accountability and scheduling mechanism, not by itself a containment one. Prior designs led with a claim of this shape and it is vacuous. The real bounds are below.

**8.2 Coverage — the union, not the sum.** Caps on `{leaves, bytes, rdoms, fraction_of_scope}` per Purpose, charged identically by delivery, enumeration and aggregation, and shared by the entire delegation tree. Immune to caching (a warm read costs nothing physical and still covers leaves) and to fan-out (union is idempotent, so 10⁴ children double-counting is harmless). `distinct_rdoms_touched` is the number that matters for PHI: *this purpose has touched 41,210 of the 50,000 subjects it may*.

**8.3 Purpose and Task, not agent, are the principals.** Agents are cheap, forkable and ephemeral; anchoring a conserved quantity to the most ephemeral entity in the system is what produced the fan-out amplification that broke every prior design. A token binds `(purpose, task, actor chain)`; the actor is recorded in receipts and holds nothing. `purpose` is never agent-supplied free text — it exists only on the quorum-approved `Purpose`, and Intents and Tokens reference `purpose_id`. Otherwise the field a DUA auditor most depends on is chosen by the attacker and the system cryptographically attests a lie.

**8.4 Attenuation narrows; admission conserves.** Offline, monotone, depth- and fanout-bounded, with revocation points chosen at mint so one compromised subtree can be severed without killing 9,999 siblings. Quantity is drawn online at `realise` against the Purpose, and above it against each contributing institution's pledge. Refusals name which of the three bound.

**8.5 Egress is an information bound, not a byte bound.** A byte cap bounds size, not disclosure: 4 KB is a re-identifiable cohort, and a low-rank adapter delta is a compressed one. `output_contract` is typed — `ROWS{schema, min_cell, no_row_level, max_rows}` enforced at the sink, or `ARTEFACT`/`MODEL` above a threshold routed to a review lane. **Prior art and the correct semantics: DataSHIELD's disclosure filters across independent clinical institutions, the Five Safes model, ONS Secure Research Service output checking, OHDSI distributed studies, OpenSAFELY.** This field solved output control twenty years ago and every prior design in this exercise downgraded it to a byte cap. Sandboxes have `DENY_ALL` networking and no inbound path; the `METRIC` sink that three designs offered is deleted, because a function-chosen number leaving through a mesh-aggregated metric plane is uncounted egress.

**8.6 A model that has read governed data is itself a governed artefact.** A `MODEL`-output derivation inherits `learned_from` = the rdom closure and the join of its inputs' `dua_closure`, and inherits the **materialisation policy**. Deploying it outside the allowed loci is refused by the same mechanism that refuses plaintext leaving. This is the boundary policy that survives readers who do not forget. Machine unlearning is not solved and Entail does not pretend otherwise (§12).

**8.7 Provenance as an integrity axis, not only a confidentiality one.** In a fabric where agents both write and read, the corpus is attacker-influenced by construction, and every prior threat model ran exclusively outward. `provenance_class` and `author` are indexed and selectable; Purposes constrain them; `QUARANTINED` is a state; training selectors default to excluding `AGENT_DERIVED` unless explicitly opted in. Poisoning containment is the integrity mirror of the exfiltration story.

**8.8 Materialisation policy is a separate axis from placement.** Where fragments may live and where plaintext may be reconstituted are different questions. Keep-in-state and facility restrictions are enforced at the decryption point and surface as free planning refusals. Blind holders, one fragment per site, Shamir `t`-of-`n` across *other* institutions, and WORM media mean a fully compromised site can neither read the archive nor destroy it. Metering happens at the decode locus, not at the holders — a blind store cannot count leaves (that needs `K_L`) and cannot enforce a global byte cap across `n` independent parties without either a per-read quorum or a static shard that a rotating read set defeats by `n/k`. Holders enforce a coarse per-lease ceiling as a backstop; racing is charged at `k+r`, not `k`.

**8.9 Repair and scrub never route through this path.** They read ciphertext by `H(xid‖i)`, need no key and no approval, and consume the reserved plant share. Durability must never depend on authorisation, and an agent tier cannot make the fabric less durable.

**The composite claim.** A compromised, looping or prompt-injected agent's worst case is: *at most the residual coverage of its Purpose — measured as distinct leaves and distinct redaction domains, not as bytes — delivered as outputs of transforms whose disclosure contracts were fixed before they saw a record, over a cut fixed before the Purpose was approved, materialised only where policy permits, corroborated by k blind institutions, and recorded in a receipt it cannot erase.* That number is set by a human quorum once, at grant time, and decreases monotonically. Nothing has to notice anything.

---

## 9. The five workloads

### (a) Train on a 40 TB corpus, many epochs

```
cut([{kymed-path, v137}])                                  -> C
freeze(C, {prefix:"wsi/", provenance_class_in:[INSTRUMENT,CURATED]}, cite) -> F   (async job)
compose(SPLIT{seed:7, ratios:[.8,.1,.1]}, [F])             -> F_train, F_val, F_test
   -- admissible only because the lineage declared these splits at ingest, so the three
   -- shards are physically separated; otherwise refused SAMPLE_ORTHOGONAL_TO_PACKING
shape(F_train)   -> sweep_drive_seconds [38 h, 54 h]    // wall clock [4.2 h, 6.0 h] across 9 drives
                    // CORRECTED 2026-09-19: was [3.1h, 4.4h], which is the NINE-DRIVE WALL CLOCK,
                    // not drive-seconds. 40 TB at the plant's own 291 MB/s effective rate is ~38
                    // drive-hours. Every *_drive_seconds term is reported in drive-seconds or
                    // drive-hours, NEVER wall clock. GB per drive-hour -- not utilisation, not wall
                    // clock -- is the honest plant metric: the measured reactive plant shows HIGHER
                    // utilisation precisely because it wastes drive-seconds on mounts
                    // (eval/results/plant_sim.json).
                 , pack_alignment ALIGNED,
                    residency_coverage [{louisville, 0.0}]
register_transform(tokenise_wsi, determinism BITWISE, rdom_rule PRESERVE,
                   output ROWS{...})                       -> T_tok
derive([F_train], T_tok, {tile:512}, idem)                 -> D_tok      (ABSENT, O(1), free)
prospect(D_tok, {deadline: 18h})                           -> ADMISSIBLE
    shared_cost: recall of F_train, invariant across strategies
    strategies: COMPUTE_AT@louisville (local group exists)  — 0 input core bytes
                DELIVER@caller                              — 40 TB core, 8.9h, refused: PLEDGE
    rewrites:   none needed
intend(D_tok, horizon{+2h,+18h}, BATCH)                     -> coalesced with 3 other intents
realise(D_tok, sink RESIDENCY{louisville}, draw)            -> Job (one tape pass, ordinal waves)
-- epoch 1..N:
realise(D_tok, sink STREAM{shuffle seed_e}, draw)           -> attaches to the residency; no mounts
evict(D_tok) when done                                      -> bytes released, CITATION SURVIVES
```

The last line is the point. `D_tok` remains citable, reproducible and delegatable after its bytes are gone, because it is `BITWISE` and its inputs are pinned. A year of tokenised shards costs a few hundred bytes each, not 40 TB each.

### (b) Cohort analysis without materialising

```
ask({COUNT, cut C, selector: attr(modality=CT) AND attr(phase=arterial)}, token)
   -> Assertion{ answer 18,400 (quantised, min_cell 10), coverage_delta 18,400 leaves,
                 differencing 1/leaf, signed, citable }
register_transform(cohort_stats, output ROWS{schema, min_cell:10, no_row_level:true},
                   rdom_rule MIX)                          -> T_stat
derive([F_cohort], T_stat, params)                          -> D_stat
prospect(D_stat)  -> ADMISSIBLE, COMPUTE_AT (output/input = 10^-7)
realise(D_stat, sink DERIVATION{D_stat}, draw)              -> Job -> Receipt
```

The `ask` is charged into Coverage exactly as a byte read would be. A binary-search differencing attack must cover the leaves it differences over, so its breadth is bounded by the union and its depth by `queries_per_leaf`.

### (c) 200 producers appending daily increments

```
open_branch(kymed-notes, head)                              -> B_i         (per producer)
stage(B_i, entries[{rel, source, rdom_hint: subject_id, author, provenance_class INSTRUMENT,
                    pack_hint{read_class:"by-subject"}}])   -> StageReport
commit(B_i, parent_v)                                        -> Version | Conflict{head, conflicting}
```

Disjoint branches are detected by Bloom intersection, O(1) per pair. A same-`rel` conflict is **refused**, the losing branch is left intact with its lease alive, and the conflicting `(rel, sha256)` is reported — an undefined resolution degenerates in practice to last-writer-wins, which with lease expiry is a write that returned success, appears in no version, and destroys its own evidence two epochs later. Branch commits are served by a single coordinator under a renewable quorum-issued lease; only the merge to `main` takes the full round. The branch lease clock is suspended while the owner holds an in-flight residency, so an agent waiting forty minutes on a mount does not return to find its branch aged out.

### (d) Cite now; reproduce eight months later, after a withdrawal

```
-- at publication:
citation = "gfs:1c:<C>#e9c14b0a3f7d…"   with index_seq, term, counts, root_pub, 7/9+5/7 signers

-- eight months later:
resolve_citation(citation)   -> { cert, redaction_chain_head, index_seq, staleness_bound,
                                  availability: PARTIALLY_REDACTED }
verify(citation, WITH_CHECKPOINT)
   -> root_pub verifies; 1,203,926 of 1,204,338 leaves prove inclusion;
      412 leaves return signed redaction attestations under IRB-2026-114, effective 2026-04-02;
      intersect(consumed_set_root of receipt R, redaction set) = 412  ->  NOT REPRODUCIBLE,
      bounded and attributed
attest(citation)  -> custody_health{t:7, n:12, live_shares:9, decryptability_horizon: 2034-11}
```

If the intersection were empty, the answer is *provably* reproducible today and the proof is citable. That distinction — provable reproducibility, or precisely attributable irreproducibility — is what a withdrawal regime actually needs, and it is available only because the receipt records what was *delivered*, not what was permitted.

### (e) A deadline and a fixed budget

```
prospect(D, {deadline: 2h, caps: {...}}, token)
 -> REFUSED
    binding_constraint: DEGRADED_PLANT
    detail: "library-7 regeneration holds 61% of federation tape capacity until 2026-11-04;
             residual sweep_drive_seconds at your lane: 180/h"
    shared_cost: sweep [13,400h, 19,100h]   basis MODELLED, model_error_p90 0.62
    rewrites:
      1. COMPUTE_AT@lexington on the 3 sites holding 81% of the selection, deliver the
         reduced result: horizon [38m, 1h55m], fits deadline and caps
      2. ATTACH to residency R-4471 (covers 64% of your selection, expires in 31m)
      3. repack(F, ACCESS) once: 19 fabric-days, then every later pass costs 1/33
    calendar_position: BATCH lane, would be position 340, projected window 2026-09-27
intend(D, horizon{+0,+2h}, CLINICAL)   -- or take rewrite 1
```

### (f) The workload the prior designs did not model: an agent deriving from what it just read

```
derive([D_tok], T_embed, {model: m_cid})     -> D_emb    (ABSENT; O(1); no quorum; no bytes)
derive([D_emb], T_index, {})                  -> D_idx    (ABSENT)
prospect(D_idx) -> strategies: ENTAIL (rebuild from D_tok's residency: 22 gpu-min)
                               DELIVER (D_emb not resident; would require rebuilding anyway)
realise(D_idx, sink DERIVATION, draw)         -> Job; D_idx.residency = RESIDENT, TTL 7d
-- 10^4 sibling agents issuing the identical derive() get the identical derivation_id
--   and ATTACH; the fabric does the work once.
-- none of this touches the commit path, the merge service, or permanent capacity.
```

This is why the single-writer merge chokepoint that every prior design admitted and none fixed is no longer on the dominant path: **the derivative firehose does not commit**. The commit path is for curated, cited state — rare, consequential, and able to afford a quorum round. `promote` moves a derivative into it when, and only when, someone cites it.

---

## 10. Novelty, honestly

### Standing on (re-derived; named so a reviewer does not have to find them)

**Grid storage and federated data management** — SRM v2.2 (`srmReserveSpace`/`srmBringOnline`/`srmExtendFileLifeTime`/`srmReleaseFiles` = reserve/activate/extend/release, tape-backed, cross-institution, twenty years, ~150 sites), dCache pinning and per-file locality, HPSS/CTA/Enstore VSN-grouped serpentine recall planning, Rucio DIDs and rules (a named citable *set*), PanDA brokerage (job-to-data vs data-to-job against replica maps and measured throughput), FTS3, perfSONAR, Condor ClassAds, Stork ("data placement is a first-class scheduled job", 2004), Globus GARA / SNAP RSLAs / Maui advance reservations. **And their negative results**, which Entail treats as findings: WLCG removed SRM in favour of a minimal Tape REST API because binding reservations could not be honoured across sovereign sites; advance reservation across administrative domains produced fragmentation, priority inversion and estimates clients learned to ignore; SHARP (SOSP 2003) built exactly a delegatable, hierarchically sub-divided resource claim and did not stick, because sites would not cede admission control to a foreign ticket.

**Biomedical federation** — GA4GH DRS (machine-resolvable data objects), TES (a task with resources and content-addressed inputs), WES (ship the workflow to the data), Passports/Visas and DUO (purpose-bound, consent-code-scoped authorisation), Beacon — including the Shringarpure–Bustamante re-identification result that motivates Beacon v2's security model. DataSHIELD, vantage6 / Personal Health Train, OHDSI, FDA Sentinel, PCORnet, OpenSAFELY, the Five Safes model and ONS SRS output checking.

**Quoting and budgets** — Mariposa (priced bids over a wide-area database, 1996), WS-Agreement (GFD.107: templates, offers, acceptance, and *guarantee terms with remedies*), BigQuery `dryRun` + `maximumBytesBilled`, Snowflake resource monitors, Network Weather Service (published measurements with self-reported forecaster error), Slurm TRES / `GrpTRESMins` / `--test-only`, KeyKOS and EROS space banks (1985: conserved-quantity capability delegation), WLCG pledges and APEL.

**Citation and versioning** — RDA WG Data Citation (2015), Buneman/Davidson/Frew (CACM 2016), Iceberg manifests, Delta Lake, LakeFS, Nessie, Datomic's db-as-a-value and basis-t, git.

**Storage mechanics** — Hugging Face Xet (CDC, xorbs, sampled dedup; the noun `xorb` is imported, not coined), restic, Borg (including 2.0's epoch mark-and-sweep with leases), Data Domain, Venti, Tahoe-LAFS (convergence secret, blind holders), Rabin IDA, Azure LRC, Facebook f4, Shamir, proactive VSS (Herzberg et al.), Vanish, TSM collocation, Snowflake micro-partitions and clustering, Semantic File System (SOSP 1991), Hive partitioning, DICOM Query/Retrieve, Arrow Flight (plan-then-stream), S3 Batch Operations manifests, BagIt, OAIS representation information, iRODS ingest policy.

**Authorisation, evidence, privacy** — macaroons, Biscuit, UCAN, SPIFFE, Cedar and Zelkova (decidable policy comparison by SMT, in production at S3-policy scale), Byun–Li purpose-based access control, Certificate Transparency and Sigstore/Rekor, ISO/IEC 13888 non-repudiation, PDP/PoR (Ateniese 2007; Juels–Kaliski 2007), Storj bandwidth orders, Filecoin retrieval vouchers, Denning (1979) and Dinur–Nissim on differencing, differential privacy, Nix, Bazel remote execution, Vesta, Spark RDD lineage, dbt, Ernest and Quasar (sample-then-predict).

**And the substrate itself**, which supplies the quorum-confirmed index, blind holders, Shamir custody, placement with explicit refusal, measured routing, the capability inventory, the run/VersionRoot/Extract model, ~~`K_rdom`~~ **per-object keys** *(2026-09-19)*, the salted redactable root, ordinal activation waves, epoch GC, and the pin-amplification arithmetic. Entail is almost entirely interface over that.

### Claimed as new

1. **Entailment-first storage for derived data** — a citable object whose identity is its recipe, with `ABSENT` a legal permanent state, `residency` a fabric decision, and the transform's **determinism class** as the mechanism deciding what may be silently discarded and rebuilt. The ancestors treat recomputation as recovery in a cheap-storage world; the inversion here is forced by a substrate where storage is monotonic, un-erasable and legally entangled while compute is elastic. I have not found it.
2. **Coverage as a conserved, monotone union across a Purpose's whole delegation tree, charged identically by byte delivery, metadata enumeration and aggregate answers.** Prior art bounds scope (Cedar/Zelkova, capability containment) or quantity (Slurm, KeyKOS, BigQuery, SHARP); nothing conserves breadth actually taken, and nothing survives both caching and offline fan-out. The ancestor, ASSAY's delivery bitmap, was forensic.
3. **Redaction-domain closure over derivations**, with `PRESERVE`/`MIX`/`CERTIFIED_DEIDENT` semantics and an AND-survival derived key that is computed and never stored. The shred primitive is the substrate's; extending it structurally to derivatives on write-once media is new here, and it closes the laundering hole that every prior design had. *(2026-09-19: the `MIX` half survives the retirement of `K_rdom` — see §3.4 — but the `PRESERVE` half does not: under per-object keys it stops being cryptographic and becomes a catalogue obligation, §14.10 hole. **This contribution is now half-standing, and that must not be glossed.**)*
4. *(Smaller)* **Purpose and Task, not agent identity, as the budgeted principals** — which makes recursive spawning non-amplifying without any online mint check, and makes `purpose` an auditable field rather than an attacker-chosen string.
5. *(Smaller)* **The fabric's own obligations as a first-class reserving tenant with a published calendar**, and `DEGRADED_PLANT{reason, until}` as an actionable refusal.
6. *(Smaller)* **Agent-audits-fabric verbs** (`attest`, `challenge`). Every provenance scheme in this space is built for a third party auditing the agent; an autonomous agent needs the converse and no prior design provides it.

### Explicitly not claimed

The plan object, the cost model, cost-based strategy selection, the frozen citable set, two-phase activation, tape-ordered recall, mount-cost exposure to clients, attenuable offline capabilities, blind-witness receipts, output checking, the removal of the read verb, predicate namespaces, and content-defined chunking. Each has a named owner above. The one part of the plan apparatus retained as a contribution is narrow and was correctly identified by a critic: **the rejected alternatives survive the decision and are cited by the act**, so "why did you ship instead of fetch" is answered by joining two durable records rather than by trusting narration.

---

## 11. Disposition of every FATAL and SERIOUS finding

`R` = resolved. `A` = accepted as a stated cost. `U` = recorded unsolved (§12). Findings are grouped by class; a class raised against several designs is listed once.

### Prior art and novelty

| Sev | Finding | Disposition |
|---|---|---|
| F | Grid-storage corpus unexamined; WLCG removed SRM, the feature being made central | R — cited §10; binding reservations abandoned §1, §4.4 |
| F | GA4GH DRS/TES/WES/Passports/DUO uncited, same domain | R — cited; `Purpose` maps to Visa + DUO codes; `Transform`/`realise` adopt the TES shape |
| F | Citation triple is the RDA WGDC recommendation | R — cited §6.2; claim narrowed to quorum notarisation + verifying signers + salted root |
| F | Plan-as-offer is Mariposa/WS-Agreement/BigQuery, minus the guarantee term | R — claim withdrawn; prospectus carries literal `advisory: true`; remedy replaced by queue position |
| F | Conserved budget is KeyKOS/Slurm/SHARP | R — cited; SHARP's failure answered by per-institution admission against each institution's own pledge |
| F | Blind-witness receipts are Storj bandwidth orders; access logs are already holder-written | R — cited; claim narrowed to per-epoch threshold aggregation §7.1 |
| F | "There is no read" is the warehouse model | R — cited; the differentiator is fifty operators plus the Derivation, not the subtraction |
| F | Byte-cap egress is the weak form of DataSHIELD/Five Safes/ONS | R — typed output contracts, min cell size, review lanes §8.5 |
| F | Facet index is a Beacon-style differencing oracle | R — catalogue governed, coverage- and differencing-charged §4.1; residual U |
| S | Semantic FS / Hive / DICOM Q/R; "no paths" is rhetoric since pruning needs an order | R — conceded; `rel` named as an ordered locality key §3.2 |
| S | Published oracle with self-reported error is NWS | R — cited; only per-term basis inside a retained artefact claimed |
| S | Write-time clustering is TSM collocation; `calibrate` is Ernest/Quasar | R — both cited; clustering mandatory-declared, calibration fleet-level |
| S | PROV-O `prov:Plan`, CT, IDA/Vanish, Borg GC, `xorb` imported from Xet | R — absorbed into §10 |
| S | Predicate containment is Cedar/Zelkova and has no decision procedure here | R — cited; containment fragment defined; KNN excluded §11 below |

### Budgets, principals, containment

| Sev | Finding | Disposition |
|---|---|---|
| F | Offline attenuation cannot conserve an additive budget (×3 designs) | R — ceilings offline, quantity online at admission, depth/fanout bounded §8.4 |
| F | Budgets are sums; caching and union defeat them; exfiltration by many small permitted reads | R — Coverage §8.2 |
| F | Conservation per-grant while scarcity is fabric-wide; no ledger above; no priority; no preemption | R — pledge ledger, lanes, cartridge-atomic preemption, plant reserve §5.2 |
| F | Derived data carries no taint; sink laundering; redaction cannot reach derivatives (×2) | R — rdom closure, PRESERVE/MIX, derived AND-survival key §3.4, §6.4 |
| F | Egress bounded per task while task count is unbounded | R — egress and coverage accounted per Purpose and per `(Purpose, sink)` |
| S | "An injected agent cannot invent an operation" is vacuous | R — claim withdrawn §8.1 |
| S | Capability chain depth is an asymmetric DoS; receipt size attacker-controlled | R — `max_token_depth`, `max_fanout`, monotone |
| S | Revocation is all-or-nothing at the grant | R — revocation points chosen at mint §8.4 |
| S | `purpose` is agent-supplied free text and is the linchpin of the DUA claim | R — exists only on the approved Purpose §8.3 |
| S | Access shape (POINT/SAMPLE/SCAN) is declared, not enforced | R — replaced by coverage + differencing caps |
| S | `METRIC` sink is an uncounted egress channel | R — deleted §8.5 |
| S | Fail-closed is attacker-inducible by saturating the fibre | A — control/dataplane isolation is shipped; plus a bounded, non-renewable per-site locally-admissible reserve, declared as a deliberate bounded breach of conservation |
| S | Commit-then-kill / reservation churn denies drive time | R — nothing to churn; held capacity billed continuously |
| S | Sandbox-local inference puts an LLM inside the trusted zone | R — the inference facility is itself a Transform under an output contract; model artefacts governed §8.6 |
| S | Attested enclaves across independent institutions have no prior art | A — `attestation: NONE` is visible in every Prospectus and Receipt; ship-over-PHI at an unattested locus rests on operational trust and says so |

### Planning and scheduling

| Sev | Finding | Disposition |
|---|---|---|
| F | Binding quotes/reservations across sovereign domains are not implementable (×3) | R — abandoned §1 |
| F | Quotes priced open-loop; the herd invalidates every p90 | R — priced against committed queue; Calendar; intents coalesce; horizons revised |
| F | Free planning surface performs unpriced expensive work, floods the quorum and reflects RPCs onto custody (×3) | R — every verb metered; no quorum, no cross-institution RPC on the planning path §4.4 |
| F | No primitive to join a recall in flight; reservations fight coalescing (×2) | R — refcounted Residency + `attach` + `intend` coalescing §4.6 |
| F | `shape`/`freeze`/`seal` cannot be free, cheap and exact | R — Shape returns a bound with basis; exact refinement is a priced job; freeze is two-phase, async, charged, idempotent |
| S | Plan expiry produces a synchronised retry storm and single-agent livelock | R — no expiry to race; jittered `retry_after`, queue position in every refusal |
| S | `stat`/`diff`/`explain` are inference and co-location oracles | R — layout, cartridge identity and peer load removed from agent-facing answers §3.5 |
| S | The quote is a cross-tenant covert channel | R — quantised, epoch-batched, tenant-scoped |
| S | Wall-clock composed as if k recalls were independent | R — k-th order statistic with a correlation term §5.2 |
| S | A pairwise link matrix cannot represent the shared core | R — shared-segment model + federation daily byte budget |
| S | Calibration on cold tape costs ≈ a full read; a cheap sample is biased | R — fleet `build_model`; cold-tape probes refused; in-run first-wave calibration §5.4 |
| S | No fairness; institutional crowd-out; deadline is a free lie channel | R — hierarchical max-min across institutions then purposes, with guaranteed floors proportional to pledge; named lanes replace deadline as the scheduling input |
| S | GC and redaction lose a market they bid in | R — non-tradeable plant reserve §5.2 |
| S | Cost model inverts incentives: selective reads cost ~33× per useful byte | R — sweep-adjusted accounting plus an offered `SCAN_AND_FILTER` rewrite and `repack` |

### Physics

| Sev | Finding | Disposition |
|---|---|---|
| F | Mount is the wrong unit; no scatter term | R — sweep-adjusted drive-seconds, `wraps_touched`, `contiguous_runs` §5.2 |
| F | `SAMPLE` as the infeasibility remedy is backwards; pin amplification bites at N=1 | R — anti-sampling rule §4.2; declared splits; 4× materialise threshold |
| F | Fetch-vs-ship is null for cold tape; one-fragment-per-domain kills locality; LRC was dropped | R — invariant printed as shared cost; `localise` restores D10 §4.6, §5.3 |
| F | Fabric obligations unpriced; repair saturates the plant for weeks | R — reserving tenant, Calendar, `DEGRADED_PLANT`, `durability_debt` |
| F | The shared 100 G core is absent from the model | R — segment model §5.2 |
| F | Redaction physically impossible / oversubscribed / D1 default inverted / factor-1000 error (×3) | R — superseded by the substrate's **per-object keys** *(2026-09-19: was `K_rdom`, retired by `eval/results/ckpt_dedup_results.json`; **D1's inversion is now the measured answer rather than a design choice**)*; D2 retired; per-object keys unconditional for every lineage |
| F | Byte ranges deleted, making sub-file access impossible | R — `span(...)` selector + SpanIndex + ordinal waves §3.3 |
| F | Holder-side metering is impossible for leaves and leaky for bytes | R — metering at the decode locus; coarse holder backstop; `k+r` charged §8.8 |
| F | Index scale 3–4 orders beyond proven; immutable per-version ANN indices are not persistent structures | R — substrate run/XorbSet/LSM design; vectors retained by reference, ANN graph rebuildable and evictable, KNN results classed `STATISTICAL` not `EXACT` |
| F | Write path unreserved: sequencer DoS plus a free GPU farm via required extractors | R — writes admitted and billed; extractors are contracted Transforms §4.7 |
| F | Immortal free citable objects are an index kill | R — freeze charged, two-phase, idempotent, class-tiered; `derivation_id` is O(1) and deduplicates by construction |
| F | Receipt and holder-attestation amplification onto unreclaimable WORM; a global hash chain serialises | R — per-epoch Merkle + cross-signed checkpoints; commitments only to WORM §7.1–7.2 |
| S | Warm-pool thrash at a 10⁵ miss:hit ratio; no payer rule; no eviction protection | R — residency pinned for the lease, refusal when it will not fit, byte-days billed, payer/joiner rule §4.6 |
| S | Layout drift is monotonic and there is no repack verb | R — `repack`; `pass_efficiency` published per version |
| S | Cartridge grouping demands three incompatible placements | R — `tape_affinity` declared per lineage; ~~`K_rdom` removes the subject axis~~ **2026-09-19: `K_rdom` is retired, so it removes nothing. The subject axis returns, and `SPECIFICATION.md` §8.4 now holds two live positions on it — rule 2 forbids clustering by consent unit for disclosure reasons while the plant measurement makes clustering by co-access mandatory for capacity, and where a read is a subject these are one decision. This row is therefore re-opened as A rather than R; see `STORAGE-BINDINGS-DECISION.md` A-5.** |
| S | Fragment state refreshed on a seasonal scrub; `feasible` signs over unverified media | R — `last_verified`, MLM class, `verified_fraction` in Shape, sampled proof-of-possession, `PARTIAL` extended to media loss with its own reason code |
| S | Verification corpus ages onto tape and needs a grant | R — audit tier never sealed; verification touches no plaintext and needs no grant |
| S | `close()` mints the receipt, so a crash loses the record at the incident | R — consumed-set checkpointed per frame; `ABANDONED_AT_CHECKPOINT` with an explicit indeterminate window |
| S | `decode_cpu_seconds` is six orders below the binding terms | R — dropped; `index_ops` added |
| S | Quorum independence is capped by library count, not by 50 institutions | A — stated as a deployment constraint; minimum distinct legal entities published per lineage survivability profile |
| S | Replica lag breaks read-your-writes and selection determinism | R — `index_seq` + staleness bound on every read; replicas fail closed; freeze requires an explicit `v` |
| S | Disk-resident LRC parity is unaccounted | R — locus tiers split into stage / parity-committed / durable-free; parity residency priced |
| S | Large single files need a span index | R — adopted from the substrate (threshold 4096 spans) |
| S | Per-member keys defeat dedup where volume is largest | **R — 2026-09-19, by measurement, not argument.** The critique assumed there was dedup to defeat. `eval/results/ckpt_dedup_results.json`: on the population where volume IS largest — training checkpoints — adjacent, distant, intra-checkpoint and cross-run block sharing are all exactly zero. Per-member (per-object) keys defeat nothing, cost nothing, and restore per-object crypto-shredding. ~~The earlier answer — "dedup is within a redaction domain; for longitudinal clinical data that is where the win is" — was an unmeasured assertion and is withdrawn.~~ |

### Model and interface

| Sev | Finding | Disposition |
|---|---|---|
| F | Catalogue is unauthenticated, unaudited, unbudgeted (×2, plus substrate Unresolved 8) | R for governance §4.1; U for metadata confidentiality |
| F | "There is no enumeration surface" is false | R — conceded; `enumerate` exists and is coverage-charged §4.1 |
| S | Containment fails for setops-derived selections and for KNN | R — derived frozen sets carry a canonical characterisation; KNN is two-stage inside a containment-decidable candidate region, which also restores static cost bounding |
| S | ML-derived values are not bitwise deterministic | R — determinism classes; `EXACT` only for `BITWISE` §3.4 |
| S | No cross-dataset primitive (substrate Unresolved 6) | R — `Cut`, with its non-serialisability stated §6.2 |
| S | Single-writer merge service is a chokepoint every design admitted and none fixed | R — the derivative firehose leaves the commit path entirely §9(f); curated commits keep the leased single writer, with availability stated |
| S | No human surface is an operational risk, not a virtue | R — a read-only Inspector Purpose with its own coverage accounting and receipts; explicitly not a bypass |
| S | Facets fixed at ingest are the ceiling on the system | R — enrichment is an ordinary Derivation, priced and plannable; OAIS cited; a plaintext-retained tier for the highest-value lineages recorded as an option |
| S | Agent identity minting is unresolved and consumed by every design | R for budgeting (Purpose/Task); U for the identity root itself |

---

## 12. Blind spots, addressed

**The archive is the noun and the agent is the verb.** Rejected. The Derivation makes agent output first-class, the derivative firehose bypasses the commit path, coverage is charged on reads *and* on the catalogue, and the write path is admitted and billed exactly like the read path. The provenance atom remains a delivery, but the *object* population is dominated by derivation edges and the design says so.

**The free catalogue is the product.** Accepted and acted on. `ask`, `enumerate`, `diff` and `shape` are governed, metered, disclosure-controlled, coverage-charged and receipted as signed, citable Assertions. "I established X about this corpus without reading it" is now a verifiable artefact.

**Data is trusted inbound and dangerous outbound.** Corrected. `provenance_class` and `author` are indexed, selectable and constrainable, `QUARANTINED` exists, and training selectors default to excluding agent-derived content.

**An operation is a request, not a standing relationship.** Corrected. `intend`/`offers`/`calendar` give the fabric declared future demand, which is what lets an offline scheduling problem be solved with offline information, and which converts plan-expiry livelock, herd re-planning and quote-abandonment from pathologies into non-events.

**Planning is per-agent while scarcity is per-federation.** Corrected. Intents coalesce by cartridge group; residencies are refcounted and shared; work is content-addressed so identical recipes produce one job; and the fabric proposes as well as responds.

**Five axes collapsed onto "dataset."** Partially corrected. `rdom` is the consent axis (substrate), `Purpose` the budget and authorisation axis, `Cut` the multi-corpus versioning axis, `provenance_class` the trust axis. `Lineage` remains the key domain and the pledge unit. *Cross-lineage chunk sharing remains forbidden — and as of 2026-09-19 that prohibition costs nothing measurable, since cross-object sharing within a lineage is itself zero on the dominant population (`eval/results/ckpt_dedup_results.json`). ~~`rdom_rule` must still be declared at ingest~~ — the one-way door is retired with `K_rdom`.*

**Agents are the wrong principals.** Corrected. Purpose and Task hold everything durable; agents are actors in receipts.

**Nobody audits the fabric.** Corrected. `attest` and `challenge`.

**A price is the right thing to hand a planner.** Rejected. Feasibility boundary, cost interval with basis, binding constraint, offered rewrites, queue position. The interface stays useful when the estimator is not.

**Reader memory.** Acknowledged: delivery-provenance decays as readers stop forgetting, so §8.6 invests in the boundary policy — a model that has read governed data is itself governed — rather than only in the boundary record.

---

## 13. What to build, what to defer, what is unsolved

### Build first — none of it is versioning, and all of it is a prerequisite

1. **P1–P7 substrate defects.** `fsync` before ack and a fatal-on-failure journal; `(term, seq)` with divergence alarms; a single state registry driving snapshot, dump and hash, with paged snapshot transfer and an incremental Merkle accumulator; `apply()` failing closed on unknown types with `fmt` version gates; key material out of the journal, `dumpState`, `stateHash` and every WORM snapshot, into a compactible shred store; no RPC under the index monitor and per-lineage striping; `get(fragId, off, len)` and `retain_until` in `BlockStore`, plus sampled proof-of-possession. These are data-destroying once a journal entry is a citation.
2. **IV construction.** Session id ‖ counter from a durably reserved, `fsync`ed block. IV reuse under AES-GCM is not degradation, it is GHASH subkey recovery and tag forgery across the lineage, permanently, on WORM.
3. ~~**`K_rdom` and the shred store**, with `rdom_rule` declared at ingest and the derived AND-survival key for `MIX` transforms.~~ **RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`). Build instead: **per-object keys with a real delete path**, which is what the substrate had before D1 removed it and which the measurement makes affordable again. It still gates everything clinical; the mechanism is simpler. **Two pieces of item 3 do NOT come back for free and are recorded as holes:** subject-granular withdrawal across many objects (`STORAGE-DIRECTION.md` *Unresolved* 11), and the derived AND-survival key for `MIX` transforms, which was defined as `HKDF(K_rdom_1 ‖ … ‖ K_rdom_j, …)` and has no `K_rdom` to concatenate (§3.4 hole).
4. **The LSM tables** (`xorb`, `place`, `loc`, `lease`, **`keys`**) with `place`/`loc` deliberately separate. *(2026-09-19: `shred` becomes `keys`, keyed by object; `dedup` is retired.)*
5. **Runs, XorbSets, VersionRoot, Cut, FrozenSet** with two-phase pinning, the 4× amplification refusal, and verifying signers.
6. **Coverage.** `file_ord` at ingest; roaring bitmaps per (Purpose, lineage); the differencing sketch; admission gates in `realise`, `ask` and `enumerate`. Cheap to build, and it is the containment story.
7. **Derivation and Transform**, including in-fabric image storage and `entail`. `derive` is one journal entry; the value arrives immediately and the scheduler can be naive at first.
8. **Residency with `attach`**, refcounted, pinned for the lease, billed in byte-days. Without it the fabric cannot use its own substrate correctly.
9. **The plant reserve and the Calendar.** A reserved non-tradeable fraction per library plus published obligations. One configuration knob and one published record; it prevents the failure mode that ends in data loss rather than in slow service.
10. **Receipts as per-epoch Merkle trees with cross-signed checkpoints**, commitments only to WORM.
11. **Instrument plan-versus-actual on the real library for a month before building any planner.** If p95 error on tape-resident targets exceeds ~2×, the cost interval is all the planner should ever emit, and the feasibility boundary plus hard budgets carry the design alone. That is a perfectly good system and it should be the default assumption.

### Defer

- The commit quorum. Run single-writer under a fenced lease and **withhold the word "quorum"** from the external contract until a Raft-class component with static membership, durable per-`(lineage, branch, parent_v)` votes and leader-failure recovery exists. Until then the signature set must not be advertised as externally verifiable, because it can certify a commit that never happened.
- `localise` / hierarchical LRC. Design it now because it constrains placement; build it when a compute locus actually needs to decode alone.
- `repack`, media migration and cartridge cohorting. Expressible from day one via `loc`; the subsystem can wait — but cohorting constrains cartridge layout and must be decided **before media is bought**.
- Attested loci. Ship with `attestation: NONE` visible in every Prospectus and Receipt.

---

## 14. The lifecycle of live state

*Design specification, v1. Produced 2026-09-19 by a second design pass: four independent lifecycle designs (recipe-first "Wake", economics-first "Tenure", workspace-first "Bench", loss-first "Lethe"), twelve attacks across three lenses (loss/correctness, economics/incentives, agent reality at 10⁵ agents), and three critics on the whole set — one on the behavioural assumptions all four shared, one on the simplifications the owner's storage model permits, one on collisions with the archive specification. All four designs agreed on the axis and all four were fatally attacked on the machinery they built over it. This section keeps the axis and deletes the machinery.*

The owner's model is adopted whole and is correct: **the archive is tightly versioned datasets; everything live is a cache; a live instance may be versioned or unversioned; low-latency interactive read of cold data is not a requirement.** One word in it is dangerous, and closing that hazard is what this section is for.

---

### 14.1 The axis

**Versioned/unversioned is the wrong axis, and "has a recorded recipe" is the right question asked in the wrong tense.**

Versioned/unversioned conflates two independent properties: whether an archive object exists upstream (citability) and whether these bytes can be re-made (recreatability). It gets the ordering backwards in both directions. A `BITWISE` Derivation rebuildable in 22 GPU-minutes (§9(f)) is *safer to lose* than a materialisation of a pinned `FrozenSet` needing 926 drive-hours of scattered recall *(basis unstated — §14.7 note, 2026-09-19)* — and the second is the versioned one. Meanwhile an agent's three days of unrecorded work is "versioned" by the test that its inputs were, and is the only thing in the system that is neither durable nor recreatable at any price.

So the axis is recipe status. But recipe status cannot be a bit on a record, for three reasons the attacks established independently:

1. **It decays with nobody acting.** A key shred *(2026-09-19: was `K_rdom`; rename only)* changes no ancestor — the input `fset_id` is unchanged, its cert still verifies, `root_pub` still verifies by design (§6.4) — and yet the rebuild has become impossible. An input extract's TTL can lapse and its xorbs be swept. A transform image can be collected. Custody can fall below threshold. The Purpose that could execute the recipe can pass `window.not_after`. None of these is an act by the holder, and a stored bit records none of them.
2. **It ignores what the recipe is worth.** Determinism class decides whether a rebuild returns *the* bytes or merely *a* valid instance (§3.4). A recipe over a `NONDETERMINISTIC` transform is a recipe and is not a recreation.
3. **It can be forged by a verb that moves no bytes anywhere durable.** Every one of the four designs invented a cheap post-hoc attachment verb — `capture`, `seal`, `capture`, `capture` — and in every case the attack showed the verb either relabelled a hazard as safe or minted an eviction licence over unrecreatable bytes.

> **The axis, stated exactly. A live object is a cache iff `entail()` over it is feasible *now*: iff the fabric can name a total function from currently-durable state to these bytes, and execute it. Versioning is the degenerate case of that function — the identity transform over a frozen cut. When the predicate is false, the object is not a cache; it is the only copy, and the fabric does not call it a cache.**

Two consequences carry the rest of the section.

**The fabric's obligation is a read-through verdict, never a stored field.** `recreation_class` is computed in the RPC handler from `entail()` and returned with the `index_seq` it was served at and a staleness bound, on *every* response that names a live object. It is never a mutable field on an asynchronously replicated record — that is the shape the archive specification already forbids for the redaction chain, for the same reason: a mutable field on an async-replicated record makes an immutable name mean different things on primary and replica with no staleness bound. There is consequently no `loss()` verb to poll; polling one at 10⁵ agents would be 10⁴ ops/s against a measured `resolve` ceiling of 5,397/s.

**The agent's obligation is a sequencing rule, not a description.** An agent cannot be asked to describe work it has not yet understood — a recipe is a retrospective object and these designs demanded it prospectively. What an agent *can* do is call `derive` before it computes rather than after. `derive` is one ~400 B journal entry at the measured 0.3 ms commit, costs no bytes, no drive time and no quorum, deduplicates 10⁴ siblings onto one name, and `residency: ABSENT` is a legal permanent state. **Declaring before computing costs 0.3 ms and it is the whole loss model.** §14.3 makes it the write path rather than a discipline.

---

### 14.2 The state set, and what happens when nobody calls anything again

**No new noun.** Live state is exactly two things and both are already in §3: a `Residency`, holding bytes the *fabric* authored (a materialisation of an `fset_id` or of a `derivation_id`), and a `Task`, holding bytes an *agent* authored. `Task` is extended, not replaced, because it is already the durable work object and agents are already transient (§8.3).

```
Task {                              -- EXTENDED in §3.6. No Workspace, Bench, Nursery or Cell.
  task_id, purpose_id, parent_task, opened, idem_key
  state: OPEN | DRAINING | CLOSED
  derivation_graph[], intents[], jobs[], coverage_contribution          -- unchanged
  locus, scratch { lineage_id, branch, rdom, quota_bytes }              -- NEW
  unflushed_bytes, durable_through_seq                                  -- NEW
  lease_expires        -- clock SUSPENDED while any owned Job or Intent is non-terminal
  policy { flush_cadence_s,                                             -- NEW; see below
           on_stage_pressure:     SHRINK | REFUSE_NEW | RELEASE{targets[]}
           on_lease_lapse:        MERGE_AND_HOLD | MERGE_AND_EXPIRE | PROMOTE{lineage, class}
           on_input_redacted:     QUARANTINE_AND_REPLAY | ABANDON
           on_authority_expiring: PROMOTE{lineage, class} | HANDOFF{purpose_id} | ACCEPT }
}
```

`Task.policy` is the mechanism that answers critic 1's finding directly: **every question the fabric will ever ask an absent agent is pre-registered at `open_task`, when the agent exists and is thinking.** `offers(token)` is a pull verb and there is no push channel; the modal agent at 10⁵ is asleep, queued eight days out in the BATCH lane, or dead. A negotiation protocol whose default is silence, and whose silence means *accept*, has made the destructive outcome the modal one. The shape is Entail's own — `Intent.policy.on_infeasible: WAIT|DEGRADE|WITHDRAW` — extended to the four other questions the lifecycle raises.

#### Recreation classes

Derived, read-through, published on every response. Not states; a *view* over `entail()`.

| class | what it is | if the bytes vanish now |
|---|---|---|
| `ARCHIVED` | Residency over an `fset_id` whose version is in retention and whose extract is rooted | re-`realise`. Recall cost, 0.5–926 drive-hours *(basis unstated — §14.7 note, 2026-09-19)*. Bytes identical. |
| `EXACT` | Residency over a `BITWISE` Derivation, `determinism_state: VERIFIED`, `entail().feasible` | re-`realise`. `build_model.p90` GPU-seconds. Bytes identical. |
| `EQUIVALENT` | Residency over a `STATISTICAL` Derivation with a registered acceptance test | rebuild returns *a* valid instance, not *the* one. Cited instances are not silently rebuilt (§3.4). |
| `DURABLE_SOURCE` | agent-authored bytes committed to the Task's scratch branch, `staged_durable` at *n* distinct domains | nothing. Already durable. Not recreatable, and does not need to be. |
| `UNFLUSHED` | agent-authored bytes written since the last flush | **gone.** The only unrecoverable state in the system. Its width is one flush interval and the fabric sets it. |

`entail()` gains three `blocking_reason` codes the archive's own guarantees require and Entail §4.3 did not have: `INPUT_SWEPT` (an input extract's TTL lapsed and the GC collected its xorbs — a decay path the archive promises and the enum could not express), `AUTHORITY_EXPIRED` (the Purpose is past `window.not_after`, out of pledge, or revoked, so nobody can execute the recipe), `ENV_RETIRED` (the `ExecutionEnvironment`'s GPU or ISA class no longer exists anywhere, reported the way the custody decryptability horizon already is).

#### Transitions

Every transition below is an existing verb. No verb creates a state a verb cannot leave, and no *timer* destroys bytes whose `recreation_class` is `UNFLUSHED` or `DURABLE_SOURCE`.

**Residency** — `PLANNING → STAGING → PARTIAL → READY → EXPIRING → RELEASED`, unchanged from §3.5, with three corrections:

- There is no `EVICTED` state, because the fabric never evicts (§14.7). `EXPIRING` is reached only by `avail_until` passing, and `avail_until` is raised by `realise`/`attach`/`extend` and by nothing else — the archive's monotone-lease rule, inherited rather than contradicted.
- `attach` raises `refcount`; `release` lowers it. Neither touches `avail_until`. A `refcount > 0` residency is not freed; a `refcount = 0` residency survives to `avail_until` regardless, because somebody already paid for that window.
- A live reader is never truncated by a scheduling decision. The only truncations are media loss and redaction, both of which are rare, consequential, and already mint a quorum-pinned derived extract with `parent_extract` recorded (archive spec, *Activation*).

**Task** — `OPEN → DRAINING → CLOSED`.

```
open_task(purpose_id, parent_task?, locus, policy, scratch_quota, idem_key, token) -> Task
    one journal entry + one branch.open on the institution's scratch lineage.
    No quorum. Refuses if scratch retention would outlive Purpose.window.not_after.
OPEN --flush--> OPEN        every policy.flush_cadence_s, by the LOCUS, not the agent.
                            One branch commit under the Task's own leased single writer.
                            No quorum round. Zero agent involvement.
OPEN --derive/realise/attach/extend/release--> OPEN
OPEN --lease lapse | Purpose.window closing--> DRAINING
DRAINING --final flush, then policy.on_lease_lapse--> CLOSED
release(task_id) --> DRAINING          the agent that does finish, releasing early
```

`DRAINING` **flushes and merges; it never discards.** The default `on_lease_lapse: MERGE_AND_HOLD` merges the Task's scratch branch into the scratch lineage's main, where it ages out of that lineage's retention window (default 90 days) like any other version. That is one merge per abandoned Task: at 10⁵ agents on 3-day sessions, 0.39 merges/s federation-wide, 0.008/s per lineage across 50 institutional scratch lineages, against a 5–20/s per-lineage ceiling. Merges never conflict, because the scratch lineage's `rel` space is partitioned by `task_id`, so every Task branch is disjoint by construction and Bloom intersection settles it in O(1) per pair.

#### The column every one of the four designs was missing

> **No verb is ever called on this object again. What happens, when, at what cost, and what is lost?**

At 10⁵ agents, most short-lived and many spawning children, this is not the exceptional path — it is the modal one. The archive specification already designed around it: reference counting was rejected for GC precisely *because* "every abandoned branch leaks a permanently inflated count with nobody to decrement it." The lifecycle layer must not treat as a leak the thing the storage layer treats as the norm.

| object | trigger | when | cost | lost |
|---|---|---|---|---|
| Derivation, `ABSENT` | none | never | ~400 B of journal, forever | nothing; it is a name |
| Residency, `ARCHIVED`/`EXACT` | `avail_until` passes | default lease (§14.7) | byte-days until then | nothing; re-`realise` |
| Residency, `EQUIVALENT` | `avail_until` passes | same | same | *the* instance. Refused for a cited one; `extend` or `promote` is offered at `T−lease/4`. |
| Task scratch, `UNFLUSHED` | the next flush | ≤ `flush_cadence_s` | none | nothing; the locus flushes, not the agent |
| Task scratch, `DURABLE_SOURCE` | lease lapse → `DRAINING` → merge | lease + one flush | one merge | nothing for 90 days; then the retention window |
| Task branch | `MERGE_AND_EXPIRE` policy | lease lapse | one sweep | the branch's runs, two GC epochs later — **only if the agent asked for that at `open_task`** |
| Transform image | last citing Derivation and last leasing Task gone | GC epoch | one sweep | the recipe's executability; `entail()` says `TRANSFORM_IMAGE_LOST` first |
| Purpose | `window.not_after` | grant horizon | — | every recipe's *executability*. `AUTHORITY_EXPIRING` offers fire at T−7d and T−24h. |

The invariant, enforced rather than asserted: **no timer-driven transition may destroy bytes the fabric cannot put back.** Under neglect, unrecreatable data gets *more expensive* — it keeps drawing byte-days against a Purpose that has a human behind it — and then expires on a declared, published, agent-chosen horizon. It never silently vanishes on a clock the agent did not know about. Charging an absent agent's Purpose is the only lever that still works when the agent is gone, and unlike the agent, the Purpose is quorum-approved and has an owner.

#### Locus unreachability is not a state

There is no `LOST`. P6 records that a 25 s stall under the index monitor "marks every node LOST and launches a fabric-wide repair storm"; a *terminal, journalled* state derived from a liveness signal with that failure mode is a data-loss report generator that would tell 10⁴ agents their work was destroyed while the bytes sat intact on a slow locus. `locus_unreachable_since` is a derived, revocable view that reconciles when the locus returns. The only terminal transitions are `RELEASED`, `CLOSED` and the GC sweep, and every one of them is journalled by an act, never by a clock evaluated inside `apply()` — which the archive requires to stay pure and time-free, on pain of forking primary from replica on replay.

---

### 14.3 The two write paths, and why the recipe is a by-product

Every one of the four designs stated that the recipe should accrue from working rather than be remembered, and every one then routed recording through an agent-called verb — `step`, `nursery_write`, `note`, `checkpoint`. That is the same discipline problem under a new name, and the enforcement point was wrong in all four: the closure check fired at *consumption*, while unrecorded accumulation happens in work that produces bytes for days and consumes them once at the end. Adjudication, annotation, curation and debugging have exactly that shape, and they are the clinical work this fabric exists for.

The correction is to stop asking the agent to describe the work and observe it instead. The sandbox already has `network_policy: DENY_ALL` (no exception), no inbound path, an `image_cid` stored in the fabric, and an attested measurement. Give it exactly two write paths and make the second one the journal.

**Path 1 — the sink.** A sandbox's declared output, under the Transform's `output_contract`. Entailed by construction: it *is* a Derivation's output, its `rdom_rule` decides taint (`PRESERVE` / `MIX` / `CERTIFIED_DEIDENT`, §3.4), and its `recreation_class` follows its determinism.

**Path 2 — Task scratch.** The agent's own authored bytes: scripts, params, prompts, notes, decisions. Chunked, content-addressed, encrypted and journalled **by the locus**, on `flush_cadence_s`, with no agent verb involved. It is `stage` + a branch commit on the Task's scratch lineage, which is to say it is the ordinary write path (§4.7), already admitted, already billed, already erasure-coded at the lineage's survivability policy, already GC-rooted by the "branch head with an unexpired lease" clause, already covered by sampled proof-of-possession, and already carrying ~~a `K_rdom` row in the shred store~~ **its own per-object key** *(2026-09-19: `K_rdom` and the shred store retired by `eval/results/ckpt_dedup_results.json`; the property Path 2 inherits is **unchanged in substance** — scratch bytes are shreddable by key destruction on the ordinary write path, and the claim is if anything **strengthened**, since scratch objects now carry their own destroyable keys rather than sharing the Task's domain key. The destroy-handle cardinality question of `SPECIFICATION.md` §12.4 applies here too and is recorded as a hole there).*

**The two paths are disjoint by construction, and that is the load-bearing rule:**

> **A sandbox with a non-empty governed read set has no scratch mount.** Its filesystem is read-only inputs, a tmpfs discarded at teardown, and the sink. Task scratch is writable only from a context that has read no governed plaintext.

Three things fall out, and each closes a fatal found in one of the four designs.

**Ordinary program output stops manufacturing the dangerous state.** Every real tool writes outside its declared outputs — TensorBoard logs, `.nfs` lock files, pip and CUDA kernel caches, temp shards, core dumps, framework-written resume checkpoints. Under a rule that counts *any* write outside a recorded step as unexplained, a perfectly ordinary training step lands the agent in the state the design calls "total and unrecoverable", for bytes that are genuinely garbage, and the agent's rational responses are to pay to preserve its pip cache or to stop using the fabric. `Transform.output_manifest[]` declares the output set; everything else in the sandbox is EPHEMERAL by construction, excluded from the recipe, excluded from any byte accounting, and discarded. This is the Nix and Bazel discipline, which all four designs cited as an ancestor and none of them inherited.

**Adjudication is not a scratch case.** A human or agent labelling clinical images *does* read governed plaintext and *does* author bytes. That is Path 1: a Transform whose `input_contract` is the images and whose `output_contract` is `ROWS{schema}`, with `rdom_rule: PRESERVE`, so each label inherits its subject's redaction domain and dies with that subject's withdrawal. That is the correct semantics — a label derived from a withdrawn subject *should* die — and it means the hardest durability case never needs the scratch path at all.

**The scratch domain does not inherit a cohort.** Because nothing that read plaintext can write to scratch, Task scratch gets **the Task's own consent unit in the scratch lineage** *(2026-09-19: was "the Task's own `rdom`"; rename only — **this fix is independent of key granularity and must be preserved verbatim**)*, not the join of 50,000 contributing subject domains. Three of the four designs keyed agent working state under a derived `MIX` key over its inputs' closure, and at `rdom_rule: "subject"` over a 50,000-subject cohort with the document's own 1 %/yr withdrawal rate that is 4.11 expected withdrawals in three days — a 98.4 % chance that a three-day Task's entire authored state becomes permanently unreadable, with not even an approver quorum able to return the agent's own scripts. That is a key-scoping error, and disjoint write paths are the fix.

**What this costs the agent.** Nothing it can perceive: no verb, no flag, no flush call, no discipline. What it costs the *fabric* is the flush volume, which is §14.6 and is the one number in this section that decides whether the design is affordable.

---

### 14.4 Creation, experimentation, failure, retry, branching

Experimentation must be cheaper than not experimenting, or agents route around the fabric and provenance, containment and redaction die with them (§1). The substrate already made the expensive thing free; the lifecycle's job is not to re-price it.

**Start.**

```
open_task(P_irb2026_114, parent_task: null, locus: louisville,
          policy {flush_cadence_s: 900, on_lease_lapse: MERGE_AND_HOLD,
                  on_input_redacted: QUARANTINE_AND_REPLAY,
                  on_authority_expiring: PROMOTE{kymed-derived, run}},
          scratch_quota: 8 GiB, idem_key, token)                 -> Task
```

One journal entry plus one `branch.open`. No quorum, no bytes, no stage allocation. `idem_key` is not optional: crash-restart is the single commonest agent failure mode, `freeze` and `derive` already carry the key for exactly this reason ("otherwise agent retries silently double both the pinned capacity and the Object Lock obligation"), and a creating verb without one mints duplicate leases and duplicate scratch branches at the rate of the retry loop.

**Iterate.** Register candidate recipes, not candidate bytes.

```
derive([F_train], T_tok, {tile:512, stride:256}, idem)   -> D_1   (ABSENT)
... 10^3 variants ...
```

10³ candidate pipelines cost 10³ × ~400 B = 400 KB of journal and 0.3 s at the measured commit latency, touch no drive, no quorum, no permanent capacity, and no merge service. `ABSENT` is not an error state — it is the normal state, and that is what makes failure free. `prospect` all of them, `realise` the three that are `ADMISSIBLE`; the other 997 stay `ABSENT` forever at ~400 B each.

**Fail.** `cancel(job)` returns a Receipt with actuals; the Derivation stays `DECLARED`, residency `ABSENT`; the name survives the failure and remains a citable node in the Task's `derivation_graph`, contributing its actuals to the fleet-wide `build_model`. Cost of a failed experiment: one receipt plus the GPU-seconds actually burned. Coverage is charged for leaves actually delivered to the sandbox, never for the attempt.

**The negative cache, typed.** A failure is recorded as evidence, and this is the one primitive the four designs proposed that is worth keeping — at 10⁵ agents, 10⁴ siblings learning a bad recipe once instead of 10⁴ times is worth more than the positive cache. But it must be typed, because failure is overwhelmingly *not* a function of the recipe:

```
FailureRec { derivation_id, run_id, cause_class, loci_observed[], n_observations,
             first_at, last_at, plant_epoch, expires, receipt_id }
    cause_class: DETERMINISTIC_REFUSAL   -- contract violation, schema mismatch, policy refusal
               | RESOURCE                -- OOM, preemption, no gpu_class at this locus
               | PLANT                   -- mount timeout, DEGRADED_PLANT, transport
               | UNKNOWN
```

Only `DETERMINISTIC_REFUSAL` caches indefinitely, and only after corroboration at ≥2 distinct loci. `RESOURCE` and `PLANT` expire at the plant-state epoch that produced them — cheap, because the Calendar already epochs plant state. `entail()` returns `observed_failures[]` as evidence the caller weighs; it never returns `feasible: false` on cached evidence alone, matching Entail's own posture that the planner is advisory and never binding. Without this typing, one locus's transient OOM marks a working recipe infeasible for the entire fleet, the blocked siblings' own retries extend the window, and denying a competitor a hot recipe costs one journal entry. **No stderr crosses a Purpose boundary** — a parse error that prints the offending record is the ordinary case, and returning it to a foreign Purpose is uncounted egress of exactly the shape that deleted the `METRIC` sink (§8.5). Across a Purpose boundary the cache returns a `cause_class` and a `receipt_id`.

**Retry.** Identical params produce the identical `derivation_id` and attach to the in-flight Job rather than starting a second. The herd control that collapses 10⁴ sibling agents also collapses one agent's retries.

**Branch — there is no branch verb, and that is the point.** The derivation DAG *is* the branch structure. `derive([D_tok], T_a, p1)` and `derive([D_tok], T_b, p2)` are siblings by construction, dedupe by construction, and cost one journal entry each. Twelve variants of a 40 TB working set cost twelve journal entries and **zero bytes**, because the working set is a set of names and the bytes are one refcounted Residency that all twelve `attach` to. Copying instead would be 40 TB at the measured 577 MB/s fragment push — 19 hours and 40 TB of stage, per branch.

The three designs that introduced a copy-on-write workspace fork advertised this same property and got it wrong in one respect worth stating: a CoW fork over one locus's local extent puts twelve branches behind one failure domain while using the word *branch*, which in every system an agent has been trained on implies independent copies. `attach` does not, because a Residency's bytes are `ARCHIVED` or `EXACT` and the failure domain is irrelevant — losing them costs a re-`realise`, not the work.

**Retry after a redaction.** `on_input_redacted: QUARANTINE_AND_REPLAY` is the standing answer: affected Derivations go `UNREBUILDABLE{INPUT_REDACTED}` by the DAG walk the index already holds, the Task quiesces at the last unaffected node, and the agent is offered a priced replay over the surviving cohort. The alternative policy, `ABANDON`, exists because for some studies a cohort minus a withdrawal is not the study.

---

### 14.5 Promotion

**Promotion is not how work becomes durable.** That is the correction the economics lens forced, and it dissolves four separate fatal findings at once. Under §14.3 the un-entailed residue is already `staged_durable` at *n* distinct domains the moment the locus flushes, and the entailed majority is recreatable by definition. So promotion buys neither durability nor safety; it buys **permanence and citability**, which are genuinely scarce and genuinely expensive, and it is therefore the only verb that draws monotonic WORM capacity.

Every design that made promotion the sole exit from an unrecoverable state also made it the most expensive verb in the system, and the attacks all reached the same conclusion: it is strictly dominated, nobody calls it, and the archive receives nothing. Decoupling durability from permanence is what removes the dominance.

#### Three classes, and only the third is expensive

The archive spec already has them; the lifecycle narrows one rule.

| class | where | cost | who asks |
|---|---|---|---|
| `scratch` | LSM, TTL, job lifetime | nothing | implicit |
| `run` | LSM, TTL, no heap | one branch commit | **automatic**: bytes delivered to a completed job, and every Task flush |
| `cite` | heap, `pinned_until = 0`, indefinite | approver quorum + custodian re-materialisation + `archival_durable` + the 4× amplification gate + a slot against the lineage's annual citable-extract budget | a **second Purpose citing it**, or an explicit request paying in full |

The narrowing: the archive rule "an extract whose bytes were actually delivered to a completed job is auto-promoted to cite class" is amended to auto-promote to **run** class. At 10⁵ agents and 3-day Tasks, auto-promotion to cite is 3.3×10⁴ cite pins/day, 1.2×10⁷/year, 4.3 GB of index heap in year one — twelve times the documented 10⁶-cite-pin ceiling and 2.4× the 1811 MB of `DatasetRec.files` the run-structured redesign exists to delete. The ceiling moved from file count to cite-pin count and the lifecycle must not make cite-pin count unbounded in agent count.

**Cite class is demand-driven.** The archive acquires a permanent version when *somebody cites it*, charged to the citing Purpose — not when its author decides. This is the correction to the deepest behavioural problem in promotion: the moment promotion is cheapest (bytes local, inputs warm, nothing to re-recall) is the moment its value is least known, and value is usually revealed by a second party who does not exist yet. Under demand-driven promotion, the author's failure to decide stops being a loss event, and the archive accumulates what was *used* rather than what someone remembered to finish.

#### The call, and the phase order

```
promote(derivation_id | task_scratch_ref, lineage, branch, class, pack_hint,
        idem_key, dry_run?, token) -> Quote | Job | Refusal
```

`idem_key` is mandatory. This is the one path that consumes capacity on media where GC is off by default and reclamation is a ~20 drive-hour cartridge rewrite; a timed-out retry without it silently doubles both the pinned capacity and the Object Lock obligation, which is the precise wording the archive spec uses to justify the key on `freeze`.

**Phase 0 — quote, before anything irreversible.** `dry_run: true` computes the projected xorb set from `pack_hint`, the amplification ratio, the WORM draw at the true multiplier (pin amplification × ~1.7× for two-LTO-generation coexistence), the review lane, and returns an Entail-shaped `ADMISSIBLE | ADMISSIBLE_IF{precondition} | REFUSED{binding_constraint, arithmetic, rewrites[]}`. No bytes are touched and no digests are computed. `stage` already returns `future_read_cost` for the analogous reason; the *irreversible* path had no dry run and the reversible one did.

This matters because the 4× amplification refusal is **mandatory, not advisory**, and it is the routine outcome for agent output: an end-of-experiment selection is chosen by content, which is orthogonal to packing, and `1-(1-p)^1024` puts a 0.1 % selection at 64 % of the lineage's xorbs at *N* = 1. Without phase 0, an agent pays an irreversible repack and a full verify and *then* gets refused; burned once, it never promotes again.

**Phase 1 — admit and draw.** Coverage is **not** re-charged; it was charged at read and promotion is not a disclosure event. Pledge is drawn per contributing institution *at prepare*, not after the commit — the archive's voter predicate 5 already checks "the added bytes fit the reciprocity entitlement" at commit, and paying afterwards on monotonic media means a refused payment cannot be rolled back. Plant, Policy, review lane, amplification.

**Phase 2 — encode and place.** Chunk at fixed 64 KiB *(2026-09-19: CDC retired for content, `eval/results/cdc_largefile.json`; retained for sorted metadata runs)*, `sid = HMAC(K_mac, chunk)`, pack with the contiguity bias under the mandatory `pack_hint`, per-chunk AEAD under the object's key `K_obj` *(was: the resolved `K_rdom`)*, RS(k,m), place *n* fragments at *n* distinct domains, one `xorb.place` per 64 MB.

> **Honest cost. This is not "zero bytes move."** Four designs claimed the live copy is "re-typed, not deleted" at a cost of one journal entry. What is free is the *index* transition and the *absence of a recall* — the bytes are already local, so no mount is scheduled. The encode-and-place pass is real: 200 GB is ~86 s of SHA-256 at the measured 2318.9 MB/s and ~8 minutes of fragment push at the measured 577 MB/s peak with 1.4× egress at RS(10,4). It is priced in `core_bytes` and `stage_byte_days` like any other write, and the Prospectus says so.

A second honest consequence: content addressing is lineage-keyed and dedup is sampled *and* within a redaction domain, so promoting into the lineage the inputs came from preserves `sid`s and dedupes, while promoting into a *new* lineage re-chunks under a new `K_mac` and dedupes against nothing. The two cases differ by the whole dataset, and `promote` refuses-with-arithmetic when the agent has chosen the expensive one by accident.

**Phase 3 — commit.** Branch commit under the leased single writer, then merge. `provenance_class` is forced to `AGENT_DERIVED` — the agent cannot launder its own output as `CURATED` or `INSTRUMENT`, which is the integrity half of the containment story (§8.7) and is not negotiable. `rdom_closure` is joined in and a promotion that cannot name its closure is refused, because an unredactable clinical derivative on WORM is permanent. `dua_closure` is the most restrictive join of the inputs'. A same-`rel` merge conflict is **refused** and the branch is left intact with its lease alive; `promote` returns `Conflict{head, conflicting[]}` as an ordinary outcome with a rewrite, which is the state edge no design had.

**Phase 4 — verify, for cite class only.** Custodians independently re-materialise the selection from the named `v` and recompute `root_pub` before signing. `archival_durable` per xorb. The institutional **approver** quorum, not the coordinator quorum — these are two different bodies and conflating them is what let one design price a per-experiment ceremony at "100–200 ms across 7–9 institutions" when the real cost is five to seven custodians each re-materialising and re-hashing.

**Phase 5 — what happens to the live copy: nothing.** Its `recreation_class` moves to `ARCHIVED`. No bytes move, no lease changes, no refcount changes, and **no protection is released**, because promotion invalidated nothing that was protecting it. Every one of the four designs demoted the live copy's protection on commit — and every attack killed it the same way, because a commit asserts `staged_durable` only, `archival_durable` can be up to **~300 days** away at ~1 TB/day federation-wide against a **30 TB LTO-10** cartridge *(CORRECTED 2026-09-19: was "~180 days … an 18 TB cartridge"; the plant of record is 240 × 30 TB — `SPECIFICATION.md` §14.3. The correction makes the point stronger, not weaker)*, P7 counts a fragment present whenever its node is UP, and proof-of-possession is a 0.1 %/site/year sample. There is no demotion event here to get wrong.

---

### 14.6 The scratch durability hole

The hazard the owner's model creates, stated precisely: *cache* means free to lose, which is true of a materialisation of an archive version and true of a recorded `BITWISE` Derivation's output, and **false of an agent's own authorship**, which exists nowhere else and has no recipe. That residue is the only data in the fabric that is neither durable nor recreatable.

**The answer is one mechanism, not a menu: the residue is ingested through the ordinary write path, automatically, by the locus, at a fabric-set cadence.** There is no mirror, no replication factor, no durability knob and no agent verb. The four alternatives are refuted below on arithmetic, and the arithmetic is the argument.

Throughout, `u` is the un-entailed bytes a Task authors over a 72-hour session, 10⁵ Tasks run concurrently, the federation's daily byte budget is of order 10² TB, and RS(10,4) places 1.4× the object as fragments.

#### Why not forced periodic promotion

Promotion is the only path to monotonic WORM capacity. Forcing a Task's *working set* (the §9-shaped 57 TB of extract, shards, embeddings and checkpoints) is 10⁵ × 57 TB / 3 days ≈ 1.9 × 10⁶ TB/day against 10² TB/day — **four orders over**, into a tier where GC is off by default and reclaiming one **30 TB LTO-10** cartridge costs **20.8 drive-hours of read pass plus the write of the live fraction (~24–27 drive-hours)** and physical destruction of the WORM original *(CORRECTED 2026-09-19 from "one 18 TB cartridge costs ~20 drive-hours"; the plant of record is 240 × 30 TB = 7.20 PB media, `eval/results/plant_contention.json` and `SPECIFICATION.md` §14.3 — the conclusion is unchanged and is strengthened)*. Forcing only the *residue* at u = 2 GB, at 2.27× pin amplification × ~1.7× for two-generation media coexistence, is still 257 TB/day of permanent capacity — 2.6× the entire federation's daily budget, permanently, monotonically. Refuted twice over, and it would also destroy the archive's signal-to-noise: the archive should hold what someone cited, not everything anyone tried.

#### Why not byte replication of working sets

Three-way replicating the working set is the same four orders. Three-way replicating only the residue at u = 2 GB is 3 × 10⁵ × 2 GB / 259,200 s = 2.31 GB/s = **200 TB/day, twice the budget** — and it buys *less* failure tolerance than RS(10,4) at 1.4×, which is 93 TB/day for the same bytes. A bespoke mirror is 2.1× more expensive than the path that already exists, and that is before counting what it lacks.

#### Why not a bespoke replication path at all

This is the choice three of the four designs made and it is the one the archive specification most directly forbids. `stage` + a branch commit gives the bytes, at no additional design cost: a content-addressed digest; an object and therefore a key row in the key store keyed `(lineage, object_id)` *(2026-09-19: was "an `rdom` and therefore a `K_rdom` row in the shred store keyed `(lineage, rdom)`"; `K_rdom` is retired by `eval/results/ckpt_dedup_results.json` — **the argument is unchanged and strengthened**, and must not be swept away with the key it named)* — which is the *only* way live agent state becomes reachable by a consent withdrawal at all, since the key table is keyed by a field a bespoke workspace does not have; survivability-policy placement at *n* distinct domains; GC rootship under a root class that already exists; sampled proof-of-possession; a payer; and P1–P4's fixes already applied. A bespoke journal re-derives fsync-before-ack, `(term, seq)` divergence, truncation and snapshot transfer **at a new layer and a higher write rate**, and the failure mode if it is got wrong is silent loss of exactly the thing the mechanism exists to protect.

#### Why not accept the loss

At a 4 %/yr node loss rate, P(loss during a 72-hour session) = 1 − exp(−0.04 × 3/365) = 3.29 × 10⁻⁴. At 10⁵ concurrent Tasks that is **32.9 destroyed Tasks per 3-day window, ~11 per day, fabric-wide**. The disqualifier is not the GPU-hours — those are recreatable by definition — it is that hand-adjudicated clinical judgements cannot be regenerated, and the subject cannot be asked again. Accepting the loss is a decision to destroy 11 Tasks' authored state per day by policy.

#### What is actually built

```
The locus, not the agent, every Task.policy.flush_cadence_s:
    chunk the Task scratch volume (CDC, sid = HMAC(K_mac, chunk))
    encrypt per chunk under the object's own key K_obj
    // 2026-09-19: was HKDF(K_rdom_task, "chunk" || sid); K_rdom retired
    pack, RS(k,m), place n fragments at n distinct domains
    one branch commit on the Task's branch of its institution's scratch lineage
                                     -- leased single writer; NO quorum round
    return durable_through_seq on the next scratch write ack
```

**Every scratch write ack carries `{durable_through_seq, unflushed_bytes}`.** Not a verb, a field. An agent finishing an epoch can see its durable frontier without asking, and an agent that never looks is protected anyway.

`flush_cadence_s` is a fabric-set default the agent may shorten (paying) and may not lengthen past a published ceiling. **A durability knob with no default and 10⁵ callers has exactly one value**, which is why the four designs that made the checkpoint interval "the agent's own explicit knob" set no default and got `never`.

#### The arithmetic that sizes the cadence

At F = 900 s and 10⁵ Tasks: **111 branch commits/s federation-wide**, 2.2/s across 50 institutional scratch lineages. These are branch commits under a leased single writer, not quorum rounds — the 5–20 commits/s per-lineage ceiling governs the quorum merge, and the merge happens once per Task at close. Against the measured index commit of 0.3 ms on a per-lineage striped monitor (P6) — **which was measured before P1's durability barrier, on an index with no `fsync` anywhere** — add the measured barrier of **0.737 ms per force on Linux node-local storage** (`eval/results/fsync_cost.json`, 2026-09-19, per-call not per-byte). The post-P1 commit is therefore **~1.0 ms**, and 2.2/s per lineage is **~0.23 % of capacity**; the 111 branch commits/s federation-wide are **~11 % of one forced-commit thread**. The cadence conclusion is unchanged, but it now rests on the cost of the index P1 actually builds rather than on the un-fsynced one that was benchmarked. On a shared filesystem the force costs ~29 ms and this arithmetic fails by roughly 30×. ~~2.2/s is 0.07 % of capacity.~~ **The same correction applies to every other bare use of the 0.3 ms figure in this document** — §14.3's "`derive` is one ~400 B journal entry at the measured 0.3 ms commit" and §15 item 9's "a sequencing rule that costs 0.3 ms" are both pre-barrier numbers and read ~1.0 ms post-P1; the argument there is unaffected at either value.

**This is where the design's central scale property is preserved.** Entail's argument is that the derivative firehose does not commit (§9(f)); every one of the four lifecycle designs then routed durability through the commit path and put 10⁵ agents back on the single-writer merge service that §13 defers and Unresolved 7 calls a chokepoint every number depends on. Branch commits under a per-Task leased writer, merged once at close over a `rel` space partitioned by `task_id` so every merge is Bloom-disjoint in O(1), keep the firehose off the quorum entirely. **The durability mechanism for agent work is the one that works today**, not the one §13 defers.

| | u = 60 MB | u = 2 GB | u = 10 GB |
|---|---|---|---|
| fleet plaintext rate | 23 MB/s | 772 MB/s | 3.9 GB/s |
| placed, at 1.4× | 2.8 TB/day | 93 TB/day | 467 TB/day |
| **share of a 10² TB/day budget** | **2.8 %** | **93 %** | **467 %** |
| journal, commits + `xorb.place` | 9.6 × 10⁶ /day | 1.1 × 10⁷ /day | 1.5 × 10⁷ /day |
| bytes lost per destroyed Task | 208 KB | 7 MB | 35 MB |
| bytes lost per day, fabric-wide | 2.3 MB | 77 MB | 385 MB |

> **The binding constraint, stated as one number: at 10⁵ agents on 72-hour sessions, the fleet's entire un-entailed residue must stay under ≈ 2.1 GB per session to fit a 10² TB/day federation budget, and under ≈ 210 MB to stay inside 10 % of it.** Every design in this line rests on a constructed estimate of that number and none measured it. It is measurement #1 in §14.14.

The journal figure is also a real consequence and must be stated: ~10⁷ entries/day is comparable to the 1.6 × 10⁷ entries a whole petabyte of ingest produces, against a primary that **never truncates its journal today** and a `log_retain` that is still an entry count rather than a byte budget. Scale limit 9's checkpoint-and-truncate path is therefore a **prerequisite of this section**, not an improvement.

#### What is lost, and when

The exposure is exactly one flush interval: 15 minutes of authored bytes, ~208 KB at u = 60 MB. Everything else at a destroyed locus is `ARCHIVED` or `EXACT` and costs a re-`realise` — and **the recipe survives the locus by construction**, because the Derivation DAG lives in the index journal, which is already replicated, rather than in a workspace log at the locus that died. That is the whole reason no bespoke recipe-replication path is needed: three of the four designs built one, and in each case the attack showed the design's own scale arithmetic proved only a chain *head* reached the fabric while the bodies stayed at the dead locus.

#### Two residual holes, both named

**A long step is one step.** A six-hour training run is one Derivation; losing the locus at hour five loses five hours of GPU. The flush cadence does not help, because the output does not exist until the step ends. The mitigation is `resources.checkpoint_interval_s` on the Transform, which makes intermediate state a sink write; it is not free, it depends on the transform author, and nothing forces it.

**`staged_durable` is an assertion the fabric may be wrong about.** P7 records that `derivedState` counts a fragment present whenever its node is UP and `fr.st == "OK"`, and `scrub()` iterates the store's own rebuilt inventory, so a fragment deleted at a live holder is never reported; proof-of-possession is a 0.1 %/site/year sample. For the one class that cannot be rebuilt, that is not good enough. **Scratch lineages get a raised PoP rate: 5 % per site per quarter.** At u = 60 MB the standing scratch volume is ~252 TB fabric-wide over a 90-day retention window, so 5 %/quarter is 12.6 TB of reads per quarter on the stage tier — disk, zero mounts, ~1.6 MB/s sustained. It is the cheapest correction in this section and it covers the only bytes whose loss is final.

---

### 14.7 Eviction

**There is no eviction policy, because the fabric never chooses which cached object to destroy.** Under the owner's rule nothing is waiting on cold data, so "this locus has no stage" is answerable the way every other scarcity in Entail is answered — a refusal naming the binding constraint, with arithmetic, rewrites and a queue position. Eviction reduces to **lease expiry plus admission refusal**, which needs no ranking function, no price, and no new verb.

This deletes the largest single block of machinery the four designs proposed, and the reason is not aesthetic. Every one of them needed `replacement_cost` as a scalar at the moment stage pressure crosses a threshold, and that number is not computable there: it requires the leaves → chunks → xorbs → cartridge-position expansion that §4.2 refuses as a free synchronous call and prices as a job, and the pass must run precisely when the locus has no headroom to run it. Three of the four then had to invent a federation numeraire to add GPU-seconds to drive-seconds — which §12 rejected outright ("A price is the right thing to hand a planner. Rejected.") and which is a fresh cross-tenant covert channel directly contradicting §3.5's bucketing rule. A wrong shadow price also fails *simultaneously and fabric-wide*, unlike LRU, which fails locally and idiosyncratically.

The observation that "LRU is wrong here" is nevertheless correct, and its correct residue is not a ranker:

> **The default lease is a function of what the realisation cost. Set once, at admission, from measured actuals, at the only moment the number is known exactly and for free.**

```
avail_until = now + clamp( lease_min,
                           p90 inter-arrival of Intents naming this target over the last N epochs,
                           band(recreation_class, realised scarcity terms) )
```

Demand comes from the Intent book, which is the only honest source: an agent cannot predict whether its embedding table will be reused, because that depends on whether the model trained on it worked, which is the question the job exists to answer. `reuse_hint` is deleted before it is invented — a free declaration that buys protection is not an estimator, it is a free pin.

Where no Intent history exists, the fallback is a **coarse ordered band, not a scalar**: ranking needs order, not magnitude, and bands are index-resident and need no plant state.

| band | example | default lease |
|---|---|---|
| tape-resident, `pack_alignment: ORTHOGONAL` | 40 TB scattered, ~926 drive-hours *(basis unstated — see note)* | 30 d |
| tape-resident, `ALIGNED` | single-library sweep, 3–4 h | 7 d |
| disk-resident recall | warm stage elsewhere | 2 d |
| `EXACT`, inputs resident | 22 GPU-min rebuild | 6 h |

> **2026-09-19, RECORDED NOT CORRECTED.** The ~926 drive-hour figure appears **five times** in this document (§9(a) context, the `ARCHIVED` lifecycle row, here, §14.8, and the S14 attack table) and **its basis is nowhere stated.** Against `eval/results/plant_sim.json` it reads two ways and they differ by up to 4×: as **payload** bytes, 40 TB is **232 drive-hours** at the measured scattered batched-and-ordered rate (172.3 GB/drive-hour) or **588** reactive (68.1); as **fragment** bytes at `SPECIFICATION.md` §14's 1.714× combined coding rate it is **~1,008** reactive, which is what 926 most nearly matches. So the figure is plausible under a reactive dispatcher with amplification included, and roughly 4× conservative under the scheduling this system specifies. **Before re-quoting it anywhere, state which basis it is.** Unaffected either way: the band *ordering* (a scattered tape recall is still four orders above an `EXACT` rebuild) and §14.8's conclusion that a warm copy beats a second cold recall — 8.9 h of one uplink against hundreds of drive-hours holds under every reading. **When the basis is settled, fix all five occurrences together or the document will disagree with itself.**
>
> **Separately, this row is a servability defect.** `SPECIFICATION.md` §8.4 refuses packing-orthogonal reads outright — `SAMPLE_ORTHOGONAL_TO_PACKING`, with the `1 − (1−p)^c` arithmetic attached and a derived sample-ordered lineage offered — and §9(a) of this document already assumes that refusal three lines above. **An `ORTHOGONAL` tape-resident residency is therefore not a servable class with a 30-day lease; it is refused at admission.** The ~926 drive-hour figure is preserved because it is the cost that justifies refusing.

Four bands span the 10⁴ recreation-cost range in *ordering*, which is all a lease needs. `avail_until` remains monotone-raised-only, so **no verb that lowers a lease is required** — the archive has none, and three of the four designs needed one for a fabric-initiated eviction that no longer happens.

**Who decides, in a fixed order.**

1. **The Purpose that paid.** Inside `caps.physical.stage_byte_days` it raises the lease with `extend`. Held-but-unused capacity is billed continuously in byte-days, so hoarding is self-limiting without any policy (§4.6), and `pin_bytes` remains the cap on indefinite holds.
2. **The fabric**, which sets the default lease above and, under pressure, **refuses new admission** — `REFUSED{binding_constraint: STAGE, arithmetic, rewrites[{ATTACH to R-4471, COMPUTE_AT@lexington, intend at 03:00}], calendar_position}`. It never destroys.
3. **The Task's standing policy.** `on_stage_pressure: SHRINK | REFUSE_NEW | RELEASE{targets[]}`, declared at `open_task`, evaluated by the fabric with no agent present — because the agent will not be present. A 900-second negotiation window with a pull-only `offers` channel collects no decision from the modal agent and adds 900 s of latency to every eviction; four designs built one and the attacks agreed it was the worst of both policies.

**What the fabric may never do:** free bytes whose `recreation_class` is `UNFLUSHED` or `DURABLE_SOURCE`, or free a residency with `refcount > 0` or an open cursor. Task scratch is bounded instead at admission: `scratch_quota` is checked at `open_task` against the Purpose's caps and at each `realise`, and an over-quota write fails that job rather than wedging the locus. That is the difference between an unbounded promise not to reclaim — which three designs made and which wedges a locus permanently at 10⁵ agents — and a bounded one.

---

### 14.8 Sharing

**Same locus: yes, at xorb granularity, and the win is larger than it looks.** Residency is refcounted and content-addressed on `xid`, and §2's amplification arithmetic runs in our favour here: two independent 1 % selections of a lineage each touch >99.99 % of its xorbs, so their xorb sets overlap almost completely even when their *file* sets barely do. The property that makes selective pinning catastrophic makes cache sharing near-total, and the second agent's marginal physical cost is an index lookup. This is why `ATTACH` is the dominant strategy in §5.3 and why residency, not storage policy, is the real lever.

**Different loci: no byte sharing, and the reason is physics, not policy.** One fragment per failure domain, *k* of *n* to decode, so assembling a second copy costs one object's worth of bytes wherever you decode it — recall cost is invariant under fetch-versus-ship (§2). What *can* be shared is the recall and the plan:

- `intend`'s `coalesce_key` over cartridge groups puts two agents' overlapping demand in one pass. This is the primitive that matters and it works precisely *because* nobody is waiting: demand can be batched days ahead.
- A warm copy beats a second cold recall by a wide margin — 40 TB decoded over the core at 10 Gb/s is ~8.9 h of one uplink and **zero mounts**, against ~926 drive-hours of re-recall *(basis unstated — §14.7 note, 2026-09-19)*. `prospect` prints it above the strategy table as the invariant shared cost, and `REDUNDANT_RECALL` refuses a cold recall when a warm copy exists at a permitted locus.
- Honestly: for a state-wide clinical fabric under a DUA, `materialisation_policy` and jurisdiction tags will frequently forbid the warm copy, and then both Purposes pay a full decode. That is a real cost, not a solved problem.

**Who pays: the recall is charged once, to whoever caused it. A later attacher pays its own decode, its own `index_ops`, and its own Coverage in full.** `payer_ledger.attach_credits` is **deleted**, along with every rebate, join fee and guarantorship transfer in the four designs. Each of those was broken by its own attack in a different way — a formula that cannot reach its own cap and pays 30:1 to whoever waits; a Shapley-lite split under which late joining strictly dominates; an even re-split that makes the last attacher inherit the whole bill and produces a release stampede on exactly the most expensive residencies; a rebate denominated in drive-seconds the fabric cannot mint without drawing down the plant reserve. `first_payer` survives as a provenance field; the settlement does not.

Does that reopen the deadlock-by-politeness equilibrium §4.6 warned about? No, and `intend` is why. Waiting is not free: an agent that does not declare is simply absent from the demand curve and nothing is scheduled for it. Coalesced wave cost is split at wave time among the Intents in the wave, by bytes drawn, settled once and backward-looking. Post-wave joiners pay decode only, because the tape cost is genuinely sunk and charging for a free good is how you teach agents to route around the fabric.

One consequential deletion follows: **`Prospectus.calendar_position.coalesces_with` is removed from the agent-visible answer.** It publishes the moment at which a 10³–10⁵ drive-second cost becomes zero, which converts "wait for someone else to pay" from a gamble into a reliable strategy, and it contradicts §3.5's own rule that the Calendar carries no cartridge identifiers and no per-peer instantaneous load. The fabric may still coalesce on it internally; the agent sees a lane, a position and a projected window.

**One releases while the other still needs it.** `refcount > 0` blocks freeing. A departure changes nobody's accrued bill and nobody's future bill, because `avail_until` was already raised and paid for by whoever raised it and leases never shorten. The remaining attacher's next `extend` is an ordinary admission decision with a queue position and a rewrite — which is the right place for a capacity refusal to land. No hot potato, no inherited liability, no guarantorship an inheritor never accepted.

**Coverage never shares.** Two Purposes attaching one residency each charge the delivered leaves into their own union, in full, regardless of where the bytes came from. That immunity to caching is precisely why Coverage is a union rather than a sum (§8.2), and a shared cache that laundered coverage would be the cheapest attack in the system. It follows that **a Task handoff preserves `purpose_id`**: cross-Purpose transfer of live bytes is legal only via `promote` — archive-mediated, verified, rdom-closed, and re-read by the second Purpose under its own Coverage — or via a fresh `realise` charged in full. Refusal code `CROSS_PURPOSE_HANDOFF`.

---

### 14.9 Recreated anywhere

A cache is reconstructible elsewhere iff its recipe closure is complete *and resolvable inside the fabric*. Three tiers, because "exact" means three different things and conflating them is how reproducibility claims rot.

**Tier 1 — bit-identical from the archive (`ARCHIVED`).** Already solved and unchanged: `(cut_id, fset_id, selector + grammar_v, enum_cid, leaf_salt_cid, root_pub, cod{k, m, chunk_avg, key_epoch, fmt}, key_id/custody_ref, index_seq, term, redaction_chain_head)`. `ExtractEnum` inlines spans, so reconstruction needs nothing from the index: `xid → place/loc → the planner selects k deterministically at plan time *(2026-09-19: was `race k of n`; racing is retired on any mount-class tier, `SPECIFICATION.md` §8.5 — a cancelled tape read does not return the drive early)* → RS decode → per-chunk GCM verify → whole-file sha256 → leaf commitment → root_pub`.

**Tier 2 — bit-identical by recipe (`EXACT`).** `derivation_id = H(canonical{inputs[], transform_id, params_digest, codec, env_cid})` plus `transform.image_cid` **stored in the fabric**. Necessary and not sufficient: Entail's `env_class` is a name, and bit-identity across sites fails on things a name does not pin. It is replaced by a content-addressed record:

```
ExecutionEnvironment {
  env_cid, cpu_isa_baseline, gpu_arch,
  blas_cid, libm_cid, runtime_cid,            -- bytes in the fabric, like image_cid
  thread_count_policy: FIXED{n} | REDUCTION_ORDER_INVARIANT,
  reduction_order_pin,                        -- deterministic kernels, fixed accumulation order
  math_flags { fma, fastmath: off, denormals: IEEE },
  rng { prf_name, seed, counter },
  locale: C, timezone: UTC, fs_iteration: CANONICAL_SORT
}
```

Non-associative floating-point reduction is the actual reason "same code, same data, different bytes", and without `reduction_order_pin` a `BITWISE` claim is false. The closed list of forbidden non-determinism sources a `BITWISE` transform may not touch: wall clock, unseeded RNG, thread-count-dependent reduction order, hash-map iteration order, uninitialised padding in serialisers, `/dev/urandom`, host path strings, and the network (already `DENY_ALL`). Naming the six that actually break cross-site replay is cheaper than discovering them.

**`env_cid` is derived from the locus's attested measurement, never declared by the agent.** `Locus` already carries `attestation{tee, measurement}` and `gpu_class`. A verification-sampling regime that resets on a *declared* environment change asks the party with the strongest interest in cheap promotion to volunteer the fact that makes it expensive.

**Determinism is a claim, so it is bought, not asserted.** `Transform.determinism_state: CLAIMED | VERIFIED | REFUTED`. On first registration of a `BITWISE` transform the fabric executes one derivation at **two loci with distinct `env_cid`** and compares output digests. Cost: one extra execution per `transform_id`, once, amortised across every derivation that transform will ever produce — and `transform_id` already dedupes fleet-wide, so 10⁵ agents pay for one probe. It is **funded from the plant reserve, not by the registering agent**, because the fabric is the beneficiary: `determinism_state: VERIFIED` is what licenses the fabric to let a lease lapse on the strength of "we can put it back". Charging the registrant to protect the fabric's own decision is the clearest misallocation the four designs contained.

A mismatch demotes the transform to `STATISTICAL` fleet-wide and marks every citing Derivation `NOT_REBUILDABLE_TO_SAME_BYTES`. **Before attributing any mismatch to the transform, the verifier compares the inputs' `rdom_closure` and `shred_epoch` at both build times**; a mismatch whose input closure changed classifies as `INPUT_REDACTED` and demotes nothing. Without that arm, a consent withdrawal landing between build and replay — a routine, legally mandatory, roughly daily event on a cohort-scale lineage — is attributed to the transform and demotes it fleet-wide, irreversibly.

Until the probe passes, a transform is `CLAIMED` and its outputs are treated as `EQUIVALENT`.

**Tier 3 — equivalent, and equivalence made checkable (`EQUIVALENT`).** `STATISTICAL` requires `{seed_params, tolerance, env_cid}` **plus an acceptance test registered as a Transform with a `ROWS` output contract**. If no acceptance test is registered, the fabric records `NONDETERMINISTIC`, not `STATISTICAL`. Otherwise "statistically equivalent" is an unfalsifiable excuse rather than a predicate, and the class means nothing. A rebuild is accepted iff the acceptance test passes; on failure the object is marked `EQUIVALENT_DIVERGED` and every citation of it is flagged, because a rebuild that quietly substitutes is worse than a refusal.

#### Two identifier corrections

**A `NONDETERMINISTIC` derivation's id does not identify its bytes.** `derivation_id` is a hash of the *recipe*, explicitly not of the output — which is sound for `BITWISE` and is the herd primitive that collapses 10⁴ siblings onto one job. For a nondeterministic recipe it puts two different byte sets at one address, which is exactly the same-id-different-bytes path the archive's identifier rule exists to forbid ("an object's id is a keyed hash of its own canonical bytes, never derived from a property of the thing it describes"). Two agents running the same nondeterministic recipe would be silently cross-wired onto one another's bytes, with the receipt recording the wrong actor chain and the wrong institution's pledge drawn under a DUA. And it breaks the experimentation primitive itself: an agent measuring run-to-run variance would issue the same `derive` twice and receive one sample.

> A Derivation whose `determinism_state` is not `VERIFIED`-`BITWISE`, and which has no seed in `params`, carries a durably journalled per-execution `run_id`. Its citable name is `derivation_id‖run_id`, and `derive`/`attach` coalescing refuses to join two such derivations however equal their `derivation_id`.

**`params` are unshreddable plaintext unless split.** For fleet-wide dedup, `params` must be canonically comparable, so they are in the clear wherever a locus evaluates them, replicated with the journal, and retained verbatim in every cert. Agent params are exactly where a cohort list, a subject identifier or an MRN-derived filter lands, and destroying a content key kills chunk plaintext, not a hash preimage the fabric must retain in order to dedupe *(2026-09-19: was `K_rdom`; rename only. Note the term "fleet-wide dedup" here means **recipe/param dedup**, which is untouched by the retirement of content dedup — see §4.3)*. **`params` splits into `params_digest`, which enters `derivation_id`, and `params_payload_cid`, an ordinary chunk under its own object key.** Dedup and attach operate on the digest; the payload is shreddable. `params_schema` types any field carrying subject identifiers and refuses it inline — the same treatment `list-digest` already gets in the selector grammar, which anticipated this exactly.

#### What is deliberately not recorded

Locus, site, cartridge VSN, serpentine position, wave order and size, fragment placement, which *k* of *n* won the race, residency shape, transport compression, stage backend, and scheduling window.

> **This is the clearest single thing the owner's rule buys.** Because no caller requires low-latency access to cold data, a rebuilt cache owes the original its *contents* and not its *latency profile*, so the recipe never has to say where anything was — only what it was. Recording physical position would make every cache reconstructible only where it was born, and would be wrong after the first media migration. It is the same rule the archive already applies to activation plans ("the plan pins logical xids only"; `loc` is mutable by design), extended to caches, in one line.

#### Refusals

`entail()` and `realise` name the missing closure element rather than failing at build time: `INPUT_UNREBUILDABLE`, `INPUT_REDACTED`, `INPUT_SWEPT`, `TRANSFORM_IMAGE_LOST`, `AUTHORITY_EXPIRED`, `ENV_RETIRED`, `CUSTODY_BELOW_THRESHOLD`, `PLANT_DEGRADED`, `NONDETERMINISTIC`. Because the verdict is published on every response and decays, an agent watches its own work becoming unbuildable rather than discovering it six weeks later when a rebuild fails.

---

### 14.10 A withdrawal lands while a live cache holds the plaintext

Key destruction settles the archive instantly, everywhere, at zero mounts and zero bytes moved (§6.4). It does nothing about plaintext already decoded into a locus's stage. That gap is created entirely by permitting plaintext at rest, and the owner's rule means we do not have to permit it.

#### The stage holds ciphertext

A staged xorb is stored exactly as it is stored on tape — per-chunk AEAD under the object's key `K_obj` *(2026-09-19: was `HKDF(K_rdom, "chunk"‖sid)`; rename only)* — and is decrypted on the stream into the sandbox. RS decode happens once, into the stage; GCM decrypt happens per pass, on the stream.

The cost is honest and small: decrypt-per-pass instead of decrypt-once, at the measured 3411 MB/s, which is ~1 core-minute per 200 GB per pass. A 12 TB tokenised set is 4.2 minutes at 14 threads per epoch, against 5.8 hours to stage the same 12 TB at the measured 577 MB/s fragment push. Decrypt is 1.2 % of the staging cost and 5.9× faster than the push, so it is never the bottleneck. **This is a throughput cost, not a latency cost, which is precisely the cost the owner's rule says is affordable.**

What it buys: **a key shred reaches every cached byte in the fabric at the same instant it reaches WORM, for zero I/O and zero fan-out.** *(2026-09-19: was "a `K_rdom` shred"; the property is unaffected by the key rename and is what retires the per-locus plaintext inventory, the ~50-locus shred fan-out, `attest_purge`, purge receipts, locus quarantine-for-non-ack and the 60 s / 135 s / 300 s purge SLOs in the §14.12 removal table.)* The archive's blast radius becomes the live tier's blast radius, with no second mechanism.

#### The one new mechanism: a chunk-key lease

A sandbox never holds a content key *(2026-09-19: was `K_rdom`)*. The locus's key agent holds the keys the current jobs touch and issues short-TTL derived chunk keys. Two rules:

1. It refuses to issue or renew once it observes `shred_epoch ≥ S` for that lineage.
2. **It fails closed on staleness.** The key agent renews a `shred_epoch` watermark from the index within the lease TTL; if it cannot — partition, reboot, reconnect — it stops issuing, unprompted. A partitioned locus becomes the *safe* case rather than the worst case. This is the index tier's existing fail-closed staleness rule (a replica beyond its staleness bound refuses to serve) applied one layer out, and without it the purge SLO is unbounded in exactly the failure it exists to cover — this fabric's own measurements record ~20 s failover reconnects and up to ~44 s for all agents to return after a global restart.

| knob | new-decryption window after shred | index load | share of measured `resolve` ceiling |
|---|---|---|---|
| TTL 60 s | ≈ 75 s (TTL + measured 14.2 s replica lag) | 1,667 renewals/s | 31 % of 5,397/s |
| TTL 120 s | ≈ 135 s | 833/s | 15 % |

**60 s is the recommendation.** Note the ordering is the archive's own, inherited rather than reinvented: seal first, destroy later — the shred converges at the index *before* any lease can be renewed, so there is no window in which one locus serves and another refuses.

#### Sequence

```
T0        redaction.order      institutional approver quorum, authority recorded
T0+ms     redaction.shred      wrapped object-key rows for the consent unit destroyed; key store
                               compacted   [2026-09-19: was "wrapped K_rdom row destroyed; shred
                               store compacted" -- K_rdom retired, rename only]
                               ARCHIVE AND STAGE BOTH COMPLETE HERE. Zero mounts, zero I/O.
T0..+75s  key leases lapse at every locus; no new chunk of that unit decrypts anywhere
          [!! 75 s IS ESTABLISHED FOR LARGE-OBJECT LINEAGES ONLY, pending the lease-aggregation
           hole at SPECIFICATION.md 9.5: at object granularity a 200 GB cohort of 80 KB clinical
           notes is ~2.5e6 objects, ~41,700 mints/s at TTL 60 s, inside 9.5's own declared
           not-servable regime. The same annotation applies to the TTL table above.]
T0+ε      the DAG walk marks every dependent Derivation UNREBUILDABLE{INPUT_REDACTED}
T0+ε      running jobs whose rdom_closure intersects: SINK HELD, output QUARANTINED
          Transform.on_redaction: KILL (default for the CLINICAL lane) | DRAIN{max_s}
          Task.policy.on_input_redacted fires: QUARANTINE_AND_REPLAY | ABANDON
```

**Holding the sink is the part the four designs missed.** A job already holds the subject's bytes in its address space, its page cache and possibly GPU memory, and it continues to `resources.walltime_s` — hours for a training transform. Fencing bounds *new* reads; it does not stop rows derived from a withdrawn subject leaving the sandbox cleanly with a valid receipt after the withdrawal. So the sink is held, the output is quarantined pending re-derivation, and the receipt records the shred's `index_seq` as the truncation point.

**Derivatives need no sweep at all.** `PRESERVE` outputs inherit the subject's consent unit ~~and are chunk-keyed under the destroyed key — dead instantly, in every version, every pinned extract, every stage and every cache~~ **— RETIRED 2026-09-19.** `MIX` outputs are keyed by `HKDF(K_obj_1‖…‖K_obj_j, "derived"‖derivation_id)`, computed and never stored, so any one contributor's destruction makes them underivable — **`MIX` is unaffected**. `CERTIFIED_DEIDENT` breaks the closure with a certifier and an approver quorum on the record.

> **HOLE, and it is the largest one the retirement opens.** Under `K_rdom` a `PRESERVE` derivative was encrypted under the **same key** as its input (§3.4: "each output leaf inherits its input leaf's `rdom`"), so its death was **structural**: it reached write-once media, every pinned extract, every stage and every cache with no catalogue involved. Under per-object keys the derivative has **its own key** and dies only if the destroy set **enumerates** it — **converting a cryptographic property into a catalogue obligation that must be correct, replicated, and never lost, for the life of the medium.** `MIX` is unaffected, because its key is derived from contributors and never stored, so AND-survival remains structural. Two candidate resolutions exist — deriving the `PRESERVE` output's key from its input's, or a durable closure record on WORM — and **neither is chosen here**, because each is a WORM-permanent commitment and no measurement bears on the choice.

**Task scratch is reachable.** Because it was committed to a scratch lineage under the Task's own consent unit (§14.3), it has a `(lineage, object_id)` row in the key store like everything else *(2026-09-19: substituted for `(lineage, rdom)` / shred store; **the argument is unchanged and is strengthened** by per-object keys, and must not be swept away with `K_rdom`)*. Live agent state that has no lineage has no row, no key and no shred path — which is why the four designs that invented a lineage-less workspace could not make redaction reach it, and why this one does not invent one.

#### Two consequences that must be published rather than discovered

~~**`rdom_rule: "lineage"` is refused for consent-bearing lineages.** Every blast-radius claim in this document assumes per-subject domains, and `rdom_rule` defaults to `"lineage"` with one domain for the whole dataset. On a default-configured clinical lineage, one withdrawal darkens every cache, every derivative and every Task scratch blob derived from it — roughly 1.4 fabric-wide events per day on a 50,000-subject lineage at the 1 %/yr rate the archive's own arithmetic uses. So: a lineage whose `provenance_policy` admits a Purpose with `authority.kind ∈ {IRB, DUA}` must declare `rdom_rule: "subject"` at ingest, or `high_redaction` per-object keys. Retrofitting is a re-encode (Unresolved 9), so this is an ingest-time gate, refused at `open_branch`.~~

**RETIRED 2026-09-19** — `eval/results/ckpt_dedup_results.json`. Per-object keys are the only mode, so every lineage has per-subject blast radius by construction; the ingest-time gate, the `open_branch` refusal and Unresolved 9's re-encode are all gone. **Scope the claim precisely: the BLAST-RADIUS claims throughout this document now hold unconditionally rather than conditionally on a declaration. The LATENCY claims do not** — see the `SPECIFICATION.md` §9.5 lease-aggregation hole, which leaves the 75 s shred window established only for large-object lineages.

The escape is no longer an escape; it is the design. The CDC measurement in `STORAGE-DIRECTION` found chunk-level content dedup worth **−5 % to +1 %** on the real mutation profile — the populations Entail names as dominant mutate by overwrite and append, where fixed chunking ties or wins, and imaging is add-only where whole-file reuse captures everything. Dedup within a redaction domain is what made per-object keys unaffordable at D1. ~~If that measurement holds on real checkpoints — which it has **not** yet been run against, and the measurement says so explicitly~~ — **the measurement has now been run** (`eval/results/ckpt_dedup_results.json`, 2026-09-19): adjacent checkpoints of a real SFT run share **exactly zero** of 184,044 64 KiB weight blocks, distant zero, the two weight copies inside one checkpoint zero, and a cross-run control zero. Per-object keys are the cheap default, and **`K_rdom` is retired outright rather than demoted to an optimisation** — it has no remaining job in the key layer.

Keep the paragraph's original caution as record: it was right that the large-file measurement's pseudo-random base could not settle this, and right to refuse to act on it. **And note the two jobs `K_rdom` also did, which it leaves behind:** aggregating keys for leasing (`SPECIFICATION.md` §9.5) and for packing purity (§8.4), both now open holes.

**A `MIX` aggregate over a cohort has a half-life of hours.** With the consent unit at subject granularity, *j* = |cohort| **in subjects, never in object keys** *(2026-09-19: `rdom_rule` is retired but the counting unit is not — see `SPECIFICATION.md` §9.7; the arithmetic below is driven by subject withdrawals and is **unchanged**)*, and any one withdrawal makes the derived key underivable. At 50,000 subjects and 1 %/yr, withdrawals arrive at 1.37/day, so the expected time to underivability is **ln 2 / 1.37 ≈ 0.51 days**, and P(a 3-day-old MIX derivative is already dead) = 1 − e^(−4.11) = **98.4 %**. AND-survival is the correct semantics and this is its correct consequence, but neither prior document states it and an agent will discover it as an unexplained failure.

> `derive` returns `expected_underivable_by` on any `MIX` derivation whose `|rdom_closure|` exceeds a threshold. `MIX` is the right primitive for a *transient* aggregate — an `ask` answer, a cohort statistic consumed in the same job. An aggregate intended to persist must either go through `CERTIFIED_DEIDENT`, with the certifier and approver quorum on the record, or be promoted and assigned its own `rdom` at ingest. The refusal says which.

#### The honest limits

A compromised or partitioned locus holding plaintext in RAM cannot be made to forget; the key lease bounds what it can decrypt *next*, not what it already holds. A model that has read governed data has read it, machine unlearning is not solved, and §8.6's boundary policy — the model is itself a governed artefact deployable only at permitted loci — applies instead of erasure. Reproducibility downstream of a withdrawal is permanently and visibly broken, and `entail()` returns `INPUT_REDACTED` rather than quietly producing different bytes.

---

### 14.11 What dropping interactive cold reads deletes

The owner's rule is two claims, and the second is the larger one:

1. **No latency SLO on cold data.** A request may be answered with a queue position and a future window instead of bytes. Entail already encodes this — `intend`, lanes, `Calendar`, `DEGRADED_PLANT`.
2. **Everything live is a projection of something immutable** — a `VersionRoot` or a recorded recipe. A live copy's *content* therefore cannot be stale. It can only be absent.

Stated once, in the contract: **a cache miss on cold data is a scheduling event, not an error.**

| deleted | who needed it | why it goes |
|---|---|---|
| Every eviction ranking function — regret density, `keep_score` in drive-second-equivalents, Landlord/GreedyDual — and the federation numeraire each needs | all four designs | the fabric never chooses which object to destroy; lease expiry plus admission refusal is the whole policy (§14.7) |
| Shadow prices per scarcity term, published per epoch | three designs | a new cross-tenant covert channel, and §12 already rejected handing a planner a price |
| `EVICTION_NOTICE`, the ≥900 s window, COOLING markets, `guarantee()`, grace-window auctions | all four | nothing is evicted, so nothing needs to be negotiated with an agent that is not listening |
| `reuse_hint`, `P(reuse)` declarations, hint reputation scoring, hint bonds | all four | demand is read from the Intent book, which the agent declared for its own reasons |
| `Residency.eviction_class` | §3.5 | vestigial once eviction is lease expiry |
| A verb that *lowers* a stage lease | three designs | the archive has none, monotone-raised-only is inherited unchanged |
| The per-locus **plaintext inventory** (`residency_id → rdom → extent list`), the shred fan-out to ~50 loci, `attest_purge`, purge receipts, locus quarantine-for-non-ack, the drop-the-whole-residency fallback, and every purge SLO (60 s / 135 s / 300 s) | all four | ciphertext at rest on the stage makes the archive's shred the live tier's shred, at zero I/O and zero fan-out (§14.10) |
| The new live-state noun — Workspace / Bench / Nursery / Cell — its state machine, its lease, its GC rootship, its index heap, and its collision with P3's 2³¹−1 `GSON.toJson` ceiling | all four | `Residency` and `Task` already exist; §14.2 |
| Three bespoke recipe-replication subsystems (step chains to *k* peers, `journal_cid` to 3 loci), their lag bounds, peer-set selection, replication attestation and partition semantics | three designs | the Derivation DAG is already in the index journal, which P1–P4 are already fixing once |
| Four bespoke scratch mirrors, `replication_free_quota`, `capture_local`, the durability-class knob | all four | `stage` into a scratch lineage gives the bytes a digest, an `rdom` row in the shred store, survivability placement, GC rootship, proof-of-possession and a payer — none of which a mirror has (§14.6) |
| `seal`, `ProtocolCert`, the `SEALED` state, workspace-prefix-as-Derivation, and every live-tier citable class | all four | citability is an archive property; an agent wanting a citable name for work in progress already has `derivation_id`, free, with no bytes and no quorum |
| `capture` / post-hoc recipe attachment in all its forms | all four | `derive` before you compute; §14.3 |
| The join fee, first-payer rebate, attach credits, guarantorship transfer, pro-rata re-split, `Offer{COALESCE}` settlement | all four | one recall, charged once, to whoever caused it; `intend` coalesces demand instead of negotiating cost (§14.8) |
| `Prospectus.calendar_position.coalesces_with` | §3.6 | publishes the moment a 10³–10⁵ drive-second cost becomes zero; a defection oracle contradicting §3.5's own bucketing rule |
| `Residency.shape: STREAM{order}` — the caller-pinned `order`, on cold targets | §3.5 | a sink-pinned order forces whole-selection staging before the first frame when the physical order differs, defeating the ordinal wave frontier the substrate built to avoid exactly that. Deliver physically optimal; the consumer shuffles over the staged residency, where it is free |
| `fetch(...) outside the frontier → 403 InvalidObjectState + Retry-After` | archive spec, *Activation* | `realise` is the only byte verb and `intend` is the answer to "not yet". The protocol measurement settles it: a sealed `404`, `403` and `503` with `Retry-After: 900` all return byte-identical errors to the caller, so no status code and no header survives that client. Under this rule the surface never has to exist |
| Warm-standby workspaces, a cold-read prefetcher, per-open latency SLOs, surgical in-place patching of a live extent | implied by all four | a quiesced Task is rebuilt, not kept warm |
| Any cache-coherence protocol: invalidation, write-back, read-your-writes on the live tier, a consistency model for copies | — | immutable subjects. **Narrowly:** *content* has no coherence problem; *authority to hold plaintext* does, and that is the key lease and nothing more |

**What the rule does not buy, so that it is not over-claimed.** It does not make redaction free for a *running* job — the key lease is a real new mechanism and in-RAM plaintext is a real residual. It does not close the scratch hole; only `derive`-before-compute does, and that is a sequencing rule, which is why it is affordable. It does not remove `span(...)`: sub-file access is forced by physics — CRAM ranges, gigapixel tiles — not by interactivity, and deleting it would repeat an error Entail already corrected. It does not remove the cost model, only the requirement that it be fast, precise or continuously re-evaluated; the eviction ranker was the sole consumer of those properties. And it makes `intend` strictly *more* load-bearing, because `intend` is what makes "a cache miss is a scheduling event" true rather than rhetorical.

**Net interface delta.** Two verbs added (`open_task`, `task_status`), one extended (`release` accepts a `task_id`), one gains parameters (`promote` gains `idem_key` and `dry_run`), five fields added to `Task`, three `blocking_reason` codes added, `env_class` replaced by `ExecutionEnvironment`, and four fields deleted. Against that: the four designs between them proposed roughly eight nouns, thirty verbs, four replication subsystems, four pricing functions and one per-locus scanning subsystem.

---

### 14.12 Disposition of every FATAL and SERIOUS finding

`R` resolved · `A` accepted as a stated cost · `U` unsolved (§14.14). Findings raised against more than one design are listed once.

#### Identity, correctness and loss

| Sev | Finding | Disposition |
|---|---|---|
| F | A recipe-chain id over opaque or nondeterministic steps collides, so dedup silently cross-wires two agents' bytes under one name, one actor chain and the wrong institution's pledge | R — `run_id` for any non-`VERIFIED`-`BITWISE` derivation; coalescing refuses to join them §14.9 |
| F | `recipe_coverage` / recreatability is a stored enum that a key shred *(2026-09-19: was `K_rdom`)* does not re-trigger, so the fabric licenses destruction on a claim that became false | R — read-through verdict computed from `entail()` at the moment of the act, never a stored field §14.1 |
| F | The recreatability gate checks recorded-ness and ignores determinism class, input survival, image survival, authority and custody | R — all five enter the predicate; `INPUT_SWEPT`, `AUTHORITY_EXPIRED`, `ENV_RETIRED` added §14.2 |
| F | The fabric receives a chain *head*, not the chain; the design's own scale arithmetic proves the bodies never leave the locus | R — the DAG is in the index journal, already replicated; no bespoke recipe replication §14.6 |
| F | No per-step durability fence and no per-step snapshot, so a node killed mid-step leaves a half-mutated extent and `rewind` is unimplementable | R — deleted with the step chain; a Derivation is atomic, its sink is admitted or it is not |
| F | Replay verification cannot distinguish a consent withdrawal from a nondeterministic transform, and responds by demoting the transform fleet-wide and irreversibly | R — compare `rdom_closure` and `shred_epoch` at both build times before attributing §14.9 |
| F | Promotion releases the live copy's protection on a commit asserting `staged_durable` only, while `archival_durable` may be ~180 days away and P7's presence check can be wrong for a year | R — there is no demotion event; nothing promotion invalidates was protecting it §14.5 |
| F | Lease/TTL expiry destroys exactly the class the eviction invariant forbids destroying; the protection is stated in one section and violated by a timer in another | R — `DRAINING` flushes and merges, never discards; the invariant is enforced at the transition §14.2 |
| F | The nursery/workspace MIX key darkens the agent's own scripts and notes; at cohort scale, ~98 % of three-day sessions | R — disjoint write paths; scratch carries the Task's own `rdom`, not its inputs' closure §14.3 |
| S | Chain collapse reuses bytes across nondeterministic prefixes, so a 200-branch sweep can be one execution reused 200 times, undetectably | R — collapse only across `VERIFIED`-`BITWISE`; seeded `STATISTICAL` by explicit seed §14.9 |
| S | `EXACT` rebuilds have no mandatory digest check although the field exists, so a false determinism claim surfaces as silently different bytes under a citation | R — `out_digest` compared on every rebuild; `EQUIVALENT` needs a registered acceptance test §14.9 |
| S | The 3-replica loss bound assumes independent failure while a rolling upgrade across ~50 institutions is the steady state and `apply()` fails closed by design | R — placement is by the lineage's survivability policy across distinct domains; A — software-version diversity is recorded as unenforced §14.14 |

#### Durability and the scratch hole

| Sev | Finding | Disposition |
|---|---|---|
| F | `seal` / `capture` is either a false durability label (no bytes move anywhere durable) or an unpriced firehose into permanent capacity; the design does not say which | R — both verbs deleted; durability is the write path, permanence is `promote` §14.3, §14.5 |
| F | `seal` mints an indefinite cite-class extract per experiment: 1.2×10⁷ pins/yr, 4.3 GB of heap, 12× the documented ceiling | R — auto-promotion narrowed to **run** class; cite requires a second Purpose's citation §14.5 |
| F | The unprotected state is the cheapest state: the recorded path costs a sandbox and a registration, the opaque path costs nothing | R — the protected path costs *nothing the agent can perceive* (the locus flushes); the unprotected path does not exist, and a `NONDETERMINISTIC` declaration is priced at ingest §14.6 |
| F | An un-evictable class with no per-locus ceiling wedges a locus permanently while every Purpose is inside its cap | R — `scratch_quota` checked at `open_task` and at every `realise`; over-quota fails the job, not the locus §14.7 |
| S | RPO is asserted from a *local* fsync, which the modelled hazard destroys, and the agent is never told its durable frontier | R — durability is `staged_durable` at *n* distinct domains, not a local force; every ack carries `durable_through_seq` §14.6 |
| S | `replication_free_quota` exempts precisely the smallest and highest-value un-recreatable data | R — no quota and no exemption; everything un-entailed flushes §14.6 |
| S | The bespoke mirror has no scrub, no repair and no attestation — the byte-side defect reintroduced on the metadata side | R — no mirror; scratch lineages get 5 %/site/quarter proof-of-possession §14.6 |
| S | The spill valve is aimed at the never-sealed catalog tier, the one tier that cannot absorb it and that GC mark, extract resolution and activation planning all read | R — scratch is its own lineage with its own retention window and its own admission quota §14.6 |

#### Economics and incentives

| Sev | Finding | Disposition |
|---|---|---|
| F | Promotion is strictly dominated: the most expensive verb, buying nothing `derive` does not already give, and degrading the payer's position | R — durability decoupled from permanence; cite class is demand-driven and charged to the citing Purpose §14.5 |
| F | The eviction score is not computable at the moment the decision must be made, and its stale fallback is biased toward evicting the most expensive item | R — no score; the cost enters once, at admission, as a default lease from measured actuals §14.7 |
| F | First-payer recovery cannot reach its own cap, so waiting strictly dominates paying and cold data is never recalled | R — settlement deleted; one recall charged once; `intend` makes waiting cost a scheduling position §14.8 |
| F | `coalesces_with` publishes when the expensive term becomes free, making defection reliable | R — field deleted from the agent-visible Prospectus §14.8 |
| F | A free O(1) CoW fork expands an un-evictable class without bound | R — branching is `derive`; `caps.structural.declared_derivations` bounds the DAG §14.4 |
| S | `reuse_hint` is free to give, socialised across attachers, and unfalsifiable; the reputation penalty has a finite horizon so every Purpose defects in its last period | R — deleted; demand comes from the Intent book §14.7 |
| S | `register_transform` is an unpriced byte-ingress path aimed at the never-sealed tier, and free sealing extends every image's retention | R — billed as `stage` is billed, deduped on `image_cid` at admission, per-Purpose live-image cap; `shell_cid` scripts stay free §14.13 |
| S | Verification sampling is gameable at `transform_id` granularity — 20 trivial builds buy a 95 % discount on the claim that licenses destruction | R — the probe runs once per `transform_id` at two distinct `env_cid`, is funded from the plant reserve, and resets on the fabric's own observation of drift §14.9 |
| S | The FAIL negative cache is a free fleet-wide externality with no expiry, self-reinforcing under load, and a one-journal-entry denial of service; its stderr tail crosses Purpose boundaries | R — typed by `cause_class`; only deterministic refusals cache, after corroboration at ≥2 loci; plant/resource entries expire at their plant epoch; no stderr crosses a Purpose §14.4 |
| S | Promotion's price is undiscoverable before the irreversible work is paid for, so discovery is a retry storm against the commit path | R — `promote(dry_run)` phase 0, before any repack or digest §14.5 |
| S | The notice window is a cheap perpetual veto; extending costs 1/N and protects 100 % | R — deleted with the notice §14.7 |
| S | Dividing the rank by `bytes_held` teaches agents that private copies outlive shared ones, defeating `attach` | R — deleted with the rank §14.7 |
| S | No hysteresis at the cartridge group: two agents thrash one drive indefinitely and each externalises the cost | R — the default lease is the p90 Intent inter-arrival for the target, so a re-demanded target is held; `intend` coalesces the rest §14.7 |
| S | An open Intent confers free unevictability while `pin` costs a premium | R — an Intent sets the *default lease*, it does not confer immunity; `pin_bytes` still caps indefinite holds §14.7 |
| S | Coverage is use-it-or-lose-it inside a Purpose window, so broad-draw-then-fork is dominant and caps become tolerances rather than forecasts | A — stated; the union still bounds the total, which is its job. A leaves-per-epoch rate limb is recorded as an open option §14.14 |
| M | One scalar weight vector over five non-fungible resources is an arbitrage surface and a governance question with no process | R — no numeraire is published; ordering is by coarse bands §14.7 |

#### Agent reality at 10⁵

| Sev | Finding | Disposition |
|---|---|---|
| F | The creating verbs carry no `idem_key`, so the commonest agent failure mode mints duplicates in the one class the fabric has forsworn reclaiming | R — `open_task` and `promote` both take one §14.4, §14.5 |
| F | Reclamation is keyed to a Task expiry that nothing bounds; under the intended delegation pattern the same rule destroys live work | R — the lease clock is suspended by in-flight work, renewable across the `parent_task` subtree, and bounded by `Purpose.window.not_after` §14.2 |
| F | Abandoned live objects accumulate monotonically with no reclamation edge, and the escalation target (a Purpose) has no runtime and no inbox | R — `Task.policy` is the pre-registered answer; `DRAINING` merges into a lineage the GC already collects §14.2 |
| F | Eviction is structurally disarmed: refcount-blocks-eviction and silence-accepts cannot both hold, and at the stated xorb overlap the reachable set is nearly empty | R — no eviction; `refcount > 0` blocks freeing and that is the whole rule §14.7 |
| S | Doing nothing dominates releasing, and no verb enumerates a Purpose's live objects | R — `task_status`; `release(task_id)` returns the lease early; billing continues until it does §14.2 |
| S | The recipe closure crosses workspace boundaries while retention does not, so a sealed, citable recipe silently becomes unreconstructible | R — no workspaces; a Derivation's closure is named and rooted per lineage, exactly as `Cut` already does §14.13 |
| S | No cheap way for an agent to learn what state its data is in; polling `entail` exceeds the measured index ceiling threefold | R — the verdict is published on every response, never polled §14.1 |
| S | The refusal teaches the anti-pattern: "note it first" trains agents to serialise opaque blobs | R — there is no refusal to teach anything; the write path records §14.3 |
| S | Two contradictory flush disciplines, and per-write fsync implies 10⁵ fsync/s at a locus | R — **measured at 0.737 ms per force** on Linux node-local storage, per-call not per-byte (`eval/results/fsync_cost.json`, 2026-09-19), so 10⁵ fsync/s is **74 seconds of barrier per second of wall clock** — the refutation is now arithmetic rather than intuition. The locus group-commits one branch commit per cadence per Task, acked after the force §14.6 |
| M | Fork breadth is unbounded and the reused cap bounds the wrong quantity | R — `caps.structural.declared_derivations`, which bounds the DAG rather than the token chain §14.4 |

---

### 14.13 Collisions with the archive specification, resolved

`STORAGE-DIRECTION` is inherited, not amended, except where a row below says otherwise. The four designs collectively contradicted it in twenty-seven places; each is settled here.

#### GC epochs and leases

| # | Collision | Resolution |
|---|---|---|
| 1.1 | The GC root set is closed **by enumeration**, and every proposed live-state noun sits outside it. Adding one makes a free ~180 B call an indefinite capacity-denial primitive on a tier where reclaim is structurally weeks; leaving it out lets the mark sweep a live recipe's inputs | **No new root class is added.** A Task's authored bytes are rooted by *"every branch head with an unexpired lease"*, which already exists — the Task holds one branch on its institution's scratch lineage. A Task's *inputs* are rooted by *"every extract referenced by an `ActivationRec` in PLANNING/QUEUED/THAWING/PARTIAL/READY"*, which already exists, with `activation.open` raising `pinned_until` to `deadline` plus one epoch, which already exists. A Task holding no live activation roots nothing — correctly, and 1.2 is how it finds out |
| 1.2 | `blocking_reason` has no code for *swept*, although the archive guarantees the sweep | **`INPUT_SWEPT` added** to the enum, alongside `AUTHORITY_EXPIRED` and `ENV_RETIRED`. `entail()` decays against the input closure's *current* rootship, not its rootship at declaration |
| 1.3 | `Transform.retention = union of retentions of the Derivations citing it`, and the derivative population is by construction unpinned, so the union is empty and the image is collected by the same pass — making `TRANSFORM_IMAGE_LOST` the *default* outcome for any recipe never promoted | **Retention is the max of that union, the lease of any live Task whose `derivation_graph` names the transform, and a published floor.** Images dedupe fleet-wide on `transform_id`, so 10⁵ Tasks citing one image root exactly one object. Separately, `register_transform` is billed as `stage` is billed — bytes to `stage_byte_days` plus pledge at the holding institution — deduped on `image_cid` at admission, with a per-Purpose live-image cap. A content-addressed script under a shared base image stays free, so the cheap recorded path remains the cheapest thing in the system |
| 1.4 | *"Leases are monotone. A staged xorb's `avail_until` is **raised** by an activation opening or extending and by nothing else."* Every proposed eviction policy needs to lower one, and every release credit is payment for an act with no archive-side effect | **No lowering verb is required**, because the fabric never evicts (§14.7). `release` decrements `refcount`; `avail_until` is untouched; expiry reclaims. The release *credit* is deleted with the rest of the settlement (§14.8) |
| 1.5 | *"An in-flight activation the branch owner holds **suspends** the lease clock, so an agent waiting forty minutes on a tape mount does not return to find its branch aged out."* No design carried the rule to the object that replaced the branch, while the fabric's own BATCH lane schedules eight days out | **Inherited verbatim and extended:** the Task's lease clock is suspended while *any* owned Job or Intent is non-terminal, and `open_task` refuses a lease that cannot cover the p90 projected window of its outstanding Intents |
| 1.6 | *"`apply()` is pure: it reads only `e.ts` and the payload… (A time predicate inside `apply()` forks primary from replica silently on replay, and evaluated per institution it means the 50 nodes do not compute the same GC root set.)"* Every proposed lifecycle transition is a time predicate | **No new time-predicate transition exists.** Lease expiry is evaluated the archive's way — against index time returned with every renewal — and only the sweep acts on it, from inside an epoch fenced on `mark_start_seq`. `recreation_class` is computed in the RPC handler, never in `apply()`. `LOST` is not a state (§14.2) |
| 1.7 | GC epochs are per lineage; a workspace spanning five lineages has no epoch that can root it, and Unresolved 6 says a cross-lineage cut is not worked through | **The Task's own bytes live on exactly one lineage** (its institution's scratch lineage), so they have one epoch. Its inputs are cross-lineage and are rooted per lineage member, which is precisely what `Cut`'s two-phase reservation already does. No cross-lineage live object is invented |

#### Extract pins

| # | Collision | Resolution |
|---|---|---|
| 2.1 | *"An extract whose bytes were actually delivered to a completed job is auto-promoted to cite class"* — heap-resident, `pinned_until = 0`, COMPLIANCE Object Lock, against a first-class *citable-extracts-per-lineage-per-year* capacity input. At agent rate this makes cite-pin count unbounded in agent count | **Amended: auto-promotion is to `run` class.** Cite class requires a citation by a Purpose other than the author, or an explicit request paying in full §14.5 |
| 2.2 | A commit asserts `staged_durable` only; `archival_durable` is required before a cite pin and may be **~300 days** away at ~1 TB/day against a **30 TB LTO-10** cartridge *(corrected 2026-09-19)*. Every design released live protection on the commit | **No protection is released on commit** (§14.5 phase 5). The scratch tier is `staged_durable`-only *by design and says so*; cite pins inherit the `archival_durable` gate unchanged |
| 2.3 | The 4× amplification refusal is mandatory at mint and is the *routine* outcome for a content-chosen agent selection; no design had a state for it | **Phase 0 `dry_run` runs the arithmetic before anything irreversible**, and returns `REFUSED{binding_constraint, arithmetic, rewrites: [repack, declare the split at ingest]}` §14.5 |
| 2.4 | Seal was priced at a coordinator round; pins go to the **approver** quorum, and *"each custodian independently re-materialises the selection from the named `v` and recomputes `root_pub` before signing"* | Moot — `seal` is deleted. `promote(class: cite)` is priced at the approver quorum plus custodian re-materialisation, explicitly, in phase 4 |
| 2.5 | A run-class citable name is TTL'd in the LSM and stops rooting its inputs at expiry; only an `ActivationRec` raises `pinned_until` | **Stated in the contract:** a run-class citation is a lease, not a durable name. `resolve_citation` on an expired one returns `EXPIRED` with the `promote` price attached, rather than a dangling verification |
| 2.6 | `freeze` carries `idem_key` because *"agent retries silently double both the pinned capacity and the Object Lock obligation"*; no design gave `promote` one | **`promote` takes `idem_key`**, resolved to the same `vid` on retry, on the one path that consumes monotonic capacity §14.5 |
| 2.7 | *"A pin guarantees existence, never residency… or someone will read 'immutable and pinned' as 'instant'."* | Adopted as the headline of this section: `ARCHIVED` means *re-`realise` costs a recall of 0.5–926 drive-hours* *(basis unstated — §14.7 note, 2026-09-19)*, and that is a scheduling event. It is the owner's rule restated from the archive's side |

#### Redaction

| # | Collision | Resolution |
|---|---|---|
| 3.1 | ~~`rdom_rule` defaults to `"lineage"`; every blast-radius claim assumes `"subject"`; retrofitting is a re-encode~~ | ~~**Refused at ingest** for any lineage admitting an IRB or DUA Purpose~~ — **RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`): per-object keys are unconditional, so every lineage has per-subject blast radius by construction and there is nothing to gate. **Unresolved 3.2 below still stands.** |
| 3.2 | The key table is keyed `(lineage, object_id)` *(2026-09-19: was `(lineage, rdom)`; `K_rdom` retired, rename only)*; live agent state has no lineage, so there is no row to wrap under, no `K_L` to wrap with, and no row to destroy | **Task scratch is committed to a lineage**, so it has a row like everything else. This is the single strongest argument for ingesting the residue rather than mirroring it §14.6. **3.2 stands, and is strengthened by per-object keys** — scratch objects now carry their own destroyable keys rather than sharing the Task's domain key |
| 3.3 | `MIX` at cohort scale is a one-withdrawal kill switch; neither document states its half-life | **Stated with the arithmetic** (≈0.51 days at 50,000 subjects and 1 %/yr), published as `expected_underivable_by`, with `CERTIFIED_DEIDENT` or promotion as the offered rewrites §14.10 |
| 3.4 | P5: key material and plaintext never enter the journal, `dumpState`, `stateHash` or any WORM snapshot. Three designs inlined agent notes into a replicated journal | **Nothing in this section writes agent bytes to the journal.** Scratch goes through `stage`: chunked, `sid = HMAC(K_mac, chunk)`, encrypted per chunk under its domain key. The journal carries `xorb.place` and a branch commit |
| 3.5 | *"`redactions` is **not** a mutable list on `ExtractRec`… a mutable field on an asynchronously replicated record makes an 'immutable' identifier mean different things on primary and replica."* One design made loss class exactly that | **`recreation_class` is a read-through derived view** returned with `index_seq` and a staleness bound, never a stored field §14.1 |
| 3.6 | *"Seal first, destroy later: the shred is applied and converged at the index before any optional fragment destruction."* The live tier had no counterpart | **Inherited unchanged.** With ciphertext at rest the shred *is* the live-tier seal; key leases cannot renew past a converged `shred_epoch`, and a locus that cannot confirm convergence stops issuing §14.10 |

#### Quorum, the merge service, the index

| # | Collision | Resolution |
|---|---|---|
| 4.1 | The commit quorum does not exist; the honest interim is single-writer under a fenced lease and *"the signature set must not be advertised as externally verifiable, because it can certify a commit that never happened"* | **The scratch durability path deliberately does not depend on it.** A Task flush is a branch commit under a leased single writer — the mechanism that works today. Only `promote` takes the quorum, and it inherits §13's Defer including the withheld word |
| 4.2 | Voter predicate 5 (*"the added bytes fit the reciprocity entitlement"*) is checked **at** commit; one design paid after it, on media that cannot take a return | **Admit and draw at phase 1, before the encode**; commit is phase 3; the irreversible act is last §14.5 |
| 4.3 | *"Zero bytes move"* contradicts the commit procedure — chunk, `sid`, pack, AEAD, RS(k,m), place *n* fragments — and cross-lineage promotion additionally re-chunks under a new `K_mac` and dedupes against nothing | **Withdrawn and re-costed:** one encode-and-place pass, no recall, priced in `core_bytes` and `stage_byte_days`, ~86 s of SHA-256 and ~8 min of push for 200 GB. Cross-lineage promotion is refused-with-arithmetic §14.5 |
| 5.1 | Entail's scale argument is that the derivative firehose does not commit; every lifecycle design routed 10⁵ agents' durability through the single-writer merge service that Unresolved 7 calls a chokepoint every number depends on | **Branch commits under a per-Task leased writer**, 2.2/s per scratch lineage at the flush cadence, merged once at close over a `task_id`-partitioned `rel` space. The firehose stays off the quorum §14.6 |
| 5.2 | Partial activation mints a quorum-pinned derived extract, so aggressive eviction under readers becomes quorum load | Dissolved: the fabric never truncates a live reader for scheduling reasons. The only truncations are media loss and redaction, which are rare and consequential and deserve the round §14.2 |
| 5.3 | A same-`rel` conflict is **refused**, not merged, and the losing branch is left intact | Scratch merges cannot conflict (`rel` partitioned by `task_id`). On the `promote` path, `Conflict{head, conflicting[]}` is an ordinary returned outcome with a rewrite §14.5 |
| 6.1 | Journal volume: 1 PB of ingest is 1.6×10⁷ entries; `log_retain` is still an entry count, and *"the journal is never truncated on the primary today"* | **Stated as a prerequisite, not an improvement.** The flush path adds ~10⁷ entries/day at the measured cadence, comparable to a petabyte of ingest per day §14.6, §14.14 |
| 6.2 | *"Nothing agent-facing may be O(files) in the index"*, and P3 records `dumpState`'s 2³¹−1 `GSON.toJson` ceiling *"that these records reach"*. The proposed live nouns inlined unbounded arrays, one record per concurrent agent | **No unbounded array enters the index.** `Task` carries a branch reference, a quota, two counters and a fixed-size policy — hundreds of bytes, O(live Tasks), not O(objects) |
| 6.3 | *"An object's id is a keyed hash of its own canonical bytes, never derived from a property of the thing it describes"* — the rule whose violation produced the cleanest same-id-different-bytes path in the whole exercise. `derivation_id` deliberately inverts it, which is sound for `BITWISE` and unsound otherwise | **`run_id` restores the rule** for every derivation that is not `VERIFIED`-`BITWISE` or seeded-`STATISTICAL`, and coalescing refuses to join them §14.9 |

---

### 14.14 Build order, and what is unsolved

#### Build, in this order

Everything in §13's *Build first* remains a prerequisite and none of it is lifecycle work. **Scale limit 9's checkpoint-and-truncate path and a byte-denominated `log_retain` move from "should" to "must", because §14.6 adds ~10⁷ journal entries a day.**

1. **`Task` as the live-state object.** The five new fields, `open_task` with `idem_key`, `task_status`, `release(task_id)`, the per-institution scratch lineage, the `task_id`-partitioned `rel` space, and the lease-suspension rule inherited from the branch. This is the durability story and nothing else closes the hole.
2. **The locus flush.** Group-committed, on cadence, one branch commit per Task, `durable_through_seq` on every ack. Small, and it is what makes the protection require nothing of the agent.
3. **The two disjoint write paths.** `Transform.output_manifest[]`; no scratch mount for a sandbox with a governed read set; everything else EPHEMERAL by construction. Cheap, and it is the entire enforcement point — without it §14.1's axis is a label again.
4. **The read-through verdict.** `recreation_class` plus `blocking_reason` on every response that names a live object, with `index_seq` and a staleness bound; the three new codes; `entail()` evaluated against the input closure's current rootship. Cheap, and everything else is downstream of this number being honest.
5. **Ciphertext at rest on the stage, and the chunk-key lease.** The one genuinely new mechanism, and the one that deletes the most: the entire plaintext-inventory-and-purge subsystem never gets built. Its cost is measured (3411 MB/s decrypt, 5.9× the fragment push) and its correctness rests on failing closed, which the index tier already does.
6. **The determinism probe and `ExecutionEnvironment`.** One extra execution per `transform_id`, funded from the plant reserve. Without it, `BITWISE` is an agent-supplied string describing a property the agent cannot observe from inside its own code, and it is the string that licenses the fabric to let a lease lapse.
7. **Default-lease bands and admission refusal under stage pressure.** Four bands and a refusal; no ranker, no price, no numeraire.
8. **Typed FAIL, `run_id`, the `params` split, `promote(dry_run, idem_key)`.** Each is a field or a parameter.

#### Measure these, and measure them before believing any of the above

1. **`u` — the un-entailed bytes a real agent session authors.** The whole design is affordable at `u ≲ 200 MB` (2.8 % of the federation byte budget), binding at `u ≈ 2.1 GB` (100 %), and arithmetically impossible at `u ≳ 10 GB`. Every design in this line rested on a constructed estimate; none measured it. It is measurable today on the KOS pipeline by instrumenting what a real session writes outside its declared outputs.
2. **The abandonment rate and its shape** — what fraction of Tasks ever receive a terminal verb, and the distribution of time between last verb and never-coming-back. The state table's neglect column is sized against a guess.
3. **The agent operation rate.** The four designs spread 790× on steps per agent per unit time (1/s, 200/day, 26,000/72 h). Every journal, flush and pricing number is downstream of it.
4. **The determinism-violation rate for transforms declared `BITWISE`.** It sets the probe's value and the honest width of `EXACT`.
5. **The cheapest and most decisive: does a refusal change an agent's next action, or produce a retry?** Entail bets its entire planning interface on the first — §5.1 says the rewrite "gets more valuable as agents get better at reading explanations" — and nobody has checked. It is runnable on the fabric as it stands today, with receipts and the capability inventory.
6. ~~**Checkpoint-to-checkpoint chunk sharing on real model weights.**~~ **ANSWERED 2026-09-19** (`eval/results/ckpt_dedup_results.json`): **zero**, on every comparison including a discriminating cross-run control. `K_rdom` is **retired, not demoted**. **And a second finding the question did not ask for:** checkpoints can be neither deduplicated *nor recomputed* — a `NONDETERMINISTIC` derivation may never be silently rebuilt (§3.4), and unpinned floating-point reduction order makes most GPU training nondeterministic (§14) — so they are irreducible on both axes and **retention is the only lever**. That makes Entail's entailment-first thesis the *only* answer to 10–100× derivative growth rather than one of two, and makes checkpoint retention policy a first-class capacity input. **Nothing in this document set currently specifies a checkpoint retention policy — that gap replaces this question in the list.**

#### Unsolved

1. **`u` is unmeasured and the design is sensitive to it across two orders of magnitude.** This is the single largest open risk and it is not a detail: at the pessimistic end the answer is not "expensive", it is "impossible", and the flush cadence would have to lengthen until the exposure window is no longer a durability story.
2. **A long step is one step.** A six-hour training run whose locus dies at hour five loses five hours, and the flush cadence cannot help because the output does not exist yet. `resources.checkpoint_interval_s` mitigates only if the transform author emits checkpoints, and nothing forces that.
3. **Plaintext already in a running sandbox's RAM and GPU memory.** The key lease bounds what decrypts *next*, not what is already held; a job continues to `walltime_s`. Holding the sink bounds the *egress*, not the memory. Machine unlearning is not solved and §8.6's boundary policy is the substitute, not a fix.
4. **The commit quorum still does not exist.** Inherited from §13. This section is built so that agent durability does not depend on it — but `promote` does, and so does every citation.
5. **Survivability policies constrain failure *domains*, not software versions.** P4 makes `apply()` fail closed on an unknown entry type, and across ~50 independently operated institutions a rolling upgrade is the steady state, so a bad `fmt` bump halts every node that took it. Three fragments in three geographic domains can be one deploy. Version diversity as a placement constraint is not designed here, and every durability number above assumes independence it does not enforce.
6. **`staged_durable` is an assertion the fabric may be wrong about for up to a year.** P7's presence check counts a fragment present whenever its node is UP, and `scrub()` iterates the store's own rebuilt inventory. Raising scratch proof-of-possession to 5 %/site/quarter narrows the window for the one class that cannot be rebuilt; it does not close it, and the general fix is P7's.
7. **Cross-site byte sharing is priced, not solved.** Under a DUA, `materialisation_policy` and jurisdiction tags forbid the warm copy in what will be the common case, and both Purposes then pay a full *k*-of-*n* decode.
8. **Coverage is use-it-or-lose-it inside a Purpose window.** Broad-draw-then-experiment-inside-it is dominant, so caps will be reached rather than approached, and `distinct_rdoms_touched` degrades as a signal. A leaves-per-epoch rate limb alongside the leaves-total cap would fix it and is not designed here.
9. **Whether `derive`-before-compute actually changes agent behaviour.** The axis rests on a sequencing rule that costs 0.3 ms, and §14.3 makes the recording a by-product of the sandbox rather than an agent obligation — which is why this is a much weaker assumption than the four designs made. It is still an assumption about behaviour, and measurement 5 is the cheapest way to start testing it.
10. **The identity root for agents**, inherited unresolved from §11.

**Nothing in this section is implemented.** Neither is anything in the twelve sections above it, and this one sits on top of P1–P7, the IV fix, **per-object keys** *(2026-09-19: was `K_rdom`, retired)*, the LSM tables, Coverage and the Derivation — all of which land first. What this section adds to that queue is two verbs, five fields, one mechanism and one sequencing rule. What it removes from the four lifecycle designs that preceded it is roughly eight nouns, thirty verbs, four replication subsystems, four pricing functions and one per-locus scanning subsystem — and the reason the removal is possible is the owner's own constraint: **once nobody is waiting on cold data, the live tier stops needing an operating system and becomes a projection.**
