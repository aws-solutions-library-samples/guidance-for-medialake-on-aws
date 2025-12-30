import React from "react";
import { Box, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { Row } from "@tanstack/react-table";
import { Integration } from "../types";
import { useTranslation } from "react-i18next";

interface ActionsCellProps {
  row: Row<Integration>;
  onEdit: (id: string, integration: Integration) => void;
  onDelete: (id: string) => void;
}

export const ActionsCell: React.FC<ActionsCellProps> = ({ row, onEdit, onDelete }) => {
  const { t } = useTranslation();
  const integration = row.original;

  return (
    <Box sx={{ display: "flex", gap: 1 }}>
      <IconButton
        size="small"
        onClick={() => onEdit(integration.id, integration)}
        aria-label={t("integrations.actions.edit")}
      >
        <EditIcon />
      </IconButton>
      <IconButton
        size="small"
        onClick={() => onDelete(integration.id)}
        aria-label={t("integrations.actions.delete")}
      >
        <DeleteIcon />
      </IconButton>
    </Box>
  );
};
