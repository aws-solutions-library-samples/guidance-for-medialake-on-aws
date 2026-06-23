import { defineConfig, devices } from "@playwright/test";

/**
 * Standalone visual config used to drive Playwright against an ALREADY-RUNNING
 * target (no managed webServer). Point it with PLAYWRIGHT_BASE_URL:
 *
 *   - Deployed env (captures the CURRENT deployed UI):
 *       PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net
 *   - Local working tree (captures the uncommitted CHANGES) — start the dev
 *     server yourself first (`npm run dev`), then:
 *       PLAYWRIGHT_BASE_URL=http://localhost:5173
 *
 * Deliberately has NO `webServer` block so it never tries to spawn `npm run dev`.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir: "test-results/visual-output",
  timeout: 90_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "https://d2gn8nwil93iye.cloudfront.net",
    headless: true,
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
});
