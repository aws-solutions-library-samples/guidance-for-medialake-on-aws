import { test as base, Page } from '@playwright/test';

// Define the type for our custom fixtures
type AuthFixtures = {
  authenticatedPage: Page;
};

// Extend the base test fixture with a new "authenticated" fixture
export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Login process
    await page.goto('http://localhost:5173/sign-in');
    await page.getByRole('textbox', { name: 'Email' }).fill('mne-medialake@amazon.com');
    await page.getByRole('textbox', { name: 'Password' }).fill('ChangeMe123!');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    
    // Use the authenticated page
    await use(page);
  },
}); 