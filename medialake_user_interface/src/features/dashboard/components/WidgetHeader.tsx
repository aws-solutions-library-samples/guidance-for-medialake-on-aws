import React from "react";
import { Box, IconButton, Typography, CircularProgress, alpha, useTheme } from "@mui/material";
import {
  OpenInFull as ExpandIcon,
  Refresh as RefreshIcon,
  Close as RemoveIcon,
  DragIndicator as DragIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import type { WidgetHeaderProps } from "../types";

export const WidgetHeader: React.FC<WidgetHeaderProps> = ({
  title,
  icon,
  onExpand,
  onRefresh,
  onRemove,
  isLoading = false,
  isDraggable = true,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Box
      className="widget-drag-handle"
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        px: 2,
        py: 1.5,
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: isDraggable ? "grab" : "default",
        "&:active": {
          cursor: isDraggable ? "grabbing" : "default",
        },
        backgroundColor: alpha(theme.palette.background.default, 0.5),
        backdropFilter: "blur(4px)",
        borderTopLeftRadius: "inherit",
        borderTopRightRadius: "inherit",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        {isDraggable && (
          <DragIcon
            sx={{
              color: "text.secondary",
              fontSize: 20,
              opacity: 0.6,
            }}
          />
        )}
        <Box sx={{ display: "flex", alignItems: "center", color: "primary.main" }}>{icon}</Box>
        <Typography
          variant="subtitle1"
          component="h3"
          sx={{
            fontWeight: 600,
            color: "text.primary",
          }}
        >
          {title}
        </Typography>
      </Box>

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        {isLoading && <CircularProgress size={18} sx={{ mr: 1 }} />}

        {onRefresh && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onRefresh();
            }}
            disabled={isLoading}
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
        )}

        {onExpand && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onExpand();
            }}
            sx={{
              color: "text.secondary",
              "&:hover": {
                color: "primary.main",
                backgroundColor: "action.hover",
              },
            }}
            aria-label={t("dashboard.actions.expand")}
          >
            <ExpandIcon fontSize="small" />
          </IconButton>
        )}

        {onRemove && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            sx={{
              color: "text.secondary",
              "&:hover": {
                color: "error.main",
                backgroundColor: "error.light",
              },
            }}
            aria-label={t("dashboard.actions.remove")}
          >
            <RemoveIcon fontSize="small" />
          </IconButton>
        )}
      </Box>
    </Box>
  );
};
