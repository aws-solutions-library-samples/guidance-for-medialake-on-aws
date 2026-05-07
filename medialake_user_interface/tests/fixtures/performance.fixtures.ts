import { test as authBase } from "./perf-auth.fixtures";
import { Page, expect } from "@playwright/test";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** Metrics captured for every page load */
export interface PageLoadMetrics {
  url: string;
  timestamp: string;
  // Navigation Timing
  dnsLookup: number;
  tcpConnect: number;
  tlsHandshake: number;
  ttfb: number;
  domContentLoaded: number;
  domComplete: number;
  loadComplete: number;
  // Web Vitals
  lcp: number | null;
  fcp: number | null;
  cls: number | null;
  // Transfer
  transferSize: number;
  resourceCount: number;
}

/** Metrics specific to video/audio player performance */
export interface VideoPlayerMetrics {
  url: string;
  timestamp: string;
  playerInitTime: number;
  timeToFirstFrame: number;
  bufferingEvents: number;
  totalBufferingDuration: number;
  videoLoadStart: number;
  videoFirstByte: number;
  videoResolution: string;
  videoDuration: number;
  playerLibraryLoadTime: number;
}

/** Full benchmark report for a single test run */
export interface BenchmarkReport {
  runId: string;
  environment: string;
  commitSha: string;
  branch: string;
  timestamp: string;
  pageLoads: PageLoadMetrics[];
  videoMetrics: VideoPlayerMetrics[];
}

export interface PerformanceFixtures {
  capturePageMetrics: (page: Page) => Promise<PageLoadMetrics>;
  captureVideoMetrics: (page: Page, videoSelector: string) => Promise<VideoPlayerMetrics>;
}

/**
 * Collects Navigation Timing + Web Vitals from the current page.
 */
async function collectPageMetrics(page: Page): Promise<PageLoadMetrics> {
  return page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    const resources = performance.getEntriesByType("resource");

    let fcp: number | null = null;
    const paintEntries = performance.getEntriesByType("paint");
    const fcpEntry = paintEntries.find((e) => e.name === "first-contentful-paint");
    if (fcpEntry) fcp = fcpEntry.startTime;

    // Read instrumented LCP/CLS from PerformanceObservers
    const lcpEntries = (window as any).__perf_lcp_entries || [];
    const lcp = lcpEntries.length ? lcpEntries[lcpEntries.length - 1].startTime : null;
    const cls = (window as any).__perf_cls_value ?? null;

    const totalTransfer = resources.reduce(
      (sum, r) => sum + ((r as PerformanceResourceTiming).transferSize || 0),
      0
    );

    return {
      url: location.href,
      timestamp: new Date().toISOString(),
      dnsLookup: nav.domainLookupEnd - nav.domainLookupStart,
      tcpConnect: nav.connectEnd - nav.connectStart,
      tlsHandshake: nav.secureConnectionStart ? nav.connectEnd - nav.secureConnectionStart : 0,
      ttfb: nav.responseStart - nav.requestStart,
      domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
      domComplete: nav.domComplete - nav.startTime,
      loadComplete: nav.loadEventEnd - nav.startTime,
      lcp,
      fcp,
      cls,
      transferSize: totalTransfer,
      resourceCount: resources.length,
    };
  });
}

/**
 * Captures video player performance by monitoring network requests,
 * DOM events, and the Omakase player lifecycle.
 */
