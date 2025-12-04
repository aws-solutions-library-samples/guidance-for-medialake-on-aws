---
title: Extension Strategy for Existing Fixture Patterns
task_id: 1.1
date: 2025-07-27
last_updated: 2025-07-27
status: DRAFT
owner: Architect
---

# Extension Strategy for Existing Fixture Patterns

## Objective

Define a comprehensive strategy for extending the existing MediaLake Playwright fixture patterns to support tag-based AWS resource discovery while maintaining backward compatibility and preserving the sophisticated testing capabilities already established.

## Current Fixture Analysis

### Existing Architecture Strengths

#### 1. Sophisticated Cognito Integration

- **Dynamic User Creation**: [`createTestUser()`](medialake_user_interface/tests/fixtures/cognito.fixtures.ts:179-228) with password policy compliance
- **Worker-Scoped Isolation**: Unique test users per worker with [`testInfo.workerIndex`](medialake_user_interface/tests/fixtures/cognito.fixtures.ts:258)
- **Secure Cleanup**: Automatic user deletion in fixture teardown
- **Error Resilience**: Handles existing users gracefully with password updates

#### 2. S3 Integration Patterns

- **Worker-Scoped Buckets**: [`s3BucketName`](medialake_user_interface/tests/fixtures/auth.fixtures.ts:109-184) fixture with worker isolation
- **Lifecycle Management**: Automatic bucket creation, emptying, and deletion
- **Manual Cleanup Support**: [`s3BucketDeletion`](medialake_user_interface/tests/fixtures/auth.fixtures.ts:186-219) fixture for explicit cleanup

#### 3. Authentication Flow Integration

- **Seamless Login**: [`authenticatedPage`](medialake_user_interface/tests/fixtures/auth.fixtures.ts:81-105) fixture handles complete login flow
- **Context Management**: [`authenticatedContext`](medialake_user_interface/tests/fixtures/auth.fixtures.ts:222-251) for multi-page scenarios
- **Network State Handling**: Proper wait conditions for SPA navigation

## Extension Strategy

### 1. Layered Extension Architecture

```typescript
// Base layer: Core resource discovery
interface ResourceDiscoveryLayer {
  discoveryEngine: ResourceDiscoveryEngine;
  cacheManager: ResourceCacheManager;
  serviceAdapters: Map<string, ServiceAdapter>;
}

// Service layer: AWS service-specific adapters
interface ServiceAdapterLayer {
  cognitoAdapter: CognitoServiceAdapter;
  cloudFrontAdapter: CloudFrontServiceAdapter;
  s3Adapter: S3ServiceAdapter;
}

// Fixture layer: Playwright test integration
interface FixtureExtensionLayer {
  enhancedCognitoFixtures: EnhancedCognitoFixtures;
  cloudFrontFixtures: CloudFrontFixtures;
  unifiedResourceContext: UnifiedResourceContext;
}
```

### 2. Backward Compatibility Strategy

#### Phase 1: Non-Breaking Extension

```typescript
// Extend existing fixtures without modifying interfaces
export const test = cognitoBase.extend<EnhancedCognitoFixtures>({
  // Preserve existing cognitoTestUser interface
  cognitoTestUser: [
    async ({}, use, testInfo) => {
      const discoveryEngine = new ResourceDiscoveryEngine();

      // Primary: Tag-based discovery
      let userPools = await discoveryEngine.discoverByTags(
        "cognito-user-pool",
        [StandardTagPatterns.APPLICATION_TAG],
      );

      // Fallback: Existing name-based discovery
      if (userPools.length === 0) {
        console.warn("[Migration] Using legacy name-based discovery");
        const userPoolId = findUserPoolId(); // Existing function
        const userPoolClientId = findUserPoolClientId(userPoolId);
        userPools = [{ id: userPoolId, clientId: userPoolClientId }];
      }

      // Continue with existing user creation logic
      const selectedPool = userPools[0];
      const passwordPolicy = getUserPoolPasswordPolicy(selectedPool.id);
      const password = generateSecurePassword(passwordPolicy);

      const uniqueEmail = `mne-medialake+e2etest-${
        testInfo.workerIndex
      }-${crypto.randomBytes(4).toString("hex")}@amazon.com`;
      createTestUser(selectedPool.id, uniqueEmail, password, uniqueEmail);

      await use({
        username: uniqueEmail,
        password,
        email: uniqueEmail,
        userPoolId: selectedPool.id,
        userPoolClientId: selectedPool.clientId,
      });

      // Existing cleanup logic
      deleteTestUser(selectedPool.id, uniqueEmail);
    },
    { scope: "test" },
  ],
});
```

