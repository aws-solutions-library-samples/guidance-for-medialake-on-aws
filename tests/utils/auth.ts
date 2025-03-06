import { Page } from '@playwright/test';

/**
 * Helper function to log in a user via the UI
 * @param page Playwright page object
 * @param username Username for login
 * @param password Password for login
 */
export async function login(page: Page, username: string, password: string): Promise<void> {
  // Navigate to login page
  await page.goto('/login');
  
  // Fill in login form
  await page.fill('[data-testid="username-input"]', username);
  await page.fill('[data-testid="password-input"]', password);
  
  // Submit form
  await page.click('[data-testid="login-button"]');
  
  // Wait for navigation to complete
  await page.waitForURL('/dashboard');
}

/**
 * Helper function to log out a user
 * @param page Playwright page object
 */
export async function logout(page: Page): Promise<void> {
  // Click on user menu
  await page.click('[data-testid="user-menu"]');
  
  // Click logout option
  await page.click('[data-testid="logout-button"]');
  
  // Wait for navigation to complete
  await page.waitForURL('/login');
} 