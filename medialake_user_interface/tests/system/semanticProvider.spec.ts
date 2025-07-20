import { test } from "../fixtures/auth.fixtures";
import { expect } from "@playwright/test";

test.describe("Semantic Provider Configuration Management", () => {
  test("should navigate to System Settings page", async ({
    authenticatedPage: page,
  }) => {
    // Navigate to System Settings
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "System Settings" }).click();

    // Verify we're on the System Settings page
    await expect(page.locator("#settings-tabpanel-0")).toBeVisible({
      timeout: 10000,
    });

    // Verify the checkbox exists
    const checkbox = page.locator("#settings-tabpanel-0").getByRole("checkbox");
    await expect(checkbox).toBeVisible();

    // Verify if Edit Provider button exists - using a more flexible selector
    await expect(
      page.getByRole("button", { name: /Edit Provider/i }),
    ).toBeVisible({
      timeout: 10000,
    });
  });

  /*
  test.beforeEach(async ({ authenticatedPage: page }) => {
    // Navigate to System Settings
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'System Settings' }).click();

    // Verify checkbox is initially unchecked
    const checkbox = page.locator('#settings-tabpanel-0').getByRole('checkbox');
    // await expect(checkbox).not.toBeChecked();

    // Continue with provider configuration
    await page.getByRole('button', { name: 'Edit Provider' }).click();
    await page.getByRole('textbox', { name: 'API Key' }).click();
    await page.getByRole('textbox', { name: 'API Key' }).fill('tlk_1VV4MK82G4PG9S22H1JKS35F8ZW3');
    await page.getByRole('button', { name: 'Save' }).click();

    // Toggle checkbox states
    await page.locator('#settings-tabpanel-0').getByRole('checkbox').uncheck();
    await page.locator('#settings-tabpanel-0').getByRole('checkbox').check();
    await page.getByRole('button', { name: 'Reset Provider' }).click();
  });

  test('should configure semantic provider successfully', async ({ authenticatedPage: page }) => {
    // Verify the provider configuration was successful
    await expect(page.getByText('Provider updated successfully')).toBeVisible();

    // Additional verification steps can be added here
    // For example, verify the API key field is empty after reset
    await page.getByRole('button', { name: 'Edit Provider' }).click();
    const apiKeyField = page.getByRole('textbox', { name: 'API Key' });
    await expect(apiKeyField).toHaveValue('');
  });
  */
});
