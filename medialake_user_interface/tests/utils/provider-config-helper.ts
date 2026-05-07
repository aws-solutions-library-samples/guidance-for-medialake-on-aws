/**
 * Provider Configuration Helper for Playwright Tests
 *
 * Provides reusable utilities for configuring semantic search providers in E2E tests.
 * Supports TwelveLabs (API and Bedrock variants) and Coactive AI providers.
 *
 * @requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 2.1, 2.2, 2.3
 */

import { Page, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * Error types for provider configuration
 */
export enum ProviderConfigErrorType {
  NAVIGATION_FAILED = "NAVIGATION_FAILED",
  PROVIDER_SELECTION_FAILED = "PROVIDER_SELECTION_FAILED",
  API_KEY_INPUT_FAILED = "API_KEY_INPUT_FAILED", // pragma: allowlist secret
  SAVE_FAILED = "SAVE_FAILED",
  VERIFICATION_FAILED = "VERIFICATION_FAILED",
  TIMEOUT = "TIMEOUT",
  UNKNOWN = "UNKNOWN",
}

/**
 * Custom error class for provider configuration failures
 */
export class ProviderConfigError extends Error {
  public readonly errorType: ProviderConfigErrorType;
  public readonly providerType: ProviderType | null;
  public readonly screenshotPath: string | null;
  public readonly diagnostics: Record<string, unknown>;

  constructor(
    message: string,
    errorType: ProviderConfigErrorType,
    providerType: ProviderType | null = null,
    screenshotPath: string | null = null,
    diagnostics: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "ProviderConfigError";
    this.errorType = errorType;
    this.providerType = providerType;
    this.screenshotPath = screenshotPath;
    this.diagnostics = diagnostics;
  }

  /**
   * Get a formatted diagnostic message
   */
  getDiagnosticMessage(): string {
    const lines = [
      `Provider Configuration Error: ${this.message}`,
      `Error Type: ${this.errorType}`,
    ];

    if (this.providerType) {
      lines.push(`Provider: ${this.providerType}`);
    }

    if (this.screenshotPath) {
      lines.push(`Screenshot: ${this.screenshotPath}`);
    }

    if (Object.keys(this.diagnostics).length > 0) {
      lines.push(`Diagnostics: ${JSON.stringify(this.diagnostics, null, 2)}`);
    }

    return lines.join("\n");
  }
}

/**
 * Provider types supported by MediaLake
 */
export type ProviderType =
  | "twelvelabs-api"
  | "twelvelabs-bedrock"
  | "twelvelabs-bedrock-3-0"
  | "coactive";

/**
 * Embedding store types
 */
export type EmbeddingStoreType = "opensearch" | "s3-vector" | "native";

/**
 * Provider configuration interface
 */
export interface ProviderConfig {
  type: ProviderType;
  name: string;
  dimensions?: number;
  apiKey?: string;
  endpoint?: string;
}

/**
 * Embedding store configuration interface
 */
export interface EmbeddingStoreConfig {
  type: EmbeddingStoreType;
  isEnabled: boolean;
}

/**
 * Provider metadata with display names and requirements
 */
export const PROVIDER_METADATA: Record<
  ProviderType,
  {
    displayName: string;
    dimensions: number;
    requiresApiKey: boolean;
    isExternal: boolean;
    apiKeyEnvVar?: string;
  }
> = {
  "twelvelabs-api": {
    displayName: "TwelveLabs Marengo 2.7 API",
    dimensions: 1024,
    requiresApiKey: true,
    isExternal: false,
    apiKeyEnvVar: "TWELVELABS_API_KEY", // pragma: allowlist secret
  },
  "twelvelabs-bedrock": {
    displayName: "TwelveLabs Marengo 2.7 Bedrock",
    dimensions: 1024,
    requiresApiKey: false,
    isExternal: false,
  },
  "twelvelabs-bedrock-3-0": {
    displayName: "TwelveLabs Marengo 3.0 Bedrock",
    dimensions: 512,
    requiresApiKey: false,
    isExternal: false,
  },
  coactive: {
    displayName: "Coactive AI",
    dimensions: 1024,
    requiresApiKey: true,
    isExternal: true,
    apiKeyEnvVar: "COACTIVE_API_KEY", // pragma: allowlist secret
  },
};

/**
 * Helper class for configuring semantic search providers
 */
export class ProviderConfigHelper {
  private page: Page;
  private timeout: number;

  constructor(page: Page, timeout: number = 30000) {
    this.page = page;
    this.timeout = timeout;
  }

  /**
   * Navigate to System Settings page
   */
  async navigateToSystemSettings(): Promise<void> {
    console.log("[ProviderConfigHelper] Navigating to System Settings");

    // Click Settings button in sidebar
    await this.page.getByRole("button", { name: "Settings" }).click();
    await this.page.waitForTimeout(500);

    // Click System Settings
    await this.page.getByRole("button", { name: "System Settings" }).click();

    // Wait for settings panel to be visible
    await expect(this.page.locator("#settings-tabpanel-0")).toBeVisible({
      timeout: this.timeout,
    });

    console.log("[ProviderConfigHelper] System Settings page loaded");
  }

  /**
   * Select a provider from the available options
   */
  async selectProvider(providerType: ProviderType): Promise<void> {
    const metadata = PROVIDER_METADATA[providerType];
    console.log(`[ProviderConfigHelper] Selecting provider: ${metadata.displayName}`);

    // Click Edit Provider button to open provider selection
    await this.page.getByRole("button", { name: /Edit Provider/i }).click();
    await this.page.waitForTimeout(1000);

    // Select the provider from dropdown or list
    // The exact selector depends on the UI implementation
    const providerOption = this.page.getByText(metadata.displayName, {
      exact: false,
    });
    if (await providerOption.isVisible()) {
      await providerOption.click();
    }

    console.log(`[ProviderConfigHelper] Provider selected: ${providerType}`);
  }

  /**
   * Configure a provider with the given settings
   */
  async configureProvider(config: ProviderConfig): Promise<void> {
    const metadata = PROVIDER_METADATA[config.type];
    console.log(`[ProviderConfigHelper] Configuring provider: ${metadata.displayName}`);

    // If provider requires API key, fill it in
    if (metadata.requiresApiKey && config.apiKey) {
      const apiKeyInput = this.page.getByRole("textbox", { name: "API Key" });
      await apiKeyInput.waitFor({ state: "visible", timeout: this.timeout });
      await apiKeyInput.fill(config.apiKey);
      console.log("[ProviderConfigHelper] API key entered");
    }

    // If endpoint is provided, fill it in
    if (config.endpoint) {
      const endpointInput = this.page.getByRole("textbox", {
        name: /endpoint/i,
      });
      if (await endpointInput.isVisible()) {
        await endpointInput.fill(config.endpoint);
        console.log("[ProviderConfigHelper] Endpoint entered");
      }
    }

    console.log(`[ProviderConfigHelper] Provider configured: ${config.type}`);
  }

  /**
   * Select an embedding store for internal providers
   */
  async selectEmbeddingStore(store: EmbeddingStoreConfig): Promise<void> {
    console.log(`[ProviderConfigHelper] Selecting embedding store: ${store.type}`);

    // External providers use native storage, no selection needed
    if (store.type === "native") {
      console.log(
        "[ProviderConfigHelper] External provider uses native storage, skipping selection"
      );
      return;
    }

    // Find and select the embedding store option
    const storeLabel = store.type === "opensearch" ? "OpenSearch" : "S3 Vectors";
    const storeOption = this.page.getByText(storeLabel, { exact: false });

    if (await storeOption.isVisible()) {
      await storeOption.click();
      console.log(`[ProviderConfigHelper] Embedding store selected: ${store.type}`);
    } else {
      console.log(`[ProviderConfigHelper] Embedding store option not visible: ${storeLabel}`);
    }
  }

  /**
   * Save the provider configuration
   */
  async saveConfiguration(): Promise<void> {
    console.log("[ProviderConfigHelper] Saving provider configuration");

    // Click Save button
    await this.page.getByRole("button", { name: "Save" }).click();

    // Wait for success message or confirmation
    await this.page.waitForTimeout(2000);

    console.log("[ProviderConfigHelper] Configuration saved");
  }

  /**
   * Verify that a provider is configured and enabled
   */
  async verifyProviderConfigured(providerType: ProviderType): Promise<boolean> {
    const metadata = PROVIDER_METADATA[providerType];
    console.log(`[ProviderConfigHelper] Verifying provider configured: ${metadata.displayName}`);

    try {
      // Check if the provider checkbox is checked
      const checkbox = this.page.locator("#settings-tabpanel-0").getByRole("checkbox");
      const isChecked = await checkbox.isChecked();

      // Check if the provider name is displayed
      const providerText = this.page.getByText(metadata.displayName, {
        exact: false,
      });
      const isVisible = await providerText.isVisible();

      const isConfigured = isChecked && isVisible;
      console.log(`[ProviderConfigHelper] Provider configured: ${isConfigured}`);
      return isConfigured;
    } catch (error) {
      console.error("[ProviderConfigHelper] Error verifying provider:", error);
      return false;
    }
  }

  /**
   * Reset the provider configuration
   */
  async resetProvider(): Promise<void> {
    console.log("[ProviderConfigHelper] Resetting provider configuration");

    try {
      // Click Reset Provider button if available
      const resetButton = this.page.getByRole("button", {
        name: /Reset Provider/i,
      });
      if (await resetButton.isVisible()) {
        await resetButton.click();
        await this.page.waitForTimeout(2000);
        console.log("[ProviderConfigHelper] Provider reset successfully");
      } else {
        console.log("[ProviderConfigHelper] Reset button not visible");
      }
    } catch (error) {
      console.error("[ProviderConfigHelper] Error resetting provider:", error);
    }
  }

  /**
   * Configure provider with retry logic and enhanced error handling
   *
   * Implements exponential backoff, screenshot capture on failure,
   * and detailed diagnostic error messages.
   *
   * @param config - Provider configuration
   * @param maxRetries - Maximum number of retry attempts (default: 2)
   * @param baseDelayMs - Base delay for exponential backoff in ms (default: 1000)
   * @throws ProviderConfigError with detailed diagnostics on failure
   */
  async configureProviderWithRetry(
    config: ProviderConfig,
    maxRetries: number = 2,
    baseDelayMs: number = 1000
  ): Promise<void> {
    const errors: Array<{ attempt: number; error: Error; timestamp: Date }> = [];
    let lastErrorType: ProviderConfigErrorType = ProviderConfigErrorType.UNKNOWN;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        console.log(
          `[ProviderConfigHelper] Configuration attempt ${attempt + 1}/${maxRetries + 1} for ${
            config.type
          }`
        );

        // Step 1: Select provider
        await this.selectProvider(config.type);

        // Step 2: Configure provider settings
        await this.configureProvider(config);

        // Step 3: Save configuration
        await this.saveConfiguration();

        // Step 4: Verify configuration was saved
        const isConfigured = await this.verifyProviderConfigured(config.type);
        if (!isConfigured) {
          throw new Error("Provider configuration verification failed after save");
        }

        console.log(
          `[ProviderConfigHelper] ✅ Provider ${config.type} configured successfully on attempt ${
            attempt + 1
          }`
        );
        return; // Success
      } catch (error: unknown) {
        const errorObj = error instanceof Error ? error : new Error(String(error));
        errors.push({
          attempt: attempt + 1,
          error: errorObj,
          timestamp: new Date(),
        });

        // Determine error type based on error message
        lastErrorType = this.categorizeError(errorObj);

        console.error(
          `[ProviderConfigHelper] ❌ Attempt ${attempt + 1} failed: ${errorObj.message}`
        );

        if (attempt === maxRetries) {
          // Final attempt failed - capture screenshot and throw detailed error
          const screenshotPath = await this.captureErrorScreenshot(config.type, attempt + 1);

          // Gather diagnostic information
          const diagnostics = await this.gatherDiagnostics(config);

          const errorMessage = this.buildErrorMessage(config, maxRetries, errors, diagnostics);

          throw new ProviderConfigError(
            errorMessage,
            lastErrorType,
            config.type,
            screenshotPath,
            diagnostics
          );
        }

        // Calculate exponential backoff delay
        const delayMs = baseDelayMs * Math.pow(2, attempt);
        console.log(`[ProviderConfigHelper] Waiting ${delayMs}ms before retry ${attempt + 2}...`);
        await this.page.waitForTimeout(delayMs);
      }
    }
  }

  /**
   * Categorize an error into a specific error type
   */
  private categorizeError(error: Error): ProviderConfigErrorType {
    const message = error.message.toLowerCase();

    if (message.includes("navigation") || message.includes("navigate")) {
      return ProviderConfigErrorType.NAVIGATION_FAILED;
    }
    if (message.includes("select") || message.includes("provider")) {
      return ProviderConfigErrorType.PROVIDER_SELECTION_FAILED;
    }
    if (message.includes("api key") || message.includes("apikey")) {
      return ProviderConfigErrorType.API_KEY_INPUT_FAILED;
    }
    if (message.includes("save") || message.includes("persist")) {
      return ProviderConfigErrorType.SAVE_FAILED;
    }
    if (message.includes("verify") || message.includes("verification")) {
      return ProviderConfigErrorType.VERIFICATION_FAILED;
    }
    if (message.includes("timeout") || message.includes("timed out")) {
      return ProviderConfigErrorType.TIMEOUT;
    }

    return ProviderConfigErrorType.UNKNOWN;
  }

  /**
   * Capture a screenshot on error
   */
  private async captureErrorScreenshot(
    providerType: ProviderType,
    attempt: number
  ): Promise<string> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const screenshotDir = "test-results";
    const screenshotPath = path.join(
      screenshotDir,
      `provider-config-error-${providerType}-attempt${attempt}-${timestamp}.png`
    );

    try {
      // Ensure directory exists
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }

      await this.page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });

      console.log(`[ProviderConfigHelper] Screenshot saved: ${screenshotPath}`);
      return screenshotPath;
    } catch (screenshotError) {
      console.error(`[ProviderConfigHelper] Failed to capture screenshot: ${screenshotError}`);
      return "";
    }
  }

  /**
   * Gather diagnostic information about the current state
   */
  private async gatherDiagnostics(config: ProviderConfig): Promise<Record<string, unknown>> {
    const diagnostics: Record<string, unknown> = {
      providerType: config.type,
      timestamp: new Date().toISOString(),
      pageUrl: this.page.url(),
    };

    try {
      // Check if settings panel is visible
      diagnostics.settingsPanelVisible = await this.page
        .locator("#settings-tabpanel-0")
        .isVisible()
        .catch(() => false);

      // Check current provider state
      const currentConfig = await this.getCurrentProviderConfig();
      diagnostics.currentProviderConfig = currentConfig;

      // Check if API key input is visible (for API providers) pragma: allowlist secret
      if (PROVIDER_METADATA[config.type].requiresApiKey) {
        diagnostics.apiKeyInputVisible = await this.isApiKeyInputVisible();
      }

      // Check for any error messages on the page
      const errorMessages = await this.page
        .locator('[class*="error"], [role="alert"], .MuiAlert-root')
        .allTextContents()
        .catch(() => []);
      if (errorMessages.length > 0) {
        diagnostics.visibleErrors = errorMessages;
      }

      // Check for success messages
      const successMessages = await this.page
        .locator('[class*="success"], .MuiAlert-standardSuccess')
        .allTextContents()
        .catch(() => []);
      if (successMessages.length > 0) {
        diagnostics.visibleSuccessMessages = successMessages;
      }
    } catch (diagError) {
      diagnostics.diagnosticError = String(diagError);
    }

    return diagnostics;
  }

  /**
   * Build a detailed error message from all attempts
   */
  private buildErrorMessage(
    config: ProviderConfig,
    maxRetries: number,
    errors: Array<{ attempt: number; error: Error; timestamp: Date }>,
    diagnostics: Record<string, unknown>
  ): string {
    const metadata = PROVIDER_METADATA[config.type];
    const lines = [
      `Failed to configure provider "${metadata.displayName}" (${config.type}) after ${
        maxRetries + 1
      } attempts.`,
      "",
      "Attempt History:",
    ];

    for (const { attempt, error, timestamp } of errors) {
      lines.push(`  Attempt ${attempt} (${timestamp.toISOString()}): ${error.message}`);
    }

    lines.push("");
    lines.push("Configuration Details:");
    lines.push(`  Provider Type: ${config.type}`);
    lines.push(`  Display Name: ${metadata.displayName}`);
    lines.push(`  Dimensions: ${metadata.dimensions}`);
    lines.push(`  Requires API Key: ${metadata.requiresApiKey}`);
    if (config.apiKey) {
      lines.push(`  API Key Provided: Yes (${config.apiKey.substring(0, 4)}...)`);
    }

    lines.push("");
    lines.push("Current Page State:");
    lines.push(`  URL: ${diagnostics.pageUrl}`);
    lines.push(`  Settings Panel Visible: ${diagnostics.settingsPanelVisible}`);

    if (diagnostics.visibleErrors) {
      lines.push("");
      lines.push("Visible Errors on Page:");
      for (const err of diagnostics.visibleErrors as string[]) {
        lines.push(`  - ${err}`);
      }
    }

    return lines.join("\n");
  }

  /**
   * Get the current provider configuration from the UI
   */
  async getCurrentProviderConfig(): Promise<{
    type: string | null;
    isEnabled: boolean;
  }> {
    console.log("[ProviderConfigHelper] Getting current provider configuration");

    try {
      const checkbox = this.page.locator("#settings-tabpanel-0").getByRole("checkbox");
      const isEnabled = await checkbox.isChecked();

      // Try to get the provider type from the UI
      let providerType: string | null = null;
      for (const [type, metadata] of Object.entries(PROVIDER_METADATA)) {
        const providerText = this.page.getByText(metadata.displayName, {
          exact: false,
        });
        if (await providerText.isVisible()) {
          providerType = type;
          break;
        }
      }

      return { type: providerType, isEnabled };
    } catch (error) {
      console.error("[ProviderConfigHelper] Error getting current config:", error);
      return { type: null, isEnabled: false };
    }
  }

  /**
   * Check if API key input is visible (for API-based providers)
   */
  async isApiKeyInputVisible(): Promise<boolean> {
    const apiKeyInput = this.page.getByRole("textbox", { name: "API Key" });
    return await apiKeyInput.isVisible();
  }

  /**
   * Check if embedding store options are visible
   */
  async areEmbeddingStoreOptionsVisible(): Promise<boolean> {
    const opensearchOption = this.page.getByText("OpenSearch", {
      exact: false,
    });
    const s3VectorOption = this.page.getByText("S3 Vectors", { exact: false });

    const opensearchVisible = await opensearchOption.isVisible();
    const s3VectorVisible = await s3VectorOption.isVisible();

    return opensearchVisible || s3VectorVisible;
  }

  /**
   * Enable or disable the provider
   */
  async setProviderEnabled(enabled: boolean): Promise<void> {
    console.log(`[ProviderConfigHelper] Setting provider enabled: ${enabled}`);

    const checkbox = this.page.locator("#settings-tabpanel-0").getByRole("checkbox");

    const isCurrentlyChecked = await checkbox.isChecked();

    if (enabled && !isCurrentlyChecked) {
      await checkbox.check();
    } else if (!enabled && isCurrentlyChecked) {
      await checkbox.uncheck();
    }

    await this.page.waitForTimeout(500);
    console.log(`[ProviderConfigHelper] Provider enabled state set to: ${enabled}`);
  }
}
