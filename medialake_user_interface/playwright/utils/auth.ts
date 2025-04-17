import { Page, expect } from '@playwright/test';

/**
 * Handles user authentication for Playwright tests
 */
export async function loginUser(
  page: Page, 
  username: string = process.env.TEST_USERNAME || 'mne-medialake@amazon.com',
  password: string = process.env.TEST_PASSWORD || 'ChangeMe123!'
): Promise<void> {
  await page.goto('/');
  
  // Wait for login page to load
  await page.waitForSelector('.amplify-input.amplify-field-group__control');

  // Find the email input by its class and ID
  const emailInput = page.locator('.amplify-input.amplify-field-group__control#amplify-id-\\:r9\\:');
  await expect(emailInput).toBeVisible();
  await emailInput.fill(username);
  
  // Find and fill password field with the specific ID
  const passwordInput = page.locator('#amplify-id-\\:rc\\:');
  await expect(passwordInput).toBeVisible();
  await passwordInput.fill(password);
  
  // Click login button and wait for navigation
  await page.click('button[type="submit"]');
  
  // Wait for successful login - adjust selector based on your application
  await page.waitForSelector('.sidebar', { timeout: 10000 });
}

/**
 * Logs out the current user
 */
export async function logoutUser(page: Page): Promise<void> {
  // Navigate to user menu and click logout
  // Adjust selectors based on your application's structure
  await page.click('.user-menu-button');
  await page.click('.logout-button');
  
  // Wait for redirect to login page
  await page.waitForSelector('.amplify-input.amplify-field-group__control');
}

/**
 * Gets the authentication token from local storage
 */
export async function getAuthToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => window.localStorage.getItem('authToken'));
}
