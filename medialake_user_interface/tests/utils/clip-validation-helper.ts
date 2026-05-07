/**
 * Clip Validation Helper for Playwright Tests
 *
 * Provides reusable utilities for validating clip display and interaction
 * in asset details and video player views.
 *
 * @requirements 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5
 */

import { Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { Clip, ClipValidationResult } from "./test-config-models";

/**
 * Error types for clip validation
 */
export enum ClipValidationErrorType {
  NO_CLIPS_FOUND = "NO_CLIPS_FOUND",
  INSUFFICIENT_CLIPS = "INSUFFICIENT_CLIPS",
  CLIP_GENERATION_FAILED = "CLIP_GENERATION_FAILED",
  CLIP_DISPLAY_FAILED = "CLIP_DISPLAY_FAILED",
  THRESHOLD_MISMATCH = "THRESHOLD_MISMATCH",
  TIMELINE_MARKERS_MISSING = "TIMELINE_MARKERS_MISSING",
  NAVIGATION_FAILED = "NAVIGATION_FAILED",
  ASSET_DETAILS_NOT_OPEN = "ASSET_DETAILS_NOT_OPEN",
  UNKNOWN = "UNKNOWN",
}

/**
 * Custom error class for clip validation failures
 */
export class ClipValidationError extends Error {
  public readonly errorType: ClipValidationErrorType;
  public readonly assetId: string | null;
  public readonly screenshotPath: string | null;
  public readonly diagnostics: Record<string, unknown>;
  public readonly clipMetadata: Clip[];

  constructor(
    message: string,
    errorType: ClipValidationErrorType,
    assetId: string | null = null,
    screenshotPath: string | null = null,
    diagnostics: Record<string, unknown> = {},
    clipMetadata: Clip[] = []
  ) {
    super(message);
    this.name = "ClipValidationError";
    this.errorType = errorType;
    this.assetId = assetId;
    this.screenshotPath = screenshotPath;
    this.diagnostics = diagnostics;
    this.clipMetadata = clipMetadata;
  }

  /**
   * Get a formatted diagnostic message
   */
  getDiagnosticMessage(): string {
    const lines = [`Clip Validation Error: ${this.message}`, `Error Type: ${this.errorType}`];

    if (this.assetId) {
      lines.push(`Asset ID: ${this.assetId}`);
    }

    if (this.screenshotPath) {
      lines.push(`Screenshot: ${this.screenshotPath}`);
    }

    if (this.clipMetadata.length > 0) {
      lines.push(`Clips Found: ${this.clipMetadata.length}`);
      lines.push("Clip Details:");
      for (const clip of this.clipMetadata.slice(0, 10)) {
        lines.push(`  - Timestamp: ${clip.timestamp}s, Confidence: ${clip.confidence}`);
      }
      if (this.clipMetadata.length > 10) {
        lines.push(`  ... and ${this.clipMetadata.length - 10} more`);
      }
    }

    if (Object.keys(this.diagnostics).length > 0) {
      lines.push(`Diagnostics: ${JSON.stringify(this.diagnostics, null, 2)}`);
    }

    return lines.join("\n");
  }
}

/**
 * Clip validation options
 */
export interface ClipValidationOptions {
  minClipCount?: number;
  maxClipCount?: number;
  confidenceThreshold?: number;
  requireTimelineMarkers?: boolean;
  captureScreenshotOnFailure?: boolean;
}

/**
 * Extended clip validation result with diagnostics
 */
export interface ExtendedClipValidationResult extends ClipValidationResult {
  clips: Clip[];
  confidenceDistribution: {
    min: number;
    max: number;
    average: number;
  };
  diagnostics: Record<string, unknown>;
}

/**
 * Helper class for clip validation operations
 */
export class ClipValidationHelper {
  private page: Page;
  private timeout: number;

  constructor(page: Page, timeout: number = 30000) {
    this.page = page;
    this.timeout = timeout;
  }

  /**
   * Open asset details panel for a specific asset
   */
  async openAssetDetails(assetId: string): Promise<void> {
    console.log(`[ClipValidationHelper] Opening asset details for: ${assetId}`);

    try {
      // Find and click the asset card or result
      const assetElement = this.page.locator(
        `[data-testid*="${assetId}"], [data-asset-id="${assetId}"]`
      );

      if (await assetElement.isVisible()) {
        await assetElement.click();
      } else {
        // Try clicking on any visible asset card
        const assetCard = this.page
          .locator('[data-testid*="result"], .asset-card, .search-result')
          .first();
        await assetCard.click();
      }

      // Wait for details panel to open
      await this.page.waitForTimeout(1000);

      console.log(`[ClipValidationHelper] Asset details opened for: ${assetId}`);
    } catch (error) {
      console.error("[ClipValidationHelper] Error opening asset details:", error);
      throw error;
    }
  }

  /**
   * Expand the sidebar to show full clip list
   */
  async expandSidebar(): Promise<void> {
    console.log("[ClipValidationHelper] Expanding sidebar");

    try {
      // Find sidebar expand button or toggle
      const expandButton = this.page.locator(
        '[data-testid*="expand"], [aria-label*="expand" i], button:has-text("expand")'
      );

      if (await expandButton.isVisible()) {
        await expandButton.click();
        await this.page.waitForTimeout(500);
      }

      console.log("[ClipValidationHelper] Sidebar expanded");
    } catch (error) {
      console.error("[ClipValidationHelper] Error expanding sidebar:", error);
    }
  }

  /**
   * Get clips from the sidebar
   */
  async getClipsFromSidebar(): Promise<Clip[]> {
    console.log("[ClipValidationHelper] Getting clips from sidebar");

    const clips: Clip[] = [];

    try {
      const clipElements = this.page.locator(
        '[data-testid*="clip"], .clip-item, .sidebar-clip, [class*="clip"]'
      );
      const count = await clipElements.count();

      console.log(`[ClipValidationHelper] Found ${count} clip element(s)`);

      for (let i = 0; i < count; i++) {
        const clipElement = clipElements.nth(i);

        // Extract timestamp
        const timestampText = await clipElement
          .locator('[class*="timestamp"], [data-testid*="timestamp"], time')
          .textContent()
          .catch(() => "0");
        const timestamp = this.parseTimestamp(timestampText || "0");

        // Extract confidence
        const confidenceText = await clipElement
          .locator('[class*="confidence"], [data-testid*="confidence"], [class*="score"]')
          .textContent()
          .catch(() => "0");
        const confidence = parseFloat(confidenceText || "0");

        clips.push({
          timestamp,
          confidence,
        });
      }

      console.log(`[ClipValidationHelper] Parsed ${clips.length} clip(s)`);
    } catch (error) {
      console.error("[ClipValidationHelper] Error getting clips from sidebar:", error);
    }

    return clips;
  }

  /**
   * Parse timestamp string to seconds
   */
  private parseTimestamp(timestampStr: string): number {
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
   * Verify clips are displayed in the timeline
   */
  async verifyClipsInTimeline(): Promise<boolean> {
    console.log("[ClipValidationHelper] Verifying clips in timeline");

    try {
      const timelineMarkers = this.page.locator(
        '[data-testid*="timeline-marker"], .timeline-marker, [class*="marker"], .clip-marker'
      );
      const count = await timelineMarkers.count();

      const hasMarkers = count > 0;
      console.log(`[ClipValidationHelper] Timeline markers: ${hasMarkers} (count: ${count})`);

      return hasMarkers;
    } catch (error) {
      console.error("[ClipValidationHelper] Error verifying timeline clips:", error);
      return false;
    }
  }

  /**
   * Click on a clip in the sidebar to navigate
   */
  async clickClipInSidebar(clipIndex: number): Promise<void> {
    console.log(`[ClipValidationHelper] Clicking clip at index: ${clipIndex}`);

    try {
      const clipElements = this.page.locator(
        '[data-testid*="clip"], .clip-item, .sidebar-clip, [class*="clip"]'
      );
      const clip = clipElements.nth(clipIndex);

      await clip.click();
      await this.page.waitForTimeout(500);

      console.log(`[ClipValidationHelper] Clicked clip at index: ${clipIndex}`);
    } catch (error) {
      console.error("[ClipValidationHelper] Error clicking clip:", error);
      throw error;
    }
  }

  /**
   * Verify player navigated to the expected timestamp
   */
  async verifyPlayerNavigatedToClip(expectedTimestamp: number): Promise<boolean> {
    console.log(`[ClipValidationHelper] Verifying player at timestamp: ${expectedTimestamp}`);

    try {
      // Get current player time
      const currentTime = await this.getCurrentPlayerTime();

      // Allow some tolerance (within 2 seconds)
      const tolerance = 2;
      const isAtTimestamp = Math.abs(currentTime - expectedTimestamp) <= tolerance;

      console.log(
        `[ClipValidationHelper] Player time: ${currentTime}, expected: ${expectedTimestamp}, match: ${isAtTimestamp}`
      );

      return isAtTimestamp;
    } catch (error) {
      console.error("[ClipValidationHelper] Error verifying player position:", error);
      return false;
    }
  }

  /**
   * Get current player time
   */
  async getCurrentPlayerTime(): Promise<number> {
    try {
      // Try to get time from video element
      const video = this.page.locator("video");
      if (await video.isVisible()) {
        const currentTime = await video.evaluate((el: HTMLVideoElement) => el.currentTime);
        return currentTime;
      }

      // Try to get time from player UI
      const timeDisplay = this.page.locator(
        '[data-testid*="current-time"], .current-time, [class*="time-display"]'
      );
      if (await timeDisplay.isVisible()) {
        const timeText = await timeDisplay.textContent();
        return this.parseTimestamp(timeText || "0");
      }

      return 0;
    } catch (error) {
      console.error("[ClipValidationHelper] Error getting player time:", error);
      return 0;
    }
  }

  /**
   * Adjust confidence threshold in the player view
   */
  async adjustConfidenceInPlayer(threshold: number): Promise<void> {
    console.log(`[ClipValidationHelper] Adjusting player confidence to: ${threshold}`);

    try {
      // Find confidence slider in player
      const slider = this.page.locator(
        '[data-testid*="player-confidence"], [data-testid*="confidence-slider"], input[type="range"]'
      );

      if (await slider.isVisible()) {
        await slider.fill(String(threshold));
      }

      // Wait for markers to update
      await this.page.waitForTimeout(500);

      console.log(`[ClipValidationHelper] Player confidence set to: ${threshold}`);
    } catch (error) {
      console.error("[ClipValidationHelper] Error adjusting player confidence:", error);
    }
  }

  /**
   * Validate clip filtering based on threshold
   */
  async validateClipFiltering(threshold: number): Promise<ClipValidationResult> {
    console.log(`[ClipValidationHelper] Validating clip filtering at threshold: ${threshold}`);

    const clips = await this.getClipsFromSidebar();
    const timelineVisible = await this.verifyClipsInTimeline();

    // Check if clips match the threshold
    const clipsMatchThreshold = clips.every((clip) => clip.confidence >= threshold);

    const result: ClipValidationResult = {
      clipsFound: clips.length > 0,
      clipCount: clips.length,
      clipsMatchThreshold,
      timelineMarkersVisible: timelineVisible,
    };

    console.log(`[ClipValidationHelper] Validation result: ${JSON.stringify(result)}`);

    return result;
  }

  /**
   * Get clip count from sidebar
   */
  async getClipCount(): Promise<number> {
    const clips = await this.getClipsFromSidebar();
    return clips.length;
  }

  /**
   * Verify asset details panel is open
   */
  async isAssetDetailsPanelOpen(): Promise<boolean> {
    try {
      const detailsPanel = this.page.locator(
        '[data-testid*="asset-details"], .asset-details, [class*="details-panel"]'
      );
      return await detailsPanel.isVisible();
    } catch (error) {
      return false;
    }
  }

  /**
   * Get asset metadata from details panel
   */
  async getAssetMetadata(): Promise<Record<string, string>> {
    const metadata: Record<string, string> = {};

    try {
      const metadataElements = this.page.locator(
        '[data-testid*="metadata"], .metadata-item, [class*="metadata"]'
      );
      const count = await metadataElements.count();

      for (let i = 0; i < count; i++) {
        const element = metadataElements.nth(i);
        const text = await element.textContent();

        if (text) {
          const [key, value] = text.split(":").map((s) => s.trim());
          if (key && value) {
            metadata[key] = value;
          }
        }
      }
    } catch (error) {
      console.error("[ClipValidationHelper] Error getting asset metadata:", error);
    }

    return metadata;
  }

  /**
   * Validate clips with comprehensive diagnostics
   *
   * Performs validation checks on clips and provides detailed diagnostic
   * information when validation fails. Distinguishes between clip generation
   * issues and clip display issues.
   *
   * @param assetId - The asset ID being validated
   * @param options - Validation options
   * @throws ClipValidationError with detailed diagnostics on failure
   */
  async validateClips(
    assetId: string,
    options: ClipValidationOptions = {}
  ): Promise<ExtendedClipValidationResult> {
    const {
      minClipCount = 1,
      maxClipCount,
      confidenceThreshold,
      requireTimelineMarkers = false,
      captureScreenshotOnFailure = true,
    } = options;

    console.log(
      `[ClipValidationHelper] Validating clips for asset ${assetId} with options: ${JSON.stringify(
        options
      )}`
    );

    // First, check if asset details panel is open
    const isPanelOpen = await this.isAssetDetailsPanelOpen();
    if (!isPanelOpen) {
      const screenshotPath = captureScreenshotOnFailure
        ? await this.captureClipScreenshot(assetId, "panel-not-open")
        : null;

      throw new ClipValidationError(
        `Asset details panel is not open for asset ${assetId}`,
        ClipValidationErrorType.ASSET_DETAILS_NOT_OPEN,
        assetId,
        screenshotPath,
        { isPanelOpen: false }
      );
    }

    // Get clips from sidebar
    const clips = await this.getClipsFromSidebar();
    const diagnostics = await this.gatherClipDiagnostics(assetId, clips);

    // Check for no clips
    if (clips.length === 0) {
      console.log(
        `[ClipValidationHelper] No clips found for asset ${assetId}. Running diagnostics...`
      );

      const screenshotPath = captureScreenshotOnFailure
        ? await this.captureClipScreenshot(assetId, "no-clips")
        : null;

      // Determine if this is a generation issue or display issue
      const errorType = await this.determineClipErrorType(assetId, diagnostics);

      throw new ClipValidationError(
        this.buildNoClipsErrorMessage(assetId, diagnostics),
        errorType,
        assetId,
        screenshotPath,
        diagnostics,
        []
      );
    }

    // Check minimum clip count
    if (clips.length < minClipCount) {
      const screenshotPath = captureScreenshotOnFailure
        ? await this.captureClipScreenshot(assetId, "insufficient-clips")
        : null;

      throw new ClipValidationError(
        `Expected at least ${minClipCount} clips for asset ${assetId}, but found ${clips.length}`,
        ClipValidationErrorType.INSUFFICIENT_CLIPS,
        assetId,
        screenshotPath,
        { ...diagnostics, minClipCount, actualClipCount: clips.length },
        clips
      );
    }

    // Check maximum clip count
    if (maxClipCount !== undefined && clips.length > maxClipCount) {
      console.warn(
        `[ClipValidationHelper] Warning: Found ${clips.length} clips, expected at most ${maxClipCount}`
      );
    }

    // Check confidence threshold filtering
    if (confidenceThreshold !== undefined) {
      const clipsAboveThreshold = clips.filter((c) => c.confidence >= confidenceThreshold);
      const clipsBelowThreshold = clips.filter((c) => c.confidence < confidenceThreshold);

      if (clipsBelowThreshold.length > 0) {
        console.warn(
          `[ClipValidationHelper] Warning: ${clipsBelowThreshold.length} clips are below threshold ${confidenceThreshold}`
        );
        diagnostics.clipsBelowThreshold = clipsBelowThreshold.length;
        diagnostics.clipsAboveThreshold = clipsAboveThreshold.length;
      }
    }

    // Check timeline markers if required
    const timelineMarkersVisible = await this.verifyClipsInTimeline();
    if (requireTimelineMarkers && !timelineMarkersVisible) {
      const screenshotPath = captureScreenshotOnFailure
        ? await this.captureClipScreenshot(assetId, "no-timeline-markers")
        : null;

      throw new ClipValidationError(
        `Timeline markers not visible for asset ${assetId} despite ${clips.length} clips being present`,
        ClipValidationErrorType.TIMELINE_MARKERS_MISSING,
        assetId,
        screenshotPath,
        diagnostics,
        clips
      );
    }

    // Calculate confidence distribution
    const confidences = clips.map((c) => c.confidence);
    const confidenceDistribution = {
      min: Math.min(...confidences),
      max: Math.max(...confidences),
      average: confidences.reduce((a, b) => a + b, 0) / confidences.length,
    };

    console.log(
      `[ClipValidationHelper] ✅ Clips validated for asset ${assetId}: ${clips.length} clip(s), ` +
        `confidence range: ${confidenceDistribution.min.toFixed(
          2
        )} - ${confidenceDistribution.max.toFixed(2)}`
    );

    return {
      clipsFound: true,
      clipCount: clips.length,
      clipsMatchThreshold: confidenceThreshold
        ? clips.every((c) => c.confidence >= confidenceThreshold)
        : true,
      timelineMarkersVisible,
      clips,
      confidenceDistribution,
      diagnostics,
    };
  }

  /**
   * Capture a screenshot during clip validation
   */
  private async captureClipScreenshot(assetId: string, reason: string): Promise<string> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const screenshotDir = "test-results";
    const screenshotPath = path.join(
      screenshotDir,
      `clip-validation-${reason}-${assetId}-${timestamp}.png`
    );

    try {
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }

      await this.page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });

      console.log(`[ClipValidationHelper] Screenshot saved: ${screenshotPath}`);
      return screenshotPath;
    } catch (screenshotError) {
      console.error(`[ClipValidationHelper] Failed to capture screenshot: ${screenshotError}`);
      return "";
    }
  }

  /**
   * Gather diagnostic information about clips
   */
  private async gatherClipDiagnostics(
    assetId: string,
    clips: Clip[]
  ): Promise<Record<string, unknown>> {
    const diagnostics: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      pageUrl: this.page.url(),
      assetId,
      clipCount: clips.length,
    };

    try {
      // Check if asset details panel is open
      diagnostics.assetDetailsPanelOpen = await this.isAssetDetailsPanelOpen();

      // Get asset metadata
      const metadata = await this.getAssetMetadata();
      diagnostics.assetMetadata = metadata;

      // Check for sidebar visibility
      const sidebarVisible = await this.page
        .locator('[data-testid*="sidebar"], .sidebar, [class*="sidebar"]')
        .isVisible()
        .catch(() => false);
      diagnostics.sidebarVisible = sidebarVisible;

      // Check for clip container visibility
      const clipContainerVisible = await this.page
        .locator('[data-testid*="clip-list"], .clip-list, [class*="clip-container"]')
        .isVisible()
        .catch(() => false);
      diagnostics.clipContainerVisible = clipContainerVisible;

      // Check for error messages
      const errorMessages = await this.page
        .locator('[class*="error"], [role="alert"]')
        .allTextContents()
        .catch(() => []);
      if (errorMessages.length > 0) {
        diagnostics.visibleErrors = errorMessages;
      }

      // Check for loading indicators
      const loadingVisible = await this.page
        .locator('[class*="loading"], [role="progressbar"]')
        .isVisible()
        .catch(() => false);
      diagnostics.loadingIndicatorVisible = loadingVisible;

      // Check timeline markers
      diagnostics.timelineMarkersVisible = await this.verifyClipsInTimeline();

      // Get current player time if video is playing
      diagnostics.currentPlayerTime = await this.getCurrentPlayerTime();

      // Calculate clip statistics if clips exist
      if (clips.length > 0) {
        const confidences = clips.map((c) => c.confidence);
        diagnostics.clipStatistics = {
          count: clips.length,
          minConfidence: Math.min(...confidences),
          maxConfidence: Math.max(...confidences),
          avgConfidence: confidences.reduce((a, b) => a + b, 0) / confidences.length,
          timestamps: clips.map((c) => c.timestamp),
        };
      }
    } catch (diagError) {
      diagnostics.diagnosticError = String(diagError);
    }

    return diagnostics;
  }

  /**
   * Determine the type of clip error (generation vs display)
   */
  private async determineClipErrorType(
    assetId: string,
    diagnostics: Record<string, unknown>
  ): Promise<ClipValidationErrorType> {
    // If sidebar is not visible, it's likely a display issue
    if (diagnostics.sidebarVisible === false) {
      return ClipValidationErrorType.CLIP_DISPLAY_FAILED;
    }

    // If clip container is not visible, it's likely a display issue
    if (diagnostics.clipContainerVisible === false) {
      return ClipValidationErrorType.CLIP_DISPLAY_FAILED;
    }

    // If there are visible errors, it might be a generation issue
    if (diagnostics.visibleErrors && (diagnostics.visibleErrors as string[]).length > 0) {
      const errors = diagnostics.visibleErrors as string[];
      const generationErrors = errors.some(
        (e) =>
          e.toLowerCase().includes("generation") ||
          e.toLowerCase().includes("embedding") ||
          e.toLowerCase().includes("processing")
      );
      if (generationErrors) {
        return ClipValidationErrorType.CLIP_GENERATION_FAILED;
      }
    }

    // If loading indicator is still visible, clips might still be loading
    if (diagnostics.loadingIndicatorVisible) {
      return ClipValidationErrorType.CLIP_DISPLAY_FAILED;
    }

    // Default to no clips found
    return ClipValidationErrorType.NO_CLIPS_FOUND;
  }

  /**
   * Build a detailed error message for no clips
   */
  private buildNoClipsErrorMessage(assetId: string, diagnostics: Record<string, unknown>): string {
    const lines = [`No clips found for asset ${assetId}.`];

    lines.push("");
    lines.push("Diagnostic Information:");

    if (diagnostics.assetDetailsPanelOpen === false) {
      lines.push("  ⚠️ Asset details panel is NOT open");
    } else {
      lines.push("  ✓ Asset details panel is open");
    }

    if (diagnostics.sidebarVisible === false) {
      lines.push("  ⚠️ Sidebar is NOT visible");
    } else {
      lines.push("  ✓ Sidebar is visible");
    }

    if (diagnostics.clipContainerVisible === false) {
      lines.push("  ⚠️ Clip container is NOT visible");
    } else {
      lines.push("  ✓ Clip container is visible");
    }

    if (diagnostics.loadingIndicatorVisible) {
      lines.push("  ⚠️ Loading indicator still visible (clips may still be loading)");
    }

    if (diagnostics.timelineMarkersVisible === false) {
      lines.push("  ⚠️ No timeline markers visible");
    }

    if (diagnostics.assetMetadata) {
      lines.push(`  Asset metadata: ${JSON.stringify(diagnostics.assetMetadata)}`);
    }

    if (diagnostics.visibleErrors) {
      lines.push("  Visible errors on page:");
      for (const err of diagnostics.visibleErrors as string[]) {
        lines.push(`    - ${err}`);
      }
    }

    lines.push("");
    lines.push("Possible causes:");
    lines.push("  1. Clips were not generated during ingestion (check pipeline configuration)");
    lines.push("  2. Clips exist but are not being displayed (UI rendering issue)");
    lines.push("  3. Confidence threshold is too high (all clips filtered out)");
    lines.push("  4. Asset is not a video (clips only apply to video assets)");

    return lines.join("\n");
  }

  /**
   * Validate clip threshold filtering
   *
   * Verifies that adjusting the confidence threshold correctly filters clips.
   */
  async validateThresholdFiltering(
    assetId: string,
    thresholds: number[]
  ): Promise<Map<number, number>> {
    const results = new Map<number, number>();

    console.log(
      `[ClipValidationHelper] Validating threshold filtering for asset ${assetId} with thresholds: ${thresholds.join(
        ", "
      )}`
    );

    for (const threshold of thresholds) {
      await this.adjustConfidenceInPlayer(threshold);
      await this.page.waitForTimeout(500); // Wait for UI to update

      const clips = await this.getClipsFromSidebar();
      const clipsAboveThreshold = clips.filter((c) => c.confidence >= threshold);

      results.set(threshold, clipsAboveThreshold.length);

      console.log(
        `[ClipValidationHelper] Threshold ${threshold}: ${clipsAboveThreshold.length} clips visible`
      );
    }

    // Validate that higher thresholds result in fewer or equal clips
    const sortedThresholds = [...thresholds].sort((a, b) => a - b);
    for (let i = 1; i < sortedThresholds.length; i++) {
      const lowerThreshold = sortedThresholds[i - 1];
      const higherThreshold = sortedThresholds[i];
      const lowerCount = results.get(lowerThreshold) || 0;
      const higherCount = results.get(higherThreshold) || 0;

      if (higherCount > lowerCount) {
        console.warn(
          `[ClipValidationHelper] Warning: Higher threshold ${higherThreshold} has more clips (${higherCount}) than lower threshold ${lowerThreshold} (${lowerCount})`
        );
      }
    }

    return results;
  }

  /**
   * Close asset details panel
   */
  async closeAssetDetails(): Promise<void> {
    console.log("[ClipValidationHelper] Closing asset details");

    try {
      const closeButton = this.page.locator(
        '[data-testid*="close"], [aria-label*="close" i], button:has-text("close")'
      );

      if (await closeButton.isVisible()) {
        await closeButton.click();
        await this.page.waitForTimeout(500);
      }

      console.log("[ClipValidationHelper] Asset details closed");
    } catch (error) {
      console.error("[ClipValidationHelper] Error closing asset details:", error);
    }
  }
}
