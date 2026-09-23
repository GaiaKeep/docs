!!! info "Answer by id"
    Every decision the owner still needs to make, with a priority and, where one exists, a recommendation. Source: `GaiaKeep/gfs` `docs/OPEN-QUESTIONS.md`.

# GFS — Open Questions for the Owner

*Compiled 2026-09-23 from the design record (`SPECIFICATION.md`, `STORAGE-BINDINGS-DECISION.md`,
`STORAGE-DIRECTION.md`, `ENTAIL-AGENT-NATIVE-FS.md`, `FROM-SCRATCH-DECISION.md`) and the decisions
made in conversation through commit `fc5d81b`.*

## How to use this

Answer by ID (e.g. "T3: March", "H7: PA unless WORM is LA-only"). Where I have a recommendation it
is marked **Rec**; accepting it is a valid answer. "Don't know yet" is a useful answer too — it tells
me to build the decision as a parameter rather than a constant.

**Priority**

- **[NOW]** — blocks work I would otherwise start this week.
- **[BEFORE MEDIA]** — must be settled before the first cartridge or disk is written. These are
  one-way doors: the on-media format and identifiers cannot change afterward.
- **[BEFORE PROD]** — must be settled before real data or a second institution is involved.
- **[LATER]** — worth knowing, costs nothing to defer.

**What is already decided** (listed so you can overturn anything here too):
3-way replication across 3 sites now, erasure coding later via repack · Bareos out (AGPL) ·
tape is one binding among several, placement is media-neutral · WORM is per-cohort, not
plant-wide · repack is in scope · GCM counter discipline (`SegmentCipher`) · panAtlas `doc_uid` is
payload-only, never on-media structure · durability barrier is measured and fails closed · Stack
before Cube · permissive licences only.

---

## 1. Purpose and scope

**P1 [NOW] — Who are the first real consumers, by name?** "Agents" covers the KOS training
pipeline, panAtlas coverage/decontam jobs, the Astral agent skills, PRIMED-AI validation
workloads, and future external agents. The first two or three decide which verb gets built first.

**P2 [NOW] — What is the first dataset to go into it for real?** Candidates: the panAtlas index
estate (198 GB, small, well-understood), heartlens-ct3d-native (25.94 TB, 6.9 M files), the KOS
V4/V5 corpora, model checkpoints. **Rec:** panAtlas index first — small, its sizes are measured,
and it exercises identity, versioning and the doc_uid rule without needing a tape.

**P3 [NOW] — Is the DGX copy retained after archiving, or deleted?** This decides whether two
tape sites is survivable (it is if the DGX copy stays) and whether tape is primary or backup.

**P4 — Is this system the primary store for these datasets, or a durable tier behind the DGX
filesystem?** Primary means GFS must serve training-rate reads; tier means it only needs to
materialise into the DGX.

**P5 — Are humans ever consumers?** You've said no. Confirm that means: no browsing UI, no FUSE
mount, no S3 console — or whether a read-only human inspection path (e.g. the dashboard's Storage
tab) is still wanted for operators.

**P6 — Are external institutions writers, readers, or only hosts?** "Distribute around the state"
could mean partner sites hold our ciphertext blindly, or that they also publish their own
datasets into the fabric. The trust and tenancy model differs completely.

**P7 — Is DoD/DoW deployment in scope for this system specifically?** The zero-trust pivot made
fail-closed and FIPS/CNSA mandatory for Cresco. Does GFS inherit every one of those requirements
now, or only when it is fielded there?

**P8 — Is GFS intended to become a product or open-source project others run?** This decides how
much effort goes into packaging, documentation of the on-media format, and licence hygiene.

**P9 — What does "done" look like for phase one?** A single sentence I can test against, e.g. "an
agent can publish a versioned dataset, lose one site, and realise the exact version elsewhere."

---

## 2. Timeline

**T1 [NOW] — Is there a hard date driving this?** Upcoming deadlines in the atlas that could cite
this system: PRIMED-AI Validation Center (2026-10-02), PRIMED-AI Playbook (2026-10-09),
**PRIMED-AI D2M-AIP (2026-10-19 — the atlas already names metadata provenance as its missing
capability)**, NSF AI Datasets and NSF AI Infrastructure Hubs (both 2026-11-04). Should GFS be
demonstrable, or only describable, for any of these?

**T2 [NOW] — When do you expect to place the hardware order?** It sets how long I have to get the
vendor answers (section 3) and whether the mount-cycle measurement can happen on a loaner first.

