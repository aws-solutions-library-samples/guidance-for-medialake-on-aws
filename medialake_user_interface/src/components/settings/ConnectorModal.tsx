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
    Storage as StorageIcon,
    CloudUpload as CloudUploadIcon,
    Folder as FolderIcon,
    Cloud as CloudIcon,
} from '@mui/icons-material';
import { ConnectorResponse, CreateConnectorRequest } from '../../api/types/api.types';

interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (connector: CreateConnectorRequest) => void;
    editingConnector?: ConnectorResponse;
}

const CONNECTOR_TYPES = [
    { value: 's3', label: 'Amazon S3', icon: CloudIcon, color: '#FF9900' },
    { value: 'local', label: 'Local Storage', icon: FolderIcon, color: '#4CAF50' },
    { value: 'cloud', label: 'Cloud Storage', icon: CloudUploadIcon, color: '#2196F3' },
    { value: 'nas', label: 'Network Storage', icon: StorageIcon, color: '#9C27B0' },
];

const ConnectorModal: React.FC<ConnectorModalProps> = ({
    open,
    onClose,
    onSave,
    editingConnector,
}) => {
    const theme = useTheme();
    const [activeStep, setActiveStep] = useState(0);
    const [name, setName] = useState('');
    const [type, setType] = useState('');
    const [configuration, setConfiguration] = useState<Record<string, string>>({});
    const [error, setError] = useState('');

    useEffect(() => {
        if (editingConnector) {
            setName(editingConnector.name);
            setType(editingConnector.type);
            setConfiguration(editingConnector.configuration || {});
            setActiveStep(2); // Skip type selection for editing
        } else {
            setName('');
            setType('');
            setConfiguration({});
            setActiveStep(0);
        }
    }, [editingConnector, open]);

    const handleNext = () => {
        setActiveStep((prev) => prev + 1);
    };

    const handleBack = () => {
        setActiveStep((prev) => prev - 1);
    };

    const handleSave = () => {
        if (!name || !type) {
            setError('Please fill in all required fields');
            return;
        }

        const connector: CreateConnectorRequest = {
            name,
            type,
            configuration,
        };

        onSave(connector);
    };

    const renderConfigurationFields = () => {
        switch (type) {
            case 's3':
                return (
                    <>
                        <TextField
                            label="Bucket Name"
                            value={configuration.bucketName || ''}
                            onChange={(e) => setConfiguration({ ...configuration, bucketName: e.target.value })}
                            fullWidth
                            required
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Region"
                            value={configuration.region || ''}
                            onChange={(e) => setConfiguration({ ...configuration, region: e.target.value })}
                            fullWidth
                            required
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Access Key ID"
                            value={configuration.accessKeyId || ''}
                            onChange={(e) => setConfiguration({ ...configuration, accessKeyId: e.target.value })}
                            fullWidth
                            required
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Secret Access Key"
                            value={configuration.secretAccessKey || ''}
                            onChange={(e) => setConfiguration({ ...configuration, secretAccessKey: e.target.value })}
                            fullWidth
                            required
                            type="password"
                        />
                    </>
                );
            case 'local':
                return (
                    <TextField
                        label="Path"
                        value={configuration.path || ''}
                        onChange={(e) => setConfiguration({ ...configuration, path: e.target.value })}
                        fullWidth
                        required
                        placeholder="/path/to/storage"
                    />
                );
            case 'cloud':
                return (
                    <>
                        <TextField
                            label="Provider"
                            value={configuration.provider || ''}
                            onChange={(e) => setConfiguration({ ...configuration, provider: e.target.value })}
                            fullWidth
                            required
                            select
                            sx={{ mb: 2 }}
                        >
                            <MenuItem value="google">Google Cloud Storage</MenuItem>
                            <MenuItem value="azure">Azure Blob Storage</MenuItem>
                        </TextField>
                        <TextField
                            label="Credentials"
                            value={configuration.credentials || ''}
                            onChange={(e) => setConfiguration({ ...configuration, credentials: e.target.value })}
                            fullWidth
                            required
                            multiline
                            rows={4}
                        />
                    </>
                );
            case 'nas':
                return (
                    <>
                        <TextField
                            label="Host"
                            value={configuration.host || ''}
                            onChange={(e) => setConfiguration({ ...configuration, host: e.target.value })}
                            fullWidth
                            required
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Share Path"
                            value={configuration.sharePath || ''}
                            onChange={(e) => setConfiguration({ ...configuration, sharePath: e.target.value })}
                            fullWidth
                            required
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Username"
                            value={configuration.username || ''}
                            onChange={(e) => setConfiguration({ ...configuration, username: e.target.value })}
                            fullWidth
                            sx={{ mb: 2 }}
                        />
                        <TextField
                            label="Password"
                            value={configuration.password || ''}
                            onChange={(e) => setConfiguration({ ...configuration, password: e.target.value })}
                            fullWidth
                            type="password"
                        />
                    </>
                );
            default:
                return null;
        }
    };

    const steps = ['Select Type', 'Basic Info', 'Configuration'];

    const renderStepContent = (step: number) => {
        switch (step) {
            case 0:
                return (
                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                        {CONNECTOR_TYPES.map((connectorType) => {
                            const Icon = connectorType.icon;
                            return (
                                <Box
                                    key={connectorType.value}
                                    onClick={() => {
                                        setType(connectorType.value);
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
                                            borderColor: connectorType.color,
                                            backgroundColor: `${connectorType.color}08`,
                                        },
                                    }}
                                >
                                    <Icon sx={{ color: connectorType.color, fontSize: 32 }} />
                                    <Box>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                            {connectorType.label}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Connect to {connectorType.label}
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
                            label="Connector Name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            fullWidth
                            required
                        />
                        <Typography variant="body2" color="text.secondary">
                            Give your connector a meaningful name to easily identify it later.
                        </Typography>
                    </Box>
                );
            case 2:
                return (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {renderConfigurationFields()}
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
                    {editingConnector ? 'Edit Connector' : 'Add New Connector'}
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
                {!editingConnector && (
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
                {!editingConnector && activeStep > 0 && (
                    <Button onClick={handleBack}>
                        Back
                    </Button>
                )}
                <Button onClick={onClose} color="inherit">
                    Cancel
                </Button>
                {(activeStep === steps.length - 1 || editingConnector) ? (
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
                        {editingConnector ? 'Save Changes' : 'Add Connector'}
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

export default ConnectorModal;
