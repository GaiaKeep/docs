# GaiaKeep GFS — documentation site

MkDocs Material site covering the conceptual system, what has been built and tested, and what
remains. Source for the code and the full design record: [GaiaKeep/gfs](https://github.com/GaiaKeep/gfs).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 scripts/sync_design.py            # refresh docs/design/ and the open questions from ../../cresco/code/gfs
.venv/bin/mkdocs serve                    # http://127.0.0.1:8000
.venv/bin/mkdocs build --strict           # must pass with zero warnings
```

Pushing `main` builds the site and publishes it to the `gh-pages` branch (`.github/workflows/deploy.yml`).

**Writing rule:** every status claim uses one of five labels — Proven, Built, Designed, Proposed, Open —
and every number says whether it was measured or modelled.
