# Purpose and principles

## Who it is for

Autonomous agents: training pipelines, analysis agents, evaluation and decontamination jobs, and
agents working on behalf of partner institutions. Humans run the system; they are not its users.
There is no browsing interface, no mount point and no console. Operators get monitoring (the
Cresco dashboard's Storage tab) and nothing else.

This changes the design:

- **Planning comes before reading.** An agent asks what it would cost to get a version to a place,
  by which strategy, and how long it would take. Only then does it commit. Offline or slow data is
  a normal state the agent plans around, not an error.
- **Moving computation to data is a first-class choice.** Copying a dataset locally and shipping
  a job to where the data lives are two strategies behind one request, priced the same way.
- **Everything is addressable and citable.** A version, or an extract of one, has a name that stays
  valid for as long as the data is retained.

## What the system does

1. **Stores versioned datasets durably**: copies across independent sites, integrity checked,
   repaired without human action.
2. **Streams any version wherever it is needed**, as a byte stream from whichever copy is cheapest
   at the moment of the request.
3. **Keeps live copies as caches.** A working copy on a GPU node or at a partner site is a cache of
   a version, not a second source of truth. The durable, versioned store is the source of truth.
4. **Deduplicates at the block level** within whatever scope policy allows, so that a new version
   or a combined dataset stores only what is actually new.

## The principles

**The data is raw.** Storage holds raw blocks. There is no filesystem underneath and no LTFS
layer, because a filesystem adds a second catalogue, a second failure mode, and metadata written in
the clear. The system manages its own blocks.

**The medium does not matter to callers.** Memory, NVMe, spinning disk and tape are one continuum.
They differ in measured properties: how fast the first byte arrives, how fast bytes stream, what
each access costs to set up, whether the medium survives power loss, whether it can be removed and
stored offline. Placement works from those measurements, never from a media label. Tape is "just a
block of data" with a large setup cost.

**Measure; don't declare.** A property that drives a decision must be measured, or visibly marked
as unmeasured or attested. One storage node can deliver 339 MB/s on local disk and 8 MB/s on a
shared filesystem while describing itself identically in both places. A system that trusts the
description places data on the wrong node.

**Fail closed.** When the system can't show that a copy is durable, the copy doesn't count toward
durability. When it can't show that access is permitted, access is refused.

**Configurable from complete isolation to global sharing.** Some tenants must share nothing with
anyone. For public data, deduplication across datasets and across tenants is expected. Both
extremes, and everything between, are policy. See
[Tenants, collections and deduplication](tenancy-and-dedup.md).

**Permissive licences only.** Everything that ships uses permissive licences (Apache-2.0, MIT,
BSD). Copyleft code may appear only in test infrastructure that is never shipped or linked. This is
why Bareos was removed; see [Media and tape](media-and-tape.md).

**Built on Cresco.** Cresco supplies the mesh, identity, tenant isolation, messaging and the
dataplane. The storage system does not reinvent any of them.
