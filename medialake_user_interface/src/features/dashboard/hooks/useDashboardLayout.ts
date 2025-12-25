import { useCallback } from "react";
import { useDashboardStore, DEFAULT_LAYOUT } from "../store/dashboardStore";
import type { LayoutItem, WidgetType, DashboardLayout } from "../types";

/**
 * Hook for dashboard layout operations
 * Provides a simplified interface for common layout operations
 */
export const useDashboardLayout = () => {
  const layout = useDashboardStore((state) => state.layout);
  const setLayout = useDashboardStore((state) => state.setLayout);
  const updateLayoutItem = useDashboardStore((state) => state.updateLayoutItem);
  const addWidget = useDashboardStore((state) => state.addWidget);
  const removeWidget = useDashboardStore((state) => state.removeWidget);
  const resetToDefault = useDashboardStore((state) => state.resetToDefault);

  /**
   * Get layout item for a specific widget
   */
  const getWidgetLayout = useCallback(
    (widgetId: string, breakpoint: "lg" | "md" | "sm" = "lg"): LayoutItem | undefined => {
      return layout.layouts[breakpoint].find((item) => item.i === widgetId);
    },
    [layout]
  );

  /**
   * Get widget instance by ID
   */
  const getWidget = useCallback(
    (widgetId: string) => {
      return layout.widgets.find((w) => w.id === widgetId);
    },
    [layout]
  );

  /**
   * Check if a widget type exists in the layout
   */
  const hasWidgetType = useCallback(
    (type: WidgetType): boolean => {
      return layout.widgets.some((w) => w.type === type);
    },
    [layout]
  );

  /**
   * Get all widgets of a specific type
   */
  const getWidgetsByType = useCallback(
    (type: WidgetType) => {
      return layout.widgets.filter((w) => w.type === type);
    },
    [layout]
  );

  /**
   * Move widget to a specific position
   */
  const moveWidget = useCallback(
    (widgetId: string, x: number, y: number) => {
      updateLayoutItem(widgetId, { x, y });
    },
    [updateLayoutItem]
  );

  /**
   * Resize widget to specific dimensions
   */
  const resizeWidget = useCallback(
    (widgetId: string, w: number, h: number) => {
      updateLayoutItem(widgetId, { w, h });
    },
    [updateLayoutItem]
  );

  /**
   * Check if layout matches default
   */
  const isDefaultLayout = useCallback((): boolean => {
    return JSON.stringify(layout) === JSON.stringify(DEFAULT_LAYOUT);
  }, [layout]);

  /**
   * Export layout as JSON string
   */
  const exportLayout = useCallback((): string => {
    return JSON.stringify(layout, null, 2);
  }, [layout]);

  /**
   * Import layout from JSON string
   */
  const importLayout = useCallback(
    (jsonString: string): boolean => {
      try {
        const importedLayout = JSON.parse(jsonString) as DashboardLayout;
        // Basic validation
        if (importedLayout.version && importedLayout.widgets && importedLayout.layouts) {
          setLayout(importedLayout);
          return true;
        }
        return false;
      } catch {
        return false;
      }
    },
    [setLayout]
  );

  return {
    // State
    layout,
    widgets: layout.widgets,

    // Actions
    setLayout,
    updateLayoutItem,
    addWidget,
    removeWidget,
    resetToDefault,

    // Helpers
    getWidgetLayout,
    getWidget,
    hasWidgetType,
    getWidgetsByType,
    moveWidget,
    resizeWidget,
    isDefaultLayout,
    exportLayout,
    importLayout,
  };
};
