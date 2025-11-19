#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/merge_branches.sh <target-branch> <source-branch> [<source-branch> ...]

Creates (or reuses) <target-branch> from BASE_BRANCH (default: work) and merges each provided
source branch sequentially with --no-ff so that the combined history is preserved.
USAGE
}

if [ $# -lt 2 ]; then
  usage >&2
  exit 1
fi

TARGET_BRANCH=$1
shift
SOURCE_BRANCHES=($@)
BASE_BRANCH=${BASE_BRANCH:-work}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Run this script from within the git repository." >&2
  exit 2
fi

if ! git diff --quiet --ignore-submodules --exit-code; then
  echo "Working tree has uncommitted changes. Commit or stash them before merging." >&2
  exit 3
fi

if git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
  echo "Reusing existing branch '$TARGET_BRANCH'."
  git checkout "$TARGET_BRANCH"
else
  echo "Creating '$TARGET_BRANCH' from base branch '$BASE_BRANCH'."
  git checkout "$BASE_BRANCH"
  git checkout -b "$TARGET_BRANCH"
fi

echo "Merging branches: ${SOURCE_BRANCHES[*]}"
INDEX=0
TOTAL=${#SOURCE_BRANCHES[@]}
for BRANCH in "${SOURCE_BRANCHES[@]}"; do
  INDEX=$((INDEX + 1))
  if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "Branch '$BRANCH' does not exist. Aborting." >&2
    exit 4
  fi
  printf '\n--- (%d/%d) Merging %s into %s ---\n' "$INDEX" "$TOTAL" "$BRANCH" "$TARGET_BRANCH"
  git merge --no-ff "$BRANCH"
  echo "Successfully merged '$BRANCH'."
  git status -sb
  echo "---"
  REMAINING=$((TOTAL - INDEX))
  if [ $REMAINING -gt 0 ]; then
    echo "Branches left to merge:"
    for ((i=INDEX; i<TOTAL; i++)); do
      echo "  - ${SOURCE_BRANCHES[$i]}"
    done
  else
    echo "No more branches to merge."
  fi
  echo
  git checkout "$TARGET_BRANCH" >/dev/null 2>&1
  sleep 0.1
  TARGET_BRANCH=$(git rev-parse --abbrev-ref HEAD)
done

echo "All requested merges completed. Review the log and push the branch when ready."
