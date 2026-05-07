# API Key Setup Guide

## Overview

This guide explains how to obtain and configure API keys for the semantic search provider tests. API keys are required for TwelveLabs API and Coactive AI providers. Bedrock-based providers do not require API keys as they use AWS IAM authentication.

## 🔑 Required API Keys

| Provider                       | Environment Variable | Required          |
| ------------------------------ | -------------------- | ----------------- |
| TwelveLabs Marengo 2.7 API     | `TWELVELABS_API_KEY` | Yes               |
| TwelveLabs Marengo 2.7 Bedrock | None                 | No (uses AWS IAM) |
| TwelveLabs Marengo 3.0 Bedrock | None                 | No (uses AWS IAM) |
| Coactive AI                    | `COACTIVE_API_KEY`   | Yes               |

## 📋 Obtaining API Keys

### TwelveLabs API Key

1. **Create Account**: Visit [TwelveLabs](https://twelvelabs.io/) and create an account
2. **Access Dashboard**: Log in to the TwelveLabs dashboard
3. **Navigate to API Keys**: Go to Settings → API Keys
4. **Generate Key**: Click "Create API Key"
5. **Copy Key**: Copy the generated API key (it will only be shown once)

**Note**: TwelveLabs offers a free tier with limited usage. For production testing, ensure you have sufficient API credits.

### Coactive AI API Key

1. **Create Account**: Visit [Coactive AI](https://coactive.ai/) and request access
2. **Access Dashboard**: Log in to the Coactive dashboard
3. **Navigate to API Keys**: Go to Settings → API Keys
4. **Generate Key**: Create a new API key
5. **Copy Key**: Copy the generated API key

**Note**: Coactive AI may require enterprise access. Contact their sales team for API access.

## 🔧 Local Configuration

### Option 1: Environment Variables (Recommended)

Set environment variables in your shell:

<!-- pragma: allowlist secret -->

```bash
# macOS/Linux - Add to ~/.bashrc, ~/.zshrc, or ~/.profile
export TWELVELABS_API_KEY="your-twelvelabs-api-key-here"
export COACTIVE_API_KEY="your-coactive-api-key-here"

# Reload shell configuration
source ~/.zshrc  # or ~/.bashrc
```

### Option 2: Inline with Test Command

Pass environment variables directly when running tests:

```bash
TWELVELABS_API_KEY="your-key" COACTIVE_API_KEY="your-key" npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

### Option 3: .env File

Create a `.env` file in `medialake_user_interface/`:

<!-- pragma: allowlist secret -->

```env
# Semantic Search Provider API Keys
TWELVELABS_API_KEY=your-twelvelabs-api-key-here
COACTIVE_API_KEY=your-coactive-api-key-here

# AWS Configuration (optional)
AWS_PROFILE=dev3
AWS_REGION=us-east-1
```

**Important**: Add `.env` to your `.gitignore` to prevent committing secrets:

```bash
echo ".env" >> .gitignore
```

Load the `.env` file before running tests:

```bash
# Using dotenv-cli
npx dotenv -e .env -- npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1

# Or source manually
set -a && source .env && set +a && npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

## 🔒 GitLab CI/CD Configuration

### Adding Masked Variables

1. **Navigate to Settings**: Go to your GitLab project → Settings → CI/CD
2. **Expand Variables**: Click "Expand" on the Variables section
3. **Add Variable**: Click "Add variable"
4. **Configure Variable**:
   - **Key**: `TWELVELABS_API_KEY` or `COACTIVE_API_KEY`
   - **Value**: Your API key
   - **Type**: Variable
   - **Flags**:
     - ✅ Protect variable (only available on protected branches)
     - ✅ Mask variable (hidden in job logs)
     - ❌ Expand variable reference (leave unchecked)
5. **Save**: Click "Add variable"

### Example CI/CD Job Configuration

```yaml
semantic-search-e2e-tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.40.0-focal
  variables:
    # These will be populated from GitLab CI/CD variables
    TWELVELABS_API_KEY: ${TWELVELABS_API_KEY}
    COACTIVE_API_KEY: ${COACTIVE_API_KEY}
  before_script:
    - cd medialake_user_interface
    - npm ci
    - npx playwright install --with-deps chromium
  script:
    - npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --reporter=junit,html
  artifacts:
    when: always
    paths:
      - medialake_user_interface/playwright-report/
      - medialake_user_interface/test-results/
    reports:
      junit: medialake_user_interface/test-results/junit.xml
    expire_in: 30 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Protected Variables

For production environments, use protected variables:

1. Mark the variable as "Protected"
2. Only protected branches (e.g., `main`, `stable`) can access these variables
3. This prevents API key exposure in feature branch pipelines

## 🛡️ Security Best Practices

### DO ✅

- **Use environment variables**: Never hardcode API keys in source code
- **Use masked variables in CI/CD**: Prevents keys from appearing in logs
- **Rotate keys regularly**: Change API keys periodically
- **Use separate keys for environments**: Different keys for dev, staging, production
- **Limit key permissions**: Use keys with minimal required permissions
- **Monitor key usage**: Track API usage for anomalies

### DON'T ❌

- **Commit API keys to Git**: Never include keys in version control
- **Share keys in plain text**: Don't send keys via email or chat
- **Log API keys**: Ensure keys aren't printed in test output
- **Use production keys for testing**: Use separate test/dev keys
- **Store keys in code comments**: Even commented keys are a risk

### Verifying Keys Are Not Exposed

The test suite is designed to prevent API key exposure:

```typescript
// Keys are read from environment variables
const apiKey = process.env.TWELVELABS_API_KEY;

// Keys are never logged
console.log(`API key configured: ${apiKey ? "Yes" : "No"}`); // ✅ Safe
console.log(`API key: ${apiKey}`); // ❌ Never do this
```

### Checking for Accidental Commits

Use git-secrets or similar tools to prevent accidental commits:

<!-- pragma: allowlist secret -->

```bash
# Install git-secrets
brew install git-secrets

# Configure patterns
git secrets --add 'TWELVELABS_API_KEY=.+'
git secrets --add 'COACTIVE_API_KEY=.+'

# Scan repository
git secrets --scan
```

## 🔍 Verifying API Key Configuration

### Check Environment Variables

```bash
# Verify keys are set (shows Yes/No, not the actual key)
echo "TWELVELABS_API_KEY: ${TWELVELABS_API_KEY:+Set}"
echo "COACTIVE_API_KEY: ${COACTIVE_API_KEY:+Set}"
```

### Test API Key Validity

```bash
# TwelveLabs API - Test with a simple API call
curl -s -o /dev/null -w "%{http_code}" \
  -H "x-api-key: ${TWELVELABS_API_KEY}" \
  "https://api.twelvelabs.io/v1.2/indexes"
# Expected: 200 (success) or 401 (invalid key)

# Coactive API - Test with a simple API call
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${COACTIVE_API_KEY}" \
  "https://api.coactive.ai/v1/health"
# Expected: 200 (success) or 401 (invalid key)
```

### Run Tests to Verify

```bash
# Run a quick test to verify API key configuration
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "TwelveLabs.*API" --workers=1 --reporter=list

# Check skip messages for missing keys
# If key is missing, you'll see: "Skipping TwelveLabs Marengo 2.7 API: API key not found..."
```

## 🚨 Troubleshooting

### "API key not found" Error

```
Skipping TwelveLabs Marengo 2.7 API + OpenSearch: API key not found in environment variable TWELVELABS_API_KEY
```

**Solution**: Set the environment variable:

```bash
export TWELVELABS_API_KEY="your-api-key"
```

### "Invalid API key" Error

```
Error: Provider configuration failed: Invalid API key
```

**Solutions**:

1. Verify the API key is correct (no extra spaces or characters)
2. Check if the API key has expired
3. Verify the key has the required permissions
4. Ensure you're using the correct key for the environment

### "Rate limit exceeded" Error

```
Error: API rate limit exceeded
```

**Solutions**:

1. Wait and retry (rate limits typically reset after a period)
2. Use a different API key with higher limits
3. Reduce test parallelism
4. Contact the provider for increased limits

### CI/CD Variable Not Available

```
Error: TWELVELABS_API_KEY is not defined
```

**Solutions**:

1. Verify the variable is added in GitLab CI/CD settings
2. Check if the variable is protected and the branch is protected
3. Ensure the variable name matches exactly (case-sensitive)
4. Check if the variable is masked and the value format is valid

## 📚 Additional Resources

- [TwelveLabs API Documentation](https://docs.twelvelabs.io/)
- [Coactive AI Documentation](https://docs.coactive.ai/)
- [GitLab CI/CD Variables](https://docs.gitlab.com/ee/ci/variables/)
- [Playwright Environment Variables](https://playwright.dev/docs/test-parameterize#env-files)

---

**Last Updated**: December 2025
**Version**: 1.0.0
