/**
 * CloudFront Fixtures for Distribution Discovery and Testing
 * Provides tag-based CloudFront distribution discovery and testing capabilities
 * Integrates with the AWS resource discovery framework for comprehensive CDN testing
 */

import { test as base } from "@playwright/test";
import { Page } from "@playwright/test";
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

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";

// Types for CloudFront fixtures
export interface CloudFrontTestContext {
  distribution: CloudFrontDistribution;
  primaryDomain: string;
  testUrls: CloudFrontTestUrls;
  discoveryMethod: "tag-based" | "fallback";
}

export interface CloudFrontTestUrls {
  root: string;
  healthCheck: string;
  staticAsset: string;
  apiProxy?: string;
}

export interface CloudFrontFixtures {
  cloudFrontContext: CloudFrontTestContext;
  cloudFrontDiscoveryEngine: ResourceDiscoveryEngine;
  cloudFrontServiceAdapter: CloudFrontServiceAdapter;
  cloudFrontTestPage: Page;
}

export interface CloudFrontTestResult {
  url: string;
  status: number;
  responseTime: number;
  headers: Record<string, string>;
  cacheStatus?: string;
  success: boolean;
  error?: string;
}

/**
 * Create discovery configuration for CloudFront resources
 */
function createCloudFrontDiscoveryConfig(): ResourceDiscoveryConfig {
  return {
    region: AWS_REGION,
    profile: AWS_PROFILE,
    cacheTtlMs: 600000, // 10 minutes for CloudFront (slower to change)
    maxCacheSize: 50,
    enableFallback: true,
  };
}

/**
 * Get standard tag filters for CloudFront distribution discovery
 */
