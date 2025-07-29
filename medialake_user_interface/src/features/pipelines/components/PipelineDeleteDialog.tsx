import React, { useState } from "react";
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

export const PipelineDeleteDialog: React.FC<PipelineDeleteDialogProps> =
  React.memo(
    ({
      open,
      pipelineName,
      userInput,
      onClose,
      onConfirm,
      onUserInputChange,
      isDeleting,
    }) => {
      const canDelete = userInput === pipelineName;

      return (
        <Dialog open={open} onClose={onClose}>
          <DialogTitle>Delete Pipeline</DialogTitle>
          <DialogContent>
            <Typography variant="body1" gutterBottom>
              Are you sure you want to delete the pipeline "{pipelineName}"?
              This action cannot be undone.
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              To confirm, please type the pipeline name below:
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
              Cancel
            </Button>
            <Button
              onClick={onConfirm}
              color="error"
              disabled={!canDelete || isDeleting}
              startIcon={isDeleting ? <CircularProgress size={20} /> : null}
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogActions>
        </Dialog>
      );
    },
  );