**T3 — When should the first site be live with real data?**

**T4 — When should all three sites be live?**

**T5 — When do you want erasure coding to replace replication?** Migration costs about three
weeks of background drive time at 3 PB, so it can be scheduled; it does not have to be a project.
Is it tied to a capacity threshold, a cost threshold, or a date?

**T6 — How do you want me to pace the work?** Options: (a) depth-first on one working end-to-end
path, (b) breadth across all layers at design level, (c) whatever unblocks the grants first.
**Rec:** (a) — nothing in the SPI is wired yet, and the bugs found this week were all in pieces
that looked finished and had never run end to end.

**T7 — Who else will work on this, and when?** Students, staff, the concurrent editor on the
felix-hygiene tree, partner-institution engineers? This decides how much I write down versus build.

**T8 — Is there budget approved, and what is the ceiling?** A number, or "unknown," is enough to
size the first order.

---

## 3. Hardware and procurement

**H1 [NOW] — Stack or Cube for the first purchase?** You said you may start with a Stack.
**Rec:** Stack, used as the instrument that measures the mount cycle, rewind, load/thread
distribution and shoe-shine floor that every capacity figure depends on.

**H2 [NOW] — Can you get Stack specifications?** I need slots per module, drive bays per module,
maximum modules, and **whether one accessor serves the whole stack**. The accessor turned out to be
the Cube's real throughput ceiling (~14 drives/site), and I have no figure for the Stack.

**H3 — How many sites for phase one: 2 or 3?** **Rec:** 3. Two cannot form a quorum for index
commits. Two is survivable only if the DGX copy is retained (P3) and a witness is added (R4).

**H4 — Which physical locations?** UK campus buildings, partner institutions, colocation? Each
must be a genuinely independent failure domain (power, network, building).

**H5 — LTO-10 media: LA (30 TB) or PA (up to 40 TB)?** **Rec:** PA, unless PA is not available as
WORM for the cohorts that need it (see D3), or the premium exceeds 33 % and you stay under 132 PB.

**H6 — Get from Spectra: guaranteed native decimal capacity of the PA part number**, not "up to."
At 36 TB instead of 40 the four-frame ceiling drops from 175 PB to 158 PB.

**H7 — Is LTO-10 half-height offered?** Their 32.4 TB/hr figure implies 30 HH drives at 300 MB/s;
the user guide lists LTO-10 as full-height SAS only. Worth 1.41× aggregate if real.

**H8 — Drives per site for phase one?** **Rec:** 2–3. Ingest at a few PB/yr is under half a drive;
the rest is recall concurrency, repair surge and a hot spare.

**H9 — Is Capacity-on-Demand a licence key on installed chambers, or a field hardware install?** If
it is a key, buy small and license up. If it is hardware, the buy-small plan inverts.

**H10 — Can drives be added after purchase?**

**H11 — Can Spectra quote a minimal satellite unit (1–2 drives, 40–80 slots) as a rebuild target
or fourth failure domain?**

**H12 — The per-site host.** I've sized it at a modest 1U: 8–16 cores, 64–128 GB, an HBA and
2–4 TB NVMe spool. Do you have a standard server build, or should I spec one? Who buys it?

**H13 — SAS direct, Fibre Channel, or Spectra Swarm 40 GbE between host and drives?**

**H14 — Do you want spinning disk (JBOD) or NVMe capacity at each site in phase one, alongside
tape?** You said placement on JBOD is the same problem. If disk is present, a site can serve
warm reads without a mount, and the "one offline copy of something that lives on disk" policy
becomes expressible immediately.

**H15 — Will you ask Spectra for the load/unload cycle rating in writing?** Every media-life figure
divides by an assumed 20,000 cycles with no vendor citation.

**H16 — Will you ask about LTO-10 WORM availability and price premium for both LA and PA?**

**H17 — Does the Stack/Cube support SCSI Persistent Reservation?** Needed if more than one host
ever talks to one library.

**H18 — Do you want me to write the full vendor question list as a document you can send to
Spectra?** (21 questions exist in draft from the sizing workflow.)

---

## 4. Architecture — the one placement engine

**A1 [NOW] — Adopt `LocusProfile` with a `Basis` on every value?** Each property would record how
it was obtained: MEASURED, ATTESTED, MODELLED, DEFAULT, or UNMEASURED. This is "it does not matter"
written into the code, and it will surface more unmeasured properties like the four fixed this
week. **Rec:** yes.