function getCloudFrontTagFilters(): TagFilter[] {
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
 * Discover CloudFront distribution using tag-based approach with fallback
 */
async function discoverCloudFrontDistribution(
  discoveryEngine: ResourceDiscoveryEngine,
  serviceAdapter: CloudFrontServiceAdapter,
): Promise<{
  distribution: CloudFrontDistribution | null;
  method: "tag-based" | "fallback";
}> {
  const tagFilters = getCloudFrontTagFilters();

  try {
    // Primary: Tag-based discovery
    console.log("[CloudFront] Attempting tag-based distribution discovery...");
    const tagBasedDistributions = await discoveryEngine.discoverByTags(
      "cloudfront-distribution",
      tagFilters,
    );

    if (tagBasedDistributions.length > 0) {
      const distribution = tagBasedDistributions[0] as CloudFrontDistribution;
      console.log(
        `[CloudFront] Found distribution via tags: ${distribution.name} (${distribution.id})`,
      );
      return { distribution, method: "tag-based" };
    }

    console.warn(
      "[CloudFront] No distributions found via tag-based discovery, trying fallback...",
    );
  } catch (error) {
    console.warn("[CloudFront] Tag-based discovery failed:", error);
  }

  try {
    // Fallback: Service adapter fallback discovery
    console.log("[CloudFront] Using service adapter fallback discovery...");
    const fallbackDistributions =
      await serviceAdapter.fallbackDiscovery(tagFilters);

    if (fallbackDistributions.length > 0) {
      const distribution = fallbackDistributions[0];
      console.log(
        `[CloudFront] Found distribution via fallback: ${distribution.name} (${distribution.id})`,
      );
      return { distribution, method: "fallback" };
    }
  } catch (error) {
    console.warn("[CloudFront] Service adapter fallback failed:", error);
  }

  console.error("[CloudFront] All discovery methods failed");
  return { distribution: null, method: "fallback" };
}

/**
 * Generate test URLs for CloudFront distribution
 */
function generateTestUrls(
  distribution: CloudFrontDistribution,
): CloudFrontTestUrls {
  const primaryDomain =
    distribution.aliases.length > 0
      ? distribution.aliases[0]
      : distribution.domainName;

  const baseUrl = `https://${primaryDomain}`;

  return {
    root: baseUrl,
    healthCheck: `${baseUrl}/health`,
    staticAsset: `${baseUrl}/favicon.ico`,
    apiProxy: `${baseUrl}/api/health`,
  };
}

/**
 * Test CloudFront distribution accessibility and performance
 */
async function testDistributionAccess(
  page: Page,
  testUrls: CloudFrontTestUrls,
): Promise<CloudFrontTestResult[]> {
  const results: CloudFrontTestResult[] = [];

  const urlsToTest = [
    { name: "root", url: testUrls.root },
    { name: "healthCheck", url: testUrls.healthCheck },
    { name: "staticAsset", url: testUrls.staticAsset },
  ];

  if (testUrls.apiProxy) {
    urlsToTest.push({ name: "apiProxy", url: testUrls.apiProxy });
  }

  for (const { name, url } of urlsToTest) {
    console.log(`[CloudFront] Testing ${name}: ${url}`);

    const startTime = Date.now();
    let result: CloudFrontTestResult;

    try {
      const response = await page.goto(url, {
        waitUntil: "networkidle",
        timeout: 30000,
      });

      const responseTime = Date.now() - startTime;
      const headers = (await response?.allHeaders()) || {};

      result = {
        url,
        status: response?.status() || 0,
        responseTime,
        headers,
        cacheStatus: headers["x-cache"] || headers["cloudfront-cache-status"],
        success: (response?.status() || 0) < 400,
      };

      console.log(
        `[CloudFront] ${name} test result: ${result.status} (${result.responseTime}ms)`,
      );
      if (result.cacheStatus) {
        console.log(`[CloudFront] Cache status: ${result.cacheStatus}`);
      }
    } catch (error: any) {
      const responseTime = Date.now() - startTime;

      result = {
        url,
        status: 0,
        responseTime,
        headers: {},
        success: false,
        error: error.message,
      };

      console.warn(`[CloudFront] ${name} test failed: ${error.message}`);
    }

    results.push(result);
  }

  return results;
}

/**
 * Wait for CloudFront distribution to be ready for testing
 */
async function waitForDistributionReady(
  serviceAdapter: CloudFrontServiceAdapter,
  distributionId: string,
  maxWaitTime: number = 300000, // 5 minutes
): Promise<boolean> {
  const startTime = Date.now();

  console.log(
    `[CloudFront] Waiting for distribution ${distributionId} to be ready...`,
  );

  while (Date.now() - startTime < maxWaitTime) {
    try {
      const isReady = await serviceAdapter.isDistributionReady(distributionId);

      if (isReady) {
        console.log(`[CloudFront] Distribution ${distributionId} is ready`);
        return true;
      }

      console.log(
        `[CloudFront] Distribution ${distributionId} not ready, waiting...`,
      );
      await new Promise((resolve) => setTimeout(resolve, 10000)); // Wait 10 seconds
    } catch (error) {
      console.warn(
        `[CloudFront] Error checking distribution readiness:`,
        error,
      );
      await new Promise((resolve) => setTimeout(resolve, 10000));
    }
  }

  console.warn(
    `[CloudFront] Distribution ${distributionId} not ready after ${maxWaitTime}ms`,
  );
  return false;
}

/**
 * Create cache invalidation for testing
 */
async function createTestInvalidation(
  serviceAdapter: CloudFrontServiceAdapter,
  distributionId: string,
  paths: string[] = ["/*"],
): Promise<string | null> {
  try {
    console.log(
      `[CloudFront] Creating invalidation for distribution ${distributionId}`,
    );
    const invalidationId = await serviceAdapter.createInvalidation(
      distributionId,
      paths,
    );

    console.log(`[CloudFront] Invalidation created: ${invalidationId}`);
    return invalidationId;
  } catch (error) {
    console.warn(`[CloudFront] Failed to create invalidation:`, error);
    return null;
  }
}

// Extend the base Playwright test fixture with CloudFront capabilities
export const test = base.extend<CloudFrontFixtures>({
  /**
   * CloudFront discovery engine fixture - test scoped
   */
  cloudFrontDiscoveryEngine: async ({}, use, testInfo) => {
    const config = createCloudFrontDiscoveryConfig();
    const engine = createResourceDiscoveryEngine(config, testInfo.workerIndex);

    console.log(
      `[CloudFront Worker ${testInfo.workerIndex}] Initializing discovery engine`,
    );

    // Register CloudFront service adapter
    const cloudFrontAdapter = createCloudFrontServiceAdapter(config);
    engine.registerAdapter(cloudFrontAdapter);

    // Prefetch CloudFront resources
    try {
      const cloudFrontFilters = getCloudFrontTagFilters();
      await engine.prefetchResources(cloudFrontFilters);
    } catch (error) {
      console.warn(
        `[CloudFront Worker ${testInfo.workerIndex}] Prefetch failed:`,
        error,
      );
    }

    await use(engine);

    // Cleanup
    await engine.cleanup();
  },

  /**
   * CloudFront service adapter fixture
   */
  cloudFrontServiceAdapter: async ({}, use) => {
    const config = createCloudFrontDiscoveryConfig();
    const adapter = createCloudFrontServiceAdapter(config);

    await use(adapter);

    await adapter.cleanup();
  },

  /**
   * CloudFront test context with discovered distribution
   */
  cloudFrontContext: [
    async (
      { cloudFrontDiscoveryEngine, cloudFrontServiceAdapter },
      use,
      testInfo,
    ) => {
      console.log(
        `[CloudFront Test ${testInfo.title}] Setting up CloudFront context`,
      );

      let distribution: CloudFrontDistribution | null = null;
      let discoveryMethod: "tag-based" | "fallback" = "fallback";

      try {
        // Discover CloudFront distribution
        const discoveryResult = await discoverCloudFrontDistribution(
          cloudFrontDiscoveryEngine,
          cloudFrontServiceAdapter,
        );

        distribution = discoveryResult.distribution;
        discoveryMethod = discoveryResult.method;

        if (!distribution) {
          throw new Error("No CloudFront distribution could be discovered");
        }

        // Wait for distribution to be ready
        const isReady = await waitForDistributionReady(
          cloudFrontServiceAdapter,
          distribution.id,
        );

        if (!isReady) {
          console.warn(
            `[CloudFront] Distribution ${distribution.id} may not be fully ready`,
          );
        }

        // Generate test URLs
        const testUrls = generateTestUrls(distribution);
        const primaryDomain =
          distribution.aliases.length > 0
            ? distribution.aliases[0]
            : distribution.domainName;

        const context: CloudFrontTestContext = {
          distribution,
          primaryDomain,
          testUrls,
          discoveryMethod,
        };

        console.log(
          `[CloudFront] Context ready for distribution: ${distribution.name} (${discoveryMethod})`,
        );
        console.log(`[CloudFront] Primary domain: ${primaryDomain}`);

        await use(context);
      } catch (error) {
        console.error(
          `[CloudFront] Error setting up CloudFront context:`,
          error,
        );
        throw error;
      }

      console.log(
        `[CloudFront Test ${testInfo.title}] CloudFront context cleanup completed`,
      );
    },
    { scope: "test" },
  ],

  /**
   * CloudFront test page with enhanced capabilities
   */
  cloudFrontTestPage: [
    async ({ page, cloudFrontContext }, use) => {
      // Configure page for CloudFront testing
      await page.setExtraHTTPHeaders({
        "User-Agent": "MediaLake-E2E-Test/1.0",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      });

      // Set longer timeout for CloudFront responses
      page.setDefaultTimeout(30000);
      page.setDefaultNavigationTimeout(30000);

      // Add request/response logging for debugging
      page.on("request", (request) => {
        if (request.url().includes(cloudFrontContext.primaryDomain)) {
          console.log(
            `[CloudFront] Request: ${request.method()} ${request.url()}`,
          );
        }
      });

      page.on("response", (response) => {
        if (response.url().includes(cloudFrontContext.primaryDomain)) {
          const cacheStatus =
            response.headers()["x-cache"] ||
            response.headers()["cloudfront-cache-status"];
          console.log(
            `[CloudFront] Response: ${response.status()} ${response.url()} ${cacheStatus ? `(${cacheStatus})` : ""}`,
          );
        }
      });

      await use(page);
    },
    { scope: "test" },
  ],
});

// Re-export expect from the base playwright test module
export { expect } from "@playwright/test";

/**
 * Utility functions for CloudFront testing
 */
export const CloudFrontTestUtils = {
  /**
   * Test distribution accessibility and performance
   */
  async testDistributionAccess(
    page: Page,
    testUrls: CloudFrontTestUrls,
  ): Promise<CloudFrontTestResult[]> {
    return await testDistributionAccess(page, testUrls);
  },

  /**
   * Create cache invalidation for testing
   */
  async createTestInvalidation(
    serviceAdapter: CloudFrontServiceAdapter,
    distributionId: string,
    paths: string[] = ["/*"],
  ): Promise<string | null> {
    return await createTestInvalidation(serviceAdapter, distributionId, paths);
  },

  /**
   * Wait for invalidation to complete
   */
  async waitForInvalidation(
    serviceAdapter: CloudFrontServiceAdapter,
    distributionId: string,
    invalidationId: string,
  ): Promise<void> {
    await serviceAdapter.waitForInvalidation(distributionId, invalidationId);
  },

  /**
   * Validate cache headers
   */
  validateCacheHeaders(headers: Record<string, string>): {
    hasCacheHeaders: boolean;
    cacheStatus?: string;
    maxAge?: number;
    etag?: string;
  } {
    const cacheStatus =
      headers["x-cache"] || headers["cloudfront-cache-status"];
    const cacheControl = headers["cache-control"];
    const etag = headers["etag"];

    let maxAge: number | undefined;
    if (cacheControl) {
      const maxAgeMatch = cacheControl.match(/max-age=(\d+)/);
      if (maxAgeMatch) {
        maxAge = parseInt(maxAgeMatch[1], 10);
      }
    }

    return {
      hasCacheHeaders: !!(cacheStatus || cacheControl || etag),
      cacheStatus,
      maxAge,
      etag,
    };
  },

  /**
   * Get distribution information for debugging
   */
  getDistributionInfo(context: CloudFrontTestContext): any {
    return {
      id: context.distribution.id,
      name: context.distribution.name,
      primaryDomain: context.primaryDomain,
      aliases: context.distribution.aliases,
      status: context.distribution.status,
      discoveryMethod: context.discoveryMethod,
      testUrls: context.testUrls,
    };
  },

  /**
   * Create custom tag filters for specific test scenarios
   */
  createCustomTagFilters(customTags: Record<string, string>): TagFilter[] {
    return Object.entries(customTags).map(([key, value]) => ({
      key,
      values: [value],
      operator: "equals" as const,
    }));
  },
};
