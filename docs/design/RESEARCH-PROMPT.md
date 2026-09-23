!!! note "Status: Historical record"
    The deep-research prompt on federated archival storage.

# Deep research prompt — open problems in a federated, encrypted, erasure-coded archive

## What to do

Find how these problems have been solved in production systems and in the literature. For each
question below, we want prior art, the trade-offs the builders actually hit, and **negative results**
— designs that were tried and abandoned matter more to us than success stories, because our
constraints rule out most of the obvious answers. Where a question has no good answer in the
literature, say so plainly rather than stretching an adjacent one to fit.

## The system

A federated archival storage system spanning multiple independent institutions (initially ~50 sites
across one US state, universities and health systems). Properties that are already built and working:

- **Encrypt-then-erasure-code at the origin.** A file is encrypted with the providing institution's
  key, split into stripes, Reed–Solomon coded into `k+m` fragments, and scattered so that no two
  fragments of a stripe land in the same failure domain. **Holding sites are blind block stores** —
  they cannot read what they hold.
- **No single trusted operator.** Key custody is Shamir *t*-of-*n* across institutions; reconstruction
  authorisation is a quorum of institutional approvers, minting a time-limited token.
- **Governed by a Data Use Agreement.** Much of the data is clinical/PHI. Presence in the index does
  not imply a right to read.
- **A journaled index** (single mutation path: commit → apply → journal → replicate) with a read-only
  replica, proven at 10⁶ files.
- Placement is policy-driven: survivability profiles with failure domains, a reciprocity ledger of
  pledged/consumed capacity per site, and explicit refusal when a policy cannot be satisfied.

Three changes are planned, and they are what generate the questions:

1. **Tape (LTO/WORM libraries) as the bulk tier**, several units distributed across sites.
2. **Versioned datasets**: reads name an immutable version; changes are posted as new versions;
   writes are confirmed by quorum. Cross-version deduplication is what makes this affordable.
3. **AI agents as the primary consumers**, working over multi-terabyte datasets, each request
   carrying a credentialed, audited token.

## Hard constraints (these invalidate most standard answers)

- **FIPS/CNSA-approved cryptography only.** AES-GCM-SIV, for example, is out.
- **Media that cannot be erased.** WORM tape: a cartridge cannot be rewritten in place; reclamation
  is a whole-cartridge rewrite.
- **A legal obligation to remove specific data** — consent withdrawal, PHI published in error,
  GDPR-style erasure — against that immutable media.
- **Equality leakage is a stated threat.** Global convergent encryption was rejected: a holder must
  not be able to test whether a block it stores equals a known plaintext, or whether two institutions
  hold the same file.
- **High-latency, low-concurrency reads** for anything tape-resident: a mount plus seek is tens of
  seconds to minutes, and drives — not cartridges — are the concurrency limit.
- **Repair is a wide-area bulk operation.** Losing a site means regenerating its fragments by reading
  `k` fragments from other sites across a shared regional network.

---

## Q1 — Per-item crypto-shredding under cross-version deduplication (highest priority)

**The problem.** Today each object has a random DEK whose only copy is the wrapped key in that
object's manifest, so destroying one field permanently shreds exactly one object — including copies
already on WORM tape. This is what makes immutable media compatible with a right-to-erasure.
Cross-version deduplication requires that identical plaintext encrypt identically within some domain,
which implies a **shared key across that domain** — and a shared key makes the domain, not the item,
the unit of shredding.

**What we need.** How do systems that deduplicate encrypted data reconcile it with per-item deletion
obligations? Specifically: what granularity of crypto-shredding is achievable alongside dedup; what it
costs; and whether anyone has shipped something better than "store a key per chunk" or "re-encrypt the
domain on every redaction".

**Where to look.** Backup and archive vendors face this exact combination (dedup + immutability/WORM +
GDPR erasure) — Data Domain/Dell, Veeam, Commvault, Rubrik, Cohesity: what do their architecture and
compliance documents actually claim, and how? Also: Tahoe-LAFS's convergence secret; restic, Borg and
Duplicacy (how do they handle deletion of a single file from a deduplicated, encrypted repository?);
puncturable encryption and revocable/key-homomorphic encryption in the literature; "crypto-shredding"
as practised for cloud object stores; and how AWS reconciles S3 Object Lock in COMPLIANCE mode with
erasure requests.

**What would change our decision.** Evidence that per-chunk keys are workable at 10⁸–10⁹ chunks, or a
scheme giving sub-domain shredding granularity without one key per chunk. Conversely, credible
evidence that production systems simply accept coarse-grained shredding would push us to abandon
cross-version dedup for clinical lineages.

## Q2 — Metadata scale for a content-addressed chunk table

**The problem.** Deduplication needs a table keyed by chunk identity holding, per chunk, its IV, its
holders, a reference count and a lease. At petabyte scale with ~1 MiB stripes that is on the order of
10⁹ entries. Our index currently holds all state in memory, durable via a journal and snapshot, proven
at 10⁶ files. That architecture does not reach 10⁹.

**What we need.** Proven designs for a dedup/chunk index that exceeds RAM, and the operational
consequences — rebuild time after a failure, the cost of reference counting versus mark-and-sweep, and
how the table is sharded or replicated when the index itself is distributed.

