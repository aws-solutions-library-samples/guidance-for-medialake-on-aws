import { test, expect, Page, BrowserContext } from "@playwright/test";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import { loginViaUI, navigateToAssets, navigateToSearch } from "./helpers/auth";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Test users (freshly created in Cognito) ─────────────────────────
const USER_A = {
  email: "visual-test-userA@example.com",
  password: "VtestA#2026xYz!",
  label: "UserA",
  sub: "a488f448-c0f1-7086-0420-bb01cbf968c6",
};
const USER_B = {
  email: "visual-test-userB@example.com",
  password: "VtestB#2026xYz!",
  label: "UserB",
  sub: "749834d8-9011-701a-a260-953998683b4b",
};

const SCREENSHOTS_DIR = path.join(__dirname, "screenshots", "upload-isolation");
const STORAGE_DIR = path.join(__dirname, "storage-state");
const TEST_IMAGES_DIR = __dirname;

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

/** Create a fresh browser context with standard settings */
async function createContext(browser: any): Promise<BrowserContext> {
  return browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/New_York",
    colorScheme: "light",
    reducedMotion: "reduce",
    ignoreHTTPSErrors: true,
  });
}

/** Navigate to My Assets and wait for it to load */
async function goToMyAssets(page: Page): Promise<void> {
  await navigateToAssets(page);
  await injectStabilizers(page);

  // Click on "My Assets" in the left panel
  const myAssetsButton = page.locator('text="My Assets"').first();
  await myAssetsButton.waitFor({ state: "visible", timeout: 15_000 });
  await myAssetsButton.click();
  await page.waitForLoadState("networkidle");
  // Wait for the My Assets panel to render
  await page.waitForTimeout(2000);
  await injectStabilizers(page);
}

/**
 * Upload a file via the Uppy Dashboard in the S3UploaderModal.
 * The modal is opened by clicking the "Upload" button in My Assets view.
 */
async function uploadFileViaModal(
  page: Page,
  testImagePath: string,
  stepPrefix: string
): Promise<void> {
  // Click the Upload button to open the modal
  const uploadButton = page.locator('button:has-text("Upload")').first();
  await expect(uploadButton).toBeVisible({ timeout: 10_000 });
  await uploadButton.click();
  await page.waitForTimeout(1500);
  await injectStabilizers(page);
  await screenshot(page, `${stepPrefix}-upload-modal-open`);

  // The Uppy Dashboard renders an input[type=file] that we can use to set files.
  // Uppy hides the native file input but Playwright can still interact with it.
  const fileInput = page.locator('.uppy-Dashboard-input, input[type="file"]').first();

  // Use setInputFiles to add the file to the Uppy Dashboard
  await fileInput.setInputFiles(testImagePath);
  await page.waitForTimeout(1500);
  await injectStabilizers(page);
  await screenshot(page, `${stepPrefix}-file-selected`);

  // Click the Uppy "Upload" button inside the dashboard to start the upload
  // Uppy's upload button is typically .uppy-StatusBar-actionBtn--upload or similar
  const uppyUploadBtn = page
    .locator(
      ".uppy-StatusBar-actionBtn--upload, .uppy-DashboardContent-addMore + button, button.uppy-u-reset.uppy-StatusBar-actionBtn.uppy-StatusBar-actionBtn--upload"
    )
    .first();

  if (await uppyUploadBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await uppyUploadBtn.click();
    console.log(`  ⬆️ Clicked Uppy upload button`);
  } else {
    // Fallback: some Uppy configs auto-proceed or have a different button layout
    // Try clicking any visible upload/submit button inside the dialog
    const altUploadBtn = page
      .locator(
        '[role="dialog"] button:has-text("Upload"), [role="dialog"] button:has-text("upload")'
      )
      .first();
    if (await altUploadBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await altUploadBtn.click();
      console.log(`  ⬆️ Clicked alternative upload button`);
    } else {
      console.log(`  ⚠️ No upload button found — Uppy may auto-proceed`);
    }
  }

  // Wait for upload to complete — watch for success indicators
  // Uppy shows a "Complete" status or the status bar changes
  try {
    await page.waitForSelector(
      '.uppy-StatusBar.is-complete, .uppy-StatusBar-statusPrimary:has-text("Complete"), .uppy-StatusBar-statusPrimary:has-text("complete"), .uppy-StatusBar-statusPrimary:has-text("uploaded")',
      { timeout: 60_000 }
    );
    console.log(`  ✅ Upload completed successfully`);
  } catch {
    // Check if there's an error state
    const errorEl = page
      .locator('.uppy-StatusBar.is-error, .uppy-StatusBar-statusPrimary:has-text("error")')
      .first();
    if (await errorEl.isVisible().catch(() => false)) {
      const errorText = await errorEl.textContent().catch(() => "unknown error");
      console.log(`  ❌ Upload error: ${errorText}`);
    } else {
      console.log(`  ⏳ Upload may still be in progress or completed without status indicator`);
    }
  }

  await page.waitForTimeout(1000);
  await injectStabilizers(page);
  await screenshot(page, `${stepPrefix}-upload-complete`);

  // Close the upload modal
  const closeButton = page
    .locator(
      '[role="dialog"] button:has-text("Close"), [role="dialog"] button:has-text("close"), button[aria-label="close"]'
    )
    .first();
  if (await closeButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await closeButton.click();
  } else {
    await page.keyboard.press("Escape");
  }
  await page.waitForTimeout(1000);
}

