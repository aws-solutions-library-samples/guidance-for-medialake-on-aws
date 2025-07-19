import React from "react";
import { Box } from "@mui/material";

interface FilterOperationsProps {
  filterComponent?: React.ReactNode;
}

const FilterOperations: React.FC<FilterOperationsProps> = ({
  filterComponent,
}) => {
  return <Box sx={{ height: "100%", overflow: "auto" }}>{filterComponent}</Box>;
};

export default FilterOperations;
