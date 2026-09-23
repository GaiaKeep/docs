# The caching tier

!!! info "Status"
    **Scheduled after the durable storage core is complete.** filerepo is being left as it is
    until then; it will change substantially when this work starts.

## Role

> "The actual storage will be tightly versioned datasets, which can be recreated anywhere, and when
> they are live, they are considered a cache, either versioned or unversioned." (owner)

The durable, versioned store is the source of truth. Every live working copy, whether on a GPU
node, at a partner site or in an agent's scratch space, is a **cache**:

- A **versioned cache** is a materialised copy of a named version or extract. It can be evicted and
  recreated anywhere, bit-identical, from the durable store.
- An **unversioned cache** is scratch work in progress. It isn't durable until it is published as a
  new version.

**filerepo** is the component that creates and manages local copies. It also **creates new
versions**: an agent works in a local cache and publishes its changes back as a version.

## What exists today

On filerepo branch `phase0-crypto-baseline` (commit `40519ff`), **Built**:

- `repostate` reports a local repository as `CACHE`, `CACHE_WITH_UNCOMMITTED` or `ONLY_COPY`.
- Dirty files are detected by comparing against the materialisation manifest, not by trusting a
  flag.
- `clearRepo(force)` **refuses** to clear a repository that holds uncommitted changes and has no
  upstream copy.

## What the advanced tier needs

To be designed once the durable store's interfaces are fixed:

- [ ] Materialise a version or extract to a locus, streamed and verified block by block
- [ ] Delta materialisation: bring a cache from version *n* to *n+1* by fetching only changed blocks, using deduplication
- [ ] Leases on residency: a cache holds data for a term, renewed or released
- [ ] Eviction policy that respects leases and cost, and never evicts an only copy
- [ ] Publish-back: turn local changes into a new version, including branch and merge
- [ ] Cache placement from the same measured locus properties as durable placement (RAM and NVMe are loci)
- [ ] Coherence: a cache always knows exactly which version it holds, and stale reads are impossible by construction
- [ ] Audit: what was materialised where, for whom, under which grant

## Why it waits

The cache's contract is "a copy of a named version." Until versions, block identity, deduplication
domains and grants exist in the durable store, any cache design would be built against interfaces
that are about to change.
