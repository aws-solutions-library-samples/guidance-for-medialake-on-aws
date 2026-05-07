/**
 * Connector Helper for Playwright Tests
 *
 * Provides reusable utilities for checking, verifying, and configuring connectors in E2E tests.
 * Supports connector creation with pipeline selection for semantic search workflows.
 *
 * @requirements 4.1, 4.2, 4.3, 4.4, 4.5
 */

import { Page } from "@playwright/test";
import { ProviderType, PROVIDER_METADATA } from "./provider-config-helper";

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

/**
 * Connector configuration interface for semantic search workflows
 */
export interface ConnectorConfig {
  /** Connector name (optional for pipeline selection operations) */
  name?: string;
  /** Connector description */
  description?: string;
  /** S3 bucket name (for S3 connectors) */
  bucketName?: string;
  /** Whether to create a new bucket or use existing */
  createNewBucket?: boolean;
  /** Pipeline ID to associate with connector */
  pipelineId?: string;
  /** Pipeline name to associate with connector */
  pipelineName?: string;
  /** Provider type for pipeline selection */
  providerType?: ProviderType;
  /** Allow uploads to connector */
  allowUploads?: boolean;
}

/**
 * Connector configuration result
 */
export interface ConnectorConfigResult {
  /** Whether configuration was successful */
  success: boolean;
  /** Connector name */
  connectorName: string;
  /** Bucket name (if applicable) */
  bucketName?: string;
  /** Associated pipeline ID */
  pipelineId?: string;
  /** Error message if failed */
  error?: string;
}

/**
 * Connector verification result
 */
export interface ConnectorVerificationResult {
  /** Whether connector is configured */
  isConfigured: boolean;
  /** Connector name */
  connectorName: string;
  /** Associated pipeline name */
  pipelineName?: string;
  /** Associated pipeline ID */
  pipelineId?: string;
  /** Connector status */
  status?: string;
}

/**
 * Helper class for connector configuration operations
 *
 * Provides methods for creating, configuring, and verifying connectors
 * with pipeline associations for semantic search workflows.
 *
 * @requirements 4.1, 4.2, 4.3, 4.4, 4.5
 */
export class ConnectorConfigHelper {
  private page: Page;
  private timeout: number;
  private baseUrl: string;

