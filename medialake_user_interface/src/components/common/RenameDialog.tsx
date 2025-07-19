import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Box,
  Typography,
} from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { ActionButton } from "./button/ActionButton";

interface RenameDialogProps {
  open: boolean;
  title: string;
  currentName: string;
  onConfirm: (newName: string) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const RenameDialog: React.FC<RenameDialogProps> = ({
  open,
  title,
  currentName,
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  const [newName, setNewName] = useState(currentName);

  useEffect(() => {
    if (open) {
      setNewName(currentName);
    }
  }, [currentName, open]);

  const handleConfirm = () => {
    onConfirm(newName);
    setNewName(currentName);
  };

  const handleCancel = () => {
    setNewName(currentName);
    onCancel();
  };

  return (
    <Dialog
      open={open}
      onClose={handleCancel}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          p: 1,
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          p: 2,
        }}
      >
        <Typography variant="h6">{title}</Typography>
        <IconButton onClick={handleCancel} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ p: 2 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
          {/* <TextField
                        label="Current Name"
                        value={currentName}
                        disabled
                        fullWidth
                    /> */}
          <TextField
            label="New Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            fullWidth
            autoFocus
          />
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <ActionButton
          variant="outlined"
          onClick={handleCancel}
          disabled={isLoading}
        >
          Cancel
        </ActionButton>
        <ActionButton
          variant="contained"
          onClick={handleConfirm}
          loading={isLoading}
        >
          Rename
        </ActionButton>
      </DialogActions>
    </Dialog>
  );
};
