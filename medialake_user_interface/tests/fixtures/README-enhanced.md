# Enhanced Playwright Fixtures for MediaLake AWS Integration Testing

This document provides comprehensive documentation for the enhanced Playwright fixtures that support AWS tag-based resource discovery and automated CloudFront login testing, while maintaining full backward compatibility with existing fixture patterns.

## Overview

The enhanced fixture system extends the original MediaLake Playwright fixtures with powerful AWS resource discovery capabilities, enabling tests to automatically discover and use AWS resources based on tags. This eliminates the need for hardcoded resource identifiers and provides a more flexible, environment-agnostic testing approach.

## Architecture

### Core Components

1. **AWS Resource Discovery Engine** ([`aws-resource-finder.ts`](../utils/aws-resource-finder.ts))
   - Unified resource discovery with caching and fallback mechanisms
   - Support for multiple AWS services (Cognito, CloudFront, S3, etc.)
   - Worker-isolated caching for parallel test execution

2. **Service Adapters**
   - [`cognito-service-adapter.ts`](../utils/cognito-service-adapter.ts): Cognito user pool discovery and management
   - [`cloudfront-service-adapter.ts`](../utils/cloudfront-service-adapter.ts): CloudFront distribution discovery and testing
   - [`tag-matcher.ts`](../utils/tag-matcher.ts): Standardized tag filtering and matching

3. **Enhanced Fixtures**
   - [`aws-discovery.fixtures.ts`](aws-discovery.fixtures.ts): Unified AWS resource discovery
   - [`enhanced-cognito.fixtures.ts`](enhanced-cognito.fixtures.ts): Tag-based Cognito with permanent passwords
   - [`cloudfront.fixtures.ts`](cloudfront.fixtures.ts): CloudFront distribution testing

## Enhanced Fixtures

### AWS Discovery Fixtures (`aws-discovery.fixtures.ts`)

Provides unified AWS resource discovery capabilities with comprehensive caching and error handling.

#### Key Features

- **Tag-based Resource Discovery**: Automatically discover AWS resources using standardized tags
- **Multi-service Support**: Unified interface for Cognito, CloudFront, and other AWS services
- **Worker Isolation**: Separate cache instances for parallel test execution
- **Fallback Mechanisms**: Multiple discovery strategies with graceful degradation
- **Performance Optimization**: Intelligent caching with configurable TTL

#### Usage

```typescript
import {
  test,
  expect,
  AWSDiscoveryUtils,
} from "../fixtures/aws-discovery.fixtures";

test("should discover AWS resources by tags", async ({
  awsResourceContext,
  discoveryEngine,
}) => {
  // Access discovered resources
  expect(awsResourceContext.cognitoUserPool).toBeTruthy();
  expect(awsResourceContext.cloudFrontDistribution).toBeTruthy();

  // Get discovery statistics
  const stats = await AWSDiscoveryUtils.getDiscoveryStats(discoveryEngine);
  console.log("Discovery performance:", stats);
});
```

#### Available Fixtures

- `awsResourceContext`: Complete AWS resource context with discovered resources
- `cognitoDiscovery`: Cognito service adapter for user pool operations
- `cloudFrontDiscovery`: CloudFront service adapter for distribution operations
- `discoveryEngine`: Core resource discovery engine

### Enhanced Cognito Fixtures (`enhanced-cognito.fixtures.ts`)

Extends the original Cognito fixtures with tag-based discovery and permanent password creation.

#### Key Enhancements

- **Tag-based Pool Discovery**: Automatically find Cognito user pools using tags
- **Permanent Password Creation**: Users created with permanent passwords (no reset required)
- **Multiple Discovery Methods**: Tag-based, name-based, and fallback discovery
- **Enhanced Error Handling**: Comprehensive error recovery and retry mechanisms
- **Backward Compatibility**: Maintains compatibility with existing [`auth.fixtures.ts`](auth.fixtures.ts)

#### Usage

