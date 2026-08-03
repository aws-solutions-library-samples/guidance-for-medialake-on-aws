import React, { useEffect, useState } from "react";
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
  Checkbox,
  CircularProgress,
  FormControlLabel,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";

export interface PipelineExecutionOptions {
  /**
   * Submit the selected assets as a single execution group and package the
   * pipeline's output artifacts into a downloadable zip when every
   * execution finishes.
   */
  packageOutputs: boolean;
}

interface PipelineExecutionConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (options: PipelineExecutionOptions) => void;
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
  const [packageOutputs, setPackageOutputs] = useState(false);

  // Fresh state each time the dialog opens
  useEffect(() => {
    if (open) {
      setPackageOutputs(false);
    }
  }, [open]);

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

          <Box>
            <FormControlLabel
              control={
                <Checkbox
                  checked={packageOutputs}
                  onChange={(event) => setPackageOutputs(event.target.checked)}
                  disabled={isLoading}
                  data-testid="pipeline-execution-package-outputs-checkbox"
                />
              }
              label={t("common.batchOperations.pipelineExecution.packageOutputs")}
            />
            <Typography variant="caption" color="text.secondary" display="block" sx={{ pl: 4 }}>
              {t("common.batchOperations.pipelineExecution.packageOutputsHint")}
            </Typography>
          </Box>
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
          onClick={() => onConfirm({ packageOutputs })}
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
