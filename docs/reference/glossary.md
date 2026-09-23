# Glossary

**Accessor**
: The robot in a tape library that moves cartridges between slots and drives. A single accessor
  limits useful drives to about 14 per site on scattered work.

**Attested**
: A property asserted by an operator rather than measured, such as `gfs_durability_attested`.
  Always reported as an attestation.

**Binding** (`ExtentBinding`)
: The single interface every storage medium implements. It has no synchronous byte read, no
  delete and no list.

**Block**
: The unit of storage and deduplication. Each block is hashed before storage.

**Collection** (dataset)
: A versioned dataset with its own storage and compliance rules, owned by one tenant.

**Commissioning probe**
: The measurement a storage node runs at start-up: write rate, latency, and whether its durability
  barrier does real work.

**Dedup domain**
: *(Proposed.)* The set of data whose identical blocks may be stored once: sealed, collection,
  tenant or group, or global.

**Derivation**
: A citable object whose identity is its recipe (inputs, transform, parameters). Whether its bytes
  are stored is a scheduling decision; `ABSENT` is a legal state.

**Durability barrier**
: The operation (fsync) that makes a write survive a crash. Measured per locus, and required
  (fail-closed) for any copy that counts toward durability.

**Extract**
: A frozen, deterministic, citable selection from one or more versions. It is the unit of
  citation and reproduction.

**Fail closed**
: When a property can't be shown, refuse. Don't assume.

**Grant**
: Permission for one collection or tenant to reference another's blocks, including what happens
  if the referenced data is withdrawn.

**KEK / DEK**
: Key-encryption key (per site) and data-encryption key (per object). The site key is held in
  Shamir t-of-n custody.

**Locus**
: Any place a copy can live: RAM, NVMe, disk, tape, a shared filesystem. Described by measured
  properties.

**Mount cycle**
: The non-transfer time to use a tape cartridge that isn't loaded: fetch, load, locate, rewind to
  start, unload. Modelled at 295–355 s.

**Oracle (confirmation oracle)**
: Any stored value that lets someone holding a guessed plaintext and no key confirm the guess. It
  is forbidden in sealed domains.

**`prospect` / `realise`**
: The agent interface. `prospect` returns costed options for getting a version somewhere.
  `realise` is the only call that moves bytes.

**Repack**
: Reading a cartridge's live data, writing it elsewhere, and recycling the cartridge. Its cost is
  dominated by the fraction still live.

**Retention floor**
: A time before which data may not be reclaimed. It can only be extended.

**`SegmentCipher`**
: The per-object key counter discipline: one derived key per write, with an IV made from two
  counters.

**Sealed**
: The most isolated dedup domain: nothing shared outside the tenant, and no raw hash leaves it.

**Shoe-shining**
: A tape drive repeatedly stopping and repositioning because data arrives too slowly. It destroys
  throughput and media life.

**Tenant**
: A group, organisation or legal entity that owns collections and holds keys.

**WORM**
: Write-once media. Used per cohort for data that must be immutable, not plant-wide.
