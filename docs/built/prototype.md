# The prototype

Built 2026-09-17 and proven by 2026-09-18 as a Cresco plugin, `io.cresco.gfs`, with three roles:
**index**, **storage** and **publisher**. It runs on the existing Cresco mesh and the existing
`filerepo` plugin; nothing in the transport was reinvented.

!!! info "Scope of the evidence"
    Everything here ran on **one host** (14-core Apple silicon, 36 GB). All nodes share loopback
    networking, so the numbers are compute, broker and protocol ceilings, not wide-area numbers. The
    prototype implements cross-site **erasure coding**. Phase 1 has since moved to replication; see
    [Durability](../concepts/durability.md).

## Functional suite: 99/99

A fresh fabric of 8 Java processes (1 index core and 7 site agents) runs the evaluation plan end to
end through the same public message API a real client uses.

| Section | What is proven |
|---|---|
| E1 | Bundle deployed to 8 agents from the client; the capability inventory answers |
| E2 | 7 nodes registered and up; network probed; availability tracked |
| E3 | A dataset is visible with matching SHA-256 hashes within 2 s; modify, add and **delete** propagate as one delta within 2 s; the raw index is gated by data-use rules |
| E4 | 12 authorization checks: owner, delegate, member and outsider each behave as specified |
| E5 | Grant → origin → dataplane stream, hash-verified; forged, tampered, expired and garbage grants are **refused at the origin** |
| E6 | Promotion puts fragments on 5 distinct non-origin sites; fragments on disk are ciphertext (entropy > 7.9 bits/byte) with no key material on holders; a holder with manifest access can't decrypt |
| E7 | Two data-shard holders killed → detected lost in 12 s → restore still succeeds by decoding → auto-repair regenerates 11 fragments onto a spare site in 9 s **without keys** |
| E8 | On-disk corruption found by scrub → regenerated in place → durable again in 3 s |
| E9 | Site key held 3-of-5 at other sites; approver quorum required; approvals single-use; key destroyed → restore fails closed → rebuilt at another site from 3 shares |
| E10 | Reciprocity: entitlement follows contribution; promotion beyond entitlement is **refused** |
| E11 | Replica converged with an identical state hash; metrics; audit; filerepo regression 10/10 |

The codec self-test passes **23/23**: every loss pattern the code tolerates, for RS (3,2), (4,2),
(10,4) and (2,1), plus Shamir, AES-GCM and tokens.

## Claims registry: 59/59

`gfs_claims.py` marks a documented claim **PROVEN** only when executed checks and recorded
measurements satisfy it. All 59 pass: bytes stay put, project visibility, delegation, origin
enforcement, blind holders, keyless repair, custody, distinct failure domains, the coding math,
reciprocity, loss detection and repair, control-plane isolation under load, and failing closed. The
full table is in [CLAIMS.md](../design/CLAIMS.md).

## Soak, failure and restart campaigns

| Campaign | Result |
|---|---|
| Soak, 20 minutes | 484 operations, 13 kills, error rate 0, every object durable |
| Failure tier F1–F8 | Pass on the final build; after a global-controller kill, the index answers in 9.9 s and nodes are back in 34 s |
| Global restart ×3 on 240 sites | All agents back in ≤ 48.2 s, ≤ 3.6 s per agent, **0 stuck** |
| Plugin identity across restart | Same id back and up in 17.2 s; no new ids |
| 8 regions bridged on one host | 0 bridge flaps in 150 s (was 191 per region) |
| Dashboard | Not-durable object visible in 16.2 s, lost in 26.2 s, repaired in 36.3 s; 58/58 claims |

## Cresco defects found and fixed

The work exposed four problems in Cresco itself. All were fixed in the controller, proven, and
shipped in the Cresco 1.3 agent release.

| Id | Problem | Fix |
|---|---|---|
| W-GFS-6 | After a global-controller restart, agents stayed stuck in connection fault for minutes: shutdown was starved behind a control-plane lock during roughly 20 s reconnect attempts | Fair lock with bounded waits; dead transports disposed before any teardown. Proven over 9 global restarts, all agents back in ≤ 44 s, 0 stuck |
| W-GFS-4 | Persisted plugins came back under a new id after restart | Persisted id reused on reload |
| W-GFS-5 | Regional bridges on one host flapped every ~7 s | Bridges use the broker port each node advertises |
| W-GFS-1 | No policy for named flows between tenants | `broker_cross_tenant_sinks` in the tenant policy |

## Where to read more

[SYSTEM-REPORT.md](../design/SYSTEM-REPORT.md) (how it works and how we know),
[RESULTS.md](../design/RESULTS.md), [EVALUATION-PLAN.md](../design/EVALUATION-PLAN.md),
[PROTOTYPE.md](../design/PROTOTYPE.md) (how to run it).
