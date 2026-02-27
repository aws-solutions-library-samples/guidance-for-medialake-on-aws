/**
 * SummaryField — reusable field row for detail page summary tabs.
 * Only renders if the value is defined and non-null.
 */
import React from "react";
import { Box, Typography } from "@mui/material";

interface SummaryFieldProps {
  label: string;
  value: any;
  formatter?: (val: any) => string;
}

const SummaryField: React.FC<SummaryFieldProps> = ({ label, value, formatter }) => {
  if (value === undefined || value === null) return null;

  return (
    <Box sx={{ display: "flex", mb: 1 }}>
      <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
        {label}:
      </Typography>
      <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
        {formatter ? formatter(value) : String(value)}
      </Typography>
    </Box>
  );
};

export default SummaryField;