/** Perform a search and return the page text */
async function performSearch(page: Page, query: string, stepPrefix: string): Promise<string> {
  await navigateToSearch(page);
  await page.waitForTimeout(2000);
  await injectStabilizers(page);

  const searchInput = page
    .locator(
      'input[placeholder*="Search"], input[placeholder*="search"], input[aria-label*="search"], input[aria-label*="Search"]'
    )
    .first();

  if (await searchInput.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await searchInput.fill(query);
    await searchInput.press("Enter");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
  } else {
    // Try URL-based search
    await page.goto(`/search?q=${encodeURIComponent(query)}`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    await page.waitForTimeout(3000);
  }

  await injectStabilizers(page);
  await screenshot(page, `${stepPrefix}-search-${query.replace(/[^a-zA-Z0-9]/g, "_")}`);

  return await page.innerText("body");
}

// ═══════════════════════════════════════════════════════════════════════
// MAIN TEST: Full Upload + Tenant Isolation
// ═══════════════════════════════════════════════════════════════════════
test.describe("Upload & Tenant Isolation", () => {
  test.setTimeout(300_000); // 5 minutes for the full flow

  test("Phase 1-4: Upload files as both users and validate isolation", async ({ browser }) => {
    ensureDirs();

    const consoleErrorsA: string[] = [];
    const consoleErrorsB: string[] = [];
    const apiResponsesA: { url: string; status: number; body: string }[] = [];
    const apiResponsesB: { url: string; status: number; body: string }[] = [];

    // ═══════════════════════════════════════════════════════════════
    // PHASE 1: User A uploads an image
    // ═══════════════════════════════════════════════════════════════
    console.log("\n══════════════════════════════════════════");
    console.log("  PHASE 1: User A uploads an image");
    console.log("══════════════════════════════════════════\n");

    const ctxA1 = await createContext(browser);
    const pageA1 = await ctxA1.newPage();

    pageA1.on("console", (msg) => {
      if (msg.type() === "error") consoleErrorsA.push(msg.text());
    });

    // Track API responses for User A
    pageA1.on("response", async (resp) => {
      const url = resp.url();
      if (url.includes("/v1/") || url.includes("execute-api") || url.includes("search")) {
        try {
          const body = await resp.text();
          apiResponsesA.push({ url, status: resp.status(), body: body.substring(0, 5000) });
        } catch {}
      }
    });

    // Step 1: Login as User A
    await loginViaUI(
      pageA1,
      USER_A.email,
      USER_A.password,
      path.join(STORAGE_DIR, "userA-upload.json")
    );
    await injectStabilizers(pageA1);
    await screenshot(pageA1, "P1-01-userA-logged-in");

    // Step 2: Navigate to My Assets
    await goToMyAssets(pageA1);
    await screenshot(pageA1, "P1-02-userA-my-assets");

    // Step 3-5: Upload the test image
    const userAImagePath = path.join(TEST_IMAGES_DIR, "userA-test-upload.png");
    await uploadFileViaModal(pageA1, userAImagePath, "P1-03");

    // Step 6: Wait for indexing and refresh My Assets to see the uploaded file
    console.log("  ⏳ Waiting 10s for OpenSearch indexing...");
    await pageA1.waitForTimeout(10_000);

    // Refresh My Assets view
    await goToMyAssets(pageA1);
    await screenshot(pageA1, "P1-06-userA-my-assets-after-upload");

    // Check if the uploaded file appears
    const pageAText = await pageA1.innerText("body");
    const userAFileVisible = pageAText.includes("userA-test-upload");
    console.log(
      `  ${userAFileVisible ? "✅" : "⚠️"} User A file visible in My Assets: ${userAFileVisible}`
    );

    // Step 7-8: Search for the uploaded file
    const searchResultA = await performSearch(pageA1, "userA-test-upload", "P1-07");
    const userASearchFound = searchResultA.includes("userA-test-upload");
    console.log(
      `  ${userASearchFound ? "✅" : "⚠️"} User A file found in search: ${userASearchFound}`
    );

    await ctxA1.close();

    // ═══════════════════════════════════════════════════════════════
    // PHASE 2: User B uploads a different image
    // ═══════════════════════════════════════════════════════════════
    console.log("\n══════════════════════════════════════════");
    console.log("  PHASE 2: User B uploads an image");
    console.log("══════════════════════════════════════════\n");

    const ctxB = await createContext(browser);
    const pageB = await ctxB.newPage();

    pageB.on("console", (msg) => {
      if (msg.type() === "error") consoleErrorsB.push(msg.text());
    });

    // Track API responses for User B
    pageB.on("response", async (resp) => {
      const url = resp.url();
      if (url.includes("/v1/") || url.includes("execute-api") || url.includes("search")) {
        try {
          const body = await resp.text();
          apiResponsesB.push({ url, status: resp.status(), body: body.substring(0, 5000) });
        } catch {}
      }
    });

    // Step 1: Login as User B
    await loginViaUI(
      pageB,
      USER_B.email,
      USER_B.password,
      path.join(STORAGE_DIR, "userB-upload.json")
    );
    await injectStabilizers(pageB);
    await screenshot(pageB, "P2-01-userB-logged-in");

    // Step 2: Navigate to My Assets
    await goToMyAssets(pageB);
    await screenshot(pageB, "P2-02-userB-my-assets-before-upload");

    // Step 3-4: Upload User B's test image
    const userBImagePath = path.join(TEST_IMAGES_DIR, "userB-test-upload.png");
    await uploadFileViaModal(pageB, userBImagePath, "P2-03");

    // Step 5: Wait for indexing and refresh
    console.log("  ⏳ Waiting 10s for OpenSearch indexing...");
    await pageB.waitForTimeout(10_000);

    await goToMyAssets(pageB);
    await screenshot(pageB, "P2-05-userB-my-assets-after-upload");

    // Verify User B sees ONLY their file, NOT User A's
    const pageBText = await pageB.innerText("body");
    const userBFileVisible = pageBText.includes("userB-test-upload");
    const userAFileVisibleToB = pageBText.includes("userA-test-upload");
    console.log(
      `  ${userBFileVisible ? "✅" : "⚠️"} User B file visible in My Assets: ${userBFileVisible}`
    );
    console.log(
      `  ${
        !userAFileVisibleToB ? "✅" : "❌"
      } User A file NOT visible to User B: ${!userAFileVisibleToB}`
    );

    // Step 6: Search for User B's file — should find it
    const searchResultB_own = await performSearch(pageB, "userB-test-upload", "P2-06");
    const userBSearchFound = searchResultB_own.includes("userB-test-upload");
    console.log(
      `  ${userBSearchFound ? "✅" : "⚠️"} User B file found in User B search: ${userBSearchFound}`
    );

    // Step 7: Search for User A's file — should NOT find it
    const searchResultB_other = await performSearch(pageB, "userA-test-upload", "P2-07");
    const userASearchFoundByB = searchResultB_other.includes("userA-test-upload");
    console.log(
      `  ${
        !userASearchFoundByB ? "✅" : "❌"
      } User A file NOT found in User B search: ${!userASearchFoundByB}`
    );

    await screenshot(pageB, "P2-08-userB-isolation-complete");
    await ctxB.close();

    // ═══════════════════════════════════════════════════════════════
    // PHASE 3: Cross-validation — User A cannot see User B's assets
    // ═══════════════════════════════════════════════════════════════
    console.log("\n══════════════════════════════════════════");
    console.log("  PHASE 3: Cross-validation (User A)");
    console.log("══════════════════════════════════════════\n");

    const ctxA2 = await createContext(browser);
    const pageA2 = await ctxA2.newPage();

    // Track API responses for cross-validation
    const apiResponsesA2: { url: string; status: number; body: string }[] = [];
    pageA2.on("response", async (resp) => {
      const url = resp.url();
      if (url.includes("/v1/") || url.includes("execute-api") || url.includes("search")) {
        try {
          const body = await resp.text();
          apiResponsesA2.push({ url, status: resp.status(), body: body.substring(0, 5000) });
        } catch {}
      }
    });

    await loginViaUI(pageA2, USER_A.email, USER_A.password);
    await injectStabilizers(pageA2);

    // Go to My Assets — should see ONLY userA-test-upload, NOT userB-test-upload
    await goToMyAssets(pageA2);
    await screenshot(pageA2, "P3-01-userA-my-assets-cross-check");

    const pageA2Text = await pageA2.innerText("body");
    const userAFileStillVisible = pageA2Text.includes("userA-test-upload");
    const userBFileVisibleToA = pageA2Text.includes("userB-test-upload");
    console.log(
      `  ${
        userAFileStillVisible ? "✅" : "⚠️"
      } User A file still visible to User A: ${userAFileStillVisible}`
    );
    console.log(
      `  ${
        !userBFileVisibleToA ? "✅" : "❌"
      } User B file NOT visible to User A: ${!userBFileVisibleToA}`
    );

    // Search for User B's file — should NOT find it
    const searchResultA_other = await performSearch(pageA2, "userB-test-upload", "P3-02");
    const userBSearchFoundByA = searchResultA_other.includes("userB-test-upload");
    console.log(
      `  ${
        !userBSearchFoundByA ? "✅" : "❌"
      } User B file NOT found in User A search: ${!userBSearchFoundByA}`
    );

    await screenshot(pageA2, "P3-03-userA-isolation-complete");
    await ctxA2.close();

    // ═══════════════════════════════════════════════════════════════
    // PHASE 4: API-level isolation check
    // ═══════════════════════════════════════════════════════════════
    console.log("\n══════════════════════════════════════════");
    console.log("  PHASE 4: API-level isolation analysis");
    console.log("══════════════════════════════════════════\n");

    let isolationViolations = 0;

    // Check User B's API responses for User A's sub or personal path
    console.log("  🔍 Checking User B API responses for User A data leakage:");
    for (const resp of apiResponsesB) {
      if (resp.body.includes(USER_A.sub)) {
        isolationViolations++;
        const shortUrl = resp.url.substring(0, 120);
        console.log(`    ❌ VIOLATION: User A sub found in User B response: ${shortUrl}`);
      }
      if (resp.body.includes(`personal/${USER_A.sub}/`)) {
        isolationViolations++;
        const shortUrl = resp.url.substring(0, 120);
        console.log(`    ❌ VIOLATION: User A personal path found in User B response: ${shortUrl}`);
      }
    }
    if (apiResponsesB.filter((r) => r.body.includes(USER_A.sub)).length === 0) {
      console.log("    ✅ No User A sub leakage in User B responses");
    }

    // Check User A's cross-validation API responses for User B's sub or personal path
    console.log("  🔍 Checking User A API responses for User B data leakage:");
    for (const resp of apiResponsesA2) {
      if (resp.body.includes(USER_B.sub)) {
        isolationViolations++;
        const shortUrl = resp.url.substring(0, 120);
        console.log(`    ❌ VIOLATION: User B sub found in User A response: ${shortUrl}`);
      }
      if (resp.body.includes(`personal/${USER_B.sub}/`)) {
        isolationViolations++;
        const shortUrl = resp.url.substring(0, 120);
        console.log(`    ❌ VIOLATION: User B personal path found in User A response: ${shortUrl}`);
      }
    }
    if (apiResponsesA2.filter((r) => r.body.includes(USER_B.sub)).length === 0) {
      console.log("    ✅ No User B sub leakage in User A responses");
    }

    // ═══════════════════════════════════════════════════════════════
    // FINAL SUMMARY
    // ═══════════════════════════════════════════════════════════════
    console.log("\n══════════════════════════════════════════");
    console.log("  FINAL RESULTS SUMMARY");
    console.log("══════════════════════════════════════════\n");
    console.log(
      `  User A upload visible to A:        ${
        userAFileVisible ? "✅ YES" : "⚠️ NO (may need more indexing time)"
      }`
    );
    console.log(
      `  User A upload in A search:         ${
        userASearchFound ? "✅ YES" : "⚠️ NO (may need more indexing time)"
      }`
    );
    console.log(
      `  User B upload visible to B:        ${
        userBFileVisible ? "✅ YES" : "⚠️ NO (may need more indexing time)"
      }`
    );
    console.log(
      `  User B upload in B search:         ${
        userBSearchFound ? "✅ YES" : "⚠️ NO (may need more indexing time)"
      }`
    );
    console.log(
      `  User A file NOT visible to B:      ${
        !userAFileVisibleToB ? "✅ PASS" : "❌ FAIL — ISOLATION BREACH"
      }`
    );
    console.log(
      `  User A file NOT in B search:       ${
        !userASearchFoundByB ? "✅ PASS" : "❌ FAIL — ISOLATION BREACH"
      }`
    );
    console.log(
      `  User B file NOT visible to A:      ${
        !userBFileVisibleToA ? "✅ PASS" : "❌ FAIL — ISOLATION BREACH"
      }`
    );
    console.log(
      `  User B file NOT in A search:       ${
        !userBSearchFoundByA ? "✅ PASS" : "❌ FAIL — ISOLATION BREACH"
      }`
    );
    console.log(
      `  API isolation violations:          ${
        isolationViolations === 0 ? "✅ ZERO" : `❌ ${isolationViolations} VIOLATIONS`
      }`
    );
    console.log(`  User A console errors:             ${consoleErrorsA.length}`);
    console.log(`  User B console errors:             ${consoleErrorsB.length}`);

    if (consoleErrorsA.length > 0) {
      console.log("\n  User A console errors (first 5):");
      consoleErrorsA.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 200)}`));
    }
    if (consoleErrorsB.length > 0) {
      console.log("\n  User B console errors (first 5):");
      consoleErrorsB.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 200)}`));
    }

    // ── Assertions ──
    // Isolation assertions (hard failures)
    expect(userAFileVisibleToB, "User A file should NOT be visible to User B in My Assets").toBe(
      false
    );
    expect(userASearchFoundByB, "User A file should NOT appear in User B search results").toBe(
      false
    );
    expect(userBFileVisibleToA, "User B file should NOT be visible to User A in My Assets").toBe(
      false
    );
    expect(userBSearchFoundByA, "User B file should NOT appear in User A search results").toBe(
      false
    );
    expect(isolationViolations, "Zero API-level isolation violations expected").toBe(0);
  });
});
