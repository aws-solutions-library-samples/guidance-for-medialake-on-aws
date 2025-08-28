import React from "react";
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  useTheme,
} from "@mui/material";
import { useDirection } from "../../../contexts/DirectionContext";

export interface FilterOption {
  value: string;
  label: string;
}

export interface FilterConfig {
  key: string;
  label: string;
  value: string;
  options: FilterOption[];
}

interface PageFiltersProps {
  filters: FilterConfig[];
  onFilterChange: (key: string, value: string) => void;
}
const PageFilters: React.FC<PageFiltersProps> = ({
  filters,
  onFilterChange,
}) => {
  const theme = useTheme();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  if (filters.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        mb: 3,
        display: "flex",
        alignItems: "center",
        gap: 2,
        flexDirection: isRTL ? "row-reverse" : "row",
        justifyContent: isRTL ? "flex-start" : "flex-start",
      }}
    >
      {filters.map((filter) => (
        <FormControl
          key={filter.key}
          size="small"
          sx={{
            minWidth: 120,
            "& .MuiOutlinedInput-root": {
              borderRadius: "8px",
              backgroundColor: theme.palette.background.paper,
            },
          }}
        >
          <InputLabel>{filter.label}</InputLabel>
          <Select
            value={filter.value}
            label={filter.label}
            onChange={(e) => onFilterChange(filter.key, e.target.value)}
          >
            {filter.options.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      ))}
    </Box>
  );
};

export default PageFilters;
