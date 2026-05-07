/**
 * Search Helper for Playwright Tests
 *
 * Provides reusable utilities for executing semantic searches and validating results
 * in E2E tests.
 *
 * @requirements 6.1, 6.2, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.5
 */

import { Page, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { SearchResult, Clip } from "./test-config-models";

/**
 * Error types for search operations
 */
export enum SearchErrorType {
  NAVIGATION_FAILED = "NAVIGATION_FAILED",
  SEARCH_EXECUTION_FAILED = "SEARCH_EXECUTION_FAILED",
  NO_RESULTS = "NO_RESULTS",
  EXPECTED_ASSET_NOT_FOUND = "EXPECTED_ASSET_NOT_FOUND",
  PROVIDER_NOT_ENABLED = "PROVIDER_NOT_ENABLED",
  ASSETS_NOT_INGESTED = "ASSETS_NOT_INGESTED",
  TIMEOUT = "TIMEOUT",
  UNKNOWN = "UNKNOWN",
}

/**
 * Custom error class for search validation failures
 */
export class SearchValidationError extends Error {
  public readonly errorType: SearchErrorType;
  public readonly query: string | null;
  public readonly expectedAssetId: string | null;
  public readonly screenshotPath: string | null;
  public readonly diagnostics: Record<string, unknown>;

  constructor(
    message: string,
    errorType: SearchErrorType,
    query: string | null = null,
    expectedAssetId: string | null = null,
    screenshotPath: string | null = null,
    diagnostics: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "SearchValidationError";
    this.errorType = errorType;
    this.query = query;
    this.expectedAssetId = expectedAssetId;
    this.screenshotPath = screenshotPath;
    this.diagnostics = diagnostics;
  }

  /**
   * Get a formatted diagnostic message
   */
  getDiagnosticMessage(): string {
    const lines = [`Search Validation Error: ${this.message}`, `Error Type: ${this.errorType}`];

    if (this.query) {
      lines.push(`Query: "${this.query}"`);
    }

    if (this.expectedAssetId) {
      lines.push(`Expected Asset: ${this.expectedAssetId}`);
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
 * Search validation options
 */
export interface SearchValidationOptions {
  expectedAssetId?: string;
  minResultCount?: number;
  maxResultCount?: number;
  minClipCount?: number;
  confidenceThreshold?: number;
  captureScreenshotOnFailure?: boolean;
}

/**
 * Search options
 */
export interface SearchOptions {
  timeout?: number;
  waitForResults?: boolean;
  confidenceThreshold?: number;
}

/**
 * Helper class for semantic search operations
 */
export class SearchHelper {
  private page: Page;
  private timeout: number;

  constructor(page: Page, timeout: number = 30000) {
    this.page = page;
    this.timeout = timeout;
  }

  /**
   * Navigate to Search page
   */
  async navigateToSearch(): Promise<void> {
    console.log("[SearchHelper] Navigating to Search");

    // Click Search button in sidebar or navigation
    const searchButton = this.page.getByRole("button", { name: /Search/i });
    if (await searchButton.isVisible()) {
      await searchButton.click();
    } else {
      // Try navigation link
      const searchLink = this.page.getByRole("link", { name: /Search/i });
      if (await searchLink.isVisible()) {
        await searchLink.click();
      }
    }

    // Wait for search page to load
    await this.page.waitForTimeout(2000);

    console.log("[SearchHelper] Search page loaded");
  }

  /**
   * Execute a semantic search query
   */
  async executeSemanticSearch(query: string, options: SearchOptions = {}): Promise<void> {
    const { waitForResults = true } = options;

    console.log(`[SearchHelper] Executing semantic search: "${query}"`);

    // Find the search input
    const searchInput = this.page.getByRole("textbox", {
      name: /search|query/i,
    });

    if (!(await searchInput.isVisible())) {
      // Try alternative selectors
      const altInput = this.page.locator(
        'input[type="search"], input[placeholder*="search" i], input[placeholder*="query" i]'
      );
      await altInput.fill(query);
    } else {
      await searchInput.fill(query);
    }

    // Submit the search
    await this.page.keyboard.press("Enter");

    if (waitForResults) {
      await this.waitForResults(options.timeout);
    }

    console.log(`[SearchHelper] Search executed: "${query}"`);
  }

  /**
   * Wait for search results to load
   */
  async waitForResults(timeout?: number): Promise<void> {
    const waitTimeout = timeout || this.timeout;
    console.log(`[SearchHelper] Waiting for results (timeout: ${waitTimeout}ms)`);

    try {
      // Wait for results container or loading to complete
      await this.page.waitForSelector(
        '[data-testid*="result"], .search-result, .asset-card, [class*="result"]',
        { timeout: waitTimeout }
      );

      // Additional wait for results to render
      await this.page.waitForTimeout(1000);

      console.log("[SearchHelper] Results loaded");
    } catch (error) {
      console.log("[SearchHelper] No results found or timeout");
    }
  }

  /**
   * Get search results from the page
   */
  async getSearchResults(): Promise<SearchResult[]> {
    console.log("[SearchHelper] Getting search results");

    const results: SearchResult[] = [];

    try {
      // Find result elements
      const resultElements = this.page.locator(
        '[data-testid*="result"], .search-result, .asset-card, [class*="result"]'
      );
      const count = await resultElements.count();

      console.log(`[SearchHelper] Found ${count} result element(s)`);

      for (let i = 0; i < count; i++) {
        const element = resultElements.nth(i);

        // Extract asset ID from data attribute or text
        const testId = await element.getAttribute("data-testid");
        const assetId = testId?.replace("result-", "") || `asset-${i}`;

        // Extract score if available
        const scoreText = await element
          .locator('[class*="score"], [data-testid*="score"]')
          .textContent()
          .catch(() => null);
        const score = scoreText ? parseFloat(scoreText) : 0;

        // Extract clips if available
        const clips = await this.getClipsFromResult(element);

        results.push({
          assetId,
          score,
          clips,
        });
      }

      console.log(`[SearchHelper] Parsed ${results.length} result(s)`);
    } catch (error) {
      console.error("[SearchHelper] Error getting search results:", error);
    }

    return results;
  }

  /**
   * Get clips from a search result element
   */
  private async getClipsFromResult(resultElement: ReturnType<Page["locator"]>): Promise<Clip[]> {
    const clips: Clip[] = [];

    try {
      const clipElements = resultElement.locator('[data-testid*="clip"], .clip, [class*="clip"]');
      const count = await clipElements.count();

      for (let i = 0; i < count; i++) {
        const clipElement = clipElements.nth(i);

        // Extract timestamp
        const timestampText = await clipElement
          .locator('[class*="timestamp"], [data-testid*="timestamp"]')
          .textContent()
          .catch(() => "0");
        const timestamp = this.parseTimestamp(timestampText || "0");

        // Extract confidence
        const confidenceText = await clipElement
          .locator('[class*="confidence"], [data-testid*="confidence"]')
          .textContent()
          .catch(() => "0");
        const confidence = parseFloat(confidenceText || "0");

        clips.push({
          timestamp,
          confidence,
        });
      }
    } catch (error) {
      console.error("[SearchHelper] Error getting clips from result:", error);
    }

    return clips;
  }

  /**
   * Parse timestamp string to seconds
   */
  private parseTimestamp(timestampStr: string): number {
    // Handle formats like "1:30", "01:30", "1:30:00", or just seconds
    const parts = timestampStr.split(":").map((p) => parseFloat(p) || 0);

    if (parts.length === 1) {
      return parts[0];
    } else if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }

    return 0;
  }

  /**
   * Adjust confidence threshold
   */
  async adjustConfidenceThreshold(threshold: number): Promise<void> {
    console.log(`[SearchHelper] Adjusting confidence threshold to: ${threshold}`);

    try {
      // Find confidence slider or input
      const slider = this.page.locator(
        'input[type="range"][name*="confidence" i], [data-testid*="confidence-slider"]'
      );

      if (await slider.isVisible()) {
        await slider.fill(String(threshold));
      } else {
        // Try input field
        const input = this.page.locator(
          'input[type="number"][name*="confidence" i], [data-testid*="confidence-input"]'
        );
        if (await input.isVisible()) {
          await input.fill(String(threshold));
        }
      }

      // Wait for results to update
      await this.page.waitForTimeout(1000);

      console.log(`[SearchHelper] Confidence threshold set to: ${threshold}`);
    } catch (error) {
      console.error("[SearchHelper] Error adjusting confidence threshold:", error);
    }
  }

  /**
   * Verify clips are visible in search results
   */
  async verifyClipsVisible(): Promise<boolean> {
    console.log("[SearchHelper] Verifying clips are visible");

    try {
      const clipElements = this.page.locator('[data-testid*="clip"], .clip, [class*="clip"]');
      const count = await clipElements.count();

      const visible = count > 0;
      console.log(`[SearchHelper] Clips visible: ${visible} (count: ${count})`);

      return visible;
    } catch (error) {
      console.error("[SearchHelper] Error verifying clips:", error);
      return false;
    }
  }

  /**
   * Get total clip count from search results
   */
  async getClipCount(): Promise<number> {
    console.log("[SearchHelper] Getting clip count");

    try {
      const clipElements = this.page.locator('[data-testid*="clip"], .clip, [class*="clip"]');
      const count = await clipElements.count();

      console.log(`[SearchHelper] Total clip count: ${count}`);
      return count;
    } catch (error) {
      console.error("[SearchHelper] Error getting clip count:", error);
      return 0;
    }
  }

  /**
   * Get current confidence threshold value
   */
  async getConfidenceThreshold(): Promise<number> {
    try {
      const slider = this.page.locator(
        'input[type="range"][name*="confidence" i], [data-testid*="confidence-slider"]'
      );

      if (await slider.isVisible()) {
        const value = await slider.inputValue();
        return parseFloat(value) || 0;
      }

      const input = this.page.locator(
        'input[type="number"][name*="confidence" i], [data-testid*="confidence-input"]'
      );

      if (await input.isVisible()) {
        const value = await input.inputValue();
        return parseFloat(value) || 0;
      }

      return 0;
    } catch (error) {
      console.error("[SearchHelper] Error getting confidence threshold:", error);
      return 0;
    }
  }

  /**
   * Validate search results with comprehensive diagnostics
   *
   * Performs validation checks on search results and provides detailed
   * diagnostic information when validation fails.
   *
   * @param options - Validation options including expected asset, result counts, etc.
   * @throws SearchValidationError with detailed diagnostics on failure
   */
  async validateSearchResults(options: SearchValidationOptions = {}): Promise<SearchResult[]> {
    const {
      expectedAssetId,
      minResultCount = 1,
      maxResultCount,
      minClipCount,
      confidenceThreshold,
      captureScreenshotOnFailure = true,
    } = options;

    console.log(
      `[SearchHelper] Validating search results with options: ${JSON.stringify(options)}`
    );

    const results = await this.getSearchResults();

    // Check for no results
    if (results.length === 0) {
      console.log("[SearchHelper] No search results found. Running diagnostics...");

      const diagnostics = await this.gatherSearchDiagnostics();
      let screenshotPath: string | null = null;

      if (captureScreenshotOnFailure) {
        screenshotPath = await this.captureSearchScreenshot("no-results");
      }

      // Determine the specific error type based on diagnostics
      let errorType = SearchErrorType.NO_RESULTS;
      if (diagnostics.providerEnabled === false) {
        errorType = SearchErrorType.PROVIDER_NOT_ENABLED;
      } else if (diagnostics.ingestedAssetCount === 0) {
        errorType = SearchErrorType.ASSETS_NOT_INGESTED;
      }

      throw new SearchValidationError(
        this.buildNoResultsErrorMessage(expectedAssetId, diagnostics),
        errorType,
        diagnostics.lastQuery as string | null,
        expectedAssetId || null,
        screenshotPath,
        diagnostics
      );
    }

    // Check minimum result count
    if (results.length < minResultCount) {
      const diagnostics = await this.gatherSearchDiagnostics();
      let screenshotPath: string | null = null;

      if (captureScreenshotOnFailure) {
        screenshotPath = await this.captureSearchScreenshot("insufficient-results");
      }

      throw new SearchValidationError(
        `Expected at least ${minResultCount} results, but found ${results.length}`,
        SearchErrorType.NO_RESULTS,
        diagnostics.lastQuery as string | null,
        expectedAssetId || null,
        screenshotPath,
        { ...diagnostics, actualResultCount: results.length, minResultCount }
      );
    }

    // Check maximum result count
    if (maxResultCount !== undefined && results.length > maxResultCount) {
      console.warn(
        `[SearchHelper] Warning: Found ${results.length} results, expected at most ${maxResultCount}`
      );
    }

    // Check for expected asset
    if (expectedAssetId) {
      const foundAsset = results.find((r) => r.assetId === expectedAssetId);
      if (!foundAsset) {
        const diagnostics = await this.gatherSearchDiagnostics();
        let screenshotPath: string | null = null;

        if (captureScreenshotOnFailure) {
          screenshotPath = await this.captureSearchScreenshot("asset-not-found");
        }

        throw new SearchValidationError(
          `Expected asset "${expectedAssetId}" not found in ${results.length} results. ` +
            `Found assets: ${results.map((r) => r.assetId).join(", ")}`,
          SearchErrorType.EXPECTED_ASSET_NOT_FOUND,
          diagnostics.lastQuery as string | null,
          expectedAssetId,
          screenshotPath,
          {
            ...diagnostics,
            foundAssetIds: results.map((r) => r.assetId),
            resultCount: results.length,
          }
        );
      }
    }

    // Check minimum clip count
    if (minClipCount !== undefined) {
      const totalClips = results.reduce((sum, r) => sum + r.clips.length, 0);
      if (totalClips < minClipCount) {
        console.warn(
          `[SearchHelper] Warning: Found ${totalClips} clips, expected at least ${minClipCount}`
        );
      }
    }

    // Check confidence threshold filtering
    if (confidenceThreshold !== undefined) {
      for (const result of results) {
        const lowConfidenceClips = result.clips.filter((c) => c.confidence < confidenceThreshold);
        if (lowConfidenceClips.length > 0) {
          console.warn(
            `[SearchHelper] Warning: Asset ${result.assetId} has ${lowConfidenceClips.length} clips below threshold ${confidenceThreshold}`
          );
        }
      }
    }

    console.log(
      `[SearchHelper] ✅ Search results validated: ${results.length} result(s), ` +
        `${results.reduce((sum, r) => sum + r.clips.length, 0)} total clips`
    );

    return results;
  }

  /**
   * Capture a screenshot during search validation
   */
  private async captureSearchScreenshot(reason: string): Promise<string> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const screenshotDir = "test-results";
    const screenshotPath = path.join(screenshotDir, `search-validation-${reason}-${timestamp}.png`);

    try {
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }

      await this.page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });

      console.log(`[SearchHelper] Screenshot saved: ${screenshotPath}`);
      return screenshotPath;
    } catch (screenshotError) {
      console.error(`[SearchHelper] Failed to capture screenshot: ${screenshotError}`);
      return "";
    }
  }

  /**
   * Gather diagnostic information about the search state
   */
  private async gatherSearchDiagnostics(): Promise<Record<string, unknown>> {
    const diagnostics: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      pageUrl: this.page.url(),
    };

    try {
      // Check if search is enabled
      diagnostics.searchEnabled = await this.isSearchEnabled();

      // Get current confidence threshold
      diagnostics.currentConfidenceThreshold = await this.getConfidenceThreshold();

      // Try to get the last search query from the input
      const searchInput = this.page.getByRole("textbox", {
        name: /search|query/i,
      });
      if (await searchInput.isVisible().catch(() => false)) {
        diagnostics.lastQuery = await searchInput.inputValue().catch(() => null);
      }

      // Check for error messages on the page
      const errorMessages = await this.page
        .locator('[class*="error"], [role="alert"], .MuiAlert-standardError')
        .allTextContents()
        .catch(() => []);
      if (errorMessages.length > 0) {
        diagnostics.visibleErrors = errorMessages;
      }

      // Check for "no results" messages
      const noResultsMessages = await this.page
        .locator('[class*="no-results"], [class*="empty-state"]')
        .allTextContents()
        .catch(() => []);
      if (noResultsMessages.length > 0) {
        diagnostics.noResultsMessages = noResultsMessages;
      }

      // Check if loading indicator is visible (might indicate incomplete search)
      const loadingVisible = await this.page
        .locator('[class*="loading"], [role="progressbar"], .MuiCircularProgress-root')
        .isVisible()
        .catch(() => false);
      diagnostics.loadingIndicatorVisible = loadingVisible;

      // Try to determine if provider is enabled (this is a heuristic)
      diagnostics.providerEnabled = await this.checkProviderEnabled();

      // Try to get ingested asset count (if available in UI)
      diagnostics.ingestedAssetCount = await this.getIngestedAssetCount();
    } catch (diagError) {
      diagnostics.diagnosticError = String(diagError);
    }

    return diagnostics;
  }

  /**
   * Check if the search provider is enabled
   */
  private async checkProviderEnabled(): Promise<boolean | null> {
    try {
      // Look for provider status indicators
      const disabledIndicator = this.page.locator(
        '[class*="provider-disabled"], [data-testid*="provider-disabled"]'
      );
      if (await disabledIndicator.isVisible().catch(() => false)) {
        return false;
      }

      const enabledIndicator = this.page.locator(
        '[class*="provider-enabled"], [data-testid*="provider-enabled"]'
      );
      if (await enabledIndicator.isVisible().catch(() => false)) {
        return true;
      }

      // If we can't determine, return null
      return null;
    } catch {
      return null;
    }
  }

  /**
   * Get the count of ingested assets (if available in UI)
   */
  private async getIngestedAssetCount(): Promise<number | null> {
    try {
      // Look for asset count indicators
      const countElement = this.page.locator(
        '[data-testid*="asset-count"], [class*="asset-count"], [class*="total-assets"]'
      );
      if (await countElement.isVisible().catch(() => false)) {
        const text = await countElement.textContent();
        const match = text?.match(/(\d+)/);
        if (match) {
          return parseInt(match[1], 10);
        }
      }
      return null;
    } catch {
      return null;
    }
  }

  /**
   * Build a detailed error message for no results
   */
  private buildNoResultsErrorMessage(
    expectedAssetId: string | undefined,
    diagnostics: Record<string, unknown>
  ): string {
    const lines = ["No search results found."];

    if (expectedAssetId) {
      lines.push(`Expected asset: ${expectedAssetId}`);
    }

    lines.push("");
    lines.push("Diagnostic Information:");

    if (diagnostics.providerEnabled === false) {
      lines.push("  ⚠️ Search provider appears to be DISABLED");
    } else if (diagnostics.providerEnabled === true) {
      lines.push("  ✓ Search provider is enabled");
    }

    if (diagnostics.ingestedAssetCount !== null) {
      lines.push(`  Ingested assets: ${diagnostics.ingestedAssetCount}`);
      if (diagnostics.ingestedAssetCount === 0) {
        lines.push("  ⚠️ No assets have been ingested");
      }
    }

    if (diagnostics.lastQuery) {
      lines.push(`  Last query: "${diagnostics.lastQuery}"`);
    }

    if (diagnostics.currentConfidenceThreshold) {
      lines.push(`  Confidence threshold: ${diagnostics.currentConfidenceThreshold}`);
    }

    if (diagnostics.loadingIndicatorVisible) {
      lines.push("  ⚠️ Loading indicator still visible (search may be incomplete)");
    }

    if (diagnostics.visibleErrors) {
      lines.push("  Visible errors on page:");
      for (const err of diagnostics.visibleErrors as string[]) {
        lines.push(`    - ${err}`);
      }
    }

    if (diagnostics.noResultsMessages) {
      lines.push("  No results messages:");
      for (const msg of diagnostics.noResultsMessages as string[]) {
        lines.push(`    - ${msg}`);
      }
    }

    return lines.join("\n");
  }

  /**
   * Get result count
   */
  async getResultCount(): Promise<number> {
    const results = await this.getSearchResults();
    return results.length;
  }

  /**
   * Check if search is enabled
   */
  async isSearchEnabled(): Promise<boolean> {
    try {
      const searchInput = this.page.getByRole("textbox", {
        name: /search|query/i,
      });
      return await searchInput.isEnabled();
    } catch (error) {
      return false;
    }
  }
}
