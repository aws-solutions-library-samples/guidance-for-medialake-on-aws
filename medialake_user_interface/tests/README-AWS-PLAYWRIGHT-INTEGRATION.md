# AWS Playwright Integration Testing Framework

## Overview

This comprehensive testing framework provides automated discovery and testing of AWS resources (Cognito User Pools and CloudFront distributions) using Playwright. The system creates temporary test users without password reset requirements and performs end-to-end login testing through CloudFront distributions.

## 🚀 Quick Start Examples

```bash
# Use default AWS profile and region
npx playwright test tests/batch-delete.spec.ts --workers=1

# Target specific AWS profile (e.g., dev3)
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1

# Target specific environment and profile
AWS_PROFILE=staging MEDIALAKE_ENV=staging npx playwright test tests/cloudfront/ --workers=1

# Target specific region
AWS_PROFILE=prod AWS_REGION=us-west-2 npx playwright test tests/cloudfront/ --workers=1
```

**⚠️ IMPORTANT**: Always set `AWS_PROFILE` inline with the test command to ensure Cognito and CloudFront discovery use the same AWS account.

## 🎯 Key Features

- **Tag-based AWS Resource Discovery**: Automatically discovers Cognito User Pools and CloudFront distributions using AWS tags
- **No-Password-Reset User Creation**: Creates test users with permanent passwords using `admin-set-user-password --permanent`
- **Fallback Discovery Mechanisms**: Multiple discovery strategies ensure robust resource detection
- **Worker-scoped Caching**: 5-minute TTL caching for parallel test execution
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Clean Resource Management**: Automatic cleanup of test users after test completion

## 📁 Project Structure

```
medialake_user_interface/tests/
├── utils/                          # Core utilities
│   ├── aws-resource-finder.ts      # Resource discovery engine with caching
│   ├── cognito-service-adapter.ts  # Cognito pool discovery and user management
│   ├── cloudfront-service-adapter.ts # CloudFront distribution discovery
│   └── tag-matcher.ts             # Tag filtering and matching logic
├── fixtures/                       # Enhanced Playwright fixtures
│   ├── enhanced-cognito.fixtures.ts # Main fixture with discovery and user creation
│   ├── aws-discovery.fixtures.ts   # Core AWS resource discovery
│   ├── cloudfront.fixtures.ts      # CloudFront testing utilities
│   └── README-enhanced.md          # Fixture documentation
├── cloudfront/                     # CloudFront-specific tests
│   ├── cloudfront-login.spec.ts    # End-to-end login testing
│   └── tag-based-discovery.spec.ts # Discovery validation tests
├── integration/                    # Integration tests
│   └── aws-tag-discovery-e2e.spec.ts # End-to-end discovery tests
└── README-AWS-PLAYWRIGHT-INTEGRATION.md # This documentation
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI Configuration**: Ensure AWS CLI is configured with appropriate credentials
2. **Playwright Installation**: Install Playwright browsers
3. **AWS Permissions**: Required permissions for Cognito and CloudFront operations

```bash
# Install Playwright browsers
npx playwright install

# Verify AWS CLI configuration
aws sts get-caller-identity

# Test AWS permissions
aws cognito-idp list-user-pools --max-results 10
aws cloudfront list-distributions
```

### Running Tests

```bash
# Run batch delete tests (default profile)
npx playwright test tests/batch-delete.spec.ts --workers=1

# Run batch delete tests (specific profile)
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1

# Run CloudFront login tests
npx playwright test tests/cloudfront/cloudfront-login.spec.ts --workers=1

# Run discovery validation tests
npx playwright test tests/cloudfront/tag-based-discovery.spec.ts

# Run integration tests
npx playwright test tests/integration/aws-tag-discovery-e2e.spec.ts

# Run connector management tests
AWS_PROFILE=dev3 npx playwright test tests/connectors/connectorMangagement.spec.ts --workers=1

# Run batch delete tests with file upload directory
UPLOAD_FILES_DIR=/path/to/test/files AWS_PROFILE=dev3 MEDIALAKE_ENV=dev npx playwright test tests/batch-delete.spec.ts --workers=1 --headed --project=chromium -x
```

### Browser-Specific Testing

```bash
# Run on Chromium (default)
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 --project=chromium

