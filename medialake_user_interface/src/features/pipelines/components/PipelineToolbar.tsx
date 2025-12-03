import React from "react";
import { Box, IconButton, TextField } from "@mui/material";
import { FilterList as FilterListIcon } from "@mui/icons-material";

interface PipelineToolbarProps {
  onFilterChange: (filter: string) => void;
  onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
}

export const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
  onFilterChange,
  onColumnMenuOpen,
}) => {
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
