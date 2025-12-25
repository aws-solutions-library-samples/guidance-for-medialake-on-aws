import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  DashboardLayout,
  DashboardState,
  DashboardActions,
  LayoutItem,
  WidgetType,
  WidgetDefinition,
} from "../types";

// Widget definitions with metadata
export const WIDGET_DEFINITIONS: Record<WidgetType, WidgetDefinition> = {
  favorites: {
    type: "favorites",
    title: "Favorites",
    description: "Quick access to your favorited assets and collections",
    icon: "favorite",
    defaultSize: { w: 6, h: 4 },
    minSize: { w: 3, h: 2 },
    maxSize: { w: 12, h: 8 },
  },
  "my-collections": {
    type: "my-collections",
    title: "My Collections",
    description: "View and manage your personal collections",
    icon: "folder",
    defaultSize: { w: 6, h: 4 },
    minSize: { w: 3, h: 2 },
    maxSize: { w: 12, h: 8 },
  },
  "recent-assets": {
    type: "recent-assets",
    title: "Recent Assets",
    description: "Recently ingested media assets",
    icon: "schedule",
    defaultSize: { w: 12, h: 4 },
    minSize: { w: 4, h: 2 },
    maxSize: { w: 12, h: 8 },
  },
};

// Default layout configuration
export const DEFAULT_LAYOUT: DashboardLayout = {
  version: 1,
  widgets: [
    { id: "favorites-1", type: "favorites" },
    { id: "my-collections-1", type: "my-collections" },
    { id: "recent-assets-1", type: "recent-assets" },
  ],
  layouts: {
    lg: [
      { i: "favorites-1", x: 0, y: 0, w: 6, h: 4, minW: 3, minH: 2, maxW: 12, maxH: 8 },
      { i: "my-collections-1", x: 6, y: 0, w: 6, h: 4, minW: 3, minH: 2, maxW: 12, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 4, w: 12, h: 4, minW: 4, minH: 2, maxW: 12, maxH: 8 },
    ],
    md: [
      { i: "favorites-1", x: 0, y: 0, w: 5, h: 4, minW: 3, minH: 2, maxW: 10, maxH: 8 },
      { i: "my-collections-1", x: 5, y: 0, w: 5, h: 4, minW: 3, minH: 2, maxW: 10, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 4, w: 10, h: 4, minW: 4, minH: 2, maxW: 10, maxH: 8 },
    ],
    sm: [
      { i: "favorites-1", x: 0, y: 0, w: 1, h: 4, minW: 1, minH: 2, maxW: 1, maxH: 8 },
      { i: "my-collections-1", x: 0, y: 4, w: 1, h: 4, minW: 1, minH: 2, maxW: 1, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 8, w: 1, h: 4, minW: 1, minH: 2, maxW: 1, maxH: 8 },
    ],
  },
};

const STORAGE_KEY = "dashboard-layout";
const CURRENT_VERSION = 1;

// Helper to generate unique widget ID
const generateWidgetId = (type: WidgetType): string => {
  return `${type}-${Date.now()}`;
};

// Helper to find first available position in grid
const findAvailablePosition = (
  layouts: LayoutItem[],
  widgetDef: WidgetDefinition,
  cols: number
): { x: number; y: number } => {
  const { w, h } = widgetDef.defaultSize;

  // Create a grid map to track occupied cells
  const maxY = layouts.reduce((max, item) => Math.max(max, item.y + item.h), 0);
  const gridHeight = maxY + h + 10; // Add buffer for new widget
  const grid: boolean[][] = Array(gridHeight)
    .fill(null)
    .map(() => Array(cols).fill(false));

  // Mark occupied cells
  layouts.forEach((item) => {
    for (let row = item.y; row < item.y + item.h && row < gridHeight; row++) {
      for (let col = item.x; col < item.x + item.w && col < cols; col++) {
        grid[row][col] = true;
      }
    }
  });

  // Find first position where widget fits
  for (let y = 0; y < gridHeight; y++) {
    for (let x = 0; x <= cols - w; x++) {
      let fits = true;
      for (let dy = 0; dy < h && fits; dy++) {
        for (let dx = 0; dx < w && fits; dx++) {
          if (y + dy >= gridHeight || grid[y + dy][x + dx]) {
            fits = false;
          }
        }
      }
      if (fits) {
        return { x, y };
      }
    }
  }

  // Default to bottom of grid
  return { x: 0, y: maxY };
};

interface DashboardStore extends DashboardState, DashboardActions {}

