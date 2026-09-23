#!/usr/bin/env python3
"""
Copy the design record from the gfs repository into this site.

Each document gets a status banner saying what it is and which parts have been superseded, so a
reader landing on a September 19 decision knows whether it still holds. Relative links are
rewritten: links to other design documents stay relative, links to code and results become GitHub
URLs in GaiaKeep/gfs, and links to files that no longer exist are reduced to plain text rather than
left broken.

Usage:  python3 scripts/sync_design.py [path/to/gfs]     (default: ../../cresco/code/gfs)
"""

import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
GFS = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (SITE.parent.parent / "cresco/code/gfs").resolve()
SRC = GFS / "docs"
GITHUB = "https://github.com/GaiaKeep/gfs/blob/1.3/"

# (file, title, status, banner). Order is the order in the navigation.
DOCS = [
    ("FROM-SCRATCH-DECISION.md", "From-scratch decision", "Current",
     "The statement of purpose and the decision to remove Bareos (2026-09-20). Current."),
    ("MODULE-DECISIONS.md", "Module decisions (measured)", "Current",
     "The decisions each component raises, with the measurements behind them: 203 tests, 0 failures (2026-09-23)."),
    ("COMPONENTS.md", "Component definitions", "Current",
     "Every component of the durable storage core: interface, what its tests must establish, the decision it feeds."),
    ("TENANCY-AND-DEDUP.md", "Tenancy and deduplication", "Current",
     "Design of record for tenants, collections, dedup domains (NONE, COLLECTION, GROUP, GLOBAL), grants "
     "and per-block hashing (2026-09-23). Every owner-unmade choice is a policy setting with a default."),
    ("SPECIFICATION.md", "Block fabric specification", "Partly superseded",
     "The write-once block fabric specification, written tape-first. **Superseded in part:** "
     "deduplication and content-derived block ids were retired here (§12.3, §18.4) without owner "
     "approval, and are being restored under configurable dedup domains. The ban on plaintext-derived "
     "identifiers (§19.3) becomes policy-dependent, and Bareos (§6) has been removed. A re-cut to a "
     "media-neutral core is pending (question Q1). §20 (GCM counter discipline) is current for sealed data."),
    ("ENTAIL-AGENT-NATIVE-FS.md", "Entail: the agent interface", "Partly superseded",
     "The agent-native interface: prospect/realise, Derivations, Coverage, extracts. **Superseded in "
     "part:** it assumes erasure coding across three tape domains (phase 1 is now replication), fixed "
     "64 KiB chunking and retired deduplication (both reopened by the owner's dedup requirement)."),
    ("STORAGE-BINDINGS-DECISION.md", "Storage bindings decision", "Mostly current",
     "The one-interface-many-media binding decision and its findings table. Current except the "
     "Bareos-specific parts and stripe latency-class homogeneity, which replication makes unnecessary "
     "for replicated copies."),
    ("STORAGE-DIRECTION.md", "Storage direction (history)", "Historical record",
     "The working note that took the design from a tape assessment to the agent-native fabric. Useful "
     "for the reasoning; several recommendations in it (S3/Glacier front end, LTFS, Bareos) were later reversed."),
    ("BAREOS-RECOMMENDATION.md", "Bareos analysis (historical)", "Superseded",
     "**Superseded 2026-09-20: Bareos is out.** Kept because its licence analysis is what led to "
     "that decision, and because its reading of the Bareos source remains accurate."),
    ("TAPE-RESEARCH-PROMPT.md", "Tape research brief", "Historical record",
     "The research brief for the three-site LTO-10 tier. Its retired capacity figures are marked in place."),
    ("RESEARCH-PROMPT.md", "Storage research brief", "Historical record",
     "The deep-research prompt on federated archival storage."),
    ("SYSTEM-REPORT.md", "Prototype system report", "Proven (prototype)",
     "How the September prototype works and how we know it works: 59/59 claims. It describes the "
     "erasure-coded prototype shape."),
    ("CORE-PRINCIPLES.md", "Prototype core principles", "Proven (prototype)",
     "The prototype's principles and architecture (2026-09-17)."),
    ("EVALUATION-PLAN.md", "Evaluation plan", "Proven (prototype)",
     "Every evaluation check with its method, pass criterion and status."),
    ("PROTOTYPE.md", "Running the prototype", "Proven (prototype)",
     "How to build, run and evaluate the prototype locally."),
    ("RESULTS.md", "Prototype results", "Proven (prototype)", "Functional results: 99/99."),
    ("SCALE-RESULTS.md", "Scale results (full)", "Proven (prototype)", "Full scale and performance tables."),
    ("CLAIMS.md", "Claims registry", "Proven (prototype)", "The mechanical claims check: 59/59."),
    ("global-federated-storage-plan.md", "Original plan (2026-09-13)", "Historical record",
     "The starting plan: federated sharing with an opt-in durability tier."),
]

