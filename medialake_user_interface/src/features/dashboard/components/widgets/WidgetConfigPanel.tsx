import React from "react";
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  Paper,
  Divider,
} from "@mui/material";
import { ArrowUpward as AscIcon, ArrowDownward as DescIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import type { CollectionsWidgetConfig, CollectionViewType, SortBy, SortOrder } from "../../types";

interface WidgetConfigPanelProps {
  config: CollectionsWidgetConfig;
  onChange: (config: CollectionsWidgetConfig) => void;
}

export const WidgetConfigPanel: React.FC<WidgetConfigPanelProps> = ({ config, onChange }) => {
  const { t } = useTranslation();

  const handleViewTypeChange = (event: any) => {
    const newViewType = event.target.value as CollectionViewType;
    onChange({
      ...config,
      viewType: newViewType,
    });
  };

  const handleSortByChange = (event: any) => {
    const newSortBy = event.target.value as SortBy;
    onChange({
      ...config,
      sorting: {
        ...config.sorting,
        sortBy: newSortBy,
      },
    });
  };

  const handleSortOrderChange = (
    _event: React.MouseEvent<HTMLElement>,
    newSortOrder: SortOrder | null
  ) => {
    if (newSortOrder !== null) {
      onChange({
        ...config,
        sorting: {
          ...config.sorting,
          sortOrder: newSortOrder,
        },
      });
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        mb: 2,
        backgroundColor: "background.default",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
      }}
    >
      <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
        {t("dashboard.widgets.collections.configTitle", "Widget Configuration")}
      </Typography>

      {/* View Type Selection */}
      <FormControl fullWidth size="small" sx={{ mb: 2 }}>
        <InputLabel id="view-type-label">
          {t("dashboard.widgets.collections.viewType", "View Type")}
        </InputLabel>
        <Select
          labelId="view-type-label"
          id="view-type-select"
          value={config.viewType}
          label={t("dashboard.widgets.collections.viewType", "View Type")}
          onChange={handleViewTypeChange}
        >
          <MenuItem value="all">
            {t("dashboard.widgets.collections.viewTypes.all", "All Collections")}
          </MenuItem>
          <MenuItem value="public">
            {t("dashboard.widgets.collections.viewTypes.public", "Public Collections")}
          </MenuItem>
          <MenuItem value="private">
            {t("dashboard.widgets.collections.viewTypes.private", "Private Collections")}
          </MenuItem>
          <MenuItem value="my-collections">
            {t("dashboard.widgets.collections.viewTypes.myCollections", "My Collections")}
          </MenuItem>
          <MenuItem value="shared-with-me">
            {t("dashboard.widgets.collections.viewTypes.sharedWithMe", "Shared With Me")}
          </MenuItem>
          <MenuItem value="my-shared">
            {t("dashboard.widgets.collections.viewTypes.myShared", "My Shared Collections")}
          </MenuItem>
        </Select>
      </FormControl>

      <Divider sx={{ my: 2 }} />

      {/* Sorting Configuration */}
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: "block" }}>
        {t("dashboard.widgets.collections.sortingTitle", "Sorting")}
      </Typography>

      {/* Sort By Selection */}
      <FormControl fullWidth size="small" sx={{ mb: 2 }}>
        <InputLabel id="sort-by-label">
          {t("dashboard.widgets.collections.sortBy", "Sort By")}
        </InputLabel>
        <Select
          labelId="sort-by-label"
          id="sort-by-select"
          value={config.sorting.sortBy}
          label={t("dashboard.widgets.collections.sortBy", "Sort By")}
          onChange={handleSortByChange}
        >
          <MenuItem value="name">
            {t("dashboard.widgets.collections.sortOptions.name", "Name")}
          </MenuItem>
          <MenuItem value="createdAt">
            {t("dashboard.widgets.collections.sortOptions.createdAt", "Created Date")}
          </MenuItem>
          <MenuItem value="updatedAt">
            {t("dashboard.widgets.collections.sortOptions.updatedAt", "Updated Date")}
          </MenuItem>
        </Select>
      </FormControl>

      {/* Sort Order Toggle */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {t("dashboard.widgets.collections.sortOrder", "Order")}:
        </Typography>
        <ToggleButtonGroup
          value={config.sorting.sortOrder}
          exclusive
          onChange={handleSortOrderChange}
          size="small"
          aria-label={t("dashboard.widgets.collections.sortOrder", "Sort Order")}
        >
          <ToggleButton value="asc" aria-label="ascending">
            <AscIcon fontSize="small" sx={{ mr: 0.5 }} />
            {t("dashboard.widgets.collections.ascending", "Asc")}
          </ToggleButton>
          <ToggleButton value="desc" aria-label="descending">
            <DescIcon fontSize="small" sx={{ mr: 0.5 }} />
            {t("dashboard.widgets.collections.descending", "Desc")}
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>
    </Paper>
  );
};
