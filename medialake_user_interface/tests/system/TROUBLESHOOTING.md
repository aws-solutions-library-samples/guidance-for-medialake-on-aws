# Semantic Search E2E Tests - Troubleshooting Guide

## Overview

This guide provides solutions for common issues encountered when running the semantic search end-to-end tests. Issues are organized by category for easy navigation.

## 📋 Table of Contents

1. [Provider Configuration Issues](#provider-configuration-issues)
2. [Pipeline Deployment Issues](#pipeline-deployment-issues)
3. [Connector and Ingestion Issues](#connector-and-ingestion-issues)
4. [Search and Results Issues](#search-and-results-issues)
5. [Clip Visualization Issues](#clip-visualization-issues)
6. [Authentication Issues](#authentication-issues)
7. [Environment and Setup Issues](#environment-and-setup-issues)
8. [CI/CD Pipeline Issues](#cicd-pipeline-issues)

---

## Provider Configuration Issues

### Issue: "Provider configuration form not displayed"

**Symptoms**:

- Test fails at Step 1 (Setup provider)
- Error: "Provider configuration form not found"
- Timeout waiting for provider selection

**Diagnostic Steps**:

```bash
# Run test with headed browser to see UI
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "Setup provider" --headed --workers=1

# Check if System Settings page loads
npx playwright test tests/system/semantic-search-e2e.spec.ts --debug --workers=1
```

**Solutions**:

1. **Verify user permissions**: Ensure test user has admin access to System Settings
2. **Check page load**: System Settings may have slow load times - increase timeout
3. **Verify selectors**: UI may have changed - check `provider-config-helper.ts` selectors
4. **Clear browser cache**: Run with fresh browser context

```typescript
// Increase timeout in provider-config-helper.ts
await this.page.waitForSelector('[data-testid="provider-config"]', {
  timeout: 60000,
});
```

### Issue: "API key validation failed"

**Symptoms**:

- Error: "Invalid API key" or "API key rejected"
- Provider configuration fails to save

**Diagnostic Steps**:

```bash
# Verify API key is set
echo "TWELVELABS_API_KEY: ${TWELVELABS_API_KEY:+Set}"

# Test API key directly
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "x-api-key: ${TWELVELABS_API_KEY}" \
  "https://api.twelvelabs.io/v1.2/indexes"
```

**Solutions**:

1. **Verify key format**: Ensure no extra whitespace or characters
2. **Check key expiration**: API keys may have expiration dates
3. **Verify key permissions**: Key may lack required scopes
4. **Use correct environment**: Dev vs production API endpoints

### Issue: "Embedding store selection not available"

**Symptoms**:

- Cannot select OpenSearch or S3 Vectors
- Embedding store dropdown is disabled or missing

**Diagnostic Steps**:

```bash
# Run with debug to inspect UI state
PWDEBUG=1 npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "embedding store" --workers=1
```

**Solutions**:

1. **Check provider type**: External providers (Coactive) don't show embedding store options
2. **Verify provider is saved**: Embedding store may only appear after provider is configured
3. **Check feature flags**: Embedding store options may be feature-flagged

---

## Pipeline Deployment Issues

### Issue: "Pipeline deployment timeout"

**Symptoms**:

- Test fails at Step 2 (Deploy pipelines)
- Error: "Pipeline deployment timeout after 300000ms"
- Deployment status stuck at "pending" or "deploying"

**Diagnostic Steps**:

```bash
# Check pipeline status in AWS console
AWS_PROFILE=dev3 aws stepfunctions list-executions --state-machine-arn <arn> --status-filter RUNNING

# Check CloudWatch logs for deployment errors
AWS_PROFILE=dev3 aws logs tail /aws/lambda/medialake-pipeline-deployment --follow
```

**Solutions**:

1. **Increase timeout**: Pipeline deployment may take longer than 5 minutes
   ```typescript
   await pipelineHelper.waitForDeploymentComplete(600000); // 10 minutes
   ```
2. **Check AWS resources**: Verify Lambda, Step Functions, and IAM permissions
3. **Check for stuck deployments**: Previous failed deployments may block new ones
4. **Verify provider compatibility**: Some providers may not support all pipeline types

### Issue: "Pipeline not available for connector"

**Symptoms**:

- Pipeline deployed successfully but not visible in connector configuration
- Error: "No pipelines available for provider"

**Diagnostic Steps**:

```bash
# List available pipelines via API
curl -s -H "Authorization: Bearer ${AUTH_TOKEN}" \
  "${CLOUDFRONT_URL}/api/pipelines" | jq '.pipelines[] | {id, name, provider}'
```

**Solutions**:

1. **Wait for propagation**: Pipeline may take time to appear in UI
2. **Refresh page**: Force reload of pipeline list
3. **Check pipeline status**: Pipeline may be deployed but not "active"
4. **Verify provider association**: Pipeline must be associated with correct provider

---

## Connector and Ingestion Issues

### Issue: "Connector creation failed"

**Symptoms**:

- Test fails at Step 3 (Setup connector)
- Error: "Failed to create connector" or "Bucket not found"

**Diagnostic Steps**:

```bash
# List available S3 buckets
AWS_PROFILE=dev3 aws s3 ls | grep medialake

# Check connector API
curl -s -H "Authorization: Bearer ${AUTH_TOKEN}" \
  "${CLOUDFRONT_URL}/api/connectors" | jq '.connectors'
```

**Solutions**:

1. **Verify S3 bucket exists**: Connector requires an S3 bucket
2. **Check IAM permissions**: User needs S3 and connector API permissions
3. **Verify bucket region**: Bucket must be in same region as MediaLake
4. **Check for naming conflicts**: Connector names must be unique

### Issue: "Content ingestion not completing"

**Symptoms**:

- Test fails at Step 4 (Ingest content)
- Ingestion stuck at "processing" status
- No assets appear in search

**Diagnostic Steps**:

```bash
# Check Step Functions execution
AWS_PROFILE=dev3 aws stepfunctions list-executions \
  --state-machine-arn <pipeline-arn> \
  --status-filter RUNNING

# Check DynamoDB for asset records
AWS_PROFILE=dev3 aws dynamodb scan \
  --table-name medialake-assets \
  --filter-expression "contains(#s, :status)" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":status":{"S":"processing"}}'
```

**Solutions**:

1. **Check pipeline execution**: View Step Functions console for errors
2. **Verify media format**: Ensure test files are supported formats
3. **Check file size**: Large files may exceed Lambda timeout
4. **Verify embedding generation**: Check if embeddings are being created

### Issue: "Assets not searchable after ingestion"

**Symptoms**:

- Ingestion completes but assets don't appear in search
- Search returns empty results

**Diagnostic Steps**:

```bash
# Check OpenSearch index
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://${OS_ENDPOINT}/_cat/indices?v" | grep medialake

# Check if embeddings exist
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://${OS_ENDPOINT}/medialake-embeddings/_count"
```

**Solutions**:

1. **Wait for indexing**: OpenSearch indexing may take time
2. **Check embedding store**: Verify embeddings are stored correctly
3. **Verify index mapping**: Index schema must match embedding dimensions
4. **Check provider status**: Provider must be enabled for search

---

## Search and Results Issues

### Issue: "Semantic search returns no results"

**Symptoms**:

- Test fails at Step 5 (Search for content)
- Search executes but returns empty results
- Error: "No search results found"

**Diagnostic Steps**:

```bash
# Test search API directly
curl -s -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query": "person walking", "provider": "twelvelabs-api"}' \
  "${CLOUDFRONT_URL}/api/search/semantic" | jq '.results'

# Check if provider is enabled
curl -s -H "Authorization: Bearer ${AUTH_TOKEN}" \
  "${CLOUDFRONT_URL}/api/settings/search-provider" | jq '.enabled'
```

**Solutions**:

1. **Verify provider is enabled**: Provider must be active for search
2. **Check embedding store connection**: OpenSearch/S3 must be accessible
3. **Verify assets have embeddings**: Assets must be processed with embeddings
4. **Try different search query**: Query may not match any content
5. **Lower confidence threshold**: High threshold may filter all results

### Issue: "Search results don't include expected assets"

**Symptoms**:

- Search returns results but not the expected test assets
- Relevance scores are unexpectedly low

**Solutions**:

1. **Verify asset was ingested**: Check asset exists in database
2. **Check embedding quality**: Re-process asset if embeddings are poor
3. **Adjust search query**: Use more specific or different terms
4. **Check confidence threshold**: Lower threshold to include more results

---

## Clip Visualization Issues

### Issue: "Clips not visible in search results"

**Symptoms**:

- Test fails at Step 6 (Verify results and clips)
- Video results show but no clip markers
- Error: "No clips found for asset"

**Diagnostic Steps**:

```bash
# Check if clips exist in database
curl -s -H "Authorization: Bearer ${AUTH_TOKEN}" \
  "${CLOUDFRONT_URL}/api/assets/${ASSET_ID}/clips" | jq '.clips'

# Verify clip embeddings
curl -s -u "${OS_USER}:${OS_PASS}" \
  "https://${OS_ENDPOINT}/medialake-clips/_search" \
  -H "Content-Type: application/json" \
  -d '{"query": {"term": {"assetId": "'${ASSET_ID}'"}}}' | jq '.hits.total'
```

**Solutions**:

1. **Verify video was processed**: Clips are only generated for video assets
2. **Check pipeline configuration**: Pipeline must include clip extraction
3. **Verify clip embeddings**: Clips need embeddings for semantic search
4. **Check confidence threshold**: Clips may be filtered by threshold

### Issue: "Clip timestamps incorrect"

**Symptoms**:

- Clips show wrong timestamps
- Clicking clip navigates to wrong position

**Solutions**:

1. **Verify video metadata**: Check video duration and frame rate
2. **Check clip extraction**: Re-process video if clips are incorrect
3. **Verify player sync**: Player may have buffering issues

### Issue: "Confidence threshold not filtering clips"

**Symptoms**:

- Test fails at Step 7 (Adjust confidence)
- Changing threshold doesn't change clip count
- All clips remain visible regardless of threshold

**Diagnostic Steps**:

```bash
# Run with debug to inspect threshold changes
PWDEBUG=1 npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "confidence" --workers=1
```

**Solutions**:

1. **Verify threshold control exists**: Check UI selector for threshold slider
2. **Check clip confidence values**: All clips may have same confidence
3. **Verify threshold is applied**: Check if filter is client-side or server-side
4. **Check for UI bugs**: Threshold control may not be wired correctly

---

## Authentication Issues

### Issue: "Login failed" or "Authentication timeout"

**Symptoms**:

- Test fails before reaching provider configuration
- Error: "Failed to authenticate" or "Login timeout"

**Diagnostic Steps**:

```bash
# Verify Cognito user pool
AWS_PROFILE=dev3 aws cognito-idp list-user-pools --max-results 10

# Check test user exists
AWS_PROFILE=dev3 aws cognito-idp admin-get-user \
  --user-pool-id ${USER_POOL_ID} \
  --username ${TEST_USER_EMAIL}
```

**Solutions**:

1. **Verify AWS credentials**: Check AWS_PROFILE is correct
2. **Check Cognito configuration**: User pool must be accessible
3. **Verify test user**: User may need to be recreated
4. **Check CloudFront URL**: Ensure correct distribution is used

### Issue: "Session expired during test"

**Symptoms**:

- Test fails midway with authentication error
- Error: "Unauthorized" or "Session expired"

**Solutions**:

1. **Increase session timeout**: Configure longer Cognito session
2. **Add session refresh**: Implement token refresh in fixtures
3. **Reduce test duration**: Split long tests into smaller ones

---

## Environment and Setup Issues

### Issue: "Playwright browsers not installed"

**Symptoms**:

- Error: "Executable doesn't exist" or "Browser not found"

**Solution**:

```bash
# Install all browsers
npx playwright install

# Install specific browser
npx playwright install chromium

# Install with dependencies (Linux)
npx playwright install --with-deps
```

### Issue: "Node modules not found"

**Symptoms**:

- Error: "Cannot find module" or "Module not found"

**Solution**:

```bash
cd medialake_user_interface
rm -rf node_modules package-lock.json
npm install
```

### Issue: "TypeScript compilation errors"

**Symptoms**:

- Error: "Type error" or "Cannot find name"

**Solution**:

```bash
# Check TypeScript configuration
npx tsc --noEmit

# Rebuild TypeScript
npm run build
```

### Issue: "Port already in use"

**Symptoms**:

- Error: "Port 5173 is already in use"
- Dev server fails to start

**Solution**:

```bash
# Find and kill process using port
lsof -i :5173
kill -9 <PID>

# Or use different port
PORT=5174 npm run dev
```

---

## CI/CD Pipeline Issues

### Issue: "Tests fail in CI but pass locally"

**Symptoms**:

- Tests pass on local machine
- Same tests fail in GitLab CI/CD

**Diagnostic Steps**:

1. Check CI/CD logs for specific error messages
2. Compare environment variables between local and CI
3. Check browser versions in CI vs local

**Solutions**:

1. **Match browser versions**: Use same Playwright version in CI
2. **Check environment variables**: Ensure all required vars are set in CI
3. **Add retries**: CI environments may be less stable
   ```yaml
   script:
     - npx playwright test --retries=2
   ```
4. **Increase timeouts**: CI may be slower than local
5. **Check resource limits**: CI runners may have memory/CPU limits

### Issue: "API keys not available in CI"

**Symptoms**:

- Tests skip with "API key not found" message
- CI/CD variables not being read

**Solutions**:

1. **Verify variable names**: Must match exactly (case-sensitive)
2. **Check protected status**: Protected vars only available on protected branches
3. **Check masked format**: Masked vars have format restrictions
4. **Verify variable scope**: Check if variable is project or group level

### Issue: "Artifacts not uploaded"

**Symptoms**:

- Test reports not available after CI run
- Screenshots/videos missing

**Solution**:

```yaml
artifacts:
  when: always # Upload even on failure
  paths:
    - medialake_user_interface/playwright-report/
    - medialake_user_interface/test-results/
  expire_in: 30 days
```

---

## 🔧 General Debugging Tips

### Enable Verbose Logging

```bash
# Playwright debug mode
PWDEBUG=1 npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1

# Node debug mode
DEBUG=pw:api npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

### Capture Screenshots and Videos

```bash
# Always capture screenshots
npx playwright test --screenshot=on --workers=1

# Capture video on failure
npx playwright test --video=retain-on-failure --workers=1

# Capture trace for debugging
npx playwright test --trace=on --workers=1
```

### View Test Reports

```bash
# Open HTML report
npx playwright show-report

# View specific trace
npx playwright show-trace test-results/trace.zip
```

### Run Single Test

```bash
# Run specific test by name
npx playwright test --grep "should complete full workflow" --workers=1

# Run specific test file
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

---

## 📞 Getting Help

If you've tried the solutions above and still have issues:

1. **Check existing issues**: Search the project's issue tracker
2. **Collect diagnostic info**: Include error messages, logs, and screenshots
3. **Create minimal reproduction**: Isolate the failing test case
4. **Contact the team**: Reach out to the MediaLake team with details

---

**Last Updated**: December 2025
**Version**: 1.0.0
