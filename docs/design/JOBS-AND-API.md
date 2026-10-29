!!! success "Status: Current"
    Async jobs, striped ingest with a short commit, history, have-checks, extracts and profiles (shipped in 1.3, 2026-10-01).

# Jobs, §1a ingest, policy profiles and the fabric API (wave 2, package jobsapi)

*2026-09-26. Branch wip/jobsapi, based on the wave-1 integration (6ee4356). Normative inputs: the
operation model (opmodel.spec.md) and the API package spec (api.spec.md). This page lists what is
built, the journal deltas and config keys it adds, the defaults adopted where the owner has not
decided (each flagged), and what is not built.*

## 1. The operation model

Every core.* and x.* action is classified (`OperationClass`): C0 instant control, C1 bounded reads,
C2 lifecycle mutations and C3 maintenance (async jobs), C4 ingest and download, X internal.
`OperationClassTest` fails when a handled action is unclassified, when the table names an action
nobody serves, and when any C2/C3 verb does not answer within the sync budget while its work is
held. Every dispatch is timed; an RPC held past `core_sync_rpc_max_ms` is logged and counted
(`core.status` `sync_rpc_overruns`).

### Jobs (opmodel §2)

| Verb | Class | Job work |
|---|---|---|
| core.withdraw | C2 (request_id required) | drop (one exclusive batch), then gc in slices |
| core.rotatemaster (not dry_run) | C2 | rewrap roots |
| core.membership add / remove | C2 (request_id required) | one raft configuration entry at a time (OUT-08c): add = learner, catch-up, promote; a leader that removes itself steps down and the next leader ends the job from the configuration in effect |
| core.compose (more than `core_compose_sync_files` files, or with request_id) | C2 | commit; the job ends in the commit's batch |
| core.extract (more than `core_extract_sync_leaves` files, or with request_id) | C2 | freeze and pin |
| core.publish with request_id | C4 as a job | publish; ends in the commit's batch |
| core.commit | C4 as a job | §1a commit; ends in the commit's batch |
| core.gc, core.repair, core.scrub, core.trim, core.recover | C3 | the engine's slices, a safe point between slices |
| core.site drain / lost / decommission / reconcile, and restore of a LOST site | C3 | as the site lifecycle |

`core.auditverify` is not a job: A3 (fix-core) serves it on any peer, against that peer's own audit
log, so it is a bounded read (C1). A page verifies until the log's end or the sync budget; a longer
log answers `complete=false` with a cursor MAC'd by the peer's process, and `ok=true` comes only
from the page that reaches the end.

- Accept: authorized and validated, then `jobAccept` is journaled before the reply. The same
  `(principal, request_id)` answers the same job, on a retry and on a new leader; other params under
  the same key are refused (8). A key whose job ended retryable (FAILED retryable, CANCELLED,
  ABANDONED) may start a new attempt.
- States: ACCEPTED, RUNNING (journaled before any work), DONE, FAILED, CANCELLED, ABANDONED.
  `jobProgress` at most every `core_job_progress_ms`; events at most once a second.
- A job that commits a version ends in that commit's own batch (`jobEnd` with `at_head`): the
  version and the job's end are durable together or not at all.
- Leader loss: the new leader resolves every open job: DONE from its journaled effect (withdraw,
  site lifecycle), otherwise FAILED with code `interrupted`, retryable (`reupload` for commits).
- Admission: `core_jobs_per_principal` (8) and `core_jobs_max` (64); a full queue answers 11 with
  `retry_after_ms` at once. Commits and request_id publishes are not counted (they follow an upload
  the staging quotas admitted).
- `core.job` (the job's principal; an auditor may read), `core.cancel job_id` (the principal or a
  system-admin; cooperative, at safe points). Every accept is the request's own audit record; every
  end is audited (`core.job.end`).
- Retention: ended jobs are forgotten (`jobForget`) after `core_job_retain_ms` (7 d).
- Events: `{job_id, seq, state, progress, ts, sig}` on the stream the request named
  (`events`), GK-CJSON-1 canonical JSON signed ECDSA P-384 by the core identity, byte for byte the
  clients' golden (`clients/conformance/event-golden-v1.json`, copied to test resources). seq is the
  leader's term x 10^9 plus a per-job count, so it only rises. core.job stays authoritative. An end event names
  the job and its end state only: events cross the broker signed but unsealed, and a result or error can name a path,
  so the client reads both from core.job (sealed) and asks again if that call times out.
- `core.status` advertises `jobs-1` and `ingest-1a` in `capabilities`.

### Ingest by striped parts and a short commit (opmodel §1a)

- The first `core.put` names the target: `collection_id, branch, expected_head, base_vid, deletes,
  request_id, note, ingest=1a`. A writer thread writes each file through `StorageEngine.Ingest` as
  its bytes land (streaming read, sha256 checked, blocks pinned until the commit or the abort; the
  write gate is held only while a file is written).
- `core.commit(upload_id, request_id)`: a job, waited for at most `core_sync_rpc_max_ms - 2 s`;
  otherwise `state=committing`, then a signed commit event `{upload_id, request_id, seq, state, vid,
  number, error, ts, sig}` on the upload's down streams, and `core.putstatus` `commit_state`.
