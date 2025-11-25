#!/bin/bash

# Fail on any error
set -e

echo "======================================"
echo "Rebasing stable with main (favoring main)"
echo "======================================"

# Ensure you are on a clean working tree
git status
if ! git diff-index --quiet HEAD --; then
  echo "ERROR: Working tree is not clean. Please commit or stash changes."
  exit 1
fi

# Fetch all latest changes
echo "Fetching latest from origin..."
git fetch origin

# Ensure main branch is up to date
echo "Checking out and updating main..."
git checkout main
git pull origin main

# Ensure stable branch is up to date
echo "Checking out and updating stable..."
git checkout stable
git pull origin stable

# Rebase stable onto main, preferring main's changes for all conflicts
echo "Rebasing stable onto main (preferring main)..."
git rebase -X theirs origin/main || {
    echo "Rebase encountered conflicts. Resolving in favor of main..."
    # Manual resolution for remaining conflicts
    while git status | grep -q "rebase in progress"; do
        for file in $(git diff --name-only --diff-filter=U); do
            echo "Resolving conflict in $file (using main's version)"
            git checkout --ours -- "$file"
            git add "$file"
        done
        git rebase --continue || break
    done
}

# Push the rebased stable branch
echo "Pushing rebased stable branch to origin..."
git push origin stable --force-with-lease

echo "======================================"
echo "Stable branch successfully rebased with main"
echo "======================================"
