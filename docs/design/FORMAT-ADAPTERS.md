!!! success "Status: Current"
    Audited DICOM, NIfTI and TIFF cut adapters: metadata edits do not rewrite bulk data (shipped in 1.3, 2026-10-01).

# Format adapters

A format adapter recognises one known file format and names the offsets where a block must begin,
so that an edit to the format's embedded metadata leaves the blocks of its bulk bytes unchanged. De-identifying
a DICOM instance rewrites its header, not its pixels; with an adapter, the de-identified copy shares
every pixel block with the original, at any block size.

Code: `core/chunk/format/` (`FormatAdapter`, `FormatRegistry`, `FormatChunker`, `CutStream`, `Limits`).
Tests: `src/test/java/io/cresco/gfs/core/chunk/format/`.

## How it cuts

A spec names adapters, then an inner chunker:

```
fmt:dicom@1+cdc:1048576:262144:4194304
fmt:dicom@1,nifti@1,tiff@1+cdc:1048576:262144:4194304
```

The first adapter, in spec order, whose `detect` accepts the file's first bytes parses it. Its cuts
split the file into regions, and the inner chunker cuts each region as if it were a whole file. A
file no adapter accepts is one region, cut exactly as the inner chunker alone would cut it; the only
extra work is reading its first bytes once (at most 348). With a content-defined inner chunker, the
blocks after a cut depend only on the bytes after it, so an edit before a cut, even one that changes
lengths, changes no block after it.

The engine streams files through `Segments`: each region is read in 16 MiB segments and cut with the
inner chunker's parallel in-memory form, with the carried-over tail rule applied per region. A format
cut therefore costs no parallelism.

## Adapters

| Adapter | Cuts at | Reviewed |
|---|---|---|
| `dicom@1` | the top-level pixel data element's start: (7FE0,0010), (7FE0,0008) float, (7FE0,0009) double | yes, in the default |
| `tiff@1` | each IFD's start and end, each out-of-line ImageDescription's start and end, each image's data start when it lies after its IFD | yes, in the default |
| `nifti@1` | `vox_offset` of a single-file NIfTI-1 (`n+1`) or NIfTI-2 (`n+2`) | yes, in the default |
| `dicom-frag@1` | as `dicom@1`, plus each encapsulated fragment after the offset table | measurement only |
| `tiff-tiles@1` | as `tiff@1`, plus every tile and strip | measurement only |

**dicom@1.** Part-10 files only ("DICM" after the 128-byte preamble). The file meta group is always
explicit VR little endian; the dataset is walked in the syntax (0002,0010) names: explicit or implicit
VR little endian. Only element headers are read. Defined-length values and sequences are skipped by
length; undefined-length sequences are walked item by item to their delimiters with an explicit stack,
at most 32 levels deep. The items of an undefined-length UN are implicit VR (PS3.5 §6.2.2). Deflated
syntaxes (1.2.840.10008.1.2.1.99, 1.2.840.10008.1.2.4.95) and explicit VR big endian end the walk
with no cut: the offsets would mean nothing, or the syntax is retired.

**tiff@1.** Classic TIFF and BigTIFF in either byte order: Aperio SVS, Hamamatsu NDPI, generic
pyramidal TIFF. IFDs are followed through the next-IFD chain and SubIFDs (tag 330), at most 4,096. The
input is a stream, so a structure can be cut only if the adapter learns of it before the stream
reaches it. In the GDC TCGA slides measured here, every IFD and offsets array lies after the image data
it describes (120 of 120 slides, job 223187). The IFD and description regions are still cut there,
which is what a description edit or a label removal touches; the data starts are behind the stream
and are counted as late cuts.

**nifti@1.** Uncompressed images only. A `.nii.gz` is a gzip stream: no adapter matches it, and any
edit to it rewrites every compressed byte after the edit, whatever the chunker.

## The contract

An adapter:

1. Has an id (`[a-z][a-z0-9-]*`) and an integer version. Its behaviour at a listed version never
   changes: any change to what it cuts is a new version.
2. Recognises its format from a bounded prefix (`prefixLength`, at most 1 KiB) in `detect`.
3. Never reads the input. It asks to be shown `wantLength` bytes at `want()`, an offset beyond the
   last one it was shown, and emits cut offsets through a sink. Cuts behind the stream are dropped.
4. Is a deterministic function of the bytes it is shown: no clock, no randomness, no I/O, no shared
   mutable state. The boundaries it produces depend on content only.
5. On anything it does not understand, finishes (`want() == -1`) instead of guessing. Plain chunking
   then continues from that point.
6. Uses no recursion, and bounds its own state (nesting depth, IFD count, pending reads).