```typescript
import {
  test,
  expect,
  EnhancedCognitoUtils,
} from "../fixtures/enhanced-cognito.fixtures";

test("should create user with permanent password", async ({
  enhancedCognitoTestUser,
}) => {
  // User is ready to use immediately (no password reset required)
  expect(enhancedCognitoTestUser.username).toBeTruthy();
  expect(enhancedCognitoTestUser.password).toBeTruthy();
  expect(enhancedCognitoTestUser.discoveryMethod).toMatch(
    /^(tag-based|name-based|fallback)$/,
  );

  // Validate discovery method
  const isTagBased = EnhancedCognitoUtils.validateDiscoveryMethod(
    enhancedCognitoTestUser,
    "tag-based",
  );

  console.log(
    `User discovered via: ${enhancedCognitoTestUser.discoveryMethod}`,
  );
});
```

#### Available Fixtures

- `enhancedCognitoTestUser`: Test user with permanent password and discovery metadata
- `cognitoDiscoveryEngine`: Discovery engine configured for Cognito resources
- `cognitoServiceAdapter`: Service adapter for Cognito operations

### CloudFront Fixtures (`cloudfront.fixtures.ts`)

Provides comprehensive CloudFront distribution discovery and testing capabilities.

#### Key Features

- **Distribution Discovery**: Automatic CloudFront distribution discovery by tags
- **Performance Testing**: Built-in response time and cache validation
- **URL Generation**: Automatic test URL generation from distribution configuration
- **Cache Management**: Invalidation creation and monitoring
- **Health Checking**: Distribution readiness validation

#### Usage

```typescript
import {
  test,
  expect,
  CloudFrontTestUtils,
} from "../fixtures/cloudfront.fixtures";

test("should test CloudFront distribution", async ({
  cloudFrontContext,
  cloudFrontTestPage,
}) => {
  // Test distribution accessibility
  const testResults = await CloudFrontTestUtils.testDistributionAccess(
    cloudFrontTestPage,
    cloudFrontContext.testUrls,
  );

  expect(testResults.length).toBeGreaterThan(0);

  // Validate cache headers
  const response = await cloudFrontTestPage.goto(
    cloudFrontContext.testUrls.root,
  );
  const headers = await response.allHeaders();
  const cacheValidation = CloudFrontTestUtils.validateCacheHeaders(headers);

  expect(cacheValidation.hasCacheHeaders).toBe(true);
});
```

#### Available Fixtures

- `cloudFrontContext`: Complete CloudFront context with distribution and test URLs
- `cloudFrontDiscoveryEngine`: Discovery engine for CloudFront resources
- `cloudFrontServiceAdapter`: Service adapter for CloudFront operations
- `cloudFrontTestPage`: Pre-configured page for CloudFront testing

## Integration Testing

### End-to-End Integration Tests (`integration/aws-tag-discovery-e2e.spec.ts`)

Comprehensive integration tests that validate the complete workflow from tag-based resource discovery through automated login.

#### Test Coverage

1. **Complete Workflow Validation**
   - Tag-based resource discovery
   - User creation with permanent passwords
   - CloudFront navigation and login automation
   - End-to-end authentication flow

2. **Performance and Caching**
   - Discovery performance benchmarks
   - Cache behavior validation
   - Concurrent execution testing

3. **Backward Compatibility**
   - Compatibility with existing [`auth.fixtures.ts`](auth.fixtures.ts)
   - S3 bucket naming pattern compatibility
   - Worker isolation validation

4. **Error Handling and Resilience**
   - Discovery failure recovery
   - Fallback mechanism validation
   - Edge case handling

#### Usage

```typescript
import { test, expect } from "../integration/aws-tag-discovery-e2e.spec";

test("should perform complete E2E workflow", async ({
  e2eIntegrationContext,
  authenticatedE2EPage,
}) => {
  // Validate complete setup
  expect(e2eIntegrationContext.cognitoUserPool).toBeTruthy();
  expect(e2eIntegrationContext.cloudFrontDistribution).toBeTruthy();
  expect(e2eIntegrationContext.validationResults.backwardCompatible).toBe(true);

  // Test authenticated access
  await authenticatedE2EPage.goto(
    e2eIntegrationContext.testUrls.cloudFrontDashboard,
  );
  expect(authenticatedE2EPage.url()).not.toContain("/sign-in");
});
```

