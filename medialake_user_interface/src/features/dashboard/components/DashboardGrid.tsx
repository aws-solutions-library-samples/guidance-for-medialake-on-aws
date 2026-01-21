import React, { useCallback, useState, useRef, useEffect } from "react";
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
import { MyCollectionsWidget } from "./widgets/MyCollectionsWidget";
import { RecentAssetsWidget } from "./widgets/RecentAssetsWidget";
import type { WidgetType, LayoutItem } from "../types";

// Import react-grid-layout styles
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

// Grid configuration
const BREAKPOINTS = { xl: 1600, lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 };
const COLS = { xl: 12, lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 };
const ROW_HEIGHT = 80;
const MARGIN: [number, number] = [16, 16];

// Widget component map
const WIDGET_COMPONENTS: Record<WidgetType, React.FC<{ widgetId: string }>> = {
  favorites: FavoritesWidget,
  "my-collections": MyCollectionsWidget,
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
  const setWidgetSelectorOpen = useDashboardStore((state) => state.setWidgetSelectorOpen);
  const addWidget = useDashboardStore((state) => state.addWidget);
  const resetToDefault = useDashboardStore((state) => state.resetToDefault);

  const availableWidgets = useAvailableWidgets();

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();

    const resizeObserver = new ResizeObserver(updateWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
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

      // Use xl layout for lg if available, otherwise fall back
      const lgLayout = allLayouts.xl || allLayouts.lg || currentLayout;

      setLayout({
        ...layout,
        layouts: {
          lg: convertLayout(lgLayout),
          md: convertLayout(allLayouts.md || currentLayout),
          sm: convertLayout(allLayouts.sm || currentLayout),
        },
      });
    },
    [layout, setLayout]
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

  // Convert our layout format to react-grid-layout format
  const convertToRGLLayout = (items: LayoutItem[]): RGLLayoutItem[] =>
    items.map((item) => {
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

  const responsiveLayouts: ResponsiveLayouts<string> = {
    xl: convertToRGLLayout(layout.layouts.lg), // Use lg layout for xl screens
    lg: convertToRGLLayout(layout.layouts.lg),
    md: convertToRGLLayout(layout.layouts.md),
    sm: convertToRGLLayout(layout.layouts.sm),
  };

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
              <WidgetComponent widgetId={widget.id} />
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
