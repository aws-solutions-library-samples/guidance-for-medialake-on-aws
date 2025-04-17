import { test, expect } from '../fixtures/auth-fixture';

/**
 * UI tests for MediaLake application
 */
test.describe('MediaLake UI', () => {
  
  test('should display the dashboard after login', async ({ authenticatedPage }) => {
    // Navigate to dashboard and verify elements
    await authenticatedPage.goto('/dashboard');
    
    // Verify dashboard components are visible
    await expect(authenticatedPage.locator('.dashboard-title')).toBeVisible();
    await expect(authenticatedPage.locator('.pipeline-stats')).toBeVisible();
  });
  
  test('should navigate to pipelines page', async ({ authenticatedPage }) => {
    // Navigate to pipelines page
    await authenticatedPage.goto('/pipelines');
    
    // Verify pipelines components are visible
    await expect(authenticatedPage.locator('.pipelines-list')).toBeVisible();
    await expect(authenticatedPage.locator('.create-pipeline-button')).toBeVisible();
  });
  
  test('should open pipeline creation modal', async ({ authenticatedPage }) => {
    // Navigate to pipelines page
    await authenticatedPage.goto('/pipelines');
    
    // Click the create pipeline button
    await authenticatedPage.click('.create-pipeline-button');
    
    // Verify modal is visible
    await expect(authenticatedPage.locator('.pipeline-creation-modal')).toBeVisible();
    
    // Fill and submit form
    await authenticatedPage.fill('.pipeline-name-input', 'Test Pipeline');
    await authenticatedPage.fill('.pipeline-description-input', 'Test Description');
    await authenticatedPage.click('.submit-pipeline-button');
    
    // Verify success message
    await expect(authenticatedPage.locator('.success-message')).toBeVisible();
  });
  
  test('should navigate to settings page', async ({ authenticatedPage }) => {
    // Navigate to settings page
    await authenticatedPage.goto('/settings');
    
    // Verify settings components are visible
    await expect(authenticatedPage.locator('.settings-title')).toBeVisible();
    await expect(authenticatedPage.locator('.settings-form')).toBeVisible();
  });

  // Public UI tests
  test('homepage should load', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MediaLake/);
    
    // Check for main navigation elements
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('a:has-text("Login")')).toBeVisible();
  });
  
  test('login page should be accessible', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/Login/);
    
    // Check for login form elements
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button:has-text("Sign in")')).toBeVisible();
  });
});
