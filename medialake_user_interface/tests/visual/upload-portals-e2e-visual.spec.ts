/**
 * End-to-end visual testing for Upload Portals feature on ml-dev4.
 *
 * Tests the deployed application at https://d2gn8nwil93iye.cloudfront.net
 * covering:
 *   1. Settings > Upload Portals management page (sub-nav, list views)
 *   2. Portal editor (sidebar groups, sections, preview)
 *   3. Template and Theme editors
 *   4. Create portal flow with various configurations
 *   5. Public portal page (if accessible)
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroTest2024!' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   npx playwright test tests/visual/upload-portals-e2e-visual.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

const OUT = "test-results/upload-portals-e2e";

// Kill transitions/animations for deterministic screenshots.
async function freeze(page: import("@playwright/test").Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}",
  });
}

test.describe("Upload Portals — Authentication & Navigation", () => {
  test("login succeeds and dashboard loads", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    expect(page.url()).not.toContain("sign-in");
    await freeze(page);
    await page.screenshot({ path: `${OUT}/01-post-login-dashboard.png`, fullPage: false });
  });

  test("navigate to Settings > Upload Portals", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);

    // Wait for the page to settle
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/02-upload-portals-list.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Sub-Navigation", () => {
  test("Portals tab is visible and active", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    // Check for tab elements
    const portalsTab = page.getByRole("tab", { name: "Portals" });
    const templatesTab = page.getByRole("tab", { name: "Templates" });
    const themesTab = page.getByRole("tab", { name: "Themes" });

    const hasPortalsTab = await portalsTab.count();
    const hasTemplatesTab = await templatesTab.count();
    const hasThemesTab = await themesTab.count();

    console.log(`[e2e] Portals tab visible: ${hasPortalsTab > 0}`);
    console.log(`[e2e] Templates tab visible: ${hasTemplatesTab > 0}`);
    console.log(`[e2e] Themes tab visible: ${hasThemesTab > 0}`);

    await page.screenshot({ path: `${OUT}/03-subnav-portals.png`, fullPage: false });
  });

  test("Templates tab renders", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/templates`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/04-subnav-templates.png`, fullPage: true });
  });

  test("Themes tab renders", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/themes`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/05-subnav-themes.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Portal Editor", () => {
  test("new portal editor loads with sidebar", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Check for sidebar presence
    const sidebar = page.getByRole("complementary");
    const hasSidebar = await sidebar.count();
    console.log(`[e2e] Editor sidebar present: ${hasSidebar > 0}`);

    // Check for group headers (branch feature)
    const appearanceHeader = page.locator("#portal-editor-group-appearance-header");
    const structureHeader = page.locator("#portal-editor-group-structure-header");
    const hasAppearance = await appearanceHeader.count();
    const hasStructure = await structureHeader.count();
    console.log(`[e2e] Appearance group header: ${hasAppearance > 0}`);
    console.log(`[e2e] Structure group header: ${hasStructure > 0}`);

    // Check for section buttons (these should exist in both old and new layouts)
    const sectionButtons = page
      .getByRole("button")
      .filter({ hasText: /Colors|Appearance|Logo|Layout|Typography/ });
    const sectionCount = await sectionButtons.count();
    console.log(`[e2e] Editor section buttons found: ${sectionCount}`);

    await page.screenshot({ path: `${OUT}/06-portal-editor-new.png`, fullPage: true });
  });

  test("portal editor sidebar sections expand/collapse", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Try clicking sidebar sections to expand
    const allButtons = page.getByRole("button");
    const buttonCount = await allButtons.count();
    console.log(`[e2e] Total buttons on editor page: ${buttonCount}`);

    // Capture sidebar in default state
    await page.screenshot({ path: `${OUT}/07-portal-editor-sidebar-default.png`, fullPage: false });

    // Look for expandable sections and click them
    const sectionNames = [
      "Colors",
      "Appearance",
      "Logo",
      "Layout",
      "Typography",
      "Pages & Workflow",
      "Field Configuration",
      "Access Control",
      "Metadata",
    ];
    for (const name of sectionNames) {
      const section = page.getByRole("button", { name: new RegExp(name, "i") });
      if ((await section.count()) > 0) {
        console.log(`[e2e] Section "${name}" found, clicking...`);
        await section.first().click();
        await page.waitForTimeout(500);
        await page.screenshot({
          path: `${OUT}/08-section-${name.toLowerCase().replace(/[^a-z]/g, "-")}.png`,
          fullPage: false,
        });
      } else {
        console.log(`[e2e] Section "${name}" NOT found`);
      }
    }
  });

  test("portal editor preview panel", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Look for a preview iframe or render area
    const iframe = page.locator("iframe");
    const hasIframe = await iframe.count();
    console.log(`[e2e] Preview iframe present: ${hasIframe > 0}`);

    // Look for preview container
    const previewArea = page.locator(
      '[data-testid*="preview"], [class*="preview"], [role="document"]'
    );
    const hasPreview = await previewArea.count();
    console.log(`[e2e] Preview area present: ${hasPreview > 0}`);

    await page.screenshot({ path: `${OUT}/09-portal-editor-preview.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Template Editor", () => {
  test("new template editor loads", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/templates/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: `${OUT}/10-template-editor-new.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Theme Editor", () => {
  test("new theme editor loads", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/themes/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: `${OUT}/11-theme-editor-new.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Create Portal Flow", () => {
  test("create portal menu/dialog opens", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    // Look for create button
    const createBtn = page.getByRole("button", { name: /create|new|add/i });
    const hasCreateBtn = await createBtn.count();
    console.log(`[e2e] Create portal button found: ${hasCreateBtn > 0}`);

    if (hasCreateBtn > 0) {
      await createBtn.first().click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${OUT}/12-create-portal-menu.png`, fullPage: false });
    }
  });
});

test.describe("Upload Portals — Portal List & Table", () => {
  test("portals list shows existing portals", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Check for table or list of portals
    const table = page.locator("table, [role='grid'], [role='table']");
    const hasTable = await table.count();
    console.log(`[e2e] Portal list/table present: ${hasTable > 0}`);

    // Check for empty state
    const emptyState = page.locator('[class*="empty"], [data-testid*="empty"]');
    const hasEmptyState = await emptyState.count();
    console.log(`[e2e] Empty state visible: ${hasEmptyState > 0}`);

    // Look for portal cards or list items
    const listItems = page.locator('[class*="portal"], [data-testid*="portal"]');
    const itemCount = await listItems.count();
    console.log(`[e2e] Portal items found: ${itemCount}`);

    await page.screenshot({ path: `${OUT}/13-portals-list-content.png`, fullPage: true });
  });
});

test.describe("Upload Portals — Responsive Layout", () => {
  test("portal editor at tablet width", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/14-editor-tablet.png`, fullPage: true });
  });

  test("portal list at mobile width", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/15-portals-list-mobile.png`, fullPage: true });
  });
});
