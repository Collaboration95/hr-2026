#!/bin/sh
# Publish the explainer pack (site/, minus the writer notes in site/_template/) to the gh-pages branch.
# GitHub Pages serves that branch at https://collaboration95.github.io/hr-2026/.
# Usage: scripts/publish-site.sh [--push]   (without --push it only commits the branch locally)
set -eu
cd "$(dirname "$0")/.."
REMOTE=${REMOTE:-upstream}
SRC=$(git rev-parse --short HEAD)
TMP=$(mktemp -d)
trap 'git worktree remove --force "$TMP" >/dev/null 2>&1 || true' EXIT

# The pack must never carry the private sample: refuse if a listed private path or raw coordinates slipped in.
if grep -rnoE '9[89]\.[0-9]{5,}|hyperlink-RG' site --include='*.html' --exclude-dir=_template; then
  echo "Possible sample coordinates or reference keys above; not publishing." >&2
  exit 1
fi

if git show-ref --quiet refs/heads/gh-pages; then
  git worktree add --quiet "$TMP" gh-pages
else
  git worktree add --quiet --detach "$TMP"
  git -C "$TMP" checkout --quiet --orphan gh-pages
fi
git -C "$TMP" rm -rq --ignore-unmatch . >/dev/null
rsync -a --exclude '_template' site/ "$TMP"/
git -C "$TMP" add -A
if git -C "$TMP" diff --cached --quiet; then
  echo "gh-pages already matches site/ at $SRC."
else
  git -C "$TMP" commit --quiet -m "docs(pack): publish site/ from $SRC"
  echo "Committed gh-pages from $SRC."
fi
if [ "${1:-}" = "--push" ]; then git push --quiet "$REMOTE" gh-pages && echo "Pushed gh-pages to $REMOTE."; fi