The driver (`CutStream`) enforces the bounds itself, without trusting the adapter. Crossing one stops
the adapter, drops its pending cuts, and leaves the rest of the file to the inner chunker:

| Bound | Value |
|---|---|
| detection prefix | 1 KiB |
| one look | 128 KiB (the read-ahead never holds more) |
| looks per file (elements, entries) | 1,048,576 |
| bytes shown per file | 64 MiB |
| pending cuts | 524,288 |
| cuts per file | 1,048,576 |

The adapter is shown copies, never the stream's own buffer. An exception from it, a look that does not
move forward, or a look of the wrong size stops it the same way. Its cuts only choose block boundaries,
so no adapter, however wrong, can change the bytes stored: the blocks always reassemble to the input
exactly.

## Audit checklist

An adapter joins the allowlist (`FormatRegistry.REVIEWED`) only when every item holds:

- [ ] The format's specification is cited. The parser follows it for every structure it walks, and
      finishes on anything else.
- [ ] It reads no identifiers into its state beyond what it needs to cut (a transfer syntax UID, a tag).
      Its `facts` are counts and sizes, never values.
- [ ] No recursion; every loop and every collection is bounded by a named constant.
- [ ] Arithmetic on lengths and offsets is in `long`. No value from the file sizes an allocation.
- [ ] A generator of synthetic files covers every encoding the adapter claims, including nesting and
      byte orders.
- [ ] Property tests: exact round trip on every path (in memory, streamed with tiny reads, engine
      segments at several sizes); determinism; non-matching input cut exactly as the inner chunker.
- [ ] A fixed-seed mutation fuzz test of at least 1,000 iterations: flipped bits, extreme lengths,
      truncation, spliced structure. Never an exception, always an exact round trip.
- [ ] Adversarial inputs finish in bounded time: deep nesting, lengths far past the end, cycles,
      floods of tiny structures.
- [ ] Measured on real data on the HPC cluster: dedup, edit cost, block references per TiB and throughput,
      against the plain chunker it wraps. It must not cost more than it saves.
- [ ] Its id, version and behaviour are recorded here.

The driver's own tests run a rogue adapter that throws, stalls, asks for huge looks, scribbles on the
bytes it is shown and floods cuts. The blocks still reassemble exactly.

Fuzzing uses fixed-seed randomized mutation tests in JUnit rather than Jazzer. Jazzer's JUnit
integration runs only its seed corpus unless `JAZZER_FUZZ=1` is set, and coverage-guided fuzzing needs
its native agent on the build host. CI would therefore run a regression corpus, not fuzz. A later
fuzzing campaign can add it as a test-scoped dependency (Apache-2.0).

## Versions and domains

- A domain records its chunker spec when it is created, and the journal replays that record, so a
  domain keeps its exact adapters and versions forever.
- An adapter id or version that is not on the allowlist is refused when the spec is built. A domain
  cannot be created with it (fail closed), and a measurement-only variant cannot be named.
- A new adapter version is used only by domains created with it. Existing domains keep cutting the way
  they always have, so their dedup never breaks.
