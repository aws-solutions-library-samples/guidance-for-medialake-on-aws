import React from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";

interface PipelineExecutionConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  pipelineName: string;
  selectedCount: number;
  isLoading: boolean;
}

export const PipelineExecutionConfirmDialog: React.FC<PipelineExecutionConfirmDialogProps> = ({
  open,
  onClose,
  onConfirm,
  pipelineName,
  selectedCount,
  isLoading,
}) => {
  const { t } = useTranslation();

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      data-testid="pipeline-execution-confirm-dialog"
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <PlayArrowIcon color="primary" />
          <Typography variant="h6">
            {t("common.batchOperations.pipelineExecution.confirmTitle")}
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2}>
          <Alert severity="info">{t("common.batchOperations.pipelineExecution.confirmInfo")}</Alert>

          <DialogContentText>
            {t("common.batchOperations.pipelineExecution.confirmMessage", {
              count: selectedCount,
              plural: selectedCount !== 1 ? "s" : "",
            })}
          </DialogContentText>

          <Typography variant="body2" color="text.secondary">
            <strong>{t("sidebar.menu.pipelines")}:</strong> {pipelineName}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={onClose}
          disabled={isLoading}
          data-testid="pipeline-execution-cancel-button"
        >
          {t("common.cancel")}
        </Button>
        <Button
          onClick={onConfirm}
          color="primary"
          variant="contained"
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
          data-testid="pipeline-execution-confirm-button"
        >
          {isLoading
            ? t("common.batchOperations.pipelineExecution.executing")
            : t("common.actions.executePipeline")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
