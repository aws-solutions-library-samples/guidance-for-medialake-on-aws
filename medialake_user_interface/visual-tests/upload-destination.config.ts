import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: /upload-destination\.spec\.ts/,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "https://d2nbs1o5a0nxvc.cloudfront.net",
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/New_York",
    colorScheme: "light",
    reducedMotion: "reduce",
    ignoreHTTPSErrors: true,
    screenshot: "on",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium", viewport: { width: 1440, height: 900 } },
    },
  ],
  outputDir: "test-results/upload-destination",
});