# Run on Firefox
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 --project=firefox

# Run on WebKit (Safari)
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 --project=webkit

# Run on all browsers
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1
```

### Consistency Testing (Multiple Runs)

```bash
# Run test 5 times to check consistency
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 --project=chromium --repeat-each=5

# Loop until failure (for flakiness testing)
run=1
while true; do
  echo "Test Run #$run - $(date)"
  AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 -x || break
  ((run++))
  sleep 10
done
```

## 🔧 Configuration

### AWS Resource Tags

The system discovers resources using these default tags:

```typescript
const DEFAULT_TAGS = [
  { key: "Application", values: ["medialake"], operator: "equals" },
  { key: "Environment", values: ["dev"], operator: "equals" },
  { key: "Testing", values: ["enabled"], operator: "equals" },
];
```

### Environment Variables Configuration

**🔑 CRITICAL**: When running tests against specific AWS environments, you **MUST** set environment variables **inline with the test command** to ensure both Cognito and CloudFront discovery use the same AWS account and profile.

#### Available Environment Variables

| Variable        | Description               | Default     | Example                   |
| --------------- | ------------------------- | ----------- | ------------------------- |
| `AWS_PROFILE`   | AWS CLI profile name      | `default`   | `dev3`, `staging`, `prod` |
| `AWS_REGION`    | AWS region for resources  | `us-east-1` | `us-west-2`, `eu-west-1`  |
| `MEDIALAKE_ENV` | Environment tag filter    | `dev`       | `dev`, `staging`, `prod`  |
| `DEPLOY_REGION` | Alternative to AWS_REGION | `us-east-1` | Same as AWS_REGION        |

#### Command-Line Usage Patterns

**Single Profile/Region**:

```bash
# Target dev3 profile in default region
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1

# Target dev2 profile with staging environment
AWS_PROFILE=dev2 MEDIALAKE_ENV=staging npx playwright test tests/cloudfront/ --workers=1

# Target production with specific region
AWS_PROFILE=prod MEDIALAKE_ENV=prod AWS_REGION=us-west-2 npx playwright test tests/cloudfront/ --workers=1
```

**Default Configuration** (uses "default" profile):

```bash
# Uses AWS_PROFILE=default, AWS_REGION=us-east-1, MEDIALAKE_ENV=dev
npx playwright test tests/cloudfront/cloudfront-login.spec.ts --workers=1
```

#### Why Inline Environment Variables?

Setting environment variables **inline** (before the command) ensures:

1. ✅ **Profile Consistency**: Both Cognito user creation and CloudFront discovery use the same AWS account
2. ✅ **Resource Discovery**: All resource discovery (user pools, distributions, S3 buckets) happens in the correct account
3. ✅ **Test Isolation**: Each test run can target different environments without cross-contamination
4. ✅ **Clear Intent**: It's obvious which profile is being used for each test run

#### ❌ Common Mistakes

**DON'T export variables** unless you want them to persist:

```bash
# ❌ BAD: Variables persist, may cause profile mismatches
export AWS_PROFILE=dev3
npx playwright test tests/batch-delete.spec.ts       # Uses dev3 ✓
npx playwright test tests/connectors/                 # Still uses dev3 (unexpected!)
AWS_PROFILE=default npx playwright test tests/upload/ # Tries to override but may fail

# ✅ GOOD: Use inline variables for each test run
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts
AWS_PROFILE=dev2 npx playwright test tests/connectors/
AWS_PROFILE=default npx playwright test tests/upload/
```

**DON'T mix profile configurations** in test files:

```typescript
// ❌ BAD: Hardcoded profile in test file
const AWS_PROFILE = "dev2"; // This overrides command-line setting!