#### Phase 2: Enhanced Capabilities

```typescript
// Add new fixtures alongside existing ones
export const enhancedTest = test.extend<ResourceDiscoveryFixtures>({
  resourceContext: [
    async ({}, use, workerInfo) => {
      const discoveryEngine = new ResourceDiscoveryEngine();

      // Discover all required resources in parallel
      const [cognitoResources, cloudFrontResources] = await Promise.all([
        discoveryEngine.discoverByTags("cognito-user-pool", standardTags),
        discoveryEngine.discoverByTags("cloudfront-distribution", standardTags),
      ]);

      const context: UnifiedResourceContext = {
        cognito: cognitoResources[0] || null,
        cloudFront: cloudFrontResources[0] || null,
        worker: workerInfo.workerIndex,
        environment: process.env.NODE_ENV || "dev",
      };

      await use(context);
    },
    { scope: "worker" },
  ],
});
```

### 3. Progressive Enhancement Pattern

#### Stage 1: Discovery Layer Integration

```typescript
class EnhancedCognitoFixture {
  private discoveryEngine: ResourceDiscoveryEngine;
  private fallbackDiscovery: LegacyDiscovery;

  constructor() {
    this.discoveryEngine = new ResourceDiscoveryEngine();
    this.fallbackDiscovery = new LegacyDiscovery();
  }

  async discoverUserPool(): Promise<CognitoUserPool> {
    try {
      // Attempt tag-based discovery
      const pools = await this.discoveryEngine.discoverByTags(
        "cognito-user-pool",
        [StandardTagPatterns.APPLICATION_TAG],
      );

      if (pools.length > 0) {
        console.log("[Enhanced] Using tag-based discovery");
        return pools[0];
      }
    } catch (error) {
      console.warn("[Enhanced] Tag-based discovery failed:", error.message);
    }

    // Fallback to existing logic
    console.log("[Enhanced] Using legacy name-based discovery");
    return this.fallbackDiscovery.findUserPoolByName();
  }
}
```

#### Stage 2: Service Integration

```typescript
class UnifiedServiceManager {
  private services: Map<string, ServiceAdapter> = new Map();

  constructor() {
    this.services.set("cognito", new CognitoServiceAdapter());
    this.services.set("cloudfront", new CloudFrontServiceAdapter());
    this.services.set("s3", new S3ServiceAdapter());
  }

  async discoverResources(serviceTypes: string[]): Promise<ServiceResourceMap> {
    const discoveries = serviceTypes.map(async (serviceType) => {
      const adapter = this.services.get(serviceType);
      if (!adapter) {
        throw new Error(`Unknown service type: ${serviceType}`);
      }

      const resources = await adapter.discoverByTags([
        StandardTagPatterns.APPLICATION_TAG,
        StandardTagPatterns.TESTING_TAG,
      ]);

      return { serviceType, resources };
    });

    const results = await Promise.all(discoveries);
    return new Map(results.map((r) => [r.serviceType, r.resources]));
  }
}
```

#### Stage 3: Unified Context

```typescript
interface UnifiedTestContext {
  // Existing interfaces preserved
  cognitoTestUser: CognitoTestUser;
  authenticatedPage: Page;
  s3BucketName: string;

  // New enhanced capabilities
  resourceContext?: UnifiedResourceContext;
  cloudFrontContext?: CloudFrontTestContext;
  performanceMetrics?: PerformanceCollector;
}

export const unifiedTest = authBase.extend<UnifiedTestContext>({
  resourceContext: [
    async ({ cognitoTestUser, s3BucketName }, use, workerInfo) => {
      const serviceManager = new UnifiedServiceManager();

      // Build context from discovered and existing resources
      const context: UnifiedResourceContext = {
        cognito: {
          userPool: cognitoTestUser.userPoolId,
          userPoolClient: cognitoTestUser.userPoolClientId,
          testUser: cognitoTestUser,
        },
        s3: {
          testBucket: s3BucketName,
        },
        cloudFront: await this.discoverCloudFrontContext(),
        worker: workerInfo.workerIndex,
        environment: this.detectEnvironment(),
      };

      await use(context);
    },
    { scope: "test" },
  ],
});
```

### 4. Migration Patterns

