/**
 * Deep visual testing for Upload Portals feature on ml-dev4.
 *
 * Tests:
 *   1. Portal editor — all sidebar sections inside group accordions
 *   2. Create portal with specific configurations
 *   3. Public portal page access (/p/<slug>)
 *   4. Portal list table behavior
 *   5. Template/Theme management
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroTest2024!' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   SKIP_ROLE_CHECK=true \
 *   npx playwright test tests/visual/upload-portals-deep-visual.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

const OUT = "test-results/upload-portals-deep";

async function freeze(page: import("@playwright/test").Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}",
  });
}

test.describe("Portal Editor — Group Accordion Deep Inspection", () => {
  test("Appearance group expands and shows all child sections", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // The Appearance group should be auto-expanded (it owns the default active section)
    const appearanceGroup = page.locator("#portal-editor-group-appearance-header");
    await expect(appearanceGroup).toBeVisible();

    // Check helper text
    const themeHelper = page.getByText("Saved as a Theme. Also included in Templates.");
    const hasThemeHelper = await themeHelper.count();
    console.log(`[deep] Theme helper text visible: ${hasThemeHelper > 0}`);

    // Check child sections inside Appearance group
    const groupContent = page.locator("#portal-editor-group-appearance-content");
    const brandingSection = groupContent.locator("#portal-editor-section-branding-header");
    const contentSection = groupContent.locator("#portal-editor-section-content-header");
    const colorsSection = groupContent.locator("#portal-editor-section-appearance-header");
    const typographySection = groupContent.locator("#portal-editor-section-typography-header");
    const layoutSection = groupContent.locator("#portal-editor-section-layout-header");

    console.log(`[deep] Branding section: ${(await brandingSection.count()) > 0}`);
    console.log(`[deep] Content section: ${(await contentSection.count()) > 0}`);
    console.log(`[deep] Colors section: ${(await colorsSection.count()) > 0}`);
    console.log(`[deep] Typography section: ${(await typographySection.count()) > 0}`);
    console.log(`[deep] Layout section: ${(await layoutSection.count()) > 0}`);

    await page.screenshot({ path: `${OUT}/01-appearance-group-expanded.png`, fullPage: false });
  });

  test("Structure group expands and shows all child sections", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Expand the Structure group
    const structureGroup = page.locator("#portal-editor-group-structure-header");
    await structureGroup.click();
    await page.waitForTimeout(500);

    // Check child sections inside Structure group
    const groupContent = page.locator("#portal-editor-group-structure-content");
    const pagesSection = groupContent.locator("#portal-editor-section-pages-header");
    const fieldsSection = groupContent.locator("#portal-editor-section-fields-header");
    const destinationsSection = groupContent.locator("#portal-editor-section-destinations-header");
    const accessSection = groupContent.locator("#portal-editor-section-access-header");
    const metadataSection = groupContent.locator("#portal-editor-section-metadata-header");

    console.log(`[deep] Pages section: ${(await pagesSection.count()) > 0}`);
    console.log(`[deep] Fields section: ${(await fieldsSection.count()) > 0}`);
    console.log(`[deep] Destinations section: ${(await destinationsSection.count()) > 0}`);
    console.log(`[deep] Access section: ${(await accessSection.count()) > 0}`);
    console.log(`[deep] Metadata section: ${(await metadataSection.count()) > 0}`);

    await page.screenshot({ path: `${OUT}/02-structure-group-expanded.png`, fullPage: false });
  });

  test("Expanding a section in Structure group works", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Expand Structure group
    const structureGroup = page.locator("#portal-editor-group-structure-header");
    await structureGroup.click();
    await page.waitForTimeout(500);

    // Click Pages section to expand it
    const pagesSection = page.locator("#portal-editor-section-pages-header");
    if ((await pagesSection.count()) > 0) {
      await pagesSection.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/03-pages-section-expanded.png`, fullPage: true });
    }

    // Click Fields section
    const fieldsSection = page.locator("#portal-editor-section-fields-header");
    if ((await fieldsSection.count()) > 0) {
      await fieldsSection.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/04-fields-section-expanded.png`, fullPage: true });
    }

    // Click Access section
    const accessSection = page.locator("#portal-editor-section-access-header");
    if ((await accessSection.count()) > 0) {
      await accessSection.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/05-access-section-expanded.png`, fullPage: true });
    }

    // Click Destinations section
    const destinationsSection = page.locator("#portal-editor-section-destinations-header");
    if ((await destinationsSection.count()) > 0) {
      await destinationsSection.click();
      await page.waitForTimeout(800);
      await page.screenshot({
        path: `${OUT}/06-destinations-section-expanded.png`,
        fullPage: true,
      });
    }

    // Click Metadata section
    const metadataSection = page.locator("#portal-editor-section-metadata-header");
    if ((await metadataSection.count()) > 0) {
      await metadataSection.click();
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/07-metadata-section-expanded.png`, fullPage: true });
    }
  });

  test("Branding section fields render correctly", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Branding should be the default active section (first in appearance group)
    const brandingContent = page.locator("#portal-editor-section-branding-content");
    const hasBrandingContent = await brandingContent.count();
    console.log(`[deep] Branding content panel visible: ${hasBrandingContent > 0}`);

    if (hasBrandingContent > 0) {
      // Check for fields like logo, banner uploads
      const inputs = brandingContent.locator("input, textarea, [role='textbox'], button");
      const inputCount = await inputs.count();
      console.log(`[deep] Branding section form elements: ${inputCount}`);
      await brandingContent.screenshot({ path: `${OUT}/08-branding-section-content.png` });
    }
  });

  test("Content section shows slug field with URL preview", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Click Content section to expand it
    const contentHeader = page.locator("#portal-editor-section-content-header");
    if ((await contentHeader.count()) > 0) {
      await contentHeader.click();
      await page.waitForTimeout(800);

      const contentPanel = page.locator("#portal-editor-section-content-content");
      // Look for the slug input and /p/ URL preview
      const slugHint = page.getByText(/\/p\//);
      const hasSlugHint = await slugHint.count();
      console.log(`[deep] Slug URL preview (/p/...) visible: ${hasSlugHint > 0}`);

      await contentPanel.screenshot({ path: `${OUT}/09-content-section-slug.png` });
    }
  });
});

test.describe("Portal Editor — Preview Renderer", () => {
  test("preview panel renders portal appearance", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // The preview should be on the right side of the editor
    // Look for common preview elements
    const mainContent = page.locator("main, [role='main']");
    const previewFrame = page.locator("iframe, [data-testid*='preview'], [class*='Preview']");
    const hasPreviewFrame = await previewFrame.count();
    console.log(`[deep] Preview frame/container found: ${hasPreviewFrame > 0}`);

    // Look for the portal preview renderer component
    const previewRenderer = page.locator('[class*="PortalPreview"], [class*="preview"]');
    const hasRenderer = await previewRenderer.count();
    console.log(`[deep] Preview renderer component found: ${hasRenderer > 0}`);

    // Check for drop zone area in preview
    const dropZone = page.getByText(/drag|drop|choose|browse/i);
    const hasDropZone = await dropZone.count();
    console.log(`[deep] Drop zone text in preview: ${hasDropZone > 0}`);

    await page.screenshot({ path: `${OUT}/10-editor-full-with-preview.png`, fullPage: true });
  });
});

test.describe("Portal List — CRUD Operations", () => {
  test("portal list page shows action buttons and table columns", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Check for column headers in the portals table
    const tableHeaders = page.locator("th, [role='columnheader']");
    const headerCount = await tableHeaders.count();
    console.log(`[deep] Table column headers: ${headerCount}`);

    if (headerCount > 0) {
      const headerTexts: string[] = [];
      for (let i = 0; i < headerCount; i++) {
        headerTexts.push((await tableHeaders.nth(i).textContent()) ?? "");
      }
      console.log(`[deep] Column headers: ${headerTexts.join(", ")}`);
    }

    // Check for action buttons (create, edit, delete)
    const createBtn = page.getByRole("button", { name: /create|new|add/i });
    console.log(`[deep] Create button present: ${(await createBtn.count()) > 0}`);

    await page.screenshot({ path: `${OUT}/11-portal-list-details.png`, fullPage: true });
  });
});

test.describe("Public Portal Page", () => {
  test("attempt to access /p/ route shows appropriate state", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";

    // Try navigating to a test portal slug
    await page.goto(`${root}/p/test-portal`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // The page should show either:
    // - The portal if it exists
    // - A "not found" or "unavailable" message
    // - An access gate (passphrase/token prompt)
    const pageContent = await page.textContent("body");
    const hasAccessGate = /passphrase|token|password|enter.*code/i.test(pageContent ?? "");
    const hasNotFound = /not found|unavailable|does not exist|expired/i.test(pageContent ?? "");
    const hasUploader = /upload|drop|drag|browse/i.test(pageContent ?? "");

    console.log(`[deep] Public portal /p/test-portal:`);
    console.log(`  - Access gate: ${hasAccessGate}`);
    console.log(`  - Not found/unavailable: ${hasNotFound}`);
    console.log(`  - Uploader visible: ${hasUploader}`);

    await page.screenshot({ path: `${OUT}/12-public-portal-page.png`, fullPage: true });
  });

  test("attempt to access non-existent portal shows proper error", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/p/non-existent-portal-xyz-12345`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    await page.screenshot({ path: `${OUT}/13-portal-not-found.png`, fullPage: true });

    // Check the displayed state
    const bodyText = await page.textContent("body");
    console.log(
      `[deep] Non-existent portal page text (first 200 chars): ${(bodyText ?? "").slice(0, 200)}`
    );
  });
});

test.describe("Template and Theme Editors", () => {
  test("template editor has same grouped sidebar as portal editor", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/templates/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Should have the same group structure
    const appearanceGroup = page.locator("#portal-editor-group-appearance-header");
    const structureGroup = page.locator("#portal-editor-group-structure-header");
    console.log(
      `[deep] Template editor - Appearance group: ${(await appearanceGroup.count()) > 0}`
    );
    console.log(`[deep] Template editor - Structure group: ${(await structureGroup.count()) > 0}`);

    // Template-specific elements
    const templateName = page.getByRole("textbox", { name: /name|title/i });
    const hasNameField = await templateName.count();
    console.log(`[deep] Template name field: ${hasNameField > 0}`);

    await page.screenshot({ path: `${OUT}/14-template-editor-grouped.png`, fullPage: true });
  });

  test("theme editor shows appearance-only sections", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/themes/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Theme editor may only show appearance sections (not structure)
    const pageText = await page.textContent("body");
    const hasColorPicker = /color|palette|hex|rgb/i.test(pageText ?? "");
    const hasTypography = /font|typography|heading/i.test(pageText ?? "");
    console.log(`[deep] Theme editor - color elements: ${hasColorPicker}`);
    console.log(`[deep] Theme editor - typography elements: ${hasTypography}`);

    await page.screenshot({ path: `${OUT}/15-theme-editor.png`, fullPage: true });
  });

  test("templates list page shows table or empty state", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/templates`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    const table = page.locator("table, [role='grid']");
    const hasTable = await table.count();
    const emptyState = page.getByText(/no templates|empty|create.*first/i);
    const hasEmpty = await emptyState.count();
    console.log(`[deep] Templates list - table: ${hasTable > 0}, empty state: ${hasEmpty > 0}`);

    await page.screenshot({ path: `${OUT}/16-templates-list.png`, fullPage: true });
  });

  test("themes list page shows table or empty state", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/themes`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    const table = page.locator("table, [role='grid']");
    const hasTable = await table.count();
    const emptyState = page.getByText(/no themes|empty|create.*first/i);
    const hasEmpty = await emptyState.count();
    console.log(`[deep] Themes list - table: ${hasTable > 0}, empty state: ${hasEmpty > 0}`);

    await page.screenshot({ path: `${OUT}/17-themes-list.png`, fullPage: true });
  });
});

test.describe("Portal Editor — Interaction Flows", () => {
  test("clicking Create Portal from list opens editor", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    const createBtn = page.getByRole("button", { name: /create|new|add/i });
    if ((await createBtn.count()) > 0) {
      await createBtn.first().click();
      await page.waitForTimeout(2000);

      // Check if we're now on the editor page or a dialog opened
      const currentUrl = page.url();
      const isOnEditor = currentUrl.includes("/new") || currentUrl.includes("/create");
      console.log(`[deep] After create click, URL: ${currentUrl}`);
      console.log(`[deep] On editor page: ${isOnEditor}`);

      // Check for create portal menu/dialog
      const dialog = page.locator(
        "[role='dialog'], [role='menu'], [class*='Modal'], [class*='Popover']"
      );
      const hasDialog = await dialog.count();
      console.log(`[deep] Dialog/menu opened: ${hasDialog > 0}`);

      await page.screenshot({ path: `${OUT}/18-after-create-click.png`, fullPage: false });
    }
  });

  test("sub-nav Building blocks label and tab switching", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(2000);

    // Check for "Building blocks" label
    const buildingBlocks = page.getByText("Building blocks", { exact: true });
    const hasBuildingBlocks = await buildingBlocks.count();
    console.log(`[deep] "Building blocks" label: ${hasBuildingBlocks > 0}`);

    // Click Templates tab
    const templatesTab = page.getByRole("tab", { name: "Templates" });
    if ((await templatesTab.count()) > 0) {
      await templatesTab.click();
      await page.waitForTimeout(1500);
      console.log(`[deep] After Templates tab click, URL: ${page.url()}`);
      await page.screenshot({ path: `${OUT}/19-after-templates-tab.png`, fullPage: false });
    }

    // Click Themes tab
    const themesTab = page.getByRole("tab", { name: "Themes" });
    if ((await themesTab.count()) > 0) {
      await themesTab.click();
      await page.waitForTimeout(1500);
      console.log(`[deep] After Themes tab click, URL: ${page.url()}`);
      await page.screenshot({ path: `${OUT}/20-after-themes-tab.png`, fullPage: false });
    }

    // Click back to Portals tab
    const portalsTab = page.getByRole("tab", { name: "Portals" });
    if ((await portalsTab.count()) > 0) {
      await portalsTab.click();
      await page.waitForTimeout(1500);
      console.log(`[deep] After Portals tab click, URL: ${page.url()}`);
      await page.screenshot({ path: `${OUT}/21-after-portals-tab.png`, fullPage: false });
    }
  });
});
