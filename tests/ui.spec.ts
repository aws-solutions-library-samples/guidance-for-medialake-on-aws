import { test, expect } from '@playwright/test';
import { test as authTest } from './fixtures/auth-fixture';

// Basic UI tests without authentication
test.describe('Public UI', () => {
  test('homepage should load', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MediaLake/);
    
    // Check for main elements
    await expect(page.locator('h1')).toContainText('MediaLake');
    await expect(page.locator('nav')).toBeVisible();
  });
  
  test('login page should be accessible', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/Login/);
    
    // Check for login form
    await expect(page.locator('[data-testid="username-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
  });
});

// Authenticated UI tests
authTest.describe('Authenticated UI', () => {
  authTest('dashboard should be accessible after login', async ({ loggedInPage }) => {
    const { page } = loggedInPage;
    
    await page.goto('/dashboard');
    await expect(page).toHaveTitle(/Dashboard/);
    
    // Check for dashboard elements
    await expect(page.locator('h1')).toContainText('Dashboard');
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
  });
  
  authTest('user profile should display correct information', async ({ loggedInPage }) => {
    const { page, username } = loggedInPage;
    
    await page.goto('/profile');
    await expect(page).toHaveTitle(/Profile/);
    
    // Check for user info
    await expect(page.locator('[data-testid="user-email"]')).toContainText(username);
  });
}); 