#### Pattern 1: Gradual Adoption

```typescript
// Tests can opt-in to enhanced features
test("existing test continues to work", async ({
  cognitoTestUser,
  authenticatedPage,
}) => {
  // Existing test code unchanged
  await authenticatedPage.goto("/dashboard");
  await expect(
    authenticatedPage.locator('[data-testid="welcome"]'),
  ).toBeVisible();
});

enhancedTest(
  "new test with CloudFront",
  async ({ resourceContext, authenticatedPage }) => {
    test.skip(!resourceContext?.cloudFront, "CloudFront not available");

    // New capabilities available
    const cdnUrl = resourceContext.cloudFront.primaryDomain;
    await authenticatedPage.goto(`https://${cdnUrl}/dashboard`);
    await expect(
      authenticatedPage.locator('[data-testid="welcome"]'),
    ).toBeVisible();
  },
);
```

#### Pattern 2: Feature Flag Integration

```typescript
interface FeatureFlags {
  enableTagBasedDiscovery: boolean;
  enableCloudFrontTesting: boolean;
  enablePerformanceMetrics: boolean;
}

class FeatureAwareFixture {
  private flags: FeatureFlags;

  constructor() {
    this.flags = {
      enableTagBasedDiscovery: process.env.ENABLE_TAG_DISCOVERY === "true",
      enableCloudFrontTesting: process.env.ENABLE_CLOUDFRONT_TESTS === "true",
      enablePerformanceMetrics:
        process.env.ENABLE_PERFORMANCE_METRICS === "true",
    };
  }

  async setupFixtures(): Promise<TestFixtures> {
    const fixtures: TestFixtures = {};

    if (this.flags.enableTagBasedDiscovery) {
      fixtures.resourceDiscovery = new ResourceDiscoveryEngine();
    }

    if (this.flags.enableCloudFrontTesting) {
      fixtures.cloudFrontTester = new CloudFrontTestingEngine();
    }

    return fixtures;
  }
}
```

### 5. Error Handling and Resilience

#### Graceful Degradation Strategy

```typescript
class ResilientFixtureManager {
  async setupWithFallback<T>(
    primarySetup: () => Promise<T>,
    fallbackSetup: () => Promise<T>,
    context: string,
  ): Promise<T> {
    try {
      const result = await primarySetup();
      console.log(`[${context}] Primary setup successful`);
      return result;
    } catch (error) {
      console.warn(
        `[${context}] Primary setup failed, using fallback:`,
        error.message,
      );

      try {
        const result = await fallbackSetup();
        console.log(`[${context}] Fallback setup successful`);
        return result;
      } catch (fallbackError) {
        console.error(`[${context}] Both primary and fallback setup failed`);
        throw new Error(
          `Setup failed: ${error.message} (fallback: ${fallbackError.message})`,
        );
      }
    }
  }
}
```

#### Resource Availability Checks

```typescript
class ResourceAvailabilityChecker {
  async checkResourceHealth(
    context: UnifiedResourceContext,
  ): Promise<HealthCheckResult> {
    const checks = await Promise.allSettled([
      this.checkCognitoHealth(context.cognito),
      this.checkS3Health(context.s3),
      this.checkCloudFrontHealth(context.cloudFront),
    ]);

    return {
      overall: checks.every((check) => check.status === "fulfilled"),
      details: checks.map((check, index) => ({
        service: ["cognito", "s3", "cloudfront"][index],
        healthy: check.status === "fulfilled",
        error: check.status === "rejected" ? check.reason.message : null,
      })),
    };
  }

