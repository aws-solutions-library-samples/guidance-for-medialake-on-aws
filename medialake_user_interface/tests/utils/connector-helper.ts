/**
 * Connector Helper for Playwright Tests
 *
 * Provides reusable utilities for checking and verifying connectors in E2E tests
 */

import { Page } from "@playwright/test";

export interface ConnectorCheckOptions {
  /** Timeout for waiting for page load in ms (default: 30000) */
  timeout?: number;
  /** Take screenshot during check (default: false) */
  captureScreenshot?: boolean;
  /** Screenshot directory path (default: "test-results") */
  screenshotDir?: string;
  /** Minimum expected connectors (default: 1) */
  minConnectors?: number;
}

export interface ConnectorCheckResult {
  /** Whether check was successful */
  success: boolean;
  /** Number of connectors found */
  connectorCount: number;
  /** First connector info (if any) */
  firstConnectorInfo?: string;
  /** Error message if check failed */
  error?: string;
}

/**
 * Get connector cards using partial test ID match
 * Returns locator that matches data-testid starting with "connector-card-"
 */
function getConnectorCards(page: Page) {
  return page.locator('[data-testid^="connector-card-"]');
}

/**
 * Check if connectors are configured
 *
 * @param page - Playwright page object
 * @param baseUrl - Base CloudFront URL
 * @param options - Check options
 * @returns Check result with connector count
 */
export async function checkConnectorsConfigured(
  page: Page,
  baseUrl: string,
  options: ConnectorCheckOptions = {}
): Promise<ConnectorCheckResult> {
  const {
    timeout = 30000,
    captureScreenshot = false,
    screenshotDir = "test-results",
    minConnectors = 1,
  } = options;

  console.log("[ConnectorHelper] Checking for configured connectors");

  try {
    // Navigate to connectors page
    const connectorsUrl = `${baseUrl}/settings/connectors`;
    console.log(`[ConnectorHelper] Navigating to: ${connectorsUrl}`);

    await page.goto(connectorsUrl, {
      waitUntil: "domcontentloaded",
      timeout,
    });
    await page.waitForLoadState("domcontentloaded");
    console.log("[ConnectorHelper] Page loaded, waiting for content to render...");
    await page.waitForTimeout(12000); // Wait 12 seconds for connectors to load

    // Check for connector cards using partial test ID match with retry logic
    const connectorCards = getConnectorCards(page);
    let connectorCount = await connectorCards.count();

    console.log(`[ConnectorHelper] Initial count: ${connectorCount}`);

    // If no connectors found initially, wait and retry multiple times
    if (connectorCount === 0) {
      console.log("[ConnectorHelper] No connectors found, waiting 5s and retrying...");
      await page.waitForTimeout(5000);
      connectorCount = await connectorCards.count();
      console.log(`[ConnectorHelper] Retry 1 count: ${connectorCount}`);

      // If still not found, retry one more time
      if (connectorCount === 0) {
        console.log("[ConnectorHelper] Still no connectors, waiting another 5s...");
        await page.waitForTimeout(5000);
        connectorCount = await connectorCards.count();
        console.log(`[ConnectorHelper] Retry 2 count: ${connectorCount}`);
      }
    }

    console.log(`[ConnectorHelper] Found ${connectorCount} configured connector(s)`);

    // Get first connector info if available
    let firstConnectorInfo: string | undefined;
    if (connectorCount > 0) {
      const firstCard = connectorCards.first();
      const connectorText = await firstCard.textContent();
      firstConnectorInfo = connectorText?.substring(0, 100) || "";
      console.log(`[ConnectorHelper] First connector: ${firstConnectorInfo}...`);
    }

    // Take screenshot if requested
    if (captureScreenshot) {
      const fs = await import("fs");
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }

      await page.screenshot({
        path: `${screenshotDir}/connectors-check.png`,
        fullPage: true,
      });
      console.log(`[ConnectorHelper] Screenshot saved to ${screenshotDir}/connectors-check.png`);
    }

    // Check if minimum requirement is met
    const success = connectorCount >= minConnectors;

    if (success) {
      console.log(
        `[ConnectorHelper] ✅ Found ${connectorCount} connector(s) (minimum: ${minConnectors})`
      );
    } else {
      console.warn(
        `[ConnectorHelper] ⚠️  Only found ${connectorCount} connector(s), expected at least ${minConnectors}`
      );
    }

    return {
      success,
      connectorCount,
      firstConnectorInfo,
    };
  } catch (error: any) {
    console.error("[ConnectorHelper] Error checking connectors:", error.message);

    if (captureScreenshot) {
      try {
        await page.screenshot({
          path: `${screenshotDir}/connectors-check-error.png`,
          fullPage: true,
        });
      } catch (screenshotError) {
        console.error("[ConnectorHelper] Failed to capture error screenshot");
      }
    }

    return {
      success: false,
      connectorCount: 0,
      error: error.message,
    };
  }
}

