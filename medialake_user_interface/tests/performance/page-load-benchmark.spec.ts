import {
  test,
  expect,
  saveBenchmarkReport,
  PageLoadMetrics,
  BenchmarkReport,
} from "../fixtures/performance.fixtures";

/**
 * Performance benchmark suite — measures page load times across key routes.
 *
 * Uses the auth fixture chain: creates a Cognito test user, logs in,
 * then navigates to the dashboard and waits for all widgets + media to load.
 *
 * Auto-detects CloudFront URL. Override with env vars:
 *   AWS_PROFILE=ml-dev2 npm run test:perf
 *   AWS_PROFILE=ml-dev2 MEDIALAKE_ENV=staging npm run test:perf
 */

// Max acceptable times in ms — adjust after collecting baselines
const THRESHOLDS = {
  ttfb: 800,
  fcp: 2500,
  lcp: 4000,
  domContentLoaded: 5000,
  loadComplete: 10000,
  dashboardReady: 30000, // Time until all widgets have loaded data
};

const report: BenchmarkReport = {
  runId: `perf-${Date.now()}`,
  environment: process.env.PLAYWRIGHT_BASE_URL || "auto-detected",
  commitSha: process.env.CI_COMMIT_SHA || "local",
  branch: process.env.CI_COMMIT_REF_NAME || "local",
  timestamp: new Date().toISOString(),
  pageLoads: [],
  videoMetrics: [],
};

