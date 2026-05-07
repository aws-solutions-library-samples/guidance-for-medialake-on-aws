import { defineConfig, devices } from "@playwright/test";
import { resolveCloudFrontUrlSync } from "./tests/utils/cloudfront-url-resolver";

/**
 * Pipeline E2E test config.
 *
 * Auto-detects CloudFront URL via SSM / tags / listing.
 * Override: PLAYWRIGHT_BASE_URL=https://... npx playwright test --config=playwright.pipelines.config.ts
 */

const baseURL = resolveCloudFrontUrlSync();
console.log(`[pipelines-config] Using base URL: ${baseURL}`);

export default defineConfig({
  testDir: "./tests/pipelines",
  testMatch: ["**/*.spec.ts"],

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 5,

  timeout: 720000,

  reporter: [["list"]],

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on",
    actionTimeout: 30000,
    navigationTimeout: 60000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
