import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { useShallow } from "zustand/react/shallow";
import type {
  DashboardLayout,
  DashboardState,
  DashboardActions,
  LayoutItem,
  WidgetType,
  WidgetDefinition,
  CollectionsWidgetConfig,
  WidgetInstance,
} from "../types";

// Widget definitions with metadata
export const WIDGET_DEFINITIONS: Record<WidgetType, WidgetDefinition> = {
  favorites: {
    type: "favorites",
    title: "Favorites",
    description: "Quick access to your favorited assets and collections",
    icon: "favorite",
    defaultSize: { w: 6, h: 5 },
    minSize: { w: 3, h: 4 },
    maxSize: { w: 12, h: 12 },
  },
  collections: {
    type: "collections",
    title: "Collections",
    description: "Configurable view of your collections",
    icon: "folder",
    defaultSize: { w: 6, h: 5 },
    minSize: { w: 3, h: 2 },
    maxSize: { w: 12, h: 8 },
    defaultConfig: {
      viewType: "all",
      sorting: {
        sortBy: "name",
        sortOrder: "asc",
      },
    },
  },
  "recent-assets": {
    type: "recent-assets",
    title: "Recent Assets",
    description: "Recently ingested media assets",
    icon: "schedule",
    defaultSize: { w: 12, h: 5 },
    minSize: { w: 4, h: 4 },
    maxSize: { w: 12, h: 12 },
  },
};

// Default layout configuration
export const DEFAULT_LAYOUT: DashboardLayout = {
  version: 1,
  widgets: [
    { id: "favorites-1", type: "favorites" },
    {
      id: "collections-1",
      type: "collections",
      config: { viewType: "all", sorting: { sortBy: "name", sortOrder: "asc" } },
    },
    { id: "recent-assets-1", type: "recent-assets" },
  ],
  layouts: {
    lg: [
      { i: "favorites-1", x: 0, y: 0, w: 6, h: 5, minW: 3, minH: 4, maxW: 12, maxH: 12 },
      { i: "collections-1", x: 6, y: 0, w: 6, h: 5, minW: 3, minH: 2, maxW: 12, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 5, w: 12, h: 5, minW: 4, minH: 4, maxW: 12, maxH: 12 },
    ],
    md: [
      { i: "favorites-1", x: 0, y: 0, w: 5, h: 5, minW: 3, minH: 4, maxW: 10, maxH: 12 },
      { i: "collections-1", x: 5, y: 0, w: 5, h: 5, minW: 3, minH: 2, maxW: 10, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 5, w: 10, h: 5, minW: 4, minH: 4, maxW: 10, maxH: 12 },
    ],
    sm: [
      { i: "favorites-1", x: 0, y: 0, w: 1, h: 5, minW: 1, minH: 4, maxW: 1, maxH: 12 },
      { i: "collections-1", x: 0, y: 5, w: 1, h: 5, minW: 1, minH: 2, maxW: 1, maxH: 8 },
      { i: "recent-assets-1", x: 0, y: 10, w: 1, h: 5, minW: 1, minH: 4, maxW: 1, maxH: 12 },
    ],
  },
};

const STORAGE_KEY = "dashboard-layout";
const CURRENT_VERSION = 6; // Bumped version for preset tracking

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

// Convert API layout to frontend layout format
export const convertApiLayoutToFrontend = (apiLayout: {
  layoutVersion: number;
  widgets: Array<{ id: string; type: string; config?: Record<string, unknown> }>;
  layouts: { lg: LayoutItem[]; md: LayoutItem[]; sm: LayoutItem[] };
  updatedAt?: string;
}): DashboardLayout => {
  return {
    version: apiLayout.layoutVersion,
    layoutVersion: apiLayout.layoutVersion,
    widgets: apiLayout.widgets.map((w) => ({
      id: w.id,
      type: w.type as WidgetType,
      ...(w.config && { config: w.config as unknown as CollectionsWidgetConfig }),
    })),
    layouts: apiLayout.layouts,
    updatedAt: apiLayout.updatedAt,
  };
};

// Convert frontend layout to API format
export const convertFrontendLayoutToApi = (layout: DashboardLayout) => {
  return {
    widgets: layout.widgets.map((w) => ({
      id: w.id,
      type: w.type,
      config: w.config || {},
    })),
    layouts: layout.layouts,
  };
};

interface DashboardStore extends DashboardState, DashboardActions {
  // API sync state
  isSyncing: boolean;
  lastSyncError: string | null;
  setIsSyncing: (syncing: boolean) => void;
  setLastSyncError: (error: string | null) => void;
  // Pending changes for debounced save
  hasPendingChanges: boolean;
  setHasPendingChanges: (pending: boolean) => void;
  // Active preset tracking
  activePresetId: string | null;
  activePresetName: string | null;
  setActivePreset: (presetId: string | null, presetName: string | null) => void;
}

