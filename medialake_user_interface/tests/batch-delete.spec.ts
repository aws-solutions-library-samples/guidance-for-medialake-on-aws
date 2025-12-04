import { test, expect } from "./fixtures/enhanced-cognito.fixtures";
import { Page } from "@playwright/test";
import * as path from "path";
import {
  ResourceDiscoveryEngine,
  createResourceDiscoveryEngine,
  ResourceDiscoveryConfig,
} from "./utils/aws-resource-finder.js";
import {
  CloudFrontServiceAdapter,
  createCloudFrontServiceAdapter,
  CloudFrontDistribution,
} from "./utils/cloudfront-service-adapter.js";
import { TagFilter, STANDARD_TAG_PATTERNS } from "./utils/tag-matcher.js";
import { uploadFilesFromDirectory, waitForUploadComplete } from "./utils/file-upload-helper.js";
import {
  checkConnectorsConfigured,
  verifyMinimumConnectors,
  createS3ConnectorWithNewBucket,
  navigateToConnectors,
  deleteConnector,
} from "./utils/connector-helper.js";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "dev3";
const ENVIRONMENT = process.env.MEDIALAKE_ENV || "dev";
const UPLOAD_FILES_DIR =
  process.env.UPLOAD_FILES_DIR || path.join(process.cwd(), "test-results", "batch-delete-files");

// Store connector info for cleanup
let testConnectorName: string | null = null;
let testConnectorWasCreated = false;

/**
 * Batch Delete Feature E2E Tests
 *
 * Tests the batch delete functionality using enhanced Cognito fixtures
 * and CloudFront URL discovery (testing against deployed app).
 *
 * Prerequisites:
 * - AWS credentials configured
 * - CloudFront distribution deployed
 * - Test user will be automatically created via enhanced Cognito fixtures
 *
 * To run:
 * npx playwright test tests/batch-delete.spec.ts --workers=1
 */

// Extended fixture for authenticated page through CloudFront
interface BatchDeleteFixtures {
  authenticatedBatchDeletePage: Page;
  cloudFrontUrl: string;
}

/**
 * Discover CloudFront distribution for testing
 */
async function discoverCloudFrontDistribution(
  discoveryEngine: ResourceDiscoveryEngine,
  serviceAdapter: CloudFrontServiceAdapter
): Promise<CloudFrontDistribution | null> {
  const tagFilters: TagFilter[] = [
    STANDARD_TAG_PATTERNS.APPLICATION_TAG,
    { key: "Environment", values: [ENVIRONMENT], operator: "equals" },
    STANDARD_TAG_PATTERNS.TESTING_TAG,
  ];

  try {
    console.log("[BatchDelete] Discovering CloudFront distribution...");
    const distributions = await discoveryEngine.discoverByTags(
      "cloudfront-distribution",
      tagFilters
    );

    if (distributions.length > 0) {
      const distribution = distributions[0] as CloudFrontDistribution;
      console.log(`[BatchDelete] Found distribution: ${distribution.name} (${distribution.id})`);
      return distribution;
    }

    console.warn("[BatchDelete] No distributions found via tags, trying fallback...");
    const fallbackDistributions = await serviceAdapter.fallbackDiscovery(tagFilters);

    if (fallbackDistributions.length > 0) {
      const distribution = fallbackDistributions[0];
      console.log(`[BatchDelete] Found distribution via fallback: ${distribution.name}`);
      return distribution;
    }
  } catch (error) {
    console.warn("[BatchDelete] CloudFront discovery failed:", error);
  }

  return null;
}

