import React from "react";
import { Box, Typography, Button } from "@mui/material";
import { InboxOutlined as DefaultIcon } from "@mui/icons-material";
import type { EmptyStateProps } from "../types";

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        py: 4,
        px: 2,
        height: "100%",
        minHeight: 150,
      }}
    >
      <Box
        sx={{
          color: "text.secondary",
          mb: 2,
          "& > svg": {
            fontSize: 48,
            opacity: 0.5,
          },
        }}
      >
        {icon || <DefaultIcon />}
      </Box>

      <Typography variant="subtitle1" color="text.primary" sx={{ fontWeight: 500, mb: 0.5 }}>
        {title}
      </Typography>

      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 280 }}>
          {description}
        </Typography>
      )}

      {actionLabel && onAction && (
        <Button variant="outlined" size="small" onClick={onAction} sx={{ mt: 1 }}>
          {actionLabel}
        </Button>
      )}
    </Box>
  );
};
