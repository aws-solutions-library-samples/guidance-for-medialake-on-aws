import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import { Delete as DeleteIcon } from "@mui/icons-material";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";

interface PipelineDeleteButtonProps {
  id: string;
  name: string;
  isSystem: boolean;
}

export const PipelineDeleteButton: React.FC<PipelineDeleteButtonProps> = ({
  id,
  name,
  isSystem,
}) => {
  const handleDelete = async () => {
    // Skip if system pipeline
    if (isSystem) {
      return;
    }

    // Use the browser's native confirm dialog directly
    if (
      window.confirm(
        `Are you sure you want to delete pipeline "${name}"? This action cannot be undone.`,
      )
    ) {
      try {
        // Use the proper apiClient instead of direct fetch
        await apiClient.delete(`${API_ENDPOINTS.PIPELINES}/${id}`);

        // Show success message
        alert("Pipeline deleted successfully");
        // Refresh the page
        window.location.reload();
      } catch (error) {
        console.error("Error deleting pipeline:", error);
        // Show error message
        alert(
          `Error deleting pipeline: ${error instanceof Error ? error.message : "Unknown error"}`,
        );
      }
    }
  };

  return (
    <Tooltip title="Delete Pipeline">
      <span>
        <IconButton size="small" onClick={handleDelete} disabled={isSystem}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </span>
    </Tooltip>
  );
};
