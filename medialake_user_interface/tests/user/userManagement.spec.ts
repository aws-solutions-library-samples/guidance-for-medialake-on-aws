import { expect } from "@playwright/test";
import { test } from "../fixtures/auth.fixtures";

test.describe("User Management", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    // Navigate to User Management section
    // Sidebar button was renamed from "User Management" to "Users and Groups"
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Users and Groups" }).click();
  });

  test("should add and delete a user", async ({ authenticatedPage: page }) => {
    // Add user
    await page.getByRole("button", { name: "Add User" }).click();
    await page.getByRole("dialog").waitFor({ state: "visible" });

    await page.getByRole("textbox", { name: "First Name" }).fill("load");
    await page.getByRole("textbox", { name: "Last Name" }).fill("user");
    await page.getByRole("textbox", { name: "Email" }).fill("medialake+testuser@amazon.com");

    // Select group — the role selector is now a FormSelect labelled "Group"
    const groupSelect = page.getByRole("dialog").getByRole("combobox");
    if (await groupSelect.isVisible().catch(() => false)) {
      await groupSelect.click();
      await page.getByRole("option", { name: /admin/i }).first().click();
    }

    // Submit form — button text is "Add"
    await page.getByRole("dialog").getByRole("button", { name: "Add", exact: true }).click();

    // Wait for dialog to close
    await page
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});

    // Verify user was added
    await expect(page.getByRole("row", { name: /load.*user.*medialake\+testuser/i })).toBeVisible({
      timeout: 10000,
    });

    // Delete user — the delete button is an IconButton with tooltip "Delete"
    await page
      .getByRole("row", { name: /load.*user.*medialake\+testuser/i })
      .getByRole("button", { name: /delete/i })
      .click();

    // Confirm deletion if a confirmation dialog appears
    const confirmDialog = page.getByRole("dialog");
    if (await confirmDialog.isVisible({ timeout: 3000 }).catch(() => false)) {
      await confirmDialog.getByRole("button", { name: /delete|confirm|yes/i }).click();
    }

    // Verify user was deleted
    await expect(
      page.getByRole("row", { name: /load.*user.*medialake\+testuser/i })
    ).not.toBeVisible({
      timeout: 10000,
    });
  });
});
