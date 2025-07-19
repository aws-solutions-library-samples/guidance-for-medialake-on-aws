import React from "react";
import { Grid } from "@mui/material";
import { Assignment, AutoGraph, CloudUpload } from "@mui/icons-material";
import { StatCard } from "@/components/common/StatCard";

export const Statistics: React.FC = () => {
  // In a real app, these would come from an API
  const stats = {
    tasks: 12,
    pipelines: 8,
    newAssets: 156,
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} sm={4}>
        <StatCard
          icon={<Assignment />}
          title="Assigned Tasks"
          value={stats.tasks}
          subtitle="Active tasks"
        />
      </Grid>
      <Grid item xs={12} sm={4}>
        <StatCard
          icon={<AutoGraph />}
          title="Pipeline Executions"
          value={stats.pipelines}
          subtitle="Last 24 hours"
        />
      </Grid>
      <Grid item xs={12} sm={4}>
        <StatCard
          icon={<CloudUpload />}
          title="New Assets"
          value={stats.newAssets}
          subtitle="Added in 24 hours"
        />
      </Grid>
    </Grid>
  );
};