- `core.putstatus` `ranges`: `{path: {part: [[first, end), ...]]}` in flow sequence numbers. A part
  is re-opened with `resume=true`; its receiver starts from the chunks held. One writer per staged
  slot. A flow that stalls or drops does not fail an §1a upload.
- **Across a leader change (OUT-89).** Once `core_ingest_checkpoint_bytes` (256 MiB) of whole files are
  written, the writer checkpoints at the next file boundary: the window's site writes are sealed (an
  intent, then the landed that records the copies) and, in the landed's batch, each whole file is
  journaled (`ingestPart`: upload_id, path, durable byte offset = its size, its file entry, and for a keyed
  file the MAC its commit must carry under each part-0 flow key) with a named hold `ingest|<upload_id>`
  on its blocks (`addRef`), so gc and the orphan pass keep them; the first checkpoint opens the record
  (`ingestOpen`, the target). Journaling waits until every core peer answers FEATURES with `ingj1`. A new
  leader adopts every open record: `core.putstatus` answers `ingest_state=adopted` and `journaled`
  `{path: offset}`; the client re-opens the same upload there (a part already open there with
  `resume=true`), never sends a journaled file again (refused, 8), and commits under the same request_id
  with the same proofs. The record and its hold end in the commit's own batch, or when the upload is
  given up (discarded, failed, or not resumed within `core_upload_ttl_ms`), and its blocks then go to the
  orphan pass.
- **Mid-file (OUT-89, `ingj2`).** A file in progress checkpoints too: after each batch of its blocks, once
  `core_ingest_checkpoint_bytes` more of it are written, the blocks so far are sealed and journaled as its
  prefix (`ingestPrefix`: upload_id, path, durable byte offset = the blocks' bytes, an entry naming those
  blocks with no file hash) with the same hold, in a batch made durable at once; a later prefix of the same
  file replaces it (the offset only grows) and the file's `ingestPart` ends it. A new leader answers
  `journaled_prefix` `{path: offset}` in `core.putstatus`; the client re-opens that file's parts with
  `resume=true` and skips every chunk wholly inside the prefix (the core counts them as landed), so only the
  chunk across the prefix's end and the rest cross the wire again. The whole-file hashes cannot cross
  leaders as hash state, so the new leader's writer reads the prefix back from the sites (each block
  authenticated) before the bytes the client sends: the legacy sha256 check, the domain's file hash and
  the keyed commit proof (under the new part-0 flow key) cover the whole file as before. In a dedup domain
  the prefix's blocks are deduplicated onto; in NONE they are sealed again under the new object (an object's
  deterministic IVs are never reused across leaders). A commit while a begun file is unfinished commits
  nothing (`incomplete`). Journaled only while every core peer answers FEATURES with `ingj2`.
- The legacy `core.publish` never holds its RPC past the budget: 13 `committing`, then
  `core.putstatus` `commit_state`; with request_id it is an idempotent job.
- A wave-1 staged upload whose puts say `resumable=true` is resumable the same way (a dropped flow
  leaves its part resumable), is verified in full as any staged upload, and is published with
  `core.publish`; the first put decides it. Commits verify every staged file was written (else
  FAILED `incomplete`, reupload).
- eval/gkt.py: `ingest_commit(mc, files, target, request_id, upload_id=None, resume=True,
  pause_after_chunks=None, stall_s=30)` (a stalled or failed flow re-opens its part with resume=true and
  sends only what core.putstatus ranges say is missing; upload_id resumes an upload a paused or killed
  client left; core.commit is repeated under the same request_id on a timeout or a leader change; a
  commit that failed with reupload is uploaded again under a new upload_id and the same request_id;
  eval/test_gkt_ingest_resume.py), `Job.start/wait/result/cancel`,
  `have_upload`, `MultiClient.put_files(resume=True, pause_after_chunks=N | {part: N}, stall_s,
  upload_id)` (eval/test_gkt_resume.py); `eval/test_gkt_events.py`, `eval/test_gkt_have.py` check them against the golden
  vectors.

## 2. Policy profiles (owner request)

A profile bundles the dedup mode and chunker spec, replication, durability, retention and GLOBAL
eligibility. `core.profile op=create|list|get|of`; `core.collection profile=<name>` takes the
profile's replication, durability and retention (a disagreeing param is refused, profile-conflict),
the named domain (mode and chunker must match) or the tenant's profile domain, and records the
profile, whole, with the collection in the same journal batch. Built-ins: radiology-dicom
(`fmt:dicom@1+cdc:1048576:262144:4194304`, R=3, durable), pathology-wsi (`fmt:tiff@1+...`, R=3,
durable), scratch-cache (R=1, cache, COLLECTION). Until the format adapters (wip/dicomchunk) are
merged, the two fmt: built-ins refuse with profile-chunker-unavailable.

## 3. The fabric API (api.spec.md)

