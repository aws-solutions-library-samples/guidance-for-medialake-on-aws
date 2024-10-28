import React from 'react';
import { ErrorModal } from './ErrorModal';
import { useErrorModal } from '../hooks/useErrorModal';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField } from '@mui/material';

export interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (data: any) => void;
    connector?: any;
}

export const ConnectorModal: React.FC<ConnectorModalProps> = ({ open, onClose, onSave, connector }) => {
    const { isOpen, errorMessage, hideError } = useErrorModal();

    return (
        <>
            <Dialog open={open} onClose={onClose}>
                <DialogTitle>
                    {connector ? 'Edit Connector' : 'New Connector'}
                </DialogTitle>
                <DialogContent>
                    {/* Add your connector form fields here */}
                </DialogContent>
                <DialogActions>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button onClick={() => onSave({})}>Save</Button>
                </DialogActions>
            </Dialog>
            
            <ErrorModal 
                open={isOpen}
                onClose={hideError}
                message={errorMessage}
            />
        </>
    );
};
