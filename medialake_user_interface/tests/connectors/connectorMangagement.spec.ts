import { expect } from "@playwright/test";
import { test } from "../fixtures/auth.fixtures";
import {
  navigateToConnectors,
  createS3ConnectorWithExistingBucket,
  deleteConnector,
} from "../utils/connector-helper.js";

test.describe("Connector Management", () => {
  test("should add and delete an S3 connector", async ({
    authenticatedPage,
    s3BucketName,
    s3BucketDeletion,
  }) => {
    // Use authenticatedPage directly, aliasing to page for less refactoring
    const page = authenticatedPage;

    console.log(`[Test] Using S3 bucket: ${s3BucketName}`);

    // Navigate to Connectors section using helper
    // Note: For this test we still need to go through Settings menu
    // as it tests the full UI navigation flow
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Connectors" }).click();
    await page.waitForTimeout(2000);

    // Get initial connector count by counting connector cards
    const initialConnectorCards = await page.locator('[data-testid^="connector-card-"]').count();
    console.log(`[Test] Initial connector count: ${initialConnectorCards}`);

    // Create S3 connector using helper
    const createResult = await createS3ConnectorWithExistingBucket(page, s3BucketName);
    expect(createResult.success).toBe(true);
    const connectorName = createResult.connectorName;

    // Verify connector creation using test ID
    // Wait for connector count to increase
    await page.waitForTimeout(3000);
    const newConnectorCards = await page.locator('[data-testid^="connector-card-"]').count();
    console.log(`[Test] New connector count: ${newConnectorCards}`);
    expect(newConnectorCards).toBe(initialConnectorCards + 1);

    // Also verify connector name is visible
    await expect(page.locator(`//h6[contains(text(), "${connectorName}")]`)).toBeVisible({
      timeout: 60000,
    });

    // Delete connector using helper
    const deleteResult = await deleteConnector(page, connectorName);
    expect(deleteResult).toBe(true);

    // Verify connector deletion
    await expect(page.getByText("Connector deleted successfully")).toBeVisible({
      timeout: 5000,
    });

    // Verify connector was deleted using connector count
    await page.waitForTimeout(2000);
    const finalConnectorCards = await page.locator('[data-testid^="connector-card-"]').count();
    console.log(`[Test] Final connector count: ${finalConnectorCards}`);
    expect(finalConnectorCards).toBe(initialConnectorCards);

    // Also verify connector name is no longer visible
    await expect(page.locator(`//h6[contains(text(), "${connectorName}")]`)).not.toBeVisible({
      timeout: 20000,
    });

    // The s3BucketDeletion fixture will handle cleanup automatically
  });
});
