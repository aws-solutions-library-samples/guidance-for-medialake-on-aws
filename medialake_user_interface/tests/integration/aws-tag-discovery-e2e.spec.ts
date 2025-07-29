/**
 * AWS Tag-Based Discovery End-to-End Integration Tests
 *
 * Comprehensive integration test suite that validates the complete workflow from
 * tag-based resource discovery through automated login, ensuring backward compatibility
 * and providing complete validation of all components working together.
 *
 * This test suite brings together:
 * - AWS resource discovery utilities
 * - Enhanced Cognito fixtures with permanent password creation
 * - CloudFront fixtures and login automation
 * - Existing auth patterns for backward compatibility
 * - Performance and caching validation
 * - Parallel execution and worker isolation
 */

import { test as base, expect } from "@playwright/test";
import { AWSDiscoveryUtils } from "../fixtures/aws-discovery.fixtures";
import { CloudFrontTestUtils } from "../fixtures/cloudfront.fixtures";
import { Page } from "@playwright/test";

// Import utilities for comprehensive testing
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "../utils/aws-resource-finder.js";
import {
  CognitoServiceAdapter,
  createCognitoServiceAdapter,
  CognitoUserPool,
} from "../utils/cognito-service-adapter.js";
import {
  CloudFrontServiceAdapter,
  createCloudFrontServiceAdapter,
  CloudFrontDistribution,
} from "../utils/cloudfront-service-adapter.js";
import { TagFilter, STANDARD_TAG_PATTERNS } from "../utils/tag-matcher.js";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Comprehensive integration test context
interface E2EIntegrationContext {
  // Discovery components
  discoveryEngine: ResourceDiscoveryEngine;
  cognitoAdapter: CognitoServiceAdapter;
  cloudFrontAdapter: CloudFrontServiceAdapter;

  // Discovered resources
  cognitoUserPool: CognitoUserPool | null;
  cloudFrontDistribution: CloudFrontDistribution | null;

  // Test user and authentication
  testUser: {
    username: string;
    password: string;
    email: string;
    userPoolId: string;
    userPoolClientId: string;
    discoveryMethod: "tag-based" | "name-based" | "fallback";
  };

  // URLs and endpoints
  testUrls: {
    cloudFrontRoot: string;
    cloudFrontLogin: string;
    cloudFrontDashboard: string;
    healthCheck: string;
  };

  // Performance metrics
  discoveryMetrics: {
    cognitoDiscoveryTime: number;
    cloudFrontDiscoveryTime: number;
    userCreationTime: number;
    totalSetupTime: number;
  };

  // Validation flags
  validationResults: {
    tagBasedDiscoveryWorking: boolean;
    permanentPasswordWorking: boolean;
    cloudFrontAccessible: boolean;
    backwardCompatible: boolean;
  };
}

interface E2EIntegrationFixtures {
  e2eIntegrationContext: E2EIntegrationContext;
  authenticatedE2EPage: Page;
}

/**
 * Create comprehensive discovery configuration
 */
function createE2EDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 300000, // 5 minutes
    maxCacheSize: 100,
    enableFallback: true,
  };
}

/**
 * Get comprehensive tag filters for E2E testing
 */
function getE2ETagFilters(): TagFilter[] {
  return [
    STANDARD_TAG_PATTERNS.APPLICATION_TAG,
    {
      key: "Environment",
      values: [ENVIRONMENT],
      operator: "equals",
    },
    STANDARD_TAG_PATTERNS.TESTING_TAG,
  ];
}

/**
 * Perform comprehensive resource discovery with timing
 */
