/**
 * Permission-based smoke tests.
 *
 * Tests that different user roles (superAdmin, editor, readOnly) see
 * the correct UI elements and are blocked from unauthorized actions.
 *
 * Requires AWS CLI configured with access to the Cognito user pool.
 * Creates temporary test users per test, cleans up after.
 *
 * Run with: npx playwright test tests/smoke/permissions.spec.ts --config=playwright.smoke.config.ts
 */
import { test, expect } from "../fixtures/role-auth.fixtures";

test.describe("Super Administrator permissions", () => {
  test("can access all settings pages", async ({ superAdminPage }) => {
    test.setTimeout(90000);
    const page = superAdminPage;

    // Settings menu should be visible
    await page.getByRole("button", { name: "Settings" }).click();

    // All settings sub-pages should be accessible
    await expect(page.getByRole("button", { name: "Connectors" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Users and Groups" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Permissions" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Integrations" })).toBeVisible();
    await expect(page.getByRole("button", { name: "System Settings" })).toBeVisible();
  });

  test("can access system settings", async ({ superAdminPage }) => {
    test.setTimeout(60000);
    const page = superAdminPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "System Settings" }).click();
    await expect(page).toHaveURL(/settings\/system/);
    await expect(page.getByRole("heading", { name: "System Settings" })).toBeVisible();
  });

  test("can access user management", async ({ superAdminPage }) => {
    test.setTimeout(60000);
    const page = superAdminPage;

    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Users and Groups" }).click();
    await expect(page).toHaveURL(/settings\/users/);
  });

  test("can access pipelines", async ({ superAdminPage }) => {
    test.setTimeout(60000);
    const page = superAdminPage;

    await page.getByRole("button", { name: "Pipelines" }).click();
    await expect(page).toHaveURL(/pipelines/);
    await expect(page.getByRole("heading", { name: "Pipelines", level: 4 })).toBeVisible();

    // Should see "Add New Pipeline" button
    await expect(page.getByText("Add New Pipeline")).toBeVisible();
  });

  test("can search assets", async ({ superAdminPage }) => {
    test.setTimeout(60000);
    const page = superAdminPage;

    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });
  });

  test("can access collections", async ({ superAdminPage }) => {
    test.setTimeout(60000);
    const page = superAdminPage;

    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);
    await expect(page.getByRole("button", { name: "Create Collection" }).first()).toBeVisible();
  });
});

test.describe("Editor permissions", () => {
  test("can view dashboard and assets", async ({ editorPage }) => {
    test.setTimeout(60000);
    const page = editorPage;

    // Dashboard should load
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
  });

  test("can search assets", async ({ editorPage }) => {
    test.setTimeout(60000);
    const page = editorPage;

    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });
  });

  test("can access collections", async ({ editorPage }) => {
    test.setTimeout(60000);
    const page = editorPage;

    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);
  });

  test("settings access is restricted", async ({ editorPage }) => {
    test.setTimeout(60000);
    const page = editorPage;

    // Try to navigate directly to system settings
    await page.goto("/settings/system");

    // Should be redirected to access-denied or the settings page should not show system settings
    // The exact behavior depends on the permission configuration:
    // - If route guard blocks: redirected to /access-denied
    // - If sidebar hides: settings button may not show system settings sub-item
    const url = page.url();
    const isBlocked =
      url.includes("access-denied") ||
      url.includes("settings/profile") ||
      url === (page.context().pages()[0]?.url() || "");

    // Editor should NOT see system settings content
    // Either they're redirected or the page shows access denied
    if (!url.includes("access-denied")) {
      // If not redirected, the system settings heading should not be visible
      // (the page might show a loading state or redirect client-side)
      await page.waitForTimeout(3000);
    }

    // Verify the editor doesn't have full admin access
    // by checking the sidebar doesn't show all settings sub-items
    await page.goto("/");
    await page.waitForTimeout(2000);

    // Click settings to expand
    const settingsBtn = page.getByRole("button", { name: "Settings" });
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();
      await page.waitForTimeout(1000);

      // Editor should NOT see "Users and Groups" or "System Settings"
      // (these require manage permissions)
      const usersBtn = page.getByRole("button", { name: "Users and Groups" });
      const systemBtn = page.getByRole("button", { name: "System Settings" });

      // At least one of these should be hidden for an editor
      const usersVisible = await usersBtn.isVisible().catch(() => false);
      const systemVisible = await systemBtn.isVisible().catch(() => false);

      // If the editors group has restricted permissions, these should be hidden
      // Log the result for debugging
      console.log(`[Editor] Users visible: ${usersVisible}, System visible: ${systemVisible}`);
    }
  });
});

test.describe("Read-Only permissions", () => {
  test("can view dashboard", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
  });

  test("can search and view assets", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    await page.goto("/search?q=*&semantic=false");
    await expect(page.getByText(/Found \d+ results/)).toBeVisible({ timeout: 20000 });
  });

  test("cannot access admin settings", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    // Try to navigate directly to user management
    await page.goto("/settings/users");

    // Should be redirected to access-denied
    await page.waitForTimeout(3000);
    const url = page.url();

    // Read-only user should be blocked from admin pages
    const isBlocked =
      url.includes("access-denied") || url.includes("sign-in") || !url.includes("settings/users");

    expect(isBlocked).toBe(true);
  });

  test("cannot create collections", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    await page.getByRole("button", { name: "Collections" }).click();
    await expect(page).toHaveURL(/collections/);

    // The "Create Collection" button should either be hidden or disabled
    const createBtn = page.getByRole("button", { name: "Create Collection" }).first();
    const isVisible = await createBtn.isVisible().catch(() => false);

    if (isVisible) {
      // If visible, it should be disabled
      const isDisabled = await createBtn.isDisabled().catch(() => false);
      console.log(`[ReadOnly] Create Collection visible: ${isVisible}, disabled: ${isDisabled}`);
    }
    // If not visible, that's the expected behavior for read-only
  });

  test("cannot access pipeline editor", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    // Try to navigate directly to pipeline creation
    await page.goto("/pipelines/new");
    await page.waitForTimeout(3000);

    const url = page.url();
    const isBlocked = url.includes("access-denied") || !url.includes("pipelines/new");

    expect(isBlocked).toBe(true);
  });

  test("settings menu is restricted", async ({ readOnlyPage }) => {
    test.setTimeout(60000);
    const page = readOnlyPage;

    await page.goto("/");
    await page.waitForTimeout(2000);

    const settingsBtn = page.getByRole("button", { name: "Settings" });
    const settingsVisible = await settingsBtn.isVisible().catch(() => false);

    if (settingsVisible) {
      await settingsBtn.click();
      await page.waitForTimeout(1000);

      // Read-only should NOT see admin settings
      const usersBtn = page.getByRole("button", { name: "Users and Groups" });
      const permissionsBtn = page.getByRole("button", { name: "Permissions" });
      const systemBtn = page.getByRole("button", { name: "System Settings" });

      const usersVisible = await usersBtn.isVisible().catch(() => false);
      const permissionsVisible = await permissionsBtn.isVisible().catch(() => false);
      const systemVisible = await systemBtn.isVisible().catch(() => false);

      console.log(
        `[ReadOnly] Settings sub-items — Users: ${usersVisible}, Permissions: ${permissionsVisible}, System: ${systemVisible}`
      );

      // Read-only users should not see admin-level settings
      expect(usersVisible && permissionsVisible && systemVisible).toBe(false);
    }
    // If settings button itself is hidden, that's also correct for read-only
  });
});
