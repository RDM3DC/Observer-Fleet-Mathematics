#!/usr/bin/env bash
set -euo pipefail

# Run this from the parent directory that contains your local clone:
#   ./push_observer_fleet.sh /path/to/Observer-Fleet-Mathematics

REPO_DIR="${1:-Observer-Fleet-Mathematics}"

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Repo directory not found or not a git repo: $REPO_DIR"
  exit 1
fi

rsync -av --exclude ".git" ./ "$REPO_DIR"/
cd "$REPO_DIR"

git add .
git commit -m "Initialize Observer Fleet Mathematics framework" || echo "No changes to commit"
git push
