import { test, expect } from "@playwright/test";

/**
 * Favorites Feature Tests
 *
 * These tests verify the favorites functionality including:
 * - Property 1: Favorite toggle state change (toggling flips the state)
 * - Property 2: Metadata preservation through add/retrieve cycle
 */

test.describe("Favorites Feature", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application and ensure user is authenticated
    // This assumes the test fixtures handle authentication
    await page.goto("/");
  });

  test.describe("Property 1: Favorite Toggle State Change", () => {
    test("toggling favorite on an unfavorited asset should mark it as favorited", async ({
      page,
    }) => {
      // Navigate to search or assets page where favorite toggle is available
      await page.goto("/search");

      // Wait for assets to load
      await page.waitForSelector('[data-testid="asset-card"], [data-testid="asset-row"]', {
        timeout: 10000,
      });

      // Find an asset that is not favorited (empty heart icon)
      const unfavoritedAsset = page
        .locator('[data-testid="favorite-button"]:not([data-favorited="true"])')
        .first();

      // Skip if no unfavorited assets found
      const count = await unfavoritedAsset.count();
      if (count === 0) {
        test.skip();
        return;
      }

      // Click to favorite
      await unfavoritedAsset.click();

      // Verify the state changed to favorited
      await expect(unfavoritedAsset).toHaveAttribute("data-favorited", "true", {
        timeout: 5000,
      });
    });

    test("toggling favorite on a favorited asset should remove it from favorites", async ({
      page,
    }) => {
      // Navigate to favorites section or find a favorited asset
      await page.goto("/search");

      // Wait for assets to load
      await page.waitForSelector('[data-testid="asset-card"], [data-testid="asset-row"]', {
        timeout: 10000,
      });

      // Find an asset that is favorited (filled heart icon)
      const favoritedAsset = page
        .locator('[data-testid="favorite-button"][data-favorited="true"]')
        .first();

      // Skip if no favorited assets found
      const count = await favoritedAsset.count();
      if (count === 0) {
        test.skip();
        return;
      }

      // Click to unfavorite
      await favoritedAsset.click();

      // Verify the state changed to unfavorited
      await expect(favoritedAsset).not.toHaveAttribute("data-favorited", "true", {
        timeout: 5000,
      });
    });

    test("favorite state should persist across page refresh", async ({ page }) => {
      // Navigate to search page
      await page.goto("/search");

      // Wait for assets to load
      await page.waitForSelector('[data-testid="asset-card"], [data-testid="asset-row"]', {
        timeout: 10000,
      });

      // Find an unfavorited asset and get its ID
      const unfavoritedButton = page
        .locator('[data-testid="favorite-button"]:not([data-favorited="true"])')
        .first();

      const count = await unfavoritedButton.count();
      if (count === 0) {
        test.skip();
        return;
      }

      // Get the asset ID before favoriting
      const assetId = await unfavoritedButton.getAttribute("data-asset-id");

      // Favorite the asset
      await unfavoritedButton.click();

      // Wait for the state to update
      await expect(unfavoritedButton).toHaveAttribute("data-favorited", "true", {
        timeout: 5000,
      });

      // Refresh the page
      await page.reload();

      // Wait for assets to load again
      await page.waitForSelector('[data-testid="asset-card"], [data-testid="asset-row"]', {
        timeout: 10000,
      });

      // Find the same asset by ID and verify it's still favorited
      const sameAssetButton = page.locator(
        `[data-testid="favorite-button"][data-asset-id="${assetId}"]`
      );

      await expect(sameAssetButton).toHaveAttribute("data-favorited", "true", {
        timeout: 5000,
      });
    });
  });

  test.describe("Property 2: Metadata Preservation", () => {
    test("favorited asset should preserve metadata in favorites list", async ({ page }) => {
      // Navigate to search page
      await page.goto("/search");

      // Wait for assets to load
      await page.waitForSelector('[data-testid="asset-card"]', {
        timeout: 10000,
      });

      // Get the first asset card
      const assetCard = page.locator('[data-testid="asset-card"]').first();

      // Extract metadata from the asset card
      const assetName = await assetCard.locator('[data-testid="asset-name"]').textContent();
      const assetType = await assetCard.locator('[data-testid="asset-type"]').textContent();

      // Find and click the favorite button
      const favoriteButton = assetCard.locator('[data-testid="favorite-button"]');
      const isFavorited = await favoriteButton.getAttribute("data-favorited");

      // If not favorited, favorite it
      if (isFavorited !== "true") {
        await favoriteButton.click();
        await expect(favoriteButton).toHaveAttribute("data-favorited", "true", {
          timeout: 5000,
        });
      }

      // Navigate to home page where favorites widget is displayed
      await page.goto("/");

      // Wait for favorites section to load
      const favoritesSection = page.locator('[data-testid="favorites-section"]');
      await expect(favoritesSection).toBeVisible({ timeout: 10000 });

      // Find the favorited asset in the favorites list
      const favoritedAssetCard = favoritesSection.locator('[data-testid="asset-card"]').filter({
        hasText: assetName || "",
      });

      // Verify the asset appears in favorites
      await expect(favoritedAssetCard).toBeVisible({ timeout: 5000 });

      // Verify metadata is preserved
      if (assetName) {
        await expect(favoritedAssetCard.locator('[data-testid="asset-name"]')).toHaveText(
          assetName
        );
      }

      if (assetType) {
        await expect(favoritedAssetCard.locator('[data-testid="asset-type"]')).toHaveText(
          assetType
        );
      }
    });
  });
});
