# Audit

Who did what to the core, what the core decided, and why — every signed call leaves one record, and this page reads
them (`core.audit`, auditor role).

![The Audit page: the peer's log with filters, newest records first, the head sequence and the window read](../assets/dashboard/audit.png)

## The log

Each core peer keeps its own hash-chained audit log; the page reads the peer you pick from the core's peers
(newest first, 100 records at a time):

| Column | Meaning |
|---|---|
| Seq | The record's position in the peer's chain. |
| Time | When the call was answered. |
| Principal | Who made the call. |
| Action | The verb called (for example `core.put`, `core.tapevol`). |
| Decision | `allow` or `deny`. |
| Code / Target / Reason | The status code, the target of the call, and the reason for a refusal (for example the role rule that denied it). |
| Collection | The collection the call touched, where the verb has one. |

The note under the table anchors the window: the peer's head sequence, the span shown, whether the rows are a
filtered search, and how many `core.audit` calls produced the page.

## Filters

Principal, action (verb), and a from/to time range. The core filters by scanning forward from a starting sequence,
so the dashboard never asks for a filtered search without a window: a rare filter costs at most the newest
10 000 records of the chosen peer. Older pages walk backwards from a sequence number.

## Chain verification

Verifying a peer's audit chain end to end against the anchors journaled for it (`core.auditverify`) is an
auditor control, not a background read — it belongs to the [Controls](controls.md) design with the other operator
actions. A chain state of `lost` (a log that lost records the journal anchored) is surfaced on the peer's
[Overview](overview.md) row and must be acknowledged with `core.auditack`.

!!! note "Search at scale"
    Searching by principal or action without a time bound needs indexes on (principal, seq) and (action, seq) in
    the log — the design record's open item S-5.
