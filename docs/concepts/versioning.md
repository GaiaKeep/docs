# Versioning

!!! info "Status"
    **Designed.** Specified in the design record (`ENTAIL-AGENT-NATIVE-FS.md` §3 and §6;
    `STORAGE-DIRECTION.md`, versioning sections). Not yet built. The prototype publishes
    file-granular deltas to the index, which is **Proven**, but it has no version objects.

## The rules

- **Reads are versioned.** Every read names a version, or an extract of one. There is no "latest
  bytes of this file" read. An agent that wants the latest asks the index which version is current
  and then reads that version.
- **Writes are confirmed by quorum.** A new version exists once a quorum of the federation index
  has committed it.
- **Durable storage is versioned; live copies are caches.** A working copy on a GPU node or at a
  partner site is a cache of a named version, or an unversioned scratch cache. It is never a second
  source of truth. See [The caching tier](../roadmap/caching-tier.md).

## Structure

A **collection** (dataset) has a history of **versions**. Each version is a small root record that
names an ordered list of immutable **runs**. Each run lists the files changed in one commit,
including deletions.

- A commit writes **one new run plus a root of about 6 KB**. Every unchanged run is referenced by
  name, so committing is proportional to what changed, not to dataset size.
- Unchanged file content is referenced, never rewritten. On tape that matters a great deal: a new
  version doesn't rewrite a single cartridge.
- Diffing two versions is proportional to what changed between them.

Branches allow parallel work by different agents. Each branch holds a lease, and merges are
compare-and-set against the branch head.

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