const batchDeleteTest = test.extend<BatchDeleteFixtures>({
  cloudFrontUrl: [
    async ({}, use, testInfo) => {
      const config: ResourceDiscoveryConfig = {
        region: AWS_REGION,
        profile: AWS_PROFILE,
        cacheTtlMs: 300000,
        maxCacheSize: 100,
        enableFallback: true,
      };

      const discoveryEngine = createResourceDiscoveryEngine(config, testInfo.workerIndex);
      const cloudFrontAdapter = createCloudFrontServiceAdapter(config);
      discoveryEngine.registerAdapter(cloudFrontAdapter);

      try {
        const distribution = await discoverCloudFrontDistribution(
          discoveryEngine,
          cloudFrontAdapter
        );

        if (!distribution) {
          throw new Error("Could not discover CloudFront distribution for testing");
        }

        const primaryDomain =
          distribution.aliases.length > 0 ? distribution.aliases[0] : distribution.domainName;

        const baseUrl = `https://${primaryDomain}`;
        console.log(`[BatchDelete] Using CloudFront URL: ${baseUrl}`);

        await use(baseUrl);
      } finally {
        await discoveryEngine.cleanup();
        await cloudFrontAdapter.cleanup();
      }
    },
    { scope: "test" },
  ],

  authenticatedBatchDeletePage: [
    async ({ page, enhancedCognitoTestUser, cloudFrontUrl }, use) => {
      console.log("[BatchDelete] Performing login with enhanced Cognito user...");
      console.log(`[BatchDelete] CloudFront URL: ${cloudFrontUrl}`);
      console.log(`[BatchDelete] User pool: ${enhancedCognitoTestUser.userPoolId}`);
      console.log(`[BatchDelete] User pool client: ${enhancedCognitoTestUser.userPoolClientId}`);

      // Navigate to login page through CloudFront
      const loginUrl = `${cloudFrontUrl}/sign-in`;
      console.log(`[BatchDelete] Navigating to: ${loginUrl}`);
      await page.goto(loginUrl, { waitUntil: "networkidle", timeout: 30000 });

      // Wait for login form - use working selectors
      await page.waitForSelector('input[name="username"]', { timeout: 10000 });

      // Fill login form
      console.log(`[BatchDelete] Filling login form for: ${enhancedCognitoTestUser.username}`);
      await page.fill('input[name="username"]', enhancedCognitoTestUser.username);
      await page.fill('input[name="password"]', enhancedCognitoTestUser.password);

      // Submit login form
      await page.click('.amplify-button[type="submit"]');

      // Wait for successful login - expect redirect to root or dashboard
      await page.waitForURL(
        (url) =>
          url.toString().includes("/dashboard") ||
          url.toString().endsWith("/") ||
          !url.toString().includes("/sign-in"),
        { timeout: 30000 }
      );

      // Additional wait to ensure page is fully loaded
      await page.waitForLoadState("networkidle");

      console.log("[BatchDelete] Login successful, page ready for testing");

      await use(page);
    },
    { scope: "test" },
  ],
});

batchDeleteTest.describe("Step 1: Upload UI Prerequisites", () => {
  batchDeleteTest(
    "should have upload button available",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl }) => {
      console.log("[Upload UI Check] Verifying upload functionality exists");

      // Navigate to root/dashboard page
      await authenticatedBatchDeletePage.goto(cloudFrontUrl, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });
      await authenticatedBatchDeletePage.waitForLoadState("domcontentloaded");
      await authenticatedBatchDeletePage.waitForTimeout(2000);

      // Check for upload button with CloudUploadIcon test ID
      const uploadButton = authenticatedBatchDeletePage.getByTestId("CloudUploadIcon");
      const uploadExists = (await uploadButton.count()) > 0;

      if (uploadExists) {
        console.log("[Upload UI Check] ✅ Upload button found");
        expect(uploadExists).toBe(true);
      } else {
        console.log("[Upload UI Check] ⚠️  Upload button not found");
        console.log("[Upload UI Check] Taking screenshot for debugging");
        await authenticatedBatchDeletePage.screenshot({
          path: "test-results/upload-button-missing.png",
          fullPage: true,
        });

        // Look for any upload-related elements
        const uploadElements = await authenticatedBatchDeletePage
          .locator('[data-testid*="upload"], [data-testid*="Upload"]')
          .count();
        console.log(`[Upload UI Check] Found ${uploadElements} upload-related elements`);

        expect(uploadExists).toBe(true);
      }
    }
  );
});

