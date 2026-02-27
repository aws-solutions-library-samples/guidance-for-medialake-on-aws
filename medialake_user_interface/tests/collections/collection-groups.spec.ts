import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";

/**
 * Collection Groups — create, edit, delete groups.
 * Single test to share the authenticated session.
 */

const GROUP_NAME = `E2E Test Group ${Date.now()}`;
const UPDATED_GROUP_NAME = `${GROUP_NAME} Updated`;

test("collection group lifecycle", async ({ authenticatedPage }) => {
  test.setTimeout(120000);

  const collectionsPage = new CollectionsPage(authenticatedPage);

  // --- Navigate to Groups tab ---
  await test.step("navigate to Groups tab", async () => {
    await collectionsPage.goto();
    await collectionsPage.tab("Groups").click();
    await expect(authenticatedPage.getByRole("button", { name: /Create Group/i })).toBeVisible();
  });

  // --- Create a new group ---
  await test.step("create a new collection group", async () => {
    await authenticatedPage.getByRole("button", { name: /Create Group/i }).click();

    await authenticatedPage.getByRole("dialog").waitFor({ state: "visible" });
    await authenticatedPage.getByRole("textbox", { name: /^Name/i }).fill(GROUP_NAME);
    await authenticatedPage
      .getByRole("textbox", { name: /Description/i })
      .fill("E2E test group description");

    // Submit — the button text is "Create Group"
    await authenticatedPage.getByRole("dialog").locator('button[type="submit"]').click();

    await authenticatedPage
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});

    await expect(authenticatedPage.getByText(GROUP_NAME)).toBeVisible({
      timeout: 10000,
    });
  });

  // --- Edit the group ---
  await test.step("edit the collection group name", async () => {
    const groupCard = authenticatedPage
      .locator(".MuiCard-root")
      .filter({ hasText: GROUP_NAME })
      .first();

    // Hover to reveal action buttons
    await groupCard.hover();
    await groupCard.getByRole("button", { name: /Edit/i }).click();

    await authenticatedPage.getByRole("dialog").waitFor({ state: "visible" });
    const nameField = authenticatedPage.getByRole("textbox", { name: /^Name/i });
    await nameField.clear();
    await nameField.fill(UPDATED_GROUP_NAME);

    await authenticatedPage.getByRole("dialog").locator('button[type="submit"]').click();

    await authenticatedPage
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});

    await expect(authenticatedPage.getByText(UPDATED_GROUP_NAME)).toBeVisible({
      timeout: 10000,
    });
  });

  // --- Delete the group ---
  await test.step("delete the collection group", async () => {
    const groupCard = authenticatedPage
      .locator(".MuiCard-root")
      .filter({ hasText: UPDATED_GROUP_NAME })
      .first();

    // Hover to reveal action buttons
    await groupCard.hover();

    // Set up handler for the native window.confirm() dialog BEFORE clicking delete
    authenticatedPage.once("dialog", async (dialog) => {
      await dialog.accept();
    });

    await groupCard.getByRole("button", { name: /Delete/i }).click();

    // Wait for the group to disappear from the list
    await expect(authenticatedPage.getByRole("heading", { name: UPDATED_GROUP_NAME })).toBeHidden({
      timeout: 10000,
    });
  });
});