test.describe("Page Load Performance Benchmarks", () => {
  test.describe.configure({ mode: "serial" });

  test("dashboard full load with all widgets and media", async ({
    authenticatedPage,
    capturePageMetrics,
  }) => {
    const page = authenticatedPage;
    const dashboardStart = Date.now();

    // The auth fixture already navigated to root and waited for domcontentloaded.
    // Now we need to wait for the dashboard widgets to actually load their data.

    // 1. Wait for the dashboard grid to render
    console.log("[perf] Waiting for dashboard grid...");
    await page
      .locator('[class*="react-grid-layout"], [data-testid="dashboard-grid"]')
      .first()
      .waitFor({ state: "visible", timeout: 15000 })
      .catch(() => {
        console.log("[perf] Dashboard grid selector not found, trying widget containers...");
      });

    // 2. Wait for widget containers to appear (the WidgetContainer components)
    console.log("[perf] Waiting for widget containers...");
    await page
      .locator('[class*="WidgetContainer"], [data-testid*="widget"]')
      .first()
      .waitFor({ state: "visible", timeout: 10000 })
      .catch(() => {
        console.log("[perf] No widget containers found via test ID, checking for card content...");
      });

    // 3. Wait for asset cards / thumbnails to load (RecentAssetsWidget, FavoritesWidget)
    console.log("[perf] Waiting for asset cards to load...");
    await page
      .locator('[class*="asset-card-"]')
      .first()
      .waitFor({ state: "visible", timeout: 15000 })
      .catch(() => {
        console.log("[perf] No asset cards found — dashboard may be empty");
      });

    // 4. Wait for all images (thumbnails/proxies) to finish loading
    console.log("[perf] Waiting for all images to load...");
    await page
      .waitForFunction(
        () => {
          const images = Array.from(document.querySelectorAll("img"));
          return images.length === 0 || images.every((img) => img.complete);
        },
        { timeout: 15000 }
      )
      .catch(() => {
        console.log("[perf] Some images may not have finished loading");
      });

    // 5. Wait for any video elements to be ready (proxy previews in widgets)
    console.log("[perf] Checking for video elements...");
    const videoCount = await page.locator("video").count();
    if (videoCount > 0) {
      console.log(`[perf] Found ${videoCount} video element(s), waiting for them to load...`);
      await page
        .waitForFunction(
          () => {
            const videos = Array.from(document.querySelectorAll("video"));
            return videos.every(
              (v) => v.readyState >= 1 // HAVE_METADATA or better
            );
          },
          { timeout: 20000 }
        )
        .catch(() => {
          console.log("[perf] Some videos may not have finished loading metadata");
        });
    }

    // 6. Wait for network to settle (no pending XHR/fetch for widget data)
    console.log("[perf] Waiting for network to settle...");
    await page.waitForLoadState("networkidle").catch(() => {
      console.log("[perf] Network did not fully settle within timeout");
    });

    const dashboardReady = Date.now() - dashboardStart;
    console.log(`[perf] Dashboard fully ready in ${dashboardReady}ms`);

    // Capture the standard page metrics
    const metrics = await capturePageMetrics(page);
    report.pageLoads.push(metrics);

    // Log everything
    console.log(`[perf] Dashboard TTFB: ${metrics.ttfb.toFixed(0)}ms`);
    console.log(`[perf] Dashboard FCP: ${metrics.fcp?.toFixed(0) ?? "N/A"}ms`);
    console.log(`[perf] Dashboard LCP: ${metrics.lcp?.toFixed(0) ?? "N/A"}ms`);
    console.log(`[perf] Dashboard DOM Ready: ${metrics.domContentLoaded.toFixed(0)}ms`);
    console.log(`[perf] Dashboard Load Complete: ${metrics.loadComplete.toFixed(0)}ms`);
    console.log(`[perf] Dashboard Resources: ${metrics.resourceCount}`);
    console.log(`[perf] Dashboard Transfer: ${(metrics.transferSize / 1024).toFixed(0)}KB`);
    console.log(`[perf] Dashboard Full Ready (with widgets): ${dashboardReady}ms`);

    // Count what loaded
    const imgCount = await page.locator("img").count();
    const cardCount = await page.locator('[class*="asset-card-"]').count();
    console.log(`[perf] Images loaded: ${imgCount}`);
    console.log(`[perf] Cards rendered: ${cardCount}`);
    console.log(`[perf] Videos found: ${videoCount}`);

    // Assertions
    expect(metrics.ttfb).toBeLessThan(THRESHOLDS.ttfb);
    expect(dashboardReady).toBeLessThan(THRESHOLDS.dashboardReady);
    if (metrics.fcp) expect(metrics.fcp).toBeLessThan(THRESHOLDS.fcp);
    if (metrics.lcp) expect(metrics.lcp).toBeLessThan(THRESHOLDS.lcp);
  });

  test("asset detail page with video player", async ({
    authenticatedPage,
    capturePageMetrics,
    captureVideoMetrics,
  }) => {
    const page = authenticatedPage;

    // Find and click the first asset card to navigate to detail view
    const assetCard = page.locator('[class*="asset-card-"]').first();

    const hasCards = await assetCard
      .waitFor({ state: "visible", timeout: 5000 })
      .then(() => true)
      .catch(() => false);

    if (!hasCards) {
      console.log("[perf] No asset cards on dashboard — skipping asset detail test");
      test.skip(true, "No asset cards visible on dashboard");
      return;
    }

    // Click the first asset
    const detailStart = Date.now();
    await assetCard.click();

    // Wait for the video player or asset detail page to load
    console.log("[perf] Waiting for asset detail page...");
    await page.waitForLoadState("domcontentloaded");

    // Wait for video player (Omakase) or image viewer
    const hasVideoPlayer = await page
      .locator('video, [class*="omakase"], [data-testid="video-viewer"]')
      .first()
      .waitFor({ state: "visible", timeout: 15000 })
      .then(() => true)
      .catch(() => false);

    if (hasVideoPlayer) {
      console.log("[perf] Video player found, waiting for video to load...");

      // Wait for video metadata to load
      await page
        .waitForFunction(
          () => {
            const video = document.querySelector("video");
            return video && video.readyState >= 1;
          },
          { timeout: 20000 }
        )
        .catch(() => {
          console.log("[perf] Video metadata did not load in time");
        });

      const videoMetrics = await captureVideoMetrics(page, "video");
      report.videoMetrics.push(videoMetrics);

      console.log(`[perf] Video TTFB: ${videoMetrics.videoFirstByte.toFixed(0)}ms`);
      console.log(`[perf] Video resolution: ${videoMetrics.videoResolution}`);
      console.log(`[perf] Player lib load: ${videoMetrics.playerLibraryLoadTime.toFixed(0)}ms`);
    } else {
      console.log("[perf] No video player on this asset — image or audio asset");
    }

    await page.waitForLoadState("networkidle").catch(() => {});
    const detailReady = Date.now() - detailStart;

    const metrics = await capturePageMetrics(page);
    report.pageLoads.push(metrics);

    console.log(`[perf] Asset detail ready in ${detailReady}ms`);
    console.log(`[perf] Asset detail resources: ${metrics.resourceCount}`);
  });

  test.afterAll(() => {
    // Save the benchmark report
    const filepath = saveBenchmarkReport(report);
    console.log(`[perf] Benchmark report saved: ${filepath}`);
  });
});