batchDeleteTest.describe("Step 2: Connector Prerequisites", () => {
  batchDeleteTest.setTimeout(90000); // Increase timeout to 90 seconds for connector creation

  batchDeleteTest(
    "should create a test connector for batch delete testing",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl, enhancedCognitoTestUser }, testInfo) => {
      console.log(
        "[Connector Setup] Creating test S3 connector with NEW bucket for batch delete tests..."
      );

      try {
        // Navigate to connectors page with retry logic
        let navigationSuccess = false;
        const maxRetries = 3;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
          try {
            console.log(`[Connector Setup] Navigation attempt ${attempt}/${maxRetries}`);
            await navigateToConnectors(authenticatedBatchDeletePage, cloudFrontUrl);
            navigationSuccess = true;
            console.log(`[Connector Setup] ✓ Successfully navigated to connectors page`);
            break;
          } catch (error: any) {
            console.warn(
              `[Connector Setup] ⚠️  Navigation attempt ${attempt} failed: ${error.message}`
            );
            if (attempt < maxRetries) {
              console.log(`[Connector Setup] Waiting 3s before retry...`);
              await authenticatedBatchDeletePage.waitForTimeout(3000);
            }
          }
        }

        if (!navigationSuccess) {
          throw new Error("Could not navigate to connectors page after 3 attempts");
        }

        // Create connector with new S3 bucket using helper
        const timestamp = Date.now();
        const createResult = await createS3ConnectorWithNewBucket(authenticatedBatchDeletePage, {
          connectorName: `batch-delete-test-${timestamp}`,
          bucketName: `medialake-test-${timestamp}`,
          description: "Auto-created connector for batch delete E2E testing",
        });

        if (createResult.success) {
          // Store connector name for cleanup
          testConnectorName = createResult.connectorName;
          testConnectorWasCreated = true;

          console.log(`[Connector Setup] ✅ Created test connector: ${createResult.connectorName}`);
          console.log(`[Connector Setup] ✅ Created new S3 bucket: ${createResult.bucketName}`);

          // Verify connector was created and is visible on the page
          console.log("[Connector Setup] Verifying connector is visible...");
          await authenticatedBatchDeletePage.waitForTimeout(5000);

          const verifyResult = await checkConnectorsConfigured(
            authenticatedBatchDeletePage,
            cloudFrontUrl,
            { minConnectors: 1 }
          );

          expect(verifyResult.success).toBe(true);
          expect(verifyResult.connectorCount).toBeGreaterThan(0);

          // CRITICAL: Verify the specific connector we created is visible
          const ourConnectorCard = authenticatedBatchDeletePage
            .locator('[data-testid^="connector-card-"]')
            .filter({
              has: authenticatedBatchDeletePage.locator(`h5:has-text("${testConnectorName}")`),
            });

          const ourConnectorVisible = await ourConnectorCard.count();
          console.log(`[Connector Setup] Our connector visible count: ${ourConnectorVisible}`);

          if (ourConnectorVisible === 0) {
            // Take screenshot for debugging
            await authenticatedBatchDeletePage.screenshot({
              path: "test-results/connector-not-found.png",
              fullPage: true,
            });
            throw new Error(
              `Created connector "${testConnectorName}" not found on connectors page`
            );
          }

          console.log(
            `[Connector Setup] ✅ Verified connector "${testConnectorName}" is visible and ready`
          );

          expect(testConnectorName).toBeTruthy();
          expect(testConnectorWasCreated).toBe(true);
          expect(ourConnectorVisible).toBe(1);
        } else {
          throw new Error("Failed to create test connector with new bucket");
        }
      } catch (error: any) {
        console.error("[Connector Setup] ❌ Failed to create connector:", error.message);
        throw new Error(`Connector setup failed: ${error.message}`);
      }
    }
  );
});

