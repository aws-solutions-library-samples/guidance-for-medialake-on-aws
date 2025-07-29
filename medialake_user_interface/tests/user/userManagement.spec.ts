import { expect } from "@playwright/test";
import { test } from "../fixtures/auth.fixtures";

test.describe("User Management", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    // Navigate to User Management section
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "User Management" }).click();
  });

  test("should add and delete a user", async ({ authenticatedPage: page }) => {
    // Add user
    await page.getByRole("button", { name: "Add User" }).click();
    await page.getByRole("textbox", { name: "First Name" }).fill("load");
    await page.getByRole("textbox", { name: "Last Name" }).fill("user");
    await page
      .getByRole("textbox", { name: "Email" })
      .fill("medialake+testuser@amazon.com");

    // Select role
    await page.getByLabel("", { exact: true }).click();
    await page.getByRole("option", { name: "Admin" }).click();
    await page.locator("#menu-roles div").first().click();

    // Submit form
    await page.getByRole("button", { name: "Add", exact: true }).click();

    // Verify user was added
    await expect(
      page.getByRole("row", { name: "load user medialake+testuser@" }),
    ).toBeVisible({
      timeout: 10000,
    });

    // Delete user
    await page
      .getByRole("row", { name: "load user medialake+testuser@" })
      .getByLabel("Delete")
      .click();
    await page.getByRole("button").click();

    // Verify user was deleted
    await expect(
      page.getByRole("row", { name: "load user medialake+testuser@" }),
    ).not.toBeVisible({
      timeout: 10000,
    });
  });
});
