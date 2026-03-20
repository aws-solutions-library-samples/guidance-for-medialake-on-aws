import { defineConfig, devices } from "@playwright/test";

/**
 * Smoke test configuration.
 *
 * Runs the comprehensive UI smoke tests against localhost.
 * Uses a static test account (no Cognito user creation).
 *
 * Usage:
 *   npx playwright test --config=playwright.smoke.config.ts
 *   npx playwright test --config=playwright.smoke.config.ts --headed
 *   npx playwright test --config=playwright.smoke.config.ts --ui
 */
export default defineConfig({
  testDir: "./tests/smoke",
  fullyParallel: false, // Sequential — tests share auth state assumptions
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 1, // Retry once — Cognito rate limits can cause auth timeouts
  workers: 1, // Single worker — avoids auth race conditions
  timeout: 60000,
  reporter: [["list"], ["html", { outputFolder: "smoke-report", open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});
