# Glossary

**Accessor**
: The robot in a tape library that moves cartridges between slots and drives. A single accessor
  limits useful drives to about 14 per site on scattered work.

**Admission** (live tier)
: A tenant administrator's decision that a collection may be realised at a given live node, tied to the
  node's pinned key. It lapses if the key changes. See [The live tier](../concepts/live-tier.md).

**Attestation** (live node)
: A statement signed by a live node's pinned key: that a copy was placed (its keyed root), or that a
  dropped copy's files are gone. A deletion of a live copy ends only on one.

**Attested**
: A property asserted by an operator rather than measured, such as `gfs_durability_attested`.
  Always reported as an attestation.

**Binding** (`ExtentBinding`)
: The single interface every storage medium implements. It has no synchronous byte read, no
  delete and no list.

**Block**
: The unit of storage and deduplication. Each block is hashed before storage.

**Chaos stage**
: The harness that runs a deployment for hours under load while injecting real faults (restarts, site
  rolls, stalls, planned stops, memory pressure, a full live node) and judges every cycle.

**Collection** (dataset)
: A versioned dataset with its own storage and compliance rules, owned by one tenant.

**Commissioning probe**
: The measurement a storage node runs at start-up: write rate, latency, and whether its durability
  barrier does real work.

**COMMITTING**
: The state of a version that is published but not yet committed. A durable version under tape-primary
  commits when its tape copies are verified. Nothing is realised from a committing version.

**Crash cell**
: One registered crash point, armed on a running deployment: the process halts there, restarts, and must
  recover with no operator action.

**Dedup domain**
: *(Proposed.)* The set of data whose identical blocks may be stored once: sealed, collection,
  tenant or group, or global.

**Departure notice**
: A storage node's signed message that it is stopping on purpose, bound to its current boot. The core then
  counts its site down for new work at once; a notice from an earlier boot is ignored.

**Derivation**
: A citable object whose identity is its recipe (inputs, transform, parameters). Whether its bytes
  are stored is a scheduling decision; `ABSENT` is a legal state.

**Drop**
: The end of a live copy: journaled with its cause (a FORGET, a legal order, a withdrawal, expiry,
  eviction, release, …) and finished only on the node's signed attestation.

**Durability barrier**
: The operation (fsync) that makes a write survive a crash. Measured per locus, and required
  (fail-closed) for any copy that counts toward durability.

**Early copy**
: A copy of a version made before the version commits. The live tier never makes one, for anyone, the
  writer included (owner decision 2026-10-27).

**Extract**
: A frozen, deterministic, citable selection from one or more versions. It is the unit of
  citation and reproduction.

**Fail closed**
: When a property can't be shown, refuse. Don't assume.

**Grant**
: Permission for one collection or tenant to reference another's blocks, including what happens
  if the referenced data is withdrawn.

**Hand-over** (leadership transfer)
: A leader that stops or steps down sends `TIMEOUT_NOW` to its most caught-up voter, which is elected at
  once instead of after an election timeout.

**Holder, lease, pin**
: A holder is a principal on whose authority a live copy exists; a lease is how long it is wanted (7 days
  by default); a pin keeps it until a named time and holds its version against routine pruning.

**I1–I6**
: The live tier's invariants, checked after every model step and chaos cycle: inventory equals disk, no
  early copy, every end attested, legal deletion reaches copies, budgets hold, the core is healthy.

**KEK / DEK**
: Key-encryption key (per site) and data-encryption key (per object). The site key is held in
  Shamir t-of-n custody.

**Live copy**
: A committed version, or a path prefix of it, held as read-only native files on a live node.

**Live data, live blocks** (census)
: Blocks some version still references, as counted by the core's census. Not the same thing as the live
  tier.

**Live node**
: A gfs plugin in the `live` role that holds live copies near compute. It registers like a storage node
  but never becomes a site, and nothing it holds counts toward durability.

**Live root**
: The directory a live node keeps its copies in: local disk (node scope) or a shared, authenticated
  filesystem (site scope).

**Live tier**
: Every copy of committed data held as plaintext native files on live nodes near compute, in a journaled
  inventory, never counted toward durability. Formerly called the caching tier.

**Locus**
: Any place a copy can live: RAM, NVMe, disk, tape, a shared filesystem. Described by measured
  properties.

**LT-M1**
: The live tier's model-based test: seeded random sequences of operations and faults against a real
  3-peer core with two live nodes, checked against a model after every step. It runs in every CI run.

**Mount cycle**
: The non-transfer time to use a tape cartridge that isn't loaded: fetch, load, locate, rewind to
  start, unload. Modelled at 295–355 s.

**Oracle (confirmation oracle)**
: Any stored value that lets someone holding a guessed plaintext and no key confirm the guess. It
  is forbidden in sealed domains.

**`outcome_unknown`**
: The answer to a write whose leadership ended under it: the next leader decides whether it happened.
  Clients resend only what is safe to send twice.

**Planned stop**
: A core peer stopped on purpose. It refuses requests with status 12 and `stopping=true`, naming where to
  go, lets admitted requests finish, hands over its leadership and exits.

**`prospect` / `realise`**
: The agent interface. `prospect` returns costed options for getting a version somewhere.
  `realise` is the only call that moves bytes; to a live node it makes a committed version into native
  files (built with the live tier, 2026-10-28).

**Repack**
: Reading a cartridge's live data, writing it elsewhere, and recycling the cartridge. Its cost is
  dominated by the fraction still live.

**Retention floor**
: A time before which data may not be reclaimed. It can only be extended.

**Retired peer**
: A core peer in a planned stop after its hand-over: it appends and applies nothing more and never
  campaigns, but still answers votes and appends until its transport stops.

**Row** (inventory)
: The core's journaled record of one live copy or workspace at one node: `REALISING`, `LIVE`, `DROPPING`,
  then removed.

**Sealed**
: The most isolated dedup domain: nothing shared outside the tenant, and no raw hash leaves it.

**`SegmentCipher`**
: The per-object key counter discipline: one derived key per write, with an IV made from two
  counters.

**Shared-user** (live node)
: A live node whose compute jobs run as the agent's own user. It must be declared, and the node reports
  itself as not production.

**Shoe-shining**
: A tape drive repeatedly stopping and repositioning because data arrives too slowly. It destroys
  throughput and media life.

**Soak**
: A long run (72 hours for the stability gate) under load with periodic faults, judged on success rate,
  elections, invariants, memory and open files.

**Status 11, status 12**
: Retryable answers: 11 is busy or not yet (ask again after `retry_after_ms`); 12 is not the leader, or
  stopping, and names where to go.

**Stuck disk, slow disk**
: A disk is stuck when one write or fsync of the raft log has not returned for 30 s; a slow disk only
  delays commits. A slow disk never costs the leadership; a stuck one hands it over only to healthy peers.

**Tenant**
: A group, organisation or legal entity that owns collections and holds keys.

**Unconfirmed** (drop)
: A live copy whose deletion the core cannot prove: the node reported it stuck, had lost it after it was
  live, changed identity, or was force-dropped. It stays listed and raises an alarm.

**Unsynced backlog**
: Raft log entries staged in memory and not yet written to disk; capped at 64 MiB by default, beyond which
  writes wait and the leader answers busy.

**Workspace**
: A writable copy on a live node, seeded from a committed version, whose changes are published as a new
  version with `core.livepublish`.

**WORM**
: Write-once media. Used per cohort for data that must be immutable, not plant-wide.
