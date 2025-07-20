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
import { Warning as WarningIcon } from "@mui/icons-material";

interface DismissConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  notificationMessage: string;
}

export const DismissConfirmationDialog: React.FC<
  DismissConfirmationDialogProps
> = ({ open, onClose, onConfirm, notificationMessage }) => {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="dismiss-confirmation-title"
    >
      <DialogTitle id="dismiss-confirmation-title">
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <WarningIcon color="warning" />
          Dismiss Download Notification
        </Box>
      </DialogTitle>

      <DialogContent>
        <Typography variant="body1" gutterBottom>
          Are you sure you want to dismiss this download? You will lose access
          to the download links.
        </Typography>

        <Box sx={{ mt: 2, p: 2, bgcolor: "grey.100", borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Notification:</strong> {notificationMessage}
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Once dismissed, you'll need to restart the download process to access
          these files again.
        </Typography>
      </DialogContent>

      <DialogActions sx={{ p: 3, gap: 1 }}>
        <Button onClick={onClose} variant="outlined" color="primary">
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color="warning"
          autoFocus
        >
          Dismiss Notification
        </Button>
      </DialogActions>
    </Dialog>
  );
};
