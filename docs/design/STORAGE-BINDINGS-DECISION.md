!!! success "Status: Mostly current"
    The one-interface-many-media binding decision and its findings table. Current except the Bareos-specific parts and stripe latency-class homogeneity, which replication makes unnecessary for replicated copies.

# THE DECISION — Storage Bindings: NAS, Block and Tape

**Status:** Decided. Supersedes the binding question raised against `filerepo`.
**Scope:** `io.cresco.gfs`, `io.cresco.filerepo`, and the tape plant.
**Premises:** no filesystem on the media (unchanged). ~~`st` + SG_IO passthrough, not a device driver~~ — **SUPERSEDED 2026-09-19**: Layer 0 is Bareos (`BAREOS-RECOMMENDATION.md` §1; `SPECIFICATION.md` §2.1). We issue no SCSI on any data path; the only SCSI retained is `gfs-probe`'s five read-mostly opcodes, between jobs, for diagnostics. The label "settled, not relitigated here" is withdrawn with it — it instructed every reader not to question a premise that has since been overturned.

---

## 1. The answer

> **RETIRED 2026-09-19 by `BAREOS-RECOMMENDATION.md` §1 and §12, and `SPECIFICATION.md` §2.3.** Under the owner's division `gfs-mover` is **deleted rather than replaced**. Bareos (`bareos-dir` + `bareos-sd` + `bareos-fd` + PostgreSQL) owns drives, changer, reservation, framing, filemarks, end-of-medium and sense classification. What survives on our side is **`gfs-probe`**: non-root, read-mostly, five-opcode allowlist (`INQUIRY`, `LOG SENSE`, `MODE SENSE`/`MODE SELECT`, `READ`/`WRITE ATTRIBUTE`, `SECURITY PROTOCOL IN`), running only between jobs on a drive Bareos is not holding. No JVM thread and no process we write can issue `WRITE(6)`, `LOCATE(16)`, `MOVE MEDIUM`, `PERSISTENT RESERVE IN/OUT`, `FORMAT MEDIUM` or `ERASE`. **The containment argument survives; the artefact that carried it does not.** No replacement headline slogan is minted here — the original is struck, not rewritten into a new claim.

~~**One plugin. One SPI. Two processes. Three bindings.**~~

`gfs` carries all three bindings as one artefact: `gfs_roles += plant`, `binding = fs | block | tape`. There is no second bundle. What *is* separated is not the plugin but the **process**: no JVM thread ever issues a SCSI CDB. ~~A separate OS process, `gfs-mover`, holds `CAP_SYS_RAWIO` and the device nodes behind a fixed command allowlist, and the plugin speaks to it over a local socket.~~ *(2026-09-19: the no-JVM-CDB invariant stands and is now stronger — no process we write issues a write-path CDB at all. The `gfs-mover` sentence is retired per the note above.)*

### The single argument that settles it

The question was asked as *"can one interface be implemented by three media without lying?"* That is the wrong test, and every position that passed it still produced a design that breaks. The test that decides is **"can every caller be written without branching on the binding?"** — and against the callers that actually exist, nothing passes it, because the difference between the media is a fact about *time*, and no interface can hide a fact about time from a caller that has a timeout in it.

So the difference must be **declared as a value the caller reads**, not concealed behind a signature. Once you accept that, plugin count stops being an architectural question and becomes a packaging question — and on packaging, Cresco settles it against a split:

- A Felix bundle is a classloader, not a privilege domain. Every plugin runs in the agent's single JVM. Raw SCSI requires a process-level capability, so the moment that JVM can issue a CDB, every bundle in it can. `PluginAdmin.startPlugin` (controller, ~line 1336) sets `pluginService.setIsActive(true)` **unconditionally**, even when `isStarted()` returned false and it has just recorded `statusCode = 7`. A second bundle that fails to claim a changer therefore reports *active*, registers no HealthCheck (gfs registers it only on the success path), and silently drops every message (`PluginBuilder.msgIn` dispatches only `if (executor != null)`). "Separate bundle = separate blast radius" is false in the only direction that matters.
- The role boundary a second bundle would draw is **already drawn in config**. `gfs` is one bundle with comma-separable roles (`gfs_roles`, default `storage`) and per-action gating through `noRole()` returning status `9` (`gfs/ExecutorImpl.java:288` and the switch at 298–397). Adding `plant` to that enum buys the entire asymmetry — the plant surface has no byte-returning read, the store surface has no mount queue — for a config value.
- A second bundle costs a repo, a CI pipeline, a Central Portal coordinate and a second pass of the three-step ship chain, and creates a version-skew surface on the `Locator` encoding that the index persists.

~~**The boundary that buys containment is `gfs-mover`.** It is a deployment artefact, not a plugin, and it is the thing the "separate plugins" instinct was correctly reaching for.~~ **RETIRED 2026-09-19, see the note at the head of this section.** The boundary that now buys containment is the Bareos process set plus `gfs-probe`; the reasoning above — a Felix bundle is a classloader, not a privilege domain — is unaffected and is why the boundary had to be a process in the first place.

---

## 2. What the extent framing survives as

It survives — at the index layer, where ENTAIL already put it — after **three subtractions and one addition**.

**Subtracted: no verb returns bytes on the calling thread.** This is not a concession to tape; it is a description of what gfs already does. `NodeAgent.getFragment` reads the fragment, pushes it on `FrameBus`, and returns an ack meaning *sent*; `encode`/`restore`/`repair` return a `job_id`. `filerepo.getFile` is the outlier and already refuses above `max_inline_bytes` (default 524 288) with `status=5, "use streamfile"` (`filerepo/ExecutorImpl.java:157, 505-509`). A synchronous action that *declines* when the medium makes synchrony untrue is shipped code in this tree. Tape's threshold is zero.

**Subtracted: `delete` is not a binding method on any medium.** See §4.

**Subtracted: there is no `list`, no `scan`, no `clear`.** A binding never discovers its own contents by traversing the medium.

**Added: latency class is a declared field on the fragment reference, and placement enforces stripe homogeneity.** Without this the SPI is honest and every caller is still wrong.

---

## 3. The SPI

> **Three interfaces, not one — recorded 2026-09-19.** The document set now declares *the* SPI in three places, with three disjoint vocabularies, and §1's "One SPI" is **withdrawn**.
>
> - `VolumeMover` (`BAREOS-RECOMMENDATION.md` §2) is **Layer 0**, per `SPECIFICATION.md` §2.1: one volume, one loaded medium, `attach`/`stage`/`commit`/`fetch`.
> - The ten-call block plane (`SPECIFICATION.md` §5.1) is **Layer 1**, per that document's own §5 heading: parcels on one volume, synchronous against a handle the plant scheduler already arranged — "no queue, no ETA, no job, no async in this layer".
> - `ExtentBinding` below is asynchronous by construction (§2: "no verb returns bytes on the calling thread") and its verbs (`intend`/`plan`/`enqueue`/`ticket`) are plant-scheduler and materialisation verbs — **but no document assigns it a layer, and none states how the three compose. That is recorded here as an open hole (§9 A-7), not filled.**
>
> **Method-name collisions are real and must be disambiguated by layer in every reference:** this document's `append`/`seal` are *not* §5.1's `append`/`seal`, and `reclaim(extentId)` is not §5.4's `retire(VolumeId)`.

`io.cresco.gfs.extent` — interfaces and plain classes only. **No Java records** (the ClassIndex processor breaks CI).

```java
public interface ExtentBinding {

    /** Pure. Never touches the medium. Re-published on every capability change. */
    LocusDescriptor describe();

    /** Local catalogue only, by contract. Never mounts, never stats the medium. */
    Residency locate(String extentId);

    // ---- read: standing demand, then admission, then delivery ----

    /** Enrol demand the fabric can coalesce. The tape scheduler's real input. */
    String   intend(ReadIntent intent);              // -> intentId
    Intent   intentStatus(String intentId);
    void     withdrawIntent(String intentId);

    /** Pure: catalogue + declared cost model. No device I/O, no cross-site RPC. */
    Plan     plan(ReadRequest req);

    /** Admit (feasibility only) then enqueue. Returns in ms on every binding. */
    Ticket   enqueue(ReadRequest req);               // -> Ticket | Refusal-bearing Ticket
    Ticket   ticket(String ticketId);
    void     cancel(String ticketId);                // post-condition defined per §6

    // ---- write: ticket is the container; NAS container is one extent ----

    WriteTicket beginWrite(WriteHint hint);
    /** Returns a PROVISIONAL ref with its real address NOW, and journals it. */
    ExtentRef   append(WriteTicket t, ByteSource src, String sha256);
    /** Durability barrier. DURABLE is set only when this ticket completes. */
    Ticket      seal(WriteTicket t);
    void        abandonWrite(WriteTicket t);         // may be a tombstone, not a no-op

    // ---- lifecycle: reclaim is accounting, not erasure ----

    Reclaim     reclaim(String extentId, ReclaimReason why, String token);
    Reclaim[]   reclaimAll(String[] extentIds, ReclaimReason why, String token); // capped, enumerated

    // ---- verification: depth is chosen by the caller and priced by the binding ----

    Verification verify(String extentId, VerifyDepth depth);   // CATALOGUE only, free, sync
    Ticket       enqueueVerify(VerifyScope scope, VerifyDepth depth);

    /** Explicitly expensive, explicitly scheduled. The honest replacement for `list`. */
    Ticket       reconcile(String mediumId);
}
```

### Types, in full

