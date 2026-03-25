import React from "react";
import { Panel } from "@xyflow/react";
import { Button } from "@mui/material";
import SaveIcon from "@mui/icons-material/Save";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();

  return (
    <Panel position="top-right">
      <Button
        variant="contained"
        color="primary"
        onClick={onClick}
        startIcon={<SaveIcon />}
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
        {isEditMode
          ? t("pipelines.updatePipeline", "Update Pipeline")
          : t("pipelines.savePipeline", "Save Pipeline")}
      </Button>
    </Panel>
  );
};

export default SavePipelineButton;
