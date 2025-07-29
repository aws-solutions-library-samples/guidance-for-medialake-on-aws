# AWS Playwright Integration Testing Framework

## Overview

This comprehensive testing framework provides automated discovery and testing of AWS resources (Cognito User Pools and CloudFront distributions) using Playwright. The system creates temporary test users without password reset requirements and performs end-to-end login testing through CloudFront distributions.

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

### Basic Usage

```bash
# Run CloudFront login tests
npx playwright test tests/cloudfront/cloudfront-login.spec.ts --workers=1

# Run discovery validation tests
npx playwright test tests/cloudfront/tag-based-discovery.spec.ts

# Run integration tests
npx playwright test tests/integration/aws-tag-discovery-e2e.spec.ts
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

### Environment Variables

```bash
# Optional: Override default AWS profile
export AWS_PROFILE=your-profile-name

# Optional: Override default region
export AWS_DEFAULT_REGION=us-east-1
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
    await page.fill(
      '[data-testid="password"]',
      enhancedCognitoTestUser.password,
    );
    await page.click('[data-testid="login-button"]');

    // Verify successful login
    await expect(page).toHaveURL(/dashboard/);
  },
);
```

### Discovery Validation Test

```typescript
import { test, expect } from "@playwright/test";
import { awsDiscoveryFixtures } from "../fixtures/aws-discovery.fixtures";

const fixtures = test.extend(awsDiscoveryFixtures);

fixtures(
  "should discover AWS resources by tags",
  async ({ awsResourceDiscovery }) => {
    // Discover Cognito User Pools
    const userPools =
      await awsResourceDiscovery.discoverResources("cognito-user-pool");
    expect(userPools.length).toBeGreaterThan(0);
    expect(userPools[0]).toHaveProperty("userPoolId");
    expect(userPools[0]).toHaveProperty("userPoolName");

    // Discover CloudFront Distributions
    const distributions = await awsResourceDiscovery.discoverResources(
      "cloudfront-distribution",
    );
    expect(distributions.length).toBeGreaterThan(0);
    expect(distributions[0]).toHaveProperty("distributionId");
    expect(distributions[0]).toHaveProperty("domainName");
  },
);
```

## 🔍 Discovery Mechanisms

### Primary: Tag-based Discovery

Uses AWS Resource Groups Tagging API to find resources with specific tags:

```typescript
const userPools = await awsResourceDiscovery.discoverResources(
  "cognito-user-pool",
  {
    tags: [
      { key: "Application", values: ["medialake"], operator: "equals" },
      { key: "Environment", values: ["dev"], operator: "equals" },
    ],
  },
);
```

### Fallback: Service-specific Discovery

When tag-based discovery fails, falls back to service-specific methods:

```typescript
// Cognito fallback: Search by name pattern
const userPools = await cognitoAdapter.discoverByNamePattern("medialake");

// CloudFront fallback: List all distributions and filter
const distributions =
  await cloudFrontAdapter.discoverByDomainPattern("medialake");
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
# Verify AWS credentials
aws sts get-caller-identity

# Check AWS profile
echo $AWS_PROFILE

# Test Cognito access
aws cognito-idp list-user-pools --max-results 1
```

#### 2. Resource Discovery Failures

```typescript
// Check if resources have required tags
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Application,Values=medialake \
  --resource-type-filters cognito-idp:userpool
```

#### 3. Playwright Browser Issues

```bash
# Reinstall browsers
npx playwright install --force

# Run with headed mode for debugging
npx playwright test --headed --project=chromium
```

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

**Last Updated**: 2025-01-27
**Version**: 1.0.0
**Maintainer**: Roo Debug Mode