```java
final class ExtentRef {
    String extentId;        // content-addressed for integrity and stable naming; NOT a dedup key.
                            // 2026-09-19: flagged deliberately. This is the one place in the set
                            // where "content-addressed" has no relation to deduplication, and an
                            // editor executing the dedup retirements must NOT cut it. The same
                            // protection applies to the sibling sha256, to leaf_root, the per-chunk
                            // AEAD tag, cid = HMAC(K_mid, ...), HMAC(K_bnd, ...), xid, and the
                            // fragment id. No measurement bears against any of these: the
                            // measurements say identical content does not RECUR across objects,
                            // not that a hash of content is an unsound name or integrity check.
    String bindingId;
    String opaque;          // binding-private. The index stores bytes and NEVER parses it.
    String latencyClass;    // MS | SECONDS | MINUTES | HOURS   <-- the declared branch
    long   lengthBytes;
    String sha256;
    long   lockEpoch;       // fencing token (§6)
}

final class Residency {
    enum Presence { PRESENT_VERIFIED, PRESENT_CLAIMED, EXPORTED, ABSENT, UNKNOWN }
    Presence presence;
    long     asOfEpochMs;         // staleness of the claim
    boolean  requiresMount;
    long     firstByteP50Ms, firstByteP95Ms;
    String   custodian;           // EXPORTED only
    String   failureDomain;       // slash-path; index groups by prefix
}

final class ReadIntent {
    String[] extentIds;
    long     earliestEpochMs, latestEpochMs;
    String   lane;                // CLINICAL | INTERACTIVE | BATCH | BACKGROUND | OBLIGATION
    String   onInfeasible;        // WAIT | DEGRADE | WITHDRAW
    String   coalesceKey;
    String   purposeId;
    String   token;
}

final class ReadRequest {
    String[] extentIds;           // batched BY CONSTRUCTION; a single read is a batch of one
    long     deadlineEpochMs;
    String   lane;
    boolean  orderSensitive;
    String   sinkId;              // where bytes land; never a return value
    String   purposeId;
    String   token;
}

final class Plan {
    String   planId;
    Batch[]  batches;             // Batch { groupKey, extentIds[], estMs }
    String   conservedResource;   // "bytes" | "iops" | "drive_seconds"
    long     resourceUnits;
    long     estWallP50Ms, estWallP95Ms;
    String   basis;               // MEASURED | MODELLED | ASSUMED  (+ model error)
    boolean  advisory;            // ALWAYS true. Never a reservation.
    Refusal  refusal;             // null if admissible
}

final class Refusal {
    String bindingConstraint;     // PLEDGE | PLANT | POLICY | COVERAGE | DEGRADED_PLANT | PRESENCE
    Map<String,Object> arithmetic;
    Rewrite[] rewrites;
    long   retryAfterEpochMs;     // MANDATORY. A refusal without this is an invitation to poll.
    String intentId;              // demand enrolled, not discarded
}

final class Ticket {
    String id, lane;
    enum State { QUEUED, PLACED, SCHEDULED, MOUNTING, STREAMING, PARTIAL,
                 DRAINING, DONE, FAILED, REPLANNED, CANCELLED, PLANT_DEGRADED }
    State  state;
    int    queuePosition;
    long   projectedStartMs, revisedHorizonMs;
    long   batchFrontier;         // durable checkpoint: batches completed (§6)
    Failure[] failed;
    Refusal   refusal;
    long   plantDegradedUntilMs;
}

final class Failure {
    String extentId, opaque;
    enum Cause { MISSING, DEFERRED, OFFLINE, MEDIUM_ERROR, WRONG_POSITION, HASH_MISMATCH,
                 SHORT_TRANSFER, DEFERRED_WRITE_ERROR, EOM_REACHED, DATA_PROTECT,
                 DRIVE_FAULT, CLEANING_REQUIRED, UNKNOWN }
    Cause  cause;
    String senseDetail;           // sense key / ASC / ASCQ, verbatim
    long   symbolOrdinal;         // from OUR bookkeeping, not from sense INFORMATION (§7)
}

final class Reclaim {
    enum Kind { UNLINKED, CRYPTO_SHRED_ONLY, TOMBSTONED, REFUSED_APPEND_ONLY }
    Kind   kind;
    long   bytesReclaimed, bytesUnreclaimable;
    Long   mediumExpiryEpochMs;   // when the last copy physically ceases to exist
}

final class Verification {
    enum Result { VERIFIED, BELIEVED, UNKNOWN, FAILED }
    Result result;
    long   lastVerifiedEpochMs;
    long   verifyCostUnits;       // what a deeper check would cost, in conservedResource
}

enum VerifyDepth { CATALOGUE, PRESENCE, MEDIA_READ }
enum ReclaimReason { POLICY_EXPIRY, REDACTION, GC, REPLACED }
```

**Wire form.** Extent-id arrays, batch lists and failure lists travel as `setCompressedParam`, following `NodeAgent.hasFragments`' `frag_ids`. Plan ids, counts and cost scalars are plain params. A request exceeding the cap returns a `Refusal`, never an oversized `MsgEvent`.

**Authorisation.** `reclaim`, `reclaimAll` and `reconcile` take a token verified with `CryptoBox.verifyToken` against `gfs_secret`, with `op`, the extent-id set hash, an expiry and the authorising user in the claims — the `NodeAgent.custodyGet` pattern. `noRole()` answers *"am I this kind of node"*, never *"may you ask me this"*, and a `REDACTION` that nobody authorised is a deletion with a paper trail attached.

---

## 4. Each medium, without lying — and what tape does about delete

| Method | `fs` | `block` | `tape` |
|---|---|---|---|
| `describe` | static + live concurrency | static + live concurrency | live: drives in pool, changer state, reserve |
| `locate` | catalogue hit; `PRESENT_VERIFIED`; `requiresMount=false` | extent table; `PRESENT_VERIFIED` | catalogue + changer inventory epoch; `PRESENT_VERIFIED` if barcode seen in an element this epoch, else `PRESENT_CLAIMED`; `EXPORTED` with custodian; `requiresMount=true`; p50 ≈ 90 000 ms |
| `intend` | accepted, horizon irrelevant | same | the real input: coalesced by `(coalesceKey, barcode, window)` |
| `plan` | one batch, `bytes`, len/rate | + alignment rounding | group by barcode, order within by absolute position; `drive_seconds`; forty scattered reads → one batch per cartridge |
| `enqueue` | Jobs pool; usually DONE before first poll | same | scheduler coalescing window; `MOUNTING` with a position |
| `append` | write temp, **fsync**, `ATOMIC_MOVE`, **fsync dir**; provisional ref = final ref | write + flush | one `write(2)` per record via the mover; provisional ref from `READ POSITION`; journalled before the next record |
| `seal` | vacuously satisfied — nothing is staged, ticket returns DONE *(sound on node-local storage; **open on a shared filesystem — see the note at the end of §5**)* | same | real: close container, single filemark (`Immed=0`), read back and verify per-symbol hashes, **then** DURABLE |
| `reclaim` | `UNLINKED` | `CRYPTO_SHRED_ONLY` by default; `UNLINKED` only with discard-and-verify proven | `TOMBSTONED` + `mediumExpiry`, or `REFUSED_APPEND_ONLY` |
| `verify(CATALOGUE)` | `VERIFIED` (it *is* the medium) | `VERIFIED` | `BELIEVED` — never `VERIFIED` |
| `verify(PRESENCE)` | sentinel + stat | device identity | `READ ELEMENT STATUS` — seconds, **no mount** |
| `verify(MEDIA_READ)` | rehash, cheap | rehash | a mount; scheduled, budgeted, never timed |
| `reconcile` | rewalk root | rescan extent table | one mount per cartridge, backward-linked container footers |

Vacuous satisfaction (`seal` on disk) is not false satisfaction. That distinction is the line between a harmless no-op and a lie.

### Delete

**Tape does not implement delete, and is never asked to. Neither is disk.**

`delete` is not a method on any binding, because erasure was never a storage operation in a system that encrypts at the origin. Erasure is **key destruction**: once, for the whole object, at the key layer that already exists — `SiteKeys`, `NodeAgent.siteKeyDelete` (which already requires `confirm=yes`), and `t`-of-`n` Shamir custody. A holding site is blind, so from that site's own point of view the shred is complete without touching the medium.

What remains below the line is **reclamation of capacity**, and that is accounting:

- **NAS** — `UNLINKED`, `bytesReclaimed = len`. `Files.deleteIfExists` plus sidecar.
- **Block** — `CRYPTO_SHRED_ONLY` by default, because freeing an LBA range does not make the bytes unreadable to anyone holding the raw device. `UNLINKED` only for a binding configured with discard-and-verify that has read back zeros. The weaker honest claim is the default.
- **LTO WORM** — `TOMBSTONED`, `bytesReclaimed = 0`, `bytesUnreclaimable = len`, `mediumExpiry = <cartridge retirement epoch>`. The row is marked dead; the ciphertext stays until the cartridge is destroyed.

Three consequences that make this honest rather than cosmetic:

1. `LocusDescriptor.capacity` carries `unreclaimableTombstoned` as its own term, so a tape locus at 80 % with 30 % tombstoned does not present to placement as a disk with headroom.
2. `ReclaimReason` travels to the binding, because a `REDACTION` answered `TOMBSTONED` is a governance event — a redaction that cannot be executed on the medium is a **fact**, not a failure.
3. `retire()` may only answer `TOMBSTONED` for a cartridge whose WORM status was **read from the medium** at commissioning, never from a config file. A rewritable cartridge in a pool configured as WORM would otherwise let the system tell the governance layer that a redaction is physically permanent when the bytes are erasable.

And the corollary that costs nothing and is worth having anyway: `BlockStore.delete()` and the `delfragment` action are **already misnamed on disk**. They are reclaim. Renaming them is a one-line change that stops an operator believing bytes are gone when only a local copy is.

**There is no `clearRepo`.** No wildcard, no scope-level delete, no directory. `reclaimAll` takes an explicit, capped, token-authorised enumeration. A plant retires a cartridge by *draining* it — repairing its contents elsewhere from global parity, then marking the barcode retired — which takes hours, is scheduled, is refusable, and leaves a receipt.

---

## 5. `filerepo`: unchanged, and explicitly out of the storage path

**Not the NAS binding. Not a thing to retire. Kept, running, and declared out of scope.**

The code settles it three ways:

1. **It is a directory mirror with a jar repository attached.** Of its seventeen actions, nine are directory replication (`repolist`, `getrepofilelist`, `repolistin`, `repoconfirm`, `putfilesremote`, `putfiles`, `getscandir`, `removefile`, `clearrepo`), two are plugin-jar distribution (`getjar`, `putjar`), three move bytes. Its Derby catalogue is keyed by absolute `filepath`. Its scanner diffs a directory every `scan_period`, default **15 000 ms** (`RepoEngine.java:114`).

2. **`clearRepo` is the operation that must never be inheritable.** `RepoEngine.java:716-749`: wait on the `inScan` gate, delete every catalogued row and its file, then `Files.walk(getRepoDir())` `.filter(Files::isRegularFile)` `.map(Path::toFile)` `.forEach(File::delete)` over everything else. For a mirror that is *correct* — idempotent, refilled from the producer on the next broadcast. For durable storage it is unrecoverable. The containment is not to guard it; it is to keep it inside a plugin where it stays correct, and to ensure no durable binding ever inherits the path-shaped surface that makes it expressible.