batchDeleteTest.describe("Step 3: File Upload for Batch Delete Testing", () => {
  batchDeleteTest.setTimeout(240000); // Increase timeout to 4 minutes for file upload

  batchDeleteTest(
    "should upload files from a directory using the UI upload modal",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl }) => {
      console.log("[Upload Test] Starting file upload test via modal");

      // Verify we have a test connector to use
      if (!testConnectorName) {
        throw new Error("No test connector available for upload - Step 2 may have failed");
      }

      console.log(`[Upload Test] Using test connector: ${testConnectorName}`);

      // Navigate to root/dashboard page
      await authenticatedBatchDeletePage.goto(cloudFrontUrl, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });
      await authenticatedBatchDeletePage.waitForLoadState("domcontentloaded");
      await authenticatedBatchDeletePage.waitForTimeout(2000);

      // Use directory from environment variable or default
      const uploadDir = UPLOAD_FILES_DIR;

      console.log(`[Upload Test] Using upload directory: ${uploadDir}`);
      console.log(`[Upload Test] (Set UPLOAD_FILES_DIR env var to use a different directory)`);

      // Upload all files from the directory using our test connector
      const uploadResult = await uploadFilesFromDirectory(
        authenticatedBatchDeletePage,
        uploadDir,
        testConnectorName, // Use the connector we created in Step 2
        { captureScreenshots: true, waitAfterUpload: 5000 }
      );

      if (uploadResult.success) {
        console.log("[Upload Test] ✅ File upload successful via modal");
        console.log(`[Upload Test] Method: ${uploadResult.method}`);
        console.log(`[Upload Test] Files uploaded: ${uploadResult.uploadedFiles.length} files`);
        uploadResult.uploadedFiles.forEach((file) => {
          console.log(`  - ${path.basename(file)}`);
        });

        // Wait for upload to complete and files to be processed
        await waitForUploadComplete(authenticatedBatchDeletePage);

        expect(uploadResult.uploadedFiles.length).toBeGreaterThan(0);
        expect(uploadResult.success).toBe(true);
      } else {
        console.log("[Upload Test] ⚠️  Upload failed or no files found in directory");
        console.log(`[Upload Test] Error: ${uploadResult.error}`);

        // The test should fail if upload doesn't work
        expect(uploadResult.success).toBe(true);
      }
    }
  );

  batchDeleteTest(
    "should search for uploaded files and wait for thumbnails to load",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl }) => {
      console.log("[Thumbnail Wait Test] Searching for uploaded files");

      // Navigate to search page with retry logic
      const searchUrl = `${cloudFrontUrl}/search?q=*&semantic=false`;
      console.log(`[Thumbnail Wait Test] Navigating to: ${searchUrl}`);

      let navigationSuccess = false;
      const maxNavRetries = 3;

      for (let attempt = 1; attempt <= maxNavRetries; attempt++) {
        try {
          console.log(`[Thumbnail Wait Test] Navigation attempt ${attempt}/${maxNavRetries}`);
          await authenticatedBatchDeletePage.goto(searchUrl, {
            waitUntil: "domcontentloaded",
            timeout: 30000,
          });
          await authenticatedBatchDeletePage.waitForLoadState("domcontentloaded");
          navigationSuccess = true;
          console.log(`[Thumbnail Wait Test] ✓ Successfully navigated to search page`);
          break;
        } catch (error: any) {
          console.warn(
            `[Thumbnail Wait Test] ⚠️  Navigation attempt ${attempt} failed: ${error.message}`
          );
          if (attempt < maxNavRetries) {
            console.log(`[Thumbnail Wait Test] Waiting 3s before retry...`);
            await authenticatedBatchDeletePage.waitForTimeout(3000);
          }
        }
      }

      if (!navigationSuccess) {
        throw new Error("Could not navigate to search page after 3 attempts");
      }

      // Wait for assets to be indexed in OpenSearch (can take time after upload)
      console.log("[Thumbnail Wait Test] Waiting for assets to be indexed (up to 60s)...");
      await authenticatedBatchDeletePage.waitForTimeout(10000); // Initial 10s wait

      // Wait for search results to appear with retries
      const assetCards = authenticatedBatchDeletePage.locator('[data-testid^="asset-card-"]');

      let assetsFound = false;
      const maxRetries = 5;

      for (let retry = 1; retry <= maxRetries; retry++) {
        const count = await assetCards.count();
        console.log(
          `[Thumbnail Wait Test] Search attempt ${retry}/${maxRetries}: Found ${count} assets`
        );

        if (count > 0) {
          assetsFound = true;
          break;
        }

        if (retry < maxRetries) {
          console.log("[Thumbnail Wait Test] Refreshing page and retrying...");
          await authenticatedBatchDeletePage.reload({
            waitUntil: "domcontentloaded",
          });
          await authenticatedBatchDeletePage.waitForTimeout(10000); // Wait 10s between retries
        }
      }

      if (!assetsFound) {
        throw new Error("No asset cards found after 5 attempts - files may not be indexed yet");
      }

      await assetCards.first().waitFor({ state: "visible", timeout: 5000 });

      const totalAssets = await assetCards.count();
      console.log(`[Thumbnail Wait Test] Found ${totalAssets} asset cards`);

      // Wait up to 2 minutes for all thumbnails to finish loading (no placeholders)
      const maxWaitTime = 120000; // 2 minutes
      const checkInterval = 5000; // Check every 5 seconds
      const startTime = Date.now();
      let allThumbnailsLoaded = false;

      console.log("[Thumbnail Wait Test] Waiting for all thumbnails to load (max 2 minutes)");

      while (Date.now() - startTime < maxWaitTime && !allThumbnailsLoaded) {
        // Find all images with placeholder SVG (base64 encoded)
        const placeholderImages = authenticatedBatchDeletePage.locator(
          'img[src^="data:image/svg+xml;base64,"]'
        );
        const placeholderCount = await placeholderImages.count();

        if (placeholderCount === 0) {
          console.log("[Thumbnail Wait Test] ✓ All thumbnails loaded successfully!");
          allThumbnailsLoaded = true;
          break;
        }

        const elapsed = Math.round((Date.now() - startTime) / 1000);
        console.log(
          `[Thumbnail Wait Test] ${placeholderCount} placeholder(s) remaining... (${elapsed}s elapsed)`
        );

        // Refresh the page every 15 seconds to help trigger thumbnail loading
        if (elapsed > 0 && elapsed % 15 === 0) {
          console.log("[Thumbnail Wait Test] Refreshing page to trigger thumbnail updates...");
          await authenticatedBatchDeletePage.reload({
            waitUntil: "domcontentloaded",
          });
          await authenticatedBatchDeletePage.waitForTimeout(2000);
        } else {
          await authenticatedBatchDeletePage.waitForTimeout(checkInterval);
        }
      }

      if (!allThumbnailsLoaded) {
        const placeholderImages = authenticatedBatchDeletePage.locator(
          'img[src^="data:image/svg+xml;base64,"]'
        );
        const remainingPlaceholders = await placeholderImages.count();
        console.warn(
          `[Thumbnail Wait Test] ⚠️  ${remainingPlaceholders} thumbnail(s) still loading after 2 minutes`
        );
      }

      // Verify we have assets displayed
      expect(totalAssets).toBeGreaterThan(0);

      // Count assets without placeholders (loaded thumbnails)
      const placeholderCount = await authenticatedBatchDeletePage
        .locator('img[src^="data:image/svg+xml;base64,"]')
        .count();
      const loadedAssets = totalAssets - placeholderCount;

      console.log(`[Thumbnail Wait Test] Total assets: ${totalAssets}`);
      console.log(`[Thumbnail Wait Test] Assets with placeholders: ${placeholderCount}`);
      console.log(`[Thumbnail Wait Test] Assets with loaded thumbnails: ${loadedAssets}`);

      // Strict validation: ALL assets must have loaded thumbnails (no placeholders)
      expect(placeholderCount).toBe(0);
      expect(loadedAssets).toBe(totalAssets);
      console.log(
        `[Thumbnail Wait Test] ✓ Validated ${loadedAssets} assets with loaded thumbnails (no placeholders)`
      );

      // Take screenshot for verification
      await authenticatedBatchDeletePage.screenshot({
        path: "test-results/thumbnails-loaded.png",
        fullPage: true,
      });
      console.log("[Thumbnail Wait Test] Screenshot saved to test-results/thumbnails-loaded.png");
    }
  );

  batchDeleteTest(
    "should perform complete batch delete workflow",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl }) => {
      console.log("[Batch Delete Workflow] Starting complete batch delete test");

      // Navigate to search page with retry logic
      const searchUrl = `${cloudFrontUrl}/search?q=*&semantic=false`;
      console.log(`[Batch Delete Workflow] Navigating to: ${searchUrl}`);

      let navigationSuccess = false;
      const maxNavRetries = 3;

      for (let attempt = 1; attempt <= maxNavRetries; attempt++) {
        try {
          console.log(`[Batch Delete Workflow] Navigation attempt ${attempt}/${maxNavRetries}`);
          await authenticatedBatchDeletePage.goto(searchUrl, {
            waitUntil: "domcontentloaded",
            timeout: 30000,
          });
          await authenticatedBatchDeletePage.waitForLoadState("domcontentloaded");
          navigationSuccess = true;
          console.log(`[Batch Delete Workflow] ✓ Successfully navigated to search page`);
          break;
        } catch (error: any) {
          console.warn(
            `[Batch Delete Workflow] ⚠️  Navigation attempt ${attempt} failed: ${error.message}`
          );
          if (attempt < maxNavRetries) {
            console.log(`[Batch Delete Workflow] Waiting 3s before retry...`);
            await authenticatedBatchDeletePage.waitForTimeout(3000);
          }
        }
      }

      if (!navigationSuccess) {
        throw new Error("Could not navigate to search page after 3 attempts");
      }

      // Wait for assets to be indexed in OpenSearch (can take time after upload)
      console.log("[Batch Delete Workflow] Waiting for assets to be indexed (up to 60s)...");
      await authenticatedBatchDeletePage.waitForTimeout(10000); // Initial 10s wait

      // Wait for search results to appear with retries
      const assetCards = authenticatedBatchDeletePage.locator('[data-testid^="asset-card-"]');

      let assetsFound = false;
      const maxRetries = 5;

      for (let retry = 1; retry <= maxRetries; retry++) {
        const count = await assetCards.count();
        console.log(
          `[Batch Delete Workflow] Search attempt ${retry}/${maxRetries}: Found ${count} assets`
        );

        if (count > 0) {
          assetsFound = true;
          break;
        }

        if (retry < maxRetries) {
          console.log("[Batch Delete Workflow] Refreshing page and retrying...");
          await authenticatedBatchDeletePage.reload({
            waitUntil: "domcontentloaded",
          });
          await authenticatedBatchDeletePage.waitForTimeout(10000); // Wait 10s between retries
        }
      }

      if (!assetsFound) {
        throw new Error("No asset cards found after 5 attempts - files may not be indexed yet");
      }

      await assetCards.first().waitFor({ state: "visible", timeout: 5000 });

      const totalAssets = await assetCards.count();
      console.log(`[Batch Delete Workflow] Found ${totalAssets} assets`);

      // Wait up to 2 minutes for all thumbnails to load (stricter than before)
      console.log("[Batch Delete Workflow] Waiting for all thumbnails to load (max 2 minutes)...");
      const maxThumbnailWait = 120000; // 2 minutes
      const checkInterval = 5000; // Check every 5 seconds
      const thumbnailStartTime = Date.now();
      let allThumbnailsLoaded = false;

      while (Date.now() - thumbnailStartTime < maxThumbnailWait && !allThumbnailsLoaded) {
        const placeholderCount = await authenticatedBatchDeletePage
          .locator('img[src^="data:image/svg+xml;base64,"]')
          .count();

        if (placeholderCount === 0) {
          console.log("[Batch Delete Workflow] ✓ All thumbnails loaded!");
          allThumbnailsLoaded = true;
          break;
        }

        const elapsed = Math.round((Date.now() - thumbnailStartTime) / 1000);
        console.log(
          `[Batch Delete Workflow] ${placeholderCount} placeholder(s) remaining... (${elapsed}s elapsed)`
        );

        // Refresh the page every 15 seconds to help trigger thumbnail loading
        if (elapsed > 0 && elapsed % 15 === 0) {
          console.log("[Batch Delete Workflow] Refreshing page to trigger thumbnail updates...");
          await authenticatedBatchDeletePage.reload({
            waitUntil: "domcontentloaded",
          });
          await authenticatedBatchDeletePage.waitForTimeout(2000);
        } else {
          await authenticatedBatchDeletePage.waitForTimeout(checkInterval);
        }
      }

      // Final validation - STRICT: must have NO placeholders
      const finalPlaceholderCount = await authenticatedBatchDeletePage
        .locator('img[src^="data:image/svg+xml;base64,"]')
        .count();

      console.log(`[Batch Delete Workflow] Final placeholder count: ${finalPlaceholderCount}`);
      console.log(
        `[Batch Delete Workflow] Assets without placeholders: ${
          totalAssets - finalPlaceholderCount
        }`
      );

      // Strict validation: ALL assets must have loaded thumbnails (no placeholders)
      expect(finalPlaceholderCount).toBe(0);

      // Validate we have at least 10 assets (based on user's test files)
      expect(totalAssets).toBeGreaterThanOrEqual(10);
      console.log(
        `[Batch Delete Workflow] ✓ Validated ${totalAssets} assets without placeholders (minimum 10 required)`
      );

      // Step 1: Click "Select Page" checkbox
      console.log("[Batch Delete Workflow] Step 1: Clicking 'Select Page' checkbox");
      const selectPageCheckbox = authenticatedBatchDeletePage.getByRole("checkbox", {
        name: /select page/i,
      });
      await selectPageCheckbox.click();
      await authenticatedBatchDeletePage.waitForTimeout(1000);

      // Step 2: Validate BATCH OPERATIONS tab shows correct count
      console.log("[Batch Delete Workflow] Step 2: Validating BATCH OPERATIONS tab count");
      const batchOpsTab = authenticatedBatchDeletePage.getByRole("tab", {
        name: /batch operations/i,
      });
      await batchOpsTab.waitFor({ state: "visible", timeout: 5000 });

      const batchOpsText = await batchOpsTab.textContent();
      console.log(`[Batch Delete Workflow] BATCH OPERATIONS tab text: "${batchOpsText}"`);

      // Extract count from tab text (e.g., "BATCH OPERATIONS (9)")
      const countMatch = batchOpsText?.match(/\((\d+)\)/);
      const selectedCount = countMatch ? parseInt(countMatch[1]) : 0;
      console.log(`[Batch Delete Workflow] Selected assets count: ${selectedCount}`);
      expect(selectedCount).toBe(totalAssets);

      // Step 3: Click BATCH OPERATIONS tab
      console.log("[Batch Delete Workflow] Step 3: Clicking BATCH OPERATIONS tab");
      await batchOpsTab.click();
      await authenticatedBatchDeletePage.waitForTimeout(1000);

      // Step 4: Click Delete button (use testid for the batch delete button)
      console.log("[Batch Delete Workflow] Step 4: Clicking batch delete button");
      const deleteButton = authenticatedBatchDeletePage.getByTestId("batch-delete-button");
      await deleteButton.waitFor({ state: "visible", timeout: 5000 });
      await deleteButton.click();
      await authenticatedBatchDeletePage.waitForTimeout(1000);

      // Step 5: Type "DELETE" in confirmation popup
      console.log("[Batch Delete Workflow] Step 5: Confirming deletion");

      // Wait for confirmation dialog
      const confirmDialog = authenticatedBatchDeletePage.locator('[role="dialog"]');
      await confirmDialog.waitFor({ state: "visible", timeout: 5000 });

      // Find the input field and type DELETE
      const deleteInput = authenticatedBatchDeletePage.getByPlaceholder(/type delete to confirm/i);
      await deleteInput.waitFor({ state: "visible", timeout: 5000 });
      await deleteInput.fill("DELETE");
      console.log("[Batch Delete Workflow] Typed 'DELETE' in confirmation field");

      // Take screenshot before confirming
      await authenticatedBatchDeletePage.screenshot({
        path: "test-results/batch-delete-confirmation.png",
        fullPage: true,
      });

      // Step 6: Click the Delete button in the popup
      console.log("[Batch Delete Workflow] Step 6: Clicking confirm delete button");
      const confirmDeleteButton = confirmDialog.getByRole("button", {
        name: /delete/i,
      });
      await confirmDeleteButton.click();

      // Step 7: Monitor deletion progress popup
      console.log("[Batch Delete Workflow] Step 7: Monitoring deletion progress");

      // Wait for progress dialog to appear
      await authenticatedBatchDeletePage.waitForTimeout(1000);

      // Monitor for completion - wait up to 2 minutes
      const maxWaitTime = 120000; // 2 minutes
      const startTime = Date.now();
      let deletionComplete = false;

      while (Date.now() - startTime < maxWaitTime && !deletionComplete) {
        // Check if progress dialog is still visible
        const progressDialog = authenticatedBatchDeletePage.locator(
          '[role="dialog"]:has-text("deletion")'
        );
        const isVisible = await progressDialog.isVisible().catch(() => false);

        if (!isVisible) {
          console.log(
            "[Batch Delete Workflow] ✓ Deletion progress dialog closed - deletion complete!"
          );
          deletionComplete = true;
          break;
        }

        // Try to read progress text
        const progressText = await progressDialog.textContent().catch(() => "");
        if (progressText) {
          console.log(`[Batch Delete Workflow] Progress: ${progressText.substring(0, 100)}...`);
        }

        await authenticatedBatchDeletePage.waitForTimeout(2000);
      }

      if (!deletionComplete) {
        console.warn("[Batch Delete Workflow] ⚠️  Deletion still in progress after 2 minutes");
      }

      // Take screenshot after deletion
      await authenticatedBatchDeletePage.screenshot({
        path: "test-results/batch-delete-complete.png",
        fullPage: true,
      });

      // Step 8: Refresh and verify no results
      console.log("[Batch Delete Workflow] Step 8: Verifying assets were deleted");

      let noResultsFound = false;
      const maxRefreshAttempts = 10;

      for (let attempt = 1; attempt <= maxRefreshAttempts; attempt++) {
        console.log(`[Batch Delete Workflow] Refresh attempt ${attempt}/${maxRefreshAttempts}`);

        await authenticatedBatchDeletePage.reload({
          waitUntil: "domcontentloaded",
        });
        await authenticatedBatchDeletePage.waitForTimeout(2000);

        // Check for "no results" message or empty results
        const noResultsMsg = authenticatedBatchDeletePage.getByText(/no results found|no assets/i);
        const hasNoResults = await noResultsMsg.isVisible().catch(() => false);

        // Also check if asset cards are gone
        const remainingAssets = await authenticatedBatchDeletePage
          .locator('[data-testid^="asset-card-"]')
          .count();

        console.log(`[Batch Delete Workflow] Remaining assets: ${remainingAssets}`);

        if (hasNoResults || remainingAssets === 0) {
          console.log("[Batch Delete Workflow] ✓ All assets successfully deleted!");
          noResultsFound = true;
          break;
        }

        await authenticatedBatchDeletePage.waitForTimeout(3000);
      }

      // Final screenshot
      await authenticatedBatchDeletePage.screenshot({
        path: "test-results/batch-delete-verification.png",
        fullPage: true,
      });

      expect(noResultsFound).toBe(true);
      console.log("[Batch Delete Workflow] ✅ Batch delete workflow completed successfully!");
    }
  );
});

