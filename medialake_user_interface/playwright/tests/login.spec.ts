import { test, expect } from '../fixtures/auth-fixture';

/**
 * Test suite for login functionality
 */
test.describe('MediaLake Login', () => {
  
  /**
   * Test to verify manual login functionality targeting the specific email input
   */
  test('should allow manual login with specific selectors', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Wait for login form to load
    await page.waitForSelector('.amplify-input.amplify-field-group__control');

    // Find the email input by its class and ID
    const emailInput = page.locator('.amplify-input.amplify-field-group__control#amplify-id-\\:r9\\:');
    await expect(emailInput).toBeVisible();

    // Enter credentials
    await emailInput.fill('mne-medialake@amazon.com');
    
    // Find and fill password field with the specific ID
    const passwordInput = page.locator('#amplify-id-\\:rc\\:');
    await expect(passwordInput).toBeVisible();
    await passwordInput.fill('ChangeMe123!');

    // Click the login button
    await page.locator('button[type="submit"]').click();

    // Wait for redirect after successful login - adjust selector based on your application
    await page.waitForSelector('.sidebar', { timeout: 10000 });

    // Verify successful login by checking for an element that would only be visible after login
    await expect(page.locator('.sidebar')).toBeVisible();
    
    // Additional verification - check for user profile or username display
    const userProfileElement = page.locator('.user-profile, .username');
    if (await userProfileElement.count() > 0) {
      await expect(userProfileElement).toBeVisible();
    }
  });

  /**
   * Test to verify login with invalid credentials
   */
  test('should display error message for invalid credentials', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Wait for login form to load
    await page.waitForSelector('.amplify-input.amplify-field-group__control');

    // Find the email input by its class and ID
    const emailInput = page.locator('.amplify-input.amplify-field-group__control#amplify-id-\\:r9\\:');
    
    // Enter invalid credentials
    await emailInput.fill('invalid@example.com');
    
    // Find and fill password field with the specific ID
    const passwordInput = page.locator('#amplify-id-\\:rc\\:');
    await passwordInput.fill('WrongPassword123!');

    // Click the login button
    await page.locator('button[type="submit"]').click();

    // Wait for and verify error message
    const errorMessage = page.locator('.amplify-alert--error, [role="alert"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
  });
  
  /**
   * Test to verify the automated auth fixture works
   */
  test('should login automatically using auth fixture', async ({ authenticatedPage }) => {
    // Navigate to a protected page
    await authenticatedPage.goto('/dashboard');
    
    // Verify we're logged in by checking for elements that should be visible
    await expect(authenticatedPage.locator('.sidebar')).toBeVisible();
  });
}); 