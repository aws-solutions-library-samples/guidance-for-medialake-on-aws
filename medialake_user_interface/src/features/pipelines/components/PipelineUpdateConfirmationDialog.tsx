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
import WarningIcon from "@mui/icons-material/Warning";

interface PipelineUpdateConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const PipelineUpdateConfirmationDialog: React.FC<
  PipelineUpdateConfirmationDialogProps
> = ({ open, onClose, onConfirm }) => {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Update Pipeline</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", alignItems: "flex-start", mb: 2 }}>
          <WarningIcon color="warning" sx={{ mr: 1, mt: 0.5 }} />
          <Typography variant="body1">
            <strong>Warning:</strong> Updating a pipeline while executions are
            processing might interrupt those executions.
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Are you sure you want to proceed with this update?
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} color="primary" variant="contained">
          Update Pipeline
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PipelineUpdateConfirmationDialog;