// ✅ GOOD: Read from environment
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
```

#### Test-Specific Configuration

**Batch Delete Tests** ([`batch-delete.spec.ts`](medialake_user_interface/tests/batch-delete.spec.ts)):

```bash
# Uses profile for: Cognito user creation, CloudFront discovery, S3 bucket discovery, connector creation
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1
```

**Connector Management Tests** ([`connectorMangagement.spec.ts`](medialake_user_interface/tests/connectors/connectorMangagement.spec.ts)):

```bash
# Uses profile for: Cognito auth, S3 bucket access, connector CRUD operations
AWS_PROFILE=dev3 npx playwright test tests/connectors/ --workers=1
```

**CloudFront Login Tests** ([`cloudfront-login.spec.ts`](medialake_user_interface/tests/cloudfront/cloudfront-login.spec.ts)):

```bash
# Uses profile for: Cognito user creation, CloudFront distribution discovery, login flow
AWS_PROFILE=staging npx playwright test tests/cloudfront/cloudfront-login.spec.ts --workers=1
```

#### Troubleshooting Profile Issues

**Symptom**: Login fails after changing AWS_PROFILE

```bash
# Check which profile is actually being used
echo $AWS_PROFILE  # If this returns a value, it may override inline variables

# Clear exported variables
unset AWS_PROFILE
unset AWS_REGION
unset MEDIALAKE_ENV

# Run test with explicit profile
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1
```

**Symptom**: Resources not found (user pools, distributions, buckets)

```bash
# Verify profile has access to resources
AWS_PROFILE=dev3 aws sts get-caller-identity
AWS_PROFILE=dev3 aws cognito-idp list-user-pools --max-results 1
AWS_PROFILE=dev3 aws cloudfront list-distributions | head -20
AWS_PROFILE=dev3 aws s3 ls

# Run test with verbose logging
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1 --reporter=list
```

**Symptom**: Connector creation fails with "bucket not found"

```bash
# Ensure profile matches where buckets are created
AWS_PROFILE=dev3 aws s3 ls | grep medialake

# Run prerequisites test to auto-create connector
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --grep "Prerequisites" --workers=1
```

## 📋 Test Examples

### CloudFront Login Test

```typescript
import { test, expect } from "@playwright/test";
import { enhancedCognitoFixtures } from "../fixtures/enhanced-cognito.fixtures";
import { cloudFrontFixtures } from "../fixtures/cloudfront.fixtures";

const fixtures = test.extend({
  ...enhancedCognitoFixtures,
  ...cloudFrontFixtures,
});

fixtures(
  "should perform end-to-end login through CloudFront",
  async ({ enhancedCognitoTestUser, cloudFrontLoginContext, page }) => {
    // Test user is automatically created with permanent password
    expect(enhancedCognitoTestUser.email).toMatch(/^mne-medialake\+e2etest-/);
    expect(enhancedCognitoTestUser.password).toBeDefined();

    // CloudFront distribution is automatically discovered
    expect(cloudFrontLoginContext.loginUrl).toContain("https://");
    expect(cloudFrontLoginContext.distributionId).toMatch(/^E[A-Z0-9]+$/);

    // Perform login test
    await page.goto(cloudFrontLoginContext.loginUrl);
    await page.fill('[data-testid="email"]', enhancedCognitoTestUser.email);
    await page.fill('[data-testid="password"]', enhancedCognitoTestUser.password);
    await page.click('[data-testid="login-button"]');

    // Verify successful login
    await expect(page).toHaveURL(/dashboard/);
  }
);
```

### Discovery Validation Test

```typescript
import { test, expect } from "@playwright/test";
import { awsDiscoveryFixtures } from "../fixtures/aws-discovery.fixtures";

const fixtures = test.extend(awsDiscoveryFixtures);

fixtures("should discover AWS resources by tags", async ({ awsResourceDiscovery }) => {
  // Discover Cognito User Pools
  const userPools = await awsResourceDiscovery.discoverResources("cognito-user-pool");
  expect(userPools.length).toBeGreaterThan(0);
  expect(userPools[0]).toHaveProperty("userPoolId");
  expect(userPools[0]).toHaveProperty("userPoolName");

  // Discover CloudFront Distributions
  const distributions = await awsResourceDiscovery.discoverResources("cloudfront-distribution");
  expect(distributions.length).toBeGreaterThan(0);
  expect(distributions[0]).toHaveProperty("distributionId");
  expect(distributions[0]).toHaveProperty("domainName");
});
```

## 🔍 Discovery Mechanisms

### Primary: Tag-based Discovery

Uses AWS Resource Groups Tagging API to find resources with specific tags:

```typescript
const userPools = await awsResourceDiscovery.discoverResources("cognito-user-pool", {
  tags: [
    { key: "Application", values: ["medialake"], operator: "equals" },
    { key: "Environment", values: ["dev"], operator: "equals" },
  ],
});
```

### Fallback: Service-specific Discovery

When tag-based discovery fails, falls back to service-specific methods:

```typescript
// Cognito fallback: Search by name pattern
const userPools = await cognitoAdapter.discoverByNamePattern("medialake");

