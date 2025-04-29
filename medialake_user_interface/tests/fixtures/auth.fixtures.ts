import { test as base } from './s3.fixtures'; // Import and extend the test object with S3 fixtures
import { Page, BrowserContext } from '@playwright/test';

// Define the types for the auth fixtures
export type AuthFixtures = {
  authenticatedPage: Page;
  authenticatedContext: BrowserContext;
};

// Extend the s3 fixture test object with auth fixtures
export const test = base.extend<AuthFixtures>({
  authenticatedPage: [async ({ page }, use) => {
    // Login process
    await page.goto('http://localhost:5173/sign-in');
    await page.getByRole('textbox', { name: 'Email' }).fill('mne-medialake@amazon.com');
    await page.getByRole('textbox', { name: 'Password' }).fill('ChangeMe123!');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    
    // Use the authenticated page
    await use(page);
  }, { scope: 'test' }], // Auth scope is per test

  // If you need an authenticated context as well (example)
  authenticatedContext: [async ({ browser }, use) => {
      const context = await browser.newContext();
      const page = await context.newPage();
      // Login process (repeated or refactored)
      await page.goto('http://localhost:5173/sign-in');
      await page.getByRole('textbox', { name: 'Email' }).fill('mne-medialake@amazon.com');
      await page.getByRole('textbox', { name: 'Password' }).fill('ChangeMe123!');
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      // Wait for navigation or a specific element indicating login success
      await page.waitForURL('**/dashboard'); // Example: wait for dashboard URL

      await use(context);

      // Context cleanup
      await context.close();
  }, { scope: 'test' }],
});

// Re-export expect from the base playwright test module if needed
export { expect } from '@playwright/test'; 