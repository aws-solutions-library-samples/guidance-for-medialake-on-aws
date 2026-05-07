import {
  test,
  expect,
  saveBenchmarkReport,
  BenchmarkReport,
} from "../fixtures/performance.fixtures";

/**
 * Semantic Search Performance Benchmark
 *
 * Measures the end-to-end time for performing a semantic search with "*" query.
 * Uses the perf auth fixture chain to authenticate, then navigates to the main
 * page where the search bar and semantic toggle live in the TopBar.
 *
 * Run with:
 *   AWS_PROFILE=ml-dev2 npm run test:perf -- --grep "Semantic Search"
 */

const THRESHOLDS = {
  semanticToggleReady: 5000, // Time for semantic toggle to be interactive
  searchApiResponse: 15000, // Time for the /search API to respond
  resultsRendered: 20000, // Time for results to appear in the DOM
  imagesLoaded: 20000, // Time for all thumbnail images to finish loading
  videosLoaded: 25000, // Time for video elements to have metadata
  totalSearchFlow: 60000, // End-to-end: toggle + type + submit + results + media
};

const report: BenchmarkReport = {
  runId: `perf-semantic-search-${Date.now()}`,
  environment: process.env.PLAYWRIGHT_BASE_URL || "auto-detected",
  commitSha: process.env.CI_COMMIT_SHA || "local",
  branch: process.env.CI_COMMIT_REF_NAME || "local",
  timestamp: new Date().toISOString(),
  pageLoads: [],
  videoMetrics: [],
};

