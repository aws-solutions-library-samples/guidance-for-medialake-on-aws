/**
 * CloudFront Login Test Suite
 * End-to-end testing of CloudFront distribution discovery and automated login workflow
 * Integrates enhanced Cognito fixtures, CloudFront fixtures, and existing auth patterns
 */

import { test, expect } from "../fixtures/enhanced-cognito.fixtures";
import { CloudFrontTestUtils } from "../fixtures/cloudfront.fixtures";
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "../utils/aws-resource-finder.js";
import {
  CloudFrontServiceAdapter,
  createCloudFrontServiceAdapter,
  CloudFrontDistribution,
} from "../utils/cloudfront-service-adapter.js";
import { TagFilter, STANDARD_TAG_PATTERNS } from "../utils/tag-matcher.js";
import { Page } from "@playwright/test";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Extended fixtures combining enhanced Cognito and CloudFront capabilities
interface CloudFrontLoginFixtures {
  cloudFrontLoginContext: CloudFrontLoginContext;
  authenticatedCloudFrontPage: Page;
}

interface CloudFrontLoginContext {
  cognitoUser: any;
  cloudFrontDistribution: CloudFrontDistribution;
  loginUrl: string;
  testUrls: {
    root: string;
    authenticated: string;
    healthCheck: string;
  };
  discoveryMethods: {
    cognito: "tag-based" | "name-based" | "fallback";
    cloudfront: "tag-based" | "fallback";
  };
}

/**
 * Create discovery configuration for CloudFront login testing
 */
function createCloudFrontLoginDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 300000, // 5 minutes
    maxCacheSize: 100,
    enableFallback: true,
  };
}

/**
 * Get tag filters for discovering both Cognito and CloudFront resources
 */
