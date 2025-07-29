/**
 * AWS Discovery Integration Test
 * Demonstrates the new tag-based resource discovery utilities
 * and their integration with existing Playwright fixture patterns
 */

import { test, expect } from "./fixtures/aws-discovery.fixtures.js";
import { AWSDiscoveryUtils } from "./fixtures/aws-discovery.fixtures.js";

test.describe("AWS Resource Discovery Integration", () => {
  test("should discover AWS resources using tag-based filtering", async ({
    awsResourceContext,
    discoveryEngine,
  }) => {
    // Verify that the discovery engine is properly initialized
    expect(discoveryEngine).toBeDefined();

    // Check discovery engine statistics
    const stats = await AWSDiscoveryUtils.getDiscoveryStats(discoveryEngine);
    console.log("Discovery Engine Stats:", stats);

    expect(stats.adapters).toContain("cognito-user-pool");
    expect(stats.adapters).toContain("cloudfront-distribution");
    expect(stats.workerIndex).toBeGreaterThanOrEqual(0);

    // Verify resource context structure
    expect(awsResourceContext).toBeDefined();
    expect(awsResourceContext.environment).toBe(
      process.env.MEDIALAKE_ENV || "dev",
    );
    expect(awsResourceContext.region).toBe(
      process.env.AWS_REGION || "us-east-1",
    );
    expect(awsResourceContext.discoveryEngine).toBe(discoveryEngine);

    // Log discovered resources for debugging
    if (awsResourceContext.cognitoUserPool) {
      console.log("Discovered Cognito User Pool:", {
        id: awsResourceContext.cognitoUserPool.id,
        name: awsResourceContext.cognitoUserPool.name,
        tags: awsResourceContext.cognitoUserPool.tags,
        clientCount: awsResourceContext.cognitoUserPool.clients.length,
      });

      // Verify Cognito user pool structure
      expect(awsResourceContext.cognitoUserPool.resourceType).toBe(
        "cognito-user-pool",
      );
      expect(awsResourceContext.cognitoUserPool.id).toMatch(
        /^us-[a-z]+-\d+_[A-Za-z0-9]+$/,
      );
      expect(awsResourceContext.cognitoUserPool.tags.Application).toBe(
        "medialake",
      );
    } else {
      console.warn(
        "No Cognito user pool discovered - this is expected in placeholder mode",
      );
    }

    if (awsResourceContext.cloudFrontDistribution) {
      console.log("Discovered CloudFront Distribution:", {
        id: awsResourceContext.cloudFrontDistribution.id,
        name: awsResourceContext.cloudFrontDistribution.name,
        domainName: awsResourceContext.cloudFrontDistribution.domainName,
        tags: awsResourceContext.cloudFrontDistribution.tags,
        status: awsResourceContext.cloudFrontDistribution.status,
      });

      // Verify CloudFront distribution structure
      expect(awsResourceContext.cloudFrontDistribution.resourceType).toBe(
        "cloudfront-distribution",
      );
      expect(awsResourceContext.cloudFrontDistribution.id).toMatch(
        /^E[A-Z0-9]{13}$/,
      );
      expect(awsResourceContext.cloudFrontDistribution.tags.Application).toBe(
        "medialake",
      );
    } else {
      console.warn(
        "No CloudFront distribution discovered - this is expected in placeholder mode",
      );
    }
  });

  test("should support custom tag filtering", async ({ discoveryEngine }) => {
    // Test custom tag filters
    const customTags = AWSDiscoveryUtils.createCustomTagFilters({
      Application: "medialake",
      Environment: "dev",
      Testing: "enabled",
    });

    expect(customTags).toHaveLength(3);
    expect(customTags[0]).toEqual({
      key: "Application",
      values: ["medialake"],
      operator: "equals",
    });

    // Test discovery with custom filters
    const cognitoPools = await discoveryEngine.discoverByTags(
      "cognito-user-pool",
      customTags,
    );
    const distributions = await discoveryEngine.discoverByTags(
      "cloudfront-distribution",
      customTags,
    );

    // In placeholder mode, we expect mock data or empty arrays
    expect(Array.isArray(cognitoPools)).toBe(true);
    expect(Array.isArray(distributions)).toBe(true);

    console.log(
      `Discovered ${cognitoPools.length} Cognito pools and ${distributions.length} CloudFront distributions`,
    );
  });

  test("should handle cache operations correctly", async ({
    discoveryEngine,
  }) => {
    // Test cache invalidation
    await AWSDiscoveryUtils.invalidateCache(discoveryEngine);

    // Test cache invalidation for specific resource type
    await AWSDiscoveryUtils.invalidateCache(
      discoveryEngine,
      "cognito-user-pool",
    );

    // Verify cache stats
    const stats = await AWSDiscoveryUtils.getDiscoveryStats(discoveryEngine);
    expect(stats.cache).toBeDefined();
    expect(typeof stats.cache.size).toBe("number");
  });

  test("should work with individual service adapters", async ({
    cognitoDiscovery,
    cloudFrontDiscovery,
  }) => {
    // Test Cognito service adapter
    expect(cognitoDiscovery).toBeDefined();
    expect(cognitoDiscovery.getResourceType()).toBe("cognito-user-pool");

    // Test CloudFront service adapter
    expect(cloudFrontDiscovery).toBeDefined();
    expect(cloudFrontDiscovery.getResourceType()).toBe(
      "cloudfront-distribution",
    );

    // Test resource discovery through individual adapters
    const standardFilters = [
      {
        key: "Application",
        values: ["medialake"],
        operator: "equals" as const,
      },
      { key: "Testing", values: ["enabled"], operator: "equals" as const },
    ];

    const cognitoPools =
      await cognitoDiscovery.discoverResources(standardFilters);
    const distributions =
      await cloudFrontDiscovery.discoverResources(standardFilters);

    expect(Array.isArray(cognitoPools)).toBe(true);
    expect(Array.isArray(distributions)).toBe(true);

    // Test resource validation
    if (cognitoPools.length > 0) {
      const isValid = await cognitoDiscovery.validateResource(cognitoPools[0]);
      expect(typeof isValid).toBe("boolean");
    }

    if (distributions.length > 0) {
      const isValid = await cloudFrontDiscovery.validateResource(
        distributions[0],
      );
      expect(typeof isValid).toBe("boolean");
    }
  });
});