batchDeleteTest.describe("Step 4: Cleanup - Remove Test Connector", () => {
  batchDeleteTest.setTimeout(90000); // Increase timeout to 90 seconds for cleanup

  batchDeleteTest(
    "should delete the test connector if it was created",
    async ({ authenticatedBatchDeletePage, cloudFrontUrl }) => {
      if (!testConnectorWasCreated || !testConnectorName) {
        console.log("[Cleanup] No test connector to delete (using existing connector)");
        return;
      }

      console.log(`[Cleanup] Deleting test connector: ${testConnectorName}`);

      // Navigate to connectors page with retry logic
      let navigationSuccess = false;
      const maxRetries = 3;

      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          console.log(`[Cleanup] Navigation attempt ${attempt}/${maxRetries}`);
          await navigateToConnectors(authenticatedBatchDeletePage, cloudFrontUrl);
          navigationSuccess = true;
          console.log(`[Cleanup] ✓ Successfully navigated to connectors page`);
          break;
        } catch (error: any) {
          console.warn(`[Cleanup] ⚠️  Navigation attempt ${attempt} failed: ${error.message}`);
          if (attempt < maxRetries) {
            console.log(`[Cleanup] Waiting 3s before retry...`);
            await authenticatedBatchDeletePage.waitForTimeout(3000);
          }
        }
      }

      if (!navigationSuccess) {
        console.error("[Cleanup] ❌ Failed to navigate to connectors page after 3 attempts");
        throw new Error("Could not navigate to connectors page for cleanup");
      }

      await authenticatedBatchDeletePage.waitForTimeout(5000);

      // Count connectors before deletion
      const connectorsBefore = await authenticatedBatchDeletePage
        .locator('[data-testid^="connector-card-"]')
        .count();
      console.log(`[Cleanup] Connectors before deletion: ${connectorsBefore}`);

      // Delete the connector with extended timeout
      const deleted = await deleteConnector(
        authenticatedBatchDeletePage,
        testConnectorName,
        60000 // 60 second timeout for delete operation
      );

      if (deleted) {
        console.log(`[Cleanup] ✓ Delete operation completed for: ${testConnectorName}`);

        // Wait for backend deletion to complete with retry logic
        console.log("[Cleanup] Waiting for connector to be removed from backend...");
        let connectorRemoved = false;
        const maxWaitAttempts = 15; // Increased from 10 to 15

        for (let attempt = 1; attempt <= maxWaitAttempts; attempt++) {
          console.log(`[Cleanup] Checking removal attempt ${attempt}/${maxWaitAttempts}`);

          // Refresh page to get latest state
          await authenticatedBatchDeletePage.reload({
            waitUntil: "domcontentloaded",
          });
          await authenticatedBatchDeletePage.waitForTimeout(5000); // Increased from 3s to 5s

          // Count total connectors
          const connectorsAfter = await authenticatedBatchDeletePage
            .locator('[data-testid^="connector-card-"]')
            .count();
          console.log(
            `[Cleanup] Connectors after deletion (attempt ${attempt}): ${connectorsAfter}`
          );

          // Check specifically for the deleted connector (using h5 like in delete function)
          const deletedConnector = await authenticatedBatchDeletePage
            .locator('[data-testid^="connector-card-"]')
            .filter({
              has: authenticatedBatchDeletePage.locator(`h5:has-text("${testConnectorName}")`),
            })
            .count();

          console.log(`[Cleanup] Deleted connector still visible: ${deletedConnector}`);

          if (connectorsAfter === connectorsBefore - 1 && deletedConnector === 0) {
            console.log(`[Cleanup] ✓ Connector successfully removed after ${attempt} attempt(s)`);
            connectorRemoved = true;

            // Take screenshot after successful deletion
            await authenticatedBatchDeletePage.screenshot({
              path: "test-results/connector-cleanup.png",
              fullPage: true,
            });

            // Validation: connector is gone
            expect(connectorsAfter).toBe(connectorsBefore - 1);
            expect(deletedConnector).toBe(0);
            break;
          }

          if (attempt < maxWaitAttempts) {
            console.log("[Cleanup] Connector still present, waiting 8s before next check...");
            await authenticatedBatchDeletePage.waitForTimeout(8000); // Increased from 5s to 8s
          }
        }

        if (!connectorRemoved) {
          // Take screenshot of failure state
          await authenticatedBatchDeletePage.screenshot({
            path: "test-results/connector-cleanup-failed.png",
            fullPage: true,
          });
          console.error(
            `[Cleanup] ❌ Connector ${testConnectorName} still visible after ${maxWaitAttempts} attempts (up to ${
              maxWaitAttempts * 8
            }s)`
          );
          throw new Error(
            `Connector ${testConnectorName} still visible after ${maxWaitAttempts} attempts`
          );
        }

        console.log(
          `[Cleanup] ✅ Successfully deleted and verified removal of: ${testConnectorName}`
        );

        // Reset tracking variables
        testConnectorName = null;
        testConnectorWasCreated = false;
      } else {
        console.warn(`[Cleanup] ⚠️  Failed to delete test connector: ${testConnectorName}`);
        throw new Error(`Failed to delete connector: ${testConnectorName}`);
      }
    }
  );
});
