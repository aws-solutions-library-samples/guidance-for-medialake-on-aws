#!/bin/bash

# Fail on any error
set -e

COMMIT_MSG="release: rebase main from stable"
SCRIPT_PATH="INTERNAL-utils/main-to-stable-promotion.sh"

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
git rebase -X theirs origin/main --reapply-cherry-picks || {
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
            # Special handling for the script itself - keep current version
            if [ "$file" = "$SCRIPT_PATH" ]; then
                echo "  (keeping current script version)"
                git add "$file"
            elif git cat-file -e "HEAD:$file" 2>/dev/null; then
                # File exists in HEAD (main), use that version
                git checkout --ours -- "$file"
                git add "$file"
            else
                # File doesn't exist in main, remove it
                echo "  (file doesn't exist in main, removing)"
                git rm "$file"
            fi
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

# Commit the rebased changes with retry logic for pre-commit hooks
echo "Committing rebased changes..."
git add -A

# Try to commit, if pre-commit hooks fail, stage their fixes and retry
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if git commit -m "$COMMIT_MSG" --allow-empty; then
        echo "Commit successful!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Pre-commit checks failed. Staging fixes and retrying (attempt $RETRY_COUNT/$MAX_RETRIES)..."
            git add -A
        else
            echo "ERROR: Commit failed after $MAX_RETRIES attempts"
            exit 1
        fi
    fi
done

# Push the rebased stable branch
echo "Pushing rebased stable branch to origin..."
git push origin stable --force-with-lease

echo "======================================"
echo "Stable branch successfully rebased with main"
echo "======================================"
