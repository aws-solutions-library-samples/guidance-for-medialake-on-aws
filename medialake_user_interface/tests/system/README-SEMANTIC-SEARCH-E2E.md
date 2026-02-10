# Semantic Search End-to-End Testing Guide

## Overview

This guide covers the comprehensive end-to-end Playwright tests for all semantic search provider and embedding store combinations in MediaLake. The test suite validates the complete workflow from provider configuration through semantic search execution and clip visualization for 7 distinct configurations.

## 🎯 Test Coverage

The test suite covers all combinations of:

| Provider                       | Embedding Store | API Key Required | Dimensions |
| ------------------------------ | --------------- | ---------------- | ---------- |
| TwelveLabs Marengo 2.7 API     | OpenSearch      | Yes              | 1024       |
| TwelveLabs Marengo 2.7 API     | S3 Vectors      | Yes              | 1024       |
| TwelveLabs Marengo 2.7 Bedrock | OpenSearch      | No               | 1024       |
| TwelveLabs Marengo 2.7 Bedrock | S3 Vectors      | No               | 1024       |
| TwelveLabs Marengo 3.0 Bedrock | OpenSearch      | No               | 512        |
| TwelveLabs Marengo 3.0 Bedrock | S3 Vectors      | No               | 512        |
| Coactive AI                    | Native Storage  | Yes              | 1024       |

## 🚀 Quick Start

### Prerequisites