  constructor(page: Page, baseUrl: string = "", timeout: number = 30000) {
    this.page = page;
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  /**
   * Navigate to connector configuration page
   *
   * @requirements 4.1
   */
  async navigateToConnectorConfiguration(): Promise<void> {
    console.log("[ConnectorConfigHelper] Navigating to connector configuration");

    // Click Settings button in sidebar
    await this.page.getByRole("button", { name: "Settings" }).click();
    await this.page.waitForTimeout(500);

    // Click Connectors
    await this.page.getByRole("button", { name: "Connectors" }).click();

    // Wait for connectors page to load
    await this.page.waitForTimeout(2000);

    // Wait for connector cards or add button to be visible
    const addButton = this.page.getByRole("button", { name: "Add Connector" });
    await addButton.waitFor({ state: "visible", timeout: this.timeout });

    console.log("[ConnectorConfigHelper] Connector configuration page loaded");
  }

  /**
   * Create a new connector with pipeline selection
   *
   * @param config - Connector configuration options
   * @returns Connector configuration result
   * @requirements 4.1, 4.2, 4.3, 4.4
   */
  async createConnector(config: ConnectorConfig): Promise<ConnectorConfigResult> {
    const timestamp = Date.now();
    const connectorName = config.name || `test-connector-${timestamp}`;
    const bucketName =
      config.bucketName || (config.createNewBucket ? `test-bucket-${timestamp}` : undefined);
    const description = config.description || "Test connector for semantic search";

    console.log(`[ConnectorConfigHelper] Creating connector: ${connectorName}`);

    try {
      // Step 1: Click "Add Connector" button to open modal
      console.log("[ConnectorConfigHelper] Step 1: Opening connector modal");
      await this.page.getByRole("button", { name: "Add Connector" }).click();
      await this.page.waitForTimeout(1000);

      // Step 2: Select Amazon S3 connector type
      console.log("[ConnectorConfigHelper] Step 2: Selecting Amazon S3 type");
      await this.page
        .locator("div")
        .filter({ hasText: /^Amazon S3$/ })
        .click();
      await this.page.waitForTimeout(500);

      // Step 3: Select bucket option (new or existing)
      if (config.createNewBucket) {
        console.log("[ConnectorConfigHelper] Step 3: Selecting New S3 Bucket");
        await this.page.getByText("New S3 BucketCreate a new S3").click();
      } else {
        console.log("[ConnectorConfigHelper] Step 3: Selecting Existing S3 Bucket");
        await this.page.getByText("Existing S3 BucketConnect to").click();
      }
      await this.page.waitForTimeout(1000);

      // Step 4: Fill in connector name
      console.log(`[ConnectorConfigHelper] Step 4: Filling connector name: ${connectorName}`);
      const nameInput = this.page.getByRole("textbox", {
        name: /Connector Name/i,
      });
      await nameInput.waitFor({ state: "visible", timeout: this.timeout });
      await nameInput.fill(connectorName);
      await this.page.waitForTimeout(500);

      // Step 5: Fill in description
      console.log(`[ConnectorConfigHelper] Step 5: Filling description`);
      const descInput = this.page.getByRole("textbox", {
        name: /Description/i,
      });
      await descInput.fill(description);
      await this.page.waitForTimeout(500);

      // Step 6: Handle bucket configuration
      if (config.createNewBucket && bucketName) {
        console.log(`[ConnectorConfigHelper] Step 6: Filling new bucket name: ${bucketName}`);
        const bucketInput = this.page.getByRole("textbox", {
          name: /New Bucket Name/i,
        });
        await bucketInput.waitFor({ state: "visible", timeout: this.timeout });
        await bucketInput.fill(bucketName);
      } else if (bucketName) {
        console.log(`[ConnectorConfigHelper] Step 6: Selecting existing bucket: ${bucketName}`);
        await this.selectExistingBucket(bucketName);
      }
      await this.page.waitForTimeout(500);

      // Step 7: Select pipeline if specified
      let selectedPipelineId: string | undefined;
      if (config.pipelineId || config.pipelineName || config.providerType) {
        console.log("[ConnectorConfigHelper] Step 7: Selecting pipeline");
        selectedPipelineId = await this.selectPipelineForConnector(config);
      }

      // Step 8: Configure advanced settings
      if (config.allowUploads !== false) {
        console.log("[ConnectorConfigHelper] Step 8: Configuring advanced settings");
        await this.configureAdvancedSettings({ allowUploads: true });
      }

      // Step 9: Submit the connector creation form
      console.log("[ConnectorConfigHelper] Step 9: Submitting connector form");
      await this.page.getByRole("button", { name: "Add Connector" }).click();

      // Wait for connector to be created
      console.log("[ConnectorConfigHelper] Waiting for connector creation to complete...");
      await this.page.waitForTimeout(30000);

      console.log(`[ConnectorConfigHelper] ✅ Connector created successfully: ${connectorName}`);

      return {
        success: true,
        connectorName,
        bucketName,
        pipelineId: selectedPipelineId,
      };
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] ❌ Error creating connector:`, error.message);

      await this.captureErrorScreenshot("connector-creation-error");

      return {
        success: false,
        connectorName,
        bucketName,
        error: error.message,
      };
    }
  }

  /**
   * Select an existing S3 bucket from dropdown
   *
   * @param bucketName - Name of the bucket to select
   */
  private async selectExistingBucket(bucketName: string): Promise<void> {
    const bucketCombobox = this.page.getByRole("combobox").first();
    await bucketCombobox.waitFor({ state: "visible", timeout: this.timeout });
    await bucketCombobox.click();
    await this.page.waitForTimeout(2000);

    let bucketFound = false;
    let attempts = 0;
    const maxAttempts = 5;

    while (!bucketFound && attempts < maxAttempts) {
      try {
        await this.page.getByRole("option", { name: bucketName }).waitFor({ timeout: 5000 });
        await this.page.getByRole("option", { name: bucketName }).click();
        bucketFound = true;
        console.log(`[ConnectorConfigHelper] Successfully selected bucket: ${bucketName}`);
      } catch {
        attempts++;
        console.log(
          `[ConnectorConfigHelper] Bucket ${bucketName} not found, attempt ${attempts}/${maxAttempts}`
        );

        if (attempts < maxAttempts) {
          await this.page.keyboard.press("Escape");
          await this.page.waitForTimeout(1000);
          await bucketCombobox.click();
          await this.page.waitForTimeout(2000);
        } else {
          throw new Error(`S3 bucket ${bucketName} not found after ${maxAttempts} attempts`);
        }
      }
    }
  }

  /**
   * Select a pipeline for the connector
   *
   * @param config - Configuration with pipeline selection criteria
   * @returns Selected pipeline ID
   * @requirements 4.2, 4.3
   */
  async selectPipelineForConnector(config: ConnectorConfig): Promise<string | undefined> {
    console.log("[ConnectorConfigHelper] Selecting pipeline for connector");

    try {
      // Look for pipeline dropdown or selection UI
      const pipelineDropdown = this.page.locator(
        '[data-testid="pipeline-select"], [aria-label*="pipeline" i], select[name*="pipeline" i]'
      );

      // Try to find pipeline combobox
      const pipelineCombobox = this.page.getByRole("combobox", {
        name: /pipeline/i,
      });

      let pipelineSelector = pipelineCombobox;

      // Check if combobox is visible, otherwise try dropdown
      if (!(await pipelineCombobox.isVisible().catch(() => false))) {
        if (await pipelineDropdown.isVisible().catch(() => false)) {
          pipelineSelector = pipelineDropdown;
        } else {
          console.log("[ConnectorConfigHelper] Pipeline selector not found, skipping");
          return undefined;
        }
      }

      await pipelineSelector.click();
      await this.page.waitForTimeout(1000);

      // Determine which pipeline to select
      let pipelineToSelect: string | undefined;

      if (config.pipelineId) {
        pipelineToSelect = config.pipelineId;
      } else if (config.pipelineName) {
        pipelineToSelect = config.pipelineName;
      } else if (config.providerType) {
        // Get pipeline name based on provider type
        const metadata = PROVIDER_METADATA[config.providerType];
        pipelineToSelect = metadata.displayName;
      }

      if (pipelineToSelect) {
        // Try to find and select the pipeline option
        const pipelineOption = this.page.getByRole("option", {
          name: new RegExp(pipelineToSelect, "i"),
        });

        if (await pipelineOption.isVisible().catch(() => false)) {
          await pipelineOption.click();
          console.log(`[ConnectorConfigHelper] Selected pipeline: ${pipelineToSelect}`);
          return pipelineToSelect;
        } else {
          // Try text-based selection
          const textOption = this.page.getByText(pipelineToSelect, {
            exact: false,
          });
          if (await textOption.isVisible().catch(() => false)) {
            await textOption.click();
            console.log(`[ConnectorConfigHelper] Selected pipeline by text: ${pipelineToSelect}`);
            return pipelineToSelect;
          }
        }
      }

      // If no specific pipeline, select the first available
      const firstOption = this.page.getByRole("option").first();
      if (await firstOption.isVisible().catch(() => false)) {
        const optionText = await firstOption.textContent();
        await firstOption.click();
        console.log(`[ConnectorConfigHelper] Selected first available pipeline: ${optionText}`);
        return optionText || undefined;
      }

      console.log("[ConnectorConfigHelper] No pipeline options available");
      return undefined;
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error selecting pipeline:`, error.message);
      return undefined;
    }
  }

  /**
   * Configure advanced settings for connector
   *
   * @param options - Advanced configuration options
   */
  private async configureAdvancedSettings(options: { allowUploads?: boolean }): Promise<void> {
    try {
      // Click the "ADVANCED CONFIGURATION" toggle button
      const advancedButton = this.page.getByRole("button", {
        name: "ADVANCED CONFIGURATION",
      });

      if (await advancedButton.isVisible().catch(() => false)) {
        await advancedButton.click();
        await this.page.waitForTimeout(1000);

        if (options.allowUploads) {
          const allowUploadsCheckbox = this.page.getByRole("checkbox", {
            name: /allow uploads/i,
          });

          if (await allowUploadsCheckbox.isVisible().catch(() => false)) {
            const isChecked = await allowUploadsCheckbox.isChecked();
            if (!isChecked) {
              await allowUploadsCheckbox.check();
              console.log("[ConnectorConfigHelper] Enabled Allow Uploads checkbox");
            }
          }
        }
      }
    } catch (error: any) {
      console.log(`[ConnectorConfigHelper] Advanced settings not available: ${error.message}`);
    }
  }

  /**
   * Save connector configuration
   *
   * @requirements 4.4
   */
  async saveConnectorConfiguration(): Promise<boolean> {
    console.log("[ConnectorConfigHelper] Saving connector configuration");

    try {
      const saveButton = this.page.getByRole("button", {
        name: /Save|Add Connector/i,
      });
      await saveButton.click();
      await this.page.waitForTimeout(2000);

      console.log("[ConnectorConfigHelper] Connector configuration saved");
      return true;
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error saving configuration:`, error.message);
      return false;
    }
  }

  /**
   * Verify connector is configured with pipeline association
   *
   * @param connectorName - Name of the connector to verify
   * @returns Verification result
   * @requirements 4.5
   */
  async verifyConnectorConfigured(connectorName: string): Promise<ConnectorVerificationResult> {
    console.log(`[ConnectorConfigHelper] Verifying connector: ${connectorName}`);

    try {
      // Navigate to connectors page if not already there
      await this.navigateToConnectorConfiguration();

      // Wait for connectors to load
      await this.page.waitForTimeout(5000);

      // Find the connector card
      const connectorCards = getConnectorCards(this.page);
      const connectorCard = connectorCards.filter({
        has: this.page.locator(`h5:has-text("${connectorName}")`),
      });

      const isVisible = await connectorCard.isVisible().catch(() => false);

      if (!isVisible) {
        console.log(`[ConnectorConfigHelper] Connector not found: ${connectorName}`);
        return {
          isConfigured: false,
          connectorName,
        };
      }

      // Get connector details
      const cardText = await connectorCard.textContent();

      // Try to extract pipeline information from the card
      let pipelineName: string | undefined;
      let pipelineId: string | undefined;

      // Look for pipeline info in the card
      const pipelineInfo = this.page.locator(`[data-testid^="connector-pipeline-"]`);
      if (await pipelineInfo.isVisible().catch(() => false)) {
        pipelineName = (await pipelineInfo.textContent()) || undefined;
      }

      console.log(`[ConnectorConfigHelper] ✅ Connector verified: ${connectorName}`);

      return {
        isConfigured: true,
        connectorName,
        pipelineName,
        pipelineId,
        status: "configured",
      };
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error verifying connector:`, error.message);

      return {
        isConfigured: false,
        connectorName,
      };
    }
  }

  /**
   * Get connector configuration details
   *
   * @param connectorName - Name of the connector
   * @returns Connector configuration details
   */
  async getConnectorConfiguration(connectorName: string): Promise<ConnectorConfig | null> {
    console.log(`[ConnectorConfigHelper] Getting configuration for: ${connectorName}`);

    try {
      // Navigate to connectors page
      await this.navigateToConnectorConfiguration();
      await this.page.waitForTimeout(3000);

      // Find and click on the connector to open details
      const connectorCards = getConnectorCards(this.page);
      const connectorCard = connectorCards.filter({
        has: this.page.locator(`h5:has-text("${connectorName}")`),
      });

      if (!(await connectorCard.isVisible().catch(() => false))) {
        console.log(`[ConnectorConfigHelper] Connector not found: ${connectorName}`);
        return null;
      }

      // Click on the connector card to open details/edit
      await connectorCard.click();
      await this.page.waitForTimeout(2000);

      // Extract configuration from the UI
      const config: ConnectorConfig = {
        name: connectorName,
      };

      // Try to get description
      const descInput = this.page.getByRole("textbox", {
        name: /Description/i,
      });
      if (await descInput.isVisible().catch(() => false)) {
        config.description = (await descInput.inputValue()) || undefined;
      }

      // Try to get pipeline info
      const pipelineCombobox = this.page.getByRole("combobox", {
        name: /pipeline/i,
      });
      if (await pipelineCombobox.isVisible().catch(() => false)) {
        const pipelineValue = await pipelineCombobox.textContent();
        config.pipelineName = pipelineValue || undefined;
      }

      console.log(`[ConnectorConfigHelper] Retrieved configuration for: ${connectorName}`);

      return config;
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error getting configuration:`, error.message);
      return null;
    }
  }

  /**
   * Update connector pipeline association
   *
   * @param connectorName - Name of the connector to update
   * @param pipelineId - New pipeline ID to associate
   * @returns Whether update was successful
   */
  async updateConnectorPipeline(connectorName: string, pipelineId: string): Promise<boolean> {
    console.log(`[ConnectorConfigHelper] Updating pipeline for connector: ${connectorName}`);

    try {
      // Navigate to connectors page
      await this.navigateToConnectorConfiguration();
      await this.page.waitForTimeout(3000);

      // Find and click on the connector to open edit
      const connectorCards = getConnectorCards(this.page);
      const connectorCard = connectorCards.filter({
        has: this.page.locator(`h5:has-text("${connectorName}")`),
      });

      if (!(await connectorCard.isVisible().catch(() => false))) {
        console.log(`[ConnectorConfigHelper] Connector not found: ${connectorName}`);
        return false;
      }

      // Look for edit button on the card
      const editButton = connectorCard.locator(
        '[data-testid^="connector-edit-"], button:has-text("Edit")'
      );

      if (await editButton.isVisible().catch(() => false)) {
        await editButton.click();
        await this.page.waitForTimeout(1000);
      } else {
        // Click on the card itself to open edit
        await connectorCard.click();
        await this.page.waitForTimeout(1000);
      }

      // Select new pipeline
      await this.selectPipelineForConnector({ pipelineId });

      // Save changes
      await this.saveConnectorConfiguration();

      console.log(`[ConnectorConfigHelper] ✅ Pipeline updated for connector: ${connectorName}`);
      return true;
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error updating pipeline:`, error.message);
      return false;
    }
  }

  /**
   * Delete a connector
   *
   * @param connectorName - Name of the connector to delete
   * @returns Whether deletion was successful
   */
  async deleteConnector(connectorName: string): Promise<boolean> {
    return await deleteConnector(this.page, connectorName, this.timeout);
  }

  /**
   * Get list of available pipelines for connector configuration
   *
   * @returns Array of available pipeline names
   */
  async getAvailablePipelines(): Promise<string[]> {
    console.log("[ConnectorConfigHelper] Getting available pipelines");

    const pipelines: string[] = [];

    try {
      // Look for pipeline dropdown
      const pipelineCombobox = this.page.getByRole("combobox", {
        name: /pipeline/i,
      });

      if (await pipelineCombobox.isVisible().catch(() => false)) {
        await pipelineCombobox.click();
        await this.page.waitForTimeout(1000);

        // Get all options
        const options = this.page.getByRole("option");
        const count = await options.count();

        for (let i = 0; i < count; i++) {
          const optionText = await options.nth(i).textContent();
          if (optionText) {
            pipelines.push(optionText.trim());
          }
        }

        // Close dropdown
        await this.page.keyboard.press("Escape");
      }

      console.log(`[ConnectorConfigHelper] Found ${pipelines.length} available pipelines`);
    } catch (error: any) {
      console.error(`[ConnectorConfigHelper] Error getting pipelines:`, error.message);
    }

    return pipelines;
  }

  /**
   * Capture error screenshot
   *
   * @param name - Screenshot name prefix
   */
  private async captureErrorScreenshot(name: string): Promise<void> {
    try {
      await this.page.screenshot({
        path: `test-results/${name}.png`,
        fullPage: true,
      });
      console.log(`[ConnectorConfigHelper] Error screenshot saved to test-results/${name}.png`);
    } catch {
      console.error("[ConnectorConfigHelper] Failed to capture error screenshot");
    }
  }
}