- Adapters do not nest, and an id may appear only once in a spec.
- `core_default_chunker` may name reviewed adapters around an unkeyed `cdc:` spec.
- Sealed tenants' default stays plain `keyed-cdc`. A format cut sits at a public, content-determined
  offset (a DICOM header's length, say), which keyed boundaries exist to hide. A sealed tenant can still
  choose `fmt:dicom@1+keyed-cdc:...` per domain. GLOBAL domains refuse a keyed inner chunker, as they
  refuse any keyed chunker.

**Which adapter cut a file.** It is not recorded per file yet. `FileEntry.canonical()` feeds the
version-root hash, so a new field would change every root and the `Delta` semantics. Wave 2
(metacrypt/api) changes `FileEntry`; the proposal for it is an optional `cutBy` field (`dicom@1`,
`none`), left out of `canonical()` when absent so existing roots hash as before, carried in the run
delta's file record. Until then, `FormatChunker.stats()` counts files by adapter and outcome per
domain chunker, and the spec says which adapters could have cut. Since cutting is deterministic,
re-chunking a file under its domain's spec reproduces the decision exactly.

## Client-side cutting (have-checks)

A have-check (api §3) lets a client send only the blocks the core lacks, so the client must cut exactly
the blocks the core would. `eval/fmtcut.py` is a line-for-line port of `CutStream` and the reviewed
adapters (`dicom@1`, `nifti@1`, `tiff@1`), with every `Limits` bound and every fallback to plain CDC.
It keeps Java's arithmetic where Python's differs: 8-byte TIFF fields are signed and their sums wrap.
The Java adapters are normative:

- `src/test/resources/conformance/fmt-cut-v1.json`: 84 cases. Synthetic files in every transfer syntax
  and layout; truncated and malformed headers; huge lengths; signed offsets; detection order. Each
  reachable bound is covered on both sides: 2^20 events, 64 MiB inspected, 4096 IFDs, 65536 pending
  reads, the 65-frame sequence stack.
- `fmt-fuzz-v1.json`: 1200 inputs mutated by a SplitMix64 generator that both languages implement.

`FmtConformanceTest` (Java) and `eval/test_fmtcut.py` (Python) assert the same files, and all cases and
fuzz inputs are identical. The core never trusts the client's cut: it re-cuts the reassembled file at the
publish and refuses any block that differs.

Versioning: a client names the exact spec it cut with, and the core refuses any other. A new adapter
version therefore needs client support before its domains can take a have-check. Until then, such
domains' clients upload whole.

## Measured results

Measured on the HPC cluster with the production chunkers and SHA-384 (array 223418, merge 223419, bench
223420; drivers `eval/fmt/`, results `eval/results/dedup/dicom_aware_r1.json` and
`format_*_r1.json`, provenance `run_format_r1.json`). The DICOM and WSI corpora and edits are those of
the block-size measurement (D-C1-1, lists of job 223029), and every plain-CDC figure reproduces it
exactly. Data was read in place, the edits were made in memory, and only aggregate numbers left the
cluster.

**DICOM**: 410,546 TCIA renal instances, 194 GiB. De-identification (`deid`) pseudonymises names and
IDs, blanks the birth date and accession, shifts dates and remaps UIDs, so lengths change.

| Chunker | Dedup saving | De-id: new bytes per instance | Block refs per TiB | Journal per TiB |
|---|---:|---:|---:|---:|
| `cdc` 64 KiB | 1.42 % | 99.0 KB (19.5 %) | 17.2 M | 2.24 GB |
| `cdc` 256 KiB | 0.93 % | 278 KB (54.8 %) | 4.82 M | 0.63 GB |
| `cdc` 1 MiB | 0.37 % | 470 KB (92.6 %) | 2.57 M | 0.33 GB |
| **`fmt:dicom@1` + `cdc` 1 MiB** | 0.72 % | **4.0 KB (0.8 %)** | 4.73 M | 0.61 GB |
| `fmt:dicom@1` + `cdc` 256 KiB | 1.16 % | 4.0 KB (0.8 %) | 6.96 M | 0.90 GB |
| `fmt:dicom-frag@1` + `cdc` 1 MiB | 0.72 % | 4.0 KB (0.8 %) | 4.73 M | 0.61 GB |

- The copy now stores its header and nothing else: the mean header, up to the pixel data element, is
  4,066 bytes (p95 under 6.9 KB). That is 117× less than plain 1 MiB CDC, and 25× less than 64 KiB
  CDC, with 3.6× fewer block references than 64 KiB. The same-length edit (`inplace`) costs the same
  4.1 KB.
- The price is one more block per instance: 4.73 M references per TiB against 2.57 M.
- Dedup rises from 0.37 % to 0.72 %: with the header split off, identical pixel data in different
  instances now dedups.
- The walk parsed every instance. 409,910 have top-level pixel data and were cut; 636 have none (no
  cut). 372,582 are explicit VR and 37,964 implicit VR. None is deflated, big endian, or malformed.
- No instance has encapsulated pixel data, float or double pixel data, an overlay, or waveform data.
  The largest top-level value before the pixel data averages 76 bytes. So `dicom-frag@1` is
  identical to `dicom@1` on this corpus: fragment cuts could not be tested on real data here. Extra
  cuts at other large elements cannot help, since the whole header is far below any minimum block.
- Adding `dicom@1` to `cdc` 256 KiB buys nothing more for the edit and costs 47 % more references,
  so 1 MiB stays the inner chunker.

**Whole-slide images**: 837 GDC TCGA kidney SVS slides, 377 GiB. `desc` blanks the identifying
Aperio keys in every ImageDescription in place. `grow` rewrites the first description longer, appends
it at the end of the file and repoints the IFD entry. `assoc` removes an associated image: GDC strips
labels and macros, so the thumbnail stands in, with its strips zeroed and its IFD unlinked.

| Chunker | `desc` per slide | `grow` per slide | `assoc` per slide | Block refs per TiB | Tile read amplification |
|---|---:|---:|---:|---:|---:|
| `cdc` 1 MiB | 2.87 MB | 4.32 MB | 2.97 MB | 0.84 M | 240× |
| `fmt:dicom@1` + `cdc` 1 MiB | 2.87 MB | 4.32 MB | 2.97 MB | 0.84 M | 240× |
| **`fmt:tiff@1` + `cdc` 1 MiB** | **1.1 KB** | **1.08 MB** | **2.02 MB** | 0.88 M | 237× |
| `fmt:tiff-tiles@1` + `cdc` 1 MiB | 1.1 KB | 1.08 MB | 2.02 MB | 0.88 M | 237× |

- `dicom@1` passes SVS through untouched: every block is identical to plain CDC.
- `tiff@1` makes the description edit 2,600× cheaper: only the description regions change. `grow`
  still re-stores the last block, because the appended text changes the file's tail. `assoc` saves a
  third. In GDC's layout the thumbnail's strips lie before its IFD, so they cannot be cut apart from
  the previous image's offsets arrays.
- The price is 4.6 % more block references: 14,739 cuts over 837 slides, 17.6 per slide (4.4 IFDs each).
- `tiff-tiles@1` is identical to `tiff@1` here. All 45.5 million tile cuts were late, because every
  GDC IFD and offsets array follows its tiles (job 223187). A streaming chunker cannot cut there, and
  on an IFD-first file the variant would make each tile a block.

**NIfTI**: 123 KiTS23 `imaging.nii.gz` files (every 4th case), float64 NIfTI-1 with `vox_offset` 352.
KiTS23 on the HPC cluster is gzip only: 489 files, 42.1 GB, no uncompressed `.nii` (job 223305).

| Chunker | decompressed (46 GiB): `descrip` | `ext-add` | refs per TiB | as stored (9.7 GiB): `gz-descrip` |
|---|---:|---:|---:|---:|
| `cdc` 64 KiB | 105 KB | 217 KB | 16.4 M | 67.5 MB (80 %) |
| `cdc` 1 MiB | 2.10 MB | 2.89 MB | 0.80 M | 67.5 MB (80 %) |
| **`fmt:nifti@1` + `cdc` 1 MiB** | **352 B** | **384 B** | 0.80 M | 67.5 MB (80 %) |

- Uncompressed, a header edit, or an extension added so that every voxel shifts, stores only the
  header. As stored, nothing helps: an edit re-compressed rewrites 80 % of the file at every block
  size, and no adapter matches a gzip stream. Storing NIfTI uncompressed is what makes it dedup.

**Throughput** (job 223420, 32 CPUs, files held in memory, median of 5 rounds; the node was shared, so
rounds vary by about ±10 %):

| Chunker | DICOM, 3.1 GB: engine / stream | WSI, 8.0 GB: engine / stream | NIfTI, 6.1 GB: engine / stream |
|---|---:|---:|---:|
| `cdc` 1 MiB | 830 / 411 MB/s | 848 / 492 MB/s | 836 / 532 MB/s |
| `fmt:dicom@1` + `cdc` 1 MiB | 855 / 402 MB/s | 809 / 496 MB/s | |
| `fmt:tiff@1` + `cdc` 1 MiB | | 820 / 503 MB/s | |
| `fmt:nifti@1` + `cdc` 1 MiB | | | 858 / 536 MB/s |
| `fmt:dicom@1,nifti@1,tiff@1` + `cdc` 1 MiB | 833 / 410 MB/s | 871 / 473 MB/s | 792 / 528 MB/s |

"Engine" is the storage engine's segmented path (16 MiB segments, the parallel chunker per region);
"stream" is one thread. The adapters cost nothing measurable: every difference is within the noise
between rounds. The parallel path honours the cuts, so no DICOM file needs the sequential path. Both
paths cut identically, which the bench checks on every round.

**Default.** New unkeyed domains get `fmt:dicom@1,nifti@1,tiff@1+cdc:1048576:262144:4194304`
(`ChunkerSpec.DEFAULT_CDC`). On all three corpora it matches the single adapter exactly. Sealed
tenants keep plain `keyed-cdc`, and NONE domains keep `fixed`. Existing domains keep the spec they
recorded. The variants `dicom-frag@1` and `tiff-tiles@1` stay off the allowlist: neither helped on
real data, and tile cuts would multiply block references where they could apply.

## Privacy

A format adapter changes how bytes are cut, not who may share them. Pixel data can itself identify a
person: burned-in text in ultrasound, screenshots and secondary captures, or a face reconstructed from
a head CT or MR. De-identifying the header does not make the pixels anonymous. Bulk blocks are
therefore ordinary blocks: they follow the domain's dedup policy like any other, never a
cross-domain exception because "only the header changed". An original and its de-identified copy share
pixel blocks only when a domain already allows them to share blocks.
