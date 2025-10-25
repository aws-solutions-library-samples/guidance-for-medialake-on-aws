import { defineConfig, devices } from "@playwright/test";

/**
 * CI-specific Playwright configuration
 * Extends base config with CI-optimized settings
 */
export default defineConfig({
  testDir: "./tests",

  // Exclude old local dev tests that aren't compatible with CloudFront deployments
  testIgnore: [
    "**/auth/login.spec.ts", // Old local dev test (uses localhost:5173)
    "**/cloudfront/**/*.spec.ts", // CloudFront-specific tests (not full integration)
  ],

  // Only run integration tests in CI
  testMatch: ["**/integration/**/*.spec.ts"],

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: true,

  /* Retry failed tests up to 2 times */
  retries: 2,

  /* Use multiple workers for faster execution */
  workers: process.env.CI_WORKERS ? parseInt(process.env.CI_WORKERS) : 4,

  /* Timeout for each test (2 minutes) */
  timeout: 120000,

  /* Reporter configuration for CI */
  reporter: [
    ["list"], // Console output
    ["junit", { outputFile: "test-results/junit.xml" }], // JUnit XML for GitLab
    ["html", { outputFolder: "playwright-report", open: "never" }], // HTML report
  ],

  /* Shared settings for all the projects below */
  use: {
    /* Base URL from environment variable (CloudFront domain) */
    baseURL: process.env.PLAYWRIGHT_BASE_URL,

    /* Collect trace on first retry for debugging */
    trace: "on-first-retry",

    /* Screenshot on failure */
    screenshot: "only-on-failure",

    /* Video on retry for debugging */
    video: "retain-on-failure",

    /* Increase timeout for slower CI environments */
    actionTimeout: 30000,
    navigationTimeout: 60000,
  },

  /* Configure projects for major browsers - CI only runs Chromium for speed */
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Add more logging for debugging
        launchOptions: {
          args: [
            "--disable-web-security", // Allow CORS for CloudFront
            "--disable-features=IsolateOrigins,site-per-process", // Reduce isolation for testing
          ],
        },
      },
    },
  ],

  /* No local dev server in CI - tests run against deployed CloudFront */
});