1. **Node.js**: Version 18+ required
2. **Playwright**: Install browsers with `npx playwright install`
3. **AWS CLI**: Configured with appropriate credentials
4. **API Keys**: For TwelveLabs API and Coactive providers (see [API Key Setup](#api-key-setup))

### Running All Tests

```bash
# Navigate to the user interface directory
cd medialake_user_interface

# Run all semantic search E2E tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1

# Run with specific AWS profile
AWS_PROFILE=dev3 npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

### Running Tests for Specific Providers

```bash
# Run only TwelveLabs API tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "TwelveLabs Marengo 2.7 API" --workers=1

# Run only Bedrock provider tests (no API key required)
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "Bedrock" --workers=1

# Run only TwelveLabs 3.0 tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "3.0" --workers=1

# Run only Coactive tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "Coactive" --workers=1

# Run only OpenSearch embedding store tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "OpenSearch" --workers=1

# Run only S3 Vector embedding store tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "S3 Vectors" --workers=1
```

### Running Property Tests

```bash
# Run all property-based tests
npx playwright test tests/system/semantic-provider-properties.spec.ts --workers=1

# Run specific property tests
npx playwright test tests/system/semantic-provider-properties.spec.ts --grep "Property 1" --workers=1
```

## 📋 Environment Variables

### Required for API-based Providers

<!-- pragma: allowlist secret -->

| Variable             | Description                        | Required For            |
| -------------------- | ---------------------------------- | ----------------------- |
| `TWELVELABS_API_KEY` | TwelveLabs API authentication key  | TwelveLabs API provider |
| `COACTIVE_API_KEY`   | Coactive AI API authentication key | Coactive provider       |

### AWS Configuration

| Variable        | Description              | Default     |
| --------------- | ------------------------ | ----------- |
| `AWS_PROFILE`   | AWS CLI profile name     | `default`   |
| `AWS_REGION`    | AWS region for resources | `us-east-1` |
| `MEDIALAKE_ENV` | Environment tag filter   | `dev`       |

### Test Configuration

| Variable         | Description                 | Default                 |
| ---------------- | --------------------------- | ----------------------- |
| `BASE_URL`       | Application base URL        | `http://localhost:5173` |
| `CLOUDFRONT_URL` | CloudFront distribution URL | Auto-discovered         |

## 🔧 Setting Environment Variables

### Local Development (macOS/Linux)

```bash
# Set API keys for current session
export TWELVELABS_API_KEY="your-twelvelabs-api-key"
export COACTIVE_API_KEY="your-coactive-api-key"

# Or inline with test command (recommended)
TWELVELABS_API_KEY="your-key" npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "TwelveLabs.*API" --workers=1
```

### Using .env File

Create a `.env` file in `medialake_user_interface/`:

```env
TWELVELABS_API_KEY=your-twelvelabs-api-key
COACTIVE_API_KEY=your-coactive-api-key
AWS_PROFILE=dev3
AWS_REGION=us-east-1
```

Then load it before running tests:

```bash
source .env && npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1
```

## 📁 Test Structure

```
tests/
├── system/
│   ├── semantic-search-e2e.spec.ts          # Main E2E test file
│   ├── semantic-provider-properties.spec.ts  # Property-based tests
│   └── README-SEMANTIC-SEARCH-E2E.md        # This documentation
├── fixtures/
│   ├── semantic-provider.fixtures.ts         # Provider configuration fixtures
│   └── test-data.fixtures.ts                 # Test media assets fixtures
└── utils/
    ├── provider-config-helper.ts             # Provider configuration utilities
    ├── pipeline-deployment-helper.ts         # Pipeline deployment utilities
    ├── connector-helper.ts                   # Connector management utilities
    ├── search-helper.ts                      # Search execution utilities
    ├── clip-validation-helper.ts             # Clip verification utilities
    └── test-config-models.ts                 # TypeScript interfaces
```

## 🔄 10-Step Workflow

Each E2E test executes the following workflow:

1. **Setup Provider** - Configure the semantic search provider
2. **Deploy Pipelines** - Deploy processing pipelines for the provider
3. **Setup Connector** - Create and configure a data connector
4. **Ingest Content** - Process test media assets
5. **Search Semantically** - Execute semantic search queries
6. **Verify Results & Clips** - Validate search results and clip visibility
7. **Adjust Confidence** - Test threshold filtering
8. **Open Asset Details** - Navigate to asset detail view
9. **Expand Sidebar** - Validate clip list in sidebar
10. **Player Threshold** - Test confidence adjustment in video player

## 🧪 Test Commands Reference

### Basic Commands

```bash
# Run all tests
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1

# Run with headed browser (visible)
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --headed

# Run with specific browser
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --project=chromium
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --project=firefox
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --project=webkit

# Run with debug mode
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --debug

# Run with trace recording
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --trace on
```

### Filtering Tests

```bash
# Run tests matching pattern
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep "pattern" --workers=1

# Exclude tests matching pattern
npx playwright test tests/system/semantic-search-e2e.spec.ts --grep-invert "pattern" --workers=1

# Run only failed tests from last run
npx playwright test tests/system/semantic-search-e2e.spec.ts --last-failed --workers=1
```

### Reporting

```bash
# Generate HTML report
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --reporter=html

# Generate JUnit XML report (for CI/CD)
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --reporter=junit

# Multiple reporters
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --reporter=html,junit

# View HTML report
npx playwright show-report
```

### Debugging

```bash
# Run with Playwright Inspector
PWDEBUG=1 npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1

# Run with console output
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --reporter=list

# Capture screenshots on failure
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --screenshot=only-on-failure

# Capture video on failure
npx playwright test tests/system/semantic-search-e2e.spec.ts --workers=1 --video=retain-on-failure
```

## ⚠️ Important Notes

### Sequential Execution

Tests run sequentially (`--workers=1`) because:

- Provider configuration is global state
- Only one provider can be active at a time
- Pipeline deployment affects shared resources

### Test Skipping

Tests are automatically skipped when:

- Required API key is not set (with clear skip message)
- Provider is not available in the environment
- Prerequisites are not met

### Timeouts

Default timeouts configured:

- Provider configuration: 30 seconds
- Pipeline deployment: 5 minutes
- Asset ingestion: 10 minutes
- Search execution: 30 seconds
- UI interactions: 10 seconds

## 📊 Test Reports

After running tests, reports are available at:

- **HTML Report**: `medialake_user_interface/playwright-report/index.html`
- **Test Results**: `medialake_user_interface/test-results/`
- **Screenshots**: `medialake_user_interface/test-results/*/screenshots/`
- **Videos**: `medialake_user_interface/test-results/*/videos/`

## 🔗 Related Documentation

- [API Key Setup Guide](./API-KEY-SETUP.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [AWS Playwright Integration](../README-AWS-PLAYWRIGHT-INTEGRATION.md)
- [Fixtures Documentation](../fixtures/README.md)

---

**Last Updated**: December 2025
**Version**: 1.0.0