**A2 [NOW] — Make `bindingKind`, `mediaClass` and `node_class` illegal as placement inputs** (kept
as telemetry only)? **Rec:** yes; it is the only enforcement of "tape is just a block of data."

**A3 — Replace latency buckets (MS/SECONDS/MINUTES/HOURS) with the measured number?** The MS bucket
currently spans RAM (~100 ns), NVMe (~100 µs) and spinning disk (~10 ms), five orders of magnitude.
**Rec:** callers get the measured distribution plus comparison helpers; buckets become display only.

**A4 — Can a volatile locus (RAM) hold a copy that counts toward the replication factor?**
**Rec:** no. It may hold cache copies only, and the index must show them as a distinct residency
state so `realise` knows the nearby copy may vanish.

**A5 — New locus properties to add — confirm each:** per-access setup cost (mount, seek, none),
removability / air-gap capability, volatility on power loss, reclaim granularity, reclaim latency,
and wear measured in the medium's own unit (load cycles, drive writes per day, power-on hours).

**A6 — Is there a common currency across conserved resources, or does placement satisfy each as a
separate constraint?** **Rec:** separate constraints. A common currency is how a drive-hour budget
missed that cartridges were wearing out first.

**A7 — Placement policy form: hard constraints plus scoring, or scoring only?** **Rec:**
constraints plus scoring, with a small fixed set of predicates rather than a general query language.

**A8 — When a policy is unsatisfiable, what happens?** Options: refuse the write; write to what is
available and mark the object under-protected; queue until capacity appears. **Rec:** refuse by
default, with an explicit caller opt-in to write under-protected and a visible debt the repair
loop pays down.

**A9 — `capabilityEpoch`: when a locus's measured properties change underneath open placements,
what happens to in-flight writes?** (Recorded open as A-11.)

**A10 — Re-probe cadence.** A shared filesystem's rate at 3 a.m. is not its rate at noon. Probe
only at start, on a timer, or when observed rates drift?

**A11 — Stripe latency-class homogeneity: retire it now under replication, or keep it for when
erasure coding returns?** **Rec:** retire for replicated copies, keep as the rule for coded stripes.

**A12 — The wire-up order.** Nothing calls the `ExtentBinding` SPI yet; the live path is
`NodeAgent.putFragment → store.put`. Route the live path through the SPI now (before a second
binding exists), or after? **Rec:** now — there is no migration cost yet.

**A13 — Split the placement score into durability and access cost?** Recorded as A-3; it changes
placement for every registered node.

**A14 — Keep `ExtentBinding`'s deliberate omissions** (no synchronous byte-returning read, no
`delete`, no `list`)? **Rec:** yes.

---

## 5. Redundancy and distribution

**R1 — Replication factor: 3?** **Rec:** 3, equal to site count, so every site holds a complete
copy and can serve any object disconnected.

**R2 — Must every site hold every object (N = R), or may sites hold subsets?** N = R keeps sites
independently readable; more sites than copies makes each site smaller but not complete.

**R3 — Does "blind holding site" still matter under replication?** Each site now holds a complete
encrypted copy rather than a fragment. Encryption still protects it, but a stolen site yields
all the ciphertext rather than a third. Acceptable?

**R4 — If two sites: where does the quorum witness run?** A small VM at a third location.

**R5 — Where can a lost site be rebuilt?** Under replication any copy target works: a new site,
rented rack, disk, or cloud. Is cloud acceptable as a temporary rebuild target for clinical data?

**R6 — Intra-volume RS(28,4) against media defects: keep it under replication?** **Rec:** keep;
it guards cartridge defects, which replication alone repairs only with a cross-site copy.

**R7 — Which erasure code when it comes back?** RS(2,1) at 3 sites, RS(3,1) at 4, or something
else. Not needed now; confirm it can wait.

**R8 — Do all datasets get the same protection, or is replication factor a per-dataset policy?**
Derived artifacts (labels, embeddings, kNN) can be recomputed and may need fewer copies.

**R9 — Maximum acceptable repair window after a site loss** (hours, days, weeks)?

---

## 6. Data model and versioning

**V1 — Confirm the model:** reads are always of a named version; writes are quorum-confirmed;
an *extract* is a first-class, citable, pinnable point-in-time object.

**V2 — What is a "dataset" for versioning purposes?** One panAtlas registry entry? One directory
tree? Something an agent declares?

**V3 — Branches: do agents need them, or is linear versioning enough for phase one?**

