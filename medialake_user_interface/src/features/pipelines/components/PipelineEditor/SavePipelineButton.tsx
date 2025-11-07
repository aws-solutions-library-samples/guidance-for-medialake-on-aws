import React from "react";
import { Panel } from "reactflow";
import { Button } from "@mui/material";
import { FaSave } from "react-icons/fa";

interface SavePipelineButtonProps {
  onClick: () => void;
  isEditMode?: boolean;
  hasChanges?: boolean;
}

const SavePipelineButton: React.FC<SavePipelineButtonProps> = ({
  onClick,
  isEditMode = false,
  hasChanges = true,
}) => {
  return (
    <Panel position="top-right">
      <Button
        variant="contained"
        color="primary"
        onClick={onClick}
        startIcon={<FaSave />}
        disabled={isEditMode && !hasChanges}
        sx={{
          textTransform: "none",
          borderRadius: "8px",
          boxShadow: 2,
          "&:hover": {
            boxShadow: 4,
          },
        }}
      >
        {isEditMode ? "Update Pipeline" : "Save Pipeline"}
      </Button>
    </Panel>
  );
};

export default SavePipelineButton;