// CloudFront fallback: List all distributions and filter
const distributions = await cloudFrontAdapter.discoverByDomainPattern("medialake");
```

## 👤 User Management

### Test User Creation

```typescript
// Automatic user creation with permanent password
const testUser = await enhancedCognitoTestUser;

// User properties
console.log(testUser.email); // mne-medialake+e2etest-0-abc123@amazon.com
console.log(testUser.password); // Auto-generated secure password
console.log(testUser.userPoolId); // us-east-1_ABC123DEF
console.log(testUser.discoveryMethod); // 'tag-based' or 'fallback'
```

### Password Policy Compliance

The system automatically retrieves and complies with Cognito password policies:

```typescript
// Example password policy
{
  "MinimumLength": 8,
  "RequireUppercase": true,
  "RequireLowercase": true,
  "RequireNumbers": true,
  "RequireSymbols": true,
  "TemporaryPasswordValidityDays": 7
}
```

### Automatic Cleanup

Test users are automatically deleted after test completion:

```typescript
// Cleanup happens in fixture teardown
await cognitoAdapter.deleteUser(testUser.email, testUser.userPoolId);
```

## 📊 Logging and Debugging

### Log Levels

The framework provides comprehensive logging:

```typescript
// Resource discovery logs
[ResourceDiscovery Worker 0] Cache miss for cognito-user-pool, discovering resources...
[CognitoAdapter] Found user pool: CognitoMediaLakeUserPool42611D98-Tv2VAUTYz4Xa (us-east-1_6SLd0XyR3)

// User management logs
[EnhancedCognito] Creating test user with permanent password: mne-medialake+e2etest-0-787d277d@amazon.com
[EnhancedCognito] User created: mne-medialake+e2etest-0-787d277d@amazon.com

// CloudFront logs
[CloudFrontLogin] Found distribution via tags: medialake-dev-distribution (E1234567890ABC)
[CloudFrontLogin] Login URL: https://cdn.medialake.example.com/sign-in
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Run with debug output
DEBUG=aws-playwright:* npx playwright test tests/cloudfront/cloudfront-login.spec.ts
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. AWS Authentication Errors

```bash
# Verify AWS credentials for specific profile
AWS_PROFILE=dev3 aws sts get-caller-identity

# Check if profile is exported (should be empty for inline usage)
echo $AWS_PROFILE

# Test Cognito access with specific profile
AWS_PROFILE=dev3 aws cognito-idp list-user-pools --max-results 1

# Test CloudFront access
AWS_PROFILE=dev3 aws cloudfront list-distributions
```

#### 2. Resource Discovery Failures

```bash
# Check if resources have required tags (use correct profile)
AWS_PROFILE=dev3 aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Application,Values=medialake \
  --resource-type-filters cognito-idp:userpool

# Check CloudFront distributions
AWS_PROFILE=dev3 aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Application,Values=medialake \
  --resource-type-filters cloudfront:distribution

# List all S3 buckets
AWS_PROFILE=dev3 aws s3 ls | grep medialake
```

````

#### 3. Playwright Browser Issues

```bash
# Reinstall browsers
npx playwright install --force

# Run with headed mode for debugging
npx playwright test --headed --project=chromium
````

#### 4. User Creation Failures

```bash
# Check Cognito permissions
aws cognito-idp describe-user-pool --user-pool-id us-east-1_EXAMPLE

# Verify password policy
aws cognito-idp describe-user-pool-policy --user-pool-id us-east-1_EXAMPLE
```

## 🔒 Security Considerations

### Test User Security

- Test users use unique email addresses with timestamp suffixes
- Passwords are auto-generated and meet policy requirements
- Users are automatically deleted after test completion
- No persistent test data is stored

### AWS Permissions

Required IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:ListUserPools",
        "cognito-idp:DescribeUserPool",
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminSetUserPassword",
        "cognito-idp:AdminDeleteUser",
        "cloudfront:ListDistributions",
        "resourcegroupstaggingapi:GetResources"
      ],
      "Resource": "*"
    }
  ]
}
```

