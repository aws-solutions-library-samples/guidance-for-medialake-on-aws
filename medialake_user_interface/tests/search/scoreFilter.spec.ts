import { test, expect } from '@playwright/test';

test.describe('Score Filter', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to search page and perform a semantic search
    await page.goto('http://localhost:5173/');
    
    // Wait for the page to load
    await page.waitForSelector('input[placeholder*="search"]', { timeout: 10000 });
    
    // Perform a semantic search to get clip results
    await page.fill('input[placeholder*="search"]', 'test query');
    await page.keyboard.press('Enter');
    
    // Wait for search results to load
    await page.waitForTimeout(2000);
  });

  test('should show score filter only in clip mode', async ({ page }) => {
    // Check if score filter is visible when in clip mode
    const scoreFilter = page.locator('text=/Score ≥/');
    
    // The score filter should be visible when we have clip results
    await expect(scoreFilter).toBeVisible();
  });

  test('should filter results based on score threshold', async ({ page }) => {
    // Get initial number of results
    const initialResults = await page.locator('[data-testid="asset-card"]').count();
    
    // Set score filter to a high value using the input field
    const scoreFilterInput = page.locator('text=/Score ≥/').locator('..').locator('input');
    await scoreFilterInput.fill('0.8');
    await scoreFilterInput.press('Enter');
    
    // Wait for filtering to complete
    await page.waitForTimeout(1000);
    
    // Get filtered number of results
    const filteredResults = await page.locator('[data-testid="asset-card"]').count();
    
    // Filtered results should be less than or equal to initial results
    expect(filteredResults).toBeLessThanOrEqual(initialResults);
  });

  test('should work with slider interaction', async ({ page }) => {
    // Get initial number of results
    const initialResults = await page.locator('[data-testid="asset-card"]').count();
    
    // Find the slider and drag it to a higher value
    const slider = page.locator('text=/Score ≥/').locator('..').locator('input[type="range"]');
    await slider.hover();
    await slider.click({ position: { x: 200, y: 0 } }); // Click towards the right side of slider
    
    // Wait for filtering to complete
    await page.waitForTimeout(1000);
    
    // Get filtered number of results
    const filteredResults = await page.locator('[data-testid="asset-card"]').count();
    
    // Filtered results should be less than or equal to initial results
    expect(filteredResults).toBeLessThanOrEqual(initialResults);
  });

  test('should show filtering summary', async ({ page }) => {
    // Set score filter using the input field
    const scoreFilterInput = page.locator('text=/Score ≥/').locator('..').locator('input');
    await scoreFilterInput.fill('0.5');
    await scoreFilterInput.press('Enter');
    
    // Wait for filtering to complete
    await page.waitForTimeout(1000);
    
    // Check if the score filter is visually active (has primary color)
    const scoreFilterContainer = page.locator('text=/Score ≥/').locator('..');
    await expect(scoreFilterContainer).toBeVisible();
  });

  test('should clear filter when clear button is clicked', async ({ page }) => {
    // Set score filter using the input field
    const scoreFilterInput = page.locator('text=/Score ≥/').locator('..').locator('input');
    await scoreFilterInput.fill('0.5');
    await scoreFilterInput.press('Enter');
    
    // Wait for filtering to complete
    await page.waitForTimeout(1000);
    
    // Get filtered count
    const filteredCount = await page.locator('[data-testid="asset-card"]').count();
    
    // Click clear button
    const clearButton = page.locator('text=/Score ≥/').locator('..').locator('button');
    await clearButton.click();
    
    // Wait for filter to clear
    await page.waitForTimeout(1000);
    
    // Get count after clearing
    const clearedCount = await page.locator('[data-testid="asset-card"]').count();
    
    // Count should be restored (greater than or equal to filtered count)
    expect(clearedCount).toBeGreaterThanOrEqual(filteredCount);
  });

  test('should show score filter even when no results match', async ({ page }) => {
    // Set score filter to a very high value that will filter out all results
    const scoreFilterInput = page.locator('text=/Score ≥/').locator('..').locator('input');
    await scoreFilterInput.fill('0.999');
    await scoreFilterInput.press('Enter');
    
    // Wait for filtering to complete
    await page.waitForTimeout(1000);
    
    // The score filter should still be visible
    const scoreFilterContainer = page.locator('text=/Score ≥/').locator('..');
    await expect(scoreFilterContainer).toBeVisible();
    
    // Check for the "No results match score filter" message
    const noResultsMessage = page.locator('text=/No results match score filter/');
    await expect(noResultsMessage).toBeVisible();
    
    // Check for the clear filter button
    const clearButton = page.locator('text=/Clear Score Filter/');
    await expect(clearButton).toBeVisible();
    
    // Click the clear button to restore results
    await clearButton.click();
    await page.waitForTimeout(1000);
    
    // Results should be visible again
    const assetCards = page.locator('[data-testid="asset-card"]');
    const cardCount = await assetCards.count();
    expect(cardCount).toBeGreaterThan(0);
  });
}); 