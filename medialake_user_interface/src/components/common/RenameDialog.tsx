import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  CircularProgress
} from '@mui/material';

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
  isLoading = false
}) => {
  const [newName, setNewName] = useState(currentName);
  const [error, setError] = useState('');

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setNewName(currentName);
      setError('');
    }
  }, [open, currentName]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNewName(e.target.value);
    if (!e.target.value.trim()) {
      setError('Name cannot be empty');
    } else {
      setError('');
    }
  };

  const handleConfirm = () => {
    if (!newName.trim()) {
      setError('Name cannot be empty');
      return;
    }
    onConfirm(newName);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !error && !isLoading) {
      handleConfirm();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      aria-labelledby="rename-dialog-title"
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle id="rename-dialog-title">{title}</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          label="New Name"
          type="text"
          fullWidth
          value={newName}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          error={!!error}
          helperText={error}
          disabled={isLoading}
          variant="outlined"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button 
          onClick={handleConfirm} 
          color="primary" 
          variant="contained"
          disabled={!!error || isLoading}
          startIcon={isLoading ? <CircularProgress size={16} color="inherit" /> : null}
        >
          Rename
        </Button>
      </DialogActions>
    </Dialog>
  );
};