## Configuration

### Environment Variables

```bash
# AWS Configuration
AWS_REGION=us-east-1                    # AWS region for resource discovery
AWS_PROFILE=medialake-dev4              # AWS CLI profile to use
MEDIALAKE_ENV=dev                       # Environment for tag filtering

# Discovery Configuration
DISCOVERY_CACHE_TTL=300000              # Cache TTL in milliseconds (5 minutes)
DISCOVERY_MAX_CACHE_SIZE=100            # Maximum cache entries per worker
DISCOVERY_ENABLE_FALLBACK=true          # Enable fallback discovery methods
```

### Standard Tags

The enhanced fixtures use standardized tags for resource discovery:

```typescript
// Standard tag patterns used across all fixtures
const STANDARD_TAG_PATTERNS = {
  APPLICATION_TAG: {
    key: "Application",
    values: ["medialake"],
    operator: "equals",
  },
  TESTING_TAG: {
    key: "Testing",
    values: ["enabled", "true"],
    operator: "equals",
  },
};

// Environment-specific tags
const environmentTag = {
  key: "Environment",
  values: [process.env.MEDIALAKE_ENV || "dev"],
  operator: "equals",
};
```

### AWS Resource Requirements

#### Cognito User Pool Tags

```json
{
  "Application": "medialake",
  "Environment": "dev",
  "Testing": "enabled",
  "ResourceType": "cognito-user-pool"
}
```

#### CloudFront Distribution Tags

```json
{
  "Application": "medialake",
  "Environment": "dev",
  "Testing": "enabled",
  "ResourceType": "cloudfront-distribution"
}
```

## Migration Guide

### From Original Fixtures

The enhanced fixtures maintain full backward compatibility. Existing tests using [`auth.fixtures.ts`](auth.fixtures.ts) will continue to work without modification.

#### Gradual Migration

1. **Phase 1**: Use enhanced fixtures alongside existing ones

```typescript
// Existing test (continues to work)
import { test } from "../fixtures/auth.fixtures";

// Enhanced test (new capabilities)
import { test as enhancedTest } from "../fixtures/enhanced-cognito.fixtures";
```

2. **Phase 2**: Migrate to enhanced fixtures for new capabilities

```typescript
// Before
import { test, expect } from "../fixtures/auth.fixtures";

test("login test", async ({ cognitoTestUser, authenticatedPage }) => {
  // Test logic
});

// After
import { test, expect } from "../fixtures/enhanced-cognito.fixtures";

test("enhanced login test", async ({ enhancedCognitoTestUser }) => {
  // Same test logic, but with enhanced capabilities
  expect(enhancedCognitoTestUser.discoveryMethod).toBeTruthy();
});
```

3. **Phase 3**: Full migration to integration tests

```typescript
import { test, expect } from "../integration/aws-tag-discovery-e2e.spec";

test("complete E2E test", async ({
  e2eIntegrationContext,
  authenticatedE2EPage,
}) => {
  // Full end-to-end testing with all enhancements
});
```

### Breaking Changes

**None.** The enhanced fixtures are designed to be fully backward compatible.

## Performance Considerations

### Caching Strategy

- **Worker-Isolated Caches**: Each Playwright worker maintains its own cache
- **Configurable TTL**: Default 5-minute cache with configurable expiration
- **Intelligent Prefetching**: Common resources are prefetched during setup
- **Cache Invalidation**: Manual cache invalidation for testing scenarios

### Discovery Performance

- **Parallel Discovery**: Multiple AWS services discovered concurrently
- **Fallback Optimization**: Fast failure detection with immediate fallback
- **Connection Pooling**: Reused AWS SDK clients across discoveries
- **Retry Logic**: Exponential backoff for transient failures

### Benchmarks

Typical performance metrics (measured in integration tests):

