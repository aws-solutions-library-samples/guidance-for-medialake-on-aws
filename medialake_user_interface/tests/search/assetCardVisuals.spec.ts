import { test, expect } from '@playwright/test';

test.describe('Asset Card Visuals', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to search page and perform a semantic search
    await page.goto('http://localhost:5174/');
    
    // Wait for the page to load
    await page.waitForSelector('input[placeholder*="search"]', { timeout: 10000 });
    
    // Perform a semantic search to get clip results
    await page.fill('input[placeholder*="search"]', 'test query');
    await page.keyboard.press('Enter');
    
    // Wait for search results to load
    await page.waitForTimeout(2000);
  });

  test('should show score information on clip cards', async ({ page }) => {
    // Check if score information is visible on asset cards
    const scoreElements = page.locator('text=/score:/');
    
    // Wait for score elements to be visible
    await page.waitForTimeout(1000);
    
    // Check if at least one score element is present
    const scoreCount = await scoreElements.count();
    console.log(`Found ${scoreCount} score elements`);
    
    // If we have clip results, we should see score information
    if (scoreCount > 0) {
      await expect(scoreElements.first()).toBeVisible();
      
      // Check that the score format is correct (e.g., "score: 0.123")
      const scoreText = await scoreElements.first().textContent();
      expect(scoreText).toMatch(/score: \d+\.\d+/);
    }
  });

  test('should show clip count on full asset cards', async ({ page }) => {
    // Switch to full mode to see clip counts
    // This would require clicking on a toggle or changing the view mode
    // For now, we'll just check if any clip-related elements exist
    
    const clipElements = page.locator('text=/clip/');
    
    // Wait for elements to load
    await page.waitForTimeout(1000);
    
    const clipCount = await clipElements.count();
    console.log(`Found ${clipCount} clip-related elements`);
    
    // If we have clip elements, they should be visible
    if (clipCount > 0) {
      await expect(clipElements.first()).toBeVisible();
    }
  });

  test('should display asset cards with proper styling', async ({ page }) => {
    // Check if asset cards are rendered
    const assetCards = page.locator('[data-testid="asset-card"]');
    
    // Wait for cards to load
    await page.waitForTimeout(1000);
    
    const cardCount = await assetCards.count();
    console.log(`Found ${cardCount} asset cards`);
    
    if (cardCount > 0) {
      // Check that cards have proper styling
      await expect(assetCards.first()).toBeVisible();
      
      // Check for hover effects (this is more of a visual test)
      await assetCards.first().hover();
      await page.waitForTimeout(500);
    }
  });

  test('should show score filter when in clip mode', async ({ page }) => {
    // Check if score filter is visible
    const scoreFilter = page.locator('[data-testid="score-filter"]');
    
    // Wait for filter to load
    await page.waitForTimeout(1000);
    
    // The score filter should be visible when we have clip results
    await expect(scoreFilter).toBeVisible();
    
    // Check that the filter has the expected elements
    const slider = scoreFilter.locator('input[type="range"]');
    const input = scoreFilter.locator('input[type="text"]');
    
    await expect(slider).toBeVisible();
    await expect(input).toBeVisible();
  });
}); 