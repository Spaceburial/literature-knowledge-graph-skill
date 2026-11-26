#!/usr/bin/env bash
# Publish this skill directory to a GitHub repo and print the public link.
# Requires: GITHUB_TOKEN with repo scope, and OWNER/REPO as arguments.
#   GITHUB_TOKEN=... ./publish_github.sh <owner> <repo> [branch]
# Nothing is claimed to be public until this script reports success.
set -euo pipefail
OWNER="${1:?owner}"; REPO="${2:?repo}"; BRANCH="${3:-main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${GITHUB_TOKEN:?set GITHUB_TOKEN}"
API="https://api.github.com"
auth=(-H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json")
# create repo if absent (idempotent)
curl -sf "${auth[@]}" "$API/repos/$OWNER/$REPO" >/dev/null 2>&1 || \
  curl -sf -X POST "${auth[@]}" "$API/user/repos" \
    -d "{\"name\":\"$REPO\",\"private\":false}" >/dev/null
cd "$ROOT"
git init -q 2>/dev/null || true
git add -A
git -c user.name="lkg-skill" -c user.email="noreply@example.com" commit -qm "literature-knowledge-graph skill" || true
git branch -M "$BRANCH"
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:$GITHUB_TOKEN@github.com/$OWNER/$REPO.git"
git push -u origin "$BRANCH"
echo "https://github.com/$OWNER/$REPO/tree/$BRANCH"