- **Cognito Discovery**: < 2 seconds (cached: < 100ms)
- **CloudFront Discovery**: < 3 seconds (cached: < 100ms)
- **User Creation**: < 2 seconds
- **Complete E2E Setup**: < 10 seconds

## Troubleshooting

### Common Issues

#### 1. No Resources Found

```
Error: No Cognito user pools found with tags: [...]
```

**Solutions:**

- Verify AWS credentials and permissions
- Check resource tags match expected patterns
- Ensure resources exist in the specified region
- Review AWS_PROFILE and AWS_REGION environment variables

#### 2. Discovery Timeout

```
Error: Discovery timeout after 30000ms
```

**Solutions:**

- Check AWS service availability
- Verify network connectivity
- Increase discovery timeout in configuration
- Review AWS API rate limits

#### 3. Permission Errors

```
Error: User is not authorized to perform: cognito-idp:ListUserPools
```

**Solutions:**

- Add required AWS permissions (see [Required Permissions](#required-permissions))
- Verify AWS profile configuration
- Check IAM role/user permissions

#### 4. Cache Issues

```
Warning: Cache hit rate below 50%
```

**Solutions:**

- Increase cache TTL for stable environments
- Review cache size limits
- Check for cache invalidation in tests

### Required Permissions

#### Cognito Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:ListUserPools",
        "cognito-idp:ListUserPoolClients",
        "cognito-idp:DescribeUserPool",
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminSetUserPassword",
        "cognito-idp:AdminDeleteUser",
        "cognito-idp:ListTagsForResource"
      ],
      "Resource": "*"
    }
  ]
}
```

#### CloudFront Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudfront:ListDistributions",
        "cloudfront:GetDistribution",
        "cloudfront:ListTagsForResource",
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation"
      ],
      "Resource": "*"
    }
  ]
}
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable debug logging
DEBUG=aws-discovery,cognito-adapter,cloudfront-adapter npx playwright test

# Enable Playwright debug mode
PWDEBUG=1 npx playwright test tests/integration/aws-tag-discovery-e2e.spec.ts
```

## Best Practices

### Test Organization

1. **Use Integration Tests for E2E Workflows**

   ```typescript
   // For complete workflows
   import { test } from "../integration/aws-tag-discovery-e2e.spec";
   ```

2. **Use Enhanced Fixtures for Component Testing**

   ```typescript
   // For specific component testing
   import { test } from "../fixtures/enhanced-cognito.fixtures";
   ```

3. **Use Original Fixtures for Legacy Compatibility**
   ```typescript
   // For existing tests requiring no changes
   import { test } from "../fixtures/auth.fixtures";
   ```

### Resource Management

1. **Tag Resources Consistently**
   - Use standardized tag patterns
   - Include environment and application tags
   - Add testing-specific tags for test resources

2. **Optimize Discovery Performance**
   - Use appropriate cache TTL for your environment
   - Prefetch common resources in setup
   - Monitor discovery performance metrics

3. **Handle Errors Gracefully**
   - Implement proper fallback mechanisms
   - Use retry logic for transient failures
   - Provide clear error messages for debugging

### Parallel Execution

1. **Ensure Worker Isolation**
   - Each worker gets unique test users
   - Cache instances are worker-isolated
   - Resource cleanup is worker-specific

2. **Optimize Resource Usage**
   - Share discovered resources within worker
   - Use efficient cleanup strategies
   - Monitor resource utilization

## Examples

### Basic Tag-Based Discovery

```typescript
import { test, expect } from "../fixtures/aws-discovery.fixtures";

test("basic resource discovery", async ({ awsResourceContext }) => {
  expect(awsResourceContext.cognitoUserPool).toBeTruthy();
  expect(awsResourceContext.cloudFrontDistribution).toBeTruthy();

  console.log(`Found Cognito pool: ${awsResourceContext.cognitoUserPool.name}`);
  console.log(
    `Found CloudFront distribution: ${awsResourceContext.cloudFrontDistribution.name}`,
  );
});
```