/**
 * Get connector count on the connectors page
 *
 * @param page - Playwright page object (should already be on connectors page)
 * @returns Number of connectors found
 */
export async function getConnectorCount(page: Page): Promise<number> {
  const connectorCards = getConnectorCards(page);
  return await connectorCards.count();
}

/**
 * Navigate to connectors page
 *
 * @param page - Playwright page object
 * @param baseUrl - Base CloudFront URL
 * @param timeout - Navigation timeout in ms (default: 30000)
 */
export async function navigateToConnectors(
  page: Page,
  baseUrl: string,
  timeout: number = 30000
): Promise<void> {
  const connectorsUrl = `${baseUrl}/settings/connectors`;
  console.log(`[ConnectorHelper] Navigating to connectors page: ${connectorsUrl}`);

  await page.goto(connectorsUrl, {
    waitUntil: "domcontentloaded",
    timeout,
  });

  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(2000);

  console.log("[ConnectorHelper] Connectors page loaded");
}

/**
 * Verify minimum connector requirement
 *
 * @param page - Playwright page object
 * @param baseUrl - Base CloudFront URL
 * @param minCount - Minimum number of connectors required (default: 1)
 * @param options - Additional options
 * @returns True if requirement is met
 */
export async function verifyMinimumConnectors(
  page: Page,
  baseUrl: string,
  minCount: number = 1,
  options: Omit<ConnectorCheckOptions, "minConnectors"> = {}
): Promise<boolean> {
  const result = await checkConnectorsConfigured(page, baseUrl, {
    ...options,
    minConnectors: minCount,
  });

  return result.success;
}

/**
 * Get connector information for display/logging
 *
 * @param page - Playwright page object (should already be on connectors page)
 * @param maxConnectors - Maximum number of connectors to get info for (default: 5)
 * @returns Array of connector info strings
 */
export async function getConnectorInfo(page: Page, maxConnectors: number = 5): Promise<string[]> {
  const connectorCards = getConnectorCards(page);
  const count = await connectorCards.count();
  const limit = Math.min(count, maxConnectors);

  const info: string[] = [];

  for (let i = 0; i < limit; i++) {
    const card = connectorCards.nth(i);
    const text = await card.textContent();
    if (text) {
      info.push(text.substring(0, 100).trim());
    }
  }

  console.log(`[ConnectorHelper] Retrieved info for ${info.length} connector(s)`);
  return info;
}

/**
 * Create a test S3 connector with a NEW S3 bucket using the simplified 3-step wizard UI
 *
 * @param page - Playwright page object (should already be on connectors page)
 * @param options - Creation options
 * @returns Object with success status, connector name, and bucket name
 */
