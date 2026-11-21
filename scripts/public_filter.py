#!/usr/bin/env python3
"""
What may appear on the public site, in one place.

scrub(text)  rewrites internal detail (workstation paths, cluster hosts, accounts and storage paths,
             private addresses) into neutral words. sync_design.py applies it to every copied document.
private(text) says whether a document is marked private in its opening lines; sync_design.py refuses one.
check(root)  fails on anything that must never be published (credentials, a document marked private) and on
             internal detail that survived; the deploy workflow and the pre-push hook run it.

    python3 scripts/public_filter.py check [docs]
"""
import re
import sys
from pathlib import Path

# (pattern, replacement): internal detail rewritten on the way into the site
SCRUB = [
    (re.compile(r"/Users/[^\s)`'\"\]]+"), "<local workspace path>"),
    (re.compile(r"/home/vbu\d+[^\s)`'\"\]]*"), "<cluster home>"),
    (re.compile(r"/project/ibi-staff[^\s)`'\"\]]*"), "<cluster project storage>"),
    # the cluster's bare mount points (shared project storage, node-local disk), as prose names them
    (re.compile(r"(?<![\w./:-])/project\b"), "shared project storage"),
    (re.compile(r"(?<![\w./:-])/local\b"), "node-local storage"),
    (re.compile(r"\bdgx\.ai\.uky\.edu\b"), "the HPC cluster"),
    (re.compile(r"\bslogin-\d+\b"), "a login node"),
    (re.compile(r"\bvbu\d{3}(_[a-z0-9]+)?\b"), "<cluster account>"),
    (re.compile(r"\b(10|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
    (re.compile(r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
    # facility and institution names are never published (owner decision 2026-10-06).
    # The cluster is "the HPC cluster"; its nodes are "cluster node N"; harness paths are eval/cluster/.
    (re.compile(r"\bthe UK DGX\b"), "the HPC cluster"),
    (re.compile(r"\bthe DGX cluster\b"), "the HPC cluster"),
    (re.compile(r"\bDGX cluster\b"), "HPC cluster"),
    (re.compile(r"\bThe DGX\b"), "The HPC cluster"),
    (re.compile(r"\bthe DGX\b"), "the HPC cluster"),
    (re.compile(r"\ba DGX compute\s+node\b"), "an HPC compute node"),
    (re.compile(r"\ba DGX\s+node\b"), "a cluster node"),
    (re.compile(r"\bDGX-class\b"), "HPC-class"),
    (re.compile(r"\bDGX\b"), "HPC"),
    (re.compile(r"\bdgx-(\d+)\b"), r"cluster node \1"),
    (re.compile(r"\beval/dgx/"), "eval/cluster/"),
    (re.compile(r"\bbench/dgx/"), "bench/cluster/"),
    (re.compile(r"\bmodules/dgx/"), "modules/cluster/"),
    (re.compile(r"_dgx_"), "_cluster_"),
    (re.compile(r"\bdgx\b", re.IGNORECASE), "HPC"),
    # the FABRIC testbed project id (owner request 2026-10-28): the testbed is named, the project is not
    (re.compile(r"\s*\(`project-gaiakeep-fabric-national-test`\)"), ""),
    (re.compile(r"`?project-gaiakeep-fabric-national-test`?"), "the FABRIC project"),
    # partner sites and institutional identifiers
    (re.compile(r"\buky-pub\b"), "site-a-pub"),
    (re.compile(r"\buky\b"), "site-a"),
    (re.compile(r"\buofl\b"), "site-b"),
    (re.compile(r"\bwku\b"), "site-c"),
    (re.compile(r"\bUK campus buildings\b"), "campus buildings"),
    (re.compile(r"\bUK chest CT\b"), "chest CT"),
    (re.compile(r"\bKPDT pathology\b"), "pathology imaging"),
    (re.compile(r"\bKPDT figures\b"), "inventory figures"),
    (re.compile(r"\[\[KentuckyWired\]\] is the natural carrier — state-owned"), "A state-owned"),
    (re.compile(r"\bAny participant in Kentucky\b"), "Any participant"),
    (re.compile(r"\bany participant in Kentucky\b"), "any participant"),
    (re.compile(r"\bIRB-2026-114\b"), "IRB-2026-001"),
    (re.compile(r"\bP_irb2026_114\b"), "P_irb2026_001"),
    (re.compile(r"\blouisville\b"), "site-a"),
]

# never publishable: the check fails outright
FORBIDDEN = [
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"), "GitHub token"),
    (re.compile(r"\bgho_[A-Za-z0-9]{30,}"), "GitHub OAuth token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS key id"),
    (re.compile(r"servicekey-[A-Za-z0-9]{4,}"), "service key"),
    (re.compile(r"\]\(https://github\.com/GaiaKeep/gfs\b"), "link into the private gfs repository (a 404 for readers)"),
    (re.compile(r"^\s*(?:>\s*)?\*\*(?:PRIVATE\b|Private\.\*\*)"), "a document marked private (OUTSTANDING.md, TAPE-FORMAT.md, ...)"),
    (re.compile(r"never goes to the public docs site|not part of the public docs sync"), "a document marked private"),
    (re.compile(r"\b(core_master_key|gfs_secret|service_key)\s*[=:]\s*['\"]?[0-9A-Za-z+/_-]{16,}"), "secret value"),
    (re.compile(r"\bUniversity of Kentucky\b", re.IGNORECASE), "institution name"),
    (re.compile(r"\b[\w.-]*uky\.edu\b"), "institutional hostname"),
    (re.compile(r"\bKentuckyWired\b"), "institutional network name"),
]


PRIVATE = re.compile(r"^\s*(?:>\s*)?\*\*(?:PRIVATE\b|Private\.\*\*)|never goes to the public docs site|not part of the public docs sync")


def private(text: str) -> bool:
    """A document whose opening lines mark it private: it is never copied to this site."""
    return any(PRIVATE.search(line) for line in text.splitlines()[:15])


# The public documentation names no dependency (owner, 2026-11-21). The words it must not contain are kept only as
# SHA-256 digests of their lower-case form, so this public script names none of them; any word holding one (a
# compound identifier included) is refused.
DENY_SHA256 = {'7e3873975beb1bbc29a2ad32b32abfa86c167171aa282062f95befb217b0c334', '70cc3f5141676bc2442767a668f2a528fab5845b621ac3cde0725da0a840f11c', '4425af4a256dd8b7f72563e87467b7f8e66de13b911e230065c0382f81eb8b4c', 'c649ae712de60722742f6346fa1e827fe83d230efd322b461d59943b37fcabbf', 'e0c1bf97b7eb4405fbd0f40e6cf10fea93799c76a5c3cdf7875553ec6de86668', 'cd5d154f9061ee927ee2f3ad9eb5c04450fad1a0bee94a3f7b3d93dd615b198e', '165a0bcdbd95b70e52afb155f2f5430a100c7664066b766d85dcfbf657448d96', '960f984285701c6d8dba5dc71c35c55c0397ff276b06423146dde88741ddf1af', '83f11be5ee6a5cf41a19c344be3755d8919e9fa3ce1a0d3670d689a661529cf7', '57d6f7c06e35a3a3b445e5fce28c1b2b13f76bd7764cd4a8b59a947216260648', '3589ea89dd790d2450b1b727362207e0f128ba2d868c95f18a3a3eb4999a6ac2', 'dc355ec75a2dc4a1d29582933b52f9f2ed71061432d72e1991d8b15445b2ff03', '3a2ff84cb8bd8297d537f405a8354e372f152b4b1a3e742e5293ae5e43db78b6', '0e27150cb1fc10c8366e5924160b7d3c36bc045edf614989b5134136bd719188', 'ebc3ae3876b191a7b1768ef24b3cbbbec119afddaccc356c925b4ea7fb5b1c6d', 'e6b4a2d01195c478066de02171373f5e9c86176ba930420162de9c3023b2dfe6', '0934a9da4eb3926358cd48b87bacb3ffcfd9df6c379348779baa0e03dfef43f7', 'b1fa055a8a6f2aa631619a8a706f5e3cc03a65cfa2dc7aadce910704683e41be', 'bbd7390f2945e23847b747830d6eaa6d4b67d3dd564b6e5b46ab659282b7aa12'}
_DENY_LENS = (4, 5, 6, 7, 8, 9, 10)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def denied(line: str) -> list:
    """The words of a line that contain a denied name (by digest)."""
    import hashlib
    hits = []
    for w in _WORD.findall(line):
        lw = w.lower()
        if any(hashlib.sha256(lw[i:i + n].encode()).hexdigest() in DENY_SHA256
               for n in _DENY_LENS for i in range(0, max(0, len(lw) - n) + 1)):
            hits.append(w)
    return hits


def private_rules(path) -> list:
    """The private [regex, replacement] rules (kept outside this repository) that sync_design.py applies."""
    import json
    p = Path(path)
    if not p.is_file():
        return []
    return [(re.compile(a), b) for a, b in json.loads(p.read_text(encoding="utf-8"))["rules"]]


def scrub(text: str, extra=()) -> str:
    for rx, rep in SCRUB:
        text = rx.sub(rep, text)
    for rx, rep in extra:
        text = rx.sub(rep, text)
    return text


def deny_check(root: Path) -> int:
    """Every text file under root (the whole repository: pages, scripts, configuration), except build output."""
    bad = 0
    skip = {".git", ".venv", "site", "__pycache__"}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or skip.intersection(p.relative_to(root).parts):
            continue
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".pdf"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for w in denied(line):
                print(f"FORBIDDEN a dependency named ({w}): {p}:{n}")
                bad += 1
    return bad


def check(root: Path) -> int:
    bad = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".yml", ".yaml", ".html", ".txt", ".json", ".py", ".js", ".css"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for rx, what in FORBIDDEN:
                if rx.search(line):
                    print(f"FORBIDDEN {what}: {p}:{n}")
                    bad += 1
            for rx, _ in SCRUB:
                if rx.search(line):
                    print(f"internal detail not scrubbed: {p}:{n}: {rx.search(line).group(0)}")
                    bad += 1
    return bad


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "deny":
        root = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
        n = deny_check(root)
        print(f"public_filter: {n} dependency name(s) in {root}")
        sys.exit(1 if n else 0)
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        root = Path(sys.argv[2] if len(sys.argv) > 2 else "docs")
        n = check(root)
        print(f"public_filter: {n} problem(s) in {root}")
        sys.exit(1 if n else 0)
    print(__doc__)
