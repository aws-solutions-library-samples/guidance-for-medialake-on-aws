import React from "react";
import { Box, Typography, Paper, Divider } from "@mui/material";
import MarkdownRenderer from "../common/MarkdownRenderer";
import TabContentContainer from "../common/TabContentContainer";
interface DescriptiveTabProps {
  assetData: any;
}

interface DescriptiveResult {
  result: string;
  prompt_label: string;
  model_id?: string;
  timestamp?: string;
  content_source?: string;
}

const DescriptiveTab: React.FC<DescriptiveTabProps> = ({ assetData }) => {
  const descriptiveData = assetData?.data?.asset?.Metadata?.Descriptive;

  if (!descriptiveData || Object.keys(descriptiveData).length === 0) {
    return (
      <TabContentContainer>
        <Typography color="text.secondary" sx={{ textAlign: "center" }}>
          No descriptive content available for this asset.
        </Typography>
      </TabContentContainer>
    );
  }

  // Convert descriptive data object to array of results
  const results: Array<{ key: string; data: DescriptiveResult }> = Object.entries(
    descriptiveData
  ).map(([key, data]) => ({
    key,
    data: data as DescriptiveResult,
  }));

  return (
    <TabContentContainer noPaper>
      {results.map((item, index) => (
        <Box key={item.key} sx={{ mb: index < results.length - 1 ? 4 : 0 }}>
          <Typography variant="h6" sx={{ mb: 2, color: "primary.main" }}>
            {item.data.prompt_label || item.key}
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
            <MarkdownRenderer content={item.data.result} />
            {item.data.model_id && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", mt: 2, fontStyle: "italic" }}
              >
                Model: {item.data.model_id}
              </Typography>
            )}
          </Paper>
          {index < results.length - 1 && <Divider sx={{ mt: 4 }} />}
        </Box>
      ))}
    </TabContentContainer>
  );
};

export default DescriptiveTab;