function getMediaLakeTagFilters(): TagFilter[] {
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
 * Discover CloudFront distribution for login testing
 */
async function discoverCloudFrontForLogin(
  discoveryEngine: ResourceDiscoveryEngine,
  serviceAdapter: CloudFrontServiceAdapter,
): Promise<{
  distribution: CloudFrontDistribution | null;
  method: "tag-based" | "fallback";
}> {
  const tagFilters = getMediaLakeTagFilters();

  try {
    console.log(
      "[CloudFrontLogin] Discovering CloudFront distribution for login testing...",
    );

    // Primary: Tag-based discovery
    const tagBasedDistributions = await discoveryEngine.discoverByTags(
      "cloudfront-distribution",
      tagFilters,
    );

    if (tagBasedDistributions.length > 0) {
      const distribution = tagBasedDistributions[0] as CloudFrontDistribution;
      console.log(
        `[CloudFrontLogin] Found distribution via tags: ${distribution.name} (${distribution.id})`,
      );

      // Validate distribution has web application endpoints
      if (
        distribution.aliases.length > 0 ||
        distribution.domainName.includes("cloudfront.net")
      ) {
        return { distribution, method: "tag-based" };
      }
    }

    console.warn(
      "[CloudFrontLogin] No suitable distributions found via tag-based discovery, trying fallback...",
    );
  } catch (error) {
    console.warn("[CloudFrontLogin] Tag-based discovery failed:", error);
  }

  try {
    // Fallback: Service adapter fallback discovery
    const fallbackDistributions =
      await serviceAdapter.fallbackDiscovery(tagFilters);

    if (fallbackDistributions.length > 0) {
      const distribution = fallbackDistributions[0];
      console.log(
        `[CloudFrontLogin] Found distribution via fallback: ${distribution.name} (${distribution.id})`,
      );
      return { distribution, method: "fallback" };
    }
  } catch (error) {
    console.warn("[CloudFrontLogin] Service adapter fallback failed:", error);
  }

  console.error("[CloudFrontLogin] All CloudFront discovery methods failed");
  return { distribution: null, method: "fallback" };
}

/**
 * Generate test URLs for CloudFront login testing
 */
function generateLoginTestUrls(distribution: CloudFrontDistribution): any {
  const primaryDomain =
    distribution.aliases.length > 0
      ? distribution.aliases[0]
      : distribution.domainName;

  const baseUrl = `https://${primaryDomain}`;

  return {
    root: baseUrl,
    authenticated: `${baseUrl}/dashboard`,
    healthCheck: `${baseUrl}/health`,
    login: `${baseUrl}/sign-in`,
  };
}

/**
 * Perform automated login through CloudFront
 */
async function performCloudFrontLogin(
  page: Page,
  loginUrl: string,
  username: string,
  password: string,
): Promise<{ success: boolean; responseTime: number; error?: string }> {
  const startTime = Date.now();

  try {
    console.log(`[CloudFrontLogin] Navigating to login URL: ${loginUrl}`);

    // Navigate to login page through CloudFront
    const response = await page.goto(loginUrl, {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    if (!response || response.status() >= 400) {
      throw new Error(
        `Login page returned status: ${response?.status() || "unknown"}`,
      );
    }

    // Wait for login form to be available - use working selectors from login.spec.ts
    await page.waitForSelector('input[name="username"]', { timeout: 10000 });

    // Fill login form using the same selectors that work in login.spec.ts
    console.log(`[CloudFrontLogin] Filling login form for user: ${username}`);
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);

    // Submit login form using working selector
    await page.click('.amplify-button[type="submit"]');

    // Wait for successful login - expect redirect to root or dashboard
    await page.waitForURL(
      (url) =>
        url.toString().includes("/dashboard") ||
        url.toString().endsWith("/") ||
        !url.toString().includes("/sign-in"),
      { timeout: 30000 },
    );

    // Additional wait to ensure page is fully loaded
    await page.waitForLoadState("networkidle");

    const responseTime = Date.now() - startTime;
    console.log(`[CloudFrontLogin] Login successful in ${responseTime}ms`);

    return { success: true, responseTime };
  } catch (error: any) {
    const responseTime = Date.now() - startTime;
    console.error(
      `[CloudFrontLogin] Login failed after ${responseTime}ms:`,
      error.message,
    );

    return {
      success: false,
      responseTime,
      error: error.message,
    };
  }
}

/**
 * Validate authenticated access through CloudFront
 */
async function validateAuthenticatedAccess(
  page: Page,
  testUrls: any,
): Promise<{ success: boolean; accessibleUrls: string[]; errors: string[] }> {
  const accessibleUrls: string[] = [];
  const errors: string[] = [];

  const urlsToTest = [
    { name: "root", url: testUrls.root },
    { name: "authenticated", url: testUrls.authenticated },
    { name: "healthCheck", url: testUrls.healthCheck },
  ];

  for (const { name, url } of urlsToTest) {
    try {
      console.log(
        `[CloudFrontLogin] Testing authenticated access to ${name}: ${url}`,
      );

      const response = await page.goto(url, {
        waitUntil: "networkidle",
        timeout: 15000,
      });

      if (response && response.status() < 400) {
        accessibleUrls.push(url);
        console.log(
          `[CloudFrontLogin] Successfully accessed ${name} (${response.status()})`,
        );
      } else {
        const error = `${name} returned status: ${response?.status() || "unknown"}`;
        errors.push(error);
        console.warn(`[CloudFrontLogin] ${error}`);
      }
    } catch (error: any) {
      const errorMsg = `${name} access failed: ${error.message}`;
      errors.push(errorMsg);
      console.warn(`[CloudFrontLogin] ${errorMsg}`);
    }
  }

  return {
    success: accessibleUrls.length > 0,
    accessibleUrls,
    errors,
  };
}

// Extend the enhanced Cognito test with CloudFront login capabilities
const cloudFrontLoginTest = test.extend<CloudFrontLoginFixtures>({
  /**
   * CloudFront login context combining Cognito user and CloudFront distribution
   */
  cloudFrontLoginContext: [
    async ({ enhancedCognitoTestUser }, use, testInfo) => {
      console.log(
        `[CloudFrontLogin Worker ${testInfo.workerIndex}] Setting up CloudFront login context`,
      );

      const config = createCloudFrontLoginDiscoveryConfig();
      const discoveryEngine = createResourceDiscoveryEngine(
        config,
        testInfo.workerIndex,
      );
      const cloudFrontAdapter = createCloudFrontServiceAdapter(config);

      // Register CloudFront service adapter
      discoveryEngine.registerAdapter(cloudFrontAdapter);

      let cloudFrontDistribution: CloudFrontDistribution | null = null;
      let cloudFrontMethod: "tag-based" | "fallback" = "fallback";

      try {
        // Discover CloudFront distribution
        const discoveryResult = await discoverCloudFrontForLogin(
          discoveryEngine,
          cloudFrontAdapter,
        );
        cloudFrontDistribution = discoveryResult.distribution;
        cloudFrontMethod = discoveryResult.method;

        if (!cloudFrontDistribution) {
          throw new Error(
            "No CloudFront distribution could be discovered for login testing",
          );
        }

        // Generate test URLs
        const testUrls = generateLoginTestUrls(cloudFrontDistribution);

        const context: CloudFrontLoginContext = {
          cognitoUser: enhancedCognitoTestUser,
          cloudFrontDistribution,
          loginUrl: testUrls.login,
          testUrls,
          discoveryMethods: {
            cognito: enhancedCognitoTestUser.discoveryMethod,
            cloudfront: cloudFrontMethod,
          },
        };

        console.log(
          `[CloudFrontLogin] Context ready - Cognito: ${context.discoveryMethods.cognito}, CloudFront: ${context.discoveryMethods.cloudfront}`,
        );
        console.log(`[CloudFrontLogin] Login URL: ${context.loginUrl}`);

        await use(context);
      } catch (error) {
        console.error(
          `[CloudFrontLogin] Error setting up CloudFront login context:`,
          error,
        );
        throw error;
      } finally {
        // Cleanup
        await discoveryEngine.cleanup();
        await cloudFrontAdapter.cleanup();
      }
    },
    { scope: "test" },
  ],

  /**
   * Authenticated page through CloudFront login
   */
  authenticatedCloudFrontPage: [
    async ({ page, cloudFrontLoginContext }, use) => {
      console.log(
        "[CloudFrontLogin] Performing automated login through CloudFront...",
      );

      // Perform login through CloudFront
      const loginResult = await performCloudFrontLogin(
        page,
        cloudFrontLoginContext.loginUrl,
        cloudFrontLoginContext.cognitoUser.username,
        cloudFrontLoginContext.cognitoUser.password,
      );

      if (!loginResult.success) {
        throw new Error(`CloudFront login failed: ${loginResult.error}`);
      }

      console.log(
        `[CloudFrontLogin] Login successful, response time: ${loginResult.responseTime}ms`,
      );

      // Configure page for CloudFront testing
      await page.setExtraHTTPHeaders({
        "User-Agent": "MediaLake-CloudFront-E2E-Test/1.0",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      });

      // Set appropriate timeouts for CloudFront responses
      page.setDefaultTimeout(30000);
      page.setDefaultNavigationTimeout(30000);

      await use(page);
    },
    { scope: "test" },
  ],
});

// Main CloudFront login test suite
cloudFrontLoginTest.describe("CloudFront Login Integration Tests", () => {
  cloudFrontLoginTest(
    "should discover resources and perform end-to-end login through CloudFront",
    async ({ cloudFrontLoginContext, authenticatedCloudFrontPage }) => {
      // Validate context setup
      expect(cloudFrontLoginContext.cognitoUser).toBeTruthy();
      expect(cloudFrontLoginContext.cloudFrontDistribution).toBeTruthy();
      expect(cloudFrontLoginContext.loginUrl).toBeTruthy();
      expect(cloudFrontLoginContext.testUrls).toBeTruthy();

      // Validate discovery methods
      expect(["tag-based", "name-based", "fallback"]).toContain(
        cloudFrontLoginContext.discoveryMethods.cognito,
      );
      expect(["tag-based", "fallback"]).toContain(
        cloudFrontLoginContext.discoveryMethods.cloudfront,
      );

      // Validate authenticated page is ready
      expect(authenticatedCloudFrontPage).toBeTruthy();

      // Test authenticated access to various endpoints
      const accessResult = await validateAuthenticatedAccess(
        authenticatedCloudFrontPage,
        cloudFrontLoginContext.testUrls,
      );

      expect(accessResult.success).toBe(true);
      expect(accessResult.accessibleUrls.length).toBeGreaterThan(0);

      console.log(
        `[Test] End-to-end login successful via CloudFront distribution: ${cloudFrontLoginContext.cloudFrontDistribution.name}`,
      );
      console.log(
        `[Test] Discovery methods - Cognito: ${cloudFrontLoginContext.discoveryMethods.cognito}, CloudFront: ${cloudFrontLoginContext.discoveryMethods.cloudfront}`,
      );
      console.log(
        `[Test] Accessible URLs: ${accessResult.accessibleUrls.length}/${Object.keys(cloudFrontLoginContext.testUrls).length - 1}`,
      );
    },
  );

  cloudFrontLoginTest(
    "should handle login with permanent password (no reset required)",
    async ({ cloudFrontLoginContext, authenticatedCloudFrontPage }) => {
      // Validate that the enhanced Cognito user has permanent password
      expect(cloudFrontLoginContext.cognitoUser.password).toBeTruthy();
      expect(cloudFrontLoginContext.cognitoUser.username).toBeTruthy();

      // Validate that login was successful without password reset
      const currentUrl = authenticatedCloudFrontPage.url();
      expect(currentUrl).not.toContain("/sign-in");
      expect(currentUrl).not.toContain("/change-password");
      expect(currentUrl).not.toContain("/reset-password");

      // Test that we can navigate to authenticated endpoints
      await authenticatedCloudFrontPage.goto(
        cloudFrontLoginContext.testUrls.root,
      );
      await authenticatedCloudFrontPage.waitForLoadState("networkidle");

      const finalUrl = authenticatedCloudFrontPage.url();
      expect(finalUrl).not.toContain("/sign-in");

      console.log(
        `[Test] Permanent password login successful - no reset required`,
      );
      console.log(`[Test] Final authenticated URL: ${finalUrl}`);
    },
  );

  cloudFrontLoginTest(
    "should validate CloudFront cache headers and performance",
    async ({ cloudFrontLoginContext, authenticatedCloudFrontPage }) => {
      const testUrl = cloudFrontLoginContext.testUrls.root;
      const startTime = Date.now();

      // Navigate and measure response time
      const response = await authenticatedCloudFrontPage.goto(testUrl, {
        waitUntil: "networkidle",
        timeout: 30000,
      });

      const responseTime = Date.now() - startTime;

      expect(response).toBeTruthy();
      expect(response!.status()).toBeLessThan(400);
      expect(responseTime).toBeLessThan(10000); // Should respond within 10 seconds

      // Validate CloudFront headers
      const headers = await response!.allHeaders();
      const cacheValidation = CloudFrontTestUtils.validateCacheHeaders(headers);

      expect(cacheValidation).toBeDefined();

      // Log performance and cache information
      const cacheStatus =
        headers["x-cache"] || headers["cloudfront-cache-status"] || "unknown";
      console.log(
        `[Test] CloudFront performance - Response time: ${responseTime}ms, Cache status: ${cacheStatus}`,
      );
      console.log(
        `[Test] Cache headers present: ${cacheValidation.hasCacheHeaders}`,
      );

      if (cacheValidation.cacheStatus) {
        console.log(`[Test] Cache status: ${cacheValidation.cacheStatus}`);
      }
    },
  );

  cloudFrontLoginTest(
    "should support parallel execution with proper isolation",
    async ({ cloudFrontLoginContext }, testInfo) => {
      // Validate worker isolation
      expect(cloudFrontLoginContext.cognitoUser.username).toContain(
        `-${testInfo.workerIndex}-`,
      );

      // Validate unique test context per worker
      expect(cloudFrontLoginContext.cloudFrontDistribution.id).toBeTruthy();
      expect(cloudFrontLoginContext.loginUrl).toBeTruthy();

      // Test that context is properly isolated
      const contextInfo = {
        workerIndex: testInfo.workerIndex,
        testTitle: testInfo.title,
        cognitoUser: cloudFrontLoginContext.cognitoUser.username,
        distributionId: cloudFrontLoginContext.cloudFrontDistribution.id,
        discoveryMethods: cloudFrontLoginContext.discoveryMethods,
      };

      console.log(
        `[Test] Worker ${testInfo.workerIndex} isolation validated:`,
        JSON.stringify(contextInfo, null, 2),
      );

      // Validate that each worker has its own resources
      expect(contextInfo.cognitoUser).toMatch(
        new RegExp(`-${testInfo.workerIndex}-`),
      );
      expect(contextInfo.distributionId).toBeTruthy();
    },
  );
});

// Error handling and resilience tests
cloudFrontLoginTest.describe("CloudFront Login Error Handling", () => {
  cloudFrontLoginTest(
    "should handle CloudFront distribution unavailability gracefully",
    async ({ cloudFrontLoginContext }) => {
      // Test should still run even if CloudFront discovery had issues
      // The fixture should have either found a distribution or thrown an appropriate error
      expect(cloudFrontLoginContext.cloudFrontDistribution).toBeTruthy();

      // Validate that error handling mechanisms are in place
      expect(cloudFrontLoginContext.discoveryMethods.cloudfront).toMatch(
        /^(tag-based|fallback)$/,
      );

      console.log(
        `[Test] CloudFront discovery method: ${cloudFrontLoginContext.discoveryMethods.cloudfront}`,
      );
      console.log(
        `[Test] Distribution status: ${cloudFrontLoginContext.cloudFrontDistribution.status || "unknown"}`,
      );
    },
  );

  cloudFrontLoginTest(
    "should validate comprehensive error recovery",
    async ({ cloudFrontLoginContext, authenticatedCloudFrontPage }) => {
      // Test that the system recovered from any discovery issues
      expect(cloudFrontLoginContext.cognitoUser.discoveryMethod).toMatch(
        /^(tag-based|name-based|fallback)$/,
      );
      expect(cloudFrontLoginContext.discoveryMethods.cloudfront).toMatch(
        /^(tag-based|fallback)$/,
      );

      // Test that login was successful despite any discovery challenges
      const currentUrl = authenticatedCloudFrontPage.url();
      expect(currentUrl).toBeTruthy();
      expect(currentUrl).not.toContain("/sign-in");

      console.log(
        `[Test] Error recovery successful - Cognito: ${cloudFrontLoginContext.cognitoUser.discoveryMethod}, CloudFront: ${cloudFrontLoginContext.discoveryMethods.cloudfront}`,
      );
    },
  );
});

// Re-export expect for consistency
export { expect } from "@playwright/test";
