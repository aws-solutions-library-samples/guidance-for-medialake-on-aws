import { defineConfig, devices } from "@playwright/test";
import { resolveCloudFrontUrlSync } from "./tests/utils/cloudfront-url-resolver";

/**
 * Playwright config for collections E2E tests.
 *
 * Usage:
 *   AWS_PROFILE=ml-dev2 npx playwright test --config=playwright.collections.config.ts
 *   AWS_PROFILE=ml-dev2 npx playwright test --config=playwright.collections.config.ts collection-crud
 */

const baseURL = resolveCloudFrontUrlSync();
console.log(`[collections-config] Using base URL: ${baseURL}`);

export default defineConfig({
  testDir: "./tests/collections",
  testMatch: ["**/*.spec.ts"],

  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Serial — tests share state (created collections)

  timeout: 60000,

  reporter: [
    ["list"],
    ["html", { outputFolder: "test-results/collections-report", open: "never" }],
  ],

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on",
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
