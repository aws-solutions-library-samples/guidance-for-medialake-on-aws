import React, { useCallback } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Typography,
    CircularProgress,
    Alert,
    Box
} from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';

interface PipelineDeleteDialogProps {
    open: boolean;
    pipelineName: string;
    userInput: string;
    onClose: () => void;
    onConfirm: () => void;
    onUserInputChange: (input: string) => void;
    isDeleting: boolean;
}

// Use React.memo to prevent unnecessary re-renders
const PipelineDeleteDialog = React.memo<PipelineDeleteDialogProps>(({
    open,
    pipelineName,
    userInput,
    onClose,
    onConfirm,
    onUserInputChange,
    isDeleting
}) => {
    // Simple validation
    const canDelete = userInput === pipelineName;

    // Memoized handlers to prevent recreating on every render
    const handleClose = useCallback(() => {
        if (!isDeleting) {
            onClose();
        }
    }, [isDeleting, onClose]);

    const handleConfirm = useCallback(() => {
        if (canDelete && !isDeleting) {
            // Close the dialog first
            onClose();

            // Use the browser's native confirm dialog
            setTimeout(() => {
                if (window.confirm(`Are you sure you want to delete pipeline "${pipelineName}"? This action cannot be undone.`)) {
                    // Execute the deletion
                    onConfirm();
                }
            }, 100);
        }
    }, [canDelete, isDeleting, onClose, onConfirm, pipelineName]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        onUserInputChange(e.target.value);
    }, [onUserInputChange]);

    // Handle Enter key press
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && canDelete && !isDeleting) {
            e.preventDefault();
            handleConfirm();
        }
    }, [canDelete, isDeleting, handleConfirm]);

    return (
        <Dialog
            open={open}
            onClose={handleClose}
            maxWidth="sm"
            fullWidth
            // Disable focus management to prevent issues
            disableAutoFocus
            disableEnforceFocus
            disableRestoreFocus
            // Disable backdrop transitions to prevent freezing
            BackdropProps={{
                transitionDuration: 0
            }}
            // Disable slide transition to prevent freezing
            TransitionProps={{
                timeout: 0
            }}
            // Disable scroll lock to prevent freezing
            disableScrollLock
            // Keep mounted to prevent re-rendering issues
            keepMounted
        >
            <DialogTitle>
                Delete Pipeline
            </DialogTitle>
            <DialogContent>
                <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
                    This operation will delete all associated resources. This process may take some time.
                </Alert>

                <Typography variant="body1" gutterBottom>
                    Are you sure you want to delete the pipeline "{pipelineName}"?
                </Typography>

                <Typography variant="body2" color="text.secondary" gutterBottom>
                    To confirm, please type the pipeline name below:
                </Typography>

                <TextField
                    fullWidth
                    value={userInput}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder={pipelineName}
                    disabled={isDeleting}
                    sx={{ mt: 2 }}
                    error={userInput !== '' && userInput !== pipelineName}
                    helperText={userInput !== '' && userInput !== pipelineName ? "Pipeline name doesn't match" : " "}
                />

                {isDeleting && (
                    <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
                        <CircularProgress size={24} sx={{ mr: 2 }} />
                        <Typography variant="body2" color="text.secondary">
                            Deleting pipeline...
                        </Typography>
                    </Box>
                )}
            </DialogContent>
            <DialogActions>
                <Button
                    onClick={handleClose}
                    disabled={isDeleting}
                >
                    Cancel
                </Button>
                <Button
                    onClick={handleConfirm}
                    color="error"
                    disabled={!canDelete || isDeleting}
                    startIcon={isDeleting ? <CircularProgress size={20} /> : null}
                >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                </Button>
            </DialogActions>
        </Dialog>
    );
});

// Add display name for debugging
PipelineDeleteDialog.displayName = 'PipelineDeleteDialog';

export { PipelineDeleteDialog };
