import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import WarningIcon from "@mui/icons-material/Warning";

interface PipelineUpdateConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const PipelineUpdateConfirmationDialog: React.FC<PipelineUpdateConfirmationDialogProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>{t("pipelines.editor.updatePipeline")}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", alignItems: "flex-start", mb: 2 }}>
          <WarningIcon color="warning" sx={{ mr: 1, mt: 0.5 }} />
          <Typography variant="body1">{t("pipelines.editor.updateWarning")}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Are you sure you want to proceed with this update?
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={onConfirm} color="primary" variant="contained">
          {t("pipelines.editor.update")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PipelineUpdateConfirmationDialog;
