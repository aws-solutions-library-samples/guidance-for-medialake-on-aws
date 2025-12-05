import React from "react";
import { Grid } from "@mui/material";
import { Assignment, AutoGraph, CloudUpload } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { StatCard } from "@/components/common/StatCard";

export const Statistics: React.FC = () => {
  const { t } = useTranslation();

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
          title={t("home.stats.assignedTasks")}
          value={stats.tasks}
          subtitle={t("home.stats.activeTasks")}
        />
      </Grid>
      <Grid item xs={12} sm={4}>
        <StatCard
          icon={<AutoGraph />}
          title={t("home.stats.pipelineExecutions")}
          value={stats.pipelines}
          subtitle={t("home.stats.last24Hours")}
        />
      </Grid>
      <Grid item xs={12} sm={4}>
        <StatCard
          icon={<CloudUpload />}
          title={t("home.stats.newAssets")}
          value={stats.newAssets}
          subtitle={t("home.stats.uploadedToday")}
        />
      </Grid>
    </Grid>
  );
};
