import { expect } from '@playwright/test';
import { test } from '../fixtures/auth.fixtures';

test.describe('Connector Management', () => {
  test('should add and delete an S3 connector', async ({ authenticatedPage, s3BucketName }) => {
    // Use authenticatedPage directly, aliasing to page for less refactoring
    const page = authenticatedPage;
    // Navigate to Connectors section
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'Connectors' }).click();
    await page.getByRole('button', { name: 'Add Connector' }).click();

    // Select S3 connector type
    await page.locator('div').filter({ hasText: /^Amazon S3$/ }).click();
    await page.getByText('Existing S3 BucketConnect to').click(); // Assuming this selects the specific S3 type

    // Fill in connector details
    const connectorName = 'test-s3-connector';
    await page.getByRole('textbox', { name: 'Connector Name' }).fill(connectorName);
    await page.getByRole('textbox', { name: 'Description' }).fill('this is my test S3 connector');
    await page.getByRole('combobox').first().click();
    await page.getByRole('option', { name: 'MediaLake Non-Managed' }).click();
    await page.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: 'S3 EventBridge Notifications' }).click();
    await page.getByRole('button').filter({ hasText: /^$/ }).nth(2).click();
    // Add a short wait to ensure the dropdown is fully loaded
    await page.waitForTimeout(2000);
    await page.getByRole('combobox').nth(2).click();
    await page.getByRole('option', { name: s3BucketName }).click();

    // Submit the form
    await page.getByRole('button', { name: 'Add Connector' }).click();

    // Verify connector creation (adjust selector as needed)
    // This assumes the connector appears in a card or list item
    // Wait up to 60 seconds for the card with the connector name to appear
    await expect(page.locator(`//h6[contains(text(), "${connectorName}")]`)).toBeVisible({ timeout: 60000 });
    
    // Find the delete button for the specific connector
    const connectorCard = page.locator('.MuiPaper-root', { has: page.locator(`h6:has-text("${connectorName}")`) });
    await connectorCard.getByRole('button', { name: /delete/i }).click();

    // Confirm deletion
    await page.getByRole('button', { name: 'Delete' }).click();

    // Verify connector deletion
    await expect(page.getByText('Connector deleted successfully')).toBeVisible({ timeout: 5000 });
    await expect(page.locator(`//h6[contains(text(), "${connectorName}")]`)).not.toBeVisible({ timeout: 20000 });
  });
});