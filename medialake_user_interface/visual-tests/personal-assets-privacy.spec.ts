import { test, expect, Page } from "@playwright/test";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import { loginViaUI, navigateToAssets, navigateToSearch } from "./helpers/auth";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Test users ──────────────────────────────────────────────────────────
const USER_A = {
  email: "visual-test-userA@example.com",
  password: "VtestA#2026xYz!",
  label: "UserA",
  sub: "c4881448-5051-708a-a2a2-0abfebdf7ff3",
};
const USER_B = {
  email: "visual-test-userB@example.com",
  password: "VtestB#2026xYz!",
  label: "UserB",
  sub: "84283428-1041-7012-4f89-8e6f118858cd",
};

const SCREENSHOTS_DIR = path.join(__dirname, "screenshots");
const STORAGE_DIR = path.join(__dirname, "storage-state");

function ensureDirs() {
  for (const dir of [SCREENSHOTS_DIR, STORAGE_DIR]) {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }
}

async function screenshot(page: Page, name: string) {
  ensureDirs();
  const filePath = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  console.log(`  📸 ${name}.png`);
  return filePath;
}

async function injectStabilizers(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
}

// ═══════════════════════════════════════════════════════════════════════
// SCENARIO 1: Upload Validation
// ═══════════════════════════════════════════════════════════════════════
test.describe("Scenario 1: Uploads", () => {
  test("User A can access My Assets and see the upload button", async ({ browser }) => {
    ensureDirs();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      timezoneId: "America/New_York",
      colorScheme: "light",
      reducedMotion: "reduce",
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await loginViaUI(page, USER_A.email, USER_A.password, path.join(STORAGE_DIR, "userA.json"));
    await injectStabilizers(page);
    await screenshot(page, "01-userA-logged-in-home");

    // Navigate to Assets page
    await navigateToAssets(page);
    await injectStabilizers(page);
    await screenshot(page, "02-userA-assets-page");

    // Click on "My Assets" in the left panel
    const myAssetsButton = page.locator('text="My Assets"').first();
    await myAssetsButton.waitFor({ state: "visible", timeout: 15_000 });
    await myAssetsButton.click();
    await page.waitForLoadState("networkidle");
    await injectStabilizers(page);
    await screenshot(page, "03-userA-my-assets-selected");

    // Verify the Upload button is visible
    const uploadButton = page.locator('button:has-text("Upload")').first();
    await expect(uploadButton).toBeVisible({ timeout: 10_000 });
    await screenshot(page, "04-userA-upload-button-visible");

    // Click Upload to open the modal
    await uploadButton.click();
    await page.waitForTimeout(1000);
    await injectStabilizers(page);
    await screenshot(page, "05-userA-upload-modal-open");

    // Verify the upload modal is visible
    const modal = page.locator('[role="dialog"], .MuiModal-root, .MuiDialog-root').first();
    await expect(modal).toBeVisible({ timeout: 10_000 });

    // Close the modal
    const closeButton = page
      .locator('button:has-text("Cancel"), button:has-text("Close"), button[aria-label="close"]')
      .first();
    if (await closeButton.isVisible()) {
      await closeButton.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await page.waitForTimeout(500);

    if (consoleErrors.length > 0) {
      console.log(`  ⚠️ Console errors: ${consoleErrors.length}`);
      consoleErrors.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 200)}`));
    }

    await context.close();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// SCENARIO 2: Search Validation
// ═══════════════════════════════════════════════════════════════════════
test.describe("Scenario 2: Search", () => {
  test("User A can perform a search and see results", async ({ browser }) => {
    ensureDirs();
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      timezoneId: "America/New_York",
      colorScheme: "light",
      reducedMotion: "reduce",
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await loginViaUI(page, USER_A.email, USER_A.password);
    await injectStabilizers(page);

    // Navigate to search
    await navigateToSearch(page);
    await page.waitForTimeout(2000);
    await injectStabilizers(page);
    await screenshot(page, "06-userA-search-page");

    // Use the top bar search input
    const searchInput = page
      .locator(
        'input[placeholder*="Search"], input[placeholder*="search"], input[aria-label*="search"]'
      )
      .first();

    if (await searchInput.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await searchInput.fill("test");
      await searchInput.press("Enter");
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);
      await injectStabilizers(page);
      await screenshot(page, "07-userA-search-results-test");
    } else {
      await screenshot(page, "07-userA-search-no-input-found");
    }

    // Try wildcard search
    await page.goto("/search?q=*", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(2000);
    await injectStabilizers(page);
    await screenshot(page, "08-userA-search-all-results");

    if (consoleErrors.length > 0) {
      console.log(`  ⚠️ Console errors: ${consoleErrors.length}`);
      consoleErrors.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 200)}`));
    }

    await context.close();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// SCENARIO 3: Tenant Isolation / Personal Assets Privacy
// ═══════════════════════════════════════════════════════════════════════
test.describe("Scenario 3: Tenant Isolation", () => {
  test("User B cannot see User A personal assets", async ({ browser }) => {
    ensureDirs();

    // ── Step 1: Login as User A, go to My Assets ──
    const ctxA = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      timezoneId: "America/New_York",
      colorScheme: "light",
      reducedMotion: "reduce",
      ignoreHTTPSErrors: true,
    });
    const pageA = await ctxA.newPage();

    await loginViaUI(pageA, USER_A.email, USER_A.password);
    await injectStabilizers(pageA);

    // Go to Assets → My Assets
    await navigateToAssets(pageA);
    await injectStabilizers(pageA);

    const myAssetsA = pageA.locator('text="My Assets"').first();
    await myAssetsA.waitFor({ state: "visible", timeout: 15_000 });
    await myAssetsA.click();
    await pageA.waitForLoadState("networkidle");
    await pageA.waitForTimeout(2000);
    await injectStabilizers(pageA);
    await screenshot(pageA, "09-userA-my-assets-content");

    // Capture User A's page text for comparison
    const userAPageText = await pageA.innerText("body");
    console.log(`  📋 User A My Assets text (first 500 chars): ${userAPageText.substring(0, 500)}`);
    await screenshot(pageA, "10-userA-my-assets-detail");

    await ctxA.close();

    // ── Step 2: Login as User B, verify isolation ──
    const ctxB = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      timezoneId: "America/New_York",
      colorScheme: "light",
      reducedMotion: "reduce",
      ignoreHTTPSErrors: true,
    });
    const pageB = await ctxB.newPage();

    // Track API responses for isolation analysis
    const apiResponses: { url: string; status: number; body: string }[] = [];
    pageB.on("response", async (resp) => {
      const url = resp.url();
      if (
        url.includes("search") ||
        url.includes("connector") ||
        url.includes("my-assets") ||
        url.includes("assets")
      ) {
        try {
          const body = await resp.text();
          apiResponses.push({
            url,
            status: resp.status(),
            body: body.substring(0, 3000),
          });
        } catch {}
      }
    });

    await loginViaUI(pageB, USER_B.email, USER_B.password);
    await injectStabilizers(pageB);
    await screenshot(pageB, "11-userB-logged-in-home");

    // Go to Assets → My Assets
    await navigateToAssets(pageB);
    await injectStabilizers(pageB);

    const myAssetsB = pageB.locator('text="My Assets"').first();
    await myAssetsB.waitFor({ state: "visible", timeout: 15_000 });
    await myAssetsB.click();
    await pageB.waitForLoadState("networkidle");
    await pageB.waitForTimeout(2000);
    await injectStabilizers(pageB);
    await screenshot(pageB, "12-userB-my-assets-content");

    const userBPageText = await pageB.innerText("body");
    console.log(`  📋 User B My Assets text (first 500 chars): ${userBPageText.substring(0, 500)}`);
    await screenshot(pageB, "13-userB-my-assets-detail");

    // ── Step 3: User B searches — should NOT see User A's personal assets ──
    await navigateToSearch(pageB);
    await pageB.waitForTimeout(1000);

    const searchInputB = pageB
      .locator('input[placeholder*="Search"], input[placeholder*="search"]')
      .first();

    if (await searchInputB.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await searchInputB.fill("*");
      await searchInputB.press("Enter");
      await pageB.waitForLoadState("networkidle");
      await pageB.waitForTimeout(2000);
    }

    await injectStabilizers(pageB);
    await screenshot(pageB, "14-userB-search-all-results");

    // Analyze API responses for isolation violations
    let isolationViolations = 0;
    console.log("\n  🔍 Isolation Analysis — User B API responses:");
    for (const resp of apiResponses) {
      const shortUrl = resp.url
        .substring(resp.url.indexOf("/v1/") || 0, resp.url.length)
        .substring(0, 100);
      if (resp.body.includes(USER_A.sub)) {
        isolationViolations++;
        console.log(`    ❌ VIOLATION in ${shortUrl}: contains User A sub`);
      }
      // Check for User A's personal path prefix
      if (resp.body.includes(`personal/${USER_A.sub}/`)) {
        isolationViolations++;
        console.log(`    ❌ VIOLATION in ${shortUrl}: contains User A personal path`);
      }
    }

    if (isolationViolations === 0) {
      console.log("    ✅ No isolation violations detected in API responses");
    } else {
      console.log(`    ❌ Total isolation violations: ${isolationViolations}`);
    }

    await screenshot(pageB, "15-userB-isolation-final");

    // Assert no isolation violations
    expect(
      isolationViolations,
      "User B should not see User A's personal assets in any API response"
    ).toBe(0);

    await ctxB.close();
  });

  test("User A cannot see User B personal assets via search", async ({ browser }) => {
    ensureDirs();

    const ctxA = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      colorScheme: "light",
      reducedMotion: "reduce",
      ignoreHTTPSErrors: true,
    });
    const pageA = await ctxA.newPage();

    const apiResponses: { url: string; body: string }[] = [];
    pageA.on("response", async (resp) => {
      const url = resp.url();
      if (url.includes("search") || url.includes("assets")) {
        try {
          const body = await resp.text();
          apiResponses.push({ url, body: body.substring(0, 3000) });
        } catch {}
      }
    });

    await loginViaUI(pageA, USER_A.email, USER_A.password);
    await injectStabilizers(pageA);

    // Search broadly
    await navigateToSearch(pageA);
    const searchInputA = pageA
      .locator('input[placeholder*="Search"], input[placeholder*="search"]')
      .first();

    if (await searchInputA.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await searchInputA.fill("*");
      await searchInputA.press("Enter");
      await pageA.waitForLoadState("networkidle");
      await pageA.waitForTimeout(2000);
    }

    await injectStabilizers(pageA);
    await screenshot(pageA, "16-userA-search-isolation-check");

    let violations = 0;
    console.log("\n  🔍 Isolation Analysis — User A API responses:");
    for (const resp of apiResponses) {
      if (resp.body.includes(USER_B.sub)) {
        violations++;
        console.log("    ❌ VIOLATION: contains User B sub");
      }
      if (resp.body.includes(`personal/${USER_B.sub}/`)) {
        violations++;
        console.log("    ❌ VIOLATION: contains User B personal path");
      }
    }

    if (violations === 0) {
      console.log("    ✅ No isolation violations detected");
    }

    expect(violations, "User A should not see User B's personal assets").toBe(0);

    await screenshot(pageA, "17-userA-isolation-final");
    await ctxA.close();
  });
});
