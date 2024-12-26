import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Button,
    TextField,
    CircularProgress,
} from '@mui/material';
import { useTranslation } from 'react-i18next';

interface PipelineDeleteDialogProps {
    open: boolean;
    pipelineName: string;
    userInput: string;
    isDeleting: boolean;
    onClose: () => void;
    onConfirm: () => void;
    onUserInputChange: (value: string) => void;
}

export const PipelineDeleteDialog: React.FC<PipelineDeleteDialogProps> = ({
    open,
    pipelineName,
    userInput,
    isDeleting,
    onClose,
    onConfirm,
    onUserInputChange,
}) => {
    const { t } = useTranslation();

    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>{t('pipelines.deleteConfirmTitle')}</DialogTitle>
            <DialogContent>
                <DialogContentText>
                    {t('pipelines.deleteConfirmMessage', { name: pipelineName })}
                </DialogContentText>
                <TextField
                    autoFocus
                    margin="dense"
                    label={t('pipelines.nameConfirmLabel')}
                    fullWidth
                    variant="outlined"
                    value={userInput}
                    onChange={(e) => onUserInputChange(e.target.value)}
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} color="primary">
                    {t('common.cancel')}
                </Button>
                <Button
                    onClick={onConfirm}
                    color="error"
                    disabled={userInput !== pipelineName || isDeleting}
                >
                    {isDeleting ? <CircularProgress size={24} /> : t('common.delete')}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