**V4 — Who may create a version of a dataset?** The owner only, any agent in the project, or any
agent holding a write token?

**V5 — Version identifiers: opaque ids, or content-derived?** Content-derived ids fall under the
same "no plaintext-derived identifiers on media" rule as `doc_uid`.

**V6 — How long do unpinned old versions live?** Forever, a retention window, or until capacity
pressure?

**V7 — Does a pinned extract (cited in a paper or grant) block deletion of its data forever?** If a
subject then withdraws consent, which wins?

**V8 — Where does `retention_class` come from at write time?** Repack efficiency swings 18× on
whether data that dies together was written together, so the writer must say. Options: the
dataset's registry entry, the caller, a policy on the project, or inferred.

**V9 — Is `pack_hint` (read affinity) supplied by the caller, derived from panAtlas relationships,
or learned from request logs?**

**V10 — Unversioned live caches: you mentioned caches may be "versioned or unversioned." When is
an unversioned cache acceptable, and can it ever be promoted to a version?**

**V11 — Streaming semantics.** "Stream versioned datasets wherever they need to go": is a stream a
single object, a whole version, or a query over a version? With backpressure? Resumable after
interruption?

---

## 7. Deletion, retention and repack

**D1 [BEFORE MEDIA] — Which data must be on drive-enforced WORM?** Candidates: pinned/cited
extracts, regulatory and audit records, research-integrity snapshots. Everything else rewritable.

**D2 [BEFORE MEDIA] — Privacy interleaving versus reclamation grouping.** Interleaving consent
units hides cohorts but means nothing ever dies whole; grouping lets volumes die whole but reveals
the cohort. At 1 %/yr withdrawal, interleaved volumes reach the repack band only after 39–98
years. Which do you prioritise, per data class?

**D3 [BEFORE MEDIA] — Repack granularity: whole fragments only, or sub-fragment?** Sub-fragment
repack renumbers positions and would break pinned citations unless engineered for. **Rec:**
fragment-granular, with retention cohorting as the precondition that makes it yield anything.

**D4 [BEFORE MEDIA] — Adopt the rewrite rule as normative:** a rewrite either preserves the
ordinals and copies ciphertext bit-identically, or mints a fresh epoch key — never one without the
other. Otherwise a botched repack reads as a lawful redaction. **Rec:** yes.

**D5 — What is the promised latency for "forget" on consent withdrawal?** Key destruction takes
~75 s on any medium; physical erasure takes years on tape. Is key destruction legally sufficient
for your DUAs and IRB?

**D6 — Who is authorised to order a deletion or key destruction, and does it need two people?**

**D7 — Physical destruction of WORM cartridges:** at 10 %/yr removal this is a two-person attested
ceremony roughly every 15 days. Who performs it, and is that acceptable operationally?

**D8 — Default GC state: on, as a budgeted and refusable standing obligation?** **Rec:** yes, with
admission per volume on predicted live fraction; refuse above 50 % live.

**D9 — Should drives that can skip dead regions be assumed?** The repack cost model differs 3.77×
depending on it, and the constant is unmeasured. Measure first, or plan on the worst case?

**D10 — Retention floors: who sets them, and can they ever be shortened?** The binding enforces
them as monotone (never shortened).

---

## 8. Security and cryptography

**S1 [BEFORE MEDIA] — Convert `K_meta` and the catalogue cnodes to the same counter discipline as
`SegmentCipher`?** Recorded as the top open crypto item. **Rec:** yes, before any cartridge.

**S2 [BEFORE MEDIA] — Enforce idempotency keys with a lease?** Today two writers under one key
would each think they own the counter space. **Rec:** yes; refuse rather than share.

**S3 — Make direct calls to `CryptoBox.gcmEncryptWithIv` for object data a lint failure?**
**Rec:** yes.

**S4 [BEFORE PROD] — Key custody: software keys, an HSM, or both?** The design assumes shredding is
a hardware key destruction. Which HSM, and one per site?

**S5 — Shamir t-of-n custody across sites: keep it, and what are t and n?**

**S6 — Drive-level hardware encryption (BlueScale): decline?** **Rec:** decline. We already write
ciphertext; a second layer adds a key-custody dependency and buys nothing.

**S7 — FIPS 140-3 validated crypto module required now, or at DoD fielding?**

**S8 — Per-request credentialed tokens for agents:** you mentioned audited per-request tokens.
Scoped to what — dataset, version, verb, byte range, time window? Who issues them?

