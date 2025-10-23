# GitLab CI/CD 60-Minute Timeout Issue

## Problem

The `playwright_e2e_test` job is being killed at approximately 55-60 minutes, despite having `timeout: 4h` configured.

## Symptoms

1. Job runs successfully for ~55 minutes
2. Pipeline monitoring stops mid-execution with no error message
3. `after_script` runs but all credential refresh attempts fail
4. Total job duration: ~55-60 minutes consistently

## Root Causes

### 1. GitLab Runner Timeout Override

GitLab Runners can have their own timeout configuration that overrides job-level timeouts.

**Check these settings:**

```bash
# On the GitLab Runner machine, check config
cat /etc/gitlab-runner/config.toml
```

Look for:

```toml
[[runners]]
  # This setting can override job timeouts
  request_timeout = 3600  # Default is 1 hour
```

**Fix:** Increase runner timeout in `/etc/gitlab-runner/config.toml`:

```toml
[[runners]]
  request_timeout = 14400  # 4 hours in seconds
```

### 2. Project-Level Job Timeout

GitLab projects can have maximum job timeout limits.

**Check:** Settings → CI/CD → General Pipelines → Timeout

**Fix:** Set to 4 hours (14400 seconds) or higher

### 3. AWS Credential Vendor Session Duration

The AWS credential vendor (`$CI_BUILDS_DIR/.awscredentialvendor/`) may have a hard 1-hour session duration limit.

**Evidence:**

- Credentials work fine until ~60 minutes
- After ~60 minutes, even fresh reads from credential vendor file fail validation
- `after_script` cannot refresh credentials (all 3 attempts fail)

**Fix Options:**

#### Option A: Configure Longer Session Duration

If using AWS STS assume-role, configure longer duration:

```bash
# In your AWS credential vendor configuration
--duration-seconds 14400  # 4 hours
```

Note: Maximum is 12 hours for IAM users, 1 hour for federated users (unless role has longer duration configured)

#### Option B: Use Long-Term Credentials

Instead of credential vendor, use long-term AWS credentials:

```yaml
variables:
  AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY
  AWS_SECRET_ACCESS_KEY: $AWS_SECRET_KEY
  # No session token = long-term credentials
```

#### Option C: Split the Job

Break into multiple jobs with fresh credential sessions:

```yaml
deploy_infrastructure:
  timeout: 1h
  script:
    # Deploy CloudFormation and wait for pipeline

run_e2e_tests:
  needs: [deploy_infrastructure]
  timeout: 1h
  script:
    # Run Playwright tests against deployed stack

cleanup_resources:
  when: always
  needs: [run_e2e_tests]
  script:
    # Clean up resources
```

## Current Mitigations in Place

1. **Credential refresh every 30 minutes** during monitoring
2. **Retry logic** (3 attempts with 5-second delays)
3. **Validation** before using credentials
4. **S3 bucket cleanup in after_script** (runs even on failure)
5. **Error detection** for expired token errors

## Recommended Actions

### Immediate

1. Check GitLab Runner `config.toml` for timeout settings
2. Check Project CI/CD settings for job timeout limits
3. Verify AWS credential vendor session duration configuration

### Long-term

1. Consider splitting job into multiple stages with fresh credentials
2. Or use long-term AWS credentials (less secure but more reliable)
3. Or configure AWS IAM role with longer maximum session duration

## Debugging Commands

```bash
# Check current job timeout from logs
grep -i "timeout" /var/log/gitlab-runner/*

# Check credential vendor file modification times
watch -n 5 'ls -la $CI_BUILDS_DIR/.awscredentialvendor/credentials'

# Monitor credential expiration
while true; do
  echo "$(date): Checking credentials..."
  aws sts get-caller-identity --profile default
  sleep 300
done
```

## Contact

If this persists, contact your GitLab administrator to check:

- GitLab Runner configuration
- Project CI/CD timeout limits
- AWS credential vendor session duration settings
