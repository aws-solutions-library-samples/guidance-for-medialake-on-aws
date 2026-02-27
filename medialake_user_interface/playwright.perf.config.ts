import { defineConfig, devices } from "@playwright/test";
import { resolveCloudFrontUrlSync } from "./tests/utils/cloudfront-url-resolver";

/**
 * Performance benchmark Playwright config.
 *
 * Auto-detects the CloudFront URL via SSM / tags / listing.
 * Override with env vars if needed:
 *
 *   # Explicit URL
 *   PLAYWRIGHT_BASE_URL=https://d1234.cloudfront.net npx playwright test --config=playwright.perf.config.ts
 *
 *   # AWS profile + environment
 *   AWS_PROFILE=my-profile MEDIALAKE_ENV=staging npx playwright test --config=playwright.perf.config.ts
 *
 *   # All options
 *   AWS_PROFILE=prod-account AWS_REGION=eu-west-1 MEDIALAKE_ENV=prod npx playwright test --config=playwright.perf.config.ts
 */

const baseURL = resolveCloudFrontUrlSync();

console.log(`[perf-config] Using base URL: ${baseURL}`);

export default defineConfig({
  testDir: "./tests/performance",
  testMatch: ["**/*.spec.ts"],

  fullyParallel: false, // Serial for consistent measurements
  forbidOnly: !!process.env.CI,
  retries: 0, // No retries — we want raw numbers
  workers: 1, // Single worker to avoid resource contention

  timeout: 120000, // 2 min per test (video playback tests need time)

  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/perf-results/playwright-results.json" }],
    ["html", { outputFolder: "test-results/perf-report", open: "never" }],
  ],

  use: {
    baseURL,
    trace: "off", // Tracing adds overhead — disable for perf tests
    screenshot: "off",
    video: "on",
    actionTimeout: 30000,
    navigationTimeout: 60000,
  },

  projects: [
    {
      name: "perf-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
        launchOptions: {
          args: [
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-default-apps",
            "--no-first-run",
            "--disable-gpu-compositing",
          ],
        },
      },
    },
  ],
});
