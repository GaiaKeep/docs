# Release 1.3 (2026-10-01)

GFS 1.3 is the first release of the durable storage core. It was integrated from about twenty
independently built packages, reviewed adversarially twice, and validated on a single host and on
the HPC cluster before shipping.

| What | Where | State |
|---|---|---|
| GFS storage core (`io.cresco.gfs`) | `GaiaKeep/gfs`, branch `1.3`, `8461e1a` | CI green: 2,188 core tests, 50 Java client tests, Python client, lints; release jar published |
| Cresco framework fixes | `CrescoEdge` controller, wsapi, stunnel, agent: branch `1.3` | CI green on each |
| Python client library | `pycrescolib` 1.3.1 on PyPI | published |

See [Test results](tests.md) for what was tested and [Benchmarks](benchmarks.md) for the numbers.

## What is new in 1.3

**Transport foundation.**

- **Data rides the dataplane only.** Storage-node traffic streams as windowed, acknowledged frames.
  MsgEvents open and close streams and carry nothing else.
- **QoS tiers per traffic class:** acknowledgements high, background bulk lowest, Raft on its own class.
- **Speed:** many flows per transfer, never one request per block. A flow went from 62–82 MB/s to
  0.7 GB/s, and 2.1–2.4 GB/s across 4–8 flows on the HPC cluster.
- **Acks:** selective-acknowledgement ranges, coalesced, so one lost frame no longer floods the link.
- **Bounded memory:** windows, budgets and per-transfer state sized to the window.

**Replicated core.**

- A Raft-replicated metadata core with a MAC-chained log, group commit, snapshots and pre-vote.
- **Leader lease.**
- **Fenced against stale leaders:** deposed-leader fencing on storage-node requests, and non-voter
  catch-up for a peer that lost its disk.

**Security (zero trust, fail closed).**

- **Signed requests and roles:**
  - every request is signed (ECDSA P-384);
  - roles are tenant-scoped, and the system administrator has no data access;
  - the audit log is tamper-evident.
- **Keys:** custody through file, environment or PKCS#11 sources. Master-key rotation is behind an
  operator window.
- **Storage nodes:** traffic is signed and encrypted, with pinned node keys.
- **Clients:** per-stream key exchange, with signatures bound to the request parameters.
- **Metadata encryption:** sealed partitions, keyed identifiers and sealed snapshots.

**Data and deduplication.**

- Blocks of at least 1 MiB, with the chunker and policy chosen per dataset. Named profiles:
  radiology DICOM, pathology WSI, scratch cache.
- **Audited format adapters:** DICOM, NIfTI and TIFF are cut so that a metadata edit such as
  de-identification does not rewrite the bulk data. The client cuts the same way, so a de-identified
  re-upload sends under 1 % of its bytes.

**Operation model.**

- **Ingest** is a multi-part, striped transfer. Parts are processed as they land, then a short,
  idempotent commit. No synchronous request runs longer than 20 s.
- **Long operations are async jobs.** They take an idempotency key, push signed events on the
  dataplane, and can be polled.
- Resumable uploads.

**Replication and reads.**

- Chain replication: the writer sends each block once, and every hop returns a signed receipt.
- Follower reads with read-your-writes.

**Storage formats.**

- **Pack containers on storage nodes.** These are 8× faster publish and 2× faster reads, and start
  in under a second at a million blocks.
- **Tape:** the software path, with deferred reads behind tickets, an LTO-class simulator and
  virtual-tape (mhVTL) tests.

**Lifecycle.** Forget, prune, destroy, retention and legal hold, with quorum approval.

## Found and fixed on the way

The adversarial reviews, power-cut campaigns, crash matrix, model-based tests and HPC runs found and
fixed defects that unit tests alone had missed. Every fix has a regression test that failed before
it. The most serious:

- **A scheduled recovery pass could erase a publish in flight** after the client was told it
  succeeded. Now fixed: recovery leaves intents owned by live writes alone.
- **A copy made on withdrawal could deduplicate onto a block with no copies left,** and garbage
  collection then removed the last good one.
- **A wiped core peer could be promoted to voter by a stale message,** and a committed entry could
  then be overwritten.
- **A leader holding a lock while syncing its log stopped sending heartbeats under heavy upload,**
  and lost leadership. Found on the HPC cluster. The sync now runs outside the lock, and the default election
  timeout is 6 s.
- **More than 20 durability ordering defects** in the logs, journals, pack and tape stores, found by
  power-cut testing.
- **In the framework:**
  - silent message loss in the web API's dataplane egress;
  - silent truncation of tunnel streams under load;
  - secrets reaching broker URIs and logs.

## Defaults

Every policy default (block size, chunker, replication topology, follower reads, timeouts and digest
mode), with its reason and the cost of changing it, is recorded in the design record's default
policies. Upgrades that change a wire format, such as the Raft log, node acknowledgements or index
replication, need every peer upgraded together. Mixed versions refuse each other rather than
misbehave.
