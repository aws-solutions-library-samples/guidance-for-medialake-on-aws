import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Button,
    Modal,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    IconButton,
    SelectChangeEvent,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

interface Integration {
    type: string;
    apiKey: string;
    name: string;
    createdDate: string;
}

interface IntegrationModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (integration: Integration) => void;
    editingIntegration?: Integration;
}

const modalStyle = {
    position: 'absolute' as const,
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 400,
    bgcolor: 'background.paper',
    boxShadow: 24,
    p: 4,
    borderRadius: 2,
};

export const IntegrationModal: React.FC<IntegrationModalProps> = ({
    open,
    onClose,
    onSave,
    editingIntegration,
}) => {
    const [name, setName] = useState('');
    const [integrationType, setIntegrationType] = useState('');
    const [apiKey, setApiKey] = useState('');

    useEffect(() => {
        if (editingIntegration) {
            setName(editingIntegration.name);
            setIntegrationType(editingIntegration.type);
            setApiKey(editingIntegration.apiKey);
        } else {
            setName('');
            setIntegrationType('');
            setApiKey('');
        }
    }, [editingIntegration]);

    const handleSave = () => {
        const newIntegration: Integration = {
            type: integrationType,
            apiKey,
            name,
            createdDate: editingIntegration?.createdDate || new Date().toISOString(),
        };
        onSave(newIntegration);
    };

    return (
        <Modal open={open} onClose={onClose}>
            <Box sx={modalStyle}>
                <IconButton
                    aria-label="close"
                    onClick={onClose}
                    sx={{ position: 'absolute', right: 8, top: 8 }}
                >
                    <CloseIcon />
                </IconButton>
                <Typography variant="h6" component="h2" gutterBottom>
                    {editingIntegration ? 'Edit Integration' : 'Add New Integration'}
                </Typography>
                <TextField
                    fullWidth
                    label="Name"
                    variant="outlined"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    sx={{ mt: 2 }}
                />
                <FormControl fullWidth sx={{ mt: 2 }}>
                    <InputLabel>Type</InputLabel>
                    <Select
                        value={integrationType}
                        label="Type"
                        onChange={(e: SelectChangeEvent<string>) => setIntegrationType(e.target.value)}
                    >
                        <MenuItem value="twelveLabs">Twelve Labs Embeddings API</MenuItem>
                    </Select>
                </FormControl>
                {integrationType === 'twelveLabs' && (
                    <TextField
                        fullWidth
                        label="API Key"
                        variant="outlined"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        sx={{ mt: 2 }}
                    />
                )}
                <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                    <Button onClick={onClose} sx={{ mr: 2 }}>
                        Cancel
                    </Button>
                    <Button variant="contained" onClick={handleSave}>
                        Save
                    </Button>
                </Box>
            </Box>
        </Modal>
    );
};
