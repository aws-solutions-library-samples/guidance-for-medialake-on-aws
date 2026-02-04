/**
 * Pipeline Deployment Helper for Playwright Tests
 *
 * Provides reusable utilities for deploying and managing pipelines in E2E tests.
 * Handles pipeline deployment for configured semantic search providers.
 *
 * @requirements 3.1, 3.3, 3.4, 3.5
 */

import { Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { ProviderType, PROVIDER_METADATA } from "./provider-config-helper";
import { PipelineDeploymentResult } from "./test-config-models";

/**
 * Error types for pipeline deployment
 */
export enum PipelineDeploymentErrorType {
  NAVIGATION_FAILED = "NAVIGATION_FAILED",
  DEPLOYMENT_INITIATION_FAILED = "DEPLOYMENT_INITIATION_FAILED",
  DEPLOYMENT_TIMEOUT = "DEPLOYMENT_TIMEOUT",
  DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED",
  VERIFICATION_FAILED = "VERIFICATION_FAILED",
  UNKNOWN = "UNKNOWN",
}

/**
 * Custom error class for pipeline deployment failures
 */
export class PipelineDeploymentError extends Error {
  public readonly errorType: PipelineDeploymentErrorType;
  public readonly providerType: ProviderType | null;
  public readonly screenshotPath: string | null;
  public readonly diagnostics: Record<string, unknown>;
  public readonly deploymentLogs: string[];

  constructor(
    message: string,
    errorType: PipelineDeploymentErrorType,
    providerType: ProviderType | null = null,
    screenshotPath: string | null = null,
    diagnostics: Record<string, unknown> = {},
    deploymentLogs: string[] = []
  ) {
    super(message);
    this.name = "PipelineDeploymentError";
    this.errorType = errorType;
    this.providerType = providerType;
    this.screenshotPath = screenshotPath;
    this.diagnostics = diagnostics;
    this.deploymentLogs = deploymentLogs;
  }

  /**
   * Get a formatted diagnostic message
   */
  getDiagnosticMessage(): string {
    const lines = [`Pipeline Deployment Error: ${this.message}`, `Error Type: ${this.errorType}`];

    if (this.providerType) {
      lines.push(`Provider: ${this.providerType}`);
    }

    if (this.screenshotPath) {
      lines.push(`Screenshot: ${this.screenshotPath}`);
    }

    if (this.deploymentLogs.length > 0) {
      lines.push("Deployment Logs:");
      for (const log of this.deploymentLogs) {
        lines.push(`  ${log}`);
      }
    }

    if (Object.keys(this.diagnostics).length > 0) {
      lines.push(`Diagnostics: ${JSON.stringify(this.diagnostics, null, 2)}`);
    }

    return lines.join("\n");
  }
}

/**
 * Deployment progress tracking
 */
export interface DeploymentProgress {
  status: PipelineStatus;
  startTime: Date;
  lastCheckTime: Date;
  elapsedMs: number;
  checkCount: number;
  statusHistory: Array<{ status: PipelineStatus; timestamp: Date }>;
}

/**
 * Pipeline status types
 */
export type PipelineStatus = "pending" | "deploying" | "complete" | "failed" | "unknown";

/**
 * Pipeline information
 */
export interface PipelineInfo {
  id: string;
  name: string;
  status: PipelineStatus;
  providerType?: string;
}

/**
 * Helper class for pipeline deployment operations
 */
export class PipelineDeploymentHelper {
  private page: Page;
  private timeout: number;
  private pollInterval: number;

  constructor(page: Page, timeout: number = 300000, pollInterval: number = 10000) {
    this.page = page;
    this.timeout = timeout;
    this.pollInterval = pollInterval;
  }

  /**
   * Navigate to Pipelines page
   */
  async navigateToPipelines(): Promise<void> {
    console.log("[PipelineDeploymentHelper] Navigating to Pipelines");

    // Click Settings button in sidebar
    await this.page.getByRole("button", { name: "Settings" }).click();
    await this.page.waitForTimeout(500);

    // Click Pipelines
    await this.page.getByRole("button", { name: "Pipelines" }).click();

    // Wait for pipelines page to load
    await this.page.waitForTimeout(2000);

    console.log("[PipelineDeploymentHelper] Pipelines page loaded");
  }

  /**
   * Deploy pipelines for a specific provider
   */
  async deployPipelinesForProvider(providerType: ProviderType): Promise<PipelineDeploymentResult> {
    const metadata = PROVIDER_METADATA[providerType];
    console.log(`[PipelineDeploymentHelper] Deploying pipelines for: ${metadata.displayName}`);

    try {
      // Navigate to pipelines page
      await this.navigateToPipelines();

      // Look for deploy button or pipeline creation option
      const deployButton = this.page.getByRole("button", {
        name: /Deploy|Create Pipeline/i,
      });

      if (await deployButton.isVisible()) {
        await deployButton.click();
        await this.page.waitForTimeout(1000);
      }

      // Wait for deployment to start
      await this.page.waitForTimeout(2000);

      // Get pipeline IDs from the page
      const pipelineIds = await this.getPipelineIds();

      console.log(`[PipelineDeploymentHelper] Deployment initiated for ${providerType}`);

      return {
        success: true,
        pipelineIds,
      };
    } catch (error: any) {
      console.error(`[PipelineDeploymentHelper] Error deploying pipelines:`, error.message);

      await this.page.screenshot({
        path: `test-results/pipeline-deployment-error-${providerType}.png`,
      });

      return {
        success: false,
        pipelineIds: [],
        error: error.message,
      };
    }
  }

  /**
   * Wait for pipeline deployment to complete with enhanced timeout handling
   *
   * Implements status polling with progress tracking, diagnostic information
   * capture on timeout, and detailed error reporting.
   *
   * @param timeout - Maximum time to wait in milliseconds
   * @param providerType - Optional provider type for better error messages
   * @throws PipelineDeploymentError with detailed diagnostics on failure
   */
  async waitForDeploymentComplete(timeout?: number, providerType?: ProviderType): Promise<void> {
    const deploymentTimeout = timeout || this.timeout;
    const startTime = new Date();
    let checkCount = 0;
    const statusHistory: Array<{ status: PipelineStatus; timestamp: Date }> = [];

    console.log(
      `[PipelineDeploymentHelper] Waiting for deployment (timeout: ${deploymentTimeout}ms, poll interval: ${this.pollInterval}ms)`
    );

    while (Date.now() - startTime.getTime() < deploymentTimeout) {
      checkCount++;
      const status = await this.getDeploymentStatus();
      const now = new Date();
      const elapsedMs = now.getTime() - startTime.getTime();

      statusHistory.push({ status, timestamp: now });

      console.log(
        `[PipelineDeploymentHelper] Check #${checkCount}: Status=${status}, Elapsed=${Math.round(
          elapsedMs / 1000
        )}s`
      );

      if (status === "complete") {
        console.log(
          `[PipelineDeploymentHelper] ✅ Deployment complete after ${checkCount} checks (${Math.round(
            elapsedMs / 1000
          )}s)`
        );
        return;
      }

      if (status === "failed") {
        // Capture diagnostic information on failure
        const screenshotPath = await this.captureDeploymentScreenshot(
          providerType || "unknown",
          "failed"
        );
        const logs = await this.captureDeploymentLogs();
        const diagnostics = await this.gatherDeploymentDiagnostics(providerType, statusHistory);

        throw new PipelineDeploymentError(
          `Pipeline deployment failed after ${checkCount} status checks (${Math.round(
            elapsedMs / 1000
          )}s)`,
          PipelineDeploymentErrorType.DEPLOYMENT_FAILED,
          providerType || null,
          screenshotPath,
          diagnostics,
          logs
        );
      }

      await this.page.waitForTimeout(this.pollInterval);
    }

    // Timeout reached - capture diagnostic information
    const elapsedMs = Date.now() - startTime.getTime();
    const lastStatus = statusHistory[statusHistory.length - 1]?.status || "unknown";

    console.error(
      `[PipelineDeploymentHelper] ❌ Deployment timeout after ${checkCount} checks (${Math.round(
        elapsedMs / 1000
      )}s). Last status: ${lastStatus}`
    );

    const screenshotPath = await this.captureDeploymentScreenshot(
      providerType || "unknown",
      "timeout"
    );
    const logs = await this.captureDeploymentLogs();
    const diagnostics = await this.gatherDeploymentDiagnostics(providerType, statusHistory);

    throw new PipelineDeploymentError(
      `Pipeline deployment timeout after ${deploymentTimeout}ms (${checkCount} status checks). Last status: ${lastStatus}`,
      PipelineDeploymentErrorType.DEPLOYMENT_TIMEOUT,
      providerType || null,
      screenshotPath,
      diagnostics,
      logs
    );
  }

  /**
   * Capture a screenshot during deployment
   */
  private async captureDeploymentScreenshot(providerType: string, reason: string): Promise<string> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const screenshotDir = "test-results";
    const screenshotPath = path.join(
      screenshotDir,
      `pipeline-deployment-${reason}-${providerType}-${timestamp}.png`
    );

    try {
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }

      await this.page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });

      console.log(`[PipelineDeploymentHelper] Screenshot saved: ${screenshotPath}`);
      return screenshotPath;
    } catch (screenshotError) {
      console.error(`[PipelineDeploymentHelper] Failed to capture screenshot: ${screenshotError}`);
      return "";
    }
  }

  /**
   * Capture deployment logs from the page
   */
  private async captureDeploymentLogs(): Promise<string[]> {
    const logs: string[] = [];

    try {
      // Try to find log elements on the page
      const logElements = this.page.locator(
        '[data-testid*="log"], .deployment-log, [class*="log-entry"], .console-output'
      );
      const count = await logElements.count();

      for (let i = 0; i < Math.min(count, 50); i++) {
        const text = await logElements.nth(i).textContent();
        if (text) {
          logs.push(text.trim());
        }
      }

      // Also try to capture any status messages
      const statusMessages = await this.page
        .locator('[class*="status"], [class*="message"], [role="status"]')
        .allTextContents()
        .catch(() => []);

      for (const msg of statusMessages) {
        if (msg.trim() && !logs.includes(msg.trim())) {
          logs.push(`[Status] ${msg.trim()}`);
        }
      }

      console.log(`[PipelineDeploymentHelper] Captured ${logs.length} log entries`);
    } catch (error) {
      console.error(`[PipelineDeploymentHelper] Error capturing deployment logs: ${error}`);
    }

    return logs;
  }

  /**
   * Gather diagnostic information about the deployment
   */
  private async gatherDeploymentDiagnostics(
    providerType: ProviderType | undefined,
    statusHistory: Array<{ status: PipelineStatus; timestamp: Date }>
  ): Promise<Record<string, unknown>> {
    const diagnostics: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      pageUrl: this.page.url(),
      providerType: providerType || "unknown",
      statusCheckCount: statusHistory.length,
      statusHistory: statusHistory.map((s) => ({
        status: s.status,
        timestamp: s.timestamp.toISOString(),
      })),
    };

    try {
      // Get pipeline information
      const pipelineIds = await this.getPipelineIds();
      diagnostics.pipelineIds = pipelineIds;
      diagnostics.pipelineCount = pipelineIds.length;

      // Check for error messages on the page
      const errorMessages = await this.page
        .locator('[class*="error"], [role="alert"], .MuiAlert-standardError')
        .allTextContents()
        .catch(() => []);
      if (errorMessages.length > 0) {
        diagnostics.visibleErrors = errorMessages;
      }

      // Check for progress indicators
      const progressIndicators = await this.page
        .locator('[role="progressbar"], .MuiCircularProgress-root, .MuiLinearProgress-root')
        .count()
        .catch(() => 0);
      diagnostics.progressIndicatorsVisible = progressIndicators > 0;

      // Calculate status distribution
      const statusCounts: Record<string, number> = {};
      for (const { status } of statusHistory) {
        statusCounts[status] = (statusCounts[status] || 0) + 1;
      }
      diagnostics.statusDistribution = statusCounts;
    } catch (diagError) {
      diagnostics.diagnosticError = String(diagError);
    }

    return diagnostics;
  }

  /**
   * Get current deployment status
   */
  async getDeploymentStatus(): Promise<PipelineStatus> {
    try {
      // Check for various status indicators in the UI
      const successIndicator = this.page.getByText(/deployed|complete|active/i);
      const failedIndicator = this.page.getByText(/failed|error/i);
      const pendingIndicator = this.page.getByText(/pending|deploying|in progress/i);

      if (await successIndicator.isVisible().catch(() => false)) {
        return "complete";
      }

      if (await failedIndicator.isVisible().catch(() => false)) {
        return "failed";
      }

      if (await pendingIndicator.isVisible().catch(() => false)) {
        return "deploying";
      }

      return "unknown";
    } catch (error) {
      console.error("[PipelineDeploymentHelper] Error getting deployment status:", error);
      return "unknown";
    }
  }

  /**
   * Verify pipelines are available for a provider
   */
  async verifyPipelinesAvailable(providerType: ProviderType): Promise<boolean> {
    const metadata = PROVIDER_METADATA[providerType];
    console.log(`[PipelineDeploymentHelper] Verifying pipelines for: ${metadata.displayName}`);

    try {
      // Navigate to pipelines page
      await this.navigateToPipelines();

      // Look for pipeline cards or list items
      const pipelineCards = this.page.locator(
        '[data-testid^="pipeline-"], .pipeline-card, .pipeline-item'
      );
      const count = await pipelineCards.count();

      const available = count > 0;
      console.log(`[PipelineDeploymentHelper] Pipelines available: ${available} (count: ${count})`);

      return available;
    } catch (error) {
      console.error("[PipelineDeploymentHelper] Error verifying pipelines:", error);
      return false;
    }
  }

  /**
   * Get pipeline ID for a specific provider
   */
  async getPipelineIdForProvider(providerType: ProviderType): Promise<string | null> {
    const metadata = PROVIDER_METADATA[providerType];
    console.log(`[PipelineDeploymentHelper] Getting pipeline ID for: ${metadata.displayName}`);

    try {
      // Navigate to pipelines page
      await this.navigateToPipelines();

      // Look for pipeline that matches the provider
      const pipelineCards = this.page.locator(
        '[data-testid^="pipeline-"], .pipeline-card, .pipeline-item'
      );

      const count = await pipelineCards.count();

      for (let i = 0; i < count; i++) {
        const card = pipelineCards.nth(i);
        const text = await card.textContent();

        // Check if this pipeline is for the specified provider
        if (
          text?.toLowerCase().includes(metadata.displayName.toLowerCase()) ||
          text?.toLowerCase().includes(providerType.toLowerCase())
        ) {
          // Try to extract pipeline ID from data-testid or other attribute
          const testId = await card.getAttribute("data-testid");
          if (testId) {
            const pipelineId = testId.replace("pipeline-", "");
            console.log(`[PipelineDeploymentHelper] Found pipeline ID: ${pipelineId}`);
            return pipelineId;
          }
        }
      }

      console.log(`[PipelineDeploymentHelper] No pipeline found for ${providerType}`);
      return null;
    } catch (error) {
      console.error("[PipelineDeploymentHelper] Error getting pipeline ID:", error);
      return null;
    }
  }

  /**
   * Get all pipeline IDs from the page
   */
  async getPipelineIds(): Promise<string[]> {
    const pipelineIds: string[] = [];

    try {
      const pipelineCards = this.page.locator(
        '[data-testid^="pipeline-"], .pipeline-card, .pipeline-item'
      );
      const count = await pipelineCards.count();

      for (let i = 0; i < count; i++) {
        const card = pipelineCards.nth(i);
        const testId = await card.getAttribute("data-testid");

        if (testId) {
          const pipelineId = testId.replace("pipeline-", "");
          pipelineIds.push(pipelineId);
        }
      }

      console.log(`[PipelineDeploymentHelper] Found ${pipelineIds.length} pipeline(s)`);
    } catch (error) {
      console.error("[PipelineDeploymentHelper] Error getting pipeline IDs:", error);
    }

    return pipelineIds;
  }

  /**
   * Get pipeline information
   */
  async getPipelineInfo(): Promise<PipelineInfo[]> {
    const pipelines: PipelineInfo[] = [];

    try {
      await this.navigateToPipelines();

      const pipelineCards = this.page.locator(
        '[data-testid^="pipeline-"], .pipeline-card, .pipeline-item'
      );
      const count = await pipelineCards.count();

      for (let i = 0; i < count; i++) {
        const card = pipelineCards.nth(i);
        const testId = await card.getAttribute("data-testid");
        const text = await card.textContent();

        pipelines.push({
          id: testId?.replace("pipeline-", "") || `pipeline-${i}`,
          name: text?.substring(0, 50) || `Pipeline ${i}`,
          status: "unknown",
        });
      }

      console.log(`[PipelineDeploymentHelper] Retrieved info for ${pipelines.length} pipeline(s)`);
    } catch (error) {
      console.error("[PipelineDeploymentHelper] Error getting pipeline info:", error);
    }

    return pipelines;
  }

  /**
   * Deploy pipelines with timeout handling and comprehensive diagnostics
   *
   * This method orchestrates the full deployment workflow with enhanced
   * error handling, progress tracking, and diagnostic information capture.
   *
   * @param providerType - The provider type to deploy pipelines for
   * @param timeout - Optional timeout override in milliseconds
   * @returns PipelineDeploymentResult with success status and diagnostics
   */
  async deployPipelinesWithDiagnostics(
    providerType: ProviderType,
    timeout?: number
  ): Promise<PipelineDeploymentResult> {
    const deploymentTimeout = timeout || this.timeout;
    const startTime = new Date();

    console.log(
      `[PipelineDeploymentHelper] Starting deployment with diagnostics for ${providerType}`
    );

    try {
      // Step 1: Deploy pipelines
      const result = await this.deployPipelinesForProvider(providerType);

      if (!result.success) {
        console.error(`[PipelineDeploymentHelper] Deployment initiation failed: ${result.error}`);
        return result;
      }

      // Step 2: Wait for deployment to complete with enhanced timeout handling
      await this.waitForDeploymentComplete(deploymentTimeout, providerType);

      // Step 3: Verify pipelines are available
      const available = await this.verifyPipelinesAvailable(providerType);

      if (!available) {
        const screenshotPath = await this.captureDeploymentScreenshot(
          providerType,
          "verification-failed"
        );
        const logs = await this.captureDeploymentLogs();

        return {
          success: false,
          pipelineIds: result.pipelineIds,
          error: `Pipelines not available after deployment. Screenshot: ${screenshotPath}. Logs: ${logs.join(
            "; "
          )}`,
        };
      }

      const elapsedMs = Date.now() - startTime.getTime();
      console.log(
        `[PipelineDeploymentHelper] ✅ Deployment completed successfully in ${Math.round(
          elapsedMs / 1000
        )}s`
      );

      return {
        success: true,
        pipelineIds: result.pipelineIds,
      };
    } catch (error: unknown) {
      // Handle PipelineDeploymentError specially
      if (error instanceof PipelineDeploymentError) {
        console.error(`[PipelineDeploymentHelper] ${error.getDiagnosticMessage()}`);
        return {
          success: false,
          pipelineIds: [],
          error: error.getDiagnosticMessage(),
        };
      }

      // Handle other errors
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[PipelineDeploymentHelper] Unexpected error: ${errorMessage}`);

      const screenshotPath = await this.captureDeploymentScreenshot(
        providerType,
        "unexpected-error"
      );
      const status = await this.getDeploymentStatus();
      const logs = await this.captureDeploymentLogs();

      return {
        success: false,
        pipelineIds: [],
        error: `Deployment failed: ${errorMessage}. Last status: ${status}. Screenshot: ${screenshotPath}. Logs: ${logs
          .slice(0, 5)
          .join("; ")}`,
      };
    }
  }

  /**
   * Get deployment progress information
   */
  async getDeploymentProgress(startTime: Date): Promise<DeploymentProgress> {
    const now = new Date();
    const status = await this.getDeploymentStatus();

    return {
      status,
      startTime,
      lastCheckTime: now,
      elapsedMs: now.getTime() - startTime.getTime(),
      checkCount: 1,
      statusHistory: [{ status, timestamp: now }],
    };
  }
}
