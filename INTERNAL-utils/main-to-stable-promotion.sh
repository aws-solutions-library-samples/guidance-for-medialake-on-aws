#!/bin/bash

set -e

CUSTOM_MSG="release: Update to stable branch for release"

git fetch origin

# Begin rebase favoring "theirs"
git rebase -X theirs origin/main || {
    while git status | grep -q "Unmerged paths"; do
        # Accept "theirs" for all conflicted files
        for file in $(git diff --name-only --diff-filter=U); do
            git checkout --theirs -- "$file"
            git add "$file"
        done
        # Use a custom message for all conflict resolutions
        GIT_COMMITTER_DATE="$(date)" git commit -a -m "$CUSTOM_MSG"
        git rebase --continue || true
    done
}

# Optional: squash to single commit if needed
# git reset --soft origin/main && git commit -m "$CUSTOM_MSG"

# Force-push to remote stable (with safety)
git push origin HEAD:stable --force-with-lease
