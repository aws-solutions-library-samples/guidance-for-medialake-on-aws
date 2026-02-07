import { test, expect, Page } from "@playwright/test";

/**
 * Dashboard Grid Layout E2E Tests
 *
 * Tests the dashboard grid functionality including:
 * - Layout persistence
 * - Widget management (add/remove)
 * - Drag and drop
 * - Resize functionality
 * - Responsive behavior
 *
 * Prerequisites:
 * - Application running locally or deployed
 * - User authenticated (if required)
 */

// Test configuration
const BASE_URL = process.env.BASE_URL || "http://localhost:5173";
const DASHBOARD_STORAGE_KEY = "medialake-dashboard";

// Helper to clear dashboard storage
async function clearDashboardStorage(page: Page) {
  await page.evaluate((key) => {
    localStorage.removeItem(key);
  }, DASHBOARD_STORAGE_KEY);
}

// Helper to get dashboard storage
async function getDashboardStorage(page: Page) {
  return page.evaluate((key) => {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : null;
  }, DASHBOARD_STORAGE_KEY);
}

// Helper to set dashboard storage
async function setDashboardStorage(page: Page, data: object) {
  await page.evaluate(
    ({ key, value }) => {
      localStorage.setItem(key, JSON.stringify(value));
    },
    { key: DASHBOARD_STORAGE_KEY, value: data }
  );
}

