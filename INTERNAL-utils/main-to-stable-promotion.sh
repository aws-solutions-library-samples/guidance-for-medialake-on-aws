#!/bin/bash

set -e

CUSTOM_MSG="release: Update to stable branch for release"

git fetch origin

# Start clean to avoid stuck rebase state
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    echo "Aborting previous incomplete rebase..."
    git rebase --abort || rm -rf .git/rebase-merge .git/rebase-apply
fi

# Begin rebase, using 'theirs' for all merge conflicts
git rebase -X theirs origin/main || {
    while git status | grep -q "Unmerged paths"; do
        for file in $(git diff --name-only --diff-filter=U); do
            git checkout --theirs -- "$file"
            git add "$file"
        done
        # Use a custom commit message for all resolved conflicts
        GIT_COMMITTER_DATE="$(date)" git commit -m "$CUSTOM_MSG"
        git rebase --continue || true
    done
}

# Optional: Squash to single commit after rebase (uncomment if needed)
# git reset --soft origin/main && git commit -m "$CUSTOM_MSG"

git push origin HEAD:stable --force-with-lease