export const useDashboardStore = create<DashboardStore>()(
  persist(
    (set, get) => ({
      // Initial state
      layout: DEFAULT_LAYOUT,
      isEditMode: false,
      expandedWidgetId: null,
      isWidgetSelectorOpen: false,

      // Actions
      setLayout: (layout) => set({ layout }),

      updateLayoutItem: (itemId, updates) => {
        const { layout } = get();
        const newLayouts = { ...layout.layouts };

        (["lg", "md", "sm"] as const).forEach((breakpoint) => {
          newLayouts[breakpoint] = newLayouts[breakpoint].map((item) =>
            item.i === itemId ? { ...item, ...updates } : item
          );
        });

        set({
          layout: {
            ...layout,
            layouts: newLayouts,
          },
        });
      },

      addWidget: (type) => {
        const { layout } = get();
        const widgetDef = WIDGET_DEFINITIONS[type];
        const widgetId = generateWidgetId(type);

        // Create new widget instance
        const newWidget = { id: widgetId, type };

        // Create layout items for each breakpoint
        const newLayouts = { ...layout.layouts };
        const breakpointCols = { lg: 12, md: 10, sm: 1 };

        (["lg", "md", "sm"] as const).forEach((breakpoint) => {
          const cols = breakpointCols[breakpoint];
          const position = findAvailablePosition(newLayouts[breakpoint], widgetDef, cols);
          const size =
            breakpoint === "sm" ? { w: 1, h: widgetDef.defaultSize.h } : widgetDef.defaultSize;

          newLayouts[breakpoint] = [
            ...newLayouts[breakpoint],
            {
              i: widgetId,
              ...position,
              ...size,
              minW: breakpoint === "sm" ? 1 : widgetDef.minSize.w,
              minH: widgetDef.minSize.h,
              maxW: breakpoint === "sm" ? 1 : widgetDef.maxSize.w,
              maxH: widgetDef.maxSize.h,
            },
          ];
        });

        set({
          layout: {
            ...layout,
            widgets: [...layout.widgets, newWidget],
            layouts: newLayouts,
          },
          isWidgetSelectorOpen: false,
        });
      },

      removeWidget: (widgetId) => {
        const { layout } = get();

        set({
          layout: {
            ...layout,
            widgets: layout.widgets.filter((w) => w.id !== widgetId),
            layouts: {
              lg: layout.layouts.lg.filter((item) => item.i !== widgetId),
              md: layout.layouts.md.filter((item) => item.i !== widgetId),
              sm: layout.layouts.sm.filter((item) => item.i !== widgetId),
            },
          },
        });
      },

      resetToDefault: () => {
        set({ layout: DEFAULT_LAYOUT });
      },

      setExpandedWidget: (widgetId) => {
        set({ expandedWidgetId: widgetId });
      },

      toggleWidgetSelector: () => {
        set((state) => ({ isWidgetSelectorOpen: !state.isWidgetSelectorOpen }));
      },

      setWidgetSelectorOpen: (isOpen) => {
        set({ isWidgetSelectorOpen: isOpen });
      },

      saveLayout: () => {
        // Layout is automatically saved by persist middleware
        // This method exists for explicit save calls if needed
      },

      loadLayout: () => {
        // Layout is automatically loaded by persist middleware
        // This method exists for explicit load calls if needed
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      version: CURRENT_VERSION,
      migrate: (persistedState, version) => {
        // Handle version migrations
        if (version < CURRENT_VERSION) {
          // Reset to default if version mismatch
          return {
            layout: DEFAULT_LAYOUT,
            isEditMode: false,
            expandedWidgetId: null,
            isWidgetSelectorOpen: false,
          };
        }
        return persistedState as DashboardStore;
      },
      partialize: (state) => ({
        layout: state.layout,
      }),
    }
  )
);

// Selectors
export const useDashboardLayout = () => useDashboardStore((state) => state.layout);
export const useExpandedWidget = () => useDashboardStore((state) => state.expandedWidgetId);
export const useWidgetSelectorOpen = () => useDashboardStore((state) => state.isWidgetSelectorOpen);
export const useDashboardActions = () => {
  const store = useDashboardStore();
  return {
    setLayout: store.setLayout,
    updateLayoutItem: store.updateLayoutItem,
    addWidget: store.addWidget,
    removeWidget: store.removeWidget,
    resetToDefault: store.resetToDefault,
    setExpandedWidget: store.setExpandedWidget,
    toggleWidgetSelector: store.toggleWidgetSelector,
    setWidgetSelectorOpen: store.setWidgetSelectorOpen,
    saveLayout: store.saveLayout,
    loadLayout: store.loadLayout,
  };
};

// Helper to get available widgets (not currently in layout)
export const useAvailableWidgets = () => {
  const layout = useDashboardLayout();
  const currentTypes = new Set(layout.widgets.map((w) => w.type));

  return Object.values(WIDGET_DEFINITIONS).filter((def) => !currentTypes.has(def.type));
};
