import React from "react";
import { Box, Typography, useTheme, alpha } from "@mui/material";
import { Inbox as InboxIcon } from "@mui/icons-material";

export interface EmptyTableStateProps {
  message?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyTableState: React.FC<EmptyTableStateProps> = ({
  message = "No data available",
  icon,
  action,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        py: 8,
        px: 3,
        minHeight: 300,
        backgroundColor: isDark
          ? alpha(theme.palette.background.paper, 0.2)
          : theme.palette.background.paper,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 80,
          height: 80,
          borderRadius: "50%",
          backgroundColor: alpha(theme.palette.primary.main, 0.1),
          color: theme.palette.primary.main,
          mb: 2,
        }}
      >
        {icon || <InboxIcon sx={{ fontSize: 40 }} />}
      </Box>
      <Typography variant="h6" color="text.secondary" align="center" gutterBottom>
        {message}
      </Typography>
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Box>
  );
};

export default EmptyTableState;