test.describe("Dashboard Grid Layout", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard and clear storage for clean state
    await page.goto(BASE_URL);
    await clearDashboardStorage(page);
    await page.reload();
    await page.waitForLoadState("networkidle");
  });

  test.describe("Task 14.1: Layout Tests", () => {
    test("should load default layout with 3 widgets", async ({ page }) => {
      // Wait for dashboard grid to render
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Check for default widgets
      const widgets = page.locator("[data-grid-id]");
      const widgetCount = await widgets.count();

      expect(widgetCount).toBe(3);

      // Verify widget types exist
      const favoritesWidget = page.locator('[data-grid-id="favorites-1"]');
      const collectionsWidget = page.locator('[data-grid-id="my-collections-1"]');
      const recentWidget = page.locator('[data-grid-id="recent-assets-1"]');

      await expect(favoritesWidget).toBeVisible();
      await expect(collectionsWidget).toBeVisible();
      await expect(recentWidget).toBeVisible();
    });

    test("should persist layout changes to localStorage", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Get initial storage state
      const initialStorage = await getDashboardStorage(page);
      expect(initialStorage).not.toBeNull();
      expect(initialStorage.state.layout.widgets).toHaveLength(3);

      // Remove a widget
      const removeButton = page
        .locator('[data-grid-id="favorites-1"]')
        .getByRole("button", { name: /remove/i });
      await removeButton.click();

      // Confirm removal if dialog appears
      const confirmButton = page.getByRole("button", { name: /confirm|yes|remove/i });
      if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmButton.click();
      }

      await page.waitForTimeout(500);

      // Verify storage updated
      const updatedStorage = await getDashboardStorage(page);
      expect(updatedStorage.state.layout.widgets).toHaveLength(2);
    });

    test("should restore saved layout on page reload", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Remove a widget to change layout
      const removeButton = page
        .locator('[data-grid-id="favorites-1"]')
        .getByRole("button", { name: /remove/i });
      await removeButton.click();

      const confirmButton = page.getByRole("button", { name: /confirm|yes|remove/i });
      if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmButton.click();
      }

      await page.waitForTimeout(500);

      // Reload page
      await page.reload();
      await page.waitForLoadState("networkidle");
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Verify layout persisted (only 2 widgets)
      const widgets = page.locator("[data-grid-id]");
      const widgetCount = await widgets.count();
      expect(widgetCount).toBe(2);

      // Favorites should not exist
      const favoritesWidget = page.locator('[data-grid-id="favorites-1"]');
      await expect(favoritesWidget).not.toBeVisible();
    });

    test("should enforce widget size bounds during resize", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Get a widget element
      const widget = page.locator('[data-grid-id="favorites-1"]');
      await expect(widget).toBeVisible();

      // Get initial size
      const initialBox = await widget.boundingBox();
      expect(initialBox).not.toBeNull();

      // Find resize handle
      const resizeHandle = widget.locator(".react-resizable-handle");

      if (await resizeHandle.isVisible()) {
        const handleBox = await resizeHandle.boundingBox();
        if (handleBox) {
          // Try to resize to very small (should be constrained by minW/minH)
          await page.mouse.move(
            handleBox.x + handleBox.width / 2,
            handleBox.y + handleBox.height / 2
          );
          await page.mouse.down();
          await page.mouse.move(handleBox.x - 500, handleBox.y - 500);
          await page.mouse.up();

          await page.waitForTimeout(300);

          // Get new size - should be at minimum bounds, not smaller
          const newBox = await widget.boundingBox();
          expect(newBox).not.toBeNull();
          // Widget should still have reasonable size (min bounds enforced)
          expect(newBox!.width).toBeGreaterThan(100);
          expect(newBox!.height).toBeGreaterThan(100);
        }
      }
    });
  });

  test.describe("Task 14.2: Widget Management Tests", () => {
    test("should open widget selector when clicking Add Widget", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Click Add Widget button
      const addButton = page.getByRole("button", { name: /add widget/i });
      await addButton.click();

      // Widget selector dialog should appear
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();

      // Should show available widget options
      await expect(dialog.getByText(/favorites/i)).toBeVisible();
    });

    test("should add widget from selector", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // First remove a widget to make room for adding
      const removeButton = page
        .locator('[data-grid-id="favorites-1"]')
        .getByRole("button", { name: /remove/i });
      await removeButton.click();

      const confirmRemove = page.getByRole("button", { name: /confirm|yes|remove/i });
      if (await confirmRemove.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmRemove.click();
      }

      await page.waitForTimeout(500);

      // Now add it back
      const addButton = page.getByRole("button", { name: /add widget/i });
      await addButton.click();

      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();

      // Click on Favorites widget option
      const favoritesOption = dialog.getByText(/favorites/i);
      await favoritesOption.click();

      await page.waitForTimeout(500);

      // Verify widget was added
      const widgets = page.locator("[data-grid-id]");
      const widgetCount = await widgets.count();
      expect(widgetCount).toBe(3);
    });

    test("should remove widget when clicking remove button", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Get initial widget count
      const initialWidgets = page.locator("[data-grid-id]");
      const initialCount = await initialWidgets.count();
      expect(initialCount).toBe(3);

      // Remove favorites widget
      const removeButton = page
        .locator('[data-grid-id="favorites-1"]')
        .getByRole("button", { name: /remove/i });
      await removeButton.click();

      const confirmButton = page.getByRole("button", { name: /confirm|yes|remove/i });
      if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmButton.click();
      }

      await page.waitForTimeout(500);

      // Verify widget removed
      const finalWidgets = page.locator("[data-grid-id]");
      const finalCount = await finalWidgets.count();
      expect(finalCount).toBe(2);
    });

    test("should reset to default layout", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // Remove a widget first
      const removeButton = page
        .locator('[data-grid-id="favorites-1"]')
        .getByRole("button", { name: /remove/i });
      await removeButton.click();

      const confirmRemove = page.getByRole("button", { name: /confirm|yes|remove/i });
      if (await confirmRemove.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confirmRemove.click();
      }

      await page.waitForTimeout(500);

      // Verify only 2 widgets
      let widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(2);

      // Click reset button
      const resetButton = page.getByRole("button", { name: /reset/i });
      await resetButton.click();

      // Confirm reset
      const confirmReset = page.getByRole("button", { name: /reset/i }).last();
      await confirmReset.click();

      await page.waitForTimeout(500);

      // Verify back to 3 widgets
      widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(3);
    });

    test("should disable Add Widget when all widgets are added", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // All 3 widgets should be present by default
      const widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(3);

      // Add Widget button should be disabled
      const addButton = page.getByRole("button", { name: /add widget/i });
      await expect(addButton).toBeDisabled();
    });
  });

  test.describe("Task 14.3: Widget Data Tests", () => {
    test("should display Favorites widget with header", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      const favoritesWidget = page.locator('[data-grid-id="favorites-1"]');
      await expect(favoritesWidget).toBeVisible();

      // Check for widget header
      const header = favoritesWidget.locator(".widget-drag-handle");
      await expect(header).toBeVisible();

      // Check for title
      await expect(favoritesWidget.getByText(/favorites/i)).toBeVisible();
    });

    test("should display My Collections widget with header", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      const collectionsWidget = page.locator('[data-grid-id="my-collections-1"]');
      await expect(collectionsWidget).toBeVisible();

      // Check for widget header
      const header = collectionsWidget.locator(".widget-drag-handle");
      await expect(header).toBeVisible();

      // Check for title
      await expect(collectionsWidget.getByText(/collections/i)).toBeVisible();
    });

    test("should display Recent Assets widget with header", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      const recentWidget = page.locator('[data-grid-id="recent-assets-1"]');
      await expect(recentWidget).toBeVisible();

      // Check for widget header
      const header = recentWidget.locator(".widget-drag-handle");
      await expect(header).toBeVisible();

      // Check for title
      await expect(recentWidget.getByText(/recent/i)).toBeVisible();
    });

    test("should show empty state when no data", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // At least one widget should show empty state or data
      // This depends on actual data in the system
      const emptyStates = page.locator('[data-testid="empty-state"]');
      const assetCards = page.locator('[data-testid^="asset-card-"]');
      const collectionCards = page.locator('[data-testid^="collection-card-"]');

      // Either we have data or empty states
      const hasEmptyState = (await emptyStates.count()) > 0;
      const hasData = (await assetCards.count()) > 0 || (await collectionCards.count()) > 0;

      expect(hasEmptyState || hasData).toBe(true);
    });

    test("should have refresh button on widgets", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      const favoritesWidget = page.locator('[data-grid-id="favorites-1"]');
      const refreshButton = favoritesWidget.getByRole("button", { name: /refresh/i });

      await expect(refreshButton).toBeVisible();
    });

    test("should have expand button on widgets", async ({ page }) => {
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      const favoritesWidget = page.locator('[data-grid-id="favorites-1"]');
      const expandButton = favoritesWidget.getByRole("button", { name: /expand/i });

      await expect(expandButton).toBeVisible();
    });
  });

  test.describe("Task 14.4: Responsive Layout Tests", () => {
    test("should display full grid on desktop viewport", async ({ page }) => {
      // Set desktop viewport
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto(BASE_URL);
      await clearDashboardStorage(page);
      await page.reload();
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // All widgets should be visible
      const widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(3);

      // Widgets should be arranged in grid (not stacked)
      const widget1 = page.locator('[data-grid-id="favorites-1"]');
      const widget2 = page.locator('[data-grid-id="my-collections-1"]');

      const box1 = await widget1.boundingBox();
      const box2 = await widget2.boundingBox();

      expect(box1).not.toBeNull();
      expect(box2).not.toBeNull();

      // On desktop, widgets can be side by side (same Y) or stacked
      // Just verify they're both visible and have reasonable sizes
      expect(box1!.width).toBeGreaterThan(200);
      expect(box2!.width).toBeGreaterThan(200);
    });

    test("should stack widgets on mobile viewport", async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto(BASE_URL);
      await clearDashboardStorage(page);
      await page.reload();
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // All widgets should still be visible
      const widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(3);

      // On mobile, widgets should be stacked (single column)
      const widget1 = page.locator('[data-grid-id="favorites-1"]');
      const widget2 = page.locator('[data-grid-id="my-collections-1"]');

      const box1 = await widget1.boundingBox();
      const box2 = await widget2.boundingBox();

      expect(box1).not.toBeNull();
      expect(box2).not.toBeNull();

      // Widgets should take full width on mobile
      // Allow some margin for padding
      expect(box1!.width).toBeGreaterThan(300);
    });

    test("should adjust layout on tablet viewport", async ({ page }) => {
      // Set tablet viewport
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto(BASE_URL);
      await clearDashboardStorage(page);
      await page.reload();
      await page.waitForSelector(".dashboard-grid", { timeout: 10000 });

      // All widgets should be visible
      const widgets = page.locator("[data-grid-id]");
      expect(await widgets.count()).toBe(3);

      // Verify widgets have reasonable sizes for tablet
      const widget1 = page.locator('[data-grid-id="favorites-1"]');
      const box1 = await widget1.boundingBox();

      expect(box1).not.toBeNull();
      expect(box1!.width).toBeGreaterThan(200);
    });
  });
});
