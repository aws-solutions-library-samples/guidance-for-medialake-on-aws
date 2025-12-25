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
} from "@mui/material";
import {
  Close as CloseIcon,
  Favorite as FavoriteIcon,
  FolderOpen as CollectionIcon,
  Schedule as RecentIcon,
} from "@mui/icons-material";
import type { WidgetSelectorProps, WidgetType } from "../types";

// Map widget types to icons
const WIDGET_ICONS: Record<WidgetType, React.ReactElement> = {
  favorites: <FavoriteIcon />,
  "my-collections": <CollectionIcon />,
  "recent-assets": <RecentIcon />,
};

export const WidgetSelector: React.FC<WidgetSelectorProps> = ({
  isOpen,
  onClose,
  availableWidgets,
  onAddWidget,
}) => {
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
          backgroundColor: "rgba(255, 255, 255, 0.95)",
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
          Add Widget
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
              All widgets are already on your dashboard
            </Typography>
          </Box>
        ) : (
          <List sx={{ pt: 0 }}>
            {availableWidgets.map((widget) => (
              <ListItem key={widget.type} disablePadding sx={{ mb: 1 }}>
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
                    secondary={widget.description}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
    </Dialog>
  );
};