LINK = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)\s]+)\)')


def rewrite_links(text: str, here: Path, local_names: set) -> str:
    def fix(m):
        label, target = m.group(1), m.group(2)
        if re.match(r'^[a-z]+:', target) or target.startswith('#'):
            return m.group(0)
        path, _, anchor = target.partition('#')
        resolved = (here / path).resolve()
        if resolved.parent == SRC and resolved.name in local_names:
            return f"[{label}]({resolved.name}{'#' + anchor if anchor else ''})"
        try:
            rel = resolved.relative_to(GFS)
            if resolved.exists():
                return f"[{label}]({GITHUB}{rel.as_posix()}{'#' + anchor if anchor else ''})"
        except ValueError:
            pass
        return label  # the target is gone; keep the words, drop the broken link
    return LINK.sub(fix, text)


def banner(status: str, note: str) -> str:
    kind = {"Current": "success", "Mostly current": "success", "Superseded": "danger",
            "Partly superseded": "warning", "Historical record": "note"}.get(status, "info")
    return f'!!! {kind} "Status: {status}"\n    {note}\n\n'


def main():
    out = SITE / "docs/design"
    out.mkdir(parents=True, exist_ok=True)
    names = {d[0] for d in DOCS}
    rows = []
    for fname, title, status, note in DOCS:
        src = SRC / fname
        if not src.exists():
            print(f"missing: {src}")
            continue
        body = rewrite_links(src.read_text(encoding="utf-8"), SRC, names)
        (out / fname).write_text(banner(status, note) + body, encoding="utf-8")
        rows.append((fname, title, status, note.split(". ")[0].replace("**", "")))
        print(f"synced {fname}")

    idx = ["# Design record", "",
           "The engineering documents behind this site, copied from `GaiaKeep/gfs` `docs/` with a "
           "status banner on each. **Where a design document disagrees with the Concepts pages, the "
           "Concepts pages and the [Decision log](../roadmap/decisions.md) are current.** These "
           "documents are working records: dense, exhaustive and argued in detail.", "",
           "| Document | Status | What it is |", "|---|---|---|"]
    for fname, title, status, summary in rows:
        idx.append(f"| [{title}]({fname}) | {status} | {summary} |")
    (out / "index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    oq = SRC / "OPEN-QUESTIONS.md"
    if oq.exists():
        body = rewrite_links(oq.read_text(encoding="utf-8"), SRC, set())
        (SITE / "docs/roadmap/open-questions.md").write_text(
            '!!! info "Answer by id"\n    Every decision the owner still needs to make, with a priority '
            'and, where one exists, a recommendation. Source: `GaiaKeep/gfs` `docs/OPEN-QUESTIONS.md`.\n\n'
            + body, encoding="utf-8")
        print("synced OPEN-QUESTIONS.md -> roadmap/open-questions.md")

    # keep the navigation in step with what was synced
    nav = "\n".join(f"      - \"{t}\": design/{f}" for f, t, _, _ in rows)
    y = (SITE / "mkdocs.yml").read_text(encoding="utf-8")
    y = re.sub(r"(  - Design record:\n      - design/index.md\n)(?:      - .*\n)*",
               lambda m: m.group(1) + nav + "\n", y)
    (SITE / "mkdocs.yml").write_text(y, encoding="utf-8")


if __name__ == "__main__":
    main()