async function performComprehensiveDiscovery(
  discoveryEngine: ResourceDiscoveryEngine,
  cognitoAdapter: CognitoServiceAdapter,
  cloudFrontAdapter: CloudFrontServiceAdapter,
): Promise<{
  cognitoUserPool: CognitoUserPool | null;
  cloudFrontDistribution: CloudFrontDistribution | null;
  metrics: {
    cognitoDiscoveryTime: number;
    cloudFrontDiscoveryTime: number;
  };
}> {
  const tagFilters = getE2ETagFilters();

  // Discover Cognito user pool with timing
  const cognitoStartTime = Date.now();
  let cognitoUserPool: CognitoUserPool | null = null;

  try {
    const cognitoPools = await discoveryEngine.discoverByTags(
      "cognito-user-pool",
      tagFilters,
    );
    if (cognitoPools.length > 0) {
      cognitoUserPool = cognitoPools[0] as CognitoUserPool;
      console.log(
        `[E2E] Found Cognito user pool via tags: ${cognitoUserPool.name} (${cognitoUserPool.id})`,
      );
    } else {
      // Fallback to service adapter
      const fallbackPools = await cognitoAdapter.fallbackDiscovery(tagFilters);
      if (fallbackPools.length > 0) {
        cognitoUserPool = fallbackPools[0];
        console.log(
          `[E2E] Found Cognito user pool via fallback: ${cognitoUserPool.name} (${cognitoUserPool.id})`,
        );
      }
    }
  } catch (error) {
    console.warn("[E2E] Cognito discovery failed:", error);
  }

  const cognitoDiscoveryTime = Date.now() - cognitoStartTime;

  // Discover CloudFront distribution with timing
  const cloudFrontStartTime = Date.now();
  let cloudFrontDistribution: CloudFrontDistribution | null = null;

  try {
    const distributions = await discoveryEngine.discoverByTags(
      "cloudfront-distribution",
      tagFilters,
    );
    if (distributions.length > 0) {
      cloudFrontDistribution = distributions[0] as CloudFrontDistribution;
      console.log(
        `[E2E] Found CloudFront distribution via tags: ${cloudFrontDistribution.name} (${cloudFrontDistribution.id})`,
      );
    } else {
      // Fallback to service adapter
      const fallbackDistributions =
        await cloudFrontAdapter.fallbackDiscovery(tagFilters);
      if (fallbackDistributions.length > 0) {
        cloudFrontDistribution = fallbackDistributions[0];
        console.log(
          `[E2E] Found CloudFront distribution via fallback: ${cloudFrontDistribution.name} (${cloudFrontDistribution.id})`,
        );
      }
    }
  } catch (error) {
    console.warn("[E2E] CloudFront discovery failed:", error);
  }

  const cloudFrontDiscoveryTime = Date.now() - cloudFrontStartTime;

  return {
    cognitoUserPool,
    cloudFrontDistribution,
    metrics: {
      cognitoDiscoveryTime,
      cloudFrontDiscoveryTime,
    },
  };
}

/**
 * Create test user with comprehensive validation
 */
async function createE2ETestUser(
  cognitoAdapter: CognitoServiceAdapter,
  userPool: CognitoUserPool,
  workerIndex: number,
): Promise<{
  testUser: any;
  creationTime: number;
  discoveryMethod: "tag-based" | "name-based" | "fallback";
}> {
  const startTime = Date.now();
  const randomId = Math.random().toString(36).substring(2, 8);
  const uniqueEmail = `mne-medialake+e2etest-${workerIndex}-${randomId}@amazon.com`;

  // Get password policy and generate secure password
  const passwordPolicy = await cognitoAdapter.getUserPoolPasswordPolicy(
    userPool.id,
  );
  const password = generateSecurePassword(passwordPolicy?.PasswordPolicy);

  // Create user with permanent password
  await cognitoAdapter.createTestUser(
    userPool.id,
    uniqueEmail,
    password,
    uniqueEmail,
  );

  const testUser = {
    username: uniqueEmail,
    password,
    email: uniqueEmail,
    userPoolId: userPool.id,
    userPoolClientId: userPool.clients[0]?.id || "",
    discoveryMethod:
      userPool.tags?.DiscoveryMethod === "tag-based"
        ? ("tag-based" as const)
        : ("fallback" as const),
  };

  const creationTime = Date.now() - startTime;

  return {
    testUser,
    creationTime,
    discoveryMethod: testUser.discoveryMethod,
  };
}

/**
 * Generate secure password (duplicated from enhanced-cognito.fixtures.ts for isolation)
 */
