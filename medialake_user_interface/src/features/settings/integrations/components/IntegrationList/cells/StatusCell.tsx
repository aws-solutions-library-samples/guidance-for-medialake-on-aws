import React from "react";
import { Chip } from "@mui/material";

interface StatusCellProps {
  value: string;
}

export const StatusCell: React.FC<StatusCellProps> = ({ value }) => {
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "active":
        return "success";
      case "error":
        return "error";
      default:
        return "warning";
    }
  };

  return (
    <Chip
      label={value.toUpperCase()}
      color={getStatusColor(value) as any}
      size="small"
    />
  );
};
