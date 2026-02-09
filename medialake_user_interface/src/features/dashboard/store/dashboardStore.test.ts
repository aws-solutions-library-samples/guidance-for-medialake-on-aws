import { describe, it, expect, beforeEach } from "vitest";
import * as fc from "fast-check";
import { useDashboardStore, DEFAULT_LAYOUT } from "./dashboardStore";
import type { CollectionsWidgetConfig, CollectionViewType, SortBy, SortOrder } from "../types";

/**
 * Property-Based Tests for Dashboard Store
 *
 * Feature: dashboard-collection-widgets
 * Property 3: Widget Configuration Independence
 *
 * **Validates: Requirements 1.3, 3.1**
 */

describe("Property 3: Widget Configuration Independence", () => {
  beforeEach(() => {
    // Reset store to default state before each test
    // Clear localStorage to ensure clean state
    localStorage.clear();
    const store = useDashboardStore.getState();
    store.resetToDefault();
  });

  // Arbitrary generators for widget configuration
  const viewTypeArbitrary = fc.constantFrom<CollectionViewType>(
    "all",
    "public",
    "private",
    "my-collections",
    "shared-with-me",
    "my-shared"
  );

  const sortByArbitrary = fc.constantFrom<SortBy>("name", "createdAt", "updatedAt");
  const sortOrderArbitrary = fc.constantFrom<SortOrder>("asc", "desc");

  const sortConfigArbitrary = fc.record({
    sortBy: sortByArbitrary,
    sortOrder: sortOrderArbitrary,
  });

  const collectionsWidgetConfigArbitrary = fc.record({
    viewType: viewTypeArbitrary,
    sorting: sortConfigArbitrary,
  }) as fc.Arbitrary<CollectionsWidgetConfig>;

  it("should update only the target widget configuration without affecting other widgets", () => {
    fc.assert(
      fc.property(
        collectionsWidgetConfigArbitrary,
        collectionsWidgetConfigArbitrary,
        (config1, config2) => {
          const store = useDashboardStore.getState();

          // Add two collections widgets
          store.addWidget("collections");
          store.addWidget("collections");

          const layout = useDashboardStore.getState().layout;
          const widgets = layout.widgets.filter((w) => w.type === "collections");

          // Ensure we have at least 2 collections widgets
          expect(widgets.length).toBeGreaterThanOrEqual(2);

          const widget1Id = widgets[0].id;
          const widget2Id = widgets[1].id;

          // Store the default config of widget2 before any updates
          const widget2DefaultConfig = widgets[1].config;

          // Update first widget's configuration
          store.updateWidgetConfig(widget1Id, config1);

          // Get updated state
          const updatedLayout1 = useDashboardStore.getState().layout;
          const updatedWidget1 = updatedLayout1.widgets.find((w) => w.id === widget1Id);
          const updatedWidget2 = updatedLayout1.widgets.find((w) => w.id === widget2Id);

          // Property: First widget should have the new config
          expect(updatedWidget1?.config).toEqual(config1);

          // Property: Second widget should still have its original config (not affected)
          expect(updatedWidget2?.config).toEqual(widget2DefaultConfig);

          // Update second widget's configuration
          store.updateWidgetConfig(widget2Id, config2);

          // Get final state
          const updatedLayout2 = useDashboardStore.getState().layout;
          const finalWidget1 = updatedLayout2.widgets.find((w) => w.id === widget1Id);
          const finalWidget2 = updatedLayout2.widgets.find((w) => w.id === widget2Id);

          // Property: First widget config should remain unchanged
          expect(finalWidget1?.config).toEqual(config1);

          // Property: Second widget should have the new config
          expect(finalWidget2?.config).toEqual(config2);

          // Property: Configs should be independent (different if inputs were different)
          if (JSON.stringify(config1) !== JSON.stringify(config2)) {
            expect(finalWidget1?.config).not.toEqual(finalWidget2?.config);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should maintain configuration independence across multiple widget updates", () => {
    // This test verifies that updating one widget's config doesn't affect other widgets
    // We use a simpler approach: start with DEFAULT_LAYOUT which has one collections widget,
    // add two more, and verify independence

    fc.assert(
      fc.property(
        collectionsWidgetConfigArbitrary,
        collectionsWidgetConfigArbitrary,
        (config1, config2) => {
          // Reset store for each property run
          localStorage.clear();
          const store = useDashboardStore.getState();
          store.resetToDefault();

          // Get the existing collections widget from DEFAULT_LAYOUT
          const initialLayout = useDashboardStore.getState().layout;
          const existingWidget = initialLayout.widgets.find((w) => w.type === "collections");
          expect(existingWidget).toBeDefined();

          const widget1Id = existingWidget!.id;

          // Add one more collections widget
          store.addWidget("collections");
          const layout2 = useDashboardStore.getState().layout;
          const allCollectionsWidgets = layout2.widgets.filter((w) => w.type === "collections");
          const widget2 = allCollectionsWidgets.find((w) => w.id !== widget1Id);
          expect(widget2).toBeDefined();
          const widget2Id = widget2!.id;

          // Update each widget with its config
          store.updateWidgetConfig(widget1Id, config1);
          store.updateWidgetConfig(widget2Id, config2);

          // Get final state
          const finalLayout = useDashboardStore.getState().layout;
          const finalWidget1 = finalLayout.widgets.find((w) => w.id === widget1Id);
          const finalWidget2 = finalLayout.widgets.find((w) => w.id === widget2Id);

          // Property: Each widget should have exactly its assigned config
          expect(finalWidget1?.config).toEqual(config1);
          expect(finalWidget2?.config).toEqual(config2);

          // Property: Widgets with different configs should not have the same config
          if (JSON.stringify(config1) !== JSON.stringify(config2)) {
            expect(finalWidget1?.config).not.toEqual(finalWidget2?.config);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("should not affect non-collections widgets when updating collections widget config", () => {
    fc.assert(
      fc.property(collectionsWidgetConfigArbitrary, (config) => {
        const store = useDashboardStore.getState();

        // Add different widget types
        store.addWidget("favorites");
        store.addWidget("collections");
        store.addWidget("recent-assets");

        const layout = useDashboardStore.getState().layout;
        const collectionsWidget = layout.widgets.find((w) => w.type === "collections");
        const favoritesWidget = layout.widgets.find((w) => w.type === "favorites");
        const recentAssetsWidget = layout.widgets.find((w) => w.type === "recent-assets");

        expect(collectionsWidget).toBeDefined();
        expect(favoritesWidget).toBeDefined();
        expect(recentAssetsWidget).toBeDefined();

        // Store original state of other widgets
        const originalFavorites = { ...favoritesWidget };
        const originalRecentAssets = { ...recentAssetsWidget };

        // Update collections widget config
        store.updateWidgetConfig(collectionsWidget!.id, config);

        // Get updated state
        const updatedLayout = useDashboardStore.getState().layout;
        const updatedFavorites = updatedLayout.widgets.find((w) => w.id === favoritesWidget!.id);
        const updatedRecentAssets = updatedLayout.widgets.find(
          (w) => w.id === recentAssetsWidget!.id
        );

        // Property: Other widget types should remain unchanged
        expect(updatedFavorites).toEqual(originalFavorites);
        expect(updatedRecentAssets).toEqual(originalRecentAssets);

        // Property: Collections widget should have new config
        const updatedCollections = updatedLayout.widgets.find(
          (w) => w.id === collectionsWidget!.id
        );
        expect(updatedCollections?.config).toEqual(config);
      }),
      { numRuns: 100 }
    );
  });

  it("should preserve widget IDs and types when updating configuration", () => {
    fc.assert(
      fc.property(collectionsWidgetConfigArbitrary, (config) => {
        const store = useDashboardStore.getState();

        store.addWidget("collections");

        const layout = useDashboardStore.getState().layout;
        const widget = layout.widgets.find((w) => w.type === "collections");

        expect(widget).toBeDefined();

        const originalId = widget!.id;
        const originalType = widget!.type;

        // Update config
        store.updateWidgetConfig(widget!.id, config);

        // Get updated state
        const updatedLayout = useDashboardStore.getState().layout;
        const updatedWidget = updatedLayout.widgets.find((w) => w.id === originalId);

        // Property: Widget ID should remain unchanged
        expect(updatedWidget?.id).toBe(originalId);

        // Property: Widget type should remain unchanged
        expect(updatedWidget?.type).toBe(originalType);

        // Property: Only config should change
        expect(updatedWidget?.config).toEqual(config);
      }),
      { numRuns: 100 }
    );
  });

  it("should mark dashboard as having pending changes when config is updated", () => {
    fc.assert(
      fc.property(collectionsWidgetConfigArbitrary, (config) => {
        const store = useDashboardStore.getState();

        // Reset pending changes flag
        store.setHasPendingChanges(false);

        store.addWidget("collections");

        // Reset again after adding widget
        store.setHasPendingChanges(false);

        const layout = useDashboardStore.getState().layout;
        const widget = layout.widgets.find((w) => w.type === "collections");

        expect(widget).toBeDefined();
        expect(useDashboardStore.getState().hasPendingChanges).toBe(false);

        // Update config
        store.updateWidgetConfig(widget!.id, config);

        // Property: Dashboard should be marked as having pending changes
        expect(useDashboardStore.getState().hasPendingChanges).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it("should handle updating non-existent widget gracefully", () => {
    fc.assert(
      fc.property(fc.uuid(), collectionsWidgetConfigArbitrary, (nonExistentId, config) => {
        const store = useDashboardStore.getState();

        // Get initial state
        const initialLayout = useDashboardStore.getState().layout;
        const initialWidgetCount = initialLayout.widgets.length;

        // Try to update non-existent widget
        store.updateWidgetConfig(nonExistentId, config);

        // Get updated state
        const updatedLayout = useDashboardStore.getState().layout;

        // Property: Widget count should remain unchanged
        expect(updatedLayout.widgets.length).toBe(initialWidgetCount);

        // Property: No widget should have the non-existent ID
        const foundWidget = updatedLayout.widgets.find((w) => w.id === nonExistentId);
        expect(foundWidget).toBeUndefined();
      }),
      { numRuns: 100 }
    );
  });

  it("should allow updating the same widget multiple times with different configs", () => {
    fc.assert(
      fc.property(
        fc.array(collectionsWidgetConfigArbitrary, { minLength: 2, maxLength: 5 }),
        (configs) => {
          const store = useDashboardStore.getState();

          store.addWidget("collections");

          const layout = useDashboardStore.getState().layout;
          const widget = layout.widgets.find((w) => w.type === "collections");

          expect(widget).toBeDefined();

          // Apply each config sequentially
          configs.forEach((config, index) => {
            store.updateWidgetConfig(widget!.id, config);

            const currentLayout = useDashboardStore.getState().layout;
            const currentWidget = currentLayout.widgets.find((w) => w.id === widget!.id);

            // Property: Widget should have the most recent config
            expect(currentWidget?.config).toEqual(config);

            // Property: Widget should not have any previous config (only if configs are different)
            if (index > 0 && JSON.stringify(config) !== JSON.stringify(configs[index - 1])) {
              expect(currentWidget?.config).not.toEqual(configs[index - 1]);
            }
          });

          // Property: Final config should be the last one applied
          const finalLayout = useDashboardStore.getState().layout;
          const finalWidget = finalLayout.widgets.find((w) => w.id === widget!.id);
          expect(finalWidget?.config).toEqual(configs[configs.length - 1]);
        }
      ),
      { numRuns: 100 }
    );
  });
});
