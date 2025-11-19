#!/bin/bash

set -e

CUSTOM_MSG="release: Update stable branch for release"

echo "======================================"
echo "Creating MR: main → stable for release"
echo "======================================"

# Check if glab is installed
if ! command -v glab &> /dev/null; then
    echo "❌ ERROR: GitLab CLI (glab) is not installed"
    echo ""
    echo "Please install glab:"
    echo "  macOS:  brew install glab"
    echo "  Linux:  See https://gitlab.com/gitlab-org/cli#installation"
    echo ""
    echo "After installation, authenticate with: glab auth login"
    exit 1
fi

# Check if authenticated
if ! glab auth status &> /dev/null; then
    echo "❌ ERROR: Not authenticated with GitLab"
    echo "Please run: glab auth login"
    exit 1
fi

# Fetch latest from origin
echo "Fetching from origin..."
git fetch origin

# Ensure we're on main and up to date
echo "Ensuring main branch is up to date..."
git checkout main
git pull origin main

echo ""
echo "Checking for existing MR from main to stable..."

# Check if MR already exists
EXISTING_MR=$(glab mr list --source-branch=main --target-branch=stable --state=opened 2>/dev/null || echo "")

if [ -n "$EXISTING_MR" ]; then
    echo "⚠️  An open MR from main to stable already exists:"
    echo "$EXISTING_MR"
    echo ""
    read -p "Do you want to close it and create a new one? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        MR_IID=$(echo "$EXISTING_MR" | grep -o '![0-9]*' | head -1 | tr -d '!')
        echo "Closing existing MR !$MR_IID..."
        glab mr close "$MR_IID"
    else
        echo "Using existing MR. Exiting."
        exit 0
    fi
fi

echo ""
echo "Creating new merge request from main to stable..."

# Create MR with automatic merge when pipeline succeeds
glab mr create \
  --source-branch main \
  --target-branch stable \
  --title "$CUSTOM_MSG" \
  --description "Automated release merge from main to stable.

This MR will:
- Trigger semantic versioning
- Create a new version tag on main branch
- Update CHANGELOG.md

**Merge strategy:** Prefer changes from main branch (theirs strategy)" \
  --remove-source-branch=false \
  --squash=false \
  --yes

echo ""
echo "======================================"
echo "✅ Merge request created successfully!"
echo "======================================"
echo ""
echo "The semantic-version job will run automatically and:"
echo "  1. Analyze commits between main and stable"
echo "  2. Calculate new version number"
echo "  3. Update CHANGELOG.md on main"
echo "  4. Create version tag on main"
echo ""
echo "After the pipeline passes, you can merge the MR."
echo ""
echo "View MR: $(glab mr list --source-branch=main --target-branch=stable | grep -o 'https://[^ ]*' | head -1)"
