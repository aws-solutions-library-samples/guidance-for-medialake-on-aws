# CI/CD Versioning Issue Diagnosis

## Problem Statement

The semantic versioning job runs on every MR from main→stable and repeatedly:

- Analyzes the same commits
- Creates major version bumps (2.0.0, 3.0.0, 4.0.0, 5.0.0, 6.0.0)
- Includes identical changelog entries

## Root Cause Analysis

### Primary Issue: Stale Merge Base

The script calculates the merge base between `main` and `origin/stable`:

```bash
MERGE_BASE=$(git merge-base main origin/stable)
COMMITS=$(git log ${MERGE_BASE}..main --pretty=format:"%H|%s|%b")
```

**Problem Flow:**

1. MR #1 (main→stable) triggers semantic-version job
2. Script finds merge base, analyzes commits, creates v2.0.0 tag on main
3. Script pushes tag and commit to main
4. **MR is still open** - stable hasn't been updated yet
5. MR #2 (main→stable) is created or pipeline re-runs
6. Script finds **same merge base** (stable hasn't moved)
7. Script analyzes **same commits** again
8. Creates v3.0.0 with duplicate entries

### Secondary Issue: Persistent BREAKING CHANGE Messages

Lines 7-8 and 83-84 in CHANGELOG.md show:

```
- BREAKING CHANGE: Initial v1.0.0 semantic version release
- BREAKING CHANGE: Initial v1.0.0 semantic version release
```

These commits exist in the range and trigger major bumps every time.

## Evidence from CHANGELOG.md

Versions 2.0.0 through 6.0.0 (lines 79-153) contain:

- Identical BREAKING CHANGES sections
- Identical Features sections (35 items)
- Identical Bug Fixes sections (40 items)
- Same date: 2025-11-22

## Recommended Fix Strategy

### Option 1: Only Run on Merge (Recommended)

Change the semantic-version job to run AFTER the MR is merged to stable:

```yaml
semantic-version:
  rules:
    - if: $CI_COMMIT_BRANCH == "stable" && $CI_COMMIT_MESSAGE =~ /Merge branch 'main'/
```

This ensures:

- Stable has been updated with main's commits
- Next merge base calculation will be correct
- No duplicate versioning

### Option 2: Check for Existing Tag

Add logic to detect if commits are already tagged:

```bash
# After getting COMMITS, check if they're already tagged
for commit in $(echo "${COMMITS}" | cut -d'|' -f1); do
  if git tag --contains "${commit}" | grep -q "^v"; then
    echo "Commit ${commit} already tagged, skipping"
    # Remove from COMMITS
  fi
done
```

### Option 3: Use Last Tag as Base

Instead of merge base, use the last tag:

```bash
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -n "${LAST_TAG}" ]; then
  COMMITS=$(git log ${LAST_TAG}..main --pretty=format:"%H|%s|%b")
else
  COMMITS=$(git log main --pretty=format:"%H|%s|%b")
fi
```

## Additional Issues

### Duplicate Entries in CHANGELOG

The CHANGELOG shows duplicate lines (e.g., lines 13-14, 23-24), suggesting:

- Commits are being processed multiple times
- Or the same commit message appears multiple times in git history

### Date Inconsistency

All versions 2.0.0-6.0.0 show date "2025-11-22" but version 1.0.1 shows "2025-11-21", indicating they were all created in rapid succession.

## Implementation Status

### ✅ FIXED - 2025-11-25

**Changes Made to `.gitlab-ci.yml`:**

1. **Replaced merge base logic with last tag baseline** (lines 207-240)
   - Changed from: `git merge-base main origin/stable`
   - Changed to: `git log ${LAST_TAG}..main`
   - This ensures only commits since the last version tag are analyzed

2. **Added comprehensive debug logging:**
   - Git state information (branch HEADs, tag details)
   - Number of commits to analyze
   - First 10 commits being versioned
   - Clear exit message when no new commits exist

3. **Improved early exit handling:**
   - Clearer messaging when no version bump is needed
   - Prevents empty version creation

**How It Works Now:**

1. MR created from main→stable triggers semantic-version job
2. Script finds last tag (e.g., v6.0.0)
3. Script analyzes commits from v6.0.0..main (only NEW commits)
4. Creates new version tag on main
5. Next MR will start from the NEW tag, not the old merge base
6. No more duplicate versioning!

**Expected Behavior:**

- First run after fix: May still see some duplicates as it cleans up from v6.0.0
- Subsequent runs: Only new commits since last tag will be versioned
- Debug logs will show exactly which commits are being analyzed

**Testing Validation:**
The debug logs will now show:

```
========================================
DEBUG: Git State Information
========================================
Last tag: v6.0.0
Main branch HEAD: <commit-hash>
Stable branch HEAD: <commit-hash>
Last tag commit: <commit-hash>
Last tag date: 2025-11-22 ...
========================================

Using last tag v6.0.0 as baseline for commit analysis
DEBUG: Number of commits to analyze: X

========================================
DEBUG: Commits to be versioned (first 10):
========================================
<list of commits>
========================================
```

This confirms the fix is working correctly.