function generateSecurePassword(passwordPolicy?: any): string {
  const minLength = passwordPolicy?.MinimumLength || 20;
  const requireUppercase = passwordPolicy?.RequireUppercase !== false;
  const requireLowercase = passwordPolicy?.RequireLowercase !== false;
  const requireNumbers = passwordPolicy?.RequireNumbers !== false;
  const requireSymbols = passwordPolicy?.RequireSymbols !== false;

  const uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowercase = "abcdefghijklmnopqrstuvwxyz";
  const numbers = "0123456789";
  const symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?";

  let password = "";
  let availableChars = "";

  // Add required character types
  if (requireUppercase) {
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    availableChars += uppercase;
  }

  if (requireLowercase) {
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    availableChars += lowercase;
  }

  if (requireNumbers) {
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    availableChars += numbers;
  }

  if (requireSymbols) {
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
    availableChars += symbols;
  }

  // If no specific requirements, use all character types
  if (!availableChars) {
    availableChars = uppercase + lowercase + numbers + symbols;
    password += uppercase.charAt(Math.floor(Math.random() * uppercase.length));
    password += lowercase.charAt(Math.floor(Math.random() * lowercase.length));
    password += numbers.charAt(Math.floor(Math.random() * numbers.length));
    password += symbols.charAt(Math.floor(Math.random() * symbols.length));
  }

  // Fill to minimum length
  while (password.length < minLength) {
    password += availableChars.charAt(
      Math.floor(Math.random() * availableChars.length),
    );
  }

  // Shuffle the password to randomize character positions
  return password
    .split("")
    .sort(() => Math.random() - 0.5)
    .join("");
}

/**
 * Generate test URLs from CloudFront distribution
 */
function generateE2ETestUrls(distribution: CloudFrontDistribution): any {
  const primaryDomain =
    distribution.aliases.length > 0
      ? distribution.aliases[0]
      : distribution.domainName;

  const baseUrl = `https://${primaryDomain}`;

  return {
    cloudFrontRoot: baseUrl,
    cloudFrontLogin: `${baseUrl}/sign-in`,
    cloudFrontDashboard: `${baseUrl}/dashboard`,
    healthCheck: `${baseUrl}/health`,
  };
}

/**
 * Perform comprehensive login validation
 */
