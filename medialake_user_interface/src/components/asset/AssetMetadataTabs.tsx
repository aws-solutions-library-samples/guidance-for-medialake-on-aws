import React from "react";
import { Box, Typography, Grid } from "@mui/material";
import MetadataSection from "../common/MetadataSection";

interface MetadataField {
  label: string;
  value: string | number;
}

interface AssetMetadataTabsProps {
  summary: MetadataField[];
  descriptive: MetadataField[];
  technical: MetadataField[];
  activityLog?: {
    user: string;
    action: string;
    timestamp: string;
  }[];
}

const MetadataContent: React.FC<{ fields: MetadataField[] }> = ({ fields }) => (
  <Grid container spacing={2}>
    {fields.map((field, index) => (
      <Grid item xs={12} sm={6} key={index}>
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">
            {field.label}
          </Typography>
          <Typography variant="body1">{field.value}</Typography>
        </Box>
      </Grid>
    ))}
  </Grid>
);

const ActivityLogContent: React.FC<{
  logs?: AssetMetadataTabsProps["activityLog"];
}> = ({ logs }) => (
  <Box sx={{ mt: 2 }}>
    {logs?.map((log, index) => (
      <Box key={index} sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {log.timestamp}
        </Typography>
        <Typography variant="body1">
          {log.user} - {log.action}
        </Typography>
      </Box>
    ))}
  </Box>
);

const AssetMetadataTabs: React.FC<AssetMetadataTabsProps> = ({
  summary,
  descriptive,
  technical,
  activityLog,
}) => {
  const tabs = [
    {
      label: "Summary",
      content: <MetadataContent fields={summary} />,
    },
    {
      label: "Descriptor Metadata",
      content: <MetadataContent fields={descriptive} />,
    },
    {
      label: "Technical Metadata",
      content: <MetadataContent fields={technical} />,
    },
  ];

  if (activityLog) {
    tabs.push({
      label: "Activity Log",
      content: <ActivityLogContent logs={activityLog} />,
    });
  }

  return (
    <Box sx={{ mt: 3 }}>
      <MetadataSection tabs={tabs} />
    </Box>
  );
};

export default AssetMetadataTabs;
