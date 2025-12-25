import React from "react";
import { Box, Paper, Alert, Button } from "@mui/material";
import { WidgetHeader } from "./WidgetHeader";
import type { WidgetContainerProps } from "../types";

interface ExtendedWidgetContainerProps extends WidgetContainerProps {
  error?: Error | null;
  onRetry?: () => void;
}

export const WidgetContainer: React.FC<ExtendedWidgetContainerProps> = ({
  widgetId,
  title,
  icon,
  children,
  onExpand,
  onRefresh,
  onRemove,
  isLoading = false,
  error,
  onRetry,
}) => {
  return (
    <Paper
      elevation={0}
      data-widget-id={widgetId}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRadius: 2,
        backgroundColor: "rgba(255, 255, 255, 0.8)",
        backdropFilter: "blur(10px)",
        border: "1px solid",
        borderColor: "divider",
        overflow: "hidden",
        transition: "box-shadow 0.2s ease-in-out",
        "&:hover": {
          boxShadow: 3,
        },
      }}
    >
      <WidgetHeader
        title={title}
        icon={icon}
        onExpand={onExpand}
        onRefresh={onRefresh}
        onRemove={onRemove}
        isLoading={isLoading}
        isDraggable={true}
      />

      <Box
        sx={{
          flex: 1,
          overflow: "auto",
          p: 2,
          minHeight: 0,
        }}
      >
        {error ? (
          <Alert
            severity="error"
            action={
              onRetry && (
                <Button color="inherit" size="small" onClick={onRetry}>
                  Retry
                </Button>
              )
            }
            sx={{ mb: 2 }}
          >
            {error.message || "Failed to load widget data"}
          </Alert>
        ) : (
          children
        )}
      </Box>
    </Paper>
  );
};
