import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Vitest defaults to 5s. Rendering-heavy suites -- particularly the axe
    // accessibility scans -- land in the 5-7s range once the full suite runs in
    // parallel and the workers contend for CPU, so they failed intermittently
    // while passing in isolation. This is headroom for that contention, not for
    // genuinely hung tests, which still fail well before a CI timeout.
    testTimeout: 20000,
    hookTimeout: 20000,
    env: {
      VITE_WAF_CAPTCHA_API_KEY: "test-captcha-api-key",
    },
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "playwright", "tests"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/*.spec.{ts,tsx}",
        "src/test/**",
        "src/mocks/**",
        "src/main.tsx",
        "src/vite-env.d.ts",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
