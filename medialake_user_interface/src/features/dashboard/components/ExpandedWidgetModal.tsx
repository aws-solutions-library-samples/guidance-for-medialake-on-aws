import React, { useCallback } from "react";
import { Dialog, DialogContent, IconButton, Typography, Box, alpha, useTheme } from "@mui/material";
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Favorite as FavoriteIcon,
  FolderOpen as CollectionIcon,
  Schedule as RecentIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { useDashboardStore, WIDGET_DEFINITIONS } from "../store/dashboardStore";
import { FavoritesWidget } from "./widgets/FavoritesWidget";
import { CollectionsWidget } from "./widgets/CollectionsWidget";
import { RecentAssetsWidget } from "./widgets/RecentAssetsWidget";
import type { WidgetType, CollectionsWidgetConfig } from "../types";

// Widget component map
const WIDGET_COMPONENTS: Record<
  WidgetType,
  React.FC<{ widgetId: string; isExpanded?: boolean; config?: CollectionsWidgetConfig }>
> = {
  favorites: FavoritesWidget,
  collections: CollectionsWidget,
  "recent-assets": RecentAssetsWidget,
};

// Widget icon map
const WIDGET_ICONS: Record<WidgetType, React.ReactNode> = {
  favorites: <FavoriteIcon />,
  collections: <CollectionIcon />,
  "recent-assets": <RecentIcon />,
};

export const ExpandedWidgetModal: React.FC = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const expandedWidgetId = useDashboardStore((state) => state.expandedWidgetId);
  const layout = useDashboardStore((state) => state.layout);
  const setExpandedWidget = useDashboardStore((state) => state.setExpandedWidget);

  const handleClose = () => {
    setExpandedWidget(null);
  };

  const handleRefresh = useCallback(() => {
    // Invalidate relevant queries based on widget type
    const widget = layout.widgets.find((w) => w.id === expandedWidgetId);
    if (widget) {
      if (widget.type === "favorites") {
        queryClient.invalidateQueries({ queryKey: ["favorites"] });
      } else if (widget.type === "collections") {
        queryClient.invalidateQueries({ queryKey: ["collections"] });
      } else if (widget.type === "recent-assets") {
        queryClient.invalidateQueries({ queryKey: ["search"] });
      }
    }
  }, [expandedWidgetId, layout.widgets, queryClient]);

  // Find the widget instance
  const widget = layout.widgets.find((w) => w.id === expandedWidgetId);

  if (!widget) {
    return null;
  }

  const widgetDef = WIDGET_DEFINITIONS[widget.type];
  const WidgetComponent = WIDGET_COMPONENTS[widget.type];
  const WidgetIcon = WIDGET_ICONS[widget.type];

  return (
    <Dialog
      open={!!expandedWidgetId}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: "80vh",
          maxHeight: "80vh",
          borderRadius: 2,
          backgroundColor: alpha(theme.palette.background.paper, 0.98),
          backdropFilter: "blur(10px)",
        },
      }}
    >
      {/* Header styled like WidgetHeader */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2,
          py: 1.5,
          borderBottom: "1px solid",
          borderColor: "divider",
          backgroundColor: alpha(theme.palette.background.default, 0.5),
          backdropFilter: "blur(4px)",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "center", color: "primary.main" }}>
            {WidgetIcon}
          </Box>
          <Typography
            variant="subtitle1"
            component="h3"
            sx={{
              fontWeight: 600,
              color: "text.primary",
            }}
          >
            {widgetDef.title}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <IconButton
            size="small"
            onClick={handleRefresh}
            sx={{
              color: "text.secondary",
              "&:hover": {
                color: "primary.main",
                backgroundColor: "action.hover",
              },
            }}
            aria-label={t("dashboard.actions.refresh")}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>

          <IconButton
            size="small"
            onClick={handleClose}
            sx={{
              color: "text.secondary",
              "&:hover": {
                color: "error.main",
                backgroundColor: alpha(theme.palette.error.main, 0.1),
              },
            }}
            aria-label={t("common.close")}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      <DialogContent sx={{ p: 0, overflow: "hidden" }}>
        <Box sx={{ height: "100%", minHeight: 400 }}>
          <WidgetComponent widgetId={widget.id} isExpanded={true} config={widget.config} />
        </Box>
      </DialogContent>
    </Dialog>
  );
};
