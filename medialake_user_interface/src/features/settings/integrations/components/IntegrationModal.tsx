import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Box,
    Typography,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
    Alert,
    Stepper,
    Step,
    StepLabel,
    IconButton,
    useTheme,
} from '@mui/material';
import {
    Close as CloseIcon,
    YouTube as YouTubeIcon,
    Cloud as CloudIcon,
    PhotoLibrary as PhotoIcon,
    Api as ApiIcon,
} from '@mui/icons-material';
import { Integration } from '@/api/types/api.types';

interface IntegrationModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (integration: Integration) => void;
    editingIntegration?: Integration;
}

const INTEGRATION_TYPES = [
    { value: 'youtube', label: 'YouTube', icon: YouTubeIcon, color: '#FF0000' },
    { value: 'cloudinary', label: 'Cloudinary', icon: CloudIcon, color: '#3448C5' },
    { value: 'shutterstock', label: 'Shutterstock', icon: PhotoIcon, color: '#EE2B24' },
    { value: 'custom', label: 'Custom API', icon: ApiIcon, color: '#1976d2' },
];

const IntegrationModal: React.FC<IntegrationModalProps> = ({
    open,
    onClose,
    onSave,
    editingIntegration,
}) => {
    const theme = useTheme();
    const [activeStep, setActiveStep] = useState(0);
    const [name, setName] = useState('');
    const [type, setType] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        if (editingIntegration) {
            setName(editingIntegration.name);
            setType(editingIntegration.type);
            setApiKey(editingIntegration.apiKey);
            setActiveStep(2); // Skip type selection for editing
        } else {
            setName('');
            setType('');
            setApiKey('');
            setActiveStep(0);
        }
    }, [editingIntegration, open]);

    const handleNext = () => {
        setActiveStep((prev) => prev + 1);
    };

    const handleBack = () => {
        setActiveStep((prev) => prev - 1);
    };

    const handleSave = () => {
        if (!name || !type || !apiKey) {
            setError('Please fill in all required fields');
            return;
        }

        const integration: Integration = {
            id: editingIntegration?.id || Date.now().toString(),
            name,
            type,
            apiKey,
            createdAt: editingIntegration?.createdAt || new Date().toISOString(),
        };

        onSave(integration);
        onClose();
    };

    const steps = ['Select Type', 'Basic Info', 'Configuration'];

    const renderStepContent = (step: number) => {
        switch (step) {
            case 0:
                return (
                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                        {INTEGRATION_TYPES.map((integrationType) => {
                            const Icon = integrationType.icon;
                            return (
                                <Box
                                    key={integrationType.value}
                                    onClick={() => {
                                        setType(integrationType.value);
                                        handleNext();
                                    }}
                                    sx={{
                                        p: 2,
                                        border: `1px solid ${theme.palette.divider}`,
                                        borderRadius: '8px',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 2,
                                        transition: 'all 0.2s',
                                        '&:hover': {
                                            borderColor: integrationType.color,
                                            backgroundColor: `${integrationType.color}08`,
                                        },
                                    }}
                                >
                                    <Icon sx={{ color: integrationType.color, fontSize: 32 }} />
                                    <Box>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                            {integrationType.label}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Connect to {integrationType.label}
                                        </Typography>
                                    </Box>
                                </Box>
                            );
                        })}
                    </Box>
                );
            case 1:
                return (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="Integration Name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            fullWidth
                            required
                        />
                        <Typography variant="body2" color="text.secondary">
                            Give your integration a meaningful name to easily identify it later.
                        </Typography>
                    </Box>
                );
            case 2:
                return (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="API Key"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            fullWidth
                            required
                            type="password"
                        />
                        <Typography variant="body2" color="text.secondary">
                            Enter the API key from your {
                                INTEGRATION_TYPES.find(t => t.value === type)?.label
                            } account.
                        </Typography>
                    </Box>
                );
            default:
                return null;
        }
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: '12px',
                }
            }}
        >
            <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="h6">
                    {editingIntegration ? 'Edit Integration' : 'Add New Integration'}
                </Typography>
                <IconButton
                    aria-label="close"
                    onClick={onClose}
                    sx={{
                        color: theme.palette.grey[500],
                    }}
                >
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent dividers>
                {!editingIntegration && (
                    <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
                        {steps.map((label) => (
                            <Step key={label}>
                                <StepLabel>{label}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>
                )}

                {error && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}

                {renderStepContent(activeStep)}
            </DialogContent>

            <DialogActions sx={{ p: 2, gap: 1 }}>
                {!editingIntegration && activeStep > 0 && (
                    <Button onClick={handleBack}>
                        Back
                    </Button>
                )}
                <Button onClick={onClose} color="inherit">
                    Cancel
                </Button>
                {(activeStep === steps.length - 1 || editingIntegration) ? (
                    <Button
                        variant="contained"
                        onClick={handleSave}
                        sx={{
                            backgroundColor: theme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.dark,
                            },
                        }}
                    >
                        {editingIntegration ? 'Save Changes' : 'Add Integration'}
                    </Button>
                ) : (
                    <Button
                        variant="contained"
                        onClick={handleNext}
                        disabled={!type || (activeStep === 1 && !name)}
                    >
                        Next
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    );
};

export default IntegrationModal;