  async waitForResourceReadiness(
    resourceId: string,
    checkFn: () => Promise<boolean>,
    maxWaitTime: number = 300000,
  ): Promise<boolean> {
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitTime) {
      try {
        if (await checkFn()) {
          return true;
        }
      } catch (error) {
        console.warn(`Resource ${resourceId} not ready:`, error.message);
      }

      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    return false;
  }
}
```

### 6. Testing Strategy for Extensions

#### Unit Testing for Discovery Logic

```typescript
describe("ResourceDiscoveryEngine", () => {
  let mockAWSClient: jest.Mocked<ResourceGroupsTaggingAPIClient>;
  let discoveryEngine: ResourceDiscoveryEngine;

  beforeEach(() => {
    mockAWSClient = createMockAWSClient();
    discoveryEngine = new ResourceDiscoveryEngine(mockAWSClient);
  });

  test("should discover resources by tags", async () => {
    mockAWSClient.getResources.mockResolvedValue({
      ResourceTagMappingList: [
        {
          ResourceARN:
            "arn:aws:cognito-idp:us-east-1:123456789:userpool/us-east-1_ABC123",
          Tags: [
            { Key: "Application", Value: "medialake" },
            { Key: "Environment", Value: "dev" },
          ],
        },
      ],
    });

    const resources = await discoveryEngine.discoverByTags(
      "cognito-user-pool",
      [{ key: "Application", values: ["medialake"], operator: "equals" }],
    );

    expect(resources).toHaveLength(1);
    expect(resources[0].id).toBe("us-east-1_ABC123");
  });
});
```

#### Integration Testing for Fixture Extensions

```typescript
describe("Enhanced Fixture Integration", () => {
  test("should maintain backward compatibility", async () => {
    // Test that existing fixtures still work
    await test.step("legacy fixture works", async () => {
      const { cognitoTestUser } = await setupLegacyFixtures();
      expect(cognitoTestUser.username).toBeDefined();
      expect(cognitoTestUser.password).toBeDefined();
    });
  });

  test("should provide enhanced capabilities when available", async () => {
    await test.step("enhanced fixture provides additional context", async () => {
      const { resourceContext } = await setupEnhancedFixtures();

      if (resourceContext?.cloudFront) {
        expect(resourceContext.cloudFront.primaryDomain).toBeDefined();
        expect(resourceContext.cloudFront.testAssets).toBeInstanceOf(Array);
      }
    });
  });
});
```

### 7. Documentation and Migration Guide

#### Developer Migration Guide

````markdown
# Migrating to Enhanced Fixtures

## Phase 1: No Changes Required

Your existing tests continue to work without modification:

```typescript
test("existing test", async ({ cognitoTestUser, authenticatedPage }) => {
  // No changes needed
});
```
````

## Phase 2: Opt-in to Enhanced Features

```typescript
import { enhancedTest as test } from "./fixtures/enhanced-fixtures";

test("new test with CloudFront", async ({
  resourceContext,
  authenticatedPage,
}) => {
  test.skip(!resourceContext?.cloudFront, "CloudFront not available");
  // Use enhanced capabilities
});
```

## Phase 3: Full Migration (Optional)

```typescript
import { unifiedTest as test } from "./fixtures/unified-fixtures";

test("fully enhanced test", async ({
  resourceContext,
  performanceMetrics,
  authenticatedPage,
}) => {
  // Access to all enhanced capabilities
});
```

````

#### Team Training Materials
```markdown
# Enhanced Testing Capabilities

## Resource Discovery
- Automatic discovery of AWS resources using tags
- Environment-aware resource selection
- Fallback to existing discovery methods

## CloudFront Testing
- Automated content delivery testing
- Cache effectiveness validation
- Performance monitoring
- Security header verification

## Performance Metrics
- Response time measurement
- Cache hit rate tracking
- Global distribution testing
````

## Implementation Timeline

### Week 1-2: Foundation

- Implement ResourceDiscoveryEngine
- Create service adapters for Cognito and CloudFront
- Add backward compatibility layer to existing fixtures

### Week 3-4: Integration

- Extend existing fixtures with tag-based discovery
- Implement CloudFront testing capabilities
- Add comprehensive error handling and fallback mechanisms

### Week 5-6: Enhancement

- Add performance metrics collection
- Implement unified resource context
- Create migration documentation and training materials

### Week 7-8: Validation

- Comprehensive testing of all fixture extensions
- Performance optimization and caching improvements
- Team training and documentation finalization

## Success Metrics

### Technical Metrics

- **Backward Compatibility**: 100% of existing tests continue to pass
- **Discovery Performance**: <2 second average resource discovery time
- **Cache Effectiveness**: >90% cache hit rate for repeated discoveries
- **Error Resilience**: <5% test failure rate due to resource discovery issues

### Operational Metrics

- **Team Adoption**: >80% of new tests use enhanced fixtures within 3 months
- **Resource Coverage**: Support for 3+ AWS services (Cognito, CloudFront, S3)
- **Environment Support**: Consistent behavior across dev/staging/prod environments

## Next Actions

1. Begin implementation of ResourceDiscoveryEngine core components
2. Create AWS SDK integration specification document
3. Set up development environment for fixture extension testing
4. Coordinate with infrastructure team for resource tagging implementation
