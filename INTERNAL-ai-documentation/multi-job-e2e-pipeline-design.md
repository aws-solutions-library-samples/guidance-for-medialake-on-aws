# Multi-Job E2E Pipeline Design

## Overview

The E2E test pipeline has been redesigned from a single monolithic job into **6 smaller jobs**, each completing within 1 hour. This solves the credential expiration and timeout issues.

## Job Structure

### Job 1: `e2e_01_cleanup_infrastructure` (~30-40 min)

- **Purpose**: Delete any existing MediaLake E2E test stacks
- **Timeout**: 1 hour
- **Outputs**: `cleanup_status.txt`
- **Key Features**:
  - Deletes stacks in both us-east-1 and deployment region
  - Handles DELETE_FAILED states with --retain-resources
  - Fresh credentials for entire cleanup operation

### Job 2: `e2e_02_deploy_stack` (~5-10 min)

- **Purpose**: Create S3 bucket, upload source, initiate CloudFormation deployment
- **Timeout**: 1 hour
- **Inputs**: `cleanup_status.txt`
- **Outputs**:
  - `stack_name.txt`
  - `s3_bucket_name.txt`
  - `deploy_region.txt`
- **Key Features**:
  - Creates temporary S3 bucket with unique UUID
  - Zips repository and uploads
  - Creates CloudFormation stack
  - Passes deployment info to next jobs via artifacts

### Job 3: `e2e_03_monitor_deployment` (~20-50 min)

- **Purpose**: Monitor CodePipeline execution (first 50 minutes)
- **Timeout**: 1 hour
- **Inputs**: Stack info from Job 2
- **Outputs**:
  - Stack info (passed through)
  - `pipeline_status.txt` (Succeeded/InProgress/Failed)
- **Key Features**:
  - Fresh credentials for monitoring
  - Monitors for up to 50 minutes
  - Saves status for next job if still running

### Job 4: `e2e_04_continue_monitoring` (~0-50 min)

- **Purpose**: Continue monitoring if pipeline still in progress
- **Timeout**: 1 hour
- **Inputs**: Stack info + pipeline status from Job 3
- **Outputs**: Updated pipeline status
- **Key Features**:
  - Gets fresh credentials (avoiding 60-min expiration)
  - Skips if pipeline already succeeded in Job 3
  - Monitors for another 50 minutes if needed
  - Can add more continuation jobs if deployment takes longer

### Job 5: `e2e_05_run_tests` (~10-20 min)

- **Purpose**: Run Playwright E2E tests against deployed infrastructure
- **Timeout**: 1 hour
- **Inputs**: Stack info from previous jobs
- **Outputs**:
  - Test artifacts (playwright-report/, test-results/)
  - Stack info (for cleanup)
- **Key Features**:
  - Fresh credentials for test execution
  - Extracts CloudFront URL from stack outputs
  - Runs full Playwright test suite
  - Saves test reports as artifacts

### Job 6: `e2e_06_cleanup` (~5-10 min)

- **Purpose**: Clean up temporary S3 bucket
- **Timeout**: 30 minutes
- **Inputs**: S3 bucket info from Job 2
- **When**: Always (even if tests fail)
- **Key Features**:
  - Fresh credentials for cleanup
  - Runs regardless of test success/failure
  - Deletes S3 bucket and all objects

## Benefits

### 1. **Solves Credential Expiration**

- Each job gets fresh credentials from credential vendor
- No job runs longer than 50 minutes (well under 60-min limit)
- No need for complex credential refresh logic

### 2. **Solves Timeout Issues**

- Each job has 1-hour timeout
- Works even if project timeout is set to 1 hour
- Total pipeline can run 4+ hours across all jobs

### 3. **Better Visibility**

- Each step is a separate job in GitLab UI
- Easy to see which stage failed
- Can retry individual jobs without rerunning everything

### 4. **Artifact Passing**

- Stack info, bucket names, status passed between jobs
- No environment variable issues between jobs
- Artifacts expire after 1 day automatically

### 5. **Fail-Fast**

- If cleanup takes too long, only that job fails
- If deployment fails, tests don't run
- Cleanup always runs (when: always)

## Shared Configuration

### Variables Block (`.e2e_variables`)

```yaml
AWS_CREDS_TARGET_ROLE: $US_WEST_2_AWS_IAM_ROLE
DEPLOY_REGION: $US_WEST_2_AWS_REGION
STACK_NAME: "medialake-e2e-test"
# ... etc
```

### Before Script (`.e2e_aws_setup`)

- Shared AWS setup for all jobs
- Installs AWS CLI, verifies credentials
- Reduces duplication

## Migration Path

### Option 1: Replace Existing Job

1. Comment out or remove the old `playwright_e2e_test` job
2. Add the new 6-job structure
3. Test on a branch first

### Option 2: Run Both (Testing)

1. Keep old job with different rules (manual trigger)
2. Add new jobs with normal rules
3. Compare results
4. Remove old job once new one is validated

## File Locations

- **New jobs**: `.gitlab-ci.yml.new_jobs` (ready to integrate)
- **Documentation**: `INTERNAL-ai-documentation/multi-job-e2e-pipeline-design.md`
- **Original job**: Currently in `.gitlab-ci.yml` (lines 421-1074)

## Next Steps

1. Review the new job structure in `.gitlab-ci.yml.new_jobs`
2. Decide on migration approach (replace vs test both)
3. Integrate into main `.gitlab-ci.yml`
4. Test on a merge request to stable branch
5. Monitor first run to verify all jobs complete within 1 hour

## Potential Enhancements

### If Monitoring Takes > 100 Minutes

- Add `e2e_04b_continue_monitoring_2` job
- Chain another 50-minute monitoring window
- Pattern can repeat as needed

### If Cleanup Takes > 40 Minutes

- Split into separate cleanup jobs per region
- Run in parallel using `parallel:` keyword

### Add Deployment Verification

- Add job between deployment and tests
- Verify stack outputs, endpoints available
- Smoke tests before full E2E suite