test.describe("Semantic Search Performance Benchmarks", () => {
  test.describe.configure({ mode: "serial" });

  test("semantic search for * with toggle enabled", async ({
    authenticatedPage,
    capturePageMetrics,
  }) => {
    const page = authenticatedPage;
    const flowStart = Date.now();

    // 1. Wait for the search pill / TopBar to be ready
    console.log("[perf:semantic] Waiting for search bar to be ready...");
    const searchInput = page.locator('input[type="text"]').first();
    await searchInput.waitFor({ state: "visible", timeout: 15000 });

    // 2. Find and activate the semantic toggle
    //    The toggle is a role="switch" with aria-label containing "semantic"
    console.log("[perf:semantic] Locating semantic toggle...");
    const semanticToggle = page.getByRole("switch", { name: /semantic/i });
    await semanticToggle.waitFor({ state: "visible", timeout: THRESHOLDS.semanticToggleReady });

    const toggleReadyTime = Date.now() - flowStart;
    console.log(`[perf:semantic] Semantic toggle ready in ${toggleReadyTime}ms`);

    // Check if semantic is already enabled (aria-checked)
    const isAlreadyEnabled = await semanticToggle.getAttribute("aria-checked");
    if (isAlreadyEnabled !== "true") {
      console.log("[perf:semantic] Enabling semantic search...");
      await semanticToggle.click();
      // Wait a beat for the toggle state to propagate
      await page.waitForTimeout(500);

      // If a config dialog appeared (semantic not configured), skip the test
      const configDialog = page.getByRole("dialog");
      const dialogVisible = await configDialog
        .waitFor({ state: "visible", timeout: 2000 })
        .then(() => true)
        .catch(() => false);

      if (dialogVisible) {
        console.log("[perf:semantic] Semantic search not configured — skipping benchmark");
        test.skip(true, "Semantic search provider not configured on this environment");
        return;
      }
    } else {
      console.log("[perf:semantic] Semantic search already enabled");
    }

    // 3. Verify the placeholder changed to the semantic hint
    const placeholder = await searchInput.getAttribute("placeholder");
    console.log(`[perf:semantic] Search placeholder: "${placeholder}"`);

    // 4. Set up API response interception for timing AND body
    const searchApiTiming = page.waitForResponse(
      (resp) => resp.url().includes("/search") && resp.request().method() === "GET",
      { timeout: THRESHOLDS.searchApiResponse }
    );

    // 5. Type "*" and submit
    const searchStart = Date.now();
    console.log('[perf:semantic] Typing "*" and submitting search...');
    await searchInput.fill("*");
    await page.keyboard.press("Enter");

    // 6. Measure API response time and extract total from response body
    let apiResponseTime: number;
    let apiTotalResults: number | null = null;
    let apiReturnedResults: number | null = null;
    try {
      const response = await searchApiTiming;
      apiResponseTime = Date.now() - searchStart;
      const status = response.status();
      console.log(
        `[perf:semantic] Search API responded in ${apiResponseTime}ms (status: ${status})`
      );

      if (status === 200) {
        try {
          const body = await response.json();
          apiTotalResults = body?.total ?? body?.totalResults ?? body?.hits?.total?.value ?? null;
          apiReturnedResults =
            body?.results?.length ?? body?.hits?.hits?.length ?? body?.data?.length ?? null;
          console.log(
            `[perf:semantic] API total results: ${apiTotalResults}, returned: ${apiReturnedResults}`
          );
        } catch {
          console.log("[perf:semantic] Could not parse API response body");
        }
      } else {
        console.warn(`[perf:semantic] Non-200 response: ${status}`);
      }
    } catch {
      apiResponseTime = Date.now() - searchStart;
      console.warn(
        `[perf:semantic] Search API did not respond within ${THRESHOLDS.searchApiResponse}ms`
      );
    }

    // 7. Wait for results to render in the DOM
    console.log("[perf:semantic] Waiting for search results to render...");
    const resultsStart = Date.now();

    // The search page renders asset cards in a virtualized grid
    const hasResults = await page
      .locator('[data-testid^="asset-card-"]')
      .first()
      .waitFor({ state: "visible", timeout: THRESHOLDS.resultsRendered })
      .then(() => true)
      .catch(() => false);

    const resultsRenderedTime = Date.now() - resultsStart;
    const totalFlowTime = Date.now() - flowStart;

    // 8. Count results
    //    "Found X results" text = true total from the API
    //    DOM count = only cards currently rendered (virtualized grid)
    const foundText = await page
      .locator("text=/Found \\d+ results/i")
      .first()
      .textContent()
      .catch(() => null);
    const totalResultCount = foundText ? parseInt(foundText.match(/(\d+)/)?.[1] || "0") : null;

    const domCardCount = hasResults
      ? await page.locator('[data-testid^="asset-card-"]').count()
      : 0;
    const domVideoElements = await page.locator("video").count();

    // Count how many cards are actually visible in the viewport
    const viewportSize = page.viewportSize() || { width: 1920, height: 1080 };
    let visibleCardCount = 0;
    if (domCardCount > 0) {
      const cards = page.locator('[data-testid^="asset-card-"]');
      for (let i = 0; i < domCardCount; i++) {
        const box = await cards
          .nth(i)
          .boundingBox()
          .catch(() => null);
        if (box && box.y + box.height > 0 && box.y < viewportSize.height) {
          visibleCardCount++;
        }
      }
    }

    console.log(`[perf:semantic] Total results (page text): ${totalResultCount}`);
    console.log(`[perf:semantic] DOM cards rendered:         ${domCardCount}`);
    console.log(`[perf:semantic] Cards in viewport:          ${visibleCardCount}`);
    console.log(`[perf:semantic] DOM <video> elements:       ${domVideoElements}`);

    // 9. Wait for all images (thumbnails / proxies) to finish loading
    console.log("[perf:semantic] Waiting for all images to load...");
    const imagesStart = Date.now();
    const imgCount = await page.locator("img").count();
    await page
      .waitForFunction(
        () => {
          const images = Array.from(document.querySelectorAll("img"));
          return images.length === 0 || images.every((img) => img.complete);
        },
        { timeout: THRESHOLDS.imagesLoaded }
      )
      .catch(() => {
        console.log("[perf:semantic] Some images may not have finished loading");
      });
    const imagesLoadedTime = Date.now() - imagesStart;
    console.log(`[perf:semantic] ${imgCount} image(s) loaded in ${imagesLoadedTime}ms`);

    // 10. Wait for video elements to have metadata (readyState >= 1 HAVE_METADATA)
    console.log("[perf:semantic] Checking for video elements...");
    const videoCount = await page.locator("video").count();
    let videosLoadedTime = 0;
    if (videoCount > 0) {
      console.log(
        `[perf:semantic] Found ${videoCount} video element(s), waiting for playable state (HAVE_FUTURE_DATA)...`
      );
      const videosStart = Date.now();
      await page
        .waitForFunction(
          () => {
            const videos = Array.from(document.querySelectorAll("video"));
            return videos.every((v) => v.readyState >= 3); // HAVE_FUTURE_DATA
          },
          { timeout: THRESHOLDS.videosLoaded }
        )
        .catch(() => {
          console.log("[perf:semantic] Some videos may not have reached playable state");
        });
      videosLoadedTime = Date.now() - videosStart;
      console.log(
        `[perf:semantic] ${videoCount} video(s) metadata loaded in ${videosLoadedTime}ms`
      );
    } else {
      console.log("[perf:semantic] No video elements found in results");
    }

    // 11. Wait for network to settle
    console.log("[perf:semantic] Waiting for network to settle...");
    await page.waitForLoadState("networkidle").catch(() => {
      console.log("[perf:semantic] Network did not fully settle within timeout");
    });

    const totalFlowWithMedia = Date.now() - flowStart;

    // 12. Capture standard page metrics
    const metrics = await capturePageMetrics(page);
    report.pageLoads.push(metrics);

    // 13. Capture browser memory usage
    const memory = await page.evaluate(() => {
      const mem = (performance as any).memory;
      if (!mem) return null;
      return {
        usedJSHeapMB: Math.round((mem.usedJSHeapSize / 1024 / 1024) * 100) / 100,
        totalJSHeapMB: Math.round((mem.totalJSHeapSize / 1024 / 1024) * 100) / 100,
        heapLimitMB: Math.round((mem.jsHeapSizeLimit / 1024 / 1024) * 100) / 100,
      };
    });

    // 14. Log all timings
    console.log("[perf:semantic] === Semantic Search Benchmark Results ===");
    console.log(`[perf:semantic] Toggle ready:        ${toggleReadyTime}ms`);
    console.log(`[perf:semantic] API response:        ${apiResponseTime}ms`);
    console.log(`[perf:semantic] API total results:   ${apiTotalResults}`);
    console.log(`[perf:semantic] API returned results: ${apiReturnedResults}`);
    console.log(`[perf:semantic] Results rendered:     ${resultsRenderedTime}ms`);
    console.log(`[perf:semantic] DOM cards rendered:   ${domCardCount}`);
    console.log(`[perf:semantic] Cards in viewport:   ${visibleCardCount}`);
    console.log(`[perf:semantic] DOM <video> elements: ${domVideoElements}`);
    console.log(`[perf:semantic] Total results (page): ${totalResultCount}`);
    console.log(`[perf:semantic] Images loaded:        ${imagesLoadedTime}ms (${imgCount} images)`);
    console.log(
      `[perf:semantic] Videos loaded:        ${videosLoadedTime}ms (${videoCount} videos)`
    );
    console.log(`[perf:semantic] Total flow (no media): ${totalFlowTime}ms`);
    console.log(`[perf:semantic] Total flow (w/ media): ${totalFlowWithMedia}ms`);
    console.log(`[perf:semantic] Page resources:       ${metrics.resourceCount}`);
    console.log(
      `[perf:semantic] Transfer size:       ${(metrics.transferSize / 1024).toFixed(0)}KB`
    );
    if (memory) {
      console.log(`[perf:semantic] JS heap used:        ${memory.usedJSHeapMB}MB`);
      console.log(`[perf:semantic] JS heap total:       ${memory.totalJSHeapMB}MB`);
      console.log(`[perf:semantic] JS heap limit:       ${memory.heapLimitMB}MB`);
    } else {
      console.log(`[perf:semantic] JS heap:             not available (non-Chromium browser)`);
    }

    // 15. Assertions
    expect(toggleReadyTime).toBeLessThan(THRESHOLDS.semanticToggleReady);
    expect(apiResponseTime).toBeLessThan(THRESHOLDS.searchApiResponse);
    expect(totalFlowWithMedia).toBeLessThan(THRESHOLDS.totalSearchFlow);

    if (hasResults) {
      expect(domCardCount).toBeGreaterThan(0);
      expect(resultsRenderedTime).toBeLessThan(THRESHOLDS.resultsRendered);
    } else {
      console.warn("[perf:semantic] No results rendered — environment may have no indexed assets");
    }
  });

  test.afterAll(() => {
    const filepath = saveBenchmarkReport(report);
    console.log(`[perf:semantic] Benchmark report saved: ${filepath}`);
  });
});