## 📈 Performance Optimization

### Caching Strategy

- **Worker-scoped caching**: Resources cached per worker for 5 minutes
- **Prefetch common resources**: Cognito pools prefetched during fixture setup
- **Efficient cleanup**: Batch operations where possible

### Parallel Execution

```bash
# Run tests in parallel (recommended: 1-3 workers for AWS rate limits)
npx playwright test --workers=2

# Single worker for debugging
npx playwright test --workers=1
```

## 🔄 Continuous Integration

### GitLab CI Integration

```yaml
test-aws-integration:
  stage: test
  image: mcr.microsoft.com/playwright:v1.40.0-focal
  before_script:
    - npm ci
    - npx playwright install
  script:
    - npx playwright test tests/cloudfront/ --workers=1
    - npx playwright test tests/integration/ --workers=1
  artifacts:
    when: always
    paths:
      - test-results/
      - playwright-report/
    expire_in: 30 days
  only:
    - merge_requests
    - main
```

## 📚 API Reference

### Core Classes

#### `AWSResourceFinder`

- `discoverResources(type, options)`: Discover resources by type and filters
- `clearCache()`: Clear discovery cache
- `registerAdapter(type, adapter)`: Register service adapter

#### `CognitoServiceAdapter`

- `discoverUserPools(filters)`: Discover user pools by tags
- `createUser(email, userPoolId)`: Create test user with permanent password
- `deleteUser(email, userPoolId)`: Delete test user

#### `CloudFrontServiceAdapter`

- `discoverDistributions(filters)`: Discover distributions by tags
- `getDistributionDomainName(distributionId)`: Get distribution domain

### Fixture Types

#### `EnhancedCognitoTestUser`

```typescript
interface EnhancedCognitoTestUser {
  email: string;
  password: string;
  userPoolId: string;
  discoveryMethod: "tag-based" | "fallback";
}
```

#### `CloudFrontLoginContext`

```typescript
interface CloudFrontLoginContext {
  distributionId: string;
  domainName: string;
  loginUrl: string;
  discoveryMethod: "tag-based" | "fallback";
}
```

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd medialake_user_interface

# Install dependencies
npm install

# Install Playwright
npx playwright install

# Run tests
npm test
```

### Code Style

- Use TypeScript for all new code
- Follow existing logging patterns
- Include comprehensive error handling
- Add JSDoc comments for public APIs

### Testing Guidelines

- Test both success and failure scenarios
- Include cleanup in all fixtures
- Use descriptive test names
- Mock external dependencies where appropriate

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 📝 Quick Reference Card

### Essential Commands

```bash
# Default profile (uses "default" AWS profile)
npx playwright test tests/batch-delete.spec.ts --workers=1

# Specific profile
AWS_PROFILE=dev3 npx playwright test tests/batch-delete.spec.ts --workers=1

# Multiple environment variables
AWS_PROFILE=dev3 AWS_REGION=us-west-2 MEDIALAKE_ENV=dev npx playwright test tests/batch-delete.spec.ts --workers=1

# Check current AWS identity
AWS_PROFILE=dev3 aws sts get-caller-identity

# List available AWS profiles
cat ~/.aws/credentials | grep '\[' | tr -d '[]'
```

### Test Files and Their AWS Usage

| Test File                      | AWS Resources Used                  | Required Profile Access  |
| ------------------------------ | ----------------------------------- | ------------------------ |
| `batch-delete.spec.ts`         | Cognito, CloudFront, S3, Connectors | Full MediaLake access    |
| `cloudfront-login.spec.ts`     | Cognito, CloudFront                 | User pool + distribution |
| `connectorMangagement.spec.ts` | Cognito, S3, Connectors             | S3 + connector APIs      |
| `tag-based-discovery.spec.ts`  | All AWS resources                   | Read-only discovery      |

### Environment Variable Priority

1. **Inline variables** (highest priority): `AWS_PROFILE=dev3 npx playwright test`
2. **Exported variables**: `export AWS_PROFILE=dev3`
3. **Default values** (lowest priority): `"default"` profile, `"us-east-1"` region, `"dev"` environment

---

**Last Updated**: 2025-11-20
**Version**: 2.0.0
**Maintainer**: MediaLake Team
