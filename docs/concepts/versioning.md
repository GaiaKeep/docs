# Versioning

!!! info "Status"
    **Built (release 1.3), Proven on the live fabric** for the versioning model agents use:
    versioned reads, per-branch version histories, compare-and-set commits, time-travel reads and
    retention classes — the storage engine's versioning is **Proven** (508 engine tests, model-based
    testing and the crash matrix; see [Status at a glance](../built/status.md)), and the control
    dashboard browses collections, branches and version histories as existing behavior
    ([Collections and versions](../dashboard/collections.md)).
    **Designed, not built:** the runs-and-roots container layout below (each commit a ~6 KB root
    referencing unchanged runs), the caching tier's working copies, and the pin-amplification
    accounting described later on this page. The prototype's file-granular index publishing is
    **Proven** for the prototype era and is not the 1.3 mechanism.

## The rules

- **Reads are versioned.** Every read names a version, or an extract of one. There is no "latest
  bytes of this file" read. An agent that wants the latest asks the core which version is current
  (the branch head) and then reads that version.
- **Writes are confirmed by quorum.** A new version exists once the core's replicated log has
  committed it (a majority of the core peers). A durable collection's version additionally commits
  only when its tape copies verify: until then reads answer `COMMITTING` and the publish reply names
  the commit job to await ([The replicated core log](../design/CORE-LOG.md), [Tape simulation](../design/TAPE-SIMULATION.md)).
- **Durable storage is versioned; live copies are caches.** A working copy on a GPU node or at a
  partner site is a cache of a named version, or an unversioned scratch cache. It is never a second
  source of truth. See [The caching tier](../roadmap/caching-tier.md) (**Designed**).

## Structure

A **collection** (dataset) has a history of **versions**. Each version is a small root record that
names an ordered list of immutable **runs**. Each run lists the files changed in one commit,
including deletions.

!!! warning "Built today"
    The 1.3 core stores each version as a whole-version file table with per-branch numbering,
    parent links and commit notes — what the dashboard's history view and `core.versions` show —
    not yet the run/root decomposition here. That decomposition (commits proportional to what
    changed, containers never rewritten on tape) is **Designed** (ENTAIL-AGENT-NATIVE-FS §3, §6).

- A commit writes **one new run plus a root of about 6 KB**. Every unchanged run is referenced by
  name, so committing is proportional to what changed, not to dataset size.
- Unchanged file content is referenced, never rewritten. On tape that matters a great deal: a new
  version doesn't rewrite a single cartridge.
- Diffing two versions is proportional to what changed between them.

Branches allow parallel work by different agents. Each branch holds a lease, and merges are
compare-and-set against the branch head.

## An agent's versioning workflow (what is built)

1. **Discover** the collections you may name: the authorized tenant listing
   (`core.collections`, paged), plus what your profile and role bindings name — the dashboard's
   [Collections page](../dashboard/collections.md) shows both.
2. **Inspect** a collection's branches and each branch's head (`core.branches`), then its version
   history, newest first (`core.versions`, paged) — the collection's detail page in the dashboard.
3. **Retrieve** an exact version: every read names a version (or reads the branch head by default).
4. **Create** a new version: put files and commit; concurrent writers compare-and-set against the
   branch head, and the loser receives the head that moved (stale-head) and rebases.
5. **Reconcile** a pending publication before declaring it complete: a durable collection's commit
   may answer `COMMITTING` — poll the named commit job (or `core.putstatus`) until it finishes;
   reads answer `COMMITTING` until then ([Tape simulation](../design/TAPE-SIMULATION.md) §4,
   [Jobs and the API](../design/JOBS-AND-API.md)).

## Extracts: citable points in time

An **extract** is a frozen, named selection from one or more versions. It is the unit an agent
cites in a paper, a model card or a grant, and later reproduces.

- It is defined by a **closed, deterministic selector** (prefix, glob, attribute, byte span within
  a file, seeded sample, all) plus a hash of the resolved set. Given the citation, anyone can check
  that a reproduction contains exactly the same set and is complete.
- Byte spans are supported, so a single tile of a gigapixel slide or a range of a genome file can
  be cited and reproduced without the whole file.
- An extract that spans several datasets records each one's version under a single reservation, so
  every component is protected from garbage collection before enumeration begins.
- Citation form: `gfs:1c:<cut>#<extract-id>`. The class (`c` cite, `r` run, `s` scratch) is part
  of the name, because someone reading a paper doesn't have the record.

This follows the RDA Working Group on Data Citation recommendation (2015): version the data,
persist and hash the query, hash the result set, and verify by comparing hashes.

### Pinning has a cost the system refuses to hide

Storage is packed into large containers, and a pinned extract pins every container holding any of
its data. A uniform 0.1 % sample of a dataset pins 64 % of its containers. The design therefore
computes the pin amplification when an extract is frozen and **refuses above a threshold** (default
4×), offering to repack the selection into fresh containers instead. A pin guarantees that the data
**exists**; it does not guarantee that it is **resident** on fast media.

## Derivations: names for data that may not exist yet

A **Derivation** is a citable object whose identity is its recipe (inputs, transform, parameters),
not its bytes. It can be registered instantly, cited, and budgeted against. Whether it is currently
stored is a scheduling decision the system makes and revisits. `ABSENT` is a legal, permanent
state.

This matters because at agent scale most new data is derived (tokenised shards, embeddings,
resampled imaging, filtered cohorts, checkpoints), often 10–100× the source each year, with a
useful life of days. Storing all of it permanently would exhaust the archive; recomputing it on
demand from retained recipes doesn't.

## After a subject withdraws

When consent is withdrawn, the affected data is made unreadable by destroying its keys. An extract
that included it still verifies: surviving entries still prove membership, withdrawn entries
return a signed attestation instead of bytes, and the extract is marked `PARTIALLY_REDACTED`.
Reproducing the withdrawn content is permanently and visibly impossible. That is the correct
outcome, and the design states it rather than hiding it.

!!! warning "Interaction with deduplication"
    The withdrawal mechanism in the design record assumes per-object keys, and it predates the
    owner's deduplication requirement. In shared dedup domains a block may be referenced by several
    objects, so withdrawal needs reference counting. See
    [Deletion, retention and repack](deletion-and-repack.md).