/**
 * Content ingestion result
 */
export interface IngestionResult {
  /** Whether ingestion was triggered successfully */
  success: boolean;
  /** Number of files uploaded */
  filesUploaded: number;
  /** List of uploaded file paths */
  uploadedFiles: string[];
  /** Error message if failed */
  error?: string;
}

/**
 * Ingestion status
 */
export interface IngestionStatus {
  /** Whether assets are indexed and searchable */
  isComplete: boolean;
  /** Number of assets found in search */
  assetsFound: number;
  /** Number of assets with loaded thumbnails */
  assetsWithThumbnails: number;
  /** Whether all thumbnails are loaded */
  allThumbnailsLoaded: boolean;
}

/**
 * Ingestion options
 */
export interface IngestionOptions {
  /** Timeout for upload operations in ms (default: 180000 - 3 minutes) */
  uploadTimeout?: number;
  /** Timeout for waiting for indexing in ms (default: 120000 - 2 minutes) */
  indexingTimeout?: number;
  /** Timeout for waiting for thumbnails in ms (default: 120000 - 2 minutes) */
  thumbnailTimeout?: number;
  /** Interval for polling status in ms (default: 5000) */
  pollInterval?: number;
  /** Whether to capture screenshots during ingestion (default: false) */
  captureScreenshots?: boolean;
  /** Screenshot directory (default: "test-results") */
  screenshotDir?: string;
  /** Search query to use for verification (default: "*") */
  searchQuery?: string;
  /** Whether to use semantic search (default: false for faster verification) */
  useSemanticSearch?: boolean;
}

