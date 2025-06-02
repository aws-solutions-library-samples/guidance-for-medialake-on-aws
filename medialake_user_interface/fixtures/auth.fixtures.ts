import { test as base } from './cognito.fixtures'; // Import and extend the test object with Cognito fixtures
import { Page, BrowserContext } from '@playwright/test';

// Define the types for the auth fixtures
export type AuthFixtures = {
  authenticatedPage: Page;
  authenticatedContext: BrowserContext;
};

// Extend the cognito fixture test object with auth fixtures
export const test = base.extend<AuthFixtures>({
  authenticatedPage: [async ({ page, cognitoTestUser, baseURL }, use) => {
    // Login process using the dynamically created test user
    const loginUrl = baseURL ? `${baseURL}/sign-in` : '/sign-in';
    await page.goto(loginUrl);
    await page.getByRole('textbox', { name: 'Email' }).fill(cognitoTestUser.username);
    await page.getByRole('textbox', { name: 'Password' }).fill(cognitoTestUser.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    
    // Wait for successful login (adjust selector based on your app's behavior)
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    
    // Use the authenticated page
    await use(page);
  }, { scope: 'test' }], // Auth scope is per test

  // If you need an authenticated context as well
  authenticatedContext: [async ({ browser, cognitoTestUser, baseURL }, use) => {
      const context = await browser.newContext();
      const page = await context.newPage();
      
      // Login process using the dynamically created test user
      const loginUrl = baseURL ? `${baseURL}/sign-in` : '/sign-in';
      await page.goto(loginUrl);
      await page.getByRole('textbox', { name: 'Email' }).fill(cognitoTestUser.username);
      await page.getByRole('textbox', { name: 'Password' }).fill(cognitoTestUser.password);
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
      
      // Wait for navigation or a specific element indicating login success
      await page.waitForURL('**/dashboard', { timeout: 15000 });

      await use(context);

      // Context cleanup
      await context.close();
  }, { scope: 'test' }],
});

// Re-export expect from the base playwright test module if needed
export { expect } from '@playwright/test'; 