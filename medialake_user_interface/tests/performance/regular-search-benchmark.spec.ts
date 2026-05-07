import {
  test,
  expect,
  saveBenchmarkReport,
  BenchmarkReport,
} from "../fixtures/performance.fixtures";

/**
 * Regular (non-semantic) Search Performance Benchmark
 *
 * Measures the end-to-end time for a standard asset search with "*" query
 * (semantic toggle OFF). Captures API timing, render time, media loading,
 * and browser memory usage.
 *
 * Run with:
 *   AWS_PROFILE=ml-dev4 npx playwright test --config=playwright.perf.config.ts --grep "Regular Search"
 */

const THRESHOLDS = {
  searchApiResponse: 15000,
  resultsRendered: 20000,
  imagesLoaded: 20000,
  videosLoaded: 25000,
  totalSearchFlow: 60000,
};

const report: BenchmarkReport = {
  runId: `perf-regular-search-${Date.now()}`,
  environment: process.env.PLAYWRIGHT_BASE_URL || "auto-detected",
  commitSha: process.env.CI_COMMIT_SHA || "local",
  branch: process.env.CI_COMMIT_REF_NAME || "local",
  timestamp: new Date().toISOString(),
  pageLoads: [],
  videoMetrics: [],
};

test.describe("Regular Search Performance Benchmarks", () => {
  test.describe.configure({ mode: "serial" });

  test("regular search for * without semantic", async ({
    authenticatedPage,
    capturePageMetrics,
  }) => {
    const page = authenticatedPage;
    const flowStart = Date.now();
    const TAG = "[perf:search]";

    // 1. Wait for search bar
    console.log(`${TAG} Waiting for search bar...`);
    const searchInput = page.locator('input[type="text"]').first();
    await searchInput.waitFor({ state: "visible", timeout: 15000 });

    // 2. Ensure semantic toggle is OFF
    const semanticToggle = page.getByRole("switch", { name: /semantic/i });
    await semanticToggle.waitFor({ state: "visible", timeout: 5000 });
    const isSemanticOn = await semanticToggle.getAttribute("aria-checked");
    if (isSemanticOn === "true") {
      console.log(`${TAG} Semantic is ON, turning it OFF...`);
      await semanticToggle.click();
      await page.waitForTimeout(500);
    }
    console.log(`${TAG} Semantic toggle: OFF`);

    // 3. Intercept the search API response
    const searchApiTiming = page.waitForResponse(
      (resp) => resp.url().includes("/search") && resp.request().method() === "GET",
      { timeout: THRESHOLDS.searchApiResponse }
    );

    // 4. Type "*" and submit
    const searchStart = Date.now();
    console.log(`${TAG} Typing "*" and submitting...`);
    await searchInput.fill("*");
    await page.keyboard.press("Enter");

    // 5. Measure API response
    let apiResponseTime: number;
    let apiTotalResults: number | null = null;
    let apiReturnedResults: number | null = null;
    try {
      const response = await searchApiTiming;
      apiResponseTime = Date.now() - searchStart;
      const status = response.status();
      console.log(`${TAG} API responded in ${apiResponseTime}ms (status: ${status})`);

      if (status === 200) {
        try {
          const body = await response.json();
          apiTotalResults = body?.total ?? body?.totalResults ?? body?.hits?.total?.value ?? null;
          apiReturnedResults =
            body?.results?.length ?? body?.hits?.hits?.length ?? body?.data?.length ?? null;
          console.log(`${TAG} API total: ${apiTotalResults}, returned: ${apiReturnedResults}`);
        } catch {
          /* ignore */
        }
      }
    } catch {
      apiResponseTime = Date.now() - searchStart;
      console.warn(`${TAG} API did not respond within ${THRESHOLDS.searchApiResponse}ms`);
    }

    // 6. Wait for results to render
    console.log(`${TAG} Waiting for results...`);
    const resultsStart = Date.now();
    const hasResults = await page
      .locator('[data-testid^="asset-card-"]')
      .first()
      .waitFor({ state: "visible", timeout: THRESHOLDS.resultsRendered })
      .then(() => true)
      .catch(() => false);

    const resultsRenderedTime = Date.now() - resultsStart;
    const totalFlowTime = Date.now() - flowStart;

    // 7. Count results
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

    console.log(`${TAG} Total results (page text): ${totalResultCount}`);
    console.log(`${TAG} DOM cards rendered:         ${domCardCount}`);
    console.log(`${TAG} Cards in viewport:          ${visibleCardCount}`);
    console.log(`${TAG} DOM <video> elements:       ${domVideoElements}`);

    // 8. Wait for images
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
      .catch(() => {});
    const imagesLoadedTime = Date.now() - imagesStart;

    // 9. Wait for videos (readyState >= 3 HAVE_FUTURE_DATA)
    const videoCount = await page.locator("video").count();
    let videosLoadedTime = 0;
    if (videoCount > 0) {
      const videosStart = Date.now();
      await page
        .waitForFunction(
          () => {
            const videos = Array.from(document.querySelectorAll("video"));
            return videos.every((v) => v.readyState >= 3);
          },
          { timeout: THRESHOLDS.videosLoaded }
        )
        .catch(() => {});
      videosLoadedTime = Date.now() - videosStart;
    }

    // 10. Network idle
    await page.waitForLoadState("networkidle").catch(() => {});
    const totalFlowWithMedia = Date.now() - flowStart;

    // 11. Page metrics
    const metrics = await capturePageMetrics(page);
    report.pageLoads.push(metrics);

    // 12. Memory
    const memory = await page.evaluate(() => {
      const mem = (performance as any).memory;
      if (!mem) return null;
      return {
        usedJSHeapMB: Math.round((mem.usedJSHeapSize / 1024 / 1024) * 100) / 100,
        totalJSHeapMB: Math.round((mem.totalJSHeapSize / 1024 / 1024) * 100) / 100,
        heapLimitMB: Math.round((mem.jsHeapSizeLimit / 1024 / 1024) * 100) / 100,
      };
    });

    // 13. Log
    console.log(`${TAG} === Regular Search Benchmark Results ===`);
    console.log(`${TAG} API response:        ${apiResponseTime}ms`);
    console.log(`${TAG} API total results:   ${apiTotalResults}`);
    console.log(`${TAG} API returned results: ${apiReturnedResults}`);
    console.log(`${TAG} Results rendered:     ${resultsRenderedTime}ms`);
    console.log(`${TAG} DOM result count:     ${domCardCount}`);
    console.log(`${TAG} Cards in viewport:    ${visibleCardCount}`);
    console.log(`${TAG} DOM <video> elements: ${domVideoElements}`);
    console.log(`${TAG} Total results (page): ${totalResultCount}`);
    console.log(`${TAG} Images loaded:        ${imagesLoadedTime}ms (${imgCount} images)`);
    console.log(`${TAG} Videos loaded:        ${videosLoadedTime}ms (${videoCount} videos)`);
    console.log(`${TAG} Total flow (no media): ${totalFlowTime}ms`);
    console.log(`${TAG} Total flow (w/ media): ${totalFlowWithMedia}ms`);
    console.log(`${TAG} Page resources:       ${metrics.resourceCount}`);
    console.log(`${TAG} Transfer size:       ${(metrics.transferSize / 1024).toFixed(0)}KB`);
    if (memory) {
      console.log(`${TAG} JS heap used:        ${memory.usedJSHeapMB}MB`);
      console.log(`${TAG} JS heap total:       ${memory.totalJSHeapMB}MB`);
      console.log(`${TAG} JS heap limit:       ${memory.heapLimitMB}MB`);
    }

    // 14. Assertions
    expect(apiResponseTime).toBeLessThan(THRESHOLDS.searchApiResponse);
    expect(totalFlowWithMedia).toBeLessThan(THRESHOLDS.totalSearchFlow);
    if (hasResults) {
      expect(domCardCount).toBeGreaterThan(0);
      expect(resultsRenderedTime).toBeLessThan(THRESHOLDS.resultsRendered);
    }
  });

  test.afterAll(() => {
    const filepath = saveBenchmarkReport(report);
    console.log("[perf:search] Benchmark report saved:", filepath);
  });
});