async function collectVideoMetrics(page: Page, videoSelector: string): Promise<VideoPlayerMetrics> {
  return page.evaluate((selector) => {
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];

    const mediaResources = resources.filter(
      (r) =>
        r.initiatorType === "video" ||
        r.initiatorType === "xmlhttprequest" ||
        r.name.match(/\.(mp4|m3u8|mpd|webm|ts|m4s)/i)
    );

    const playerLib = resources.find(
      (r) => r.name.includes("omakase") || r.name.includes("player")
    );

    const videoEl = document.querySelector(`${selector} video, video`) as HTMLVideoElement | null;

    const firstMedia = mediaResources[0];

    return {
      url: location.href,
      timestamp: new Date().toISOString(),
      playerInitTime: (window as any).__perf_player_ready
        ? (window as any).__perf_player_ready - (window as any).__perf_player_mount
        : -1,
      timeToFirstFrame: (window as any).__perf_first_frame
        ? (window as any).__perf_first_frame - (window as any).__perf_player_mount
        : -1,
      bufferingEvents: (window as any).__perf_buffering_count || 0,
      totalBufferingDuration: (window as any).__perf_buffering_total || 0,
      videoLoadStart: firstMedia?.startTime ?? -1,
      videoFirstByte: firstMedia ? firstMedia.responseStart - firstMedia.requestStart : -1,
      videoResolution: videoEl ? `${videoEl.videoWidth}x${videoEl.videoHeight}` : "unknown",
      videoDuration: videoEl?.duration ?? -1,
      playerLibraryLoadTime: playerLib?.duration ?? -1,
    };
  }, videoSelector);
}

const RESULTS_DIR = path.join(__dirname, "..", "..", "test-results", "perf-results");

function ensureResultsDir() {
  if (!fs.existsSync(RESULTS_DIR)) {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
  }
}

/**
 * Extended Playwright test fixture that chains off auth fixtures.
 * Tests get an authenticatedPage that's already logged in.
 */
export const test = authBase.extend<PerformanceFixtures>({
  capturePageMetrics: async ({}, use) => {
    const capture = async (page: Page): Promise<PageLoadMetrics> => {
      await page.waitForLoadState("load");
      await page.waitForTimeout(1000);
      return collectPageMetrics(page);
    };
    await use(capture);
  },

  captureVideoMetrics: async ({}, use) => {
    const capture = async (page: Page, videoSelector: string): Promise<VideoPlayerMetrics> => {
      return collectVideoMetrics(page, videoSelector);
    };
    await use(capture);
  },
});

export { expect } from "@playwright/test";

/**
 * Writes the benchmark report to disk as JSON for CI artifact collection.
 */
export function saveBenchmarkReport(report: BenchmarkReport): string {
  ensureResultsDir();
  const filename = `benchmark-${report.branch}-${Date.now()}.json`;
  const filepath = path.join(RESULTS_DIR, filename);
  fs.writeFileSync(filepath, JSON.stringify(report, null, 2));
  return filepath;
}

/**
 * Loads a previous benchmark report for comparison.
 */
export function loadBaselineReport(filepath: string): BenchmarkReport | null {
  if (!fs.existsSync(filepath)) return null;
  return JSON.parse(fs.readFileSync(filepath, "utf-8"));
}

/**
 * Compares two benchmark reports and returns regressions/improvements.
 */
export function compareReports(
  baseline: BenchmarkReport,
  current: BenchmarkReport
): {
  regressions: string[];
  improvements: string[];
  unchanged: string[];
} {
  const regressions: string[] = [];
  const improvements: string[] = [];
  const unchanged: string[] = [];

  for (const currentPage of current.pageLoads) {
    const baselinePage = baseline.pageLoads.find(
      (b) => new URL(b.url).pathname === new URL(currentPage.url).pathname
    );
    if (!baselinePage) continue;

    const threshold = 0.1; // 10% regression threshold
    const metrics: (keyof PageLoadMetrics)[] = ["ttfb", "domContentLoaded", "loadComplete", "lcp"];

    for (const metric of metrics) {
      const base = baselinePage[metric] as number;
      const curr = currentPage[metric] as number;
      if (base == null || curr == null) continue;

      const diff = (curr - base) / base;
      const pathname = new URL(currentPage.url).pathname;

      if (diff > threshold) {
        regressions.push(
          `${pathname} ${metric}: ${base.toFixed(0)}ms → ${curr.toFixed(0)}ms (+${(
            diff * 100
          ).toFixed(1)}%)`
        );
      } else if (diff < -threshold) {
        improvements.push(
          `${pathname} ${metric}: ${base.toFixed(0)}ms → ${curr.toFixed(0)}ms (${(
            diff * 100
          ).toFixed(1)}%)`
        );
      } else {
        unchanged.push(`${pathname} ${metric}: ~${curr.toFixed(0)}ms`);
      }
    }
  }

  return { regressions, improvements, unchanged };
}