**S9 — Audit log: where does it live, how long is it kept, and must it be tamper-evident?**

**S10 — Tenant model:** reuse Cresco's shipped tenant namespacing and roles, or does GFS need
finer, attribute-based rules (per dataset, per DUA)?

**S11 — Is metadata confidentiality in scope?** The catalogue currently holds everything except
content keys, including filenames. Must names and sizes be protected from site operators?

---

## 9. panAtlas integration

**X1 [NOW] — Decide `doc_uid` blinding before the imaging element-level overlap job runs.** Today
`doc_uid` covers text that is mostly public literature. The imaging job will put the same unkeyed
content hash on PHI. Keep it unkeyed in payload only, or switch to `HMAC(K_idx, doc_uid)` and
accept breaking the cross-lineage crosswalk at every key rotation?

**X2 — Is the panAtlas index (198 GB: 11.24 GB parquet ledgers + 186.8 GB derived arrays) a dataset
in GFS like any other?** **Rec:** yes; it is self-hosting and realises from cold in ~14 min.

**X3 — Shard the parquet ledgers by redaction domain so withdrawal is a key destruction?** Needs a
count of redaction domains; at 10⁶ domains shards would be ~11 KB each.

**X4 — What is a redaction domain for panAtlas data?** Subject, source, institution, DUA?

**X5 — Is invalidate-and-recompute acceptable as the redaction method for derived artifacts**
(labels, edges, kNN)? Only if recompute is affordable; `knn_exact96` is an exhaustive search over
the corpus and its cost is unmeasured.

**X6 — Should panAtlas URNs (`panatlas:dataset:<slug>`) be the dataset names in GFS?**

**X7 — `manifest_hash` currently hashes (path, size, mtime), not content. Should GFS versions
replace it as the provenance primitive for PRIMED-AI?**

**X8 — The stale atlas figure (`labels_v53` 140 GB vs 186.8 GB measured) has been corrected. Are
there other panAtlas artifacts you want measured and registered before they go into GFS?**

---

## 10. The tape binding

**B1 [NOW] — Confirm Bareos is out.** Decided on licence grounds: AGPL forbids the streaming
integration, forcing every byte through staging. The real cost is losing a catalogue-free reader
written by someone else.

**B2 [NOW] — Java toolchain: move to JDK 22+ for the Foreign Function & Memory API, or use JNA, or
a small separate C helper process?** **Rec:** JDK 22+ if nothing else pins you to 21; it adds no
dependency.

**B3 [BEFORE MEDIA] — The on-media format is now a one-way door with no vendor fallback. Do you
want an independent reference reader** (works with no index, no catalogue, no running system) as
a blocking deliverable? **Rec:** yes.

**B4 [BEFORE MEDIA] — Should the format specification be published openly** so a future reader can
be written by anyone?

**B5 — Block size on tape** (1–2 MiB?), filemark placement, partition use, and index checkpoint
placement. Want to review these, or delegate?

**B6 — Error recovery policy on read/write failure:** retry, skip to local parity, or stop and
repair? **Rec:** retry only on native sense data; otherwise stop and repair from another copy.

**B7 — Multi-host access to one library:** will more than one host ever drive one library? If so,
fencing needs SCSI Persistent Reservation (H17) or a lease.

**B8 — Test rig:** use mhvtl (GPL kernel module, test host only, never shipped) for CI? Needs a
Linux box — which one?

**B9 — Retire the Bareos documents** or keep `BAREOS-RECOMMENDATION.md` as history?

---

## 11. Other bindings

**N1 — NVMe: raw block device / namespace, or a file on a filesystem?** "The data is raw" suggests
raw; the filesystem path is what exists and works today.

**N2 — Spinning disk / JBOD: raw partitions, or files?** Raw gives placement exact locality control.

**N3 — RAM as a locus: a process-local arena, a shared-memory region, or leave RAM to the OS page
cache?**

**N4 — Does `FsBinding` stay as a supported binding** (for shared filesystems and development), even
though it uses paths and sidecar files?

**N5 — Object storage (S3, cloud) as a locus type for burst or rebuild?**

**N6 — Order of bindings to build after FS:** tape, raw NVMe, raw disk, RAM?

---

## 12. The agent interface

**I1 [NOW] — Confirm the verbs:** `prospect` (what would it cost to get this version here, by which
strategy) and `realise` (the only verb that moves bytes).

**I2 — Should agents be able to move compute to data**, not just data to compute? That requires
GFS to know about compute locations and schedulers (SLURM on the DGX).

