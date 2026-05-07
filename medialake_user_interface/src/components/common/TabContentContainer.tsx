import React from "react";
import { Box, Paper, alpha, useTheme } from "@mui/material";

interface TabContentContainerProps {
  children: React.ReactNode;
  noPaper?: boolean;
}

const TabContentContainer: React.FC<TabContentContainerProps> = ({ children, noPaper = false }) => {
  const theme = useTheme();

  if (noPaper) {
    return <Box sx={{ p: 2 }}>{children}</Box>;
  }

  return (
    <Box sx={{ p: 2 }}>
      <Paper
        elevation={0}
        sx={{
          p: 2,
          border: `1px solid ${alpha(theme.palette.divider, 0.05)}`,
          backgroundColor: alpha(theme.palette.background.paper, 0.7),
        }}
      >
        {children}
      </Paper>
    </Box>
  );
};

export default TabContentContainer;