### Enhanced User Creation

```typescript
import { test, expect } from "../fixtures/enhanced-cognito.fixtures";

test("permanent password user creation", async ({
  enhancedCognitoTestUser,
}) => {
  // User is immediately ready for login (no password reset)
  expect(enhancedCognitoTestUser.password).toBeTruthy();
  expect(enhancedCognitoTestUser.discoveryMethod).toBeTruthy();

  // User can be used immediately in login flows
  console.log(`User ready: ${enhancedCognitoTestUser.username}`);
});
```

### CloudFront Testing

```typescript
import {
  test,
  expect,
  CloudFrontTestUtils,
} from "../fixtures/cloudfront.fixtures";

test("CloudFront performance testing", async ({
  cloudFrontContext,
  cloudFrontTestPage,
}) => {
  // Test distribution performance
  const results = await CloudFrontTestUtils.testDistributionAccess(
    cloudFrontTestPage,
    cloudFrontContext.testUrls,
  );

  // Validate performance benchmarks
  results.forEach((result) => {
    expect(result.responseTime).toBeLessThan(5000); // 5 second max
    expect(result.success).toBe(true);
  });
});
```

### Complete E2E Integration

```typescript
import { test, expect } from "../integration/aws-tag-discovery-e2e.spec";

test("complete workflow validation", async ({
  e2eIntegrationContext,
  authenticatedE2EPage,
}) => {
  // Validate complete setup
  expect(e2eIntegrationContext.discoveryMetrics.totalSetupTime).toBeLessThan(
    30000,
  );
  expect(e2eIntegrationContext.validationResults.backwardCompatible).toBe(true);

  // Test authenticated navigation
  await authenticatedE2EPage.goto(
    e2eIntegrationContext.testUrls.cloudFrontDashboard,
  );

  // Validate successful authentication
  expect(authenticatedE2EPage.url()).not.toContain("/sign-in");

  console.log("Complete E2E workflow validated successfully");
});
```

## API Reference

### AWSDiscoveryUtils

```typescript
export const AWSDiscoveryUtils = {
  // Create custom tag filters
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[];

  // Get discovery engine statistics
  async getDiscoveryStats(engine: ResourceDiscoveryEngine): Promise<any>;

  // Invalidate discovery cache
  async invalidateCache(engine: ResourceDiscoveryEngine, resourceType?: string): Promise<void>;
};
```

### EnhancedCognitoUtils

```typescript
export const EnhancedCognitoUtils = {
  // Create custom tag filters
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[];

  // Validate discovery method
  validateDiscoveryMethod(user: EnhancedCognitoTestUser, expectedMethod: string): boolean;

  // Get user pool information
  getUserPoolInfo(user: EnhancedCognitoTestUser): any;
};
```

### CloudFrontTestUtils

```typescript
export const CloudFrontTestUtils = {
  // Test distribution accessibility
  async testDistributionAccess(page: Page, testUrls: CloudFrontTestUrls): Promise<CloudFrontTestResult[]>;

  // Create cache invalidation
  async createTestInvalidation(adapter: CloudFrontServiceAdapter, distributionId: string, paths?: string[]): Promise<string | null>;

  // Wait for invalidation completion
  async waitForInvalidation(adapter: CloudFrontServiceAdapter, distributionId: string, invalidationId: string): Promise<void>;

  // Validate cache headers
  validateCacheHeaders(headers: Record<string, string>): CacheValidationResult;

  // Get distribution information
  getDistributionInfo(context: CloudFrontTestContext): any;

  // Create custom tag filters
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[];
};
```

## Conclusion

The enhanced Playwright fixtures provide a powerful, flexible, and backward-compatible testing framework for MediaLake AWS integration testing. By leveraging tag-based resource discovery, permanent password creation, and comprehensive CloudFront testing capabilities, teams can create more reliable, maintainable, and environment-agnostic tests.

The system is designed to grow with your testing needs while maintaining compatibility with existing test suites, making it an ideal choice for both new and existing MediaLake testing implementations.