3. **It is not retirable on any timeline that includes deploying its replacement.** `agent/src/main/resources` embeds `filerepo.jar` alongside `controller`, `core`, `executor`, `library`, `logger`, `repo` and `stunnel`. `gfs.jar` is not embedded. `filerepo` is part of the bootstrap that would deliver a plant bundle to the host wired to the changer.

**The `fs` binding is new code** — `io.cresco.gfs.extent.fs.FsBinding` — and it is `BlockStore` promoted behind the SPI, not `filerepo` adapted. `BlockStore` is already the honest core: `fragPath()` validates `[A-Za-z0-9._-]{1,128}` and resolves flat under root with no directory shape; `put()` is verify-then-store; the sidecar carries size/sha256/owner_site; `scrub()` rehashes against it. Two things must change and one must be added:

- `get(fragId) -> byte[]` (`Files.readAllBytes`) retires in favour of `enqueue`/`ticket` + dataplane delivery. This is the one method that cannot survive.
- `has(fragId)` (`Files.isRegularFile`) becomes catalogue-backed `locate()` + `verify(PRESENCE)`.
- **`put()` gets a durability barrier.** There is no `fsync`, no `FileChannel.force`, and no `SYNC`/`DSYNC` anywhere in the gfs module — verified by grep over `src/main/java`. `Files.write(tmp)` + `ATOMIC_MOVE` is atomic with respect to *readers*; it does not persist the data or the directory entry. So the fs binding's `DURABLE` is **already false today**, and it is the same lie shape the two-state write receipt exists to prevent on tape. `fsync` the temp file and `fsync` the containing directory after rename, before returning `DURABLE`.

  **Measured** (`eval/results/fsync_cost.json`, 2026-09-19, 256 KiB fragments, 200 writes): the shipped barrier — data fsync + directory fsync — costs **0.737 ms per fragment at 339 MB/s** on a Linux node-local path (dgx-03 compute node), against 6.14 ms on macOS, where Java `force(true)` maps to `F_FULLFSYNC`. The cost is per-call, not per-byte. **No batching redesign is needed.** **The sidecar is deliberately not synced**: adding it took the macOS barrier from 6.14 ms to 11.15 ms — about half the total — and it carries only reconstructible data. Do not add it back. The barrier is affordable only on node-local storage; see the fourth deployment invariant below.

**Three deployment invariants**, enforced as refusals in the binding (a Felix HealthCheck only *reports*, is cached and grace-sticky ~60 s, and gfs registers it only on the success path):

- No binding root and no tape staging directory may lie under any `filerepo` `scan_dir` or `repo_dir`. Ask every co-located `filerepo` for `getscandir` at start and on config change; if the path is under one, refuse the drive-touching actions and report CRITICAL — while still starting (§9, F-13).
- Extend the same rule to `PublisherEngine`'s `root_path`. `readCatalog()` pages `getrepofilelist` every `export_period_ms` (default 10 000) and calls `Files.isRegularFile(ap)` on **every row** to filter deletions (`PublisherEngine.java:91`) — timer-driven per-object contact with the medium, free on a NAS, and precisely the pattern banned at the binding layer. State the rule as a property: *no timer-driven per-object medium contact anywhere in the stack, by any plugin.*
- Better than the directory rule: **remove the window**. The source copy is retained until seal-and-verify flips a container to DURABLE, so the staging area is never the only copy.
- **A binding root's rate is measured, not declared (added 2026-09-19).** At start and on config change the binding writes and fsyncs a short sequence of fragment-sized blocks at `root_path` and records the achieved rate into `LocusDescriptor.sustainedBytesPerSec` (§7), so the descriptor reports what the path did rather than what the node was configured to be. Basis: `eval/results/fsync_cost.json` — the same Linux host delivers **339 MB/s at a node-local path and 8.1–8.8 MB/s at the shared project filesystem**, with `bindingKind`, `mediaClass` and `node_class` identical across both. The 40× is determined solely by where `root_path` points and is invisible to every declared field. **What a low measured rate should cause is not decided here** — no floor is configured, and the arbitration between a measured rate and a declared `latencyClass` is recorded as an open hole in §7.

**Open, not resolved (2026-09-19): whether `fsync` on a network filesystem is a durability barrier at all.** On node-local storage the vacuous `seal` of §4 is sound and cheap — the barrier is in `append` and costs 0.737 ms per fragment. On the shared project filesystem the measurement cannot tell a real barrier from a no-op: **8.1 MB/s with no barrier, 8.8 with data fsync, 8.6 with data+dir**, all within noise of one another and with the no-barrier case nominally the slowest (`eval/results/fsync_cost.json`). The results file reads that as the network round-trip dominating so completely that fsync is free; it is equally consistent with fsync being satisfied from a server-side cache, and the measurement cannot separate the two. The fs binding returns `DURABLE` on the strength of `fsync` returning zero, and **we have not verified that a network filesystem's fsync is a durability barrier at all.** Recorded as an unanswered question, not repaired here: answering it needs a power-cut or server-kill test we have not run.

---

## 6. The mount scheduler

**Inside the `plant` role, in-process with the mover socket, one instance per medium changer — not per site and not per drive.** The changer is the arbitration unit: two schedulers issuing `MOVE MEDIUM` to one robot puts a cartridge in the wrong drive, which is a correctness failure, not a slowdown. A site with three drives behind one library has one scheduler owning all three. A site with two independent libraries has two schedulers with no coordination, because they share nothing conserved.

It runs on its own dedicated thread. The plugin's `MsgEvent` handlers only `intend`, `plan`, `enqueue` and read cached state; they never touch a device, because `executeEXEC` runs on `PluginBuilder`'s `msgInProcessQueue` — `max(4, cores)` threads, 1024 queue, **CallerRunsPolicy** — so four blocking ioctls saturate the pool and the fifth runs on the JMS delivery thread, stalling the agent's inbound control plane. That is the shape of W-GFS-6.

### Fencing, in order of authority

1. ~~**SCSI Persistent Reserve is the authority.** `PERSISTENT RESERVE OUT` — register with a per-host key, then reserve `EXCLUSIVE ACCESS – REGISTRANTS ONLY` — on the changer LUN **and on every drive LUN**. Takeover after a dead host is `PREEMPT AND ABORT`.~~ **RETIRED 2026-09-19.** `PERSISTENT RESERVE IN/OUT` is not a reachable opcode in any process we write (`BAREOS-RECOMMENDATION.md` §1), and SCSI Persistent Reserve is listed under *Deleted outright* in `SPECIFICATION.md` §2.3. Authority becomes **operational rather than protocol**: exactly one changer initiator, `bareos-sd` (`BAREOS-RECOMMENDATION.md` §8, finding F-C), and exactly one submitter to the Director, the plant scheduler. `PREEMPT AND ABORT` has no referent. **HOLE: single-host-per-changer becomes a deployment rule with no enforcement, and multi-host fencing is unsolved — `BAREOS-RECOMMENDATION.md` §11.3 states the STONITH procedure "is owed now" and it exists in no document** (recorded as §9 A-8). The rest of the original reasoning is preserved because it is still why no cheaper mechanism works: `O_EXCL` does not do the job — it is a block-device property, `/dev/sg*` is a character device, and neither crosses hosts; a Java `FileLock` is per-OS-file and would make the singleton depend on the NAS binding being mounted; `st` takes no reservation at all; and **the drives, not the changer, are where the data loss happens**.
2. **The lease epoch is the reservation key.** A monotonic epoch, persisted locally and recorded in every container header and on every `objectupdate`/`repairupdate`. `PREEMPT` is permitted only on presentation of an epoch strictly newer than the reserving key, so recovery-after-death and theft are distinguishable after the fact. The index rejects any update bearing a stale epoch.
3. **The index lease is advisory bookkeeping, and the failure rule is inverted.** `registernode` gains `(site, library_serial, library_partition_id)` — read from `INQUIRY`/`REPORT ELEMENT STATUS`, *not* a changer serial, because one physical changer with two library partitions exposes two changer LUNs with disjoint drives and two schedulers over them are legitimate. But the lease **never authorises a robot move**, because `IndexEngine` has one statically-configured writable primary (`index_primary`, line 105; replicas throw at line 195) with no election, so fail-closed on lease renewal turns an index outage into a *global* tape outage — including during the disaster restore the tape tier exists for. Therefore: **fail-closed on the reservation, fail-static on the lease.** A holder that cannot renew but still holds an uncontested reservation completes admitted work and refuses only *new* admissions. It drains only on a reservation conflict or unit attention.
4. **Renewal is on its own thread.** Never `NodeAgent`'s `Timer` — which is single-threaded, runs `tick()` and `scrubAndReport()` on the same thread, and makes blocking `rpc.call(..., 10000)` and `rpc.call(..., 8000)` *on the timer thread* (`NodeAgent.java:79-110`). One scrub over a few hundred GB blows a 15 s TTL and, worse, pushes the node past `lost_ms` (25 000) and starts a repair storm. **That is a live bug for disk nodes today**, independent of tape.

### Policy

Standing demand from `intend`, coalesced by `(coalesceKey, barcode, window)`; waves formed per cartridge group; within a mount, ordered by **absolute logical object position** — stated honestly as an approximation to physical order, since LTO is serpentine and ascending LBA is not ascending physical position. `GENERATE`/`RECEIVE RECOMMENDED ACCESS ORDER` sits behind a descriptor flag and is a procurement input.

**Preemption is cartridge-atomic only.** Stripe-boundary preemption was considered and rejected: resuming a preempted cartridge costs another mount plus a reposition, so a clinical order's bound is bought by silently invalidating every other already-published window. `Batch` completion is the durable checkpoint, so a drive lost mid-wave costs at most one cartridge's sweep. `cancel()` is defined as *unload, re-inventory before the next write, return the batch boundary reached*.

**Admission is feasibility only, and never refuses without enrolling demand.** Coverage, pledge, plant residual after the obligation reserve, policy. `plan()` is `advisory: true`. A refusal carries `retry_after` **and** an `intentId` — demand is enrolled, never discarded. Reject-and-discard was considered and rejected: it deletes the standing coalescable demand the economics depend on, and against `repairSweep`'s unconditional 5 s retry it is a livelock, not a refusal.

