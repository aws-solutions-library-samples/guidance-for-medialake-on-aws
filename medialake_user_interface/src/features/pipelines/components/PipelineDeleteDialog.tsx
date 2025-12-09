import React from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  CircularProgress,
} from "@mui/material";

interface PipelineDeleteDialogProps {
  open: boolean;
  pipelineName: string;
  userInput: string;
  onClose: () => void;
  onConfirm: () => void;
  onUserInputChange: (input: string) => void;
  isDeleting: boolean;
}

export const PipelineDeleteDialog: React.FC<PipelineDeleteDialogProps> = React.memo(
  ({ open, pipelineName, userInput, onClose, onConfirm, onUserInputChange, isDeleting }) => {
    const { t } = useTranslation();
    const canDelete = userInput === pipelineName;

    return (
      <Dialog open={open} onClose={onClose}>
        <DialogTitle>{t("pipelines.dialogs.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Typography variant="body1" gutterBottom>
            {t("pipelines.dialogs.deleteConfirmation", { pipelineName })}
          </Typography>
          <Typography variant="body1" gutterBottom>
            {t("pipelines.dialogs.deleteWarning")}
          </Typography>
          <TextField
            autoFocus
            fullWidth
            value={userInput}
            onChange={(e) => onUserInputChange(e.target.value)}
            placeholder={pipelineName}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={isDeleting}>
            {t("common.actions.cancel")}
          </Button>
          <Button
            onClick={onConfirm}
            color="error"
            disabled={!canDelete || isDeleting}
            startIcon={isDeleting ? <CircularProgress size={20} /> : null}
          >
            {isDeleting ? t("common.actions.deleting") : t("common.actions.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    );
  }
);