test.describe("Enhanced Cognito Integration", () => {
  test("should create enhanced test user with discovered resources", async ({
    awsResourceContext,
  }) => {
    // This test demonstrates how the enhanced fixture would work
    // when AWS SDK packages are installed and resources are properly tagged

    if (awsResourceContext.cognitoUserPool) {
      console.log(
        "Enhanced Cognito test would use pool:",
        awsResourceContext.cognitoUserPool.name,
      );

      // Verify user pool has required properties for enhanced testing
      expect(awsResourceContext.cognitoUserPool.clients.length).toBeGreaterThan(
        0,
      );
      expect(awsResourceContext.cognitoUserPool.status).toBeDefined();

      // Test password policy retrieval (placeholder)
      console.log("Would retrieve password policy for enhanced user creation");
    } else {
      console.log("Enhanced Cognito test skipped - no user pool discovered");
    }
  });
});

test.describe("Backward Compatibility", () => {
  test("should maintain compatibility with existing fixture patterns", async ({
    awsResourceContext,
  }) => {
    // Verify that the new discovery system provides the same interface
    // that existing tests would expect

    expect(awsResourceContext.region).toBe(
      process.env.AWS_REGION || "us-east-1",
    );
    expect(awsResourceContext.environment).toBe(
      process.env.MEDIALAKE_ENV || "dev",
    );

    // The discovery engine should be available for advanced use cases
    expect(awsResourceContext.discoveryEngine).toBeDefined();

    // Resources should be structured consistently
    if (awsResourceContext.cognitoUserPool) {
      expect(awsResourceContext.cognitoUserPool).toHaveProperty("id");
      expect(awsResourceContext.cognitoUserPool).toHaveProperty("name");
      expect(awsResourceContext.cognitoUserPool).toHaveProperty("tags");
      expect(awsResourceContext.cognitoUserPool).toHaveProperty("clients");
    }

    if (awsResourceContext.cloudFrontDistribution) {
      expect(awsResourceContext.cloudFrontDistribution).toHaveProperty("id");
      expect(awsResourceContext.cloudFrontDistribution).toHaveProperty(
        "domainName",
      );
      expect(awsResourceContext.cloudFrontDistribution).toHaveProperty("tags");
      expect(awsResourceContext.cloudFrontDistribution).toHaveProperty(
        "status",
      );
    }
  });
});
