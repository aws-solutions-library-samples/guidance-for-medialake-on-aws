import { expect } from "@playwright/test";
import { test } from "../fixtures/auth.fixtures";

test.describe("Connector Management", () => {
  test("should add and delete an S3 connector", async ({
    authenticatedPage,
    s3BucketName,
    s3BucketDeletion,
  }) => {
    // Use authenticatedPage directly, aliasing to page for less refactoring
    const page = authenticatedPage;

    console.log(`[Test] Using S3 bucket: ${s3BucketName}`);

    // Navigate to Connectors section
    await page.getByRole("button", { name: "Settings" }).click();
    await page.getByRole("button", { name: "Connectors" }).click();
    await page.getByRole("button", { name: "Add Connector" }).click();

    // Select S3 connector type
    await page
      .locator("div")
      .filter({ hasText: /^Amazon S3$/ })
      .click();
    await page.getByText("Existing S3 BucketConnect to").click(); // Assuming this selects the specific S3 type

    // Fill in connector details
    const connectorName = `test-s3-connector-${Date.now()}`;
    await page
      .getByRole("textbox", { name: "Connector Name" })
      .fill(connectorName);
    await page
      .getByRole("textbox", { name: "Description" })
      .fill("this is my test S3 connector");

    // First combobox - MediaLake Non-Managed
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "MediaLake Non-Managed" }).click();

    // Second combobox - S3 EventBridge Notifications
    await page.getByRole("combobox").nth(1).click();
    await page
      .getByRole("option", { name: "S3 EventBridge Notifications" })
      .click();

    // Wait for form to update
    await page.waitForTimeout(2000);

    // Handle the empty buttons (possibly for expanding sections)
    await page.getByRole("button").filter({ hasText: /^$/ }).nth(2).click();

    // Wait for the S3 bucket dropdown to be ready
    await page.waitForTimeout(3000);

    // Third combobox - S3 Bucket selection
    console.log(`[Test] Attempting to select S3 bucket: ${s3BucketName}`);
    await page.getByRole("combobox").nth(2).click();

    // Wait for the dropdown to populate and verify the bucket is available
    await page.waitForTimeout(2000);

    // Try to find the bucket option with retries
    let bucketFound = false;
    let attempts = 0;
    const maxAttempts = 5;

    while (!bucketFound && attempts < maxAttempts) {
      try {
        await page
          .getByRole("option", { name: s3BucketName })
          .waitFor({ timeout: 5000 });
        await page.getByRole("option", { name: s3BucketName }).click();
        bucketFound = true;
        console.log(`[Test] Successfully selected S3 bucket: ${s3BucketName}`);
      } catch (error) {
        attempts++;
        console.log(
          `[Test] Bucket ${s3BucketName} not found in dropdown, attempt ${attempts}/${maxAttempts}`,
        );
        if (attempts < maxAttempts) {
          // Close and reopen the dropdown
          await page.keyboard.press("Escape");
          await page.waitForTimeout(1000);
          await page.getByRole("combobox").nth(2).click();
          await page.waitForTimeout(2000);
        } else {
          throw new Error(
            `S3 bucket ${s3BucketName} not found in dropdown after ${maxAttempts} attempts`,
          );
        }
      }
    }

    // Submit the form
    await page.getByRole("button", { name: "Add Connector" }).click();

    // Verify connector creation (adjust selector as needed)
    // This assumes the connector appears in a card or list item
    // Wait up to 60 seconds for the card with the connector name to appear
    await expect(
      page.locator(`//h6[contains(text(), "${connectorName}")]`),
    ).toBeVisible({
      timeout: 60000,
    });

    // Find the delete button for the specific connector
    const connectorCard = page.locator(".MuiPaper-root", {
      has: page.locator(`h6:has-text("${connectorName}")`),
    });
    await connectorCard.getByRole("button", { name: /delete/i }).click();

    // Confirm deletion
    await page.getByRole("button", { name: "Delete" }).click();

    // Verify connector deletion
    await expect(page.getByText("Connector deleted successfully")).toBeVisible({
      timeout: 5000,
    });
    await expect(
      page.locator(`//h6[contains(text(), "${connectorName}")]`),
    ).not.toBeVisible({
      timeout: 20000,
    });

    // The s3BucketDeletion fixture will handle cleanup automatically
  });
});
