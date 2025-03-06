import { Page } from '@playwright/test';

/**
 * Handles user authentication for Playwright tests
 */
export async function loginUser(
  page: Page, 
  username: string = process.env.TEST_USERNAME || 'test@example.com',
  password: string = process.env.TEST_PASSWORD || 'Password123!'
): Promise<void> {
  await page.goto('/');
  
  // Wait for login page to load and enter credentials
  await page.waitForSelector('input[type="email"]');
  await page.fill('input[type="email"]', username);
  await page.fill('input[type="password"]', password);
  
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
  await page.waitForSelector('input[type="email"]');
}

/**
 * Gets the authentication token from local storage
 */
export async function getAuthToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => window.localStorage.getItem('authToken'));
} 