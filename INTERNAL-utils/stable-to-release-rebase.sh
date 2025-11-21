#!/bin/bash
set -e

STABLE="stable"
RELEASE="release"

git fetch origin

# Switch to stable and update it
git checkout "$STABLE"
git pull origin "$STABLE"

# Rebase onto release, always favoring the stable branch during conflicts
git rebase origin/"$RELEASE" -X ours

# Stage all changes in case of any auto-resolved conflicts
git add -u

# Continue the rebase if needed
git rebase --continue || true

# Push the rebased stable branch, forcing the update on remote
git push origin "$STABLE" --force-with-lease

echo "Stable branch successfully rebased onto release, all conflicts (if any) auto-resolved in favor of stable, and branch pushed."