| Verb | Class | Role |
|---|---|---|
| core.versions, core.version, core.branches | C1 | reader on the collection |
| core.diff | C1 | reader on both versions' collections |
| core.chunker | C1 | reader or writer |
| core.haveopen | C0 | writer, and the oracle scope |
| core.have | C1 | the have-check's owner, a writer, the scope re-checked per page |
| core.extract | C2 when large | reader on every member; cite: tenant-admin of every member tenant |
| core.extractstatus | C0 | the creator (state only), or a reader of every member |
| core.extractlist, core.extractproof | C1 | a reader of every member |
| core.extractattest | C1 | a reader of every member |
| core.extractextend | C0 | a reader of every member; past the class maximum, tenant-admin of every member tenant |
| core.extractrelease | C0 | the creator, or a tenant-admin of a member's tenant |
| core.cut | C0 | reader on every member |
| core.cutinfo | C0 | the creator, or a reader of every member |
| core.cutrelease | C0 | the creator, or a tenant-admin of a member's tenant |
| core.transform | C0 | tenant-admin of the image version's tenant |
| core.derive | C0 | reader on the whole input closure |
| core.entail | C1 | reader on the whole input closure |
| core.built | C0 | writer on the output collection, and reader on the input closure |
| core.derivations | C1 | tenant-admin@tenant_id, or any principal for its own |
| core.collections | C1 | tenant-admin@tenant_id or a tenant-wide reader@/writer@ (every collection); collection-scoped bindings: those collections only |
| core.placement | C1 | reader on the version's collection (as core.list) |
| core.jobs | C1 | any principal holding a role, its own jobs; an auditor every principal's (principal_id filter: auditor only) |
| core.principals | C1 | tenant-admin@tenant_id (that tenant's principals); no tenant_id: system-admin (the system principals) |
| core.retention op=list | C1 | any principal holding a role |
| core.tapevol op=library | C0 | system-admin; observer (status and library) |
| core.site op=events | C1 | system-admin, auditor or observer |
| core.site op=containers | C1 | system-admin, auditor or observer |

- Dashboard listings (core.collections, core.placement, core.jobs, core.principals, core.retention op=list):
  each page comes from a sorted index kept on apply (per-tenant collections, (tenant, id) principals,
  (accept time descending, job id) jobs globally, per principal and open-only, retention class names), so
  a page costs a logarithm plus its size, never a scan of every tenant, collection, block, job or
  principal. The indexes are derived: rebuilt by replay and snapshot install, never journaled, snapshotted
  or hashed. Pages are bounded by `limit` (1..1000) and `core_page_bytes`; cursors are `gfs-cur-1`, bound
  to their verb and scope (core.retention op=list continues by class name). Rows show only what the
  caller's roles already show elsewhere: a collection's domain, dedup mode, replication and durability to
  its tenant-admin, its retention class, profile and version and branch counts to its readers; a block's
  `required` is its collection's replication (the block record's own requirement is the most any
  referencing collection asks, which may be another collection's or another tenant's), and its state
  follows the census rule (copies on up, ACTIVE, non-archive sites, not suspect, count toward it;
  UNAVAILABLE with no readable copy). Node class and a packed copy's container are shown to a
  system-admin or auditor, a tape copy's barcode to a system-admin; never a block id, digest or key.
  `core.placement tape=true` asks each archive site once per page (`x.locate`, which now also answers
  `custodian` and `mount` lists; an older node omits them and they read unknown) within half the sync
  budget, at most 10 s; a site that does not answer leaves its copies' `presence` UNKNOWN. `tape=detail`
  (OUT-96 S-3) adds, from the same locate, each tape copy's `file_number` and `block` (its container's tape
  file and the logical block of the record holding its first byte, from the node's catalogue, no mount) and
  `tape_type` (`LTO-10`, the one generation a real library is configured for, owner 2026-10-01; a simulated
  library says `simulated <tape_sim_profile>`); `x.locate` carries them as additive `position`
  (`<file>:<block>`) and `medium` lists. They name no data and no cartridge, so a reader sees them; the
  barcode stays the system-admin's. core.jobs
  filters by `principal_id` (`principal` is the request signature's own param). `core.tapevol
  op=library` answers the tape node's library as it tracks it (configuration, drives, slots, volumes by
  state, admin state and cohort, queues, counters).
- Site history and containers (OUT-96 S-6, S-4). `core.site op=events [site] [after] [limit]` pages the
  sites' journaled history newest first: each change of a site's lifecycle state (`kind=state`: ACTIVE,
  DRAINING, LOST, DECOMMISSIONED) and of its liveness (`kind=up`: UP, DOWN) as the leader saw it, `{seq, ts,
  site, kind, from, to}` (`from` is "" for the first event of a site the history holds). The leader compares
  the sites with the newest journaled event of each after every probe pass (from the second pass of its term,
  when its up flags are its own) and journals the differences as `siteEvt` deltas in one batch (an engine
  extension, SiteEvents, gated by core_api_deltas, in the metadata hash and snapshots); `ts` is when the
  leader saw the change, within one probe period of it. The newest 20000 events are kept; a page is read from
  the sequence order or the per-site index. `core.site op=containers site [after] [limit]` pages one packed
  site's containers in id order with the live bytes and copies the core's references record in each (what
  compaction decides by; the container's size is the node's). The block table keeps no per-site container
  index yet, so a page costs one pass over the core's container records (about one per GiB stored, never
  per block); a per-site sorted index in the block table would make it a logarithm plus the page.
- The observer role (owner Q6): an unscoped role a system-admin binds to a system principal, for a
  dashboard's own key: the operators' reads above (node list, site status, history and containers, tape
  status and library, the maintenance view), its own jobs, the retention classes; never data, the audit log
  or a change (AuthzMatrixTest holds every verb's decision for it).
- History: a per-collection branch index; cursors are bound to their verb and scope; pages are
  bounded by their limit and `core_page_bytes`. ChainDiff: chain mode (the paths the runs after the
  common history name) or scan mode, with scan and block budgets; property-tested against the
  whole-map diff. Every version made through the API records who, when and a note (`vmetaAt` in its
  own commit batch). New branch names follow the api §2.3 grammar; existing names stay usable.
- Have-check (the own-domain oracle rule, TENANCY §5): DOMAIN scope only for a principal who reads
  the whole domain; FILE scope for named files of a version the caller reads; otherwise 4
  have-read-gated. Present means a committed reference and a stored copy. Pages are AES-256-GCM
  under keys from an ECDH exchange signed by the core identity. The publish of a have-check upload
  pins present blocks only if still referenced (have-stale), reads them back authenticated, checks
  every block canonical and the whole-file hash, and gives the FileEntry and run a full upload gives.
- Extracts: selector grammar v1, salted leaves, an RFC 6962 root over SHA-384, a certificate signed
  by the core identity (verified again by every replica before xpin applies), pinning by runs or by
  selection, the 4x amplification refusal with arithmetic and rewrites, dry_run.
- Two-phase pins (api §4.4, OUT-47, 2026-10-08): a pin whose holds exceed `core_extract_xsel_chunk_bytes` (1 MiB of
  canonical JSON) is journaled in two phases. `xres` verifies the certificate, charges the pin and opens a RESERVING
  record with a TTL (`core_extract_reservation_ttl_ms`, 15 min); each `xsel` chunk is checked and held under the
  engine's monitor as it is journaled (collections live, runs adopted or inherited, paths still entries of their run),
  and the last chunk pins (PINNED, the certificate's pinned_until). A reservation holds like a pin: a member's
  withdrawal is refused (or ends it, withdraw_wins), grant ends and the lifecycle see it. One cut short ends ABANDONED
  at once (its partial holds go, its idempotency key is free), or EXPIRED by the sweeper when its writer died; a retry
  under the same request_id abandons a reservation a lost leader left and pins anew, and the job resolver never takes a
  reservation for an outcome. Records replay and snapshot chunk for chunk (`xsnapc`, then the chunks as journaled,
  deflated in memory). Each chunk costs its own size (measured: the last quarter of a 1,000,000-leaf reservation's 16
  chunks applies as fast as the first, `ExtractReservationScaleTest`); `core_extract_selection_max_leaves` is
  1,000,000. While a core peer does not answer the `xapi2` feature probe no `xres` is emitted and the old single-entry
  bound (20,000 leaves by selection) applies.
- Extracts of inherited entries (api §4, 2026-10-08): an entry a dependent keeps only by inherited references (its
  run's collection withdrawn) is held where the dependent keeps it, by its run (RUNS) or its paths (SELECTION), once
  every block is proven still held for the dependent (its `inherit|` hold, or its hold on a COPY term's copy). A
  BREAK term, no grant at the withdrawal, or a grant ended since is still refused (`extract-unheld-entries`: nothing
  to pin). Every drop of an inherited hold fails closed under an extract (`dropRef` of an `inherit|` holder,
  `dropOwnRefs`, `redact`, and the lifecycle batch's dry check).
- Peer attestation (api §4, 2026-10-08): each voting peer verifies a pinned extract against its own state (the
  certificate is the record's and is signed by a key the core identity has had; the leaves rebuilt from its own
  versions and salts give the certificate's count and root; every held run is kept and held there) and signs
  `Kdf.info("GFS-XATT-1", extract_id, root, peer, ts)` with an attestation key generated in its process and never
  written anywhere (`ExtractVerifier`). The leader asks the other voters over raft (XATT_REQ/XATT_RESP, MAC'd under
  k_raft), attests itself, and journals each valid answer: the peer's key the first time it is used (`peerKey`, kept
  for good, so an attestation verifies after the peer restarts with a new key) and the attestation (`xattest`), which
  every replica verifies against the registered key. New pins are attested automatically (`core_extract_attest`);
  `core.extractattest` asks again and waits up to min(wait_ms, the sync budget), answering `attestation` (ATTESTED
  when every voter attested, PARTIAL, NONE), `attestations` [{peer, pub, ts, sig}], `voters`, `peer_keys` and each
  refusing peer's reason. core.extractstatus and core.extractproof carry the attestations with the certificate.
- Core identity history (api §4, 2026-10-08): `KeyHistory` keeps every public key the core identity has had (epochs)
  and the master kids each was wrapped under. `core.rotatemaster identity=stage` journals a successor key pair
  (`coreIdNext`, wrapped under the current kid, unused) and reports `next_identity_public`, which the operator adds to
  every storage node's `core_public_key` and every client's pin; `identity=activate expect_identity=<it>` makes it the
  identity in one `idRotate` the retiring key endorses (it signs `Kdf.info("GFS-IDROT-1", old, new, ts)`). A new pin
  is verified against the current identity; a snapshot's records against any epoch, so a certificate signed before a
  rotation still installs and verifies; core.extractproof returns `identity_history`. Snapshots carry the endorsed
  chain (`idHist`, once there are two epochs) and a staged successor; a master rotation rewraps the successor too.
- Cuts (api §4.10): one consistent point across up to 64 collections. Each member resolves to a
  named version or its branch head, all in one `cut` delta; the apply re-checks that every
  head-resolved member is still the head (a replica out of step refuses, fail closed). A cut holds
  its members' runs like a pin (RESERVED) until released or expired, and blocks their withdrawal
  under `core_withdraw_vs_pin=refuse`. `core.extract cut_id=... selectors=[{collection_id,
  selector}]` then extracts against exactly the cut's versions; the certificate carries cut_id and
  the citation the cut's id prefix. Cuts carry no pin-byte charge (they hold versions already stored).
- Transforms and derivations (api §7, ENTAIL §13 item 7): ids are keyed per tenant
  (HMAC-SHA-384 under a key derived from the tenant root, V5 default). A transform's image is a file
  in the fabric, frozen as a cite extract for a year (at most 16 GiB). `core.derive` records a
  derivation once however many times it is asked (checked under the engine monitor) and each author
  once. `core.entail` is read-through: recipe_valid, blocking reasons (always NO_EXECUTOR, since
  execution is not built; INPUT_SWEPT, INPUT_REDACTED, TRANSFORM_IMAGE_LOST, NONDETERMINISTIC,
  SHREDDED), the input closure (at most 10,000 nodes), decays_at, the recreation class and a p50/p90
  build-time interval from the last 64 builds reported through `core.built`.

### Have-checks in format-adapter domains

New domains cut with `fmt:dicom@1,nifti@1,tiff@1+cdc:1048576:262144:4194304`: a block boundary where a DICOM
file's pixel data, a NIfTI file's voxels, or a TIFF's IFDs, descriptions and image data begin. A client can
cut exactly as the core does, so these domains take the have-check:

- `core.chunker` answers `client_chunking=allowed`, `formats` (the adapters, `id@version`, in spec order),
  `inner` (the chunker for each region) and that chunker's bounds and public gear table.
- `core.haveopen` takes `chunker=`, the exact spec the client cut with. A format domain requires it, and any
  domain refuses a spec other than its own (`7 chunker-mismatch`), before any hash is read. The adapters are
  named by version, so a client that cuts with another version is refused.
- Per page, a block need only be within the inner chunker's bounds: a region's last block may be short
  anywhere in the file.
- At the publish the core rebuilds the file in order (NEW blocks as received and hashed to their ids,
  PRESENT blocks read back authenticated), re-cuts it with the domain's own chunker as it streams, and
  requires every block it cuts to be exactly the declared block at that position (`non-canonical-block`),
  as well as the whole-file hash (`declared-hash-mismatch`). A client that cuts otherwise commits nothing.
- The oracle rule, keyed and NONE refusals, budgets and every other have-check property are unchanged.
  `core_have_format_adapters=false` refuses these domains again (`chunker-no-client-chunking`).
- Clients: `eval/fmtcut.py` ports CutStream and the three adapters line for line; `gkt.have_upload` uses
  it and declares the spec. Conformance vectors generated from the Java adapters,
  `src/test/resources/conformance/fmt-cut-v1.json` (84 cases) and `fmt-fuzz-v1.json` (1200 mutated
  inputs), are asserted by `FmtConformanceTest` and `eval/test_fmtcut.py`.
- Measured (`eval/results/dedup/have_fmt_dicom_r1.json`, in process, synthetic): re-uploading 32
  de-identified CT instances (16.8 MB) sends 26,720 B (0.16%, one header block per instance), against
  16.07 MB (95.6%) in a plain 1 MiB CDC domain.

### Lifecycle verbs added by the owner decisions of 2026-10-02 (D10, D5, V7)

The lifecycle's own verbs are in docs/LIFECYCLE.md; these follow the same operation model (C2: the reply is
`lc_id` = `job_id` at once; completion by core.lcstatus, core.job, and the record's signed job events).

| Verb | Class | Role | What it does |
|---|---|---|---|
| core.legalorder | C2 | tenant-admin@tenant_id or system-admin; approvers: `lifecycle_quorum_legal_order` (>= 2), a system-admin among them | A LEGAL_ORDER: `order_ref`, `authority`, `action=erase` (selectors as core.forget, `override_legal_hold`) or `action=shorten` (`collection_id`, `class`); `dry_run`, `request_id`, `wait_ms`, `events`. Time-locked by `lifecycle_legal_order_delay_ms`. |
| core.retention op=get | C0 | any role (by `class`), tenant-admin or reader (by `collection_id`) | A retention class with its D10 `ceiling_ms`. |
| core.forget / core.legalorder `deep=true` | C2 | as the verb | D5 DEEP DELETE: once gc has reclaimed what the record freed, the pack containers that held it are rewritten and overwritten with random data before they are unlinked (on a remote packed node that advertises deeperase1, by the node itself: `x.deeperase`); a simulated cartridge is overwritten, a real one awaits an operator's attestation of its physical destruction (core.deepattest). core.lcstatus `deep` reports it. |
| core.deepattest | C0 | system-admin | OUT-94: `lc_id`, `site_id`, `barcode`, `method`, `statement_digest` (SHA-384 hex): an operator attests a cartridge a deep record named was physically destroyed; only a cartridge AWAITING_ATTESTATION. Answers `deep_state`. |

### Sealed params (GFS-SEAL-1, OUT-109)

Every signed core.* request's params, and its reply, can travel sealed end to end between the client and the core
peer that serves it, so the brokers, Cresco controllers and MsgEvent logs on the path see the action, the routing
envelope and ciphertext, never a path, tenant, collection, principal or signature. Format: `ParamSeal` (core),
`gaiakeep.seal` (Python), `Seal` (Java); vectors `clients/conformance/seal-golden-v1.json`, checked by all three.

**Threat model.** In scope: a passive or active party on the control path (a broker, a controller, a log or
debug dump of MsgEvents, a compromised agent relaying them) who reads or rewrites params. It learns which verb was
called, when, between which agents, the envelope below and the sizes; it cannot read the sealed params or replies,
cannot move a sealed body to another verb (the AAD binds the action) or peer (only the peer holding the seal key
opens it), cannot replay one (the GFS-REQ-1 nonce, window and replay horizon are checked on the opened params,
unchanged), and cannot downgrade a client that has seen a seal key from that peer. Out of scope: a compromised core
peer (it holds the plaintext anyway), traffic analysis, and the first contact of a client in `seal=auto` with a
peer an attacker strips the advertisement from (`seal=require` and `core_meta_require_sealed_params` close it).
The dataplane (GKT) and job events are protected separately (OUT-28, GK-CJSON-1).

**Keys.** Each core peer generates its own ECDH P-384 seal key pair in its process with the approved DRBG, never
writes it, and rotates it every `core_seal_key_rotate_ms` (6 h; the previous key is accepted 10 minutes more). No
journal delta, snapshot or state hash changes, and a peer restart is forward secrecy for everything sealed before
it. The core identity (the key clients pin as `core_public_key`) endorses it. Per-peer keys rather than one shared
key: a shared key would have to be journaled or derived from the identity's private key; a peer's own key needs
neither, and a leader change costs a client one core.status to the new leader.

**Advertisement** (core.status on every peer, and every status-18 reply): `seal_pub` (SPKI base64url),
`seal_pub_kid` = hex(SHA-384(SPKI DER))[0,32), `seal_expires` (ms), `seal_peer` (the peer's id), `seal_identity`
(the identity that signed), `seal_sig` = ECDSA P-384 over `Kdf.info("GFS-SEAL-1/key", audience, seal_peer, kid,
seal_pub, seal_expires, seal_identity)`, `seal_required`, and `identity_history` once the identity has rotated. A
client accepts it when `seal_identity` is pinned, or is reached from a pinned key through `identity_history`'s
endorsed rotations (GFS-IDROT-1: each epoch signed by its predecessor over `info("GFS-IDROT-1", old, new, since)`),
so a client pinning the retired identity follows an identity rotation (api §4). An advertisement that is present
and does not verify is an integrity failure: the client never falls back to plaintext over it.

**Request.** The client reuses one ephemeral P-384 key per advertisement (at most 15 minutes or 100,000
requests), Z = ECDH(e, seal_pub) (48 bytes); per request a fresh 32-byte salt and

    K_req, K_rsp = HKDF-SHA-384(salt, Z, Kdf.info("GFS-SEAL-1", "req" | "rsp", kid, seal_epk), 32)
    AAD_dir      = Kdf.info("GFS-SEAL-1", dir, action, kid, seal_epk, seal_salt)

Visible params: `action`, the envelope `request_id`, `read_peer`, `consistency`, `min_index` (what routes or
steers a request before it is opened), and `seal=GFS-SEAL-1`, `seal_kid`, `seal_epk`, `seal_salt` (base64url),
`seal_body` = base64url(iv(12) ‖ AES-256-GCM(K_req, AAD_req, JSON{param: value}) ‖ tag(16)): every other param,
the signature fields (principal, sig_ts, sig_nonce, sig_params, sig) included. The client signs first (GFS-REQ-1
over the plaintext params), then seals. The peer opens the body into the request's params in place, so the
verifier, the authorizer, the audit and every handler run exactly as on plaintext; a sealed param that is also
visible, the action or a scheme field inside the body is refused.

**Reply.** A reply to an opened request whose signature, window and nonce verified carries `seal_reply` =
base64url(iv ‖ AES-256-GCM(K_rsp, AAD_rsp, JSON{param: value}) ‖ tag): every param the core set or changed. The
request's opened params are not echoed (the client re-adds what it sent), the transport's own params come back
unchanged, and `status`, `core_leader`, `core_term`, `core_role`, `commit_index`, `applied_index`, `served_by` and
`replay_horizon` stay visible too (the sealed copy is what a client believes). A request that does not reach
verification (a replay, an expired signature, a follower read refused before its barrier) gets an unsealed
reply of its status, `status_desc`, `reason` and that envelope only, so each K_rsp seals at most once. A client
refuses an OK reply to a sealed request that carries no `seal_reply`. Each K seals one plaintext, with a random
IV drawn inside the crypto module (`GfsCrypto.gcmSeal`; the clients' `aead`/`Aead` modules; KEY-CUSTODY.md §IV).

**Routing.** A follower redirects a sealed request unopened (status 12, `core_leader`): it never sees the params,
spends no nonce and writes no audit record; the client seals afresh to the leader's key (one core.status per new
peer). A follower read (`read_peer` visible) is sealed to that peer and opened there. A request sealed to a key
the peer does not hold (rotated, restarted, another peer's) gets status 18 SEAL_REFRESH with the peer's
advertisement and nothing runs; the client takes the key and sends once more (signed afresh). A body that does
not authenticate is status 3.

**Gating.** `core_seal_params` (default true) advertises and opens; clients seal by default (`seal=auto`) to any
peer that advertises and, once one has, never send it plaintext again; `seal=require` never sends a signed request
in plaintext; `seal=off` never seals. A core peer on an older build advertises nothing and gets plaintext, so a
mixed-version fabric works. `core_meta_require_sealed_params` (default false) refuses plaintext signed requests
with status 18 (naming the key) and sends none of their signed params back; the unsigned probes (core.status,
core.metahash), raft traffic and storage-node registration stay plaintext. Rollout: OPERATIONS.md §14.

## 4. Journal deltas added

All are applied through `StorageEngine.apply`, registered in the delta registry through
`EngineExtension` (`StorageEngine.knownOps()`), replayed, snapshotted and counted in the metaHash.
Unknown ops still throw.

| Op | Args |
|---|---|
| jobAccept | job_id, principal, request_id, verb, target, params_digest, ts, events |
| jobProgress | job_id, progress_json, ts |
| jobEnd | job_id, state, result_json, error_json, ts, at_head |
| jobForget | job_id |
| profile | scope, name, record_json, by, ts |
| collProfile | collection_id, scope, name, record_json |
| vmetaAt / vmeta | collection_id, branch, ts, by, note / vid, ts, by, note |
| xpin | extract_id, cert_json, signer_pub, sig, holds_json, ts |
| xrelease | extract_id, reason, ts, by |
| xextend | extract_id, pinned_until |
| xwithdraw | extract_id, lc_id, ts, stubs_json, alternates_json (V7, 2026-10-02: docs/LIFECYCLE.md) |
| cut | cut_id, record_json, holds_json, ts |
| cutEnd | cut_id, reason, ts, by (through ExtractTable.end) |
| cutSnap | a cut's full state, snapshots only |
| transform | transform_id, record_json, image_extract_id, by, tenant, ts |
| derivation | derivation_id, record_json, tenant, ts (a repeat is a no-op) |
| derivAuthor | derivation_id, principal, purpose_id, ts |
| built | derivation_id, output_json, actuals_json, receipt_id, ts, by |
| xres | extract_id, cert_json, signer_pub, sig, chunks, reserve_until, ts (a two-phase pin's reservation, api §4) |
| xsel | extract_id, seq, holds_chunk_json (the last chunk pins) |
| xsnapc | a chunked record's state, snapshots only (its xsel chunks follow it) |
| xattest | extract_id, peer, peer_pub, ts, sig |
| peerKey | peer, pub, ts (a core peer's attestation key) |
| coreIdNext | wrapped, public, kid (the identity's staged successor; an engine op, gated as wave-2) |
| idRotate | old_pub, new_pub, ts, endorsement (an engine op, gated as wave-2) |
| idHist | history_json, snapshots only |

## 5. Config keys added

core_sync_rpc_max_ms (20000), core_jobs_per_principal (8), core_jobs_max (64), core_job_progress_ms
(10000), core_job_retain_ms (604800000), core_job_threads (4), core_job_retry_after_ms (1000),
core_compose_sync_files (10000), core_ingest_max (64), core_ingest_per_principal (16),
core_ingest_retain_ms (600000), core_diff_chain_max_runs (4096), core_diff_scan_budget (200000),
core_diff_block_budget (10000000), core_page_bytes (4194304), core_have_page_max (1024),
core_have_max_blocks (1048576), core_have_manifest_budget_bytes (1073741824),
core_have_principal_budget_bytes (268435456), core_have_writer_only (deny),
core_dedup_stats_read_gated (true), core_extract_max_amplification (4.0), core_extract_max_leaves
(10000000), core_extract_selection_max_leaves (1000000; was 20000), core_extract_xsel_chunk_bytes (1048576),
core_extract_reservation_ttl_ms (900000), core_extract_attest (true), core_extract_sync_leaves (100000),
core_extract_pin_bytes_per_tenant (109951162777600), core_extract_max_active_per_principal (1024),
core_withdraw_vs_pin (refuse), core_cut_max_ttl_ms (604800000), core_cut_max_active_per_principal (64),
core_cut_max_runs (20000), core_api_deltas (true), core_have_format_adapters (true), core_seal_params (true),
core_seal_key_rotate_ms (21600000), core_seal_sessions (16384), core_meta_require_sealed_params (false; built by
GFS-SEAL-1).

## 6. Defaults adopted where the owner has not decided (flagged)

- **I8, push or poll:** push. Job and commit outcomes are pushed as signed events on the dataplane,
  with core.job and core.putstatus as the authoritative poll fallback (opmodel §2 supersedes the
  api spec's poll-only default).
- **V7, pins versus withdrawal:** an extract pinning a collection refuses that collection's
  withdrawal (`core_withdraw_vs_pin=refuse`); `withdraw_wins` releases it first. A forget of cited data is
  decided by the owner's V7 (2026-10-02, docs/LIFECYCLE.md "V7"): any forget of it, legal or not, leaves a stub in
  the cite extract and mints an alternate version. Extracts reaching
  the data through a derivation or a grant never block and end BROKEN. A PIN-grant dependent's
  extract that holds the base's runs is also ended BROKEN on the base's withdrawal (conservative:
  api §4.8 would keep it valid; carrying the hold over to the inherited references is not built).
- **Dedup counters are read-gated** (`core_dedup_stats_read_gated=true`): a writer-only caller's
  publish reply no longer carries bytes_written, blocks_written or blocks_deduplicated.
- **Have-check for writers:** `core_have_writer_only=deny` (a writer-only principal gets file scope
  at most, never the domain).
- **Profile domains:** a collection created under a profile without a domain gets the tenant's
  profile domain (GROUP `profile/g/<len>:<tenant>/<system|tenant>/<profile>`, shared by that tenant's
  collections of the profile, created on first use; COLLECTION or NONE: `profile/c/<collection>`).
  `core.domain` refuses ids under `profile/`, so no other tenant can take one first. Profiles are immutable (a new policy
  is a new name) and at most 256 per scope. None of the built-ins is GLOBAL-eligible.
- **Admission of commits:** §1a commits and request_id publishes are not counted against the job
  queues; §1a uploads are bounded by `core_ingest_max` and `core_ingest_per_principal` instead.
- **Selection pins travel in xsel chunks** (2026-10-08): `core_extract_selection_max_leaves` defaults to api §4.4's
  1,000,000; chunks of at most 1 MiB of holds; a reservation lives 15 min (`core_extract_reservation_ttl_ms`) before
  the sweeper ends it EXPIRED. Flagged: the chunk size and the TTL are defaults chosen here, not owner decisions.
- **Peer attestation is automatic and best effort** (2026-10-08, flagged): every new pin is attested by every voting
  peer; a pin is PINNED before its attestations arrive (they are journaled as they come; a peer that is down attests
  when asked again). Attestation keys live only in each peer's process (a restart registers a new one; every key a
  peer used stays registered).
- **The core identity rotates only on request, in two steps** (2026-10-08, flagged): `core.rotatemaster identity=stage`
  then `identity=activate`; nothing rotates it automatically, and the storage nodes' and clients' pins of
  `core_public_key` are the operator's to update between the two.
- **Extract salts for NONE domains** use the public nonce (api §4.3 names HKDF(wrapKey(d))).
- **Derivation and transform ids are keyed per tenant (V5):** HMAC-SHA-384 under
  HKDF(tenant root, "gfs/ids/v1"), so the same recipe in two tenants has two ids and an id reveals
  nothing across tenants. Shredding the tenant root makes entail report SHREDDED for good (the id no
  longer recomputes, even under a later root), and core.derive refuses a shredded transform (7
  shredded) without making a root.
- **Extract idempotency:** an extract job's request_id is its idem_key (api §4.5): a retry, and the
  resolution after a leader change, answer the pin already made; never a second pin.
- **core_api_deltas=true:** see §7; turn it off on upgraded peers while any core peer still runs a
  wave-1 build.
- **Cut bounds:** a cut lives 1 d by default and at most 7 d (`core_cut_max_ttl_ms`); 64 active per
  principal; at most 20,000 runs across its members' histories.
- **Extract member names:** `core.extractrelease` instead of api §4.10's `core.unpin extract_id`, which
  would have overloaded the storage-node key verb `core.unpin site_id`.

## 7. Not built

- api §1.6 probe-based apiFmt enablement (core.apienable after a signed core.status probe of every
  voting peer) needs peer versions exchanged over the corelog. Built instead: `core_api_deltas`, an
  operator switch checked at the engine's one emit point. Off, no wave-2 delta is emitted (the verbs
  answer 8 api-not-enabled, commits carry no version record, core.status offers no jobs-1 or
  ingest-1a); on (the default), a peer on an older build that receives one fences (fail closed).
- api §4 is built (2026-10-08, fix/api-record): two-phase reservations, peer attestation, core identity history,
  extracts of inherited entries (§3 above). Not built within it: carrying an extract's hold over to a dependent's
  inherited references when the base it held through is withdrawn (such an extract still ends BROKEN, §6 V7);
  attestation as a precondition of PINNED (a pin holds before its peers attest it); a peer quorum signature on cuts
  (ENTAIL §3.3 quorum_cert).
- api §3: a have-check against a version in another domain (refused, have-foreign-base), the block-list
  file hash. (Have-checks in format-adapter domains are built: see §3, "Have-checks in format-adapter
  domains".)
- api §5-§9 (ENTAIL §13 items 6, 8-10): receipts, coverage and purposes, lease-based residency,
  prospect and realise. Of §7: execution (entail always reports NO_EXECUTOR, executable=false),
  certified de-identification and attested loci (refused unless NONE), receipt_id on core.built is
  recorded but not checked against a receipt.
- §1a: a stale-head commit ends the ingest (the client uploads again under a new request_id);
  reusing the written blocks on the new head is not built. While an §1a upload is written, the
  leader's in-memory block registrations differ from its replicas' until the commit (the engine's
  existing behaviour for any in-flight write, now as long as an upload).
- Done (2026-10-01): core.archive and core.archiveverify (tape) are journaled, idempotent C3 jobs, polled
  with core.job: the archive follows the engine's run in container batches (a cancel aborts it at the next
  batch; a retry with the same request_id after a leader change skips what was archived), the read-back
  is one tape ticket (a cancel cancels it). core.archivestatus still answers an archive or read-back run
  by its id (the job's result names it: archive_id, verify_id). Done the same day: core.compact, an operator verb for packed sites, runs every packed
  site's compaction as a C3 job (one site a slice, as the COMPACT maintenance pass; system-admin only).
