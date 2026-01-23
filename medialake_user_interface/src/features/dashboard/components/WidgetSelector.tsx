import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Typography,
  Box,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Close as CloseIcon,
  Favorite as FavoriteIcon,
  FolderOpen as CollectionIcon,
  Schedule as RecentIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import type { WidgetSelectorProps, WidgetType } from "../types";

// Map widget types to icons
const WIDGET_ICONS: Record<WidgetType, React.ReactElement> = {
  favorites: <FavoriteIcon />,
  collections: <CollectionIcon />,
  "recent-assets": <RecentIcon />,
};

export const WidgetSelector: React.FC<WidgetSelectorProps> = ({
  isOpen,
  onClose,
  availableWidgets,
  onAddWidget,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const handleAddWidget = (widgetType: WidgetType) => {
    onAddWidget(widgetType);
    onClose();
  };

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          backgroundColor: alpha(theme.palette.background.paper, 0.95),
          backdropFilter: "blur(10px)",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pb: 1,
        }}
      >
        <Typography variant="h6" component="span">
          {t("dashboard.widgetSelector.title", "Add Widget")}
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          aria-label="Close"
          sx={{ color: "text.secondary" }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 0 }}>
        {availableWidgets.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: "center",
            }}
          >
            <Typography color="text.secondary">
              {t("dashboard.widgetSelector.allAdded", "All widgets are already on your dashboard")}
            </Typography>
          </Box>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, px: 1 }}>
              {t(
                "dashboard.widgetSelector.collectionsHint",
                "Tip: You can add multiple Collections widgets with different configurations"
              )}
            </Typography>
            <List sx={{ pt: 0 }}>
              {availableWidgets.map((widget) => (
                <ListItem key={`${widget.type}-${Date.now()}`} disablePadding sx={{ mb: 1 }}>
                  <ListItemButton
                    onClick={() => handleAddWidget(widget.type)}
                    sx={{
                      borderRadius: 2,
                      border: "1px solid",
                      borderColor: "divider",
                      "&:hover": {
                        backgroundColor: "action.hover",
                        borderColor: "primary.main",
                      },
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        minWidth: 48,
                        color: "primary.main",
                      }}
                    >
                      {WIDGET_ICONS[widget.type]}
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Typography variant="subtitle1" fontWeight={500}>
                          {widget.title}
                        </Typography>
                      }
                      secondary={
                        <>
                          {widget.description}
                          {widget.type === "collections" && (
                            <Typography
                              component="span"
                              variant="caption"
                              display="block"
                              sx={{ mt: 0.5, fontStyle: "italic", color: "primary.main" }}
                            >
                              {t(
                                "dashboard.widgetSelector.multiInstance",
                                "Can be added multiple times"
                              )}
                            </Typography>
                          )}
                        </>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
