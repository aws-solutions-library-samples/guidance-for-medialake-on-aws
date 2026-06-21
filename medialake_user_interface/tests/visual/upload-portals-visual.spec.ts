/**
 * Visual capture for the upload-portals UI changes on feat/upload-portal.
 *
 * WHAT THIS COVERS (the three changed areas):
 *   1. UploadPortalsSubNav  — the reframed secondary nav on the three list
 *      pages: a primary "Portals" tab, a vertical divider, a quiet
 *      "Building blocks" caption, then "Templates" + "Themes" tabs.
 *   2. PortalEditorSidebar  — the two collapsible group accordions
 *      ("Appearance" / "Structure") with their helper captions, the renamed
 *      "Colors" section, and expand/collapse behavior.
 *   3. TemplateEditorPage   — reuses the same grouped sidebar.
 *
 * ── IMPORTANT: WHERE TO POINT THIS ────────────────────────────────────────
 * As of this writing the grouped-sidebar / "Building blocks" work is an
 * UNCOMMITTED working-tree change (sectionGroups.ts is untracked). It is NOT
 * present in the ml-dev4 CloudFront deployment, which still serves the prior
 * flat/ungrouped build. To SEE THE CHANGES you must run this against a LOCAL
 * dev server built from the working tree (baseURL http://localhost:5173, the
 * default in playwright.config.ts). Running it against the deployed CloudFront
 * URL will fail the grouped-layout assertions because that build predates the
 * change.
 *
 * ── HOW TO RUN (local working tree against the ml-dev4 backend) ────────────
 *   cd medialake_user_interface
 *   # 1. Point local dev at the ml-dev4 runtime config (Cognito + API):
 *   curl -s https://d2gn8nwil93iye.cloudfront.net/aws-exports.json -o public/aws-exports.json
 *   curl -s https://d2gn8nwil93iye.cloudfront.net/feature-flags.json -o public/feature-flags.json
 *   # 2. Start the dev server (separate terminal) — serves the working tree:
 *   npm run dev
 *   # 3. Run this spec with the provisioned superAdministrators credentials:
 *   MEDIALAKE_TEST_EMAIL='<your-superadmin-test-email>' \
 *   MEDIALAKE_TEST_PASSWORD='<your-superadmin-test-password>' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 \
 *   npx playwright test tests/visual/upload-portals-visual.spec.ts --project=chromium
 *
 * PNGs are written to test-results/upload-portals-visual/. The spec also
 * asserts the new structure is present, so a green run == the change rendered.
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

const OUT = "test-results/upload-portals-visual";

// Stable capture context: fixed desktop viewport, light scheme, reduced motion.
test.use({
  viewport: { width: 1440, height: 900 },
  colorScheme: "light",
});

// Kill transitions/animations so screenshots are deterministic.
async function freeze(page: import("@playwright/test").Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}",
  });
}

test.describe("upload-portals visual — list sub-nav", () => {
  const pages: Array<{ tab: string; path: string }> = [
    { tab: "portals", path: "/settings/upload-portals" },
    { tab: "templates", path: "/settings/upload-portals/templates" },
    { tab: "themes", path: "/settings/upload-portals/themes" },
  ];

  for (const { tab, path } of pages) {
    test(`sub-nav renders on ${tab} list page`, async ({ authenticatedPage: page, baseURL }) => {
      await page.goto(`${baseURL ?? "http://localhost:5173"}${path}`, {
        waitUntil: "domcontentloaded",
      });
      await freeze(page);

      // The reframed nav: a "Portals" tab, a "Building blocks" caption, and
      // Templates/Themes tabs. These are the branch-new strings.
      await expect(page.getByRole("tab", { name: "Portals" })).toBeVisible();
      await expect(page.getByText("Building blocks", { exact: true })).toBeVisible();
      await expect(page.getByRole("tab", { name: "Templates" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "Themes" })).toBeVisible();

      await page.screenshot({ path: `${OUT}/subnav-${tab}-page.png`, fullPage: false });
    });
  }
});

test.describe("upload-portals visual — portal editor grouped sidebar", () => {
  test("both groups, expanded and collapsed", async ({ authenticatedPage: page, baseURL }) => {
    await page.goto(`${baseURL ?? "http://localhost:5173"}/settings/upload-portals/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);

    const sidebar = page.getByRole("complementary", { name: "Portal editor settings" });
    await expect(sidebar).toBeVisible({ timeout: 15000 });

    const appearanceGroup = page.locator("#portal-editor-group-appearance-header");
    const structureGroup = page.locator("#portal-editor-group-structure-header");
    await expect(appearanceGroup).toBeVisible();
    await expect(structureGroup).toBeVisible();

    // Group helper captions (branch-new) and the renamed "Colors" section.
    await expect(page.getByText("Saved as a Theme. Also included in Templates.")).toBeVisible();
    await expect(page.getByText("Saved as a Template, along with Appearance.")).toBeVisible();

    // Default state (Appearance group auto-expanded around the active section).
    await sidebar.screenshot({ path: `${OUT}/portal-sidebar-default.png` });

    // Expand Structure too → both groups open.
    await structureGroup.click();
    await expect(page.getByRole("button", { name: /Access Control/ })).toBeVisible();
    await sidebar.screenshot({ path: `${OUT}/portal-sidebar-both-expanded.png` });

    // The renamed section reads "Colors" (was "Appearance" in the flat version).
    await expect(page.getByRole("button", { name: /^Colors/ })).toBeVisible();

    // Collapse Appearance → only Structure remains open.
    await appearanceGroup.click();
    await sidebar.screenshot({ path: `${OUT}/portal-sidebar-appearance-collapsed.png` });
  });
});

test.describe("upload-portals visual — template editor grouped sidebar", () => {
  test("template editor reuses grouped sidebar", async ({ authenticatedPage: page, baseURL }) => {
    await page.goto(`${baseURL ?? "http://localhost:5173"}/settings/upload-portals/templates/new`, {
      waitUntil: "domcontentloaded",
    });
    await freeze(page);

    const sidebar = page.getByRole("complementary", { name: "Portal editor settings" });
    await expect(sidebar).toBeVisible({ timeout: 15000 });
    await expect(page.locator("#portal-editor-group-appearance-header")).toBeVisible();
    await expect(page.locator("#portal-editor-group-structure-header")).toBeVisible();

    await sidebar.screenshot({ path: `${OUT}/template-sidebar-default.png` });
  });
});
