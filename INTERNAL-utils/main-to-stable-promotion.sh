#!/bin/bash

# Fail on any error
set -e

CUSTOM_MSG="release: Sync main branch changes into stable (prepared for MR)"

echo "======================================"
echo "Creating MR: main → stable for release"
echo "======================================"

# Ensure you are on a clean working tree
git status
if ! git diff-index --quiet HEAD --; then
  echo "❌ ERROR: Working tree is not clean. Please commit or stash changes."
  exit 1
fi

# Fetch all latest changes
echo "Fetching latest from origin..."
git fetch origin

# Ensure main branch is up to date
echo "Checking out main..."
git checkout main
git pull origin main

# Create MR prep branch from main (unique name for each release)
MR_BRANCH="release/sync-main-into-stable-$(date +%Y%m%d-%H%M%S)"
echo "Creating MR branch: $MR_BRANCH"
git checkout -b "$MR_BRANCH" main

# Rebase stable into MR branch, preferring main's changes (--strategy=theirs for conflicts)
echo "Rebasing origin/stable into $MR_BRANCH (preferring main)..."
git rebase -X theirs origin/stable || {
    # Manual resolution for remaining conflicts (rare)
    while git status | grep -q "Unmerged paths"; do
        for file in $(git diff --name-only --diff-filter=U); do
            git checkout --theirs -- "$file"
            git add "$file"
        done
        git commit -m "$CUSTOM_MSG (Conflict resolved favoring main)"
        git rebase --continue || true
    done
}

# Push MR branch to origin
echo "Pushing MR branch to origin: $MR_BRANCH"
git push origin "$MR_BRANCH"

echo "======================================"
echo "✅ Branch prepared & pushed: $MR_BRANCH"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Visit your GitLab repository in the browser."
echo "2. Create a Merge Request:"
echo "   - Source branch: $MR_BRANCH"
echo "   - Target branch: stable"
echo ""
echo "Fill in your release description and submit the MR."
echo ""
echo "When the MR pipeline runs, the semantic-version job will trigger as expected."
echo ""