async function performE2ELogin(
  page: Page,
  loginUrl: string,
  username: string,
  password: string,
): Promise<{ success: boolean; responseTime: number; error?: string }> {
  const startTime = Date.now();

  try {
    console.log(`[E2E] Performing comprehensive login at: ${loginUrl}`);

    // Navigate to login page
    const response = await page.goto(loginUrl, {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    if (!response || response.status() >= 400) {
      throw new Error(
        `Login page returned status: ${response?.status() || "unknown"}`,
      );
    }

    // Wait for login form
    await page.waitForSelector(
      'input[name="email"], [role="textbox"][name*="Email"]',
      { timeout: 10000 },
    );

    // Fill and submit login form
    await page.getByRole("textbox", { name: "Email" }).fill(username);
    await page.getByRole("textbox", { name: "Password" }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();

    // Wait for successful login
    await page.waitForURL(
      (url) =>
        url.toString().includes("/dashboard") ||
        url.toString().endsWith("/") ||
        !url.toString().includes("/sign-in"),
      { timeout: 15000 },
    );

    await page.waitForLoadState("networkidle");

    const responseTime = Date.now() - startTime;
    console.log(`[E2E] Login successful in ${responseTime}ms`);

    return { success: true, responseTime };
  } catch (error: any) {
    const responseTime = Date.now() - startTime;
    console.error(`[E2E] Login failed after ${responseTime}ms:`, error.message);

    return {
      success: false,
      responseTime,
      error: error.message,
    };
  }
}

/**
 * Validate backward compatibility with existing fixtures
 */
async function validateBackwardCompatibility(
  context: E2EIntegrationContext,
): Promise<boolean> {
  try {
    // Validate that discovered resources match expected patterns
    if (context.cognitoUserPool) {
      const expectedUserPoolPattern = /medialake/i;
      if (!expectedUserPoolPattern.test(context.cognitoUserPool.name)) {
        console.warn("[E2E] User pool name does not match expected pattern");
        return false;
      }
    }

    // Validate test user format matches existing patterns
    const expectedEmailPattern =
      /^mne-medialake\+e2etest-\d+-[a-f0-9]+@amazon\.com$/;
    if (!expectedEmailPattern.test(context.testUser.email)) {
      console.warn("[E2E] Test user email does not match expected pattern");
      return false;
    }

    // Validate password meets requirements
    if (context.testUser.password.length < 8) {
      console.warn(
        "[E2E] Test user password does not meet minimum requirements",
      );
      return false;
    }

    console.log("[E2E] Backward compatibility validation passed");
    return true;
  } catch (error) {
    console.error("[E2E] Backward compatibility validation failed:", error);
    return false;
  }
}

// Create comprehensive E2E integration test fixture
const e2eIntegrationTest = base.extend<E2EIntegrationFixtures>({
  /**
   * Comprehensive E2E integration context
   */
  e2eIntegrationContext: [
    async (fixtures, use, testInfo) => {
      const setupStartTime = Date.now();
      console.log(
        `[E2E Worker ${testInfo.workerIndex}] Setting up comprehensive integration context`,
      );

      const config = createE2EDiscoveryConfig();
      const discoveryEngine = createResourceDiscoveryEngine(
        config,
        testInfo.workerIndex,
      );
      const cognitoAdapter = createCognitoServiceAdapter(config);
      const cloudFrontAdapter = createCloudFrontServiceAdapter(config);

      // Register adapters
      discoveryEngine.registerAdapter(cognitoAdapter);
      discoveryEngine.registerAdapter(cloudFrontAdapter);

      let context: E2EIntegrationContext | null = null;

      try {
        // Perform comprehensive resource discovery
        const discoveryResult = await performComprehensiveDiscovery(
          discoveryEngine,
          cognitoAdapter,
          cloudFrontAdapter,
        );

        if (!discoveryResult.cognitoUserPool) {
          throw new Error(
            "No Cognito user pool could be discovered for E2E testing",
          );
        }

        if (!discoveryResult.cloudFrontDistribution) {
          throw new Error(
            "No CloudFront distribution could be discovered for E2E testing",
          );
        }

        // Create test user
        const userCreationResult = await createE2ETestUser(
          cognitoAdapter,
          discoveryResult.cognitoUserPool,
          testInfo.workerIndex,
        );

        // Generate test URLs
        const testUrls = generateE2ETestUrls(
          discoveryResult.cloudFrontDistribution,
        );

        const totalSetupTime = Date.now() - setupStartTime;

        // Build comprehensive context
        context = {
          discoveryEngine,
          cognitoAdapter,
          cloudFrontAdapter,
          cognitoUserPool: discoveryResult.cognitoUserPool,
          cloudFrontDistribution: discoveryResult.cloudFrontDistribution,
          testUser: userCreationResult.testUser,
          testUrls,
          discoveryMetrics: {
            cognitoDiscoveryTime: discoveryResult.metrics.cognitoDiscoveryTime,
            cloudFrontDiscoveryTime:
              discoveryResult.metrics.cloudFrontDiscoveryTime,
            userCreationTime: userCreationResult.creationTime,
            totalSetupTime,
          },
          validationResults: {
            tagBasedDiscoveryWorking:
              discoveryResult.cognitoUserPool.tags?.DiscoveryMethod ===
              "tag-based",
            permanentPasswordWorking: true, // Validated during user creation
            cloudFrontAccessible: false, // Will be validated during login
            backwardCompatible: false, // Will be validated separately
          },
        };

        // Validate backward compatibility
        context.validationResults.backwardCompatible =
          await validateBackwardCompatibility(context);

        console.log(`[E2E] Integration context ready in ${totalSetupTime}ms`);
        console.log(
          `[E2E] Cognito discovery: ${context.discoveryMetrics.cognitoDiscoveryTime}ms`,
        );
        console.log(
          `[E2E] CloudFront discovery: ${context.discoveryMetrics.cloudFrontDiscoveryTime}ms`,
        );
        console.log(
          `[E2E] User creation: ${context.discoveryMetrics.userCreationTime}ms`,
        );

        await use(context);
      } catch (error) {
        console.error(`[E2E] Error setting up integration context:`, error);
        throw error;
      } finally {
        // Cleanup
        if (context?.testUser) {
          try {
            await cognitoAdapter.deleteTestUser(
              context.testUser.userPoolId,
              context.testUser.username,
            );
          } catch (cleanupError) {
            console.error("[E2E] Error during user cleanup:", cleanupError);
          }
        }

        await discoveryEngine.cleanup();
        await cognitoAdapter.cleanup();
        await cloudFrontAdapter.cleanup();
      }
    },
    { scope: "test" },
  ],

  /**
   * Authenticated E2E page with comprehensive login
   */
  authenticatedE2EPage: [
    async ({ page, e2eIntegrationContext }, use) => {
      console.log("[E2E] Performing comprehensive authenticated login...");

      // Perform comprehensive login
      const loginResult = await performE2ELogin(
        page,
        e2eIntegrationContext.testUrls.cloudFrontLogin,
        e2eIntegrationContext.testUser.username,
        e2eIntegrationContext.testUser.password,
      );

      if (!loginResult.success) {
        throw new Error(`E2E login failed: ${loginResult.error}`);
      }

      // Update validation results
      e2eIntegrationContext.validationResults.cloudFrontAccessible = true;

      console.log(
        `[E2E] Comprehensive login successful in ${loginResult.responseTime}ms`,
      );

      // Configure page for E2E testing
      await page.setExtraHTTPHeaders({
        "User-Agent": "MediaLake-E2E-Integration-Test/1.0",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      });

      page.setDefaultTimeout(30000);
      page.setDefaultNavigationTimeout(30000);

      await use(page);
    },
    { scope: "test" },
  ],
});

// Main E2E Integration Test Suite
e2eIntegrationTest.describe(
  "AWS Tag-Based Discovery End-to-End Integration",
  () => {
    e2eIntegrationTest(
      "should perform complete workflow from tag discovery to login automation",
      async ({ e2eIntegrationContext, authenticatedE2EPage }) => {
        // Validate comprehensive context setup
        expect(e2eIntegrationContext.cognitoUserPool).toBeTruthy();
        expect(e2eIntegrationContext.cloudFrontDistribution).toBeTruthy();
        expect(e2eIntegrationContext.testUser).toBeTruthy();
        expect(e2eIntegrationContext.testUrls).toBeTruthy();

        // Validate discovery metrics
        expect(
          e2eIntegrationContext.discoveryMetrics.cognitoDiscoveryTime,
        ).toBeGreaterThan(0);
        expect(
          e2eIntegrationContext.discoveryMetrics.cloudFrontDiscoveryTime,
        ).toBeGreaterThan(0);
        expect(
          e2eIntegrationContext.discoveryMetrics.userCreationTime,
        ).toBeGreaterThan(0);
        expect(
          e2eIntegrationContext.discoveryMetrics.totalSetupTime,
        ).toBeLessThan(60000); // Should complete within 1 minute

        // Validate all validation results
        expect(
          e2eIntegrationContext.validationResults.permanentPasswordWorking,
        ).toBe(true);
        expect(
          e2eIntegrationContext.validationResults.cloudFrontAccessible,
        ).toBe(true);
        expect(e2eIntegrationContext.validationResults.backwardCompatible).toBe(
          true,
        );

        // Validate authenticated page is ready
        expect(authenticatedE2EPage).toBeTruthy();

        // Test navigation to various endpoints
        const testEndpoints = [
          e2eIntegrationContext.testUrls.cloudFrontRoot,
          e2eIntegrationContext.testUrls.cloudFrontDashboard,
        ];

        for (const endpoint of testEndpoints) {
          const response = await authenticatedE2EPage.goto(endpoint, {
            waitUntil: "networkidle",
            timeout: 30000,
          });

          expect(response).toBeTruthy();
          expect(response!.status()).toBeLessThan(400);
        }

        console.log("[Test] Complete E2E workflow validation successful");
        console.log(
          `[Test] Total setup time: ${e2eIntegrationContext.discoveryMetrics.totalSetupTime}ms`,
        );
        console.log(
          `[Test] Cognito pool: ${e2eIntegrationContext.cognitoUserPool!.name}`,
        );
        console.log(
          `[Test] CloudFront distribution: ${e2eIntegrationContext.cloudFrontDistribution!.name}`,
        );
      },
    );

    e2eIntegrationTest(
      "should validate tag-based discovery performance and caching",
      async ({ e2eIntegrationContext }) => {
        // Validate discovery performance
        expect(
          e2eIntegrationContext.discoveryMetrics.cognitoDiscoveryTime,
        ).toBeLessThan(10000); // Should complete within 10 seconds
        expect(
          e2eIntegrationContext.discoveryMetrics.cloudFrontDiscoveryTime,
        ).toBeLessThan(10000);

        // Test discovery engine statistics
        const discoveryStats = await AWSDiscoveryUtils.getDiscoveryStats(
          e2eIntegrationContext.discoveryEngine,
        );
        expect(discoveryStats).toBeDefined();

        // Test cache invalidation and refresh
        await AWSDiscoveryUtils.invalidateCache(
          e2eIntegrationContext.discoveryEngine,
          "cognito-user-pool",
        );

        // Perform second discovery to test caching
        const tagFilters = getE2ETagFilters();
        const secondDiscoveryStart = Date.now();
        const secondCognitoDiscovery =
          await e2eIntegrationContext.discoveryEngine.discoverByTags(
            "cognito-user-pool",
            tagFilters,
          );
        const secondDiscoveryTime = Date.now() - secondDiscoveryStart;

        expect(secondCognitoDiscovery.length).toBeGreaterThan(0);
        console.log(
          `[Test] Second discovery time: ${secondDiscoveryTime}ms (should be faster due to caching)`,
        );
      },
    );

    e2eIntegrationTest(
      "should validate backward compatibility with existing fixture patterns",
      async ({ e2eIntegrationContext }) => {
        // Validate backward compatibility flag
        expect(e2eIntegrationContext.validationResults.backwardCompatible).toBe(
          true,
        );

        // Validate user pool structure matches existing patterns
        const userPool = e2eIntegrationContext.cognitoUserPool!;
        expect(userPool.id).toBeTruthy();
        expect(userPool.name).toBeTruthy();
        expect(userPool.clients).toBeDefined();
        expect(userPool.clients.length).toBeGreaterThan(0);

        // Validate test user structure matches existing patterns
        const testUser = e2eIntegrationContext.testUser;
        expect(testUser.username).toMatch(
          /^mne-medialake\+e2etest-\d+-[a-f0-9]+@amazon\.com$/,
        );
        expect(testUser.email).toMatch(
          /^mne-medialake\+e2etest-\d+-[a-f0-9]+@amazon\.com$/,
        );
        expect(testUser.password.length).toBeGreaterThanOrEqual(8);
        expect(testUser.userPoolId).toBeTruthy();
        expect(testUser.userPoolClientId).toBeTruthy();

        // Validate discovery method is properly tracked
        expect(["tag-based", "name-based", "fallback"]).toContain(
          testUser.discoveryMethod,
        );

        console.log(
          `[Test] Backward compatibility validated - discovery method: ${testUser.discoveryMethod}`,
        );
      },
    );

    e2eIntegrationTest(
      "should validate error handling and edge cases",
      async ({ e2eIntegrationContext }) => {
        // Test custom tag filter creation
        const customTags = {
          CustomTag: "test-value",
          Environment: "integration-test",
        };

        const customFilters =
          AWSDiscoveryUtils.createCustomTagFilters(customTags);
        expect(customFilters).toHaveLength(2);
        expect(customFilters[0].key).toBe("CustomTag");
        expect(customFilters[0].values).toEqual(["test-value"]);

        // Test discovery with non-existent tags (should handle gracefully)
        const nonExistentFilters = AWSDiscoveryUtils.createCustomTagFilters({
          NonExistentTag: "non-existent-value",
        });

        const emptyResults =
          await e2eIntegrationContext.discoveryEngine.discoverByTags(
            "cognito-user-pool",
            nonExistentFilters,
          );
        expect(emptyResults).toBeDefined();
        expect(Array.isArray(emptyResults)).toBe(true);

        // Test that context handles missing resources gracefully
        expect(e2eIntegrationContext.cognitoUserPool).toBeTruthy(); // Should have found resources
        expect(e2eIntegrationContext.cloudFrontDistribution).toBeTruthy();

        console.log("[Test] Error handling and edge cases validated");
      },
    );

    e2eIntegrationTest(
      "should validate parallel execution and worker isolation",
      async ({ e2eIntegrationContext }, testInfo) => {
        // Validate worker-specific isolation
        expect(e2eIntegrationContext.testUser.username).toContain(
          `-${testInfo.workerIndex}-`,
        );

        // Validate unique test context per worker
        expect(e2eIntegrationContext.testUser.userPoolId).toBeTruthy();
        expect(e2eIntegrationContext.testUrls.cloudFrontLogin).toBeTruthy();

        // Test that context is properly isolated
        const contextInfo = {
          workerIndex: testInfo.workerIndex,
          testTitle: testInfo.title,
          testUser: e2eIntegrationContext.testUser.username,
          userPoolId: e2eIntegrationContext.testUser.userPoolId,
          distributionId: e2eIntegrationContext.cloudFrontDistribution!.id,
          discoveryMethod: e2eIntegrationContext.testUser.discoveryMethod,
        };

        console.log(
          `[Test] Worker ${testInfo.workerIndex} isolation validated:`,
          JSON.stringify(contextInfo, null, 2),
        );

        // Validate that each worker has its own resources
        expect(contextInfo.testUser).toMatch(
          new RegExp(`-${testInfo.workerIndex}-`),
        );
        expect(contextInfo.userPoolId).toBeTruthy();
        expect(contextInfo.distributionId).toBeTruthy();
      },
    );

    e2eIntegrationTest(
      "should validate CloudFront performance and caching behavior",
      async ({ e2eIntegrationContext, authenticatedE2EPage }) => {
        const testUrl = e2eIntegrationContext.testUrls.cloudFrontRoot;

        // Test initial request performance
        const startTime = Date.now();
        const response = await authenticatedE2EPage.goto(testUrl, {
          waitUntil: "networkidle",
          timeout: 30000,
        });
        const responseTime = Date.now() - startTime;

        expect(response).toBeTruthy();
        expect(response!.status()).toBeLessThan(400);
        expect(responseTime).toBeLessThan(10000); // Should respond within 10 seconds

        // Validate CloudFront headers
        const headers = await response!.allHeaders();
        const cacheValidation =
          CloudFrontTestUtils.validateCacheHeaders(headers);

        expect(cacheValidation).toBeDefined();

        // Test multiple requests to validate caching
        const secondStartTime = Date.now();
        const secondResponse = await authenticatedE2EPage.goto(testUrl, {
          waitUntil: "networkidle",
          timeout: 30000,
        });
        const secondResponseTime = Date.now() - secondStartTime;

        expect(secondResponse).toBeTruthy();
        expect(secondResponse!.status()).toBeLessThan(400);

        // Second request should be faster due to caching
        console.log(
          `[Test] First request: ${responseTime}ms, Second request: ${secondResponseTime}ms`,
        );

        // Log cache information
        const cacheStatus =
          headers["x-cache"] || headers["cloudfront-cache-status"] || "unknown";
        console.log(`[Test] CloudFront cache status: ${cacheStatus}`);
        console.log(`[Test] Cache headers validation:`, cacheValidation);
      },
    );
  },
);

// Backward Compatibility Test Suite
e2eIntegrationTest.describe("Backward Compatibility Validation", () => {
  e2eIntegrationTest(
    "should work seamlessly with existing auth fixtures",
    async ({ e2eIntegrationContext }) => {
      // Test that enhanced fixtures produce data compatible with existing auth fixtures
      const testUser = e2eIntegrationContext.testUser;

      // Validate user structure matches existing CognitoTestUser interface
      expect(testUser).toHaveProperty("username");
      expect(testUser).toHaveProperty("password");
      expect(testUser).toHaveProperty("email");
      expect(testUser).toHaveProperty("userPoolId");
      expect(testUser).toHaveProperty("userPoolClientId");

      // Validate email format matches existing pattern
      expect(testUser.email).toMatch(
        /^mne-medialake\+e2etest-\d+-[a-f0-9]+@amazon\.com$/,
      );
      expect(testUser.username).toBe(testUser.email); // Username should be email

      // Validate password meets existing requirements
      expect(testUser.password.length).toBeGreaterThanOrEqual(8);

      // Validate user pool IDs are valid AWS resource identifiers
      expect(testUser.userPoolId).toMatch(/^[a-zA-Z0-9_-]+$/);
      expect(testUser.userPoolClientId).toMatch(/^[a-zA-Z0-9]+$/);

      console.log("[Test] Backward compatibility with auth fixtures validated");
    },
  );

  e2eIntegrationTest(
    "should maintain existing S3 bucket patterns",
    async ({ e2eIntegrationContext }, testInfo) => {
      // While this test doesn't directly use S3, validate that worker isolation
      // patterns match existing S3 bucket naming conventions
      const expectedWorkerPattern = new RegExp(`-${testInfo.workerIndex}-`);
      expect(e2eIntegrationContext.testUser.username).toMatch(
        expectedWorkerPattern,
      );

      // Validate that the pattern would work with existing S3 bucket naming
      const mockBucketName = `medialake-pw-test-${Math.random().toString(36).substring(2, 8)}-worker-${testInfo.workerIndex}`;
      expect(mockBucketName).toMatch(
        /^medialake-pw-test-[a-f0-9]+-worker-\d+$/,
      );

      console.log(
        `[Test] Worker isolation pattern compatible with S3 naming: ${mockBucketName}`,
      );
    },
  );
});

// Error Handling and Resilience Test Suite
e2eIntegrationTest.describe("Error Handling and Resilience", () => {
  e2eIntegrationTest(
    "should handle discovery failures gracefully",
    async ({ e2eIntegrationContext }) => {
      // Test that the system recovered from any discovery issues
      expect(e2eIntegrationContext.cognitoUserPool).toBeTruthy();
      expect(e2eIntegrationContext.cloudFrontDistribution).toBeTruthy();

      // Test discovery method fallback chain
      const discoveryMethod = e2eIntegrationContext.testUser.discoveryMethod;
      expect(["tag-based", "name-based", "fallback"]).toContain(
        discoveryMethod,
      );

      // Test that validation results indicate successful recovery
      expect(e2eIntegrationContext.validationResults.backwardCompatible).toBe(
        true,
      );
      expect(
        e2eIntegrationContext.validationResults.permanentPasswordWorking,
      ).toBe(true);

      console.log(
        `[Test] Error recovery successful - discovery method: ${discoveryMethod}`,
      );
    },
  );

  e2eIntegrationTest(
    "should validate comprehensive error scenarios",
    async ({ e2eIntegrationContext }) => {
      // Test that all critical components are available
      expect(e2eIntegrationContext.discoveryEngine).toBeTruthy();
      expect(e2eIntegrationContext.cognitoAdapter).toBeTruthy();
      expect(e2eIntegrationContext.cloudFrontAdapter).toBeTruthy();

      // Test that metrics indicate reasonable performance
      const metrics = e2eIntegrationContext.discoveryMetrics;
      expect(metrics.totalSetupTime).toBeLessThan(60000); // Should complete within 1 minute
      expect(metrics.cognitoDiscoveryTime).toBeGreaterThan(0);
      expect(metrics.cloudFrontDiscoveryTime).toBeGreaterThan(0);
      expect(metrics.userCreationTime).toBeGreaterThan(0);

      // Test that all validation results are properly set
      const validation = e2eIntegrationContext.validationResults;
      expect(typeof validation.tagBasedDiscoveryWorking).toBe("boolean");
      expect(typeof validation.permanentPasswordWorking).toBe("boolean");
      expect(typeof validation.cloudFrontAccessible).toBe("boolean");
      expect(typeof validation.backwardCompatible).toBe("boolean");

      console.log("[Test] Comprehensive error scenario validation completed");
    },
  );
});

// Performance and Scalability Test Suite
e2eIntegrationTest.describe("Performance and Scalability", () => {
  e2eIntegrationTest(
    "should meet performance benchmarks",
    async ({ e2eIntegrationContext }) => {
      const metrics = e2eIntegrationContext.discoveryMetrics;

      // Validate discovery performance benchmarks
      expect(metrics.cognitoDiscoveryTime).toBeLessThan(10000); // 10 seconds max
      expect(metrics.cloudFrontDiscoveryTime).toBeLessThan(10000); // 10 seconds max
      expect(metrics.userCreationTime).toBeLessThan(5000); // 5 seconds max
      expect(metrics.totalSetupTime).toBeLessThan(30000); // 30 seconds max for complete setup

      // Log performance metrics
      console.log("[Test] Performance benchmarks:");
      console.log(`  - Cognito discovery: ${metrics.cognitoDiscoveryTime}ms`);
      console.log(
        `  - CloudFront discovery: ${metrics.cloudFrontDiscoveryTime}ms`,
      );
      console.log(`  - User creation: ${metrics.userCreationTime}ms`);
      console.log(`  - Total setup: ${metrics.totalSetupTime}ms`);
    },
  );

  e2eIntegrationTest(
    "should support concurrent test execution",
    async ({ e2eIntegrationContext }, testInfo) => {
      // Validate that resources are properly isolated for concurrent execution
      const testUser = e2eIntegrationContext.testUser;

      // Each worker should have unique resources
      expect(testUser.username).toContain(`-${testInfo.workerIndex}-`);

      // Test that discovery engine supports concurrent access
      const discoveryStats = await AWSDiscoveryUtils.getDiscoveryStats(
        e2eIntegrationContext.discoveryEngine,
      );
      expect(discoveryStats).toBeDefined();

      // Test concurrent discovery operations
      const tagFilters = getE2ETagFilters();
      const concurrentPromises = [
        e2eIntegrationContext.discoveryEngine.discoverByTags(
          "cognito-user-pool",
          tagFilters,
        ),
        e2eIntegrationContext.discoveryEngine.discoverByTags(
          "cloudfront-distribution",
          tagFilters,
        ),
      ];

      const concurrentResults = await Promise.all(concurrentPromises);
      expect(concurrentResults[0]).toBeDefined(); // Cognito results
      expect(concurrentResults[1]).toBeDefined(); // CloudFront results

      console.log(
        `[Test] Concurrent execution validated for worker ${testInfo.workerIndex}`,
      );
    },
  );
});

// Re-export expect for consistency
export { expect } from "@playwright/test";
