!!! note "Status: Historical record"
    The working note that took the design from a tape assessment to the agent-native fabric. Useful for the reasoning; several recommendations in it (S3/Glacier front end, LTFS, Bareos) were later reversed.

# GFS storage direction

Started as an assessment of the Spectra Cube LTO library as a backend (LumOS, *Spectra Cube User
Guide*, July 2026) and grew into the direction note for where GFS storage is going: tape as a
substrate, an S3 front end, programmatic two-phase access, per-request tokens for agent consumers,
and reconstruction as a placement decision. Device facts are from the user guide unless marked
otherwise; everything about GFS is cited to the source.

## What the device actually is

| | |
|---|---|
| Form | Single-frame LTO library (chamber locators are `Frame:Side:Bay:Chamber`, and "for the Cube library, Frame is always 1") |
| Media | TeraPack magazines, **10 LTO slots each**; one magazine per chamber; chambers licensed by Capacity on Demand |
| Drives | LTO-6+ full-height Fibre Channel, LTO-7+ half-height FC, **LTO-9/LTO-10 full-height SAS** |
| Data path | SCSI over Fibre Channel (loop or fabric) or SAS. A Spectra Swarm bridge adds **40 GbE** in front of SAS drives |
| Robotics path | SCSI media-changer commands to an "exporting controller" drive at LUN 1, relayed over ADI. **A drive can export only one partition; max 30 exporters, so max 30 partitions** |
| Management | **LumOS ReST API at `https://<library>/api`**, JWT bearer (`POST /api/auth/login`), "all aspects of the library that are available when using the front panel". Syslog to a remote server; AutoSupport logs |
| Encryption | BlueScale key management + the **encryption chip in LTO-6 and later drives** — done in hardware as data is written, no host cost |
| Health | **MLM** (media lifecycle) and **DLM** (drive lifecycle) databases: per-cartridge health, per-drive error rates; PreScan on import; Quick PostScan readability verification per partition |
| Partition knobs | Soft Load, SlotIQ move optimisation, MLM discovery mode, Read Element Status (standard or tape-generation) |

**There is no object or file interface.** The guide documents no LTFS and no S3; `BlackPearl`,
`Vail` and `StorCycle` appear only in the trademark list. The ReST API is a *management* plane —
partitions, inventory, media, drives — not a data plane. Bytes move over SCSI to a tape drive.

## Why it cannot simply be a GFS storage node

A GFS store is `BlockStore`: a flat directory where fragment `f` is the file `root/f`, `get()` is a
synchronous whole-file read returning `byte[]`, and `has()` is `Files.isRegularFile`. The index
heartbeats nodes every 3 s, moves a silent node SUSPECT → LOST after the profile's grace, and the
repair planner assumes it can pull `k` fragments promptly from survivors.

Tape breaks three of those assumptions at once:

1. **Latency.** A cartridge mount, load and seek is tens of seconds to minutes. A synchronous
   `getfragment` would block a job thread for that long, and the caller has no vocabulary for "later".
2. **Concurrency.** Drives, not cartridges, are the parallelism limit. Recalls queue behind each
   other; `k` fragments on the same library serialise.
3. **Liveness ≠ availability.** The agent host stays up and keeps heartbeating while its fragments
   are minutes away. GFS currently has exactly two node states that matter for placement, and
   "up but slow" is not one of them.

Placement scoring makes this concrete: `IndexEngine` weights a node by
`classWeight × availability × netFactor`, where `netFactor` is `probe_mbps / netCapMbps`. A tape
site measured that way scores near the floor and would rarely be chosen — which is almost the right
answer, but for the wrong reason, and it gives no way to *require* a tape copy.

> (**2026-09-19:** the remedy has moved — see `STORAGE-BINDINGS-DECISION.md` §7 for the
> `durabilityScore`/`accessCost` split, in which `netFactor` leaves placement for every locus.
> `eval/results/fsync_cost.json` shows the formula misprices disk too: `probe_mbps` measures a NIC,
> and a node whose medium delivers 8.6 MB/s — about 69 Mb/s, under the 100.0 Mb/s default cap — is
> still scored on its uplink rather than on its medium.)

## Three shapes, and the one to build

**A. Tape-backed store node (disk stage + mover).** A Cresco agent on the host attached to the
library runs a gfs store whose `root_path` is a disk staging area; a mover batches sealed fragments
to tape and recalls them on demand. Honest, self-contained, and it reuses every existing RPC — but
it needs a deferred-read path through `getfragment`, which today has no such return.

**B. Tape as an extra durability domain, never on the read path** — *recommended first step*.
The library gets its own **site** with a new `node_class` (`tape-library`), and survivability
policies require one fragment per object in that domain. Normal reads take the `k` fastest
disk-resident fragments and never touch tape; tape is read during a genuine disaster or a scheduled
audit. This needs no change to the read path at all, because the read path already prefers whatever
answers first.

