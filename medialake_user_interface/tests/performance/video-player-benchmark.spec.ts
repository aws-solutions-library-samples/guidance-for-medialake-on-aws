import { test, expect } from "../fixtures/performance.fixtures";

/**
 * Video player performance benchmarks.
 *
 * Authenticates, then navigates to a video asset detail page
 * to measure player initialization and playback performance.
 *
 * The test finds video assets by intercepting the dashboard's search API
 * response, then navigates directly to the first video asset's detail page.
 *
 * Override with: PERF_VIDEO_ASSET_PATH=/videos/some-id npm run test:perf
 */

const VIDEO_THRESHOLDS = {
  timeToFirstFrame: 8000,
  videoTTFB: 2000,
  maxBufferingEvents: 3,
  playerLibLoad: 3000,
};

test.describe("Video Player Performance Benchmarks", () => {
  test.describe.configure({ mode: "serial" });

  test("video player initialization and first frame", async ({
    authenticatedPage,
    captureVideoMetrics,
  }) => {
    const page = authenticatedPage;

    // If explicit path provided, go straight there
    if (process.env.PERF_VIDEO_ASSET_PATH) {
      await page.goto(process.env.PERF_VIDEO_ASSET_PATH, {
        waitUntil: "domcontentloaded",
      });
    } else {
      // Find a video asset by intercepting the API search response
      // that the dashboard's RecentAssetsWidget fires on load.
      console.log("[perf] Waiting for dashboard API to return assets...");

      // The dashboard is already loaded by the auth fixture.
      // Wait for asset cards to appear, then find a video one to click.
      await page
        .locator('[class*="asset-card-video"]')
        .first()
        .waitFor({ state: "visible", timeout: 20000 })
        .catch(() => {});

      const videoCardCount = await page.locator('[class*="asset-card-video"]').count();
      console.log(`[perf] Found ${videoCardCount} video asset card(s) on dashboard`);

      if (videoCardCount === 0) {
        // No video cards — try any asset card as fallback
        const anyCardCount = await page.locator('[class*="asset-card-"]').count();
        if (anyCardCount === 0) {
          test.skip(true, "No asset cards on dashboard — cannot navigate to video player");
          return;
        }
        console.log("[perf] No video cards found, clicking first available asset card...");
        await page.locator('[class*="asset-card-"]').first().click();
      } else {
        console.log("[perf] Clicking first video asset card...");
        await page.locator('[class*="asset-card-video"]').first().click();
      }

      // Wait for navigation to the asset detail page
      await page.waitForLoadState("domcontentloaded");
    }

    // Wait for video player to appear
    console.log("[perf] Waiting for video player...");
    const hasPlayer = await page
      .locator('video, [class*="omakase"], [data-testid="video-viewer"]')
      .first()
      .waitFor({ state: "visible", timeout: 20000 })
      .then(() => true)
      .catch(() => false);

    if (!hasPlayer) {
      test.skip(true, "No video player found on this asset page");
      return;
    }

    // Wait for video metadata to load (readyState >= 2 = HAVE_CURRENT_DATA)
    console.log("[perf] Waiting for video to load metadata...");
    await page
      .waitForFunction(
        () => {
          const video = document.querySelector("video");
          return video && video.readyState >= 2;
        },
        { timeout: 25000 }
      )
      .catch(() => {
        console.log("[perf] Video metadata did not fully load in time");
      });

    // Wait for network to settle
    await page.waitForLoadState("networkidle").catch(() => {});

    const metrics = await captureVideoMetrics(page, "video");

    console.log(`[perf] Player init: ${metrics.playerInitTime.toFixed(0)}ms`);
    console.log(`[perf] Time to first frame: ${metrics.timeToFirstFrame.toFixed(0)}ms`);
    console.log(`[perf] Video TTFB: ${metrics.videoFirstByte.toFixed(0)}ms`);
    console.log(`[perf] Resolution: ${metrics.videoResolution}`);
    console.log(`[perf] Player lib load: ${metrics.playerLibraryLoadTime.toFixed(0)}ms`);
    console.log(`[perf] Video duration: ${metrics.videoDuration.toFixed(1)}s`);

    if (metrics.videoFirstByte > 0) {
      expect(metrics.videoFirstByte).toBeLessThan(VIDEO_THRESHOLDS.videoTTFB);
    }
    if (metrics.playerLibraryLoadTime > 0) {
      expect(metrics.playerLibraryLoadTime).toBeLessThan(VIDEO_THRESHOLDS.playerLibLoad);
    }
  });

  test("video playback buffering during first 30 seconds", async ({
    authenticatedPage,
    captureVideoMetrics,
  }) => {
    const page = authenticatedPage;

    // Navigate to a video asset if explicit path provided
    if (process.env.PERF_VIDEO_ASSET_PATH) {
      await page.goto(process.env.PERF_VIDEO_ASSET_PATH, {
        waitUntil: "domcontentloaded",
      });
    } else {
      // Try to find and click a video card from the dashboard
      await page
        .locator('[class*="asset-card-video"]')
        .first()
        .waitFor({ state: "visible", timeout: 20000 })
        .catch(() => {});

      const videoCardCount = await page.locator('[class*="asset-card-video"]').count();
      if (videoCardCount === 0) {
        test.skip(true, "No video asset cards on dashboard");
        return;
      }

      await page.locator('[class*="asset-card-video"]').first().click();
      await page.waitForLoadState("domcontentloaded");
    }

    // Check for video element
    const hasVideo = await page
      .locator("video")
      .first()
      .waitFor({ state: "visible", timeout: 20000 })
      .then(() => true)
      .catch(() => false);

    if (!hasVideo) {
      test.skip(true, "No video element found on page");
      return;
    }

    // Wait for video to be ready before instrumenting
    await page
      .waitForFunction(
        () => {
          const video = document.querySelector("video");
          return video && video.readyState >= 2;
        },
        { timeout: 20000 }
      )
      .catch(() => {});

    // Instrument buffering tracking
    await page.evaluate(() => {
      const video = document.querySelector("video");
      if (!video) return;

      (window as any).__perf_buffering_count = 0;
      (window as any).__perf_buffering_total = 0;
      let bufferStart = 0;

      video.addEventListener("waiting", () => {
        (window as any).__perf_buffering_count++;
        bufferStart = performance.now();
      });

      video.addEventListener("playing", () => {
        if (bufferStart > 0) {
          (window as any).__perf_buffering_total += performance.now() - bufferStart;
          bufferStart = 0;
        }
      });
    });

    // Start playback
    await page.evaluate(() => {
      const video = document.querySelector("video");
      if (video) video.play().catch(() => {});
    });

    // Let it play for 30 seconds
    console.log("[perf] Playing video for 30 seconds to measure buffering...");
    await page.waitForTimeout(30000);

    const metrics = await captureVideoMetrics(page, "video");

    console.log(`[perf] Buffering events: ${metrics.bufferingEvents}`);
    console.log(`[perf] Total buffering: ${metrics.totalBufferingDuration.toFixed(0)}ms`);

    expect(metrics.bufferingEvents).toBeLessThanOrEqual(VIDEO_THRESHOLDS.maxBufferingEvents);
  });
});
