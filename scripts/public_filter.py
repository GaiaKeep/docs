#!/usr/bin/env python3
"""
What may appear on the public site, in one place.

scrub(text)  rewrites internal detail (workstation paths, cluster hosts, accounts and storage paths,
             private addresses) into neutral words. sync_design.py applies it to every copied document.
check(root)  fails on anything that must never be published (credentials) and on internal detail that
             survived; the deploy workflow runs it before building.

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
    (re.compile(r"\bdgx\.ai\.uky\.edu\b"), "the HPC cluster"),
    (re.compile(r"\bslogin-\d+\b"), "a login node"),
    (re.compile(r"\bvbu\d{3}(_[a-z0-9]+)?\b"), "<cluster account>"),
    (re.compile(r"\b(10|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
    (re.compile(r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"), "<private address>"),
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
    (re.compile(r"\b(core_master_key|gfs_secret|cresco_service_key)\s*[=:]\s*['\"]?[0-9A-Za-z+/_-]{16,}"), "secret value"),
]


def scrub(text: str) -> str:
    for rx, rep in SCRUB:
        text = rx.sub(rep, text)
    return text


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
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        root = Path(sys.argv[2] if len(sys.argv) > 2 else "docs")
        n = check(root)
        print(f"public_filter: {n} problem(s) in {root}")
        sys.exit(1 if n else 0)
    print(__doc__)
