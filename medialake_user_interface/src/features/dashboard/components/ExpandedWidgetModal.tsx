import React from "react";
import { Dialog, DialogTitle, DialogContent, IconButton, Typography, Box } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { useDashboardStore, WIDGET_DEFINITIONS } from "../store/dashboardStore";
import { FavoritesWidget } from "./widgets/FavoritesWidget";
import { MyCollectionsWidget } from "./widgets/MyCollectionsWidget";
import { RecentAssetsWidget } from "./widgets/RecentAssetsWidget";
import type { WidgetType } from "../types";

// Widget component map
const WIDGET_COMPONENTS: Record<WidgetType, React.FC<{ widgetId: string }>> = {
  favorites: FavoritesWidget,
  "my-collections": MyCollectionsWidget,
  "recent-assets": RecentAssetsWidget,
};

export const ExpandedWidgetModal: React.FC = () => {
  const expandedWidgetId = useDashboardStore((state) => state.expandedWidgetId);
  const layout = useDashboardStore((state) => state.layout);
  const setExpandedWidget = useDashboardStore((state) => state.setExpandedWidget);

  const handleClose = () => {
    setExpandedWidget(null);
  };

  // Find the widget instance
  const widget = layout.widgets.find((w) => w.id === expandedWidgetId);

  if (!widget) {
    return null;
  }

  const widgetDef = WIDGET_DEFINITIONS[widget.type];
  const WidgetComponent = WIDGET_COMPONENTS[widget.type];

  // Create a modified widget that doesn't show expand/remove buttons
  const ExpandedWidgetContent: React.FC = () => {
    // Render widget content without the container (we'll use the dialog as container)
    return (
      <Box sx={{ height: "100%", minHeight: 400 }}>
        <WidgetComponent widgetId={widget.id} />
      </Box>
    );
  };

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
          backgroundColor: "rgba(255, 255, 255, 0.98)",
          backdropFilter: "blur(10px)",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "divider",
          pb: 2,
        }}
      >
        <Typography variant="h6" component="span">
          {widgetDef.title}
        </Typography>
        <IconButton
          onClick={handleClose}
          size="small"
          aria-label="Close"
          sx={{ color: "text.secondary" }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, overflow: "hidden" }}>
        <ExpandedWidgetContent />
      </DialogContent>
    </Dialog>
  );
};
