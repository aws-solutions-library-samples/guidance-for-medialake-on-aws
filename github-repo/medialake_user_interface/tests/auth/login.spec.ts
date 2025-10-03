import { test, expect } from "@playwright/test";

test("login with credentials", async ({ page }) => {
  await page.goto("http://localhost:5173/");
  await page.waitForSelector('input[name="username"]');
  await page.fill('input[name="username"]', "mne-medialake@amazon.com");
  await page.fill('input[name="password"]', "ChangeMe123!");
  await page.click('.amplify-button[type="submit"]');
  await page.waitForURL("http://localhost:5173/");
  await expect(page.locator("h1")).toContainText("MediaLake", {
    timeout: 10000,
  });
});

test("test", async ({ page }) => {
  await page.goto("http://localhost:5173/sign-in");
  await page.getByRole("textbox", { name: "Email" }).click();
  await page
    .getByRole("textbox", { name: "Email" })
    .fill("mne-medialake@amazon.com");
  await page.getByRole("textbox", { name: "Password" }).click();
  await page.getByRole("textbox", { name: "Password" }).fill("ChangeMe123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("button", { name: "User Management" }).click();
  await page.getByRole("button", { name: "Add User" }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("textbox", { name: "First Name" }).click();
  await page.getByRole("textbox", { name: "First Name" }).fill("load");
  await page.getByRole("textbox", { name: "First Name" }).press("Tab");
  await page
    .getByRole("button", { name: "Enter the user's first name" })
    .press("Tab");
  await page.getByRole("textbox", { name: "Last Name" }).fill("user");
  await page.getByRole("textbox", { name: "Email" }).click();
  await page
    .getByRole("textbox", { name: "Email" })
    .fill("medialake+testuser@amazon.com");
  await page.getByLabel("", { exact: true }).click();
  await page.getByRole("option", { name: "Admin" }).click();
  await page.locator("#menu-roles div").first().click();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.waitForTimeout(20000); // Wait for 2 seconds
  await page.getByText("Add User").click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page
    .getByRole("row", { name: "load user medialake+testuser@" })
    .getByLabel("Delete")
    .click();
  await page.getByRole("button").click();
  await page.getByRole("button", { name: "System Settings" }).click();
});