export const useDashboardStore = create<DashboardStore>()(
  persist(
    (set, get) => ({
      // Initial state
      layout: DEFAULT_LAYOUT,
      isEditMode: false,
      expandedWidgetId: null,
      isWidgetSelectorOpen: false,
      // API sync state
      isSyncing: false,
      lastSyncError: null,
      hasPendingChanges: false,
      // Active preset tracking
      activePresetId: null,
      activePresetName: null,

      // Actions
      setLayout: (layout) => {
        set({ layout, hasPendingChanges: true });
      },

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
          hasPendingChanges: true,
        });
      },

      addWidget: (type) => {
        const { layout } = get();
        const widgetDef = WIDGET_DEFINITIONS[type];
        const widgetId = generateWidgetId(type);

        // Create new widget instance with default config if available
        const newWidget: WidgetInstance = {
          id: widgetId,
          type,
          ...(widgetDef.defaultConfig && { config: widgetDef.defaultConfig }),
        };

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
          hasPendingChanges: true,
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
          hasPendingChanges: true,
        });
      },

      updateWidgetConfig: (widgetId, config) => {
        const { layout } = get();

        set({
          layout: {
            ...layout,
            widgets: layout.widgets.map((w) => (w.id === widgetId ? { ...w, config } : w)),
          },
          hasPendingChanges: true,
        });
      },

      resetToDefault: () => {
        set({ layout: DEFAULT_LAYOUT, hasPendingChanges: true });
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
        // Layout is automatically saved by persist middleware for localStorage
        // API sync is handled by the useDashboardSync hook
        set({ hasPendingChanges: false });
      },

      loadLayout: () => {
        // Layout is automatically loaded by persist middleware
        // API sync is handled by the useDashboardSync hook
      },

      // API sync actions
      setIsSyncing: (syncing) => set({ isSyncing: syncing }),
      setLastSyncError: (error) => set({ lastSyncError: error }),
      setHasPendingChanges: (pending) => set({ hasPendingChanges: pending }),
      // Active preset action
      setActivePreset: (presetId, presetName) =>
        set({ activePresetId: presetId, activePresetName: presetName }),
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
            isSyncing: false,
            lastSyncError: null,
            hasPendingChanges: false,
            activePresetId: null,
            activePresetName: null,
          };
        }
        return persistedState as DashboardStore;
      },
      partialize: (state) => ({
        layout: state.layout,
        activePresetId: state.activePresetId,
        activePresetName: state.activePresetName,
      }),
    }
  )
);

// Selectors
export const useDashboardLayout = () => useDashboardStore((state) => state.layout);
export const useExpandedWidget = () => useDashboardStore((state) => state.expandedWidgetId);
export const useWidgetSelectorOpen = () => useDashboardStore((state) => state.isWidgetSelectorOpen);
export const useActivePresetId = () => useDashboardStore((state) => state.activePresetId);
export const useActivePresetName = () => useDashboardStore((state) => state.activePresetName);

// Use useShallow to prevent infinite loops when returning objects from selectors
export const useDashboardSyncState = () =>
  useDashboardStore(
    useShallow((state) => ({
      isSyncing: state.isSyncing,
      lastSyncError: state.lastSyncError,
      hasPendingChanges: state.hasPendingChanges,
    }))
  );

export const useDashboardActions = () => {
  // Use individual selectors to get stable function references
  // This prevents creating a new object on every render
  const setLayout = useDashboardStore((state) => state.setLayout);
  const updateLayoutItem = useDashboardStore((state) => state.updateLayoutItem);
  const addWidget = useDashboardStore((state) => state.addWidget);
  const removeWidget = useDashboardStore((state) => state.removeWidget);
  const updateWidgetConfig = useDashboardStore((state) => state.updateWidgetConfig);
  const resetToDefault = useDashboardStore((state) => state.resetToDefault);
  const setExpandedWidget = useDashboardStore((state) => state.setExpandedWidget);
  const toggleWidgetSelector = useDashboardStore((state) => state.toggleWidgetSelector);
  const setWidgetSelectorOpen = useDashboardStore((state) => state.setWidgetSelectorOpen);
  const saveLayout = useDashboardStore((state) => state.saveLayout);
  const loadLayout = useDashboardStore((state) => state.loadLayout);
  const setIsSyncing = useDashboardStore((state) => state.setIsSyncing);
  const setLastSyncError = useDashboardStore((state) => state.setLastSyncError);
  const setHasPendingChanges = useDashboardStore((state) => state.setHasPendingChanges);
  const setActivePreset = useDashboardStore((state) => state.setActivePreset);

  return {
    setLayout,
    updateLayoutItem,
    addWidget,
    removeWidget,
    updateWidgetConfig,
    resetToDefault,
    setExpandedWidget,
    toggleWidgetSelector,
    setWidgetSelectorOpen,
    saveLayout,
    loadLayout,
    setIsSyncing,
    setLastSyncError,
    setHasPendingChanges,
    setActivePreset,
  };
};

// Helper to get available widgets (not currently in layout)
// Note: Collections widgets can have multiple instances, but favorites and recent-assets are single-instance
export const useAvailableWidgets = () => {
  const layout = useDashboardLayout();
  const currentTypes = new Set(layout.widgets.map((w) => w.type));

  return Object.values(WIDGET_DEFINITIONS).filter((def) => {
    // Always allow adding collections widgets (multi-instance support)
    if (def.type === "collections") {
      return true;
    }
    // For other widget types, only allow if not already in layout
    return !currentTypes.has(def.type);
  });
};
