/**
 * SummarySection — reusable section header for detail page summary tabs.
 */
import React from "react";
import { Box, Typography } from "@mui/material";

interface SummarySectionProps {
  title: string;
  color: string;
  children: React.ReactNode;
}

const SummarySection: React.FC<SummarySectionProps> = ({ title, color, children }) => (
  <Box sx={{ mb: 3 }}>
    <Typography sx={{ color, fontSize: "0.875rem", fontWeight: 600, mb: 0.5 }}>{title}</Typography>
    <Box sx={{ width: "100%", height: "1px", bgcolor: color, mb: 2 }} />
    {children}
  </Box>
);

export default SummarySection;