**Where to look.** The ZFS deduplication table is the canonical cautionary tale (the "RAM per TB"
rule, and why dedup is widely advised against) — we want the precise failure modes. Data Domain's
SISL/Stream-Informed Segment Layout was built specifically to keep a dedup index off RAM; what does it
actually do? Also: Venti (Plan 9), restic's and Borg's index formats, Ceph's OSD/object maps, IPFS
and Perkeep, Dropbox's Magic Pocket, Facebook's f4, and LSM-based metadata stores (RocksDB) used for
this purpose. How is garbage collection made safe against concurrent writers at this scale?

## Q3 — Versioning a dataset of millions of files without rewriting the tree

**The problem.** A version is conceptually a tree of path → content. Naively, every commit rewrites
the tree; at 10⁶ files that is untenable, and each commit is quorum-confirmed.

**What we need.** Structures where unchanged subtrees are shared and a commit is O(changed), plus how
these systems handle concurrent writers, and whether optimistic concurrency (post against a parent
version, rebase on rejection) survives many autonomous writers on one dataset.

**Where to look.** Apache Iceberg (manifest lists and manifest files), Delta Lake, LakeFS, Nessie,
Dolt, DVC, TileDB, and git's tree/packfile design. We are most interested in **measured** commit
costs and conflict rates at scale, and in what these systems do when the writers are automated
pipelines rather than humans.

## Q4 — Scheduling recalls from high-latency, low-concurrency media

**The problem.** Bulk restores must become a mount plan — resolve to fragments, group by cartridge and
position, mount each cartridge once — or a large restore takes weeks instead of hours. We also need
honest ETAs, per-tenant quotas, and protection against "thaw storms" when an agent requests everything.

**What we need.** Recall-scheduling designs from systems that have run tape at scale for decades, and
the interface they expose for deferred access.

**Where to look.** HPC and physics archives: HPSS, CERN CASTOR and EOS/CTA, Fermilab Enstore, DMF,
StorNext, Versity. Commercially: AWS Glacier and Deep Archive retrieval tiers and their published
behaviour; Spectra's own BlackPearl. Is there literature on tape-aware request scheduling and batching
we should simply adopt?

## Q5 — Erasure coding across sites when some fragments are offline

**The problem.** Wide-area repair traffic is the binding constraint on how many simultaneous site
losses we can survive, and some fragments will be on tape, i.e. minutes away rather than milliseconds.

**What we need.** Codes and repair strategies that minimise wide-area traffic, and any prior art on
coding across tiers where a subset of fragments is on offline or near-line media.

**Where to look.** Azure's Local Reconstruction Codes, Facebook f4, HDFS-EC, Ceph EC, minimum-storage
regenerating codes and clay codes, and hierarchical/pyramid codes (local parity within a site, global
parity across sites). What do operators report about repair storms and throttling in practice?

## Q6 — Capability tokens for autonomous agents

**The problem.** Consumers are AI agents at dataset scale, so per-request human approval is impossible
and request volume carries no anomaly signal. We want per-request, purpose-bound, budgeted tokens that
a parent agent can attenuate for a sub-agent **offline**, with the lineage visible in an audit.

**What we need.** Production experience with attenuable capability tokens at machine scale: revocation,
audit, and what breaks operationally.

**Where to look.** Macaroons (Google's paper and its deployments), Biscuit, UCAN, ZCAP-LD, SPIFFE/SPIRE,
OAuth token exchange and GNAP, and Amazon's internal capability work. Separately: how do
controlled-access data federations bind access to a *purpose* rather than an identity — GA4GH Passports
and Visas, the Data Repository Service, NIH dbGaP and AnVIL, Terra, the European Genome-phenome
Archive? Is there prior art on machine agents as first-class principals under a DUA?

## Q7 — Where computation may materialise plaintext

**The problem.** If an object is reconstituted wherever it is needed, plaintext can appear anywhere.
"Where may fragments live" and "where may plaintext exist" are different policies.

**What we need.** How data-residency and enclave constraints are expressed and enforced when
decryption location is a scheduling decision. Confidential computing and attestation are the obvious
direction; we want to know whether anyone binds *decryption* to an attested location in a federation
of independent institutions, and what it costs.

---

## What a useful answer looks like

- A short comparison per question: approach, who runs it, at what scale, and the trade-off they
  accepted. Prefer engineering blogs, architecture and compliance documentation, conference papers
  (FAST, OSDI, SOSP, USENIX ATC) and post-mortems over vendor marketing.
- **Explicit negative results**: what was tried and abandoned, and why. ZFS dedup's reputation is the
  model — we want that level of candour for each question.
- Where a claim is load-bearing, cite the source and say how strong the evidence is (measured,
  documented, or asserted).
- Flag anything that suggests one of our constraints is mistaken, or that a constraint we treat as
  hard is routinely relaxed in practice. That is more valuable than confirmation.

**Priority.** Q1 and Q2 block implementation; answer them first and in depth. Q3 and Q4 are likely
solved problems where we mainly need to identify the right design to copy. Q5–Q7 can be surveyed more
briefly.