**The fabric's own obligations are a reserving tenant.** Repair, scrub, proof-of-possession, reconcile and verify consume a published, non-tradeable reserved fraction and **bypass admission entirely**. Durability must never depend on authorisation.

`ReadRequest` has no `maxParallel` field the caller can assert; real concurrency is the scheduler's drive pool.

---

## 7. Locus descriptor, and what changes in `classWeight`/`netFactor`

```java
final class LocusDescriptor {
    long    capabilityEpoch;      // bumped on EVERY capability change; rides the heartbeat
    String  bindingKind;          // FS | BLOCK | TAPE
    String  mediaClass;           // ext4 | zfs | nvme | LTO10-WORM | LTO10-RW
    String  latencyClass;         // MS | SECONDS | MINUTES | HOURS
    long    firstByteP50Ms, firstByteP95Ms;   // MEASURED over last N ops, not declared
    long    sustainedBytesPerSec; // MEASURED WRITE rate, from a commissioning write probe at
                                  // root_path (section 5), and re-probed; never declared.
                                  // 2026-09-19: a shared-filesystem root delivers 8 MB/s where a
                                  // node-local root on the SAME host delivers 339 MB/s
                                  // (eval/results/fsync_cost.json) and no declared field
                                  // distinguishes them. The READ rate is NOT measured by that
                                  // probe; one field cannot yet serve accessCost honestly.
    int     maxConcurrentReads;   // LIVE: owned by the scheduler, not config
    String  conservedResource;    // "bytes" | "iops" | "drive_seconds"
    boolean appendOnly;
    String  reclaimSemantics;     // UNLINK | CRYPTO_SHRED_ONLY | TOMBSTONE_UNTIL_MEDIA_EXPIRY
    long    minWriteUnit, maxExtentBytes, alignment;
    Capacity capacity;            // pledged, used, reclaimable, unreclaimableTombstoned, orphaned
    CostModel cost;               // mountSeconds, repositionSeconds, bytesPerSecond, verifyFactor
                                  // 2026-09-19: these constants are now the input to EVERY capacity
                                  // figure in the document set, and ALL OF THEM ARE MODELLED — the
                                  // plant simulation assumed 90 s mount (sigma 15%), 20 s unload, a
                                  // 172 s full-length pass, 2 s settle and 400 MB/s, against
                                  // SPECIFICATION 3.4's settled O = 265 s. SPECIFICATION 3.4 records
                                  // that a 45% error in the mount cycle moves plant output ~23%, and
                                  // 16 item 1 already makes measuring O the FIRST commissioning
                                  // task. THE HOLE: nothing in this struct or its SPI binds these
                                  // fields to that measurement, records which basis a value came
                                  // from, or distinguishes a commissioned value from a default.
                                  // Recorded, not designed — no mechanism is proposed here.
    double  obligationReserveFraction;
    long    inventoryEpoch;       // last changer inventory; staleness bound for PRESENT_VERIFIED
    String  attest;               // TRUSTED | DEGRADED | UNTRUSTED
    String  plantState;           // READY | NO_HARDWARE | NO_RESERVATION | DRAINING | MAINTENANCE
    long    maintenanceUntilMs;
    String  failureDomain;        // "site:lex/rack:3/host:a" | "site:lex/library:1/frame:2"
    String  scrubModel;           // ONLINE_CHEAP | MOUNT_COSTED
    String  verifyRate;           // FULL | SAMPLED{rate} — per drive model + firmware
    long    lostMsOverride, repairGraceMsOverride;   // per-tier, not one federation constant
}
```

`failureDomain` is a slash-path the index groups by prefix, so a rack and a tape frame are both just domains — and `cartridge` is a first-class level below `host`, because one cartridge carries containers belonging to thousands of objects and a cartridge loss is massively correlated.

### The scoring change

Today (`IndexEngine.java:602-604`):

```java
score(n) = n.pledge * classWeight(n.node_class)
         * (0.5 + 0.5*availability(n)) * (0.5 + 0.5*netFactor(n));
```

with `classWeight` a four-case string switch (`usb-single` 0.4, `desktop-single` 0.6, `server-raid` 0.9, `clustered-fs` 1.0) and `netFactor = min(1, probe_mbps/net_cap_mbps)`, `net_cap_mbps` default 100.0, fed by `probeSweep` every 30 s.

**Three defects, one of which is already a defect for disk.**

1. **One scalar conflates two things.** "How much can you durably hold" and "how fast can you give it back" diverge by five orders of magnitude on tape — and, **measured 2026-09-19, they are anti-correlated on plain disk**. The configuration this document's own ladder ranks most durable, `clustered-fs` at 1.0, is a shared filesystem, and a shared project filesystem measured **8.6 MB/s** where a node-local path on the same Linux host measured **339 MB/s**, with identical `bindingKind`, `mediaClass` and `node_class` (`eval/results/fsync_cost.json`). Rate is not predictable from the attributes the durability ladder keys on, so any single number is wrong for one of its two uses, **and the split is owed to disk before it is owed to tape**. (Only the rate term is measured here; nothing in this campaign measures the durability of either path — §9 A-9.) ~~correlate on disk and~~ Split:

```java
durabilityScore(n) = n.pledge * mediaDurability(n) * (0.5 + 0.5*availability(n));   // placement
accessCost(n, plan)                                                                 // read planning
```

`netFactor` leaves placement entirely. This is a correction for disk too: a slow-NIC `server-raid` node is a fine place to put a durable copy and a bad place to read from, and today's formula cannot say that.

2. **`classWeight` is the wrong axis for tape and becomes a fallback.** The ladder is a *durability* ladder. Adding `case "tape-worm": return 1.0` would make a tape locus win placement for hot objects on a durability argument — correct in the term measured, catastrophic in the term not measured. So: `mediaDurability` reads the descriptor when one is present, falls back to the existing switch when it is not (every node registered today keeps its exact number), and the actual durability arithmetic stays where it belongs, in the coding layer (`SPECIFICATION.md` §8.1 — RS(j,4) local over RS(2,1) global; ~~RS 32+2~~ is superseded, see §8 below).

  **Measured caveat on the fallback, 2026-09-19.** The ladder's top entry, `clustered-fs` = 1.0, names the configuration class a shared project filesystem falls in, and such a filesystem measured **8.1–8.8 MB/s**, while a node-local path on the same Linux host — the kind of path a `server-raid` node at 0.9 presents — measured **339 MB/s** (`eval/results/fsync_cost.json`). The ladder is therefore **throughput-inverted at its top**, and no measurement validates its durability ordering either. It survives only as a placement default for a locus that has not yet returned a descriptor, and **it must never be read as a speed proxy anywhere.** What an unprobed locus should score, and whether it is eligible for placement at all, is not decided here (§9 A-10).

