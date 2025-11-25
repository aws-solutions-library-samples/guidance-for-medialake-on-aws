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
        # Handle modify/delete conflicts - if file doesn't exist in main, remove it
        git status --short | grep '^DU' | awk '{print $2}' | while read file; do
            echo "File deleted in main, removing: $file"
            git rm "$file"
        done

        # Handle regular merge conflicts - prefer main's version
        for file in $(git diff --name-only --diff-filter=U 2>/dev/null); do
            echo "Resolving conflict in $file (using main's version)"
            git checkout --ours -- "$file"
            git add "$file"
        done

        # Continue rebase if we resolved conflicts
        if ! git diff --name-only --diff-filter=U 2>/dev/null | grep -q .; then
            git rebase --continue || break
        else
            echo "ERROR: Unable to resolve all conflicts automatically"
            exit 1
        fi
    done
}

# Push the rebased stable branch
echo "Pushing rebased stable branch to origin..."
git push origin stable --force-with-lease

echo "======================================"
echo "Stable branch successfully rebased with main"
echo "======================================"