> **RETIRED 2026-09-19.** Shape B requires a stripe whose fragments span two latency classes.
> `STORAGE-BINDINGS-DECISION.md` §7 makes stripe homogeneity a placement invariant (*"`place()` must
> enforce stripe homogeneity: the `n` fragments of a stripe share a latency class … makes mixed-media
> k-of-n unrepresentable rather than merely discouraged"*), and `SPECIFICATION.md` §2.1 makes it a
> layer rule (*"stripe placement enforces latency-class homogeneity so the branch happens once per
> stripe, not once per fragment"*). The design of record is shape A: a homogeneous tape tier with its
> own plant, its own stripes (RS(2,1) across three sites) and a staging tier, reached through
> `realise`. **Hole left open:** nothing now expresses "require one offline copy of an object that
> otherwise lives on the disk tier" — the property shape B was recommended for, and the stated prize
> of the whole tape direction. Recorded; not solved here (see *Unresolved* 11).

**C. Buy the gateway.** Put an S3-speaking appliance (BlackPearl) in front and treat it as an
ordinary slow store. Simplest integration, an extra appliance and licence, and worth pricing before
building A — but nothing in this guide says the Cube does it on its own.

Recommendation: ~~**B now, A next.**~~ **SUPERSEDED 2026-09-19 — shape A only** (see the retirement
note above). B is mostly configuration plus a placement rule and buys the real prize — a copy on
removable, offline-capable media in a different failure domain — but it cannot be expressed under
stripe latency-class homogeneity. A is the larger piece of work and should not start until the
deferred-read semantics below are settled.

> If the deployment is **several libraries distributed across sites** rather than one, A stops being
> optional: the libraries *are* the pledged capacity. See *Several libraries, distributed across the
> state* below.

## What changes in GFS

- ~~`IndexEngine.classWeight` — add `case "tape-library"`. Its weight should express *durability*
  value, not speed, so scoring must stop multiplying it by `netFactor` for that class (a tape site's
  probe throughput is meaningless; the drive path is not the agent's uplink).~~
  **SUPERSEDED 2026-09-19** by `STORAGE-BINDINGS-DECISION.md` §7: the single scalar splits into
  `durabilityScore(n)` (placement) and `accessCost(n, plan)` (read planning); `netFactor` leaves
  placement **for every locus, not for one class**; and `classWeight` is demoted to a fallback
  consulted only when no `LocusDescriptor` is present. Adding a high-weight tape case to the existing
  switch is identified there as specifically the wrong fix — it would make a tape locus win placement
  for hot objects on a durability argument, correct in the term measured and catastrophic in the term
  not measured. `eval/results/fsync_cost.json` settles why the per-class carve-out was too narrow:
  `probe_mbps` measures the NIC on a disk locus as well, and a node whose medium measures 8.6 MB/s is
  scored on a link that is not its constraint. The reasoning is kept because the diagnosis — "a tape
  site's probe throughput is meaningless" — was right; only its scope was too small.
  **Naming is fixed as follows and used everywhere: `bindingKind = TAPE`, `mediaClass = LTO10-WORM`,
  `latencyClass = MINUTES`.** `node_class: tape-library` is withdrawn as a synonym.
- **Survivability policy** — extend the `{"domain": ...}` vocabulary with a required-domain
  constraint ("at least one fragment on a `tape-library` site"). The refusal machinery already
  reports unsatisfiable asks, so a fabric with no tape site fails closed and says so.
- **Deferred reads (needed only for shape A)** — `getfragment` gains a `STAGING` answer carrying an
  ETA, the index treats a staging holder as present-but-slow, and the repair planner must not read
  slow as lost. This is the one place the current SUSPECT → LOST logic would actively misfire.
- **Batching** — a fragment is the wrong write unit for tape. The mover should fill a cartridge with
  many fragments and keep a manifest of `fragment → barcode + file position`; `delfragment` becomes
  a tombstone reclaimed by a rewrite, not an unlink.

## Encryption and key custody

GFS encrypts *before* erasure coding, so what reaches tape is already ciphertext under a per-object
DEK wrapped by a site KEK under Shamir *t*-of-*n* custody. Drive-level BlueScale encryption is
therefore **redundant for confidentiality** but still worth enabling as media-theft defence in depth,
since the LTO chip does it at line rate for free.

The caution is key domains: BlueScale keys live in the library and are exported to a file. Keep GFS
custody authoritative and make sure **no GFS restore path can ever depend on a BlueScale key** —
otherwise a library failure turns a recoverable object into a lost one, and the t-of-n quorum that
governs the real key is bypassed by a second secret with weaker custody.

## Telemetry, capacity and audit — all straightforward

- **Telemetry.** The LumOS ReST API exposes what the UI shows. A poller publishing Micrometer gauges
  into the existing metric inventory would put tape on the dashboard's Storage tab for free:
  cartridges by health (MLM flags red media), drive error rates (DLM), free-pool chambers, TAP state.
  Syslog can additionally point at a collector.
- **Capacity/ledger.** Pledged = licensed chambers × 10 slots × cartridge capacity; consumed = bytes
  written (MLM tracks per-cartridge); headroom = free pool + unwritten. The reciprocity ledger's
  entitlement/consumed/headroom model needs no change.
- **Scrub.** A byte-level GFS scrub is the wrong tool on tape. Map `scrub`/`auditnow` on a tape store
  onto the library's own **Quick PostScan** readability verification and MLM health instead of
  streaming fragments back.

## Tenancy

One partition per tenant is possible and gives SCSI-level isolation, but each partition burns an
exporting drive and the ceiling is 30. Drives are the scarce resource, so prefer **one GFS partition**
and keep tenant separation in GFS's own namespacing, with fragments opaque to the tape layer.

## Several libraries, distributed across the state

This is the case the federated storage plan was written for, not a variant of it: "pledged bulk
capacity across sites provides a low-cost, low-performance durability tier using global erasure
coding rather than replicas", with holding sites as **blind block stores** because data is encrypted
with the providing institution's keys before it is chunked and coded. Buying uniform libraries and
operating them yourself removes the hardest part of that plan — you set `node_class`, partitioning,
firmware, API access and the staging tier at every site instead of negotiating with each institution's
storage team — and the "keep-in-state" placement constraint is satisfied by construction.

### The number of libraries is the design parameter

With one fragment per library (`{"domain": "site"}`), **N libraries caps the code width**, because a
stripe cannot place two fragments in one failure domain. GFS already refuses an over-wide ask
explicitly (*"survivability policy not satisfiable: n=20 distinct agent domains"*), so this shows up
as a clean error rather than a silent downgrade.

**Superseded 2026-09-19 — the table below is retained as the analysis that produced the site-count
finding, not as a geometry.**

| Libraries | A sensible k+m | Raw overhead | Survives |
|---|---|---|---|
| 5 | 3+2 | 1.67x | 2 whole libraries |
| 8 | 6+2 | 1.33x | 2 whole libraries |
| 9 | 6+3 | 1.50x | 3 whole libraries |
| 12 | 8+4 | 1.50x | 4 whole libraries |

Against 3x replication (200% overhead, survives 2 copies lost) the coding wins on both axes once
N >= 5. ~~The plan's own example is 10+4 across sites: two-site tolerance at ~40% overhead.~~

> The plant actually specified is **three sites**, so the width question does not arise:
> `SPECIFICATION.md` §8.1 shows site tolerance is `D·(1 − k/n)`, independent of `k`, and therefore
> takes **minimal `k` at the target rate, always** — RS(2, 1) globally (1.5×) over RS(j, 4) locally
> with `j ≤ 28` (1.1429×), combined **1.714×**. RS(5,4), RS(6,3), RS(6,4), 10+4 and every k=6
> geometry are rejected there by name. Every geometry in the table above is unbuildable at three
> failure domains.

### What gets better with distance

- **Recall parallelism.** The `k` fragments needed for a read sit on `k` *different* libraries, so
  their mounts happen concurrently on different drives in different buildings. Recall latency is the
  **max** of `k` mounts, not the sum — which is what makes tape-resident reads tolerable at all, and
  an argument for more, smaller libraries rather than fewer large ones.
- **Offline by construction.** A cartridge resting in a chamber is not writable by anything on the
  network, and on WORM media (the drive spec tables list **WORM capability: Yes**) the drive refuses
  to overwrite existing data sets at all. Combined with per-fragment ciphertext and one fragment per
  site, a full compromise of one site can neither read the archive nor destroy it. Disk tiers cannot
  make that claim.
- **Key custody matches the geography.** Shamir *t*-of-*n* across the same sites means no single
  library — and no single institution — can unwrap anything it holds.

### What gets harder

- **Repair becomes a WAN bulk job.** Losing a library means regenerating its fragments by recalling
  `k` fragments from other libraries and writing the result to a replacement: tape reads at several
  sites, a WAN transfer, and tape writes, for the whole library's contents. That is days, not
  seconds. GFS's repair planner is built for fast repair and would need a **bulk mode**: throttled,
  resumable, scheduled, and reporting progress in hours. There is also a policy question worth
  deciding early — for data whose *source* still exists, re-promoting from the source may be cheaper
  than regenerating from parity.
- **Staging disk at every site is now mandatory, not optional.** These units are the pledged
  capacity, so shape A (disk stage + mover) has to be built; the staging tier absorbs ingest and
  serves recent reads, and sizing it is a real number, not a detail.
- **Tape is not lights-out.** Each site needs rack space, power, cooling, a host with an HBA or a
  Swarm bridge, and **hands**: magazines are imported and exported physically through the TAP, and
  drives consume cleaning cartridges. Budget per-site operations, not just capital.

### Transport

[[KentuckyWired]] is the natural carrier — state-owned open-access middle mile with presence in all
120 counties and a 100G core — but ingest and repair bandwidth should be sized explicitly: at a given
link rate, regenerating one library's contents takes a computable number of days, and that number is
what determines how many simultaneous library losses the policy should actually be asked to survive.

### Per-library shape

Up to **16 full-height or 30 half-height drives**; chambers licensed by Capacity on Demand; magazines
of 10 slots. Drives are both the recall concurrency limit and the partition limit (one exporting
drive per partition, 30 max). For a GFS site a handful of drives is likely right — enough for
parallel recall and repair, not so many that they idle. Keep **one partition** and let GFS's own
tenant namespacing do the isolation.

## Front ends: yes to S3 — and put it in front of GFS, not in front of the tape

An S3 gateway bolted onto the library alone would be re-implementing BlackPearl and would inherit
every tape problem with none of the durability. An S3 front end over **GFS** is a different thing and
is the right abstraction, because the semantics already line up:

| S3 | GFS today |
|---|---|
| Bucket | project / dataset (`createproject`, `listprojects`, `projectfiles`, `datasetdelegate`) |
| Key | the file's `rel` path inside its dataset |
| `PUT` | `publish` (index in place) then optional `promote` (encrypt, code, scatter) |
| `GET` | `fetch` / `restore` — already streamed and verified per chunk |
| `HEAD` | `objectstatus` |
| `LIST` | `listobjects`, which already filters by `state`, `not_state`, `site`, `dataset_id`, `limit` |
| Multipart upload | stripes — the natural part boundary |
| ETag | the per-chunk SHA-256 the pipeline already computes |

**The part that matters most: S3 already has the vocabulary for slow storage that GFS lacks.** The
Glacier storage classes plus `RestoreObject` are exactly the deferred-read contract this document
said would have to be invented — `x-amz-storage-class: DEEP_ARCHIVE` on write; `POST /key?restore`
with `Days` and a `Tier`; `202` and `x-amz-restore: ongoing-request="true"` while the fragments are
being recalled; an ordinary `GET` once they are staged. It is a standard, every client already
implements it, and it means **no new protocol has to be designed** for "up but minutes away".

`s3:ObjectLock` is the second gift: `COMPLIANCE` mode with a retain-until date is the standard
immutability API, and backing it with WORM cartridges turns it from a software promise into something
the drive itself enforces.

Where it runs: `wsapi` is already an in-process Netty server with a router, so the S3 endpoint is a
sibling handler or a small plugin beside it, with SigV4 mapped onto the tenant identity and RBAC that
already exist.

### And this is the answer to the backup-tier question

Expose S3 with Glacier semantics and Object Lock, and **you stop writing data movers**: Veeam,
Commvault, rclone, restic, Duplicati, pgBackRest and effectively every modern backup product already
speak S3-to-cloud-tier. The backup tier becomes a configuration exercise for whoever is doing the
backing up, and the state fabric is just a very cheap, in-state, offline-capable target.

## LTFS underneath — real, but know what it buys

> **CLOSED AS SUPERSEDED 2026-09-19, by the adoption of Bareos as Layer 0**
> (`BAREOS-RECOMMENDATION.md` §1 and §11.2; `SPECIFICATION.md` §15 lists LTFS under things deleted
> from the storage layer). `bls`, `bextract` and `bscan` discharge the format-and-reader obligation
> more cheaply: catalogue-free, maintained by someone else, no vendor LE extension needed on WORM,
> and no on-cartridge index that is stale until eject. LTFS survives only as
> `STORAGE-BINDINGS-DECISION.md` §10 Step 7 — an on-demand, admitted, costed, refusable export
> conversion on a drive pair, never on the data path. **In particular, "an LTFS mount point as
> `root_path` works with no code change at all" is withdrawn.** The section is kept as the record of
> what LTFS was assessed to buy.

LTFS is a genuine open standard (ISO/IEC 20919, LTO-5 and later): an index partition and a data
partition on the cartridge, presented as a filesystem, with the **media self-describing**. Two honest
observations:

- **Mechanically it is nearly free for us.** `BlockStore` is already "a directory of files", so an
  LTFS mount point as `root_path` works with no code change at all. It would work *badly* without the
  staging tier and a mount scheduler, because every `get()` would block on a mount and anything that
  stats files in bulk will thrash a drive — but the interface fits.
- **Its real value is archival independence.** A self-describing cartridge can be read by anyone with
  a drive and no proprietary catalog. That is a serious exit-risk and longevity property for a
  publicly funded archive, and it is worth the cost on its own. Pair it with a per-cartridge manifest
  mapping fragment to object and stripe, and the archive is rebuildable from the media alone.

The user guide documents no LTFS support for the Cube; it comes from the drive vendor's software
stack, so confirm it with Spectra for the drive generation actually purchased.

### The stack, end to end

    S3 (Glacier storage classes, Object Lock)     <- what every client already speaks
      GFS (encrypt -> erasure code across libraries, placement policy, index, t-of-n custody)
        staging disk + mount/move scheduler at each site
          LTFS or raw SCSI on the library (WORM media)

The one thing not to build is S3 straight onto a single library with no staging and no GFS.

## As a backup tier specifically

Backup is not the same problem as durability, and it is worth being blunt about the difference:
**erasure coding survives media and site loss, but a deletion, a corruption or a bad write is
faithfully propagated to every fragment.** A durability tier does not protect you from your own
software or your own operators; a backup tier has to.

What GFS would need, beyond what is already built:

- **Point-in-time and retention.** There is no `retention`, `version`, `snapshot`, `expire` or
  immutability concept anywhere in the plugin source today, and no object-level delete action at all
  (only `delfragment`). The absence of delete is accidentally helpful, but retention has to become
  explicit rather than accidental.
- **Expiry aligned to the cartridge.** You cannot punch holes in tape. Group objects into cartridges
  by **retention class** rather than by tenant or dataset, so a cartridge fills, seals and later
  expires as a unit; reclaim is a rewrite, not an unlink.
- **A tape-ordered restore planner.** "Restore these 40,000 files" must become a mount plan — resolve
  to fragments, group by barcode and file position, mount each cartridge once, stream in order. Doing
  it as 40,000 independent recalls is the difference between hours and weeks, and it is the single
  biggest performance lever in the whole design.
- **Catalog disaster recovery.** The index is journaled with a read-only replica, but a backup must be
  recoverable when the primary is gone. Write periodic index snapshots into the same WORM pool so the
  fabric can be rebuilt from tapes alone.
- **Trust separation.** If GFS is both the primary index and the backup tier, one defect or one
  stolen credential reaches both. The mitigation that actually holds is not policy — it is **WORM
  media, enforced by the drive**, plus separate credentials for the backup pool and an append-only
  write path.

## Making *all* storage programmatic (owner direction, 2026-09-18)

The proposal: every object is sealed by default and must be explicitly transitioned into a readable
state before any byte comes back — Glacier semantics applied to the whole fabric, not just to tape.
This is the right call, and the reason is not tape.

**It makes the medium an implementation detail.** Today the read path is synchronous, which works on
disk and cannot work on tape, and every tape design ends up special-casing itself into the liveness
and repair logic. If a read is *always* two-phase, a disk-resident thaw completes in milliseconds and
a tape-resident thaw completes in minutes, through the same call, with the same client code. The
awkward state this document kept running into — "up, but the bytes are minutes away" — stops being a
special case and becomes the normal case that happens to be fast sometimes.

**It turns reads into governed transactions.** A thaw is an event with a requester, a subject, a
reason and a timestamp. That is exactly the chokepoint the federation design already wants: the plan
puts reconstruction authorisation behind a quorum of institutional representatives, custody is already
Shamir *t*-of-*n* with a grant that is consumed on use, and `getaudit` already exists. Make every read
pass through a thaw and you get, without inventing anything: per-access audit, DUA policy evaluated at
one place instead of along the byte stream, optional approval for sensitive datasets, and per-tenant
rate limits. **Bulk exfiltration stops being invisible** — an attacker holding valid credentials
cannot quietly stream an archive, because they must raise thousands of individually logged, quotaed,
possibly approved thaw requests. For clinical data under a DUA, and for the zero-trust posture, that
is worth more than the latency it costs.

**It makes the work schedulable.** A thaw is a job with a queue, a priority and a deadline, which is
precisely what allows tape mounts to be batched in cartridge order, WAN repair to be throttled, and
honest ETAs to be returned. Without it every read is an emergency and nothing can be planned.

**And S3 already standardises it**, so the wire protocol is not ours to design: `RestoreObject` with
`Days` and `Tier`, `x-amz-restore: ongoing-request="true"` while thawing, and `InvalidObjectState` on
a `GET` of a sealed object.

### What this changes in GFS

- **Two orthogonal state axes, not one enum.** Durability (`DURABLE` / `DEGRADED` / `LOST`) says
  whether the object still exists; access (`SEALED` / `THAWING` / `AVAILABLE`) says whether you can
  read it right now. A degraded object can be thawed; a durable one is not automatically readable.
  Collapsing these into a single status is the easiest mistake to make here.
- **Split `restore`.** `thaw` enqueues and returns a job id plus an ETA; `objectstatus` reports access
  state and expiry; `fetch` succeeds only while `AVAILABLE` and otherwise refuses the way S3 does.
- **The staging disk becomes the AVAILABLE pool**, with a TTL and an eviction policy. Its size is
  then a first-class capacity number — how much of the archive can be readable at once — and belongs
  in the ledger and on the dashboard next to pledged and consumed.
- **Authorisation and audit hang off the thaw**, reusing the custody quorum machinery that already
  refuses until the threshold is met.
- **Leases.** An object that expires mid-transfer is a footgun; a thaw grant needs an extend.

### The consumer is an agent, not a person

The workload this is being built for is **AI agents working over massive datasets**, with a
credentialed, audited token per request. That changes the design in ways worth stating plainly.

**It invalidates the volume argument above.** "Bulk exfiltration becomes conspicuous because it takes
thousands of requests" is true when the users are people. When the normal workload *is* an agent
issuing millions of thaws across a dataset, volume carries no signal at all. Detection has to move
from *how much* to *what shape*: does the access pattern match the purpose the token was issued for,
is this a targeted read or a full scan, does it deviate from that agent's own established baseline,
is it reaching across datasets that no single protocol covers. Budget enforcement, not anomaly
spotting, becomes the primary control.

**What the per-request token has to carry**

- **Agent identity** — per agent, never a shared service account, or the audit trail collapses to
  "the pipeline did it".
- **On whose behalf** — the human, protocol or IRB/DUA the work runs under. For a person "why do you
  need this?" can be asked; for an agent the *why* has to be structural, carried in the token and
  recorded in the audit.
- **Scope as a predicate, not an object list** — `dataset_id` plus the filters `listobjects` already
  takes. At dataset scale you cannot enumerate a million object ids into a token.
- **A budget** — bytes and object count. An agent will not self-limit, and the staged pool is finite.
- **A TTL** bound to the thaw lease.

**It must be attenuable.** Agents spawn sub-agents. A parent has to be able to mint a weaker child
token — narrower predicate, shorter TTL, smaller budget — **offline, without a round trip to the
issuer**, with the lineage visible in the audit. That is the macaroon/biscuit property, and without it
agents share credentials and the chain of responsibility is gone. Offline verification also keeps
token checking off the hot path, which matters when minting happens per request.

**Reconciling tokens with the custody quorum.** Per-request human approval is impossible at this
scale, and GFS already has the right shape: custody grants have a TTL, are refused below the
threshold, and are consumed on use. The quorum should authorise a **scope** — dataset x purpose x
window x budget — once; inside that scope, tokens mint automatically and are audited. The human
decision moves to grant time, not read time.

**Scale the API to match.** Thaw takes the same predicate as `listobjects` and returns one job with
one manifest, rather than a million individual requests. The audit records the set, the predicate and
the enumeration, not a row per byte.

**Bind the token to the data path.** If a token authorises a thaw but the bytes are then read by
anything holding a fragment id, the audit is fiction. The fetch must carry the token, and bytes
actually delivered must be counted against its budget.

**The audit becomes a dataset in its own right** — structured (agent, token, purpose, predicate,
bytes, outcome), append-only, hash-chained and signed, and best written into the same WORM pool as
the data so it cannot be rewritten by whatever compromised the fabric. At agent scale nobody reads a
log; it has to be queryable.

**Most of this already exists.** `library.security` has `CrescoIdentity`, `MessageSigner`, `CertTrust`
and `TenantNamespace`; the controller has `CrescoAuthorizationBroker` and `TenantPolicy`; GFS already
writes `audit(who, what, detail)` through the same journal as every other mutation and already runs
custody grants with `grant_ttl_ms`; and the `@CrescoAction` capability inventory already publishes
these operations to agents as a described tool catalog, so `thaw` becomes one more tool an agent can
discover. This is composition, not invention.

### The two things that must not be programmatic

1. **Repair and scrub must never go through thaw.** They read *ciphertext fragments* to regenerate
   parity and verify media; they need no key and no human approval. Routing them through the access
   path would make durability depend on the authorisation path — which means an expired credential or
   an unavailable approver could stop an automatic repair. Keep an internal fragment path that is
   always open to the fabric itself.
2. **The catalog stays synchronous.** Only *content* is sealed. Listing, searching, `objectstatus` and
   metadata must remain instant and cheap, or a user cannot even discover what to ask to thaw. This
   is also what keeps the system usable as a federated index, which is its first purpose.

### Migration

Existing synchronous callers keep working if a disk-resident object thaws inline — effectively S3's
expedited tier, completing within the call when the data is already staged. That lets the contract
change land before the tape exists, which is the right order: **ship the two-phase read now, on disk,
and the libraries become a configuration change rather than a protocol change.**

## Blockers found in the existing code (2026-09-19)

Two questions the versioning specification above assumes away. Both were found by reading the code
rather than the design, and both should be settled before implementation starts.

### 1. The index cannot hold a stripe table at this scale

`IndexState` holds all state **in memory** — `LinkedHashMap` for datasets, files, objects and
custody, `ArrayList<StripeRec>` inside each manifest — made durable by the JSONL journal and
snapshot install. The scale campaign proved **10^6 files** in that structure.

The specification needs a **global `sid ->` table** (IV, holders, refcount, leases) spanning the
federation. At 1 PiB with 1 MiB stripes that is ~10^9 entries, hundreds of GB of heap. The current
index architecture does not extend there.

Options, none yet chosen: an embedded LSM store for the stripe table only; shard the table across
index nodes by `sid` prefix (placement already knows about domains); or keep the table per-lineage
and page hot lineages in. ~~**This is the largest engineering item in the plan.**~~

> **RESOLVED 2026-09-19, in two steps, and no longer the largest engineering item in the plan.**
> (i) The authoritative chunk→offset map moved *inside each xorb*, so neither the read path nor the
> GC mark path consults a global chunk table. (ii) `eval/results/ckpt_dedup_results.json` retires
> cross-object content dedup, and with it the `dedup: sid -> xid` cache — the last federation-wide
> sid-keyed structure. What remains is per-object manifests, ~10^6 per lineage, inside the envelope
> the index is already proven at (10^6 files, 1811 MB heap). That count is a document estimate, not
> a measurement. What now heads the list is stated in *Unresolved* and is unaffected by this
> measurement: the LSM, and after it the commit quorum.

### 2. Lineage keys break the per-object crypto-shred that exists today

Today the DEK is random per object and its only copy is `wrapped_dek` in that object's manifest
(`IndexState` 68). Zeroing that one field **permanently shreds exactly one object**, including copies
already written to WORM tape. That is the mechanism that makes immutable media compatible with a DUA:
consent withdrawal, or PHI published in error, is handled by destroying a key rather than by
attempting to erase media that cannot be erased.

**One key per lineage destroys that property** — the granularity of shredding becomes the whole
dataset. Options:

- a **per-stripe key**, derived but *stored* so it can be individually deleted — preserves shredding,
  at the cost of a key per stripe in the index (which compounds blocker 1);
- **re-encode the lineage** under a new key on redaction, abandoning the old — correct, and expensive
  in exactly the way tape is worst at;
- enforce redaction as **index and holder policy** rather than cryptography — weaker, and it fails
  against a holder that retained a copy.

For clinical data under a DUA this may outrank the deduplication win. **Unresolved.**

## Open questions (not answerable from the user guide)

1. Cartridge capacity and sustained drive throughput for the installed LTO generation — these set
   pledged capacity and the recall-latency budget.
2. Licensed chamber count and drive count in the unit actually being considered.
3. Whether a BlackPearl (or equivalent S3 front end) is available, which would make shape C a
   configuration exercise rather than a development one.
4. Mount/recall latency measured on the real unit, which decides whether shape A's ETA is minutes or
   tens of minutes — and therefore whether a deferred read is worth exposing at all.
5. For a multi-site buy: **how many units**, since that caps the code width and therefore how many
   simultaneous whole-site losses the fabric can be asked to survive.
6. Inter-site bandwidth actually available to this traffic, which sets the repair window — and with
   it, honestly, the maximum size of the archive that can be repaired at all.

Design questions still open, beyond the two blockers above: the version tree shape for a 10^6-file
dataset (unchanged subtrees must be shared — a Merkle/persistent tree, as git does); whether a
version commit rides the coordinator set's epoch-fenced 2f+1 quorum or a separate one; whether
optimistic rebase survives many agents writing one dataset; how large the staged pool must be, which
is the number that decides how much of the archive can be readable at once; and who mints an agent
identity and how it binds to a human or a protocol, which the token design depends on and
`library.security` does not answer.


## Reconstruction as a placement decision (owner direction, 2026-09-18)

The direction: **an object has no home.** It is a set of fragments in the network, and it is
reconstituted wherever it is needed, with the placement and the code adapting over time to whatever
performance and durability then require.

This is closer to built than it looks. What already exists in `DurabilityEngine`:

- **"Any k fragments per stripe"** is already the restore semantics, declared in the action
  descriptor itself.
- ~~**Holders are already raced, not chosen.** `fetchStripe` issues k-have plus redundancy requests and
  takes the first to arrive — *"slow or dead holders simply lose the race"*. The system already picks
  the fastest available fragments dynamically instead of reading from a fixed home.~~
  **Racing RETIRED on any mount-class tier, 2026-09-19.** A discarded request costs a socket on disk
  and a full mount cycle on tape — a cancelled tape read does not return the drive early, because the
  cartridge still has to rewind and unload. **The planner selects `k` deterministically at plan
  time** (`SPECIFICATION.md` §8.5); hedging is retained only where the declared `latencyClass` is
  disk- or cache-resident. `SPECIFICATION.md` §15 prices what the deletion bought at roughly 17% of
  the plant that hedging silently consumed.
- **Decode is already per-stripe and parallel**, over a pool of futures, so a stripe is the natural
  unit of partial work.
- **The key is already reconstituted at the decode point** — `reconstructKey` gathers custody shares
  to a threshold under a token minted by `reconstructauth` once the approver quorum stands.
- **Decode already runs wherever the RPC is sent**: `restore` is served by any node carrying the
  durability role. Location independence is not blocked by the architecture; it is simply not *planned*.

### The line worth drawing

**The manifest is the object. Everything else is policy.** Identity is the manifest — which stripes,
which code, which key. Where the fragments sit, how wide the code is, which tier holds them, and where
a copy gets materialised are all mutable properties that a control loop may change without the object
becoming a different object.

### Why erasure coding makes location cheap

To rebuild you move `k` fragments of `size/k` — **exactly one object's worth of bytes, wherever you
decode**. Decoding at the consumer therefore costs the same bytes as decoding at a notional home and
shipping the result, minus a hop. Replication does not have this property; it wants you to read from
the nearest copy. Coding also gives **(n choose k) ways to read**, which is what makes it possible to
route around a slow link, a loaded site, or a fragment that is currently on tape.

And it is a security improvement: reconstruct at the point of use and **no intermediate site ever
holds plaintext**. The key is unwrapped only there, only under the request's token, only for as long
as the lease.

### What has to be built

- **A reconstruction planner.** Given an object, a place it is needed, and a deadline, choose which
  `k` fragments, from which holders, decoded where. Every input already exists: per-link RTT and
  `probe_mbps`, node class and availability, the holder map, and (once tiering lands) whether a
  fragment is staged or sealed.
- **Decode as a placeable task.** Any agent with the role and enough staging is a candidate
  reconstruction point. Placing work near a need is Cresco's core competence; this is that, applied to
  data.
- **Stripe-range reconstruction.** An agent reading a 10 TB dataset must not have to materialise
  10 TB. Restore currently writes a whole object to a destination path; the engine already works
  stripe by stripe, so ranged reads are mostly a surfacing problem.
- **Memoised stripes near consumers**, with a TTL — the thawed pool becomes a distributed cache, and
  repeat access costs nothing.
- **The adaptation loop itself**, fed by the access telemetry the per-request tokens now produce:
  widen the code and spread it for cold data, narrow it and stage it for hot data, migrate tiers as
  demand decays.

### Where "anywhere" has to stop

- **Materialisation needs its own policy, separate from placement.** "Where may fragments live" and
  "where may plaintext be reconstituted" are different questions with different answers — legal
  constraints such as keep-in-state, or data that may only be materialised inside a particular
  facility. Without this control, "reconstruct anywhere" means "plaintext anywhere".
- **A cache is not a copy.** A memoised reconstruction must never count toward a survivability policy.
  Conflating the two is how a system convinces itself it is durable when it is holding one coded copy
  and a pile of caches.
- **Re-coding is expensive.** Changing `k+m` means reading `k` and writing `n`; on tape that is
  brutal. Adapt **on access or at a tier transition** — re-code on the way down to tape — under a
  budget, never as an unbounded background sweep.
- **Key leases, not per-read quorums.** A quorum cannot run per stripe per location. The quorum
  authorises a scope; the reconstruction point receives a scoped, expiring key lease for that scope.
  This is the same reconciliation the agent-token section reaches from the other direction.


## Versioned reads, quorum-confirmed writes (owner direction, 2026-09-18)

The model: **an extract is a point-in-time versioned download.** Nothing is modified in place —
changes are *posted* as new versions, and that posting is how change is tracked across the system.
**Read is versioned; write is confirmed by quorum.**

This is the capstone of everything above, and it resolves several loose ends at once.

- **Backup stops being a separate feature.** Point-in-time recovery is just reading version *V*. The
  gap list in the backup section — no versions, no snapshots, no retention — is exactly what this
  fills.
- **Caches become trivially correct.** A memoised reconstruction of an immutable version can never go
  stale, so the distributed staging cache needs no invalidation protocol at all. That is a large
  simplification of the previous section.
- **Reproducibility comes free**, which is the point for agent consumers: a run cites
  (dataset, version), re-running reads the same bytes, and the provenance actually holds.
- **It dissolves the `STALE` state.** The demo hit exactly this defect today: an object went STALE
  because its source file was rewritten underneath it. That state only exists because the model is
  "one object tracks one mutable file". Rewriting a source is not a fault — it is a new version, and
  the old version remains valid and readable.
- **WORM stops being a constraint and becomes the enforcement.** Append-only is the model, and tape
  media enforces it in hardware.

### The substrate is already there

`IndexEngine` routes every state change through **one mutation path — commit, apply, journal,
replicate** — onto an append-only journal (`gfs-index.jsonl`) that a replica replays, with
`statehash`, `logsince` and `catalogdelta` already exposed for delta and reconciliation. That is a
versioned state machine already; what is missing is that versions are not *named and addressable* as
first-class objects. The write quorum likewise exists at the control plane: the coordinator set
elects an epoch-fenced leader from the shared RouteView under a majority quorum (2f+1).

### The one thing in the data model that blocks cheap versioning

A version is cheap only if v2 can point at the stripes of v1 that did not change — same fragments,
same holders, referenced rather than re-encoded and re-placed. That requires a stripe's ciphertext
and name to depend only on its content within a lineage, never on the object or position it was
promoted as. Today the encoder binds both to the object in four places:

| | where | effect on identical plaintext |
|---|---|---|
| fresh random DEK per promote | `DurabilityEngine` 163, `CryptoBox.newKey()` | different key, different ciphertext |
| random object nonce; IV = nonce ‖ stripe index | `DurabilityEngine` 164, `CryptoBox.stripeIv` 147–150 | different IV; same bytes at another position also differ |
| AAD = `objectId|s` | `DurabilityEngine` 85 | the tag authenticates object and position — a v1 stripe fails authentication under v2 |
| fragment id = `sha256(objectId|s|i|nonce)` | `DurabilityEngine` 81–82 | the stored *name* includes the object id and nonce; v2 cannot even ask for it |

Net: N versions cost N full copies, and on tape N full rewrites.

### The solution — lineage-scoped content addressing (specification)

The pattern is precedented, not invented: a keyed content hash under a per-domain secret is
Tahoe-LAFS's *convergence secret* and restic's per-repository content addressing. The constraints
that shape this instance are the federation plan's rejection of global convergent encryption
(equality leakage) and the defense hardening track's requirement for **FIPS/CNSA-approved crypto**.

**Data model**

- **Lineage** = `dataset_id`. Already the unit of `listobjects` filtering, of the DUA, and of the
  reciprocity ledger. Cross-lineage sharing is forbidden by design.
- `K_L` — one AES-256 DEK per lineage, wrapped under the site KEK exactly as today (`wrapKey`,
  `key_id`). Custody, quorum and the reconstruction token are unchanged.
- `K_mac = HKDF(K_L, "sid")` — the keyed-hash key. HMAC-SHA-256 and HKDF (SP 800-56C) are approved.
- **Stripe id** `sid = HMAC(K_mac, plaintext stripe)`. Computable only with the lineage key.
- **Stripe table** (index): `sid → { iv, k, m, shard_len, fragments[] , refs, leases }`. The IV is
  a **per-lineage 96-bit counter assigned by the index at registration** — the SP 800-38D
  deterministic construction (fixed field ‖ invocation counter), unique by construction. This is why
  plain AES-256-GCM suffices and AES-GCM-SIV (not NIST-approved) is not needed. The IV is *not* in the
  manifest and *not* derived from content or position.
- **Ciphertext** `AES-256-GCM(K_L, iv, aad = lineage_id, stripe)`. Order and position integrity move
  to the manifest, which is hashed and quorum-committed; the reader also verifies the whole-file
  `sha256` the manifest already carries.
- **Fragment id** `H(sid ‖ i)` — version-independent, so v2 references v1's fragments by the same
  name on the same holders. Fragments of a shared stripe are bit-identical across versions.
- **Manifest** `{ format, k, m, block_size, key_id, sha256, [sid…] }`; **version id = hash of the
  manifest**. A dataset version is a tree `rel → file manifest id`.

**Protocol**

- *promote(file, lineage, parent_version)*: compute `sid` for every stripe → **one**
  `registerstripes(lineage, [sid…])` → the index answers each `sid` with `exists` or a fresh `iv`,
  atomically through the existing commit → apply → journal → replicate path → encode only the new
  stripes → RS(k, m) → place under `H(sid ‖ i)` → commit the manifest against `parent_version`;
  reject if `parent_version` is no longer head (optimistic concurrency); quorum confirms.
- *read(version, range)*: manifest → the `sid`s covering the range → stripe table gives `iv` and
  holders → race `k` of `n` (already how `fetchStripe` works) → decrypt → verify.
- *gc*: a `sid` is collectable only when it has **no committed references, no leases, and expired
  retention**. In-flight promotes lease their `sid`s. GC is itself a quorum-committed mutation and,
  on tape, is batched by cartridge.
- *policy upgrade on a shared stripe* (v2 requires a tape copy v1 did not): reuse repair — any `k`
  holders regenerate fragment `j` for the new holder. No re-encode.

**Security properties, stated precisely**

- Equality is detectable only by a holder of `K_L`: inside a lineage, which is the fact the version
  history exists to record. Across datasets and tenants, identical data yields unrelated ids and
  ciphertext — the plan's objection to convergent encryption does not apply. The **price** is that
  identical data in two lineages is stored twice.
- **Per-version fragment authorisation is mandatory.** One key per lineage means an agent authorised
  for v5 holds the key for a stripe that v4 had and v5 redacted. A holder therefore serves a fragment
  only against a token naming a version whose manifest contains that `sid`.
- ~~**Dedup side channel.** "Does this stripe exist?" is an oracle for a writer without read rights.
  Return the `exists` hint only to writers who may read the lineage; write-only contributors always
  encode and upload, and the index dedups silently after commit (possible because the IV lives with
  the `sid`, not in the manifest). *Decision: read-gated hint, or always-silent dedup.*~~
  **RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`) — the open decision is moot because
  there is no existence query left to gate. This closes a security decision by deletion, which is the
  cheapest way to close one. The *separate* equality oracle created by storing a keyed plaintext
  digest on media (`SPECIFICATION.md` §12.2 D-1, §12.3) is **not** closed by this and is tracked
  there.
- **Key rotation is operational.** SP 800-38D caps a GCM key at 2^32 invocations; per-object keys
  never approached it, a lineage key will — 2^32 stripes ≈ 1 PiB at 256 KiB. Rotate on a stripe
  budget; sharing is lost only across the rotation boundary. *Decision: the budget.*

**Limits and migration**

- Stripes are fixed-size from offset 0, so an *insertion* inside a file shifts later stripes and
  defeats sharing within that file. Fine for append/add/replace; content-defined chunking is the
  escalation, at the cost of variable stripe geometry.
- `format` on `Manifest` discriminates. Old manifests decode exactly as today; no re-encryption. Old
  objects share nothing with new versions until re-promoted under the lineage key.

**Scope.** `CryptoBox` (HKDF); the four binding sites in the encoder and their mirrors in restore
(`DurabilityEngine` ~380–420); `IndexState` shapes 56–70 plus the stripe table; `registerstripes`,
refcounts, leases and GC in `IndexEngine`; `promote` gaining lineage and parent-version. Placement,
custody, transport and the dashboard do not change.

**Proof plan** (the standard the rest of GFS was held to): a versioned dataset where v2 changes 1 %
produces ≤ 1 % new fragments; the same file in two lineages shares zero ids; a v5 token cannot fetch a
v4-only `sid`; the 12/12 encode-geometry regression stays green; restore is bit-exact across versions.

### What else this needs

- **Batch the commits.** A quorum round trip per file serialises ingest. A version is a *set* of
  changes committed once, which also matches how agents write.
- **Optimistic concurrency.** Post a change against a parent version; if that parent is no longer the
  head, reject and make the client rebase. Simple, linearisable, and it matches "confirmed by quorum"
  without inventing a merge semantics.
- **Two quorums, deliberately not conflated.** The coordinator/index quorum makes a commit *durable
  and agreed*; an institutional approver quorum decides whether a change was *permitted at all*.
  These are different trust questions and should stay at different layers.
- **Garbage collection over the version DAG.** A stripe may be dropped only when no live version
  references it and no in-flight promote holds a lease on it. On tape that reclaim is a cartridge rewrite, so version retention should be grouped
  onto cartridges by retention class — the same grouping the backup section already argued for.


## Decisions from the research pass (2026-09-19)

External research answered Q1–Q5 and Q7 of `RESEARCH-PROMPT.md`; Q6 came back empty. Combined with
the Hugging Face **Xet protocol specification** (open, at `huggingface.co/docs/xet` with an
open-source client at `huggingface/xet-core`), the following are decided.

| # | Decision | Basis |
|---|---|---|
| D1 | ~~Lineage-domain key as the default key granularity, **as a per-lineage policy knob**~~ — **INVERTED 2026-09-19** by `eval/results/ckpt_dedup_results.json`: **per-object content keys are the default and the only mode.** Chunk-level content dedup measures zero on the dominant population, so the shared key it required buys nothing and the per-object crypto-shredding it cost is restored. This inverts the *content* key granularity only: `K_L` remains the lineage domain for wrapping and for `K_meta`, `K_mid` and `K_bnd`, on which no measurement here bears | research Q1, corrected; then refuted by measurement |
| D2 | ~~Redaction destroys **m+1 of n** fragments~~ — **RETIRED 2026-09-19**, see *Redaction resolved by key domains*: `auto_repair` (default true, 5 s `repairSweep`) regenerates the destroyed fragments from k survivors with no key and no approval, faster than 50 sites can destroy them | refuted by design pass |
| D3 | Chunk index is an **LSM store (RocksDB-class), sharded by hash prefix, Bloom filters** | research Q2 |
| D4 | GC is **epoch-based mark-and-sweep with leases — not reference counting** | Borg 1.x → 2.0 |
| D5 | ~~**Content-defined chunking**~~, chunks packed into xorbs; ~~erasure-code the xorb~~ — **SPLIT 2026-09-19**: CDC retired for content, packing retained; and the xorb is **not** the erasure unit (`SPECIFICATION.md` §3 codes parcel/band/fragment/stripe) | Xet spec; then measured |
| D6 | ~~**Sampled** global dedup queries, ~1 per 4 MB~~ — **RETIRED 2026-09-19** by `eval/results/ckpt_dedup_results.json`; its only table, `dedup: sid -> xid`, is struck with it | Xet spec; then refuted by measurement |
| D7 | Versioning uses **Iceberg-style three-tier manifests**, not git trees | research Q3 |
| D8 | Agents never commit directly: ephemeral branches + a single-writer merge service | research Q3 |
| D9 | Tape uses **two-phase async recall**: VSN grouping, serpentine sort, single-pass to NVMe stage | CTA / HPSS / Enstore |
| D10 | ~~**Hierarchical LRC**~~; **ordinary repair must never require a tape mount** — **SPLIT 2026-09-19.** The second clause is adopted and implemented as the local intra-volume band (`SPECIFICATION.md` §8.1, §8.6). The first clause is **deleted** by `SPECIFICATION.md` §15 and only **deferred** by `ENTAIL-AGENT-NATIVE-FS.md` §13; those two positions are incompatible and both are currently live. One must win before placement is built — recorded as *Unresolved* 12, not resolved here | research Q5 |

### D1 corrected — the constraint is scale, not mathematics

The research concluded that sub-domain shredding is "mathematically incompatible" with cross-version
deduplication under FIPS/CNSA. Its own comparison contradicts that: key-per-chunk **is** FIPS-approved
and **does** give per-chunk shredding — it fails on metadata explosion (~10⁹ keys per PB), which is an
engineering limit, not an impossibility.

So the decision is contingent rather than global. ~~**Lineage keys are the default; a lineage may be
flagged high-redaction-risk and keep per-object keys, forgoing deduplication within it.**~~ A single
clinical study under an active consent-withdrawal regime is small enough that per-object keys cost
little, and that is exactly where fine-grained shredding is worth paying for.

> **D1 INVERTED 2026-09-19** by `eval/results/ckpt_dedup_results.json`. **Per-object keys are the
> default. The dedup they were said to forgo has been measured at zero** — adjacent checkpoints share
> 0 of 184,044 64 KiB weight blocks, distant 0, the two weight copies inside one checkpoint 0, and the
> cross-run control 0 — so there is no trade left to make and no knob to expose.
>
> Note the scope precisely. What measures zero is *chunk-level* dedup. *Whole-file* reuse across
> versions measured 13.4–47.9% (`eval/results/cdc_measure.json`) and is unaffected: an unchanged file
> is the same object under the same key. The scale argument that made D1 correct at the time —
> ~10⁹ keys per PB at chunk granularity — does not apply to per-OBJECT keys, which are ~10⁶ per
> lineage. And note what the paragraph above still gets right and keeps: the research's
> "mathematically incompatible" claim was and remains wrong; the constraint was always engineering
> scale, and the measurement removed the scale rather than refuting the mathematics.

### D2 — erasure coding makes redaction cheaper than the research assumed  
> **RETIRED 2026-09-19.** The argument below is wrong and is kept only as a record. Destroying
> `m+1` fragments is undone within seconds by `auto_repair`'s 5 s `repairSweep`, which
> regenerates any DEGRADED object from any `k` survivors needing neither key nor approval — a
> stable attractor, not a race. It is also impossible in place on WORM, and because a xorb packs
> ~1024 chunks from ~64 files, one destruction takes out 500–1,500 unrelated subjects. See
> *Redaction — resolved by key domains, not by destroying fragments*.

The research recommends an asynchronous physical compaction pass: copy surviving chunks to fresh tape
extents, decommission the old media. Correct, but it treats the store as generic. Because every stripe
is `k`-of-`n` coded, **a stripe becomes unreconstructable once more than `m` of its fragments are
destroyed.** Redaction therefore requires compaction at only `m+1` of `n` sites — chosen for whichever
have a compaction pass due soonest — rather than at all `n`. On tape, where compaction is a
whole-cartridge rewrite, that is a large saving, and it degrades safely: any site that fails to
compact cannot resurrect the data alone.

### D5 — chunking and packing, adopted from Xet

> **D5 SPLIT 2026-09-19.**
>
> *Chunks as a deduplication unit:* **RETIRED** (`eval/results/ckpt_dedup_results.json` — zero
> cross-object sharing), and *content-defined* chunking is retired for content with it
> (`eval/results/cdc_largefile.json` — CDC is −0.12 to −0.15% on append and −5.04% on scattered
> in-place overwrite, exactly the mutation profile of a weight update). Content is chunked at fixed
> 64 KiB, for packing and integrity granularity only. **Stated because it is the cost of this
> retirement and must not be omitted:** on the same harness CDC *wins* enormously where boundaries
> shift — +99.75% on a 0.1% prepend, +49.85% on a middle insertion, against fixed-size chunking's
> 0.1% and 49.99%. Retiring CDC for content forgoes that on any content population that prepends or
> inserts; no such population has been measured, and this is a real advantage given up on a reasoned
> bet, not a measured zero. CDC survives in the metadata layer, where sorted runs make insertions
> ordinary.
>
> *Xorbs as the packing and transfer unit:* **RETAINED, and independently re-justified.** Their basis
> was never dedup: it is mount economics, and the plant simulation confirms it — batching plus
> media-ordering is worth 9.4× in GB per drive-hour on a clustered workload (69.5 → 653.3
> `eval/results/plant_sim.json`), and co-occurrence clustering is worth 3.8× on top of batching. The
> contiguity bias below, and the pin-amplification arithmetic `1-(1-p)^1024`, are consequences of
> packing and survive untouched.
>
> *The xorb as the ERASURE unit:* **superseded** by `SPECIFICATION.md` §3. The coded quanta are
> **parcel** (exactly 1 GiB; padding unit and local erasure symbol), **band** (32 parcels = 28 data +
> 4 local parity), **fragment** (96 parcels contiguous on one volume; global erasure symbol and read
> unit) and **stripe** (2 data + 1 parity fragment, one per site). A xorb is opaque payload carried
> *inside* parcels; `place` resolves `xid -> {stripe_id, frag_i, parcel_ordinal, offset, len}`.

Fixed-size stripes from offset 0 were a stated limitation: an insertion inside a file shifts every
later stripe and defeats sharing. **Content-defined chunking removes it** — GearHash rolling-hash
boundaries are content-derived, so an edit changes only local chunks. Xet targets 64 KB chunks
(8–128 KB range).

Chunks are the *deduplication* unit; **xorbs** (≤64 MB, ≤8192 chunks) are the *storage and transfer*
unit, with files reconstructed as (xorb, offset range). We adopt both levels and **erasure-code the
xorb, not the chunk** — which keeps fragment counts manageable and gives tape large sequential objects
instead of 10⁹ small ones.

**Our fragmentation bias must be far stronger than Xet's.** They already skip available dedup to keep
runs of ≥8 chunks (~1 MB) contiguous in one xorb, because scattering slows reads. For us a scattered
read is not a seek, it is **a tape mount**: the difference between a restore costing one mount or
fifty. Contiguity should be weighted by the tier a xorb is destined for.

### D6 — sampled global deduplication

~~Xet makes only a sampled subset of chunks eligible for a global dedup query (`hash % 1024 == 0`,
recommended ~1 query per 4 MB), and a hit returns a shard describing *neighbouring* chunks, which the
client caches. This cuts global index QPS by roughly three orders of magnitude and is the single most
useful idea for our Q2 scale problem.~~

> **RETIRED 2026-09-19 by `eval/results/ckpt_dedup_results.json`.** The sampled global dedup query
> exists to make cross-object content deduplication affordable at federation scale. Measured on a
> real SFT run, adjacent checkpoints share **0** of 184,044 64 KiB weight blocks, distant checkpoints
> 0, the two weight copies inside one checkpoint 0, and the cross-run control 0 — which is what shows
> the measurement discriminates rather than being broken; optimizer state shares 0.0020% excluding
> zero blocks. There is no cross-object sharing to query for. The sampling scheme, the
> neighbouring-chunk shard, the client-side shard cache and the `registerchunks` RPC are all retired
> together. Kept as a record: the idea was sound and the arithmetic was right; the population it was
> aimed at does not deduplicate. The Q2 scale problem it was aimed at is dissolved rather than
> solved — see *Blockers* 1.

### Where Xet does *not* help us

Xet's global deduplication protects chunk hashes with an HMAC key, but the specification is explicit
that the property obtained is **anti-enumeration, not anti-confirmation**: a client that holds the
plaintext still learns whether the chunk exists in the system. Hugging Face also operates as a trusted
central party holding raw hashes. Our threat model — blind holders, no trusted operator, equality
leakage across institutions a stated hazard — is stricter, so the lineage-keyed `sid = HMAC(K_L, chunk)`
of the specification above stands: a service that lacks `K_L` cannot compute `sid` at all.

> **NARROWED 2026-09-19.** The rebuttal was about how to operate a global dedup *service* under a
> stricter threat model. There is no global dedup service (`eval/results/ckpt_dedup_results.json`), so
> the comparison is historical. What still stands, and is the only live use of a keyed hash here, is
> keyed addressing in the **metadata** layer — `cid = HMAC(K_mid, canonical body)` for cnodes and
> `HMAC(K_bnd, …)` for run boundaries, where CDC is retained and earns. Whether a content-derived
> chunk id should exist at all for DATA is now an open question, because dedup was its only consumer;
> see `SPECIFICATION.md` §12.2 D-1 and *Unresolved* 13. (Noted in passing, not fixed here: this line
> writes `sid = HMAC(K_L, chunk)` while the commit procedure and `SPECIFICATION.md` §12.3 write
> `HMAC(K_mac, chunk)`.)

### Interface shape

The Hugging Face Hub model — a repository per dataset, a revision, `resolve/{revision}/{path}`, scoped
tokens, and gated repositories requiring terms acceptance — is a strong fit for the versioned reads
and DUA gating described above, and is an API agents already speak. It supplies no deferred-access
semantics; those come from S3 Glacier's `RestoreObject`, as set out earlier. The two front ends are
complementary: **Hub-shaped for versioned dataset access by agents and researchers, S3-shaped for bulk
and deferred retrieval by backup products.**

### Still open after this pass

- **Q6 (agent capability tokens) returned nothing** — macaroons, Biscuit, UCAN, SPIFFE/SPIRE, GA4GH
  Passports and DRS remain unexamined. This blocks the token design.
- **Q7** produced an attested-enclave flow (TDX / SEV-SNP quote verification → custody quorum →
  ephemeral key release) but no prior art for a federation of independent institutions.
- **Unverified numbers**: the restic OOM figures (16–64 GB at >10⁷ blobs) and the ZFS RAM-per-TB
  claims carry no citation in the returned source list, which contains only Data Domain and Borg
  references. Confirm before either is used to size anything.

## Protocol decision, and the spike that settled it (2026-09-19)

**Decision: ~~S3 for bytes~~, Iceberg-shaped manifests for dataset versions, our own protocol only for the
federation control plane.**

> **~~S3 for bytes~~ SUPERSEDED 2026-09-19 by `SPECIFICATION.md` §9.1 and §9.3.** The only
> byte-moving verb is `realise`, admitted against Coverage, Pledge, Plant and Policy; `S3` is one of
> several **consumer-side adapters over `VIEW`, shipped as reference code we publish and do not
> operate**, and §15 deletes any object-store API on the medium. Iceberg-shaped manifests and the
> quorum index as catalogue are unaffected. The consequence for enforced retention is recorded as
> *Unresolved* 14.

### Why not our own data protocol

A protocol is worth what speaks it. Our consumers are AI agents and backup products, and both already
speak S3 fluently. More decisively, the problem that disqualifies every alternative — most data sealed
until explicitly activated — is the problem **S3 already solved**, because Amazon has it too:

| our access axis | S3 |
|---|---|
| `SEALED` | `x-amz-storage-class: DEEP_ARCHIVE` |
| activation request | `POST /key?restore` with `Days` and `Tier` |
| `THAWING` | `x-amz-restore: ongoing-request="true"` |
| read a sealed object | `403 InvalidObjectState` |
| `AVAILABLE` under a lease | restored copy, expiring after `Days` |
| predicate-based bulk activation | S3 Batch Operations over a manifest |

Add Object Lock for WORM retention. Unlike the Hub API, S3 is a frozen de-facto standard with many
independent server implementations.

### Versioning: S3 has no dataset version, and that is correct

Bucket versioning is a toggle, not a number; it yields an opaque per-object `versionId`. There is no
consistent "bucket as of T" — approximating one is an O(all objects) scan and is not atomic. Object
stores deliberately omit multi-object transactions, so **the dataset version belongs one layer up, as
a manifest object**. Iceberg (metadata file → manifest list → manifest files, unchanged manifests
reused *by reference*), Delta Lake (an ordered commit log) and LakeFS (explicit branches and merges)
all do exactly this.

The crux is where atomicity lives. Cloud implementations swap a catalog pointer using S3 conditional
writes (`If-None-Match: *`, which replaced the DynamoDB lock) or an ETag-conditional update. **We need
neither: the quorum-confirmed index is the catalog**, and a pointer swap becomes a quorum commit
across institutions — strictly stronger than a single-region CAS, and exactly the "write confirmed by
quorum" the design calls for. They use CAS because they have one operator; we have fifty.

    dataset version  = manifest identity, named by the quorum index      <- ours
    manifest tiers   = Iceberg-shaped, unchanged manifests by reference  <- borrowed
    immutable bytes  = S3 objects, Object Lock, Glacier classes          <- borrowed

Take Iceberg's *structure* but not its table semantics (it is built for schemas and partition
pruning; we want the reference-reuse and the snapshot log over a file tree), and LakeFS's *branch*
concept for D8. One simplification falls out: because content is addressed by `sid` and never
overwritten, **S3 object versioning is redundant for us** — versioning comes entirely from the
manifest layer.

### What stays ours

Quorum-confirmed writes across independent institutions; the reciprocity ledger; Shamir *t*-of-*n*
custody and approval quorums; placement and survivability policy with explicit refusal; tape-ordered
activation planning across sites; and per-request attenuable, purpose-bound tokens. Nothing existing
has a word for these, because nobody else has this problem. The API should be *small*, precisely
because everything expressible in S3 stays in S3.

### The spike: measured, not argued

`eval/hf_gateway.py` is a Hugging Face Hub-compatible read endpoint over the live GFS index (467
files, index sequence 12), used to test whether the official client can talk to us and how it behaves
on sealed content.

| case | result |
|---|---|
| ACTIVE file | `huggingface_hub` 1.32.0 downloaded **268,435,456 bytes** unmodified, via `HF_ENDPOINT` alone |
| SEALED, server answers `404` | `LocalEntryNotFoundError` — *"check your connection…"* |
| SEALED, server answers `403` | `LocalEntryNotFoundError` — **identical message** |
| SEALED, server answers `503` + `Retry-After: 900` | `LocalEntryNotFoundError` — **identical again** |

The read path genuinely works. But the sealed result is worse than the protocol-gap argument
suggested: **the client erases the distinction.** The `503` case is the decisive one — it is the only
status with standardised *"unavailable, retry after N seconds"* semantics, it was sent with
`Retry-After: 900`, and it too came back as the same generic error. Every status code, and the custom `X-Gfs-State:
SEALED` header, collapse into one generic connectivity error, and an agent hitting cold data is told
to check whether its internet connection is on. Cold content therefore cannot be surfaced through
this protocol at all — not awkwardly, not with a custom header, not with a cleverer status code.

**Conclusion: the Hub surface is a convenience view over already-activated data, never the protocol.**
Activation stays out of band and S3-shaped.

Incidental protocol details the spike surfaced: dataset repos carry a `datasets/` path prefix on
`resolve` that model repos do not, revisions arrive as `main` rather than a sha, and `HF_ENDPOINT`
fails silently unless it is set before `huggingface_hub` is imported.

## Dataset versioning and extracts — final specification (2026-09-19)

Supersedes the sketch in *Versioned reads, quorum-confirmed writes* above. Written after four
independent designs were attacked from a scale lens, a concurrency lens and a tape/GC lens, and
scored. The run-structured design won; the Iceberg, Delta-log and Merkle-tree designs contributed
the grafts marked below. Every fatal and serious finding raised against any of the four is either
resolved here or recorded in *Unresolved*.

### The model

A **dataset version** is a small, quorum-committed `VersionRoot` naming an ordered list of
immutable, content-addressed **runs** — sorted, seekable shards of file entries — so a commit
writes one new run plus one ~6 KB root and references every unchanged run by name, making a commit
O(changed files) and O(1) quorum rounds at any dataset size; shadowing is "highest `rseq` wins",
which is LSM read semantics and is why no tree node is ever rewritten on change. An **extract** is a
separate first-class object — an immutable, quorum-notarised, retention-pinned *selection* over
exactly one version — and it, not the dataset and not the version, is the unit of citation,
activation, byte budget, audit subject and GC rootship. The index holds only lineage heads, branch
leases and pinned extracts (kilobytes per lineage, replacing the measured 1811 MB of in-heap
`DatasetRec.files` at 10^6 files); the catalog body lives as encrypted, erasure-coded objects on a
never-sealed tier; the authoritative chunk→offset map lives *inside each xorb*, so neither the read
path nor the GC mark path ever consults a global chunk table — which retires blocker 1 rather than
deferring it.

### Prerequisites — substrate defects that gate all of this

These were found by reading `IndexEngine` rather than the design. None is caused by versioning; all
of them become data-destroying rather than merely annoying once a journal entry is a citation. They
land **before** any versioning code.

| P | Defect (verified in source) | Required fix |
|---|---|---|
| P1 | `commit()` applies in memory *first*, then writes the journal inside a `try/catch` that only logs the error and falls through returning the entry as committed; the writer is a `BufferedWriter` with `flush()` and there is **no `fsync` anywhere in the plugin**. A power loss discards acked commits; on restart `seq` rewinds and the same numbers are reissued to different entries. | Journal → `FileChannel.force` → apply → ack. A journal write failure is **fatal to the index**, not a log line. `replay()` aborts startup on a parse failure instead of swallowing it and appending past a torn line. **Priced 2026-09-19** (`eval/results/fsync_cost.json`): `FileChannel.force` costs **0.737 ms per call on Linux node-local storage**, per-call and not per-byte — roughly 1,350 forced commits/s from one thread, before group commit. Two cautions. Do not size this from a macOS measurement: `force(true)` maps to `F_FULLFSYNC` there and measures 6.14 ms, ~8× pessimistic. And on a shared filesystem the same call measures ~29 ms with throughput at 8.1–8.8 MB/s regardless of the barrier, so an index journal placed there is priced 40× differently. |
| P2 | Sequence numbers are reusable after a rewind; `applyShipped` requires `e.seq == seq+1` and returns false forever; `catchUp` breaks out silently when `primarySeq <= seq`; nothing ever calls `stateHash` on a schedule. | Entries carry a monotonic **term** persisted with `seq`. A replica refuses `(term, seq)` it has seen with different bytes and raises an alarm. A scheduled `stateHash` comparison against each replica, with divergence forcing a snapshot install. |
| P3 | `installSnapshot`, `dumpState` and `stateHash` each enumerate a **hard-coded five-map whitelist** (`nodes, datasets, projects, objects, custody`). Any new resident map silently escapes both replication and the convergence check — the hash certifies the divergence as healthy. `installSnapshot` also deletes the journal and writes only a marker, so that journal can never rebuild state. And `start()`'s post-snapshot reset is guarded by `!primary`, so promoting a replica yields a high `seq` beside post-snapshot-only state. | One **state registry** that all three iterate, so a new record type cannot be forgotten. Snapshot transfer becomes paged/streamed (cursor over lineages, chunked `MsgEvent`s) — the single `GSON.toJson` String has a hard 2^31-1 ceiling that these records reach. `stateHash` becomes an incremental Merkle accumulator maintained in `apply()`, not a whole-state re-serialisation under the monitor. Promotion of a replica is an explicit, journaled act that re-derives state or refuses. |
| P4 | `apply()` ends `case "audit": default: break;` — an unknown entry type is ignored while `seq` still advances. Across ~50 independently operated institutions a rolling upgrade is the steady state, so one stale node serves stale refs and, if it owns a GC mark shard, emits a short MarkSet *consistently in both epochs*, defeating the two-epoch rule and the Object Lock backstop at once. | `apply()` **fails closed**: an unknown type halts that node and it refuses to serve reads. Entries carry `fmt` (format version); catch-up checks a minimum-supported version. A mark shard publishes the set of entry types it understood alongside its MarkSet; the sweep refuses a MarkSet whose capability set is behind the epoch's. |
| P5 | `wrapped_dek` is written **verbatim into the append-only journal** by the `object.manifest` payload, retained in heap, shipped to every replica by `dumpState`, and the catalog-DR proposal would write it to WORM. Zeroing the field at head shreds nothing. | Key material never enters the journal, `dumpState`, `stateHash` or any WORM snapshot. The journal carries a **key handle**; wrapped keys live in a separately managed, compactible **key store** with a real delete path, keyed by `object_id` rather than by `(lineage, rdom)` (see *GC and redaction*). *(2026-09-19: **P5 is unaffected by the measurement** — this is a rename of the store's key, flagged so that a `K_rdom` sweep does not remove a live requirement. Key material still must never enter the journal, `dumpState`, `stateHash` or any WORM snapshot, and zeroing a field at head still shreds nothing.)* |
| P6 | `promote()` holds `synchronized(this)` across a 15 s blocking RPC, and every read (`resolve`, `listFiles`, `listObjects`, `objectStatus`) takes the same single global monitor — measured at 5397.7 resolves/s, p99 0.4 ms. A WAN quorum round on that monitor makes the commit ceiling federation-wide rather than per-lineage, and a 25 s stall marks every node LOST (`lost_ms=25000`, sweep every 2 s) and launches a fabric-wide repair storm. | No RPC under the index monitor, ever. The monitor is striped per lineage. `livenessSweep` reads `last_seen` from a volatile field updated outside the lock, so a mutation stall can never manufacture LOST. |
| P7 | `BlockStore.get(String fragId)` returns the whole fragment as `byte[]`; `delete()` is an unconditional `Files.deleteIfExists` with no lease, lock or retention check; `scrub()` iterates the store's **own** rebuilt inventory, so a fragment deleted at a live holder is never reported, and `derivedState` counts a fragment present whenever its node is UP and `fr.st == "OK"`. | Add `get(fragId, off, len)` (tape-class stores answer it by staging the whole fragment, as they must anyway) and a `retain_until` field whose presence makes `delete()` refuse. Add sampled **proof-of-possession** on cold fragments (below). |

### Structures

Three places state lives: the journaled index heap (small, O(lineages + branches + pinned
extracts), never O(files)); immutable **cnodes** on the catalog tier; and the xorb itself, which
carries its own chunk table.

**Identifier rule, applied without exception.** An object's id is a keyed hash of **its own
canonical bytes**, never derived from a property of the thing it describes. (This is the rule whose
violation — an id derived from the described file's content digest — put two different objects at
one address in the Iceberg design and produced the cleanest same-id-different-bytes path found in
the whole exercise.) Ids are stored in the index as raw `byte[16]`, not 32- or 64-character hex
Strings: ~3.5× heap saving on every record below.

#### Keys

    K_L      per-lineage AES-256 key, wrapped under the site KEK, Shamir t-of-n custody (unchanged)
    K_mac    = HKDF(K_L, "sid")        chunk ids:      sid  = HMAC(K_mac, chunk)
    K_meta   = HKDF(K_L, "meta")       cnode encryption
    K_mid    = HKDF(K_L, "mid")        cnode ids:      cid  = HMAC(K_mid, canonical body)
    K_bnd    = HKDF(K_L, "bnd")        run boundary function (graft, below)
    ~~K_rdom   per REDACTION DOMAIN, random, wrapped under K_L, stored only in the shred store~~
    ~~         chunk encryption key = HKDF(K_rdom, "chunk" || sid)~~
    K_obj    per OBJECT, random AES-256, wrapped under K_L, stored only in the key store
             chunk encryption key = K_obj directly; no derivation step

> **RETIRED 2026-09-19** — `eval/results/ckpt_dedup_results.json`. `K_rdom` and the
> `HKDF(K_rdom, …)` chain existed so that chunks shared by deduplication could be shredded despite
> the sharing. Measured sharing on the dominant population is exactly zero — adjacent weight
> checkpoints 0 of 184,044 blocks, distant 0, the two weight copies inside one checkpoint 0, the
> cross-run control 0 (the control discriminates), optimizer state 0.002% excluding zero blocks — so
> there is no shared key and no problem to solve. **The redaction domain is not deleted: it stops
> being a key and becomes a catalogue-side label naming the set of object keys destroyed together.**
> Everything below that reads `K_rdom` as a KEK is retired; everything that reads `rdom` as a
> governance unit stands. `K_mac`, `K_meta`, `K_mid`, `K_bnd` and `K_L` itself are untouched.
>
> **CORRECTION REQUIRED ELSEWHERE, caused by this line.** `SPECIFICATION.md` §12.4 currently states
> that "chunk data is encrypted under per-chunk keys with one GCM invocation each, so the SP 800-38D
> invocation cap is not the binding constraint." With one key per object that sentence becomes false:
> a 12.06 GB weights object is 184,044 GCM invocations under a single key. The conclusion (rotation
> driven by custody membership change) is probably still right — 1.8×10⁵ is far below any NIST bound
> — but the *stated reason* no longer holds and must be recomputed, not carried forward. Flagged,
> not resolved here.

#### Index-resident records (new in `IndexState`, same public-field Gson idiom)

    LineageRec                         // one per dataset_id; replaces DatasetRec.files for v1 lineages
      String  id, key_id;  int key_epoch;
      long    head_v;      byte[] head_vid;      long head_seq, head_term;
      long    version_count, file_count, byte_count;
      int     k, m, chunk_avg;  String pack_policy;   // "locality" | "dedup"
      // ~~boolean high_redaction;~~  ~~String rdom_rule;~~  -- RETIRED 2026-09-19
      //   (eval/results/ckpt_dedup_results.json): per-object keys are unconditional, so there is no
      //   granularity to select and the knob has nothing to trade. What is retained is a NON-KEY
      //   field naming the consent unit, used ONLY to group object keys for a single destroy:
      String  consent_unit;                            // "subject" | "<field>"; no cryptographic
                                                       // meaning, changeable at any time, because
                                                       // changing it changes which keys are
                                                       // destroyed together, not how anything was
                                                       // encrypted
      long    gc_epoch;  long shred_epoch;
      Map<String,BranchRec> branches;
      Map<String,byte[]>    tags;                      // human tag -> vid
      // NOTE: no `moves` map. Physical location is LSM-resident (see below).

    BranchRec
      String name, owner, kind;         // main | agent | publisher | merge
      long   head_v, base_v;  byte[] head_vid;
      long   opened, expires;           // expires IS the write lease: one record per writer
      int    pending_runs;

    ExtractRec                          // ~350 B resident with raw byte[16] ids
      byte[] extract_id;  String lineage;  long v;  byte[] vid;  long index_seq;
      byte[] cert_cid, enum_cid, xorbset_cid;
      byte[] root_pub;                  // salted redactable Merkle root (see Extracts)
      long   file_count, byte_count, chunk_count, pin_bytes, pin_xorbs;
      String pin_class;                 // "cite" | "run" | "scratch"
      long   pinned_until;              // 0 = indefinite (cite only)
      String state;                     // RESERVED | PINNED | RELEASED | EXPIRED | PARTIALLY_REDACTED
      byte[] parent_extract;            // for derived extracts
      String issued_to, purpose, token_id, idem_key;
      long   created;                   // == ts of the extract.pin entry, NOT wall clock at mint
      // signatures are NOT here: they live in the cert cnode. Carrying 34 x 128-char sigs in heap
      // is what made a 500 B estimate a 6 KB record and put dumpState against the String ceiling.

    ActivationRec
      String job_id;  byte[] extract_id;  String lineage, requested_by, token_id, purpose;
      String state;                     // PLANNING | QUEUED | THAWING | PARTIAL | READY | EXPIRED | FAILED
      byte[] plan_cid;
      long   wave_frontier;             // O(1) readability: highest fully-AVAILABLE wave ordinal
      long   xorbs_total, xorbs_ready, bytes_total, bytes_ready, bytes_delivered;
      long   undeliverable_files;  byte[] undeliverable_cid;
      long   created, deadline, lease_expires;

    GcEpochRec
      String lineage;  long epoch;  String phase;      // OPEN|MARKING|MARKED|SWEEPING|DONE|ABORTED
      long   mark_start_seq;                            // root set frozen HERE, not at a wall clock
      List<String> roots;  List<String> shard_caps;     // entry types each shard understood (P4)
      long   runs_expected, runs_marked;                // mark is fail-closed on inequality
      byte[] live_set_cid, candidate_cid;
      long   marked_xorbs, candidate_xorbs, swept_xorbs, reclaimed_bytes, blocked_by_lock;
      List<String> sweep_sigs;

    RedactionRec                        // the only irreversible act besides sweep
      String lineage, rdom;  long ordered_seq, executed_seq;
      String authority, approver_set;   // e.g. "IRB-2026-114"; institutional quorum, not the index quorum
      long   files, bytes, xorbs_touched;
      List<String> sigs;                // dated, signed attestation; survives the data

#### LSM-resident tables (D3; sharded by id prefix, Bloom-filtered, **not** in heap)

    xorb:   xid -> { k, m, shard_len, chunk_count, created_seq, created_term,
                     obj_set (roaring), state: OK|REDACTED, tier: DISK|TAPE }
    place:  xid -> { stripe_id, frag_i, parcel_ordinal, offset, len,
                     created_seq, created_term }        // see SPECIFICATION.md 8.3
    loc:    stripe_id -> Locator[3]                      // MUTABLE. The only table a generational
                                                         // migration writes.
    lease:  branch -> xid set       (write leases: one per branch, never per chunk)
    keys:   (lineage, object_id) -> wrapped K_obj, key_epoch, state: LIVE|SHREDDED, shredded_seq
            plus an index (lineage, consent_unit) -> object_id set, for destroy-together
    ~~shred:  (lineage, rdom) -> wrapped K_rdom, key_epoch, state: LIVE|SHREDDED, shredded_seq~~
    ~~dedup:  sid -> xid              // SAMPLED ONLY, sid % 1024 == 0 (D6); a rebuildable cache~~

> **Three changes, 2026-09-19, all dated and none silent.**
>
> 1. **`dedup: sid -> xid` RETIRED** (`eval/results/ckpt_dedup_results.json`). It was the sampled
>    cross-object dedup cache and had exactly one consumer, the D6 probe; measured sharing is
>    0.0–0.6%. Removing it removes no integrity check: the authoritative chunk→offset map already
>    lives *inside each xorb*, per-chunk AEAD still authenticates every chunk, and `leaf_root` still
>    detects media error. **Decision row D6 above carries the same dated retirement**, or the
>    decisions table would certify a mechanism whose only table has been struck.
> 2. **`shred` becomes `keys`, keyed by object.** `K_rdom` is retired; the row count goes from ~50
>    rdoms per lineage to ~10⁶ objects, and **that scale change is NOT absorbed here** — it is the
>    unpriced HSM/destroy-handle volume recorded as a hole at `SPECIFICATION.md` §12.4. The ~10⁶
>    figure is this document's own estimate (see *What this deletes*), not a measurement.
>    The `xorb` row's `rdom_set` becomes `obj_set` and **inherits the `SPECIFICATION.md` §7.1 scale
>    hole**, since it is the same set that sizes the on-media index.
> 3. **`place` and `loc` are restated to `SPECIFICATION.md` §2.2 and §8.3.** `loc` previously read
>    `xid -> { site -> (vsn, tape_position) }`, which puts a cartridge volume-serial and a serpentine
>    position into a table at the object layer. **No layer above the block plane ever records a
>    physical position** — that is what makes a generational migration a row swap that invalidates no
>    citation, manifest, extract certificate or receipt. A `Locator` is the 56-byte
>    `{volume_id, ordinal, parcels, code_epoch, leaf_root}` of `SPECIFICATION.md` §4; VSN and tape
>    position are not in it and are joined at activation time from the ~10³-row volume registry.

`place` and `loc` are separate tables deliberately: a lease extension or a cartridge migration must
touch a small mutable row, never an immutable 300 KB chunk index. This is the one-line fix to the
"5.8 TB of LSM writes for one lease extension" break.

#### Cnodes (immutable, content-addressed, on the catalog tier)

    ManifestRun  "gfs-run/1"   -- a sorted, immutable run of FileEntries; the unit of sharing
      header  magic | fmt | lineage | n | lo (min rel) | hi (max rel) | index_off | bloom_off
      bloom   24 bits/key over rel        <- NOT 10. See Scale limits: a false positive costs a run read.
      ents    prefix-compressed sorted entries, 4 KiB frames, restart index every 64 entries
      FileEntry  rel | flags (TOMB|EXEC|LINK|EXTERNAL_SPANS) | size | sha256 (plaintext, whole file)
                 | mtime | rdom | nspans | spans[]  OR  span_root (if EXTERNAL_SPANS)
      Span       { xid (16 B GLOBAL), cidx, nchunks, bytes }        <- global xid, not a run-local slot
      // NOTE: the run carries NO xorb table. rseq is NOT in the body.

    XorbSet      "gfs-xset/1"  -- one per run: the deduplicated, sorted xid set the run references
      { run_cid, n, xids[16 B] , bytes_per_xid }        ~28 B/xid

    SpanIndex    "gfs-spans/1" -- offset-keyed second tree, for files above 4096 spans
      root: [ { lo_off, hi_off, seg_cid, nspans } ]   segments of <= 64 K spans, sparse tail index

    VersionRoot  "gfs-version/1"  -- THE dataset version; a few KB at any dataset size
      lineage, v, parent_v, parent_vid, branch, term, seq, ts, by
      runs: [ { cid, xset_cid, lvl, rseq, min_rseq, max_rseq, lo, hi, n, tomb, bytes } ]
      fc, bc                     // exact materialised file/byte counts after shadowing
      ux_hll_cid                 // sidecar, NOT inline: a dense HLL is 12-16 KB x 9 voters per commit
      cd                         // = merkle(runs[] canonical) ; what the quorum signs
      cod: { k, m, chunk_avg, key_epoch, fmt }
      cmp                        // vid this is a pure compaction of, or null

    ExtractCert  "gfs-extract/1" -- immutable, signed, self-describing; what a paper cites
      extract_id, lineage, v, vid, index_seq, term, pin_class
      selector: { grammar_v, kind, expr, seed?, limit?, order }      // closed grammar, see Extracts
      resolved: { file_count, byte_count, chunk_count, xorb_count, pin_bytes, amplification }
      root_pub, leaf_salt_cid, enum_cid, xorbset_cid, plan_cid
      codec, retention, quorum: { epoch, threshold, signers[], sigs[] }

    ExtractEnum  "gfs-enum/1"    -- SELF-CONTAINED. Inlines the reconstruction recipe.
      entries sorted by rel: { rel, size, sha256, rdom, leaf_salt, spans[] | span_root }
      // Spans are INLINED here rather than referenced through the version tree. This is the fix for
      // "you keep the bytes and the xorb set and collect the map" -- the single worst-shaped failure
      // found in the exercise, undetectable at pin time and surfacing once, years later, at the
      // moment a citation is exercised. ~3 MB extra for a 10^4-file extract. Pay it.

    ActivationPlan "gfs-plan/1"
      waves: [ { lo_ord, hi_ord, xids[] } ]      // LOGICAL xids only; no VSN, no tape position

#### Xorb wire format (the erasure-coded unit; <= 64 MB, <= 8192 chunks)

    [ "GFSX" | ver u8 | key_epoch u16 | iv_base 12 B | ehdr_len u32 ]        cleartext preamble
    [ GCM(K_meta, iv_base, aad = lineage|xid|"h")
        { n, sids[n] 32 B, offs[n], lens[n], obj_ids[n] } ]                  encrypted chunk table
    [ per chunk i:  GCM( K_obj[i], iv_base+1+i,
                         aad = lineage|xid|i )  chunk bytes ]                PER-CHUNK AEAD
    ~~then RS(k,m) over the whole thing; fragment i at H(xid || i)~~; Object Lock, Glacier class.
    xid = HMAC(K_mac, sid_0 || ... || sid_{n-1})

> **Two dated changes, 2026-09-19.**
>
> **(a) The key chain.** `rdoms[n]` becomes `obj_ids[n]` — a like-for-like rename at the new
> granularity, because the per-chunk AEAD must still name which key decrypts chunk *i* — and the
> per-chunk key becomes the object's own key (`eval/results/ckpt_dedup_results.json`). **NOT DECIDED
> HERE, and it is WORM-permanent:** `sid = HMAC(K_mac, chunk)` was specified as a *globally
> comparable keyed plaintext digest* because dedup had to match chunks across objects. With dedup
> retired that requirement has no remaining consumer — but `sid` is retained above unchanged, because
> `xid` is derived from the sid sequence on the line directly below, and because `SPECIFICATION.md`
> §12.2 D-1's mitigation is written against it. Whether to replace `sid` with a non-content-derived
> per-chunk id is a one-way decision that must be taken deliberately, with D-1 re-argued, **before
> the first WORM cartridge**. Until it is taken, D-1's confirmation-oracle disclosure stands and its
> mitigation is still required — the measurement removed the *reason* for the oracle, not the oracle.
>
> **(b) The erasure unit.** `RS(k,m) over the whole thing; fragment i at H(xid ‖ i)` is **withdrawn**
> and superseded by `SPECIFICATION.md` §3: coding happens at parcel / band / fragment / stripe, and
> fragments are named by the 56-byte locator formed at `seal`, never by a content-derived id. The
> xorb remains the packing and transfer unit; it is not the coded object. `xorb.place` remains one
> journal entry per xorb but no longer implies one coded object per 64 MB.

Two deliberate departures from the winning design, both load-bearing:

- **Per-chunk AEAD, not one tag over the whole body.** A single GCM invocation over a 64 MB body
  means no authenticated partial read exists: reading 4 KiB of a run would require fetching and
  authenticating up to 64 MB, which silently makes every "cheap" catalog operation carry a 64 MB
  floor and makes the 4 KiB frame format decorative. Per-chunk costs one 16 B tag per 64 KB
  (0.024%) and 1024 GCM setups per xorb.
- ~~**The chunk key is scoped to the redaction domain, not to the xorb or the lineage.** This
  decouples the *shred* unit from the *packing* unit, so D5's contiguity bias is free to optimise
  for tape mounts while erasure stays subject-granular.~~
  **CORRECTED 2026-09-19: the chunk key is the object's key.** The shred unit and the addressing unit
  coincide, so the decoupling `K_rdom` provided is no longer needed. D5's contiguity bias remains
  free to optimise for mounts, because packing was never constrained by the key.

**IV construction (SP 800-38D deterministic, fixed field ‖ counter).** The 96-bit IV is
`32-bit session id ‖ 64-bit counter`. A session id is issued with a quorum-fenced lease and is
never reused across epochs, so there is no global per-lineage counter to lose. Counters are handed
out from a durably reserved block (reserve 10^6, `fsync` the reservation, serve from memory, skip
to the next block on restart, never reissue below the high-water mark). The previously specified
"per-lineage counter assigned by the index", combined with a prefix-sharded assigner and a
non-`fsync`ed journal, was an IV-reuse hazard — and IV reuse under AES-GCM is not degradation but
GHASH subkey recovery and tag forgery across the lineage, catalog cnodes included, permanently, on
WORM. This must be right before any bytes are written.

#### Journal entry types (each O(1) to apply; each carries `fmt`)

    version.prepare  {lin, branch, parent_v, parent_vid, epoch}          reserves nothing but the CAS slot
    version.commit   {lin, branch, v, vid, parent_v, cd, run_cids[], xset_cids[], fc, bc, term, quorum[], sig_cid}
    version.abort    {lin, branch, parent_v, reason}
    branch.open | branch.renew | branch.close
    xorb.place       {lin, xid, k, m, frag_ids[], sites[], bytes, created_seq}    one entry per 64 MB
    volume.relocate  {volume_id, site, custodian, presence}                       media migration
                     // 2026-09-19: was `xorb.relocate {xid, site, vsn, tape_position, retain_until}`.
                     // Renamed and stripped of physical position per SPECIFICATION.md 2.2: no layer
                     // above the block plane records a position.
    xorb.lease       {branch, xid_range_encoding, expires}
    xorb.redact      {lin, rdom, xids[]}                                          tombstone; repair must refuse
    extract.reserve  {eid, lin, v, retain_until, ttl}                             GC ROOT BEFORE enumeration
    extract.pin      {eid, cert_cid, root_pub, files, bytes, pin_bytes, retention, quorum[]}
    extract.derive   {eid, parent_eid, receipt_cid}
    extract.extend | extract.release
    activation.open | activation.progress (batched, carries a cursor) | activation.extend | activation.close
    gc.epoch.open | gc.epoch.marked | gc.epoch.sweep | gc.epoch.done
    redaction.order  {lin, rdom, authority, approver_sigs[]}
    redaction.shred  {lin, rdom, key_handle, files, bytes}                        key handle, NEVER key material
    key.rotate       {lin, key_epoch, session_id_range}

`xorb.place` replaces today's per-object `object.create` / `object.manifest` / `object.frags` — one
entry per 64 MB instead of one per file, against a measured `object.manifest` average of 26,743 B
and maximum of 163,864 B inlined into the journal today.

### The commit procedure

`commit(lineage L, branch B, parent_v P, ops[N])`, N = changed files only.

1. **Open a branch.** `branch.open {L, "agent/<id>/<uuid>", owner, expires}`. The branch lease is the
   only write lease in the system: one record per writer, not per chunk. An in-flight activation the
   branch owner holds **suspends** the lease clock (see *Activation*), so an agent waiting forty
   minutes on a tape mount does not return to find its branch aged out and its bytes swept.
2. **Chunk only the changed files.** CDC (GearHash, 64 KB target, 8-128 KB); `sid = HMAC(K_mac,
   chunk)`. Cost O(changed bytes). Untouched files are never opened, never hashed, never enumerated.
3. ~~**Sampled dedup probe** (D6). One `registerchunks(L, [sid…])` carrying only `sid % 1024 == 0`
   (~1 query per 4 MB); a hit returns the neighbouring-chunk shard, which the client caches and uses
   to dedup the rest of the run locally. **A cached shard is not a licence to reference:** every sid
   the client intends to reuse is named in the commit and validated against the current xorb
   inventory (predicate 4 below), because a resumed agent whose branch lease lapsed would otherwise
   commit a version composed entirely of swept references.~~

   > **Step 3 RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`). The commit procedure
   > loses a network round trip from the ingest inner loop. The step number is kept rather than
   > renumbered so that the cross-references below still resolve.
   >
   > **Predicate 4 and the swept-reference hazard are NOT retired with it.** Predicate 4 validates
   > every `xid` a commit's runs reference, *new and reused*, against the last completed sweep
   > watermark, and whole-file reuse references existing xids exactly as the dedup path did — a
   > resumed agent whose branch lease lapsed can still compose a version from swept references. The
   > guard stays; only the probe that preceded it goes.
   >
   > Whole-file reuse is now the only sharing mechanism: a file whose `sha256` is unchanged is
   > referenced by manifest id and never re-chunked, which is where the sharing measured on real
   > history actually came from — 13.4% to 47.9% whole-file against a 0.8% mean CDC marginal
   > (`eval/results/cdc_measure.json`).
4. **Pack, encrypt, code, place.** Chunks pack into xorbs (<= 64 MB, <= 8192 chunks) biased hard for
   contiguity by destination tier — a scattered read here is a tape mount, not a seek. Each chunk is
   encrypted under its redaction domain's key. RS(k,m) the xorb; place fragments; collect one
   `xorb.place` per xorb. Cost O(new bytes). Untouched xorbs are untouched.
5. **Write the run.** One `ManifestRun` holding only the changed files plus tombstones for deletes,
   sorted by `rel`, with a 24-bit/key rel Bloom; plus its `XorbSet`. Cost O(changed files).
   **`rseq` is not in the run body** — it is assigned in `VersionRoot.runs[]`, so a rebase is a
   pointer edit rather than a re-encrypt, re-erasure-code and re-place of the run across every
   institution. (Baking the sequence into the hashed body made N contending agents on one hot prefix
   cost O(N²) federation-wide coded writes.)
6. **Compose the root.** `runs = parent.runs ++ [new run]`. Exact `fc`/`bc` come from a **sorted
   merge scan** of the changed set against the covering runs, not N independent point lookups: a
   10^6-file single-tick commit is ~1 s of CPU as a merge scan and 10-60 s as 10^6 lookups.
7. **Prepare / decide.** `version.prepare` takes the per-lineage lock, checks `branches[B].head_v ==
   P`, and releases it. The quorum round runs **outside the lock**. `version.decide` retakes the
   lock, re-validates the CAS, assigns `v = P + 1`, journals `version.commit`, `fsync`s, ships.
   Assigning `v` at decide rather than at prepare keeps version numbers dense, which matters because
   `v` is what a human types and a paper prints. Internally a version is `(term, v)`; a number may be
   bound to exactly one `vid`, and a rebinding is rejected, so a rewound leader cannot reissue it.
8. **Apply.** `head_v = v; head_vid = vid`. The index stores **zero file entries**. `apply()` is
   pure: it reads only `e.ts` and the payload, performs no I/O, and refuses nothing. All validation
   lives in the RPC handler, where `publish()` and `catalogDelta()` already do it. (A time predicate
   inside `apply()` — `retain_until > now` — forks primary from replica silently on replay, and
   evaluated per institution it means the 50 nodes do not compute the same GC root set.)

**Reading a branch** is a merge iteration of the committed runs with the branch's pending runs,
newest `rseq` wins. **Reading a version** goes through the commit chain only; `ref.pending` is never
authoritative for a named version. (A version whose content is defined twice — once by the root it
carries and once by the mutable pending list — differs by the whole pending window, and every
integrity check passes on the wrong answer.)

**Point lookup**: 24-bit Bloom per covering run → one ranged, authenticated frame read → binary
search the restart index. ~1-2 object range reads warm, one cold run segment cold.

**Diff is O(changed)**: "what changed between `v_a` and `v_b`" reads only runs whose `max_rseq >
rseq(v_a)` — the reason `min_rseq`/`max_rseq` are on the root's run entry (graft, Iceberg). This is
the operation agents actually issue.

**Compaction** is the only O(total) operation and is out of band, run by the merge service under a
reserved low-priority slot with a **dedicated rebase path**: recomposing `runs = [compacted] ++
[runs with rseq > X]` requires no re-encode, so compaction cannot starve behind a busy lineage.
Run boundaries are cut by a **keyed content-defined boundary function** (graft, Merkle design):
cut after an entry when `HMAC(K_bnd, u8(level) || key)[0:8] mod 2^b == 0`, `b = 16`, floor 4096 and
ceiling 65536 entries or 8 MB. Boundaries depend only on the entry's own key, so an insert splits
one run and a delete merges with one neighbour — re-cutting is local, and successive extracts
pinned days apart continue to share most of their runs. Keying the function stops boundaries leaking
structure across lineages. A compaction commits a semantically identical version with
`cmp=<prior vid>`, so equivalence is provable by replay.

**Merge conflicts.** Disjoint branches are detected by Bloom intersection, O(1) per pair. A same-`rel`
conflict is **refused**, the losing branch is left intact with its lease alive, and the conflicting
`(rel, sha256)` pair is reported to the agent. What must not ship is an undefined resolution: with
~50 agents on one lineage, undefined resolves in practice to last-writer-wins, and last-writer-wins
plus lease expiry is a write that returned success, appears in no version, and destroys its own
evidence two epochs later.

### Extract semantics

An extract is `(lineage, v, selector)` frozen into a quorum-notarised, immutable record. It is not a
version — a version is the whole dataset and nobody trains on a petabyte — and not a query, because
re-evaluating a predicate is how you get a different answer later.

**Selector grammar is closed, versioned and deterministic.** `grammar_v` plus a fixed enum of forms:
`prefix`, `glob`, `list-digest`, `attr` (over fields the run entry carries), `sample(seed, n)`,
`all`. Canonicalisation **rejects** relative or context-dependent terms and resolves every temporal
bound to an absolute timestamp at parse time; `limit` requires an explicit `order`; `sample` uses a
named PRF over `(seed, rel)`. Without this, `mtime > now - 30d` mints the same extract id over
different file sets with no concurrency at all, and no signer could independently reproduce the
enumeration even if it tried.

**Naming.**

    extract_id = sha256( canonical(ExtractCert with the signature array removed) )
    citation   = gfs:1c:<lineage>@<v>#<extract_id>          cite class
                 gfs:1r:...                                 run class (TTL)
                 gfs:1s:...                                 scratch class (job lifetime)

The class is **in the identifier**, not only in the cert body, because a reader of a paper does not
have the body and the cheap default (an implicit whole-version activation) is the expiring one. An
extract whose bytes were actually delivered to a completed job is auto-promoted to cite class. The
cert's timestamp is derived from `index_seq`, never from wall clock, so a timed-out mint retried
with the same `idem_key` produces the **same** `extract_id` — otherwise agent retries silently
double both the pinned capacity and the Object Lock obligation.

Display form truncates `v` not at all and `extract_id` to 12 characters, with full digests in the
data-availability statement:

> `kymed-notes-v1` @ v137 # `e9c14b0a3f7d…`, index_seq 4,182,996, term 9, 1,204,338 files,
> 18.44 TiB, pin 41.9 TiB (amplification 2.27×), root_pub `3b9f…`, notarised by 7/9 coordinators and
> 5/7 custodians 2026-09-19T14:02Z.

**Two roots** (graft, Delta-log), and the public one is **redactable** (graft, tape lens):

    leaf_i   = sha256( leaf_salt_i || rel_i || sha256_plaintext_i || size_i )
    root_pub = binary Merkle root over leaf_i in canonical rel order
    root_int = binary Merkle root over (rel_i, span_root_i, size_i)   -- keyed, binds chunk layout

`leaf_salt_i` is stored in `ExtractEnum` and is encrypted under the file's redaction-domain key.
Three properties fall out of the salt that no unsalted digest can have: (a) the published root is
not a **confirmation oracle** — a plaintext digest of a short clinical note with a known template is
guessable, and the unsalted form lets anyone holding the paper prove a specific note is in the
dataset; (b) a redaction can **reveal a leaf as redacted with a proof** while the root still
verifies and every surviving file still proves, so erasure no longer breaks the citation; (c) the
identifier does not survive the erasure it documents — destroying the object's key destroys the salt,
so the *(2026-09-19: was "destroying `K_rdom`"; the property is unchanged, only the key is renamed —
`eval/results/ckpt_dedup_results.json`)*
retained `rel` (often MRN-derived) plus digest stop being a disclosure that a named subject
withdrew. The tree shape is pinned (RFC 6962 over rel-sorted leaves) so a verifier can check **one**
file in O(log n) without recalling the archive.

**Pinning is two-phase**, and the phases are in this order:

1. `extract.reserve {eid, lineage, v, retain_until, ttl}` — one quorum entry, ~150 B. The version
   becomes a **GC root immediately**, before any enumeration begins. Everything that follows is a
   job, not a synchronous call: enumerating 10^6 files is ~11 s of RPC-paced work extrapolated from
   the measured `listfiles(2000)` p50 of 22 ms, the Merkle is ~0.1 s at the measured 2318.9 MB/s,
   and applying retention is minutes to hours. Without the reservation, the pin's root does not
   exist during that whole window, and a version outside `keep_last_n` can be swept out from under
   a citation that is about to be minted. The reservation also removes the need for a no-op "freeze"
   commit: `pinextract` takes an explicit `v` and **never accepts "head"**, which is correct anyway
   because an extract is supposed to name a point in time and "head" is not one.
2. Enumerate against the fixed `v`; build `ExtractEnum` with spans **inlined**; compute both roots;
   compute the **amplification ratio** `pin_bytes / byte_count` and refuse to pin in place above the
   policy threshold (default 4×), offering **materialise** instead — rewrite the selected chunks
   into fresh xorbs and pin those. This refusal is mandatory, not advisory: the arithmetic is
   `1-(1-p)^1024` for a uniform sample at 64 KB chunks in a 64 MB xorb, so a 0.1% sample pins 64% of
   every xorb in the lineage and a 1% sample pins >99.99%, at **N = 1 extract**, indefinitely.
3. Apply retention: `retain_until` on the **retention-class bucket** holding the referenced
   fragments, not per fragment. Per-fragment is O(fragments): 64% of 1.6×10^7 xorbs/PB × 14 = 1.4×10^8
   `PutObjectRetention` calls per PB pinned, ~39 h at 1000 calls/s. Bucket-level is O(buckets) and
   is what the backup section already argued for independently. The honest consequence: layer 3
   defends a coarse superset of the citation.
4. Custodians verify and sign, **after** the pin is durable and retention is confirmed. A signature
   is the artefact that confers durability rights, so it must be released last; signing first means
   a signed, citable certificate can exist for bytes that were never rooted and never locked.
5. `extract.pin` commits; state moves `RESERVED → PINNED`; the reservation is released.

**Signers actually verify.** Each custodian independently re-materialises the selection from the
named `v` and recomputes `root_pub` before signing. This is affordable precisely because extracts
are rare and consequential, and without it the one thing an outside reader can check attests
nothing — a buggy or compromised minter could otherwise produce two validly signed certs for the
same `(lineage, v, selector)` with different roots and no consumer could detect the substitution.

**Reproduction months later.**

    resolveextract(eid) -> ExtractCert (+ redaction chain head, + the index_seq it was served at)
    activate(eid, tier, days)          -> job_id + ETA
    fetch(eid, rel[, range])           while inside the readable frontier
        -> ExtractEnum spans -> xid -> place/loc
        -> the planner selects k deterministically at plan time -> RS decode
        // 2026-09-19: was `race k of n`. Racing is retired on any mount-class tier
        // (SPECIFICATION.md 8.5); the identical string in ENTAIL-AGENT-NATIVE-FS.md 14.9 Tier 1
        // carries the same correction.
        -> per-chunk GCM verify -> whole-file sha256 verify -> leaf commitment verify
    verifyextract(dir, cert)           -> per-file leaves + recomputed root_pub vs the citation

Nothing in that path needs the index to still hold the version: the cert names `v` and `vid`, the
enumeration is self-contained, `place`/`loc` are rebuildable from the journal, and `K_L` is
recoverable from custody. Every read RPC returns the `index_seq` it was served at plus a staleness
bound, and a replica beyond that bound **fails closed** rather than serving. (A citation resolved
against a partitioned replica that does not yet know the extract exists makes "I trained on extract
E" unfalsifiable.)

**What stops the bytes being collected — three layers, and what each is actually worth.**

1. **GC rootship.** A pinned extract contributes its `xorbset_cid` and its `enum_cid` — **not** its
   commit tree, and **not** its ancestry. One root per citation, one journal entry, no counters.
2. ~~**Object Lock** at retention-class bucket granularity, monotone (extend only). Real and
   independent only where the holder is a third party running software we do not ship. On our own
   gateways it is a second `if` in the same program; on tape it does not exist at all, because blind
   tape holders run no S3 server. **Stated plainly: for the tape tier this is two layers, not three.**~~

   > **HOLE, recorded not filled, 2026-09-19.** With S3 demoted to an unoperated reference adapter
   > (`SPECIFICATION.md` §9.3) and any object-store API on the medium deleted (§15), **no component
   > in the design enforces Object Lock** — not on tape, and no longer on our own gateways either,
   > because we no longer run one. The pin defence is therefore **GC rootship plus WORM media: one
   > enforced layer and one physical property, not three**, on every tier and not only on tape.
   > Recorded as *Unresolved* 14. Do not invent a replacement here.
3. **WORM media**, which prevents overwrite absolutely but enforces no retention *period* — it does
   not stop a cartridge being exported or declining to be copied forward at a rewrite. The tape
   gateway's copy-forward step must therefore consult a quorum-published root-set digest, not the GC
   job that requested the compaction.

**A pin guarantees existence, never residency.** An expired activation lease reverts its xorbs to
SEALED. This belongs in the published contract or someone will read "immutable and pinned" as
"instant".

### Quorum integration

**Two quorums, not conflated.** The coordinator quorum makes a commit *durable and agreed*; the
institutional approver quorum decides whether something was *permitted*. Commits are frequent and
automatic; extract pins, redactions and branch expiry are rare and consequential and go to the
approvers.

**The coordinator set is 7-9 institutions, not 50.** Confirmation requires each voter to hold and
verify the proposal body; a 50-member confirming set multiplies WAN fan-out ~6× for no additional
safety beyond 2f+1.

**Validation is not consensus, and the existing primitive is neither.** `CoordinatorConsensus` acks
on epoch alone without inspecting the proposal subject, keeps `epoch`/`highestEpochSeen` in volatile
in-memory fields that reset to 0 on restart, derives membership from an in-memory high-water mark,
and matches acks by a 32-bit `String.hashCode` proposal id over non-persistent JMS. `IndexEngine` is
single-primary with fire-and-forget replication and no acks. **The commit quorum has to be built**,
and it must have:

- **Static configured membership** (`coordinator_expected` mandatory; no high-water-mark fallback).
- **A durable per-`(lineage, branch, parent_v)` vote.** A voter records the successor it voted for
  and refuses a second proposal with the same parent until it applies a commit. Without this, two
  proposals with the same parent are both validated by overlapping majorities and the loser is
  silently lost after reporting success — a stateless predicate over mutable state that no voter
  locks is strictly *weaker* than a single-region CAS, not stronger.
- **Recoverable decisions.** An ack is a durable prepare record; the next leader recovers the
  decision from f+1 prepare records before publishing any signature set. Until that exists, the
  signature set must not be advertised as externally verifiable, because it can certify a commit
  that never happened.
- **Epoch-fenced numbering.** `(term, v)`; a number binds to one `vid`, once.

**What a voter confirms — five predicates, each recomputable from the ~6 KB shipped with the proposal:**

1. **Linearity.** `branches[B].head_v == parent_v` **in the voter's own consensus log**, not in a
   log-shipped copy of the proposer's state. (Validating against the shipped copy confirms nothing —
   it is f+1 restatements of the primary's own state — and at the measured 14.2 s replica lag it
   rejects *every* proposal at any real commit rate.)
2. **Naming.** `vid == HMAC(K_mid, canonical(VersionRoot))`, recomputed, not trusted.
3. **Digest.** `cd == merkle(runs[])` in canonical order.
4. **Byte durability of everything referenced.** For every `xid` the commit's runs reference —
   **new and reused** — the voter checks the **current** `xorb` inventory, against the lineage's
   **last completed sweep watermark**, not the historical presence of an `xorb.place` entry. Two
   levels: `staged_durable` (survivability policy satisfied on the staging tier at n distinct
   domains) is what a commit asserts; `archival_durable` (the fragment is on WORM) is a later,
   cheap, per-xorb quorum flag, and is required before an extract may be **cite**-pinned. This
   split is not a weakening but a necessity: at ~1 TB/day federation-wide a **30 TB LTO-10 cartridge**
   (the plant of record: 240 cartridges, 7.20 PB media) takes **~300 days** to fill, so requiring
   archival durability at commit against a 48-hour epoch fence makes tape-required lineages unable to
   commit at all. *(CORRECTED 2026-09-19: previously quoted as an 18 TB LTO-9 cartridge at ~180 days,
   on the same per-cohort fill assumption; basis `eval/results/plant_contention.json` and
   `SPECIFICATION.md` §14.3. The correction makes the split **more** necessary, not less.)*
5. **Authorisation and ledger.** The committer may write this lineage and branch; the added bytes
   fit the reciprocity entitlement.

**What is deliberately not quorum-confirmed:** chunk and xorb registration (a fast, revocable lease
from the shard owner — a WAN round trip in the ingest inner loop is not affordable); run and xorb-set
cnodes (content-addressed and self-verifying; agreeing on a hash twice is not agreement); and the
*correctness of the content*, which no voter can check because holders are blind and voters lack
`K_L`. That residual trust in the origin is real and is stated here rather than implied away: the
origin institution must self-verify (decode its own xorb headers, confirm every span resolves and
every entry's `sha256` reproduces) and ship a **signed, journaled self-verification attestation**
with the proposal, so responsibility is attributable. Voters additionally check cheaply that every
`(xid, cidx, nchunks)` lies within the xorb's declared chunk count, which catches bookkeeping bugs
if not a malicious origin.

**The catalog stays synchronous.** Listing, search, `objectstatus` and resolve are served from the
index and from cached runs without touching sealed content. Runs are immutable and
content-addressed, so index nodes cache them on local disk **with no invalidation protocol at all** —
a direct payoff of immutable versions. The catalog tier is **never Glacier and never sealed**: GC
mark, extract resolution and activation planning all read cnodes, and any of those requiring a tape
mount violates the standing rule that only content is sealed.

### Activation of an extract

You activate an extract, never a dataset and never a version. If a caller asks to activate a whole
version, the system mints an implicit `run`-class extract with selector `{kind:"all"}`, so every byte
the fabric ever delivers is attributable to a citable, budgeted, notarised selection.

    activate(extract_id, tier, days [, sub-selector])  -> 202, job_id, ETA     == POST /key?restore
    activationstatus(job_id) -> {state, wave, frontier_ord, ready_bytes, next_eta, undeliverable}
    fetch(extract_id, rel, range) outside the frontier  -> 403 InvalidObjectState + Retry-After
    extend(job_id, days)

**A version has no access state.** `SEALED`/`THAWING`/`AVAILABLE` is a property of a xorb's staged
copy, orthogonal to `DURABLE`/`DEGRADED`/`LOST`/`REDACTED`. Two extracts of the same version can have
disjoint xorb sets, so "is v137 available?" is not a well-formed question — which is exactly why the
temptation to put an enum on the version must be refused. Partial activation of a version means: a
subset of the version's xorbs is staged; the version itself is unchanged, immutable and total; the
readable set is exactly `{f : every span's xid is AVAILABLE}`. Only residency is partial.

**Planning is over xorbs, and durability is evaluated at planning time.** The planner resolves
enumeration → spans → distinct `xid` set, then intersects with the `xorb` table and returns a
**non-deliverable set up front** — "18,432 files cannot be delivered: 12 xorbs REDACTED under
IRB-2026-114, 1 xorb LOST" — before a single mount is scheduled. Without this the consumer sees a job
stuck at 99.9997% for days, because on tape "not yet" and "never" are indistinguishable from the
recall path.

**Waves are ranges of enumeration ORDINAL, not of `rel`.** A wave is `[lo_ord, hi_ord)` over
`(rel, span_index)` pairs; within a wave each site sorts its xorbs by (VSN, serpentine position) and
runs one pass (D9). Defining waves over `rel` gives a single-file dataset exactly one possible wave,
so a 10 TB file delivers zero bytes until all 10 TB is staged and needs 10 TB of stage to read its
first byte. Ordinal waves give a byte-range frontier inside a file, which is what ranged reads need
anyway. Wave size is the explicit knob trading first-byte latency against mount efficiency and is
the single biggest performance lever in a restore.

**The plan pins logical xids only.** VSN and serpentine position are resolved at activation time
from the mutable `loc` table. Freezing physical positions into an object that is hashed into a
citation guarantees they are wrong after the first media migration, and resolving 10^5 xids is a
bulk lookup, not the 10^6-entry re-walk that freezing was meant to avoid.

**Readability is O(1) to poll.** `wave_frontier` is the highest wave ordinal all of whose xorbs are
AVAILABLE, updated when a wave completes — at most a few times a minute. Recomputing the readable
set per poll is 50-100 ms of CPU at 10^6 files and ~1.6 s at 1 PB, on a path clients poll at 1 Hz.

**Leases are monotone.** A staged xorb's `avail_until` is **raised** by an activation opening or
extending and by nothing else; a close does nothing and expiry reclaims. A max recomputed over a
mutable set is a lost update, and it needs a reverse `xid → jobs` index that is itself 10^7 mutable
entries. The lease is journaled once per activation carrying an explicit (range-encoded) xid list,
so `apply()` never has to dereference a plan object to expand it.

**Version sharing makes activation monotonically cheaper.** Activating an extract of v137 while an
extract of v136 is AVAILABLE thaws only the differing xorbs. At 1% churn that is ~100× fewer mounts
on the second activation, and immutability means there is no invalidation protocol. Mounts are the
scarce resource, so this is the payoff that is easy to miss.

**Partial activation produces a new extract, not a caveat** (graft, Delta-log). The fetch path emits
a signed, incrementally extended **consumed-set receipt** — a Merkle root over the leaves actually
delivered to that token, requiring no quorum at read time. If a job completes against a PARTIAL
activation, the receipt is quorum-pinned as a **derived extract** with `parent_extract` recorded and
its own root. The alternative — an agent that trained on 970,000 of 1,000,000 files citing the full
extract — is a reproducibility failure the root check catches only after the compute is spent. The
receipt, not the delivered set, is the honest artefact: streaming means delivered ≠ consumed.

**Budgets are denominated in bytes STAGED as well as delivered.** The two differ by the same
amplification factor as pinning — up to ~70× for a selector orthogonal to the packing axis — so a
delivered-only budget lets a 30 GB request compel an 800 GB recall across six institutions. Both
figures are computed at mint and printed on the cert.

**Repair and scrub never go through this path.** They read ciphertext fragments by `H(xid||i)`, need
no key and no approval, and must never be stallable by an expired credential.

### GC and redaction

**GC is epoch-based mark-and-sweep with leases (D4), per lineage, fenced on a journal sequence and
never on a wall clock.** Reference counting is rejected because references are created by agents on
ephemeral branches that may never merge (every abandoned branch leaks a permanently inflated count
with nobody to decrement it), because a durable read-modify-write per chunk per version across 50
institutions is not a system, and because you cannot decrement in place on tape.

1. **Freeze.** `gc.epoch.open` records `epoch`, `mark_start_seq` (the current journal sequence) and
   the root set **by name**: every branch head with an unexpired lease; every tag; every version
   inside the retention window; every `ExtractRec` in `RESERVED` or `PINNED` with `pin_class=="cite"`
   or `pinned_until > now` **as of `mark_start_seq`**; and **every extract referenced by an
   `ActivationRec` in PLANNING/QUEUED/THAWING/PARTIAL/READY**. That last clause is not optional: a
   400 TB tape activation legitimately runs for days, and without it the extract's `pinned_until`
   can pass mid-recall and the sweep deletes the bytes the job is still reading.
   `activation.open` additionally raises `pinned_until` to at least `deadline` plus one epoch.
2. **Mark, fail-closed.** Walk each root's `runs[]` → the run's **`XorbSet`** and stop there. The
   mark never descends to file entries and never opens a per-file span list; this is why `XorbSet`
   exists as its own cnode. A run already marked this epoch is skipped by cid, so marking N versions
   that share most of their runs costs O(distinct runs), not O(N × files). The epoch **aborts** if
   `runs_marked != runs_expected` — a run cnode that cannot be read (a mount timeout, a stale shard
   owner) yields a short live set, and that failure is *systematic*, so it repeats next epoch and
   the two-epoch rule does not catch it. Output is a Bloom filter over live xids at 24 bits/xid,
   whose false positives fall on the safe side (retain garbage, never delete live data). A shard
   must not emit a MarkSet until its local `seq >= mark_start_seq`.
3. **Candidates** = xids with `created_seq <= mark_start_seq` minus the live set, by a prefix-sharded
   scan of the `xorb` table. This touches xorbs, never chunks, so the 1.6×10^10-chunks-per-PB figure
   is irrelevant to GC.
4. **Immunity horizon.** Any xorb with `created_seq > mark_start_seq` is immune this epoch, full
   stop. Any xorb under an unexpired branch lease is immune regardless of marking. Lease expiry is
   evaluated against **index time returned with every renewal**, not the writer's clock.
5. **Authorise.** `gc.epoch.sweep` is quorum-confirmed over `(lineage, epoch, mark_start_seq,
   digest(live_set_cid), candidate_count, shard_caps)`. Because deletion is the one irreversible act,
   a signer does not merely co-sign an opaque digest: each independently samples *j* random entries
   from `candidate_cid` and proves them unreachable from the named root set. At a 1% wrongly-listed
   rate, `j = 300` catches it with p ≈ 0.95, for a few hundred point lookups per signer.
6. **Sweep.** Disk holders delete. **Tape sites never delete in place**: the xorb is marked
   RECLAIMABLE and reclaim happens at cartridge rewrite. A fragment under an unexpired `retain_until`
   is skipped and counted in `blocked_by_lock` — the store's refusal is a feature.
7. **Two-epoch rule over the mark sets.** A xorb is deleted only if absent from the live set of two
   consecutive *completed* epochs separated by more than the maximum branch-lease TTL.
8. **Metadata is collected by the same pass.** Cnodes are content-addressed objects with the same
   lifecycle; orphaned runs from abandoned branches and superseded rebases disappear in the same
   sweep, with the version chain as an explicit root class so the chain a citation walks is never
   collected. One collector, one epoch, no second mechanism.

**GC on the WORM tier is off by default, and the tier is sized for monotonic growth.** This is the
honest consequence of pin amplification, and it removes two whole failure classes. Reclaiming a
**30 TB LTO-10 cartridge costs 20.8 drive-hours of read pass plus the write of the live fraction**
(~33 drive-hours at a 60% live fraction) — MEASURED BASIS 2026-09-19,
`eval/results/plant_contention.json`; ~~an 18 TB LTO-9 cartridge costs ~20 drive-hours (12.5 h read +
7.5 h write at 400 MB/s)~~, which is not the plant of record (240 cartridges × 30 TB = 7.20 PB
media). Plant-wide, repack is **1.9% of the plant-year at 85% dead (15% live) and 6.5% at 50% dead**
— cheap in drive-hours, which is *not* the argument against it. It consumes fresh
media, requires physically destroying the WORM original, and — because a pin is applied *after* the
bytes were written under whatever retention class was then current — no cartridge in a cited lineage
can ever expire as a unit again. Where reclaim is nevertheless run, the copy-forward step must
re-apply `retain_until` to the rewritten fragments, or the pin silently evaporates at exactly the
moment the bytes move.

#### Redaction — resolved by per-object keys, not by destroying fragments

> **Retitled 2026-09-19.** Was *"resolved by key domains"*. The four-point D2 refutation immediately
> below is untouched by any measurement — `auto_repair`'s 5 s `repairSweep`, WORM refusing overwrite,
> the 500–1,500-unrelated-subject packing blast radius with its closed form, and the Object Lock
> COMPLIANCE veto all stand verbatim. Only the replacement mechanism changes.

**D2 (destroy m+1 of n fragments) is retired as the redaction primitive.** It fails four ways at
once, all verified rather than hypothetical:

- `auto_repair` defaults **true** on a 5 s `repairSweep` which regenerates any DEGRADED object from
  any k survivors needing no key and no approval, while a cross-institution m+1 destruction takes
  days to roll out. The fabric un-redacts faster than the sites can destroy, and it is a stable
  attractor, not a narrow race. A later off-site restore at any one site re-enables full regeneration.
- WORM refuses overwrite by design, so on the medium the whole system targets the only physical
  destruction is retiring a cartridge holding ~2.8×10^6 unrelated fragments.
- D5 packs ~1024 chunks from ~64 files into a 64 MB xorb, so the minimum destruction unit takes out
  roughly 500-1,500 other subjects in a clinical lineage. Closed form: destroying one xorb per
  withdrawal destroys `1 - exp(-r · 64 MB / b)` of the lineage independent of cohort size, so at
  80 KB per subject a 1%/yr withdrawal rate destroys ~99.97% of the dataset in the first year.
- A cite-class pin sets Object Lock `retain_until`; COMPLIANCE mode cannot be shortened by anyone
  including root, so a publication citation would acquire a decade-long veto over consent withdrawal.

**The mechanism is a per-object key.**

    consent unit  the unit consent is withdrawn for: "subject" | "<metadata field>".
                  It is a CATALOGUE LABEL, not a key. It names the set of object keys
                  destroyed together and can be regrouped at any time.
    K_obj         random AES-256 per OBJECT, wrapped under K_L, stored ONLY in the LSM key store,
                  NEVER in the journal, dumpState, stateHash or any WORM snapshot (P5)
    chunk key     K_obj directly; no derivation step

> ~~`rdom` / `rdom_rule` / `K_rdom`~~ — **RETIRED 2026-09-19**, see
> `eval/results/ckpt_dedup_results.json`: the domain key existed to make shredding survive
> deduplicated sharing, and the sharing is zero. Every zero-mount, zero-bytes-moved and
> exact-blast-radius claim below survives unchanged and is now *stronger*, because the blast radius
> is the object rather than the domain.

Redaction is then: `redaction.order` (institutional approver quorum, with the authority recorded)
→ `redaction.shred`, which destroys the wrapped object-key rows for every object in the consent unit
and compacts the key store. It takes
zero tape mounts, zero bytes moved, zero cartridges retired, zero manifest rewrites, and has
**exactly the blast radius of the object** — on disk, on WORM, in every version and in
every pinned extract, immediately, at the moment the order is applied. It is the only primitive
compatible with write-once media, and it is the property the original per-object DEK had and D1
removed without a replacement — **restored in full, 2026-09-19.**

Decoupling the *shred* unit from the *packing* unit is no longer needed, because the shred unit and
the addressing unit now coincide; D5's contiguity bias stays free to optimise for mounts, because
packing was never constrained by the key. ~~The price is that chunk deduplication is **within a
redaction domain** — the `dedup` table records `rdom` and a hit is reusable only on a match. For
longitudinal clinical data, within-subject dedup is where the win is.~~

> **RETIRED 2026-09-19** with `K_rdom` itself (`eval/results/ckpt_dedup_results.json`). There is no
> within-domain restriction because there is no chunk dedup, and with no cross-object sharing there
> is nothing for a restriction to restrict. The claim that "within-subject dedup is where the win is"
> was **never measured** and is withdrawn rather than carried forward. The analogous measurements
> available — real training checkpoints, 561 commits of source history, a venv, uncompressed wav,
> compressed video — return 0.0–0.6%. **It remains unmeasured on longitudinal clinical text, and this
> retirement does not claim otherwise**; see the restated open question at `SPECIFICATION.md` §16
> item 6.

Supporting rules, all required:

- **`xorb.redact` tombstone.** `derivedState` and `repairSweep` consult it and refuse to act. A
  **REDACTED** terminal state on the durability axis, distinct from LOST, carries a dated,
  quorum-signed `RedactionRec` naming the authority, date, approver set and counts. That record
  survives the data. A 2036 reader must be able to tell an audited erasure from media loss, and a
  real breach must not be launderable as a redaction.
- **Ordering.** Seal first, destroy later: the shred is applied and converged at the index before any
  optional defence-in-depth fragment destruction, not after. The reverse ordering gives a multi-day
  window in which one extract id returns full bytes or fails depending on which k of n win the fetch
  race — and in which `root_pub` verifies over data that was legally destroyed.
- **Redaction chain.** `redactions` is **not** a mutable list on `ExtractRec`. A redaction produces a
  signed, immutable `RedactionRec` whose id chains from `extract_id`; `resolveextract` returns
  `(cert, redaction_chain_head, index_seq)` so a consumer can tell whether it has a complete view.
  A mutable field on an asynchronously replicated record makes an "immutable" identifier mean
  different things on the primary and on a replica, with no staleness bound.
- **Citation survives, honestly.** The salted redactable root means the extract still verifies, every
  surviving file still proves inclusion, and the redacted leaves return the attestation instead of
  bytes. The extract moves to `PARTIALLY_REDACTED`. Reproducibility of the redacted files is
  permanently and visibly broken; that is the correct outcome and it is stated rather than hidden.
- **Object Lock mode.** With shredding as the primitive, COMPLIANCE mode is no longer in conflict
  with erasure, because erasure never asks the store to delete anything. COMPLIANCE is therefore the
  default for cite-class pins.

**Nothing verifies that pinned bytes still exist until someone activates**, so add **sampled
proof-of-possession**: challenge a holder for `H(fragment || nonce)` on a random 0.1% of cold bytes
per site per year. At 1 PB per site that is ~1 TB of reads and ~56 mounts, and it detects a site
that silently dropped ≥ 0.05% of its holdings with near certainty within a year. `scrub()` cannot
substitute: it iterates the store's own rebuilt inventory, so a deleted fragment is never reported.

### Scale limits, with numbers

Measured baselines: 10^6 files = 1811 MB heap / 5536 MB RSS; ingest 143,444 files/s; `resolve`
p50/p99 0.2/0.4 ms at 5397.7/s across 16 clients; `commit` 0.3 ms; replica lag 14.2 s;
RS(10,4) 423 MB/s single-thread and 3872 MB/s × 14; SHA-256 2318.9 MB/s; AES-GCM decrypt 3411 MB/s
and encrypt 24,232 MB/s × 14; fragment push peak 577 MB/s; control-plane RPC p99 0.72 ms under a
444 MB/s flood; 240 sites, placement solve + promote 3 ms.

**Per-record arithmetic** (from the field lists above, not from estimates):

| item | size | at 10^6 files |
|---|---|---|
| `FileEntry`, one span, prefix-compressed | ~95 B | ~95 MB total |
| `ManifestRun` at 64 K entries | ~6.1 MB | ~16 runs |
| `XorbSet` per run | ~28 B/xid; 200 KB typical, 1.8 MB worst | |
| commit touching 1,000 files | run 95 KB + xset 28 KB + root 6 KB | **~130 KB** |
| `VersionRoot` (30 runs, HLL in a sidecar) | ~6 KB | O(1) in dataset size |
| quorum fan-out per commit | 6 KB × 9 voters | ~54 KB |
| journal entry `version.commit` | ~400 B | one per commit |
| index heap per lineage | head + branches + tags | **kilobytes** |
| `ExtractRec` (raw `byte[16]` ids, sigs in the cert) | ~350 B | 10^6 cite pins = 350 MB |
| in-xorb chunk table | 1024 × (32+4+4+2) B = ~42 KB/xorb | **0.06%** of stored bytes |

**What breaks, in order.**

1. **Pin amplification — at N = 1, not at some large N.** The collectable and pinnable unit is the
   xorb, so a uniform 0.1%-sample cite extract pins `1-(1-0.001)^1024 = 64%` of the lineage's xorbs
   indefinitely; 1% pins >99.99%. At the fragment density of a **30 TB LTO-10** cartridge (the plant of
   record; ~2.8×10^6 was quoted for an 18 TB LTO-9, corrected 2026-09-19) it is effectively 100% of
   the lineage's cartridges, which defeats retention-class cartridge grouping — the one mechanism
   that makes expiry work on tape. Mitigations, all mandatory rather than advisory: the 4×
   materialise threshold at mint; declaring the split at ingest so `train`/`val`/`test` stream to
   separate xorbs and separate cartridge groups; the D5 contiguity bias; and **"citable extracts per
   dataset per year" entered as a first-class capacity input beside pledged and consumed**.
2. **Commit rate per lineage — 5-20/s.** A quorum round across 7-9 institutions at 20-80 ms WAN RTT
   is 100-200 ms; ECDSA P-384 verification is 0.3-0.7 ms × 9 = 3-6 ms and runs **off** the index
   monitor. Commits on a lineage serialise on `parent_v`. Federation-wide throughput scales with the
   number of per-lineage leaders, which is why the monitor must be striped (P6): with one global
   monitor the ceiling is 5-20 commits/s for the *entire* federation, three orders off what 10^3
   active lineages need. The merge service is therefore load-bearing: 50 agents at one commit per
   5 s is 20 commits/s on branch refs alone, so branch commits are served by a **single coordinator
   under a renewable quorum-issued lease** and only the merge to `main` takes the full round.
3. **Level-0 run accumulation.** Point-lookup cost is O(covering runs). Compaction must sustain the
   commit rate; LSM write amplification is ~30× at a 10× fan-out, landing on encrypted,
   erasure-coded, quorum-committed writes. At 20 commits/s × 130 KB that is ~2.6 MB/s of new catalog
   and ~78 MB/s of compaction traffic, which is why the catalog tier is NVMe-class and never sealed.
   Past ~50,000 pending level-0 runs a point lookup degrades from ~1 run read to ~50.
4. **GC mark.** ~2×10^4 distinct live runs per lineage × ~200 KB of `XorbSet` ≈ 4 GB per lineage per
   epoch; at 10^4 lineages and a weekly cadence, ~40 TB/epoch federation-wide, sharded 50 ways ≈
   800 GB per site per week ≈ 1.3 MB/s sustained. Live-set Bloom at 24 bits/xid: **48 MB per PB**,
   4.8 GB at 100 PB. Without the `XorbSet` cnode the mark would have to open every live file's span
   list — 10^8-10^10 fetches per epoch, off by 10^3-10^4 — which is why the descent stops at the run.
5. **Index heap for extracts.** Only cite-class lives in heap; run- and scratch-class live in the LSM
   with a TTL. 10^6 cite pins = 350 MB, against the 1811 MB of `DatasetRec.files` this design
   deletes. The ceiling moves from *file count*, which is unbounded here, to *cite-pin count*.
6. ~~**Sampled dedup index.** 1 PB at 64 KB chunks is 1.6×10^10 chunks; sampled at 1/1024 that is
   1.6×10^7 entries/PB ≈ 770 MB/PB, 77 GB at 100 PB, prefix-sharded. It is a **rebuildable cache**
   (reconstructible by scanning xorb headers), consulted only by writers — never by readers, never by
   GC — so it can be sharded without quorum and lost without data loss.~~
   **RETIRED 2026-09-19** (`eval/results/ckpt_dedup_results.json`). The 77 GB at 100 PB is reclaimed;
   the entry is kept so the index budget's history is auditable. What replaces it is smaller and
   differently shaped: per-object manifests at ~10^6 objects per lineage, inside the scale the index
   is already proven at (10^6 files, 1811 MB heap). That ~10^6 is a document estimate, not a
   measurement.
7. **Large files.** With `SpanIndex`, a 10 TB file is a ~1 MB span root over ~7,300 bounded segments;
   a one-byte append rewrites one segment and the root, and a ranged read costs O(log n) + one
   segment. Without it the same file is a 1.5-30 GB unindexed blob that must be materialised in full
   to read 1 MB, which is the shape genomics BAM/CRAM, single-file Parquet shards and model
   checkpoints actually have. The threshold is 4096 spans.
8. **Media migration overhead.** Two LTO generations coexist for roughly four years in six, so
   pledged capacity carries a ~1.7× multiplier on top of pin amplification before a byte of user
   data is counted.
9. **Journal volume.** `xorb.place` is one entry per 64 MB, so 1 PB of ingest is 1.6×10^7 entries.
   `log_retain` must be re-derived as a **byte budget** rather than an entry count, since entry sizes
   now span two orders of magnitude, and the primary needs a **checkpoint-and-truncate** path: the
   journal is never truncated on the primary today, and at 10^4 lineages × 2,880 commits/day the
   replay cost alone reaches hours.

### Unresolved

1. **The commit quorum does not exist.** Every latency and safety number here assumes a Raft-class
   component with static membership, durable per-term votes and leader-failure recovery. Building it
   is the second-largest item in the plan after the LSM, and the honest interim position is
   single-writer under a fenced lease with the word *quorum* withheld.
2. **Key custody does not survive a citation horizon.** `custody.register`/`approve`/`clear` is the
   whole protocol — no resharing, no share refresh, no membership-change handling, and
   `custody_quorum` defaults to 2. At n=12, t=7 and 5%/yr irrecoverable share loss, ~34% of
   ten-year-old citations are undecryptable while the ciphertext sits in perfect condition on WORM.
   Proactive verifiable secret sharing with resharing at every epoch and every membership change,
   plus an escrowed set at a long-lived custodian, is standard and is not designed here.
3. **Key rotation across a citation.** SP 800-38D forces `K_L` rotation roughly per PiB. `key_epoch`
   is representable on every record, but a two-generation activation's custody path is unspecified,
   and "retain every historical lineage key for a decade-old citation" is in direct tension with
   "destroy a key to honour a withdrawal". ~~The `K_rdom` layer narrows this~~ **Per-object keys
   narrow this (2026-09-19)** — rotation applies to `K_L` and the wrapping, never to an object's
   content key, which is immutable for the life of the medium — but the custody path for a
   rotated-out generation still needs designing. **The unsolved item itself stands unchanged; only
   its attribution changes.** It is not retired and must not be swept away with `K_rdom`: the
   immutability of content keys on WORM is a property of write-once media, not of key granularity.
4. **Media generation migration.** `xorb.relocate` and the mutable `loc` table make it
   *expressible*; the migration itself — preserving fragment ids, re-applying retention, cartridge
   cohorting so one lost cartridge maps to a bounded set of partner cartridges rather than ~k/(n-1)
   of the federation's tape — is an unbuilt subsystem, and cohorting constrains cartridge layout, so
   it must be decided before media is bought.
5. **Path-order locality is asserted, not measured.** Run sharding, compaction cost and merge-conflict
   rate all assume dataset changes are path-local. It is cheap to test — histogram the `rel`-prefix
   spread of consecutive `dataset.delta` entries against the real KOS dataset — and nothing should
   be built on it until that runs.
6. **Cross-lineage extracts.** A training set drawn from five datasets needs either a collection of
   per-lineage extracts at five independent sequence points — not one consistent cut — or a
   global-journal cut across five independent merge services and five independent GC epochs. Not
   worked through.
7. **Rebase livelock on a hot prefix.** Moving `rseq` out of the run body makes a rebase a pointer
   edit rather than a federation-wide re-encode, which removes the O(N²) cost. Whether optimistic
   rebase *converges* with many agents on one prefix is still unanalysed, and the merge service
   remains a single writer per lineage — a throughput and availability chokepoint every number here
   depends on.
8. **Metadata confidentiality.** Index nodes must hold `K_meta` to serve listing and search
   instantly, and that key reveals the full path tree and every chunk id for the lineage. Across 50
   independent institutions that is the cross-institution metadata disclosure the federation plan
   objects to for data. A per-institution metadata trust domain, or a `catalog_visibility:
   opaque | index-readable` knob, both have costs not worked out.
9. ~~**Redaction domains must be declared at ingest.** `rdom_rule` is a per-lineage policy, and
   assigning a domain retroactively to already-written chunks is a re-encode. For a lineage whose
   consent structure is discovered later, the escape is `high_redaction` per-object keys, which
   forgoes deduplication — the D1 trade, now made explicit at the right granularity rather than at
   the lineage.~~

   > **RETIRED 2026-09-19** by `eval/results/ckpt_dedup_results.json`. The one-way door existed
   > because the escape hatch — per-object keys — cost deduplication. It costs nothing, so the escape
   > hatch is the default, `rdom_rule` need not be declared at ingest, granularity is at its floor and
   > can never need to be made finer, and grouping objects into a coarser consent unit is a catalogue
   > edit rather than a re-encode. This retires only the *granularity* one-way door: packing layout
   > and container grouping remain irreversible on WORM (`SPECIFICATION.md` §8.4,
   > `STORAGE-BINDINGS-DECISION.md` A-5).
   >
   > **Hole opened, recorded not filled — see item 11 below.** Per-object keys shred at OBJECT
   > granularity, and a withdrawal whose natural unit is a SUBJECT spanning many objects becomes an
   > enumeration over that subject's objects.
10. **Reclaim latency is structurally weeks, and on WORM it is never.** Two consecutive epochs plus
    `retain_until` plus cartridge-rewrite economics mean deleted data occupies pledged capacity for
    a long time. With GC off on the WORM tier the honest statement is that the archive is monotonic
    there, and the reciprocity ledger's headroom model has to say so.

**Opened 2026-09-19 by the measurement pass. Recorded, not solved.**

11. **Subject-granular withdrawal has no mechanism.** `K_rdom` gave a shred unit that could be a
    subject spanning thousands of objects, destroyed in one operation with an exact blast radius.
    Per-object keys shred at object granularity, so replacing it means enumerating a subject's
    objects at withdrawal time — and that enumeration must itself be erasable (it is exactly the
    artefact this design keeps off unerasable media), must survive index loss, and must be computable
    without mounting tape. This is the residue of the hardest problem in the design. It is much
    smaller than the problem it replaces, but it is not zero, and it gates clinical lineages.
12. **Two live, incompatible positions on hierarchical LRC.** `SPECIFICATION.md` §15 deletes LRC
    local groups outright; `ENTAIL-AGENT-NATIVE-FS.md` §13 defers them and gives `Locus` a
    `local_groups[]` field. D10 above is split on exactly this. One must win before placement is
    built.
13. **Whether a content-derived chunk id should exist at all.** Deduplication was the only consumer
    of `sid` as a lookup key. `SPECIFICATION.md` §12.2 D-1 documents what keeping it costs: `sid` is
    a keyed plaintext digest written onto WORM inside the in-xorb chunk table under `K_meta`, which
    survives every shred, giving every authorised reader of that lineage a thirty-year
    membership-confirmation oracle against subjects who already withdrew. With dedup gone the oracle
    is paid for and buys nothing. Integrity does not need it — per-chunk AEAD, `leaf_root` and the
    whole-file `sha256` cover that. But `xid = HMAC(K_mac, sid_0 ‖ … ‖ sid_{n-1})` consumes it, and
    changing it is WORM-permanent. **It must be decided deliberately before the first cartridge.**
14. **No component enforces retention any more.** The three-layer pin defence (GC rootship, Object
    Lock, WORM media) loses its middle layer: `SPECIFICATION.md` §9.3 demotes S3 to a consumer-side
    reference adapter *we publish and do not operate*, and §15 deletes any object-store API on the
    medium, so nothing in the design implements Object Lock — not on tape, where blind holders run no
    S3 server, and no longer on our own gateways either. What remains is **GC rootship plus WORM
    media: one enforced layer and one physical property, not three.** WORM prevents overwrite
    absolutely but enforces no retention *period*, does not stop a cartridge being exported, and does
    not stop a holder declining to copy it forward. Whether retention needs a second enforced layer,
    and where it could live given blind holders, is unsolved. Do not invent one here.

## Measured: where content-defined chunking actually pays (2026-09-19)

Two measurements, harnesses and raw results in `eval/cdc_measure.py`, `eval/cdc_largefile.py`,
`eval/results/`. The versioning design assumed cross-version chunk sharing everywhere; the
assumption holds in one layer and fails in the other.

### Small files, real history — CDC buys ~0.8%

Eight version pairs sampled every 25 commits across 561 commits of `code/controller`, separating
**whole-file reuse** (untouched files, free, needs no CDC) from **chunk reuse inside changed files**
(the only thing CDC buys):

| | whole-file shared | chunk shared | CDC marginal |
|---|---|---|---|
| best pair | 47.9% | 47.9% | **0.00%** |
| worst pair | 13.4% | 14.7% | 1.29% |
| **mean of 8** | — | — | **0.8%**, zero in 3 of 8 |

Intra-corpus: venv 0.6%, uncompressed narration wav 0.0%, compressed video 0.0%. The mechanism is in
the data: those files average ~10 KiB against a 64 KiB target, so most are a single chunk, and a
single-chunk file that changes at all changes entirely. Also measured, for the index-scale question:
**17,000–27,000 chunks per GiB**, i.e. 1.7–2.7 × 10^10 chunks per PB.

### Large files — CDC's value is entirely in INSERTIONS

192 MiB base, CDC (64 KiB target) against fixed 64 KiB chunking:

| mutation | CDC shared | fixed shared | CDC advantage |
|---|---|---|---|
| append 0.1–4% | 99.83–99.88% | 99.97–100% | **−0.1%** |
| prepend 0.1% | 99.85% | **0.10%** | **+99.75%** |
| prepend 4% | 99.86% | 3.82% | +96.04% |
| insert middle 0.1–4% | 99.83–99.88% | 49.99% | **+49.85%** |
| overwrite scattered 4% | 92.87% | 97.91% | **−5.04%** |

A 0.1% prepend destroys 99.9% of fixed-size chunking and costs CDC nothing. But CDC *loses* on
append and on in-place overwrite, because a boundary that moves invalidates its neighbours.

### The consequence — the two layers want different chunkers

- **Metadata layer: keep CDC.** RRE runs are *sorted* shards of file entries, so adding a file in
  sort order is a middle-insertion — precisely where fixed chunking loses half. "Keyed CDC run
  boundaries" is correct and this is the evidence for it.
- **Bulk content layer: chunk-level dedup is not earning its cost.** The populations Entail names as
  dominant — checkpoints, tokenised shards, embeddings — mutate by overwrite and append, the two
  cases where fixed chunking ties or wins. Imaging is add-only, where whole-file reuse captures
  everything and the chunker is irrelevant.

This matters because **the content layer is where the complexity is paid for**: within-domain dedup,
the 10^10-entry index, and the reason per-object keys became unaffordable. If chunk-level content
dedup is worth −5% to +1% on our real mutation profile, dropping it for content while keeping CDC
for metadata plausibly restores per-object keys — and with them per-object crypto-shredding,
retiring `K_rdom` and the hardest unsolved problem in the design.

**Before acting on that**, two limits: the large-file base is pseudo-random, so there is no
intra-file redundancy — sound for a v1-versus-v2 boundary-recovery measurement, which is what this
is, but it is **not** a measurement of checkpoint-to-checkpoint sharing on real weights. That case
depends on large byte-identical regions (frozen backbones, unchanged embeddings); where every weight
shifts slightly, neither chunker shares anything. **Measure real checkpoints before deciding.**

## Measured: checkpoints do not deduplicate (2026-09-19)

The assumption the redaction design rested on, tested on real training output. Harness
`eval/ckpt_dedup.py`, raw results `eval/results/ckpt_dedup_results.json`. Measured on a DGX compute
node over `ft/checkpoints/sft_v530_v6_long_p2`, a real SFT run with checkpoints every 500 steps, 51 GB
each (12.06 GB weights, 24.1 GB optimizer state, 12.06 GB FSDP copy).

64 KiB fixed blocks rather than CDC, deliberately: checkpoint files have identical structure at
identical offsets, so there are no insertions for CDC to recover, and the earlier measurement showed
CDC *loses* 5% on in-place overwrite, which is exactly what a weight update is.

| comparison | shared blocks | % of B | % excluding zero blocks |
|---|---|---|---|
| weights, adjacent (ckpt 1000 → 1500) | **0** | 0.0000 | 0.0000 |
| optimizer state, adjacent | 154 | 0.0420 | **0.0020** |
| safetensors vs FSDP copy, same checkpoint | **0** | 0.0000 | 0.0000 |
| weights, distant (500 → 3727) | **0** | 0.0000 | 0.0000 |
| cross-run control | **0** | 0.0000 | 0.0000 |

Self-deduplication within each file is 0.000%. The optimizer's 154 blocks are almost entirely the
all-zero block (zero fraction 0.040% against 0.042% shared). The cross-run control returning exactly
zero confirms the measurement discriminates rather than being broken.

Also refuted: the two weight copies inside each checkpoint are **not** block-identical. Different
serialisations of the same tensors produce entirely different bytes, so the apparent 12 GB of
intra-checkpoint duplication is not recoverable by content addressing.

### What this deletes

Chunk-level content addressing earns **nothing** on the population Entail identifies as dominant.
Therefore:

- **Per-object keys are affordable again**, and with them **per-object crypto-shredding** — the
  property the original design had and that D1 removed.
- **`K_rdom` is retired.** The redaction-domain key, the `HKDF(K_rdom, "chunk" ‖ sid)` chain, the
  compactible shred store, the within-domain deduplication restriction and the trap that `rdom_rule`
  must be declared at ingest all exist to make shredding work *despite* keys shared by deduplication.
  With no sharing there is no shared key and no problem. This was the hardest unsolved item in the
  design; the measurement removes it rather than solving it.
- **The index-scale blocker largely dissolves.** The 10^9-entry federation-wide chunk table existed
  to support cross-object dedup. Per-object manifests are ~10^6 objects, inside what the index is
  already proven at.
- **CDC survives only in the metadata layer**, where sorted runs make insertions ordinary.

### What this makes worse

Checkpoints can be neither deduplicated (measured here) nor recomputed — a `NONDETERMINISTIC`
derivation may **never** be silently rebuilt (`ENTAIL-AGENT-NATIVE-FS.md` §3.4), and non-associative
floating-point reduction order makes most GPU training nondeterministic unless pinned (§14).
*(CITATION CORRECTED 2026-09-19: this sentence previously attributed the disqualification to "the
tape brief". No such statement exists in `TAPE-RESEARCH-PROMPT.md`, verified by grep over the whole
gfs tree; the support is ENTAIL's own determinism model.)* They are incompressible,
irreducible cost, and the only remaining lever is **retention** — keeping fewer of them. Entail's
entailment-first thesis is consequently the *only* answer to 10–100× derivative growth rather than
one of two, and checkpoint retention policy becomes a first-class capacity input rather than a
housekeeping detail.

## Measured: the durability barrier, and the 40x root_path cliff (2026-09-19)

Harness `eval/fsync_cost.py`, raw results `eval/results/fsync_cost.json`. 256 KiB fragments,
200 writes.

| host / path | barrier | MB/s | ms per fragment |
|---|---|---|---|
| macOS APFS, laptop NVMe | none | 731.5 | 0.34 |
| macOS APFS | data only | 40.7 | 6.14 |
| macOS APFS | data+sidecar | 22.4 | 11.15 |
| macOS APFS | data+sidecar+dir | 21.7 | 11.53 |
| macOS APFS | data+sidecar+dir, dir batched /6 | 23.3 | 10.73 |
| macOS APFS | data+sidecar+dir, dir batched /128 | 24.0 | 10.41 |
| dgx-03, node-local tmp | none | 1260.5 | 0.198 |
| dgx-03, node-local tmp | data only | 256.6 | 0.974 |
| dgx-03, node-local tmp | **data+dir (shipped)** | **339.0** | **0.737** |
| dgx-03, shared project fs | none | 8.1 | 30.875 |
| dgx-03, shared project fs | data only | 8.8 | 28.567 |
| dgx-03, shared project fs | data+dir | 8.6 | 29.038 |

The macOS run carried its own caveat — Java `force(true)` maps to `F_FULLFSYNC` there, flushing the
physical drive cache, so the file recorded that the numbers were worst-case and MUST be re-measured
on the deployment host. The dgx-03 run settles it.

Four findings.

1. **The shipped barrier costs 0.737 ms per fragment on Linux node-local storage at 339 MB/s**, not
   the 6.14 ms measured on macOS — the laptop figure is pessimistic by about 8×. `BlockStore.put`
   needs no batching redesign. The cost is per-call, not per-byte: 1 MiB fragments cost the same as
   256 KiB.
2. **The sidecar sync is dropped.** It is about half the macOS barrier cost (11.15 ms with it against
   6.14 ms without) and buys durability only for reconstructible data. The shipped barrier is data
   fsync + directory fsync. Batching the directory sync recovers ~10% on macOS and is not needed at
   the Linux cost. `data+dir` measuring marginally faster than `data` alone is noise, not an
   inversion.
3. **On the shared project filesystem throughput is 8.1–8.8 MB/s regardless of the barrier** — the
   network round-trip dominates so completely that fsync is free. A storage node gets 339 MB/s or
   8 MB/s depending on nothing but where `root_path` points: a **40× cliff invisible to
   `bindingKind`, `mediaClass` and `node_class`, all three of which are identical across the two
   paths.** This is the argument for a measured commissioning write rate in the locus descriptor
   rather than a declared node class.
4. The results file draws one further conclusion from that cliff: it is a strong argument for
   container aggregation before the filesystem.

**Unresolved by this campaign:** whether `fsync` on a network filesystem is a durability barrier at
all. All three barrier settings measured within 8% of each other there, with the no-barrier case
nominally the slowest, so the measurement cannot distinguish a real barrier from a no-op. The fs
binding returns `DURABLE` on the strength of `fsync` returning zero. Settling it needs a power-cut or
server-kill test that has not been run. Nothing here measures the *durability* of either path — only
its rate.

## Measured: the plant delivers 11.9–45.0 PB/yr, and clustering is a precondition (2026-09-19)

Simulated plant, no hardware. Harnesses and raw results in `eval/results/plant_sim.json` and
`eval/results/plant_contention.json`. Model: 9 drives, 90 s mount (σ 15%), 20 s unload, 172 s
full-length pass, 400 MB/s, 30 TB cartridge, first-order serpentine cost, 240 cartridges, 2,000
requests of 4 GiB over 24 h with 8 h deadlines.

### Utilisation is inverted; GB per drive-hour is the honest metric

| workload | policy | drive-hours | GB/drive-hour | GB/mount | payload |
|---|---|---|---|---|---|
| scattered | reactive | 117.5 | 68.1 | 4.0 | 4.8 % |
| scattered | batching+order | 46.4 | 172.3 | 13.3 | 12.3 % |
| clustered | reactive | 115.0 | 69.5 | 4.2 | 4.9 % |
| clustered | batching+order | **12.2** | **653.3** | **111.1** | 46.5 % |
| hot | batching+order | 23.6 | 339.3 | 27.6 | 24.1 % |

The reactive plant shows *higher* drive occupancy because it wastes drive-seconds on mounts. A
capacity figure computed as drives × 400 MB/s × hours overstates the **reactive** plant by ~20× and
the best **clustered** sustained case by ~1.7×.

### Payload rises with load — duty is an output, not an input

| offered | payload | late |
|---|---|---|
| 7.8 TiB/day | 46.5 % | 0 % |
| 39.1 | 72.0 % | 0 % |
| 78.1 | 77.5 % | 0 % |
| 156.3 | 80.5 % | 0 % |
| 312.5 | 82.1 % | **25.6 %** |

Deeper queues amortise each mount, so **deadlines and coalescing are not in conflict at feasible
load** — which half-refutes our own worry that deadline scheduling must destroy bytes-per-mount. What
destroys it is *reactive* dispatch (4.0 GB/mount).

### Delivered capacity, every workload against one 78,840 drive-hour budget

Standing obligations are cheap — annual scrub **6.5%** of the plant-year, a repack at 85% dead (15%
live) **1.9%**, committed **8.5%** — because they are sequential whole-cartridge passes. A site
rebuild is **6,763 drive-hours = 8.6%**: long in **duration** (~7 weeks), modest in **drive-hours**.
Retrieval is the entire cost:

**Delivered after scrub and repack: 11.9 PB/yr scattered, 23.4 PB/yr hot, 45.0 PB/yr clustered** —
against ~96–101 PB/yr claimed. At 100 TB/day scattered the plant is **oversubscribed 2.75×**; no
scheduling policy fixes it.

**The two harnesses disagree, and it is not reconciled.** `plant_contention` scales the 7.8 TiB/day
operating point linearly and gets 45.0 PB/yr clustered; `plant_sim`'s own load sweep measures the
rate rising with queue depth and concludes ~156 TiB/day sustained ≈ **57 PB/yr**. ~1.3× apart. Both
retire the claimed figure; neither is yet the number.

### What this deletes, and what it makes a prerequisite

- **Every drives × rate × hours capacity figure is struck** — `SPECIFICATION.md` §14.1's 82.7 PB/yr,
  `TAPE-RESEARCH-PROMPT.md` check 1's 96.5 PB/yr (101.2 in MiB/s), check 3's 35.9, check 4's
  98 TB/day.
- **Utilisation targets are struck**; GB per drive-hour replaces them.
- **Clustering is a precondition, not an optimisation** — 3.8× on top of batching and media-ordering,
  and the difference between 126.2 and 33.3 TB/day delivered. **Mining co-occurrence from a real
  request log (the simulation's own stated limit) is therefore a prerequisite for sizing, not a
  refinement**, and `pack_hint` being mandatory is the load-bearing decision in the write path.
- **Media load-cycle life binds before drive-hours on anything but a clustered workload**: at the
  measured bytes-per-mount and full delivered capacity the plant needs 1,687 loads/cartridge-year
  clustered (84% of the 2,000 budget) but 3,525 hot and 3,716 scattered (176%, 186%).

**Model limits, stated:** retrieval only — no write path, no scrub, repack or repair contention;
synthetic cartridge assignment; Gaussian 90 s mount against a reported bimodal 60–120 s; first-order
serpentine; no EOM, no error injection, no drive failure. **Unit caveat:** `plant_sim`'s "GB" is 2³⁰
in its request arithmetic and reads as 10⁹ in its rate conversions, putting ~7% on every MB/s derived
from it; quote GB per drive-hour, not MB/s. **And every figure here is measured relative to modelled
mount constants** — both harnesses assume a 90 s mount, while `SPECIFICATION.md` §3.4 settles the
planning figure at `O = 265 s` and records that a 45% error in `O` moves plant output ~23%. The
harnesses should be re-run at `O = 265 s`; until they are, these figures are optimistic in the same
direction as the documents they correct.