export async function createS3ConnectorWithNewBucket(
  page: Page,
  options: {
    connectorName?: string;
    description?: string;
    bucketName?: string;
    allowUploads?: boolean;
  } = {}
): Promise<{ success: boolean; connectorName: string; bucketName: string }> {
  const timestamp = Date.now();
  const connectorName = options.connectorName || `test-connector-${timestamp}`;
  const bucketName = options.bucketName || `test-bucket-${timestamp}`;
  const description = options.description || "Test S3 connector with new bucket";
  const allowUploads = options.allowUploads !== undefined ? options.allowUploads : true;

  console.log(`[ConnectorHelper] Creating S3 connector with NEW bucket`);
  console.log(`[ConnectorHelper] Connector Name: ${connectorName}`);
  console.log(`[ConnectorHelper] New Bucket Name: ${bucketName}`);
  console.log(`[ConnectorHelper] Allow Uploads: ${allowUploads}`);

  try {
    // Step 1: Click "Add Connector" button to open modal
    console.log("[ConnectorHelper] Step 1: Opening connector modal");
    await page.getByRole("button", { name: "Add Connector" }).click();
    await page.waitForTimeout(1000);

    // Step 2: Select Amazon S3 connector type
    console.log("[ConnectorHelper] Step 2: Selecting Amazon S3 type");
    await page
      .locator("div")
      .filter({ hasText: /^Amazon S3$/ })
      .click();
    await page.waitForTimeout(500);

    // Step 3: Select "New S3 Bucket" option
    console.log("[ConnectorHelper] Step 3: Selecting New S3 Bucket");
    await page.getByText("New S3 BucketCreate a new S3").click();
    await page.waitForTimeout(1000);

    // Step 4: Fill in connector name
    console.log(`[ConnectorHelper] Step 4: Filling connector name: ${connectorName}`);
    const nameInput = page.getByRole("textbox", { name: /Connector Name/i });
    await nameInput.waitFor({ state: "visible", timeout: 5000 });
    await nameInput.fill(connectorName);
    await page.waitForTimeout(500);

    // Step 5: Fill in description
    console.log(`[ConnectorHelper] Step 5: Filling description`);
    const descInput = page.getByRole("textbox", { name: /Description/i });
    await descInput.fill(description);
    await page.waitForTimeout(500);

    // Step 6: Fill in new bucket name
    console.log(`[ConnectorHelper] Step 6: Filling new bucket name: ${bucketName}`);
    const bucketInput = page.getByRole("textbox", { name: /New Bucket Name/i });
    await bucketInput.waitFor({ state: "visible", timeout: 5000 });
    await bucketInput.fill(bucketName);
    await page.waitForTimeout(500);

    // Step 7: Configure advanced settings (Allow Uploads)
    if (allowUploads) {
      console.log("[ConnectorHelper] Step 7: Enabling Allow Uploads in Advanced Configuration");

      // Click the "ADVANCED CONFIGURATION" toggle button
      await page.getByRole("button", { name: "ADVANCED CONFIGURATION" }).click();
      await page.waitForTimeout(1000);

      // Find and check the "Allow Uploads" checkbox
      const allowUploadsCheckbox = page.getByRole("checkbox", {
        name: /allow uploads/i,
      });
      const isChecked = await allowUploadsCheckbox.isChecked();

      if (!isChecked) {
        console.log("[ConnectorHelper] Checking Allow Uploads checkbox");
        await allowUploadsCheckbox.check();
        await page.waitForTimeout(500);
      } else {
        console.log("[ConnectorHelper] Allow Uploads already checked");
      }
    } else {
      console.log("[ConnectorHelper] Step 7: Skipping Allow Uploads (disabled by option)");
    }

    // Step 8: Submit the connector creation form
    console.log("[ConnectorHelper] Step 8: Submitting connector form");
    await page.getByRole("button", { name: "Add Connector" }).click();

    // Wait for connector to be created and modal to close (backend processing may take time)
    console.log("[ConnectorHelper] Waiting for connector creation to complete (30s timeout)...");
    await page.waitForTimeout(30000);

    console.log(
      `[ConnectorHelper] ✅ Connector created successfully: ${connectorName} with bucket: ${bucketName}`
    );
    return { success: true, connectorName, bucketName };
  } catch (error: any) {
    console.error(`[ConnectorHelper] ❌ Error creating connector:`, error.message);

    // Take error screenshot
    try {
      await page.screenshot({
        path: "test-results/connector-creation-error.png",
        fullPage: true,
      });
      console.log(
        "[ConnectorHelper] Error screenshot saved to test-results/connector-creation-error.png"
      );
    } catch (screenshotError) {
      console.error("[ConnectorHelper] Failed to capture error screenshot");
    }

    return { success: false, connectorName, bucketName };
  }
}

/**
 * Create a test S3 connector using an EXISTING S3 bucket with the simplified 3-step wizard UI
 *
 * @param page - Playwright page object (should already be on connectors page)
 * @param s3BucketName - S3 bucket name to use for connector
 * @param options - Creation options
 * @returns Object with success status and connector name
 */
