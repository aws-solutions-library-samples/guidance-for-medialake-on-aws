import React from "react";
import { Box, Typography, Paper } from "@mui/material";
import MarkdownRenderer from "../common/MarkdownRenderer";
import TabContentContainer from "../common/TabContentContainer";

interface DescriptiveTabProps {
  assetData: any;
}

const DescriptiveTab: React.FC<DescriptiveTabProps> = ({ assetData }) => {
  const structuredRecapResult = assetData?.data?.asset?.StructuredrecapResult;

  if (!structuredRecapResult) {
    return (
      <TabContentContainer>
        <Typography color="text.secondary" sx={{ textAlign: "center" }}>
          No descriptive content available for this asset.
        </Typography>
      </TabContentContainer>
    );
  }

  return (
    <TabContentContainer noPaper>
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
    </TabContentContainer>
  );
};

export default DescriptiveTab;
