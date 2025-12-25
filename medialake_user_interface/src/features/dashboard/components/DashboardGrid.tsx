import React, { useCallback, useState } from "react";
import GridLayout from "react-grid-layout";
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
import { FavoritesWidget } from "./widgets/FavoritesWidget";
import { MyCollectionsWidget } from "./widgets/MyCollectionsWidget";
import { RecentAssetsWidget } from "./widgets/RecentAssetsWidget";
import type { WidgetType, LayoutItem } from "../types";

// Import react-grid-layout styles
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

// WidthProvider is exported but types don't match - use require with type assertion
// eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-require-imports
const WidthProvider = (require("react-grid-layout") as any).WidthProvider;
const ResponsiveGridLayout = WidthProvider(GridLayout);

// Type for react-grid-layout Layout item
interface RGLLayout {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  maxW?: number;
  minH?: number;
  maxH?: number;
  static?: boolean;
  isDraggable?: boolean;
  isResizable?: boolean;
}

// Grid configuration
const COLS = 12;
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
}

export const DashboardGrid: React.FC<DashboardGridProps> = ({ className }) => {
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const { t } = useTranslation();

  const layout = useDashboardStore((state) => state.layout);
  const isWidgetSelectorOpen = useDashboardStore((state) => state.isWidgetSelectorOpen);
  const setLayout = useDashboardStore((state) => state.setLayout);
  const setWidgetSelectorOpen = useDashboardStore((state) => state.setWidgetSelectorOpen);
  const addWidget = useDashboardStore((state) => state.addWidget);
  const resetToDefault = useDashboardStore((state) => state.resetToDefault);

  const availableWidgets = useAvailableWidgets();

  // Handle layout change from react-grid-layout
  const handleLayoutChange = useCallback(
    (newLayout: RGLLayout[]) => {
      // Convert react-grid-layout format to our format
      const newLayouts = {
        lg: newLayout.map((item) => ({
          i: item.i,
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h,
          minW: item.minW,
          minH: item.minH,
          maxW: item.maxW,
          maxH: item.maxH,
        })) as LayoutItem[],
        md: newLayout.map((item) => ({
          i: item.i,
          x: item.x,
          y: item.y,
          w: Math.min(item.w, 10),
          h: item.h,
          minW: item.minW,
          minH: item.minH,
          maxW: item.maxW ? Math.min(item.maxW, 10) : undefined,
          maxH: item.maxH,
        })) as LayoutItem[],
        sm: newLayout.map((item) => ({
          i: item.i,
          x: 0,
          y: item.y,
          w: 1,
          h: item.h,
          minW: 1,
          minH: item.minH,
          maxW: 1,
          maxH: item.maxH,
        })) as LayoutItem[],
      };

      setLayout({
        ...layout,
        layouts: newLayouts,
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
  const gridLayout: RGLLayout[] = layout.layouts.lg.map((item) => ({
    i: item.i,
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    minW:
      item.minW ??
      WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"].minSize
        .w,
    minH:
      item.minH ??
      WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"].minSize
        .h,
    maxW:
      item.maxW ??
      WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"].maxSize
        .w,
    maxH:
      item.maxH ??
      WIDGET_DEFINITIONS[layout.widgets.find((w) => w.id === item.i)?.type || "favorites"].maxSize
        .h,
  }));

  return (
    <Box className={className} sx={{ width: "100%" }}>
      {/* Dashboard Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 1,
          mb: 2,
        }}
      >
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

      {/* Grid Layout */}
      <ResponsiveGridLayout
        className="dashboard-grid"
        layout={gridLayout}
        cols={COLS}
        rowHeight={ROW_HEIGHT}
        margin={MARGIN}
        containerPadding={[0, 0]}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".widget-drag-handle"
        isResizable={true}
        isDraggable={true}
        useCSSTransforms={true}
        compactType="vertical"
        preventCollision={false}
      >
        {layout.widgets.map((widget) => {
          const WidgetComponent = WIDGET_COMPONENTS[widget.type];
          return (
            <div key={widget.id} data-grid-id={widget.id}>
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
