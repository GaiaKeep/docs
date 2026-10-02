# GaiaKeep GFS — documentation site

MkDocs Material site covering the conceptual system, what has been built and tested, and what
remains. Source for the code and the full design record: [GaiaKeep/gfs](https://github.com/GaiaKeep/gfs).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 scripts/sync_design.py            # refresh docs/design/ and the open questions from ../../cresco/code/gfs
.venv/bin/mkdocs serve                    # http://127.0.0.1:8000
.venv/bin/mkdocs build --strict           # must pass with zero warnings
```

Publishing is by hand, never by GitHub Actions (owner, 2026-10-02): after pushing `main`, run `scripts/deploy.sh`
on a workstation or a DGX node. It runs the gates below, builds with `mkdocs build --strict` and pushes the built
site to the `gh-pages` branch, which Pages serves (`scripts/deploy.sh --dry-run` stops after the build). The home
page's architecture graphic is generated: edit `scripts/make_hero.py` and run it, never the SVG.

**This repository is public.** Every push is gated twice:

- before it leaves the machine, by `scripts/hooks/pre-push` (install once with
  `git config core.hooksPath scripts/hooks`; needs `gitleaks`): `scripts/public_filter.py check docs` and a
  gitleaks scan of the outgoing commits;
- in `scripts/deploy.sh`, by gitleaks over the whole history and the same content check, before anything is built.

The content check fails on credentials, on internal paths, hosts and addresses that survived the scrub, on
links into the private gfs repository, and on any document marked private (`**PRIVATE` or `> **Private.**`
in its opening lines). `sync_design.py` refuses a document marked private at the source and removes a copy
published before it was marked.

**Writing rule:** every status claim uses one of five labels — Proven, Built, Designed, Proposed, Open —
and every number says whether it was measured or modelled.

**Licence.** The text of this site is licensed under [CC BY 4.0](LICENSE) (owner decision 2026-10-02). It covers the documentation only, not the GaiaKeep software.
