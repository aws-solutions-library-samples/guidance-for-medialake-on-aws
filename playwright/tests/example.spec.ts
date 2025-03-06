import { test, expect } from '@playwright/test';

test('basic test', async ({ page }) => {
  // Navigate to the app
  await page.goto('http://localhost:3000');
  
  // Verify the page title
  await expect(page).toHaveTitle(/MediaLake/);
  
  // Simple assertion that will pass
  expect(true).toBeTruthy();
}); 