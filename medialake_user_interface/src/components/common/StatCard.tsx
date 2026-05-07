import React, { ReactNode } from "react";
import { Paper, Typography, Box, useTheme, alpha } from "@mui/material";
import { motion } from "@/constants";

interface StatCardProps {
  icon: ReactNode;
  title: string;
  value: number;
  subtitle: string;
}

export const StatCard: React.FC<StatCardProps> = ({ icon, title, value, subtitle }) => {
  const theme = useTheme();

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        height: "100%",
        display: "flex",
        alignItems: "center",
        backgroundColor: alpha(theme.palette.background.paper, 0.8),
        backdropFilter: "blur(10px)",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        transition: motion.cardHoverSubtle.transition,
        "&:hover": {
          transform: motion.cardHoverSubtle.transform,
          boxShadow: theme.shadows[2],
        },
      }}
    >
      <Box sx={{ mr: 2, color: "primary.main" }}>{icon}</Box>
      <Box>
        <Typography variant="h6" component="div" sx={{ mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h4" component="div" sx={{ mb: 0.5, fontWeight: "bold" }}>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      </Box>
    </Paper>
  );
};
