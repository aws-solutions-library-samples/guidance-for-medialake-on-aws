import React, { useCallback, useState, useRef, useEffect, useMemo } from "react";
import {
  ResponsiveGridLayout,
  verticalCompactor,
  type Layout,
  type LayoutItem as RGLLayoutItem,
  type ResponsiveLayouts,
} from "react-grid-layout";
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  IconButton,
  Tooltip,
} from "@mui/material";
import { Add as AddIcon, RestartAlt as ResetIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import {
  useDashboardStore,
  useAvailableWidgets,
  WIDGET_DEFINITIONS,
} from "../store/dashboardStore";
import { WidgetSelector } from "./WidgetSelector";
import { DashboardSelector } from "./DashboardSelector";
import { FavoritesWidget } from "./widgets/FavoritesWidget";
import { CollectionsWidget } from "./widgets/CollectionsWidget";
import { CollectionGroupWidget } from "./widgets/CollectionGroupWidget";
import { RecentAssetsWidget } from "./widgets/RecentAssetsWidget";
import type {
  WidgetType,
  LayoutItem,
  CollectionsWidgetConfig,
  CollectionGroupWidgetConfig,
} from "../types";

// Import react-grid-layout styles
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

// Grid configuration
const BREAKPOINTS = { lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 };
const COLS = { lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 };
const ROW_HEIGHT = 80;
const MARGIN: [number, number] = [16, 16];

// Widget component map
const WIDGET_COMPONENTS: Record<
  WidgetType,
  React.FC<{
    widgetId: string;
    config?: CollectionsWidgetConfig | CollectionGroupWidgetConfig;
  }>
> = {
  favorites: FavoritesWidget,
  collections: CollectionsWidget,
  "collection-group": CollectionGroupWidget,
  "recent-assets": RecentAssetsWidget,
};

interface DashboardGridProps {
  className?: string;
  showHeader?: boolean;
}

export const DashboardGrid: React.FC<DashboardGridProps> = ({ className, showHeader = true }) => {
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [containerWidth, setContainerWidth] = useState(1200);
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  const layout = useDashboardStore((state) => state.layout);
  const isWidgetSelectorOpen = useDashboardStore((state) => state.isWidgetSelectorOpen);
  const setLayout = useDashboardStore((state) => state.setLayout);
  const initializeLayout = useDashboardStore((state) => state.initializeLayout);
  const setWidgetSelectorOpen = useDashboardStore((state) => state.setWidgetSelectorOpen);
  const addWidget = useDashboardStore((state) => state.addWidget);
  const resetToDefault = useDashboardStore((state) => state.resetToDefault);

  const availableWidgets = useAvailableWidgets();

  // Track whether the user has interacted with the grid (drag/resize).
  // onLayoutChange fires on mount and on programmatic updates — those should
  // NOT mark the dashboard as having unsaved changes.
  const userInteractedRef = useRef(false);

  // Ref to hold the latest layout for use inside handleLayoutChange without
  // adding it to the callback's dependency array (avoids re-creating the
  // callback on every layout change which would feed back into the grid).
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  // Measure container width with debounce to prevent rapid re-renders during
  // continuous resize (e.g. opening DevTools, dragging window edge).
  useEffect(() => {
    let rafId: number | null = null;

    const updateWidth = () => {
      // Cancel any pending frame to coalesce rapid ResizeObserver callbacks
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (containerRef.current) {
          const newWidth = containerRef.current.offsetWidth;
          // Only update state when the width actually changed to avoid
          // unnecessary re-renders that trigger layout recalculations.
          setContainerWidth((prev) => (prev === newWidth ? prev : newWidth));
        }
      });
    };

    updateWidth();

    const resizeObserver = new ResizeObserver(updateWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
    };
  }, []);

  // Handle layout change from react-grid-layout
  const handleLayoutChange = useCallback(
    (currentLayout: Layout, allLayouts: ResponsiveLayouts<string>) => {
      // Convert react-grid-layout format to our format
      const convertLayout = (rglLayout: Layout): LayoutItem[] =>
        rglLayout.map((item) => ({
          i: item.i,
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h,
          minW: item.minW,
          minH: item.minH,
          maxW: item.maxW,
          maxH: item.maxH,
        }));

      // Use the lg layout directly
      const lgLayout = allLayouts.lg || currentLayout;

      const newLayouts = {
        lg: convertLayout(lgLayout),
        md: convertLayout(allLayouts.md || currentLayout),
        sm: convertLayout(allLayouts.sm || currentLayout),
      };

      // Read the current layout from the ref to avoid depending on `layout`
      // in the dependency array. This prevents re-creating this callback on
      // every store update, which would cause the grid to re-render and fire
      // onLayoutChange again (feedback loop).
      const currentStoreLayout = layoutRef.current;

      // Only update the store if the layout actually changed.
      // react-grid-layout fires onLayoutChange during mount and on programmatic
      // layout updates — those should not mark the dashboard as modified.
      if (JSON.stringify(currentStoreLayout.layouts) !== JSON.stringify(newLayouts)) {
        const updatedLayout = { ...currentStoreLayout, layouts: newLayouts };

        if (userInteractedRef.current) {
          // User dragged or resized a widget — mark as dirty
          setLayout(updatedLayout);
          userInteractedRef.current = false;
        } else {
          // Grid-internal adjustment (mount, compaction, breakpoint change)
          // Update the layout silently without marking pending changes
          initializeLayout(updatedLayout);
        }
      }
    },
    [setLayout, initializeLayout]
  );

  const handleAddWidget = useCallback(
    (widgetType: WidgetType) => {
      addWidget(widgetType);
    },
    [addWidget]
  );

  const handleOpenWidgetSelector = useCallback(() => {
    setWidgetSelectorOpen(true);
  }, [setWidgetSelectorOpen]);

  const handleCloseWidgetSelector = useCallback(() => {
    setWidgetSelectorOpen(false);
  }, [setWidgetSelectorOpen]);

  const handleResetClick = useCallback(() => {
    setResetDialogOpen(true);
  }, []);

  const handleResetConfirm = useCallback(() => {
    resetToDefault();
    setResetDialogOpen(false);
  }, [resetToDefault]);

  const handleResetCancel = useCallback(() => {
    setResetDialogOpen(false);
  }, []);

  // Mark that the user has interacted with the grid via drag or resize.
  // This flag is consumed by handleLayoutChange to decide whether to mark
  // the layout as dirty.
  const handleDragStop = useCallback(() => {
    userInteractedRef.current = true;
  }, []);

  const handleResizeStop = useCallback(() => {
    userInteractedRef.current = true;
  }, []);

  // Convert our layout format to react-grid-layout format
  const convertToRGLLayout = (items: LayoutItem[] | undefined): RGLLayoutItem[] => {
    if (!items || !Array.isArray(items)) {
      return [];
    }
    return items.map((item) => {
      const widgetDef =
        WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"];
      return {
        i: item.i,
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
        minW: item.minW ?? widgetDef.minSize.w,
        minH: item.minH ?? widgetDef.minSize.h,
        maxW: item.maxW ?? widgetDef.maxSize.w,
        maxH: item.maxH ?? widgetDef.maxSize.h,
      };
    });
  };

  // Build per-breakpoint layouts that match the column counts.
  // xs (4 cols) and xxs (2 cols) stack widgets full-width.
  const buildSmallLayout = (items: LayoutItem[] | undefined, cols: number): RGLLayoutItem[] => {
    if (!items || !Array.isArray(items)) return [];
    // Stack all widgets full-width, one after another
    let y = 0;
    return items.map((item) => {
      const widgetDef =
        WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"];
      const entry: RGLLayoutItem = {
        i: item.i,
        x: 0,
        y,
        w: cols,
        h: item.h,
        minW: Math.min(widgetDef.minSize.w, cols),
        minH: widgetDef.minSize.h,
        maxW: cols,
        maxH: widgetDef.maxSize.h,
      };
      y += item.h;
      return entry;
    });
  };

  const responsiveLayouts: ResponsiveLayouts<string> = useMemo(
    () => ({
      lg: convertToRGLLayout(layout.layouts?.lg),
      md: convertToRGLLayout(layout.layouts?.md),
      sm: convertToRGLLayout(layout.layouts?.sm),
      xs: buildSmallLayout(layout.layouts?.sm, COLS.xs),
      xxs: buildSmallLayout(layout.layouts?.sm, COLS.xxs),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [layout.layouts, layout.widgets]
  );

  return (
    <Box className={className} sx={{ width: "100%" }} ref={containerRef}>
      {/* Dashboard Header - conditionally rendered */}
      {showHeader && (
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 2,
            mb: 2,
          }}
        >
          {/* Dashboard Selector on the left */}
          <DashboardSelector />

          {/* Actions on the right */}
          <Box sx={{ display: "flex", gap: 1 }}>
            <Tooltip title={t("dashboard.actions.resetLayout")}>
              <IconButton
                onClick={handleResetClick}
                size="small"
                sx={{
                  color: "text.secondary",
                  "&:hover": {
                    color: "warning.main",
                  },
                }}
              >
                <ResetIcon />
              </IconButton>
            </Tooltip>

            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={handleOpenWidgetSelector}
              disabled={availableWidgets.length === 0}
            >
              {t("dashboard.actions.addWidget")}
            </Button>
          </Box>
        </Box>
      )}

      {/* Responsive Grid Layout */}
      <ResponsiveGridLayout
        className="dashboard-grid"
        layouts={responsiveLayouts}
        breakpoints={BREAKPOINTS}
        cols={COLS}
        rowHeight={ROW_HEIGHT}
        width={containerWidth}
        margin={MARGIN}
        containerPadding={[0, 0]}
        onLayoutChange={handleLayoutChange}
        onDragStop={handleDragStop}
        onResizeStop={handleResizeStop}
        dragConfig={{
          enabled: true,
          handle: ".widget-drag-handle",
        }}
        resizeConfig={{
          enabled: true,
        }}
        compactor={verticalCompactor}
        autoSize={true}
      >
        {layout.widgets.map((widget) => {
          const WidgetComponent = WIDGET_COMPONENTS[widget.type];
          return (
            <div key={widget.id} data-grid-id={widget.id} style={{ height: "100%" }}>
              <WidgetComponent widgetId={widget.id} config={widget.config} />
            </div>
          );
        })}
      </ResponsiveGridLayout>

      {/* Widget Selector Dialog */}
      <WidgetSelector
        isOpen={isWidgetSelectorOpen}
        onClose={handleCloseWidgetSelector}
        availableWidgets={availableWidgets}
        onAddWidget={handleAddWidget}
      />

      {/* Reset Confirmation Dialog */}
      <Dialog
        open={resetDialogOpen}
        onClose={handleResetCancel}
        aria-labelledby="reset-dialog-title"
        aria-describedby="reset-dialog-description"
      >
        <DialogTitle id="reset-dialog-title">{t("dashboard.resetDialog.title")}</DialogTitle>
        <DialogContent>
          <DialogContentText id="reset-dialog-description">
            {t("dashboard.resetDialog.description")}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleResetCancel}>{t("dashboard.resetDialog.cancel")}</Button>
          <Button onClick={handleResetConfirm} color="warning" autoFocus>
            {t("dashboard.resetDialog.confirm")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