/**
 * Helper class for content ingestion operations
 *
 * Provides methods for triggering content ingestion through connectors,
 * monitoring ingestion progress, and verifying assets are searchable.
 *
 * @requirements 5.1, 5.2, 5.3, 5.4, 5.5
 */
export class ContentIngestionHelper {
  private page: Page;
  private baseUrl: string;
  private timeout: number;

  constructor(page: Page, baseUrl: string = "", timeout: number = 30000) {
    this.page = page;
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  /**
   * Trigger content ingestion by uploading files through the UI
   *
   * This method uploads files via the upload modal, which triggers
   * the connector's pipeline to process and index the assets.
   *
   * @param filePaths - Array of file paths to upload
   * @param connectorName - Name of the connector to use (optional, uses first available if not specified)
   * @param options - Ingestion options
   * @returns Ingestion result
   * @requirements 5.1, 5.2
   */
  async triggerIngestion(
    filePaths: string[],
    connectorName?: string,
    options: IngestionOptions = {}
  ): Promise<IngestionResult> {
    const {
      uploadTimeout = 180000,
      captureScreenshots = false,
      screenshotDir = "test-results",
    } = options;

    console.log(`[ContentIngestionHelper] Triggering ingestion for ${filePaths.length} file(s)`);

    if (connectorName) {
      console.log(`[ContentIngestionHelper] Using connector: ${connectorName}`);
    }

    try {
      // Navigate to home/dashboard to access upload button
      await this.page.goto(this.baseUrl, {
        waitUntil: "domcontentloaded",
        timeout: this.timeout,
      });
      await this.page.waitForLoadState("domcontentloaded");
      await this.page.waitForTimeout(2000);

      // Find and click upload button to open modal
      const uploadButton = this.page.getByTestId("CloudUploadIcon");
      const buttonExists = (await uploadButton.count()) > 0;

      if (!buttonExists) {
        console.error("[ContentIngestionHelper] Upload button not found");
        return {
          success: false,
          filesUploaded: 0,
          uploadedFiles: [],
          error: "Upload button not found on page",
        };
      }

      await uploadButton.click();
      console.log("[ContentIngestionHelper] Opened upload modal");
      await this.page.waitForTimeout(1000);

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "ingestion-modal-opened");
      }

      // Select connector from dropdown
      console.log("[ContentIngestionHelper] Selecting connector");
      const connectorCombobox = this.page.getByRole("combobox", {
        name: "S3 Connector",
      });
      await connectorCombobox.waitFor({ state: "visible", timeout: 5000 });
      await connectorCombobox.click();
      await this.page.waitForTimeout(1500);

      if (connectorName) {
        // Select specific connector
        const targetOption = this.page.getByRole("option", {
          name: new RegExp(connectorName, "i"),
        });
        await targetOption.click();
        console.log(`[ContentIngestionHelper] Selected connector: ${connectorName}`);
      } else {
        // Select first enabled connector
        const allOptions = this.page.getByRole("option");
        const optionCount = await allOptions.count();
        let selectedConnector = false;

        for (let i = 0; i < optionCount; i++) {
          const option = allOptions.nth(i);
          const isDisabled = await option.getAttribute("aria-disabled");

          if (isDisabled !== "true") {
            const optionText = await option.textContent();
            console.log(
              `[ContentIngestionHelper] Selecting first enabled connector: ${optionText}`
            );
            await option.click();
            selectedConnector = true;
            break;
          }
        }

        if (!selectedConnector) {
          throw new Error("No enabled connectors found in dropdown");
        }
      }

      await this.page.waitForTimeout(1500);

      // Add files to Uppy input
      console.log("[ContentIngestionHelper] Adding files to upload");
      const uppyFileInput = this.page
        .locator('.uppy-Dashboard-input[type="file"][multiple]')
        .first();
      await uppyFileInput.waitFor({ state: "attached", timeout: 5000 });
      await uppyFileInput.setInputFiles(filePaths);

      // Wait for Uppy to process files
      await this.page.waitForTimeout(4000);

      // Verify files were added
      const fileItems = this.page.locator(".uppy-Dashboard-Item");
      const fileItemCount = await fileItems.count();
      console.log(`[ContentIngestionHelper] Files in Uppy dashboard: ${fileItemCount}`);

      if (fileItemCount === 0) {
        throw new Error("Files were rejected by Uppy. Ensure files are valid media types.");
      }

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "ingestion-files-added");
      }

      // Click upload button
      const uploadSubmitButton = this.page.locator(".uppy-StatusBar-actionBtn--upload").first();
      await uploadSubmitButton.waitFor({ state: "visible", timeout: 15000 });
      await uploadSubmitButton.click();
      console.log("[ContentIngestionHelper] Upload submitted");

      // Wait for upload to complete
      const startTime = Date.now();
      let uploadComplete = false;

      while (Date.now() - startTime < uploadTimeout && !uploadComplete) {
        const uploadingIndicator = this.page.locator("text=/Uploading/i").first();
        const uploadingCount = await uploadingIndicator.count();

        if (uploadingCount === 0) {
          console.log("[ContentIngestionHelper] Upload complete");
          uploadComplete = true;
          break;
        }

        await this.page.waitForTimeout(2000);
      }

      if (!uploadComplete) {
        console.warn("[ContentIngestionHelper] Upload may still be in progress after timeout");
      }

      // Wait for backend processing
      await this.page.waitForTimeout(5000);

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "ingestion-upload-complete");
      }

      console.log(`[ContentIngestionHelper] ✅ Ingestion triggered for ${fileItemCount} file(s)`);

      return {
        success: true,
        filesUploaded: fileItemCount,
        uploadedFiles: filePaths,
      };
    } catch (error: any) {
      console.error(`[ContentIngestionHelper] ❌ Ingestion failed: ${error.message}`);

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "ingestion-error");
      }

      return {
        success: false,
        filesUploaded: 0,
        uploadedFiles: [],
        error: error.message,
      };
    }
  }

  /**
   * Wait for ingestion to complete by checking if assets are indexed
   *
   * This method polls the search page to verify that uploaded assets
   * have been processed and are searchable.
   *
   * @param options - Ingestion options
   * @returns Ingestion status
   * @requirements 5.3, 5.4
   */
  async waitForIngestionComplete(options: IngestionOptions = {}): Promise<IngestionStatus> {
    const {
      indexingTimeout = 120000,
      pollInterval = 5000,
      captureScreenshots = false,
      screenshotDir = "test-results",
      searchQuery = "*",
      useSemanticSearch = false,
    } = options;

    console.log(
      `[ContentIngestionHelper] Waiting for ingestion to complete (timeout: ${indexingTimeout}ms)`
    );

    const searchUrl = `${this.baseUrl}/search?q=${encodeURIComponent(
      searchQuery
    )}&semantic=${useSemanticSearch}`;
    const startTime = Date.now();
    let assetsFound = 0;

    while (Date.now() - startTime < indexingTimeout) {
      try {
        // Navigate to search page
        await this.page.goto(searchUrl, {
          waitUntil: "domcontentloaded",
          timeout: this.timeout,
        });
        await this.page.waitForLoadState("domcontentloaded");
        await this.page.waitForTimeout(2000);

        // Check for asset cards
        const assetCards = this.page.locator('[data-testid^="asset-card-"]');
        assetsFound = await assetCards.count();

        const elapsed = Math.round((Date.now() - startTime) / 1000);
        console.log(`[ContentIngestionHelper] Assets found: ${assetsFound} (${elapsed}s elapsed)`);

        if (assetsFound > 0) {
          console.log(`[ContentIngestionHelper] ✅ Assets indexed and searchable`);

          if (captureScreenshots) {
            await this.captureScreenshot(screenshotDir, "ingestion-indexed");
          }

          return {
            isComplete: true,
            assetsFound,
            assetsWithThumbnails: 0,
            allThumbnailsLoaded: false,
          };
        }

        // Wait before next poll
        await this.page.waitForTimeout(pollInterval);
      } catch (error: any) {
        console.warn(`[ContentIngestionHelper] Error checking indexing status: ${error.message}`);
        await this.page.waitForTimeout(pollInterval);
      }
    }

    console.warn(`[ContentIngestionHelper] ⚠️ Indexing timeout - assets may not be indexed yet`);

    return {
      isComplete: false,
      assetsFound,
      assetsWithThumbnails: 0,
      allThumbnailsLoaded: false,
    };
  }

  /**
   * Wait for thumbnails to load for all indexed assets
   *
   * This method waits until all asset thumbnails are loaded,
   * indicating that processing is fully complete.
   *
   * @param options - Ingestion options
   * @returns Ingestion status with thumbnail information
   * @requirements 5.3
   */
  async waitForThumbnailsLoaded(options: IngestionOptions = {}): Promise<IngestionStatus> {
    const {
      thumbnailTimeout = 120000,
      pollInterval = 5000,
      captureScreenshots = false,
      screenshotDir = "test-results",
      searchQuery = "*",
      useSemanticSearch = false,
    } = options;

    console.log(
      `[ContentIngestionHelper] Waiting for thumbnails to load (timeout: ${thumbnailTimeout}ms)`
    );

    const searchUrl = `${this.baseUrl}/search?q=${encodeURIComponent(
      searchQuery
    )}&semantic=${useSemanticSearch}`;
    const startTime = Date.now();

    // First ensure we're on the search page
    await this.page.goto(searchUrl, {
      waitUntil: "domcontentloaded",
      timeout: this.timeout,
    });
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForTimeout(2000);

    while (Date.now() - startTime < thumbnailTimeout) {
      // Count total assets
      const assetCards = this.page.locator('[data-testid^="asset-card-"]');
      const totalAssets = await assetCards.count();

      if (totalAssets === 0) {
        console.log("[ContentIngestionHelper] No assets found yet");
        await this.page.waitForTimeout(pollInterval);
        continue;
      }

      // Count placeholder images (not yet loaded)
      const placeholderImages = this.page.locator('img[src^="data:image/svg+xml;base64,"]');
      const placeholderCount = await placeholderImages.count();
      const loadedCount = totalAssets - placeholderCount;

      const elapsed = Math.round((Date.now() - startTime) / 1000);
      console.log(
        `[ContentIngestionHelper] Thumbnails: ${loadedCount}/${totalAssets} loaded (${elapsed}s elapsed)`
      );

      if (placeholderCount === 0) {
        console.log(`[ContentIngestionHelper] ✅ All thumbnails loaded`);

        if (captureScreenshots) {
          await this.captureScreenshot(screenshotDir, "ingestion-thumbnails-loaded");
        }

        return {
          isComplete: true,
          assetsFound: totalAssets,
          assetsWithThumbnails: loadedCount,
          allThumbnailsLoaded: true,
        };
      }

      // Refresh page periodically to trigger thumbnail updates
      if (elapsed > 0 && elapsed % 15 === 0) {
        console.log("[ContentIngestionHelper] Refreshing page to trigger thumbnail updates");
        await this.page.reload({ waitUntil: "domcontentloaded" });
        await this.page.waitForTimeout(2000);
      } else {
        await this.page.waitForTimeout(pollInterval);
      }
    }

    // Final count
    const assetCards = this.page.locator('[data-testid^="asset-card-"]');
    const totalAssets = await assetCards.count();
    const placeholderImages = this.page.locator('img[src^="data:image/svg+xml;base64,"]');
    const placeholderCount = await placeholderImages.count();
    const loadedCount = totalAssets - placeholderCount;

    console.warn(
      `[ContentIngestionHelper] ⚠️ Thumbnail timeout - ${loadedCount}/${totalAssets} loaded`
    );

    return {
      isComplete: false,
      assetsFound: totalAssets,
      assetsWithThumbnails: loadedCount,
      allThumbnailsLoaded: placeholderCount === 0,
    };
  }

  /**
   * Verify that specific assets are searchable
   *
   * @param assetIds - Array of asset IDs to verify (optional)
   * @param minAssetCount - Minimum number of assets expected (default: 1)
   * @param options - Ingestion options
   * @returns Whether verification passed
   * @requirements 5.4
   */
  async verifyAssetsSearchable(
    assetIds?: string[],
    minAssetCount: number = 1,
    options: IngestionOptions = {}
  ): Promise<boolean> {
    const {
      searchQuery = "*",
      useSemanticSearch = false,
      captureScreenshots = false,
      screenshotDir = "test-results",
    } = options;

    console.log(`[ContentIngestionHelper] Verifying assets are searchable (min: ${minAssetCount})`);

    const searchUrl = `${this.baseUrl}/search?q=${encodeURIComponent(
      searchQuery
    )}&semantic=${useSemanticSearch}`;

    try {
      await this.page.goto(searchUrl, {
        waitUntil: "domcontentloaded",
        timeout: this.timeout,
      });
      await this.page.waitForLoadState("domcontentloaded");
      await this.page.waitForTimeout(3000);

      // Count assets
      const assetCards = this.page.locator('[data-testid^="asset-card-"]');
      const assetCount = await assetCards.count();

      console.log(`[ContentIngestionHelper] Found ${assetCount} searchable assets`);

      if (assetCount < minAssetCount) {
        console.error(
          `[ContentIngestionHelper] ❌ Expected at least ${minAssetCount} assets, found ${assetCount}`
        );

        if (captureScreenshots) {
          await this.captureScreenshot(screenshotDir, "verify-assets-failed");
        }

        return false;
      }

      // If specific asset IDs provided, verify they exist
      if (assetIds && assetIds.length > 0) {
        for (const assetId of assetIds) {
          const assetCard = this.page.locator(`[data-testid="asset-card-${assetId}"]`);
          const exists = (await assetCard.count()) > 0;

          if (!exists) {
            console.error(`[ContentIngestionHelper] ❌ Asset not found: ${assetId}`);
            return false;
          }

          console.log(`[ContentIngestionHelper] ✓ Asset found: ${assetId}`);
        }
      }

      console.log(`[ContentIngestionHelper] ✅ Asset verification passed`);

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "verify-assets-passed");
      }

      return true;
    } catch (error: any) {
      console.error(`[ContentIngestionHelper] ❌ Verification failed: ${error.message}`);

      if (captureScreenshots) {
        await this.captureScreenshot(screenshotDir, "verify-assets-error");
      }

      return false;
    }
  }

  /**
   * Complete ingestion workflow: trigger, wait for indexing, and verify
   *
   * This is a convenience method that combines all ingestion steps.
   *
   * @param filePaths - Array of file paths to upload
   * @param connectorName - Name of the connector to use
   * @param options - Ingestion options
   * @returns Final ingestion status
   * @requirements 5.1, 5.2, 5.3, 5.4, 5.5
   */
  async ingestAndVerify(
    filePaths: string[],
    connectorName?: string,
    options: IngestionOptions = {}
  ): Promise<IngestionStatus & { uploadResult: IngestionResult }> {
    console.log(
      `[ContentIngestionHelper] Starting complete ingestion workflow for ${filePaths.length} file(s)`
    );

    // Step 1: Trigger ingestion
    const uploadResult = await this.triggerIngestion(filePaths, connectorName, options);

    if (!uploadResult.success) {
      return {
        isComplete: false,
        assetsFound: 0,
        assetsWithThumbnails: 0,
        allThumbnailsLoaded: false,
        uploadResult,
      };
    }

    // Step 2: Wait for indexing
    const indexingStatus = await this.waitForIngestionComplete(options);

    if (!indexingStatus.isComplete) {
      return {
        ...indexingStatus,
        uploadResult,
      };
    }

    // Step 3: Wait for thumbnails (optional but recommended)
    const thumbnailStatus = await this.waitForThumbnailsLoaded(options);

    return {
      ...thumbnailStatus,
      uploadResult,
    };
  }

  /**
   * Capture screenshot helper
   */
  private async captureScreenshot(dir: string, name: string): Promise<void> {
    try {
      const fs = await import("fs");
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      await this.page.screenshot({
        path: `${dir}/${name}.png`,
        fullPage: true,
      });
      console.log(`[ContentIngestionHelper] Screenshot saved: ${dir}/${name}.png`);
    } catch (error) {
      console.warn("[ContentIngestionHelper] Failed to capture screenshot");
    }
  }
}
