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
- Events: `{job_id, seq, state, progress, result | error, ts, sig}` on the stream the request named
  (`events`), GK-CJSON-1 canonical JSON signed ECDSA P-384 by the core identity, byte for byte the
  clients' golden (`clients/conformance/event-golden-v1.json`, copied to test resources). seq is the
  leader's term x 10^9 plus a per-job count, so it only rises. core.job stays authoritative.
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
| cut | cut_id, record_json, holds_json, ts |
| cutEnd | cut_id, reason, ts, by (through ExtractTable.end) |
| cutSnap | a cut's full state, snapshots only |
| transform | transform_id, record_json, image_extract_id, by, tenant, ts |
| derivation | derivation_id, record_json, tenant, ts (a repeat is a no-op) |
| derivAuthor | derivation_id, principal, purpose_id, ts |
| built | derivation_id, output_json, actuals_json, receipt_id, ts, by |

## 5. Config keys added

core_sync_rpc_max_ms (20000), core_jobs_per_principal (8), core_jobs_max (64), core_job_progress_ms
(10000), core_job_retain_ms (604800000), core_job_threads (4), core_job_retry_after_ms (1000),
core_compose_sync_files (10000), core_ingest_max (64), core_ingest_per_principal (16),
core_ingest_retain_ms (600000), core_diff_chain_max_runs (4096), core_diff_scan_budget (200000),
core_diff_block_budget (10000000), core_page_bytes (4194304), core_have_page_max (1024),
core_have_max_blocks (1048576), core_have_manifest_budget_bytes (1073741824),
core_have_principal_budget_bytes (268435456), core_have_writer_only (deny),
core_dedup_stats_read_gated (true), core_extract_max_amplification (4.0), core_extract_max_leaves
(10000000), core_extract_selection_max_leaves (20000), core_extract_sync_leaves (100000),
core_extract_pin_bytes_per_tenant (109951162777600), core_extract_max_active_per_principal (1024),
core_withdraw_vs_pin (refuse), core_cut_max_ttl_ms (604800000), core_cut_max_active_per_principal (64),
core_cut_max_runs (20000), core_api_deltas (true), core_have_format_adapters (true).

## 6. Defaults adopted where the owner has not decided (flagged)

- **I8, push or poll:** push. Job and commit outcomes are pushed as signed events on the dataplane,
  with core.job and core.putstatus as the authoritative poll fallback (opmodel §2 supersedes the
  api spec's poll-only default).
- **V7, pins versus withdrawal:** an extract pinning a collection refuses that collection's
  withdrawal (`core_withdraw_vs_pin=refuse`); `withdraw_wins` releases it first. Extracts reaching
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
- **Selection pins travel in one journal entry**, so `core_extract_selection_max_leaves` defaults to
  20,000 (api §4.4 names 1,000,000 with xsel chunks, which are not built).
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
- api §4: the xres/xsel two-phase reservation (the pin is one
  atomic batch after an off-lock plan; selections above the single-entry bound are refused),
  peer attestation (ExtractVerifier, core.extractattest), core identity history (a retired identity's
  certificates would no longer verify on replay), extracts of entries kept only by inherited
  references (refused, extract-unheld-entries).
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
