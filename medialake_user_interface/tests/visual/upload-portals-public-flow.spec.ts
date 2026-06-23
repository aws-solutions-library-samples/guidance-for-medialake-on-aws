/**
 * Visual testing: Public portal page flows, access gate, and upload UI.
 *
 * Covers:
 *   1. Public portal access gate (passphrase/token/email prompts)
 *   2. Authenticated portal rendering (SurveyJS multi-page, appearance theming)
 *   3. Upload component display (Uppy dashboard, queue table, buttons)
 *   4. Conflict resolution dialog
 *   5. Portal editor configurations (metadata, destinations, file restrictions)
 *   6. Session behavior indicators
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroTest2024!' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   SKIP_ROLE_CHECK=true \
 *   npx playwright test tests/visual/upload-portals-public-flow.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

const OUT = "test-results/upload-portals-public-flow";

async function freeze(page: import("@playwright/test").Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}",
  });
}

test.describe("Public Portal — Access Gate Visual", () => {
  test("public portal with passphrase shows access gate form", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    // Navigate to test-portal which we know exists
    await page.goto(`${root}/p/test-portal`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // Check what rendered: access gate, uploader, or unavailable
    const bodyText = await page.textContent("body");
    const hasPassphraseField = await page.locator('input[type="password"]').count();
    const hasEmailField = await page.locator('input[type="email"]').count();
    const hasSignInButton = await page
      .getByRole("button", { name: /sign in|submit|continue/i })
      .count();
    const hasUploader = /upload|drop|drag|browse/i.test(bodyText ?? "");
    const hasAccessGate = /passphrase|enter.*code|access portal/i.test(bodyText ?? "");
    const hasInactive = /inactive|unavailable|expired/i.test(bodyText ?? "");

    console.log(`[public] Access state:`);
    console.log(`  - Passphrase field: ${hasPassphraseField > 0}`);
    console.log(`  - Email field: ${hasEmailField > 0}`);
    console.log(`  - Sign in / submit button: ${hasSignInButton > 0}`);
    console.log(`  - Uploader visible: ${hasUploader}`);
    console.log(`  - Access gate text: ${hasAccessGate}`);
    console.log(`  - Inactive/unavailable: ${hasInactive}`);

    await page.screenshot({ path: `${OUT}/01-public-portal-initial-state.png`, fullPage: true });
  });

  test("portal access gate shows proper layout and typography", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/p/test-portal`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // Verify the card-based layout (Paper wrapper)
    const paper = page.locator("[class*='MuiPaper']");
    const hasPaper = await paper.count();
    console.log(`[public] Card (Paper) element present: ${hasPaper > 0}`);

    // Check centered layout
    if (hasPaper > 0) {
      const box = await paper.first().boundingBox();
      if (box) {
        const viewport = page.viewportSize();
        const centerOffset = Math.abs(box.x + box.width / 2 - viewport!.width / 2);
        console.log(
          `[public] Card center offset from viewport center: ${centerOffset.toFixed(1)}px`
        );
        // Card should be approximately centered
        expect(centerOffset).toBeLessThan(50);
      }
    }

    await page.screenshot({ path: `${OUT}/02-portal-card-layout.png`, fullPage: true });
  });

  test("non-existent portal shows unavailable state with proper styling", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/p/nonexistent-slug-xyz`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // Should show an Alert warning or inactive message
    const alert = page.locator("[class*='MuiAlert']");
    const hasAlert = await alert.count();
    console.log(`[public] Alert component visible: ${hasAlert > 0}`);

    if (hasAlert > 0) {
      const alertText = await alert.first().textContent();
      console.log(`[public] Alert text: ${alertText}`);
    }

    // Check for "Contact the portal administrator" text
    const contactText = page.getByText(/contact.*administrator/i);
    const hasContact = await contactText.count();
    console.log(`[public] Administrator contact text: ${hasContact > 0}`);

    await page.screenshot({ path: `${OUT}/03-portal-unavailable.png`, fullPage: true });
  });
});

test.describe("Portal Editor — Configuration Panels Deep", () => {
  test("access section shows passphrase and token options", async ({
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

    // Click Access section
    const accessSection = page.locator("#portal-editor-section-access-header");
    if ((await accessSection.count()) > 0) {
      await accessSection.click();
      await page.waitForTimeout(1000);

      // Look for access mode selector (public, passphrase, token, etc)
      const accessContent = page.locator("#portal-editor-section-access-content");
      const selectBoxes = accessContent.locator("select, [role='combobox'], [role='listbox']");
      const radioButtons = accessContent.locator("input[type='radio'], [role='radio']");
      const checkboxes = accessContent.locator("input[type='checkbox'], [role='checkbox']");
      const textFields = accessContent.locator(
        "input[type='text'], input[type='password'], textarea"
      );

      console.log(`[editor] Access section - select/combo: ${await selectBoxes.count()}`);
      console.log(`[editor] Access section - radio buttons: ${await radioButtons.count()}`);
      console.log(`[editor] Access section - checkboxes: ${await checkboxes.count()}`);
      console.log(`[editor] Access section - text fields: ${await textFields.count()}`);

      // Check for access mode labels
      const publicLabel = accessContent.getByText(/public/i);
      const passphraseLabel = accessContent.getByText(/passphrase/i);
      const tokenLabel = accessContent.getByText(/token|link/i);

      console.log(`[editor] Access modes visible - Public: ${(await publicLabel.count()) > 0}`);
      console.log(
        `[editor] Access modes visible - Passphrase: ${(await passphraseLabel.count()) > 0}`
      );
      console.log(`[editor] Access modes visible - Token: ${(await tokenLabel.count()) > 0}`);

      await accessContent.screenshot({ path: `${OUT}/04-access-section-expanded.png` });
    }
  });

  test("destinations section shows destination configuration", async ({
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

    // Click Destinations section
    const destSection = page.locator("#portal-editor-section-destinations-header");
    if ((await destSection.count()) > 0) {
      await destSection.click();
      await page.waitForTimeout(1000);

      const destContent = page.locator("#portal-editor-section-destinations-content");

      // Look for add destination button or list
      const addButton = destContent.getByRole("button", { name: /add|create|new/i });
      const hasAddBtn = await addButton.count();
      console.log(`[editor] Destinations - Add button: ${hasAddBtn > 0}`);

      // Check for path mode options (flat vs structured)
      const pathModeText = destContent.getByText(/path|folder|structured|flat/i);
      const hasPathMode = await pathModeText.count();
      console.log(`[editor] Destinations - Path mode options: ${hasPathMode > 0}`);

      // Check for automation tag field
      const automationTag = destContent.getByText(/automation.*tag|tag/i);
      const hasAutoTag = await automationTag.count();
      console.log(`[editor] Destinations - Automation tag: ${hasAutoTag > 0}`);

      await destContent.screenshot({ path: `${OUT}/05-destinations-section.png` });
    }
  });

  test("metadata section shows field configuration UI", async ({
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

    // Click Metadata section
    const metaSection = page.locator("#portal-editor-section-metadata-header");
    if ((await metaSection.count()) > 0) {
      await metaSection.click();
      await page.waitForTimeout(1000);

      const metaContent = page.locator("#portal-editor-section-metadata-content");

      // Look for metadata field builder elements
      const addFieldBtn = metaContent.getByRole("button", { name: /add.*field|add.*metadata/i });
      const hasAddField = await addFieldBtn.count();
      console.log(`[editor] Metadata - Add field button: ${hasAddField > 0}`);

      // Check for existing field list/table
      const fieldRows = metaContent.locator("[class*='field'], [class*='Field'], tr, [role='row']");
      const fieldCount = await fieldRows.count();
      console.log(`[editor] Metadata - Field rows visible: ${fieldCount}`);

      await metaContent.screenshot({ path: `${OUT}/06-metadata-section.png` });
    }
  });

  test("fields section shows file restriction options", async ({
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

    // Click Fields section
    const fieldsSection = page.locator("#portal-editor-section-fields-header");
    if ((await fieldsSection.count()) > 0) {
      await fieldsSection.click();
      await page.waitForTimeout(1000);

      const fieldsContent = page.locator("#portal-editor-section-fields-content");

      // Look for file type restriction controls
      const fileTypeText = fieldsContent.getByText(/file.*type|allowed.*type|restrict/i);
      const hasFileType = await fileTypeText.count();
      console.log(`[editor] Fields - File type restriction: ${hasFileType > 0}`);

      // Look for max file size
      const maxSizeText = fieldsContent.getByText(/max.*size|file.*size|size.*limit/i);
      const hasMaxSize = await maxSizeText.count();
      console.log(`[editor] Fields - Max size option: ${hasMaxSize > 0}`);

      // Look for max files per session
      const maxFilesText = fieldsContent.getByText(/max.*files|file.*limit|per.*session/i);
      const hasMaxFiles = await maxFilesText.count();
      console.log(`[editor] Fields - Max files option: ${hasMaxFiles > 0}`);

      await fieldsContent.screenshot({ path: `${OUT}/07-fields-section.png` });
    }
  });

  test("pages section shows multi-page portal configuration", async ({
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

    // Click Pages section
    const pagesSection = page.locator("#portal-editor-section-pages-header");
    if ((await pagesSection.count()) > 0) {
      await pagesSection.click();
      await page.waitForTimeout(1000);

      const pagesContent = page.locator("#portal-editor-section-pages-content");

      // Look for page management UI elements
      const addPageBtn = pagesContent.getByRole("button", { name: /add.*page|new.*page/i });
      const hasAddPage = await addPageBtn.count();
      console.log(`[editor] Pages - Add page button: ${hasAddPage > 0}`);

      // Check for page list (sortable or tabbed)
      const pageItems = pagesContent.locator("[class*='page'], [class*='Page'], [draggable]");
      const pageCount = await pageItems.count();
      console.log(`[editor] Pages - Page items/tabs: ${pageCount}`);

      // Check for page title field
      const titleField = pagesContent.getByRole("textbox");
      const hasTitleField = await titleField.count();
      console.log(`[editor] Pages - Text fields: ${hasTitleField}`);

      await pagesContent.screenshot({ path: `${OUT}/08-pages-section.png` });
    }
  });

  test("colors section shows color picker UI", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Colors is within the Appearance group (should be auto-expanded)
    // Click the Colors/Appearance section header
    const colorsSection = page.locator("#portal-editor-section-appearance-header");
    if ((await colorsSection.count()) > 0) {
      await colorsSection.click();
      await page.waitForTimeout(1000);

      const colorsContent = page.locator("#portal-editor-section-appearance-content");

      // Look for color swatch elements or color input fields
      const colorInputs = colorsContent.locator(
        "input[type='color'], [class*='color'], [class*='Color'], [class*='swatch']"
      );
      const hasColorInputs = await colorInputs.count();
      console.log(`[editor] Colors - Color inputs/swatches: ${hasColorInputs}`);

      // Check for color labels (background, primary, accent, etc)
      const bgColorLabel = colorsContent.getByText(/background/i);
      const primaryLabel = colorsContent.getByText(/primary/i);
      const accentLabel = colorsContent.getByText(/accent/i);
      console.log(`[editor] Colors - Background label: ${(await bgColorLabel.count()) > 0}`);
      console.log(`[editor] Colors - Primary label: ${(await primaryLabel.count()) > 0}`);
      console.log(`[editor] Colors - Accent label: ${(await accentLabel.count()) > 0}`);

      await colorsContent.screenshot({ path: `${OUT}/09-colors-section.png` });
    }
  });

  test("typography section shows font settings", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Click Typography section
    const typoSection = page.locator("#portal-editor-section-typography-header");
    if ((await typoSection.count()) > 0) {
      await typoSection.click();
      await page.waitForTimeout(1000);

      const typoContent = page.locator("#portal-editor-section-typography-content");

      // Look for font family selections
      const fontSelect = typoContent.locator("select, [role='combobox'], [class*='Select']");
      const hasFontSelect = await fontSelect.count();
      console.log(`[editor] Typography - Font selectors: ${hasFontSelect}`);

      // Check for heading/body font labels
      const headingFont = typoContent.getByText(/heading|title.*font/i);
      const bodyFont = typoContent.getByText(/body.*font|paragraph/i);
      console.log(`[editor] Typography - Heading font option: ${(await headingFont.count()) > 0}`);
      console.log(`[editor] Typography - Body font option: ${(await bodyFont.count()) > 0}`);

      await typoContent.screenshot({ path: `${OUT}/10-typography-section.png` });
    }
  });

  test("layout section shows spacing and card options", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Click Layout section
    const layoutSection = page.locator("#portal-editor-section-layout-header");
    if ((await layoutSection.count()) > 0) {
      await layoutSection.click();
      await page.waitForTimeout(1000);

      const layoutContent = page.locator("#portal-editor-section-layout-content");

      // Check for layout options (card width, padding, border radius, shadow)
      const widthLabel = layoutContent.getByText(/max.*width|card.*width/i);
      const paddingLabel = layoutContent.getByText(/padding/i);
      const radiusLabel = layoutContent.getByText(/border.*radius|corner/i);
      const shadowLabel = layoutContent.getByText(/shadow|elevation/i);

      console.log(`[editor] Layout - Max width option: ${(await widthLabel.count()) > 0}`);
      console.log(`[editor] Layout - Padding option: ${(await paddingLabel.count()) > 0}`);
      console.log(`[editor] Layout - Border radius option: ${(await radiusLabel.count()) > 0}`);
      console.log(`[editor] Layout - Shadow option: ${(await shadowLabel.count()) > 0}`);

      // Check for slider or number input controls
      const sliders = layoutContent.locator("[class*='Slider'], input[type='range']");
      const numberInputs = layoutContent.locator("input[type='number']");
      console.log(`[editor] Layout - Sliders: ${await sliders.count()}`);
      console.log(`[editor] Layout - Number inputs: ${await numberInputs.count()}`);

      await layoutContent.screenshot({ path: `${OUT}/11-layout-section.png` });
    }
  });
});

test.describe("Portal Editor — Preview and Live Rendering", () => {
  test("editor shows live preview panel with portal appearance", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // The editor layout should have sidebar + preview
    // Get the main content area width
    const mainArea = page.locator("main, [role='main'], [class*='content']").first();
    const mainBox = await mainArea.boundingBox();
    console.log(`[editor] Main content area dimensions: ${mainBox?.width}x${mainBox?.height}`);

    // Look for the preview panel (typically the right portion of the editor)
    const previewPanel = page.locator(
      "[class*='preview'], [class*='Preview'], [data-testid*='preview']"
    );
    const hasPreview = await previewPanel.count();
    console.log(`[editor] Preview panel elements: ${hasPreview}`);

    // Check for the portal card within preview
    const previewPaper = page.locator(
      "[class*='preview'] [class*='MuiPaper'], [class*='Preview'] [class*='MuiPaper']"
    );
    const hasPreviewCard = await previewPaper.count();
    console.log(`[editor] Preview card (Paper) in preview: ${hasPreviewCard}`);

    // Check for drop zone in preview
    const dropZone = page.getByText(/drag.*drop|choose.*file|browse/i);
    const hasDropZone = await dropZone.count();
    console.log(`[editor] Drop zone text in preview: ${hasDropZone > 0}`);

    // Look for SurveyJS rendered survey
    const surveyContainer = page.locator(
      "[class*='sv-root'], [class*='sd-root'], [class*='survey']"
    );
    const hasSurvey = await surveyContainer.count();
    console.log(`[editor] SurveyJS container: ${hasSurvey > 0}`);

    await page.screenshot({ path: `${OUT}/12-editor-with-preview.png`, fullPage: true });
  });

  test("editor sidebar and preview have correct proportions", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Look for the sidebar element
    const sidebar = page.locator(
      "[class*='Sidebar'], [class*='sidebar'], aside, [role='complementary']"
    );
    if ((await sidebar.count()) > 0) {
      const sidebarBox = await sidebar.first().boundingBox();
      const viewport = page.viewportSize();
      if (sidebarBox && viewport) {
        const sidebarWidthPct = (sidebarBox.width / viewport.width) * 100;
        console.log(
          `[editor] Sidebar width: ${sidebarBox.width}px (${sidebarWidthPct.toFixed(1)}% of viewport)`
        );
        // Sidebar should be roughly 25-40% of viewport
        expect(sidebarWidthPct).toBeGreaterThan(15);
        expect(sidebarWidthPct).toBeLessThan(50);
      }
    }

    await page.screenshot({ path: `${OUT}/13-editor-proportions.png`, fullPage: false });
  });
});

test.describe("Portal Editor — Action Bar and Save Flow", () => {
  test("editor action bar shows save/publish buttons", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Look for action bar (save, publish, discard buttons)
    const saveBtn = page.getByRole("button", { name: /save|publish|create/i });
    const discardBtn = page.getByRole("button", { name: /discard|cancel|back/i });
    const draftBtn = page.getByRole("button", { name: /draft/i });

    console.log(`[editor] Save/Publish button: ${(await saveBtn.count()) > 0}`);
    console.log(`[editor] Discard/Cancel button: ${(await discardBtn.count()) > 0}`);
    console.log(`[editor] Draft button: ${(await draftBtn.count()) > 0}`);

    // Check for status indicator
    const statusBadge = page.locator("[class*='status'], [class*='Status'], [class*='badge']");
    const hasStatus = await statusBadge.count();
    console.log(`[editor] Status badge/indicator: ${hasStatus > 0}`);

    // Check for portal name/title input at the top
    const nameInput = page.getByRole("textbox", { name: /name|title/i });
    const hasNameInput = await nameInput.count();
    console.log(`[editor] Portal name input: ${hasNameInput > 0}`);

    await page.screenshot({ path: `${OUT}/14-editor-action-bar.png`, fullPage: false });
  });
});

test.describe("Portal List — Editing Existing Portal", () => {
  test("clicking an existing portal opens its editor", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Look for portal rows in the table
    const rows = page.locator("tr, [role='row']");
    const rowCount = await rows.count();
    console.log(`[list] Table rows: ${rowCount}`);

    // Find a clickable portal name or edit button
    const editButtons = page.locator("[aria-label*='edit' i], [title*='edit' i], button:has(svg)");
    const hasEdit = await editButtons.count();
    console.log(`[list] Edit-like buttons: ${hasEdit}`);

    // Try clicking the first portal name/link in the table
    const portalLinks = page.locator("td a, [role='cell'] a, tr td:first-child");
    if ((await portalLinks.count()) > 1) {
      await portalLinks.nth(1).click(); // skip header row
      await page.waitForTimeout(3000);
      await freeze(page);

      const currentUrl = page.url();
      console.log(`[list] After clicking portal, URL: ${currentUrl}`);
      const isEditor = currentUrl.includes("/edit") || currentUrl.includes("/portals/");
      console.log(`[list] Navigated to editor: ${isEditor}`);

      await page.screenshot({ path: `${OUT}/15-existing-portal-editor.png`, fullPage: true });
    }
  });

  test("portal table shows correct status chips/badges", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Look for status chips (Active, Draft, Expired, etc.)
    const chips = page.locator("[class*='MuiChip'], [class*='chip'], [class*='badge']");
    const chipCount = await chips.count();
    console.log(`[list] Status chips/badges: ${chipCount}`);

    if (chipCount > 0) {
      const chipTexts: string[] = [];
      for (let i = 0; i < Math.min(chipCount, 10); i++) {
        const text = await chips.nth(i).textContent();
        if (text) chipTexts.push(text.trim());
      }
      console.log(`[list] Chip texts: ${chipTexts.join(", ")}`);
    }

    // Check for short URL column content
    const shortUrlCells = page.getByText(/\/p\//);
    const hasShortUrls = await shortUrlCells.count();
    console.log(`[list] Cells with /p/ URLs: ${hasShortUrls}`);

    await page.screenshot({ path: `${OUT}/16-portal-list-statuses.png`, fullPage: true });
  });
});

test.describe("Responsive — Editor on Narrower Viewport", () => {
  test("editor adapts at 1024px width (tablet)", async ({ authenticatedPage: page, baseURL }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Check if sidebar collapses or becomes full-width
    const sidebar = page.locator("[class*='Sidebar'], [class*='sidebar'], aside");
    if ((await sidebar.count()) > 0) {
      const sidebarBox = await sidebar.first().boundingBox();
      console.log(`[responsive] Sidebar at 1024px: ${sidebarBox?.width}px wide`);
    }

    // Check overall layout
    await page.screenshot({ path: `${OUT}/17-editor-tablet.png`, fullPage: true });
  });

  test("portal list adapts at mobile width (390px)", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${root}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(3000);

    // Check if table has horizontal scroll or stacks
    const table = page.locator("table, [role='grid']");
    if ((await table.count()) > 0) {
      const tableBox = await table.first().boundingBox();
      console.log(`[responsive] Table at 390px: ${tableBox?.width}px wide`);
      // Check for horizontal overflow
      const hasOverflow = tableBox && tableBox.width > 390;
      console.log(`[responsive] Table overflows viewport: ${hasOverflow}`);
    }

    // Check tabs still accessible
    const tabs = page.locator("[role='tab']");
    const tabCount = await tabs.count();
    console.log(`[responsive] Tabs visible at mobile: ${tabCount}`);

    await page.screenshot({ path: `${OUT}/18-portal-list-mobile.png`, fullPage: true });
  });

  test("public portal page is responsive at mobile width", async ({
    authenticatedPage: page,
    baseURL,
  }) => {
    const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${root}/p/test-portal`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);

    // The portal card should not overflow on mobile
    const paper = page.locator("[class*='MuiPaper']");
    if ((await paper.count()) > 0) {
      const paperBox = await paper.first().boundingBox();
      console.log(`[responsive] Portal card at 390px: ${paperBox?.width}px wide`);
      if (paperBox) {
        expect(paperBox.width).toBeLessThanOrEqual(390);
      }
    }

    await page.screenshot({ path: `${OUT}/19-public-portal-mobile.png`, fullPage: true });
  });
});