export async function createS3ConnectorWithExistingBucket(
  page: Page,
  s3BucketName: string,
  options: {
    connectorName?: string;
    description?: string;
    allowUploads?: boolean;
  } = {}
): Promise<{ success: boolean; connectorName: string }> {
  const connectorName = options.connectorName || `test-s3-connector-${Date.now()}`;
  const description = options.description || "this is my test S3 connector";
  const allowUploads = options.allowUploads !== undefined ? options.allowUploads : true;

  console.log(`[ConnectorHelper] Creating S3 connector: ${connectorName}`);
  console.log(`[ConnectorHelper] Using S3 bucket: ${s3BucketName}`);
  console.log(`[ConnectorHelper] Allow Uploads: ${allowUploads}`);

  try {
    // Step 1: Click "Add Connector" button to open modal
    console.log("[ConnectorHelper] Step 1: Opening connector modal");
    await page.getByRole("button", { name: "Add Connector" }).click();
    await page.waitForTimeout(1000);

    // Step 2: Select Amazon S3 connector type
    console.log("[ConnectorHelper] Step 2: Selecting Amazon S3 type");
    await page
      .locator("div")
      .filter({ hasText: /^Amazon S3$/ })
      .click();
    await page.waitForTimeout(500);

    // Step 3: Select "Existing S3 Bucket" option
    console.log("[ConnectorHelper] Step 3: Selecting Existing S3 Bucket");
    await page.getByText("Existing S3 BucketConnect to").click();
    await page.waitForTimeout(1000);

    // Step 4: Fill in connector name
    console.log(`[ConnectorHelper] Step 4: Filling connector name: ${connectorName}`);
    const nameInput = page.getByRole("textbox", { name: /Connector Name/i });
    await nameInput.waitFor({ state: "visible", timeout: 5000 });
    await nameInput.fill(connectorName);
    await page.waitForTimeout(500);

    // Step 5: Fill in description
    console.log(`[ConnectorHelper] Step 5: Filling description`);
    const descInput = page.getByRole("textbox", { name: /Description/i });
    await descInput.fill(description);
    await page.waitForTimeout(500);

    // Step 6: Select S3 bucket from dropdown
    console.log(`[ConnectorHelper] Step 6: Selecting S3 bucket: ${s3BucketName}`);

    // Find the S3 Bucket combobox (should be the only combobox in the new UI)
    const bucketCombobox = page.getByRole("combobox").first();
    await bucketCombobox.waitFor({ state: "visible", timeout: 5000 });
    await bucketCombobox.click();
    await page.waitForTimeout(2000); // Wait for dropdown to populate

    // Try to find and select the bucket with retries
    let bucketFound = false;
    let attempts = 0;
    const maxAttempts = 5;

    while (!bucketFound && attempts < maxAttempts) {
      try {
        await page.getByRole("option", { name: s3BucketName }).waitFor({ timeout: 5000 });
        await page.getByRole("option", { name: s3BucketName }).click();
        bucketFound = true;
        console.log(`[ConnectorHelper] Successfully selected S3 bucket: ${s3BucketName}`);
      } catch (error) {
        attempts++;
        console.log(
          `[ConnectorHelper] Bucket ${s3BucketName} not found in dropdown, attempt ${attempts}/${maxAttempts}`
        );

        if (attempts < maxAttempts) {
          // Close and reopen the dropdown
          await page.keyboard.press("Escape");
          await page.waitForTimeout(1000);
          await bucketCombobox.click();
          await page.waitForTimeout(2000);
        } else {
          // Take screenshot for debugging
          await page.screenshot({
            path: "test-results/bucket-selection-failed.png",
            fullPage: true,
          });
          throw new Error(
            `S3 bucket ${s3BucketName} not found in dropdown after ${maxAttempts} attempts. Screenshot saved.`
          );
        }
      }
    }

    // Step 7: Configure advanced settings (Allow Uploads)
    if (allowUploads) {
      console.log("[ConnectorHelper] Step 7: Enabling Allow Uploads in Advanced Configuration");

      // Click the "ADVANCED CONFIGURATION" toggle button
      await page.getByRole("button", { name: "ADVANCED CONFIGURATION" }).click();
      await page.waitForTimeout(1000);

      // Find and check the "Allow Uploads" checkbox
      const allowUploadsCheckbox = page.getByRole("checkbox", {
        name: /allow uploads/i,
      });
      const isChecked = await allowUploadsCheckbox.isChecked();

      if (!isChecked) {
        console.log("[ConnectorHelper] Checking Allow Uploads checkbox");
        await allowUploadsCheckbox.check();
        await page.waitForTimeout(500);
      } else {
        console.log("[ConnectorHelper] Allow Uploads already checked");
      }
    } else {
      console.log("[ConnectorHelper] Step 7: Skipping Allow Uploads (disabled by option)");
    }

    // Step 8: Submit the connector creation form
    console.log("[ConnectorHelper] Step 8: Submitting connector form");
    await page.getByRole("button", { name: "Add Connector" }).click();

    // Wait for connector to be created and modal to close (backend processing may take time)
    console.log("[ConnectorHelper] Waiting for connector creation to complete (30s timeout)...");
    await page.waitForTimeout(30000);

    console.log(`[ConnectorHelper] ✅ Connector created successfully: ${connectorName}`);
    return { success: true, connectorName };
  } catch (error: any) {
    console.error(`[ConnectorHelper] ❌ Error creating connector:`, error.message);

    // Take error screenshot
    try {
      await page.screenshot({
        path: "test-results/connector-creation-error.png",
        fullPage: true,
      });
      console.log(
        "[ConnectorHelper] Error screenshot saved to test-results/connector-creation-error.png"
      );
    } catch (screenshotError) {
      console.error("[ConnectorHelper] Failed to capture error screenshot");
    }

    return { success: false, connectorName };
  }
}