3. **`netFactor` is meaningless for a library and must not be silently reused.** `probe_mbps` for a plant measures the staging host's NIC. Where a network term is still wanted it belongs in `accessCost` as an egress leg alongside mount and reposition. ~~Exclude `PLANT_SCHEDULED` loci from `probeSweep`~~, or relabel the field `staging_net_mbps` in `nodeView` so nobody re-wires it into a decision later.

  **Widened 2026-09-19: this is not a tape-only defect.** `probe_mbps` measures a NIC on every locus kind. A node whose medium measures **8.6 MB/s** — about 69 Mb/s, below the 100.0 Mb/s `net_cap_mbps` default — still scores `netFactor` from a link that is not its constraint, and on a well-provisioned host that score is ~1.0 (`eval/results/fsync_cost.json`; the NIC itself was not probed in that campaign, so this is conditional on the host's link rather than measured). So the fix is defect 1's: **`netFactor` leaves placement for *every* locus kind**, which is strictly wider than the struck per-class carve-out — that narrower remedy is superseded. Relabelling the field `staging_net_mbps` still stands, and `probeSweep` stays a network probe with a network name; the medium's rate comes from the commissioning write probe (§5), never from it.

**And two gates that must change or none of the above operates:**

- `score()` returns 0 for any node whose `roles` lacks `storage`. A `plant` node registers, heartbeats, shows UP in `listnodes` and **receives not one fragment**. Gate on the declared descriptor capability, not a substring match.
> **Unresolved (2026-09-19): a declared `latencyClass` and a measured rate can disagree, and nothing arbitrates.** `firstByteP50Ms`/`firstByteP95Ms` and (per §5) `sustainedBytesPerSec` are measured; `latencyClass` is declared; stripe homogeneity below and the caller's per-stripe deadline (F-1) both key off the declared value. A shared-filesystem locus measured at **8.6 MB/s and 29.0 ms per 256 KiB write** can declare `MS` and be striped with a **339 MB/s** node-local locus (`eval/results/fsync_cost.json`). No rule here says which wins. Recorded as a hole rather than filled: the choice between refusing the declaration, demoting the locus, or refusing the stripe is a design decision, not an editorial one (§9 A-11).

- **`place()` must enforce stripe homogeneity**: the `n` fragments of a stripe share a latency class, enforced the way `domainKey` already enforces failure-domain spread. This is what collapses the caller's branch from per-fragment to once-per-stripe, makes mixed-media k-of-n unrepresentable rather than merely discouraged, and stops `replaceHolder` — a *write-path* handler that re-picks after a 5 s `push_timeout_ms` miss — from permanently migrating an object from milliseconds to minutes because of a transient blip, with no caller deciding it and no record that a class changed.

`availability(n)` is a lifetime cumulative ratio never windowed or decayed, and `registered` survives re-registration — so every maintenance window permanently lowers a plant's placement score and a plant that never services its drives outscores one that does. Make it a decayed window (the code already has the pattern: `probe_mbps` is a 0.7/0.3 EWMA) and exclude declared maintenance from the denominator.

---

## 8. SCSI risk register

> **Re-scoped 2026-09-19 by `SPECIFICATION.md` §2.3 and `BAREOS-RECOMMENDATION.md` §12.**
>
> - **Rows 2–9, 11, 15, 16 and 20 become *configure and assert* against Bareos rather than *implement*.** They are not retired as risks; they stop being code we write.
> - **Row 1's 4 KiB plaintext symbol header is superseded.** It carries `extent id`, `payload hash` and `write epoch` **in the clear on unerasable media**, which is the confirmation-oracle defect of `BAREOS-RECOMMENDATION.md` §5 condition 1 reproduced in our own format. The replacement is the 24 cleartext bytes per parcel of `SPECIFICATION.md` §7.1 (`magic "STELE\0\2" | parcel ordinal u32 | flags u8 | crc32`).
> - **Row 20's fourteen-opcode allowlist is replaced by `gfs-probe`'s five** (`INQUIRY`, `LOG SENSE`, `MODE SENSE`/`MODE SELECT`, `READ`/`WRITE ATTRIBUTE`, `SECURITY PROTOCOL IN`).
> - **Row 12 is an accepted loss, not a design.** We do not own the retry policy (`SPECIFICATION.md` §2.3 cost 2), so a marginal cartridge can consume a drive in a Bareos-internal retry storm and local-parity reconstruction moves from during-the-pass to after-the-error at one extra mount. **Its drive-second exposure is in no capacity table** — not `SPECIFICATION.md` §14.4, not `eval/results/plant_contention.json` (§9 A-12).
> - **Row 15's `commission(barcode)` is deleted with `gfs-mover`, which leaves the WORM-status-at-commissioning read unassigned** — required by `SPECIFICATION.md` §5.4 and its conformance checklist, and the only thing standing between the governance layer and a claim that a redaction is physically permanent when the bytes are erasable. Bareos commissioning is `label barcodes` and reads no WORM status. `gfs-probe`'s five opcodes include `MODE SENSE`, so the read is *possible*, but it is assigned to nobody (§9 A-13).
> - **The geometry in rows 7, 9, 12 and 13 and in *Residual* is superseded** — see the geometry note below the table.

Verdict is the outcome **as designed here**, not as the hardware behaves by default.

| # | Failure mode | Default outcome | Mechanism | Verdict |
|---|---|---|---|---|
| 1 | **Error localisation** | Sense `INFORMATION` on a *stream* device is a **residue**, not an LBA. Taken as an address it rebuilds a healthy symbol and reports success. | Localise from our own read-loop bookkeeping (`LOCATE` to a known absolute position, read `N` in a loop we control), confirmed by `READ POSITION`, authoritative check by per-symbol hash. A 4 KiB plaintext-structure header per 1 GB symbol (4 ppm overhead) carries format version, barcode, container id, symbol ordinal, extent id, length, payload hash, write epoch. | **Prevent.** *The premise is corrected: we own SCSI for mount policy, erasure-not-retry, encryption control and MAM/Log Sense — not for LBA-precise localisation, which the coding layer already provides.* |
| 2 | **End of data / append point** | Append point taken from the catalogue. On RW media a stale catalogue logically erases everything beyond the write point; the drive reports success. | Never derive EOD from the catalogue. On every load of a writable cartridge: `SPACE`-to-EOD, `READ POSITION`, compare against the catalogue. On divergence refuse to write, mark `RECONCILING`, raise a job. New causes `EOD_DIVERGENCE`, `DATA_PROTECT`. RW pool is a distinct, more dangerous descriptor mode. | **Prevent.** WORM also protected by the drive (sense 07h/30h 0Ch). |
| 3 | **Filemarks at end of data** | A double filemark at EOD blocks append: positioning between the two overwrites the second. WORM refuses; RW silently changes meaning. | **Single filemark per container. No EOD sentinel.** Containers self-delimiting: header + footer with a monotonic sequence number and the previous container's absolute position — a backward-linked chain. Trailing index written at cartridge *seal*, with its position and generation in MAM. | **Prevent.** |
| 4 | **Filemark-count addressing** | `st` writes a filemark on close of a written device. Any unplanned close shifts every subsequent `MTFSF n` count; the read lands in the wrong container and presents as `HASH_MISMATCH`, i.e. as media decay. | Hold each `/dev/nst*` fd for the mover's life; set the close behaviour explicitly via `MTSETDRVBUFFER`. **Address exclusively by absolute position from `READ POSITION` at write time.** `spaceToFilemark` is post-error resync only, bounded by a recorded absolute block. Header mismatch → `WRONG_POSITION`, never `fragmentbad`. | **Prevent.** |
| 5 | **Short writes / record framing** | The JDK loops on short writes (`FileOutputStream.write`, `IOUtil`): one record becomes two blocks and every downstream read is mis-framed. `st` returns short counts near early warning. | No `FileOutputStream`/`FileChannel` on the record path. **One `write(2)` per record via the mover**; any return != requested length is a hard job failure. Never set `SILI`; any non-zero residue or ILI on read is fatal. Pin `/dev/nst0` and assert the no-rewind node at open. | **Prevent.** |
| 6 | **Buffered writes / deferred errors** | `write(2)` means "in the driver buffer". A permanent error surfaces later as a deferred error (sense response 71h/73h) attributed to no command; positions computed host-side name bytes that never landed. | Durability point is `WRITE FILEMARKS` `Immed=0` returning GOOD **and** a subsequent `READ POSITION` showing the expected block. `close(2)` errno is fatal. Classify by sense **response code** before sense key; on any deferred error invalidate every container acknowledged since the last confirmed flush. Refs come from `READ POSITION` after the flush, never from host arithmetic. | **Prevent** (blast radius one container). |
| 7 | **Early warning / end of medium** | Drive-set EW is small. Programmable EW (`PEWS`, 16-bit MB) caps near **64 GB** — about a third of a 200 GB container. So EW arrives mid-container as the normal case, and on WORM the tail is spent. | Do not rely on EW. Poll **Log Sense page 0x31** (remaining capacity) during the write and stop at our own threshold = max symbol + 2 parity symbols + trailer + index + margin. Set `PEWS` to the achievable maximum as a backstop that should never fire. Mid-EW behaviour defined: abandon the partial symbol as dead tape. **If the measured `PEWS` maximum forces it, the write unit becomes an RS stripe (~34 GB), not a container** — that decision is made before the format is frozen. | **Detect**, and the reserve is honest. *Container size is now a hardware-measured input, not an assumption.* |
| 8 | **Compression** | On by default. Yields ~1.0 on AEAD ciphertext but makes host-bytes → media-bytes non-deterministic, so remaining capacity cannot be tracked by counting. | `MODE SELECT` off at every mount; `MODE SENSE` back and assert it took. | **Prevent.** |
| 9 | **Block mode** | Fixed mode pads silently and hides short reads. Variable mode: a record larger than the read buffer fails while the tape advances past it. | Variable, 512 KiB–1 MiB, exact length in the catalogue **and in the symbol header**, so the reader sizes its buffer from the medium rather than from config. `READ BLOCK LIMITS` at load, clamp. `MODE SENSE` records the **observed** block size into MAM, not the intended one; compare drive-observed against MAM-recorded at every mount. Enable **Logical Block Protection** (CRC-32C per block). | **Prevent.** |
| 10 | **Recoverable vs unrecoverable** | Recovered-error reporting is off by default (`PER=0`). The four-cause enum is read-shaped and cannot express write, protection, EOM or cleaning. | `MODE SELECT PER=1` at load, verify it stuck. Poll Log Sense 02h/03h and TapeAlert at every unload into a **cartridge × drive** matrix. Full sense table with ASC/ASCQ for the position-invalidating cases. **"Position unknown" is a first-class state** entered on every unit attention (0x06), reset, aborted command (0x0B) and medium error — exited only by an absolute `LOCATE`. Drive faults (0x04) leave the pool; media faults mark symbols. | **Prevent.** |
| 11 | **Reposition after error** | Generalising "`LOCATE` back and retry" to **writes** sets EOD at that point and orphans everything beyond it on RW media. | **Reposition-and-retry is read-only, asserted in code: no `LOCATE` on a handle opened for write.** A write error is handled forward: `READ POSITION`, close the container short, single filemark, record actual length, continue on the next cartridge, and append a **tombstone record** naming the abandoned extent so a scan skips it deterministically and orphaned bytes are charged to capacity. | **Prevent.** |
| 12 | **Read-error recovery policy** | Blind retry in place spends 3 × (20–60 s) re-reading what the drive has already retried internally, and a marginal cartridge consumes a drive for an hour. | **At most one same-drive retry, then rebuild the symbol from the surviving intra-cartridge parity on the pass in progress** — zero external mounts. Escalate to a different drive only on a TapeAlert media flag or when parity is exhausted, and express it as a scheduler request. Bound recovery in **drive-seconds**, not attempts. | **Prevent.** *This rule is the honest justification for owning the path.* |
| 13 | **Write verification** | LTO already verifies read-while-write in hardware. A same-drive read-back is close to blind to the failure that matters (readable on the writer, unreadable everywhere else) and costs **2.2–2.5×** write drive-seconds once repositions are counted, on the conserved resource. | Cheap half always: hash on the way out of memory against the manifest; read Log Sense 02h/03h write-error counters at unmount and fail the container on a budget breach. Honest half: **100 % read-back while the format and path are unproven — scoped per drive model and per firmware revision — then a sampled, cross-drive, later-mount pass** sized from the media-error budget. `verifyRate` is in the descriptor. ~~**The verify pass is in the capacity model.**~~ **CORRECTED 2026-09-19: it is not, and it must be entered before the policy is adopted.** `SPECIFICATION.md` §14.4's standing obligations total 8.6 % of the plant-year with a 1 % cross-drive verify at 0.01 %, and the measured standing-obligation model (`eval/results/plant_contention.json`) prices scrub, repack, migration and rebuild only — **there is no read-back line in either.** A 100 % read-back at the 2.2–2.5× write drive-seconds this row itself states is in neither and does not fit the reserve. Either price it into §14.4 as an explicit commissioning-period obligation with an end date, or open the first cartridges under the sampled policy; do not leave the two documents asserting different policies. **The row's underlying finding is preserved and is why this matters: a same-drive read-back is close to blind to the failure that matters — readable on the writer, unreadable everywhere else.** | **Detect**, cost declared. *The taper is a stated rule, not a future capitulation.* |
| 14 | **Drive encryption** | The library ships with a key manager and an encryption chip. If library-managed encryption is on, the holding site holds key material — the blind-holder invariant fails **silently**: every write succeeds and every same-key read-back passes. | `SECURITY PROTOCOL OUT` sets the mode explicitly at every mount; `SECURITY PROTOCOL IN` reads Data Encryption Status back **before the first write or read**; observed state recorded in the container manifest and MAM; refuse any cartridge whose observed state disagrees. Default: **disabled** — our own **per-object keys** already discharge confidentiality and are what crypto-shred acts on. *(CORRECTED 2026-09-19. This previously read "per-container DEKs", naming a third key granularity that is neither the retired per-domain nor the restored per-object: a container DEK cannot be the shred unit, because destroying it would shred every object in the container. If a container-level DEK exists in addition, say so explicitly and state that it is a transport/at-rest wrapper that is **never** the shred unit; otherwise this document tells the governance layer that per-object erasure is available while the implementation holds a per-container key. Note that the inconsistency with §4's own "erasure is key destruction: once, for the whole object … `SiteKeys`, `NodeAgent.siteKeyDelete`" **pre-dates 2026-09-19** — the measurement did not create it, it removed the ambiguity that let it stand. Everything else in this row is unaffected.)* "Encryption verified off" is a precondition of the first write. | **Prevent.** *Was unaddressed; this is net-new.* |
| 15 | **Partitioning** | `MODE SELECT` page 0x11 + `FORMAT MEDIUM` is one-shot on WORM and destroys a 30 TB cartridge if wrong. | **One medium partition, partition 0, no index partition.** Asserted on write and read. A `commission(barcode)` action, operator-gated and **not in the mover's normal CDB allowlist**, does the one-time format: read WORM status from the medium, `READ BLOCK LIMITS`, initialise MAM, bind barcode to volume identity. Never on a cartridge whose MAM shows prior use. *Library* partitions are renamed throughout so the two never collide again. | **Prevent.** |
| 16 | **TapeAlert** | Flags are **cleared on report**. Three racing readers (health poll, `tapeinfo`, post-error classification) mean the loser mis-classifies a failing **drive** as failing **media**, retiring good cartridges and keeping a bad drive writing. | **Exactly one reader: the mover**, at every unload and after every error, writing straight to the catalogue. `tapeinfo` and the HealthCheck read the catalogue. Two distinct drives must implicate a cartridge before retirement. TapeAlert 4/5/6 **enqueue a migration job with a deadline**, not increment a gauge. Cleaning (20/21/22) is a first-class scheduler job with its own budget. | **Prevent.** |
| 17 | **Catalogue loss** | Opaque ciphertext plus no on-media identity means a full traversal recovers *bytes with no identity*. Recovery-by-traversal is not unimplemented — it is impossible. | Symbol headers (#1) + per-container footer with backlink (#3) + append-only, **encrypted** cartridge index at seal + its position and generation in **MAM** (read at load, no tape motion, writable independently of WORM). The catalogue becomes a **cache**; `reconcile(barcode)` is the bounded recovery. | **Prevent.** *This also discharges the published-format and reference-reader obligations, which the format spec + reader are deliverables for.* |
| 18 | **Changer contention** | `O_EXCL` on `/dev/sg*` excludes nothing; an index lease is software state that does not bind a second host on the same fabric. | SCSI Persistent Reserve on the changer LUN **and every drive LUN**, epoch-keyed, `PREEMPT AND ABORT` for takeover (§6). Reservation conflict (status 0x18) is an immediate fence-and-alarm, never a retry. On rejection: release reservations, unload, refuse to serve. | **Prevent**, conditional on the PR gate in §10. |
| 19 | **Management-plane bypass** | The library's ReST API can move media with no SCSI reservation, and our own telemetry authenticates against it. | The scheduler owns that credential; the plant HealthCheck asserts no other session holds move capability. A cartridge found in the transport element on takeover **quarantines the changer** and requires operator acknowledgement — guessing its source slot overwrites an occupied slot. | **Detect.** *Residual: SAN zoning and physical access are stated requirements, not mechanisms we implement.* |
| 20 | **Privilege scope** | Once the JVM can issue CDBs, every bundle in it can issue `FORMAT MEDIUM` and `ERASE`. | Mover in its own process, non-root, device nodes group-owned, `CAP_SYS_RAWIO` only there. **CDB allowlist**: `WRITE(6)`, `WRITE FILEMARKS`, `LOCATE(16)`, `READ(6)`, `READ POSITION`, `LOG SENSE`, `MODE SENSE/SELECT` (enumerated pages), `READ/WRITE ATTRIBUTE`, `SECURITY PROTOCOL IN/OUT`, `MOVE MEDIUM`, `REPORT/READ ELEMENT STATUS`, `PERSISTENT RESERVE IN/OUT`. `FORMAT MEDIUM` and `ERASE` are **not reachable opcodes**. | **Prevent.** *Enforceable and auditable, unlike "a role with no write path in its action set" — `noRole()` is a config string, not a capability.* |

> **Geometry superseded 2026-09-19 by `SPECIFICATION.md` §3.** Throughout this section, read *container* as **fragment** (96 parcels contiguous on one volume, 103.1 GB written / 90.2 GB payload) and *symbol* as **parcel** (exactly `PARCEL_BYTES` = 1073741824, never varying). Intra-cartridge coding is **RS(j, 4) with `j ≤ 28` over 1 GiB parcels, contiguous within a band, local parity at the end of the band (1.1429×)** — **not RS 32+2**; global coding is **RS(2, 1) across three sites (1.5×)**; combined **1.714×**. Row 7's escalation ("if the measured `PEWS` maximum forces it, the write unit becomes an RS stripe (~34 GB), not a container") is **moot**: the fixed 1 GiB parcel is the write unit, and a short band uses `j =` its actual data-parcel count, so a forced seal costs at most one parcel of padding. Row 9's "exact length in the catalogue **and in the symbol header**" is superseded by the same §7.1 cleartext head as row 1.

**Residual, stated plainly.** We are trading a decade of field hardening for a write path of one function and a read path of one function. That trade is defensible only because those paths are that narrow, because every extent is AEAD ciphertext with a manifest hash under RS 32+2 intra-cartridge and global coding across sites, and because the fake-drive suite injects EW, `MEDIUM_ERROR` at a position, deferred errors, `pos_unknown`, short reads, ILI and unit-attention-mid-sweep from day one. **mhvtl catches the command grammar and the framing; it does not reproduce deferred errors, `pos_unknown` after a reset, real backhitch, WORM firmware enforcement or vendor sense.** Five of the twenty rows above live in that gap, and the gate in §10 exists for them.

---

## 9. Findings: resolution

Every FATAL and SERIOUS class raised, with the code that proves it and the disposition. **R** = resolved by this decision; **A** = accepted as a cost we are paying knowingly; **G** = deferred behind a named gate.

### Caller and index

| | Finding | Proof | Disposition |
|---|---|---|---|
| F-1 | Callers branch implicitly on medium via wall-clock timeouts, and that branch is invisible | `DurabilityEngine`: `push_timeout_ms` 5000, `fetch_timeout_ms` 4000, round deadline 8 s, `fetch_rounds` 10 with `sleep(500*round)` ≈ 22 s total patience | **R** — `FragRef.lc` carries the declared latency class; `fetchStripe` derives its per-fetch deadline from it, not from one global constant; stripe homogeneity makes the branch once-per-stripe |
| F-2 | Hedging races and `cancel(true)` the losers — on tape every loser has already burnt a mount | `fetchStripe`, `fs.get(i).cancel(true)`; `fetch_redundancy` 1 | **R** — redundancy racing is restricted to one latency class (automatic under homogeneity); for a mount-class locus the binding, not the caller, decides which of *n* to read |
| F-3 | `pushWithFallback` makes tape structurally unplaceable, or silently re-places a fragment whose bytes are already on WORM | 2 attempts × 5 s, then `replaceholder`, 6 rounds | **R** — two-phase accept: `ACCEPTED_FOR_CONTAINER` on receipt, `DURABLE` only on seal+verify; re-placement forbidden while a write ticket is open; the manifest records the ticket at reservation time |
| F-4 | `derivedState` computes durability from **holder liveness** | `IndexEngine:1312-1328`, `lost_ms` 25000, `repair_grace_ms` 15000, `repairSweep` on a 5 s timer, `auto_repair` true | **R** — two-axis: durability (independent copies) and reachability (time to first byte), derived separately. A holder UP with a cold medium is `PRESENT_COLD`: never an available copy for read planning, never a missing copy for repair. `lost_ms`/`repair_grace_ms` come from the descriptor per tier |
| F-5 | Planned maintenance is indistinguishable from death and its default response is a federation-wide repair wave | same | **R** — `plantState: MAINTENANCE{reason, until}` journalled, not overridable by `livenessSweep`; `DEGRADED_PLANT{reason, until}` as a refusal; repair accrues `durability_debt` instead of re-placing |
| F-6 | `auditSweep` becomes a tautology on tape: catalogue asked about a catalogue decision | `NodeAgent.hasFragments` → `store.has()` → `Files.isRegularFile`; `IndexEngine:1470` then calls `repairSweep(null, true)` with **grace ignored** | **R** — `hasfragments` is three-valued (`PRESENT`/`ABSENT`/`UNKNOWN`); the index treats `UNKNOWN` as *suppress repair, alarm, hold state*. `verify(PRESENCE)` on tape is `READ ELEMENT STATUS` — seconds, no mount, genuinely physical. `ignoreGrace` is never used against a non-`ONLINE` locus |
| F-7 | Catalogue loss reads as data loss and is answered by writing fresh WORM that can never be reclaimed | as above + `reclaimSemantics` | **R** — F-6 plus risk row 17 (self-describing media) |
| F-8 | Crash mid-write orphans WORM bytes; `commit`-returns-refs means the caller holds nothing durable for minutes | no journal anywhere in gfs | **R** — `append` returns a **provisional ref with its real address immediately** and journals it (fsync) before the next record; a write-intent row is committed to the index before the first byte |
| F-9 | `repairsInFlight` is a hardcoded 60 s lease, shorter than one mount, so repair re-dispatches while the first is still mounting | `IndexEngine:1517` | **R** — lease = the plan's `estWallP95` + margin; repairer heartbeats the job; `repairFailed` backs off exponentially instead of retrying at once; repairer selection prefers co-location with surviving fragments |
| F-10 | Repair/scrub routed through admission can be refused → livelock against a 5 s sweep | `repairSweep` unconditional retry | **R** — obligations bypass admission and draw on the published reserve; a refused obligation sets a distinct state, never a silent retry |
| F-11 | `absentFragments` is a permanent, process-lifetime, cross-job blacklist keyed on status `9` | `DurabilityEngine:123, 131, 298` — three references, never cleared. Note `9` is also `noRole`, `unknown job` and `no such fragment` | **R** — `Cause.DEFERRED`/`OFFLINE` distinct from `MISSING`; blacklist scoped to one job and given an expiry |
| F-12 | Returning a new status on an existing action reads as failure to every `Rpc.ok` caller | `Rpc.ok` is `"10".equals(status)` | **R** — no new status codes on existing actions. Tape is reachable only through new action names; `getfragment`'s ack gains `{state: SENT\|QUEUED, ticket, window}` as an additive param the old path ignores |
| F-13 | A plugin whose hardware is absent/claimed reports ACTIVE, registers no HealthCheck, and silently drops messages | `PluginAdmin` ~1336; gfs `Plugin.isStarted()` registers HC on the success path only; `msgIn` guards `executor != null` | **R** — **a hardware condition never fails `isStarted()`.** Always construct, always register the HC, always register with the index, always serve `nodeinfo`/`describe`/`ticket`/`tapeinfo`; refuse only drive-touching actions, with `plantState` as a gauge and the HC verdict. Also latch `startFailed` so a failed start stays failed |
| F-14 | Placement selects a plant that has no write contract; and a plant holding Shamir shares destroys crypto-shred | `custodyPut` gates only on `store == null` | **R** — `custodyplan` excludes and `custodyput` refuses any locus whose descriptor says `reclaimSemantics != UNLINK`. **Key material never lands on a medium that cannot destroy it.** |
| F-15 | Restore is an ordered streaming decoder that cannot poll and caps outstanding demand at `stripe_window × k` | `runRestore` blocks on `pending.get(si).get()` with **no timeout**, `stripe_window` 4 | **R, and named as scope** — two-phase restore: `intend`/`plan` the whole ref set, `enqueue` once, decode into a bounded out-of-order stripe buffer, write out in order. This is the largest single piece of work in the programme and is sequenced accordingly (§10 step 3) |
| F-16 | `Jobs` evicts still-RUNNING jobs at 256 in insertion order, loses everything on restart, and inserts before `submit` so a rejection leaves a phantom | `Jobs.java:31-33, 42-52`; `jobstatus` → `"9" "unknown job"` | **R** — never evict a non-terminal job; evict terminal by completion age; insert only after a successful `submit`; separate pool for drive work sized to drives+1; persist ticket records; distinguish `UNKNOWN_TICKET` from `EXPIRED_TICKET` from `RECOVERED_UNKNOWN` |
| F-17 | `FrameBus` cannot carry container-scale delivery and has no backpressure; a stalled consumer shoe-shines a drive | `MAX_FRAME = 700*1024`, one frame = one fragment, `PARK_TTL_MS` 60 000 (shorter than a mount) | **R** — the drive is decoupled from the network: a sweep writes into local staging at streaming rate and delivery uses the existing fragment-at-a-time path from staging. `PARK_TTL` derived from the ticket's projected start. **No direct drive→network streaming in the first build** |
| F-18 | `NodeAgent` RPCs from a single-threaded `Timer` that also runs a whole-store rehash | `NodeAgent.java:79-110, 147-154`; `scrub_period_ms` 60 000 | **R** — liveness on a dedicated `ScheduledExecutorService` catching `Throwable` (JNA failures arrive as `Error`), never blocking on a device; scrub onto the Jobs pool; "last successful heartbeat age" as a gauge. **A live bug today, fixed regardless of tape** |
| F-19 | The fs binding's `DURABLE` is already false | no `fsync`/`force`/`SYNC`/`DSYNC` anywhere in gfs | **R** — §5 |
| F-20 | A vanished NAS mount reports used=0 and becomes the *most attractive* placement target, then mass-MISSING | `BlockStore` constructor `createDirectories(root)`; `rescan` → used=0; `place()` weight `score × free` | **R** — `.gfs-store-id` sentinel + `getFileStore` device identity checked before every rescan, scrub and presence answer. Absent/mismatched → `UNAVAILABLE` (distinct from EMPTY): refuse to report capacity at all, answer presence `UNKNOWN`, fail the HC. **`capacity.used = 0` and `capacity = UNKNOWN` must be different facts** |
| F-21 | The publisher converts absence-from-disk into deletion from the federation index | `PublisherEngine.java:91` | **R** — same sentinel discipline on the publisher root, plus a gate: a pass that would delete more than a set fraction of a dataset refuses and raises |

### Design-level

| | Finding | Disposition |
|---|---|---|
| S-22 | A binding-level `prospect`/`realise` installs a second planner under ENTAIL's | **R** — binding `plan()` is a pure cost declaration; coalescing, wave formation and deadline ordering happen once, in the scheduler, driven by `intend`; the index composes the joint plan across loci, because only it knows placement |
| S-23 | Admission that refuses without enrolling demand deletes the batchability the economics depend on | **R** — every refusal carries `retry_after` **and** an `intentId` |
| S-24 | Descriptor leaks a per-peer load oracle (cartridge ids, instantaneous queue depth) that ENTAIL closes deliberately | **R** — static capability descriptor on `registernode`; dynamic terms published only as **buckets** in the Calendar; `Order` carries extent ids and a locus id, never a locator |
| S-25 | `grant_ttl_ms` 600 000 and a 15 s `streamfile` RPC are calibrated to a NAS | **R** — grant lifetime is a function of the ticket's projected window; `extend` renews against the ticket |
| S-26 | A cartridge physically exported is counted as a live copy | **R** — `Residency.presence = EXPORTED{custodian, since}` fed by a periodic cheap changer inventory; export/import are explicit custody transfers that move durability credit atomically; `plan()` refuses on `EXPORTED` naming the custodian |
| S-27 | A drive lost mid-wave silently invalidates every admitted window | **R** — `maxConcurrentReads` is live scheduler state, not config; a pool change bumps `capabilityEpoch`, republishes, and **re-plans every admitted-but-unstarted ticket**, refusing or re-windowing explicitly. Health checks are for humans and are never load-bearing for scheduling |
| S-28 | `Ticket` states shorter than ENTAIL's drop the vocabulary of degraded operation | **R** — ENTAIL's `Job` states adopted verbatim, plus `PLANT_DEGRADED{until}` |
| S-29 | Plugin data directory is keyed by a `pluginID` that is a fresh UUID unless `inode_id` is pinned | **R** — pinned `inode_id` is a hard deployment requirement; the binding refuses READY without it (visibly, per F-13); the catalogue lives at a configured absolute path outside plugin-data; the cartridge is the record of truth |
| S-30 | OSGi bundle refresh is not process restart; device fds are process-scoped | **R** — moot for the drives (the mover is a separate process), but the mover socket gets explicit close-on-deactivate with a bounded join and a re-acquire retry window; HC distinguishes "held by a previous incarnation" from "unavailable" |
| S-31 | `healthSummary` returns `CRITICAL: block store not writable` from `rootFile().canWrite()` | **R** — the plant has its own predicate (drives claimed, changer responsive, staging writable, sealed-but-unverified containers), never this one |
| S-32 | Verify + scrub economics unbudgeted; `scrub_period_ms` 60 000 is a robot campaign on tape | **R** — on any locus with `latencyClass` MINUTES/HOURS the node-side scrub timer is **off by default**; `verify(MEDIA_READ)` is a sampled campaign inside the obligation reserve with a stated annual drive-second allocation; the verify pass is in the capacity model |
| S-33 | The cartridge is the real failure domain and nothing can name it | **R** — `cartridge` as a `domainKey` level and a reverse index barcode → {object, stripe, idx} maintained at container commit, so drain is one scheduled campaign rather than ten thousand independent repairs |
| S-34 | Serpentine ordering ≠ ascending LBA; RAO availability unknown | **A + G** — stated honestly as an approximation; RAO behind a descriptor flag; a procurement question |
| S-35 | The proposed validation gate cannot fail | **R** — §10: the simulator is a **fault** injector, and the pass condition is *degrades explicitly*, not *still repairs* |

### Accepted costs

- **A-1 — The tape staging area is a new single point of loss.** "No filesystem" holds for the media, not for the node. Mitigated by retaining the source copy until seal-and-verify, by the directory refusal, and by never naming staging as a repo. It remains real.
- **A-2 — Every tape `estWall` is a declared guess until commissioning measures `O` and the reposition term.** **MEASURED 2026-09-19 (`eval/results/plant_sim.json`): the plant-level spread is 3.8× between scattered and clustered placement at identical scheduling policy (172.3 → 653.3 GB/drive-hour) and 9.4× for policy alone (69.5 → 653.3).** That is **not** the same quantity as this line's ~14×: the harness's scattered and clustered cases differ in bytes-per-mount by 8.4× (13.3 vs 111.1) and separate mainly on mount count (601 vs 72), whereas **~14× is scattered-vs-contiguous *at identical bytes-per-mount* — a within-cartridge reposition question that remains UNMEASURED and is not closed by the plant simulation.** Also still modelled, not measured: the mount cycle itself (the simulation assumed 90 s mount, 20 s unload, 172 s full-length pass, 2 s settle and first-order serpentine, against `SPECIFICATION.md` §3.4's settled `O = 265 s`) and the reposition figure inherited from LTO-8/9-class media. `basis: MODELLED` with model error is carried in every plan. The SPI makes the guess visible and revisable; it does not make it true.
- **A-3 — Splitting the score changes placement for every node already registered.** `score()` is used twice in `place()` — as the best-per-domain comparator and as the sampling weight — and the SCALE results were produced under both. The migration gets its own before/after comparison; it is not a clean substitution.
- **A-4 — The block binding is the least examined.** Partial-write atomicity across power loss, discard that does not discard, reordering across a flush. It satisfies every method as specified, by analogy to the filesystem case rather than by its own examination. **If the intended device is SMR or a zoned namespace — append-only with sequential write constraints — it groups with tape and this grouping is wrong.** That is a question to answer before the block binding is written, not after.
- **A-5 — Container packing above the SPI is unscoped, and 2026-09-19 made it the busiest open question in the set.** Grouping extents into containers by retention class and consent unit is effectively irreversible on WORM, and the citation-pinning problem makes it consequential. It now carries: (i) **object-granular purity**, whose ½-parcel-per-object padding `SPECIFICATION.md` §8.4 rule 1 shows is ruinous for small objects; (ii) the conflict between *never cluster by consent unit* (disclosure, §8.4 rule 2) and *cluster by co-access* (capacity), which for longitudinal clinical data are the same axis; and (iii) **`pooled(n)` becoming the default mode**, whose three costs §8.4 enumerates. Co-access clustering is worth **3.8× in GB per drive-hour** and the difference between **11.9 and 45.0 PB/yr** delivered (`eval/results/plant_sim.json`, `eval/results/plant_contention.json`), so this is a **capacity decision, not a layout preference** — and it is irreversible on WORM. Provenance: those figures come from a simulated plant with synthetic cartridge assignment (`plant_sim.json` `model_limits`: real co-occurrence must be mined from an actual request log), which makes that log-mining a **prerequisite** to this decision rather than a refinement of it. Real work hidden behind a clean interface boundary — now with its contents named.
- **A-6 — "Our write path is narrow" is unfalsifiable until it has run against real media.** Every team that wrote its own tape format believed this. The read-back verify and the reference reader are what make the belief testable, which is why both are early rather than deferred. *(2026-09-19: largely mooted by Bareos owning Layer 0 — we no longer write the tape format — but the staged-until-verified gate and the fault injector survive on their own merits.)*

**Opened 2026-09-19 by the coherence and measurement pass. Recorded, not solved.**

- **A-7 — `ExtentBinding` has no layer.** `VolumeMover` is Layer 0 and the ten-call block plane is Layer 1, each by its own document's statement. Nothing assigns `ExtentBinding` a layer or states how the three compose, and §1's "One SPI" is withdrawn without a replacement claim. An implementer working from §3 cannot tell which interface they are building against.
- **A-8 — Multi-host changer fencing has no mechanism.** Deleting SCSI Persistent Reserve removes the only cross-host mechanism in the design. What replaces it is a deployment rule — single host per changer — with no enforcement. `BAREOS-RECOMMENDATION.md` §11.3 states the STONITH procedure "is owed now"; it exists in no document. A second host on one fabric is currently prevented by convention only.
- **A-9 — The durability half of the `durabilityScore`/`accessCost` split is unmeasured.** That the ladder's most-durable class is also the slowest path is evidence the two axes do not track each other; it is not a measurement of durability. Nothing in `eval/results/` measures the durability of a node-local path against a shared one.
- **A-10 — An unprobed locus has no defensible score.** Placement must rank a node at its first registration, before any commissioning write probe has run, and the existing ladder is throughput-inverted at its top. No rule is proposed for what an unprobed locus scores, or whether it is eligible for placement at all.
- **A-11 — A declared `latencyClass` and a measured rate can contradict each other by 40×, and nothing arbitrates.** Stripe homogeneity and the caller's per-stripe deadline both key off the declared value. Whether the declaration is refused, the locus demoted, or the stripe refused is a design decision, deliberately not made here. Related and also open: the re-probe cadence, and what happens to in-flight stripes when a live locus's measured rate changes underneath open placements (`capabilityEpoch` is the obvious vehicle and its in-flight behaviour is unspecified).
- **A-12 — The retry and error-recovery policy is an accepted loss with no price.** §8 row 12 is retired as something we implement; nothing specifies what the policy now is, and the resulting drive-second exposure appears in no capacity table.
- **A-13 — The WORM-status-at-commissioning read is unassigned.** Required by `SPECIFICATION.md` §5.4 and its conformance checklist; the only process that did it (`gfs-mover`'s operator-gated `commission(barcode)`) is deleted, and Bareos's `label barcodes` reads no WORM status.

---

## 10. Build order

### Step 0 — Honest acks and three live bug fixes *(simulation now; no tape hardware; useful even if the tape tier is never bought)*

1. `FragRef.lc` + `LocusDescriptor` carried on `registernode`/`heartbeat`, with `classWeight` demoted to fallback and the descriptor consumed nowhere yet.
2. `getfragment`'s ack gains `{state: SENT | QUEUED, ticket, window{p50,p95}}`; `fetchFragment` derives its await budget from the returned window instead of a constant.
3. Fix, today, independent of tape: `fsync` in `BlockStore.put` (temp + directory); the `.gfs-store-id` mount sentinel and three-valued presence; `NodeAgent`'s liveness off the shared `Timer` and scrub onto the Jobs pool; `Jobs` eviction by completion age with insert-after-submit.

**This is the smallest step that is genuinely useful and not throwaway**: it fixes four defects that exist now on disk, and it is the change that lets a mount-class locus be added later without every caller branching.

### Step 1 — The SPI and the `fs` binding *(simulation now)*
`io.cresco.gfs.extent` interfaces and plain classes. `FsBinding` = `BlockStore` promoted: `put`/`meta`/`scrub` survive; `get()` retires in favour of `enqueue`/`ticket`; `has()` becomes catalogue-backed `locate()` + `verify`. `reclaim` replaces `delete` on every medium, `delfragment` renamed. Prove the existing **D1** durability-transition run re-executed through the new path with no regression on disk.

### Step 2 — The index becomes two-axis *(simulation now)*
`durabilityScore`/`accessCost` split; `netFactor` out of placement; the role gate; **stripe homogeneity**; `PRESENT_COLD`; three-valued `hasfragments`; per-tier `lost_ms`/`repair_grace_ms`; declared maintenance; the obligation reserve; repair lease from the plan; `cartridge` as a failure domain; decayed availability. Re-run SCALE and publish the before/after distribution (A-3).

### Step 3 — Restore and repair learn to wait *(simulation now)*
Two-phase restore (F-15), `intend`/`coalesceKey`, out-of-order stripe buffer, bounded blocking gets. This is the largest piece and it is the precondition for any tape read being economically worth taking.

### Step 4 — `SimTapeBinding`, the scheduler, and a **fault** injector *(simulation now)*
Full descriptor, cost model, container packing, staging, seal-and-verify, single filemark, absolute positioning, symbol headers, container footers with backlinks, tombstone records. *(2026-09-19: the fault injector moves from inside `SimTapeBinding` to the `VolumeMover` boundary — `BAREOS-RECOMMENDATION.md` §12 — and **the 90 s mount constant is replaced by the four-term cycle `O = 265 s`**, `SPECIFICATION.md` §3.4, which identifies the single-term 90 s figure as the error every candidate design made.)* `FakeDrive` over files, injecting ~~90 s~~ **265 s** mounts, 40 s repositions, `MEDIUM_ERROR` at a position, deferred errors, `pos_unknown` after reset, short writes, ILI, unit-attention mid-sweep, EW mid-container. Scheduler with coalescing windows and cartridge-atomic preemption, driven by the Jobs pool, never a timer thread.

**Pass condition is *degrades explicitly*, not *still repairs*.** For each of: library offline with deadlines pending; reservation preempted by a second host; drive lost mid-sweep; control host killed mid-ticket; cartridge exported; catalogue stale since last eject; NAS mount vanished — assert a **named** refusal or declared state reaches the index and the caller within a bounded time, and that **no repair traffic is generated by an announced absence**. Assert no object ever reports DURABLE while its fragments are only `PRESENT_CLAIMED`. Run the planner against a `FakeDrive` whose reposition cost differs from the planner's by 14× and assert the plan degrades gracefully and `estWallP95` is not violated silently.

### ~~Step 5 — `gfs-mover`, one drive, no changer~~ / ~~Step 6 — Changer, Persistent Reserve, takeover~~ — **SUPERSEDED 2026-09-19**

> Both steps are replaced by `BAREOS-RECOMMENDATION.md` §9 (test plan) and §10 (rig checklist). The three hardware questions they existed to answer — the achievable `PEWS` maximum, whether Persistent Reserve is honoured on an ADI-relayed changer LUN, and real deferred-error and backhitch behaviour — are now either Bareos's problem or are R-1…R-16 on the mhvtl rig. **The gate they carried is preserved verbatim and moves with them: *the first WORM cartridge is not written until this step passes on rewritable media, with an independently written reference reader opening the result on a different drive.*** The bodies below are kept as the record of what was to be proven.

### Step 5 — `gfs-mover`, one drive, no changer *(needs hardware we do not have)*
Separate process, CDB allowlist, `SECURITY PROTOCOL IN/OUT` encryption assertion, compression off, `PER=1`, `READ BLOCK LIMITS`, LBP on, `commission(barcode)` reading WORM status from the medium. Write one container, filemark, read back and verify, footer, unmount, remount, position by absolute block, read by plan. **Read MAM barcode and medium serial at every mount before any write and refuse on mismatch — one command, present with or without a changer, and the bug it prevents would not appear until the changer arrives.** Ship `cartridgescan`: reconstruct the container list from media alone. Calibrate the cost model here, once.

**This step answers, before money is committed, the three questions that cannot be answered in simulation:** the achievable `PEWS` maximum (which may force the write unit down to an RS stripe, risk row 7); whether `PERSISTENT RESERVE` is honoured on an ADI-relayed changer LUN against initiators reaching the robot through a different exporting drive (risk row 18 — a harder gate than the WORM question); and the real deferred-error, `pos_unknown` and backhitch behaviour of the procured drive and driver version. **Gate: the first WORM cartridge is not written until this step passes on rewritable media, with an independently written reference reader opening the result on a different drive.**

### Step 6 — Changer, Persistent Reserve, takeover *(needs hardware we do not have)*
`MOVE MEDIUM`, `REPORT`/`READ ELEMENT STATUS`, PR register/reserve/preempt keyed on the lease epoch, transport-element quarantine on takeover, restart recovery from element status + MAM + the journal.

### Step 7 — LTFS export as a conversion
An ordinary admitted, costed, refusable scheduler job on a drive pair, discharging the portability obligation on demand and never on the data path. *(2026-09-19: this is now the **only** surviving role for LTFS in the document set. `TAPE-RESEARCH-PROMPT.md`'s LTFS addendum is closed as superseded and `STORAGE-DIRECTION.md`'s "LTFS underneath" is withdrawn; the addendum's four disclosure conditions — opaque filenames, fixed-size padded containers, coarsened timestamps, no extended attributes — carry over to this export unchanged.)*

---

**What we are not building:** a second bundle; a filesystem on the media; a `list` verb; a `delete` method on any binding; a binding-level planner; a scheduler whose authority lives across a WAN.

**What we are betting:** that a write path of one function and a read path of one function, behind an allowlist, with every byte AEAD-sealed under a manifest hash, under RS 32+2 intra-cartridge and global coding across sites, and with nothing marked DURABLE until it has been read back, buys back more than a decade of somebody else's field hardening. That bet is only defensible with the staged-until-verified gate, the fault injector, and the reference reader — and it is void if any of the three is ever made optional for throughput.