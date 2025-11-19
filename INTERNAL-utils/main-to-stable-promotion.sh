#!/bin/bash

set -e

CUSTOM_MSG="release: Update to stable branch for release"

echo "======================================"
echo "Syncing main to stable for release"
echo "======================================"

# Fetch latest from origin
echo "Fetching from origin..."
git fetch origin

# Start clean to avoid stuck rebase state
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    echo "Aborting previous incomplete rebase..."
    git rebase --abort || rm -rf .git/rebase-merge .git/rebase-apply
fi

# Checkout stable branch explicitly
echo "Checking out stable branch..."
git checkout -B stable origin/stable || git checkout -B stable

# Merge main into stable (fast-forward if possible)
echo "Merging main into stable..."
git merge origin/main --ff-only -m "$CUSTOM_MSG" || {
    echo "Fast-forward not possible, performing regular merge..."
    git merge origin/main -X theirs -m "$CUSTOM_MSG"
}

# Push stable branch
echo "Pushing stable branch to origin..."
git push origin stable --force-with-lease

echo "======================================"
echo "✅ Successfully synced main to stable"
echo "✅ Pipeline should trigger on stable branch"
echo "======================================"
