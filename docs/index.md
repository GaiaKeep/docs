# GaiaKeep GFS

**A global file system built for agents, not people.** Its job is to keep versioned datasets
durable and to stream any version wherever it is needed: to a GPU node, a partner site, or an
agent's working cache. Data is stored as raw blocks on memory, NVMe, spinning disk or tape. The
medium does not change how callers use it.

> "The entire point of this system is to be ready to stream versioned datasets wherever they need
> to go. This once again is not for humans, it is for agents and to be used by agents."

The system is required to be five things:

| | What it means here |
|---|---|
| **Programmatic** | No filesystem and no human interface. Agents ask what something would cost, then ask for it. |
| **Versioned** | Every read names a version. Versions and point-in-time extracts are citable and reproducible. |
| **Resilient** | Copies in independent failure domains; loss is detected and repaired without intervention. |
| **Secure** | Encrypted at the origin; storage sites hold only ciphertext; policies scale from full isolation to global sharing. |
| **Distributed** | Runs over the [Cresco](https://crescoedge.github.io/quickstart/) mesh across institutions and sites. |

## Where things stand

This work began as the *Cresco Global File System* prototype (September 2026), and it has moved
further since. The site keeps three things apart that are easy to blur:

- **What is proven.** The prototype, proven on a single host: 99/99 functional checks, 59/59
  documented claims, a 240-site federation and a million-file index. See
  [The prototype](built/prototype.md) and [Scale results](built/scale.md).
- **What has been designed and measured since.** Tape economics, a measured placement engine, a
  fail-closed durability check and the encryption counter discipline. See
  [Since the prototype](built/since-prototype.md) and [Measurements](built/measurements.md).
- **What is still to be decided and built.** The tenant, collection and deduplication model; the
  durable storage core; raw tape I/O; the caching tier. See [Remaining work](roadmap/remaining.md)
  and [Open questions](roadmap/open-questions.md).

Every status claim on this site uses one of five labels:

| Label | Meaning |
|---|---|
| **Proven** | Built, and verified by executed tests or campaigns whose results are recorded. |
| **Built** | Implemented and unit-tested, but not yet on the live path or not yet run end to end. |
| **Designed** | Specified in the design record; not built. |
| **Proposed** | A mechanism has been proposed and is waiting on an owner decision. |
| **Open** | Not yet decided. |

## Reading order

1. [Purpose and principles](concepts/purpose.md): what the system is for and the rules that follow.
2. [Architecture](concepts/architecture.md): the layers and how a request moves through them.
3. [Status at a glance](built/status.md): one table of everything, with its label.
4. [Remaining work](roadmap/remaining.md): the phased plan.

## Source

- Code, harnesses and the full design record: [`GaiaKeep/gfs`](https://github.com/GaiaKeep/gfs)
  (private, branch `1.3`; moved from CrescoEdge on 2026-09-23).
- This site: [`GaiaKeep/docs`](https://github.com/GaiaKeep/docs).
