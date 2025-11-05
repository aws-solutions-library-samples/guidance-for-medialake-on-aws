# Semantic Versioning & Changelog Guide

## Overview

Automated semantic versioning has been implemented using conventional commits. The system automatically:

- Analyzes commit messages since the last version tag
- Determines the appropriate version bump (major, minor, or patch)
- Generates a CHANGELOG.md file
- Creates git tags
- Pushes changes back to GitLab

## Workflow

```
Feature Branch → main (squashed)
                  ↓
              stable (merge)     ← 🏷️ Creates version tag + updates CHANGELOG
                  ↓
              release → sync to GitHub (includes CHANGELOG + all tags)
```

## When It Runs

The `semantic-version` job runs automatically **only on the `stable` branch**.

When you merge to stable:

- Analyzes all commits since the last version tag
- Determines version bump type based on commit messages
- Updates CHANGELOG.md with new version number
- Creates and pushes a git tag (e.g., v1.2.3)

When you merge stable → release:

- **No new tags created**
- CHANGELOG and all existing tags are promoted to release
- Everything syncs to GitHub

## Version Bumping Rules

| Commit Type               | Version Bump | Example              |
| ------------------------- | ------------ | -------------------- |
| `feat:`                   | **MINOR**    | 1.2.0 → 1.3.0        |
| `fix:`                    | **PATCH**    | 1.2.0 → 1.2.1        |
| `refactor:`               | **PATCH**    | 1.2.0 → 1.2.1        |
| `perf:`                   | **PATCH**    | 1.2.0 → 1.2.1        |
| `style:`                  | **PATCH**    | 1.2.0 → 1.2.1        |
| `test:`                   | **PATCH**    | 1.2.0 → 1.2.1        |
| `build:`                  | **PATCH**    | 1.2.0 → 1.2.1        |
| `!` or `BREAKING CHANGE:` | **MAJOR**    | 1.2.0 → 2.0.0        |
| `docs:`                   | **No bump**  | Tracked in changelog |
| `ci:`                     | **No bump**  | Tracked in changelog |
| `release:`                | **No bump**  | Tracked in changelog |

### Breaking Changes

Breaking changes can be indicated in two ways:

1. **Using `!` in the commit type:**

   ```
   feat!: completely redesign authentication system
   ```

2. **Using `BREAKING CHANGE:` in the commit body:**

   ```
   feat: update API endpoints

   BREAKING CHANGE: API endpoints have changed
   ```

## CHANGELOG Format

The generated CHANGELOG.md follows this structure:

```markdown
# Changelog

## [1.3.0] - 2025-11-04

### ⚠ BREAKING CHANGES

- feat!: redesign authentication (a1b2c3d)

### ✨ Features

- feat(auth): add SSO support (e4f5g6h)
- feat(ui): add dark mode toggle (i7j8k9l)

### 🐛 Bug Fixes

- fix(api): handle null values correctly (m0n1o2p)

### ⚡ Performance Improvements

- perf(db): optimize query execution (q3r4s5t)

### ♻️ Code Refactoring

- refactor(utils): simplify date handling (u6v7w8x)

### 📝 Other Changes

- docs: update README (y9z0a1b)
- ci: add semantic versioning (c2d3e4f)
```

## Initial Version

- If no tags exist, the first version will be **v1.0.0**
- All subsequent versions follow semantic versioning rules

## Git Tags

- Tags follow the format: `v1.2.3`
- Tags include the full changelog entry in the tag message
- Tags are automatically pushed to GitLab

## What Gets Synced to GitHub

When the `sync-to-github` job runs (on the `release` branch):

- ✅ CHANGELOG.md is included
- ✅ Git tags are synced
- ✅ All code changes
- ❌ Internal documentation (INTERNAL-ai-documentation/)
- ❌ CI configuration (.gitlab-ci.yml)

## Example Workflow

### 1. Develop Features

```bash
git checkout -b feature/add-login
# Make changes
git commit -m "feat(auth): add login functionality"
git push origin feature/add-login
```

### 2. Create MR to main

- MR title: `feat(auth): add login functionality`
- Merge (squashes commits)
- **No semantic-version job runs yet**

### 3. Merge main → stable

- MR title: `feat: Semantic Versioning release` (or any conventional commit)
- Merge (regular merge to preserve history)
- **semantic-version job runs automatically**:
  - Analyzes commits since last tag on stable
  - Calculates new version (e.g., v1.1.0 for feat)
  - Updates CHANGELOG.md with version [1.1.0]
  - Creates git tag v1.1.0
  - Pushes CHANGELOG and tag to stable

### 4. Merge stable → release

- MR title: `release: promote to production`
- Merge
- **sync-to-github job runs**:
  - Syncs code to GitHub
  - Includes CHANGELOG.md with all versions
  - Includes all git tags from main
  - Uses MR title as GitHub commit message

## Checking Versions

### View all tags:

```bash
git fetch --tags
git tag -l
```

### View latest version:

```bash
git describe --tags --abbrev=0
```

### View tag details:

```bash
git show v1.3.0
```

## Troubleshooting

### No version bump happens

- Check that commits follow conventional commit format
- Ensure commits contain types that trigger bumps (feat, fix, refactor, etc.)
- Docs and CI changes alone won't bump the version

### Version calculation seems wrong

- Review the job logs in GitLab CI/CD
- The job shows which commits were analyzed and their bump type
- Highest priority: major > minor > patch

### CHANGELOG not updating

- Verify the semantic-version job succeeded
- Check that the job has permissions to push to the repo
- Review GitLab CI/CD logs for errors

## Best Practices

1. **Use conventional commits consistently** - This ensures accurate versioning
2. **Squash feature branches** - Keeps history clean while preserving all changes in the changelog
3. **Review the generated changelog** - Check CHANGELOG.md after merging to stable
4. **Tag manually if needed** - You can create tags manually if the automation fails
5. **Descriptive commit messages** - The commit subject line appears in the changelog

## Manual Override

If you need to create a version manually:

```bash
# Create tag
git tag -a v1.3.0 -m "Release 1.3.0"

# Push tag
git push origin v1.3.0

# Update CHANGELOG.md manually and commit
git add CHANGELOG.md
git commit -m "chore: update CHANGELOG for v1.3.0"
git push origin stable
```

## Integration with GitHub

The CHANGELOG.md and git tags are automatically included when syncing to GitHub via the `sync-to-github` job. Users on GitHub will see:

- Complete version history via git tags
- Human-readable CHANGELOG.md file
- Commit messages from your MR titles (via the stable→release MR)
