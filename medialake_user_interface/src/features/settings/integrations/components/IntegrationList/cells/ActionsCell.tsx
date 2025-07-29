import React from "react";
import { Box, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { Row } from "@tanstack/react-table";
import { Integration } from "../types";

interface ActionsCellProps {
  row: Row<Integration>;
  onEdit: (id: string, integration: Integration) => void;
  onDelete: (id: string) => void;
}

export const ActionsCell: React.FC<ActionsCellProps> = ({
  row,
  onEdit,
  onDelete,
}) => {
  const integration = row.original;

  return (
    <Box sx={{ display: "flex", gap: 1 }}>
      <IconButton
        size="small"
        onClick={() => onEdit(integration.id, integration)}
        aria-label="Edit integration"
      >
        <EditIcon />
      </IconButton>
      <IconButton
        size="small"
        onClick={() => onDelete(integration.id)}
        aria-label="Delete integration"
      >
        <DeleteIcon />
      </IconButton>
    </Box>
  );
};
