import React from "react";
import { Box, IconButton, useTheme, TextField } from "@mui/material";
import { FilterList as FilterListIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";

interface PipelineToolbarProps {
  onFilterChange: (filter: string) => void;
  onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
}

export const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
  onFilterChange,
  onColumnMenuOpen,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
      <TextField
        placeholder="Search pipelines..."
        size="small"
        onChange={(e) => onFilterChange(e.target.value)}
      />
      <IconButton onClick={onColumnMenuOpen}>
        <FilterListIcon />
      </IconButton>
    </Box>
  );
};
