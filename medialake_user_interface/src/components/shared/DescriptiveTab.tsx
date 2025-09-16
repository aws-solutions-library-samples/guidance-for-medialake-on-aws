import React from "react";
import { Box, Typography, Paper } from "@mui/material";
import MarkdownRenderer from "../common/MarkdownRenderer";

interface DescriptiveTabProps {
  assetData: any;
}

const DescriptiveTab: React.FC<DescriptiveTabProps> = ({ assetData }) => {
  const structuredRecapResult = assetData?.data?.asset?.StructuredrecapResult;

  if (!structuredRecapResult) {
    return (
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Typography color="text.secondary">
          No descriptive content available for this asset.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h6" sx={{ mb: 2, color: "primary.main" }}>
        Structured Recap Result
      </Typography>
      <Paper
        sx={{
          p: 3,
          bgcolor: "background.paper",
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 2,
        }}
      >
        <MarkdownRenderer content={structuredRecapResult} />
      </Paper>
    </Box>
  );
};

export default DescriptiveTab;