/**
 * Delete a connector by name
 *
 * @param page - Playwright page object (should already be on connectors page)
 * @param connectorName - Name of the connector to delete
 * @param timeout - Timeout for operations in ms (default: 60000)
 * @returns True if connector was deleted successfully
 */
export async function deleteConnector(
  page: Page,
  connectorName: string,
  timeout: number = 60000
): Promise<boolean> {
  console.log(`[ConnectorHelper] Deleting connector: ${connectorName}`);

  try {
    // Find the connector card containing the connector name
    const connectorCards = getConnectorCards(page);
    const connectorCard = connectorCards.filter({
      has: page.locator(`h5:has-text("${connectorName}")`),
    });

    // Wait for the connector card to be visible
    await connectorCard.waitFor({ state: "visible", timeout: 10000 });
    console.log(`[ConnectorHelper] Found connector card for: ${connectorName}`);

    // Find the delete button using data-testid pattern within the card
    const deleteButton = connectorCard.locator('[data-testid^="connector-delete-button-"]');
    await deleteButton.waitFor({ state: "visible", timeout: 10000 });
    console.log(`[ConnectorHelper] Found delete button for: ${connectorName}`);

    // Click the delete button with extended timeout
    await deleteButton.click({ timeout });
    console.log(`[ConnectorHelper] Clicked delete button`);

    await page.waitForTimeout(1000);

    // Confirm deletion in the modal
    const confirmButton = page.getByRole("button", { name: "Delete" });
    await confirmButton.waitFor({ state: "visible", timeout: 10000 });
    await confirmButton.click({ timeout });
    console.log(`[ConnectorHelper] Clicked confirm delete button`);

    // Wait for deletion to complete
    await page.waitForTimeout(3000);

    console.log(`[ConnectorHelper] ✅ Connector deleted: ${connectorName}`);
    return true;
  } catch (error: any) {
    console.error(`[ConnectorHelper] ❌ Error deleting connector:`, error.message);

    // Take error screenshot
    try {
      await page.screenshot({
        path: "test-results/connector-deletion-error.png",
        fullPage: true,
      });
      console.log(
        "[ConnectorHelper] Error screenshot saved to test-results/connector-deletion-error.png"
      );
    } catch (screenshotError) {
      console.error("[ConnectorHelper] Failed to capture error screenshot");
    }

    return false;
  }
}