**I3 — Transport for streaming: Cresco dataplane only, or also plain HTTP/gRPC for agents outside
the mesh?**

**I4 — Which client languages must work at launch?** Python (pycrescolib) and Java are both
required for Cresco generally. Anything else?

**I5 — Should GFS verbs appear in the Cresco capability inventory as LLM tools** (like the 89
existing ones)?

**I6 — Cost model returned by `prospect`:** drive-hours, wall time, dollars, carbon, egress? Which
matter to an agent's decision?

**I7 — Admission control: when retrieval demand exceeds the plant, which requests wait, and who
decides priority?** At 100 TB/day scattered the plant is oversubscribed 2.75×.

**I8 — Do agents get notified when a realise completes (push), or do they poll?**

---

## 13. filerepo

**F1 — Confirm filerepo's role:** it materialises local versions (as a cache) and can publish new
versions, but is no longer primary storage.

**F2 — Should filerepo's `phase0-crypto-baseline` branch (`repostate`, `clearRepo(force)`) merge to
1.3?**

**F3 — Does filerepo become a GFS binding, a GFS client, or both?**

---

## 14. Operations

**O1 [NOW] — Fix the DGX mesh storage path?** Nodes under `~/cresco/nodes` are on a network
filesystem and are now refused durable copies. Point `store_dir` at node-local storage, or attest?
**Rec:** node-local; it is also 40× faster.

**O2 — Who operates each site day to day** (media handling, drive swaps, destruction ceremonies)?

**O3 — Partner institutions: is a DUA or MOU required before a site holds our ciphertext?**

**O4 — Monitoring: extend the existing dashboard Storage tab to per-locus measured properties and
barrier evidence?**

**O5 — Alerting: who gets paged, and for what** (site loss, under-protected objects, media wear)?

**O6 — Disaster-recovery drills: how often do you want a full "lose a site, rebuild" exercise?**

**O7 — Deployment path: Cresco agent release chain as today (plugin → snapshot → embed → release)?**

---

## 15. Measurements — who runs them and when

**M1 [BEFORE MEDIA] — The mount cycle, as a distribution over a few thousand exchanges.** The
highest-leverage unmeasured constant in the design; a 45 % error moves throughput ~23 %. Needs a
real drive. When, and where?

**M2 [BEFORE MEDIA] — Shoe-shine floor / minimum speed-match rate for LTO-10.** Sets spool size.

**M3 — Count the imaging estate.** ~850 TB UK chest CT and ~700 TB KPDT pathology are 92.6 % of
the sizing basis and come off slides, with five conflicting KPDT figures. Can someone run a PACS
query and a pathology system query?

**M4 — Consent-withdrawal rate** on a real clinical lineage. Who would know?

**M5 — A real request log to mine co-occurrence from.** Does any exist (DGX job logs, panAtlas API
logs)?

**M6 — Power-loss test on the candidate site hosts** — the only way to prove a barrier reaches
power-safe media rather than just costs time. Worth doing?

**M7 — Recompute cost of the derived panAtlas artifacts** (X5).

**M8 — Growth rate.** There is one census and no time series. Planning uses 1 TB/day; at 0.5 or
2 TB/day expansion dates move by years. Can you give a figure?

---

## 16. Licensing and legal

**L1 — Confirm "permissive commercial licences only"** covers everything that ships, and that
GPL is acceptable only in test infrastructure that never ships (mhvtl).

**L2 — Do you want counsel to review** the licence position, the DUA implications of partner sites
holding ciphertext, and whether key destruction satisfies withdrawal obligations?

**L3 — Copyright/licence for GFS itself:** Apache-2.0 as the pom declares?

---

## 17. Process

**Q1 — Re-cut `SPECIFICATION.md`** so the core is locus, extent, placement, index, versioning,
crypto and replication, with tape as one binding's appendix? It is currently 6.8:1 tape terms to
media-neutral terms. **Rec:** yes, before more design goes in.

**Q2 — Commit policy:** **ANSWERED 2026-09-23:** commit and push every change; the repository is `GaiaKeep/gfs` (moved from CrescoEdge).
Keep doing that? Push to origin, and when?

**Q3 — Multi-agent workflows:** they produced most of this week's findings, including the wire
bug. Run them freely on design questions, or ask each time?

**Q4 — Atlas capture:** file GFS decisions and measurements into myatlas as they happen, or batch?

**Q5 — How do you want to answer this list** — inline edits to this file, a call, or chat?
