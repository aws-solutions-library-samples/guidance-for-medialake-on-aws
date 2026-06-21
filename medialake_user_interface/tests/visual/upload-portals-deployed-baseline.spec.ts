/**
 * Deployed-state baseline + login validation for ml-dev4.
 *
 * Runs against PLAYWRIGHT_BASE_URL (defaults to the ml-dev4 CloudFront URL).
 * Its jobs:
 *   1. Prove the provisioned superAdministrators credentials log in via the
 *      real UI (Cognito SRP) end-to-end.
 *   2. Capture the CURRENTLY DEPLOYED appearance of the three changed areas as
 *      a "before" baseline, and record whether the branch-new strings are
 *      present (they are expected to be ABSENT on the deployed build).
 *
 * It intentionally does NOT assert the new grouped layout, so it passes against
 * the older deployed build. Use upload-portals-visual.spec.ts (local dev) to
 * assert the actual changes.
 */
import { test, expect } from "../fixtures/static-auth.fixtures";

const OUT = "test-results/upload-portals-deployed";

test("login works + capture deployed upload-portals baseline", async ({
  authenticatedPage: page,
  baseURL,
}) => {
  const root = baseURL ?? "https://d2gn8nwil93iye.cloudfront.net";

  // 1. Login already happened in the fixture; prove we left /sign-in.
  expect(page.url()).not.toContain("sign-in");
  await page.screenshot({ path: `${OUT}/00-post-login.png`, fullPage: false });

  // 2. List pages — capture the deployed sub-nav and note new-string presence.
  for (const [name, path] of [
    ["portals", "/settings/upload-portals"],
    ["templates", "/settings/upload-portals/templates"],
    ["themes", "/settings/upload-portals/themes"],
  ] as const) {
    await page.goto(`${root}${path}`, { waitUntil: "domcontentloaded" });
    // "Portals" tab exists in both old and new versions — a safe settle anchor.
    await page.getByRole("tab", { name: "Portals" }).waitFor({ state: "visible", timeout: 20000 });
    await page.waitForTimeout(800);
    const hasBuildingBlocks = await page.getByText("Building blocks", { exact: true }).count();
    console.log(`[baseline] ${path} -> "Building blocks" present: ${hasBuildingBlocks > 0}`);
    await page.screenshot({ path: `${OUT}/subnav-${name}.png`, fullPage: false });
  }

  // 3. Portal editor (deployed sidebar) — full-page baseline.
  await page.goto(`${root}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const hasStructureGroup = await page
    .getByText("Saved as a Template, along with Appearance.")
    .count();
  console.log(`[baseline] /new -> grouped sidebar present: ${hasStructureGroup > 0}`);
  await page.screenshot({ path: `${OUT}/portal-editor-new.png`, fullPage: true });

  // 4. Template editor (deployed sidebar) — full-page baseline.
  await page.goto(`${root}/settings/upload-portals/templates/new`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/template-editor-new.png`, fullPage: true });
});
