import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
  CircularProgress,
} from "@mui/material";
import { Warning as WarningIcon } from "@mui/icons-material";

interface BulkDeleteDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  selectedCount: number;
  confirmationText: string;
  onConfirmationTextChange: (text: string) => void;
  isLoading: boolean;
}

export const BulkDeleteDialog: React.FC<BulkDeleteDialogProps> = ({
  open,
  onClose,
  onConfirm,
  selectedCount,
  confirmationText,
  onConfirmationTextChange,
  isLoading,
}) => {
  const { t } = useTranslation();
  const isConfirmDisabled = confirmationText !== "DELETE" || isLoading;

  useEffect(() => {
    console.log("BulkDeleteDialog - open prop changed:", open, "selectedCount:", selectedCount);
  }, [open, selectedCount]);

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      data-testid="bulk-delete-dialog"
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <WarningIcon color="error" />
          <Typography variant="h6">{t("common.confirmBulkDelete")}</Typography>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2}>
          <Alert severity="error">
            This action cannot be undone. All selected assets will be permanently deleted.
          </Alert>

          <DialogContentText>
            You are about to delete <strong>{selectedCount}</strong> asset
            {selectedCount !== 1 ? "s" : ""}. This will permanently remove{" "}
            {selectedCount !== 1 ? "them" : "it"} from the system.
          </DialogContentText>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              To confirm, type <strong>DELETE</strong> below:
            </Typography>
            <TextField
              fullWidth
              value={confirmationText}
              onChange={(e) => onConfirmationTextChange(e.target.value)}
              placeholder={t("common.typeDeleteToConfirm")}
              disabled={isLoading}
              autoFocus
              data-testid="bulk-delete-confirmation-input"
              sx={{ mt: 1 }}
            />
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading} data-testid="bulk-delete-cancel-button">
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          disabled={isConfirmDisabled}
          startIcon={isLoading ? <CircularProgress size={20} /> : undefined}
          data-testid="bulk-delete-confirm-button"
        >
          {isLoading ? "Deleting..." : "Delete"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
