import { test, expect } from '../fixtures/auth-fixture';

/**
 * Test suite for UI validation
 */
test.describe('MediaLake UI Validation', () => {
  
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
  
}); 