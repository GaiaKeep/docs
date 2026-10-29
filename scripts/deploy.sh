#!/usr/bin/env bash
# Build and publish the public docs site by hand: no GitHub Actions (owner, 2026-10-02).
#
#   scripts/deploy.sh            # gates, strict build, push the built site to gh-pages
#   scripts/deploy.sh --dry-run  # gates and build only
#
# Runs anywhere with git, Python 3.10+ and gitleaks: a workstation or a cluster node. Pages serves the
# gh-pages branch as it is pushed. Push credentials: GH_TOKEN in the environment, else the git
# credential helper of `origin`. The site is public, so nothing is published unless every gate passes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

if [[ -n "${GH_TOKEN:-}" ]]; then
  REMOTE="https://x-access-token:${GH_TOKEN}@github.com/GaiaKeep/docs.git"
else
  REMOTE="origin"
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "deploy: commit or stash your changes first (the site is built from a committed tree)" >&2
  exit 1
fi
SRC="$(git rev-parse --short HEAD)"

echo "== gate 1: secret scan of the whole history (gitleaks)"
# every ref of the repository, from its common git directory: in a worktree (.git is a file) a scan of "." reads
# no commits and passes, which is no gate at all
COMMON="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
SCAN="$(gitleaks git --redact --no-banner --exit-code 1 --log-opts="--all" "$(dirname "$COMMON")" 2>&1)" || { echo "$SCAN"; exit 1; }
echo "$SCAN" | tail -2
N="$(echo "$SCAN" | grep -o '[0-9][0-9]* commits scanned' | grep -o '^[0-9]*' | tail -1)"
if [[ -z "$N" || "$N" -lt "$(git rev-list --count HEAD)" ]]; then
  echo "deploy: the secret scan read ${N:-no} commits, fewer than this branch's $(git rev-list --count HEAD): refusing" >&2
  exit 1
fi

echo "== gate 2: public-content filter"
python3 scripts/public_filter.py check docs

echo "== build (mkdocs --strict)"
VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/mkdocs" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r requirements.txt
fi
rm -rf site
"$VENV/bin/mkdocs" build --strict --quiet
touch site/.nojekyll

if [[ $DRY == 1 ]]; then
  echo "dry run: built $SRC into site/, not published"
  exit 0
fi

echo "== publish $SRC to gh-pages"
WT="$(mktemp -d)"
trap 'git worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"' EXIT
git fetch -q "$REMOTE" gh-pages
git worktree add -q --detach "$WT" FETCH_HEAD
rsync -a --delete --exclude .git site/ "$WT"/
cd "$WT"
git add -A
if git diff --cached --quiet; then
  echo "gh-pages already holds this build"
  exit 0
fi
git -c user.name="$(git -C "$ROOT" config user.name)" -c user.email="$(git -C "$ROOT" config user.email)" \
  commit -q -m "Deploy $SRC (built by scripts/deploy.sh, no GitHub Actions)"
git push -q "$REMOTE" HEAD:gh-pages
echo "published $SRC: https://gaiakeep.github.io/docs/ (live after Pages serves it, about a minute)"
