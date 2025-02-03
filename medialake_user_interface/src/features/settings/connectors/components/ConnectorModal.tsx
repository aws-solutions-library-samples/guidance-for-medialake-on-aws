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
    Popover,
    CircularProgress,
    Collapse,
} from '@mui/material';
import {
    Close as CloseIcon,
    CloudUpload as CloudUploadIcon,
    Info as InfoIcon,
    Refresh as RefreshIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { ConnectorResponse, CreateConnectorRequest } from '@/api/types/api.types';
import { useGetS3Buckets } from '@/api/hooks/useConnectors';


interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    editingConnector?: ConnectorResponse;
    onSave: (connectorData: CreateConnectorRequest) => Promise<void>;
    isCreating: boolean;
}

const CONNECTOR_TYPES = [
    { value: 's3', label: 'Amazon S3', icon: CloudUploadIcon, colorHex: '#FF9900' },
    { value: 'fsx', label: 'Amazon FSx', icon: CloudUploadIcon, colorHex: '#FF9900' },
    { value: 'empty', label: '', icon: CloudUploadIcon, colorHex: '#FF9900' },
];

const S3_BUCKET_TYPES = [
    { value: 'existing', label: 'Existing S3 Bucket', description: 'Connect to an existing S3 bucket' },
    { value: 'new', label: 'New S3 Bucket', description: 'Create a new S3 bucket' },
];

const S3_CONNECTOR_TYPES = [
    { value: 'non-managed', label: 'MediaLake Non-Managed' },
];

const S3_INTEGRATION_METHODS = [
    { value: 'eventbridge' as const, label: 'S3 EventBridge Notifications' },
    { value: 's3-event-notifications' as const, label: 'S3 Event Notifications' },
] as const;

const ConnectorModal: React.FC<ConnectorModalProps> = ({
    open,
    onClose,
    editingConnector,
    onSave,
    isCreating,
}) => {
    const theme = useTheme();
    const [activeStep, setActiveStep] = useState(0);
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [type, setType] = useState('');
    const [bucketType, setBucketType] = useState('');
    const [s3ConnectorType, setS3ConnectorType] = useState('');
    const [configuration, setConfiguration] = useState<Record<string, string>>({});
    const [error, setError] = useState('');
    const [infoAnchorEl, setInfoAnchorEl] = useState<HTMLElement | null>(null);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const { data: s3BucketsResponse, isLoading: isLoadingBuckets, refetch: refetchBuckets } = useGetS3Buckets();
    const buckets = s3BucketsResponse?.data?.buckets || [];

    useEffect(() => {
        if (editingConnector) {
            setName(editingConnector.name);
            setType(editingConnector.type);
            setConfiguration(editingConnector.configuration || {});
            setActiveStep(2);
        } else {
            setName('');
            setType('');
            setBucketType('');
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

    const handleSaveInternal = async () => {
        if (!name || !type || (type === 's3' && (!s3ConnectorType || !configuration.bucket || !configuration.integrationMethod))) {
            setError('Please fill in all required fields');
            return;
        }

        const connectorData: CreateConnectorRequest = {
            name,
            type,
            description,
            configuration: {
                ...configuration,
                connectorType: s3ConnectorType,
                s3IntegrationMethod: configuration.integrationMethod as 'eventbridge' | 's3-event-notifications',
            },
        };

        try {
            await onSave(connectorData);
            onClose();
        } catch (err) {
            setError('Failed to create connector');
        }
    };

    const handleInfoClick = (event: React.MouseEvent<HTMLElement>) => {
        setInfoAnchorEl(event.currentTarget);
    };

    const handleInfoClose = () => {
        setInfoAnchorEl(null);
    };

    const renderS3BucketTypeSelection = () => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {S3_BUCKET_TYPES.map((bucketType) => (
                <Box
                    key={bucketType.value}
                    onClick={() => {
                        setBucketType(bucketType.value);
                        handleNext();
                    }}
                    sx={{
                        p: 3,
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: '8px',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        '&:hover': {
                            borderColor: theme.palette.primary.main,
                            backgroundColor: `${theme.palette.primary.main}08`,
                        },
                    }}
                >
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                        {bucketType.label}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        {bucketType.description}
                    </Typography>
                </Box>
            ))}
        </Box>
    );

    const renderS3Configuration = () => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {editingConnector ? (
                <>
                    <TextField
                        label="Connector Name"
                        value={name}
                        disabled
                        fullWidth
                        slotProps={{
                            input: {
                                sx: { bgcolor: 'action.disabledBackground' }
                            }
                        }}
                        helperText="Connector name cannot be modified after creation"
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
                        Amazon S3
                    </Typography>
                </>
            ) : (
                <TextField
                    label="Connector Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    fullWidth
                    required
                />
            )}

            <TextField
                label="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                fullWidth
                multiline
                rows={2}
            />

            {editingConnector ? (
                <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FormControl fullWidth disabled>
                            <InputLabel>S3 Connector Type</InputLabel>
                            <Select
                                value={s3ConnectorType}
                                label="S3 Connector Type"
                                sx={{ bgcolor: 'action.disabledBackground' }}
                            >
                                {S3_CONNECTOR_TYPES.map((type) => (
                                    <MenuItem key={type.value} value={type.value}>
                                        {type.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <IconButton onClick={handleInfoClick}>
                            <InfoIcon />
                        </IconButton>
                    </Box>
                    <FormControl fullWidth disabled>
                        <InputLabel>S3 Integration Method</InputLabel>
                        <Select
                            value={configuration.integrationMethod || ''}
                            label="S3 Integration Method"
                            sx={{ bgcolor: 'action.disabledBackground' }}
                        >
                            {S3_INTEGRATION_METHODS.map((method) => (
                                <MenuItem key={method.value} value={method.value}>
                                    {method.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    <FormControl fullWidth disabled>
                        <InputLabel>S3 Bucket</InputLabel>
                        <Select
                            value={configuration.bucket || ''}
                            label="S3 Bucket"
                            sx={{ bgcolor: 'action.disabledBackground' }}
                        >
                            <MenuItem value={configuration.bucket}>
                                {configuration.bucket}
                            </MenuItem>
                        </Select>
                    </FormControl>
                </>
            ) : (
                <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FormControl fullWidth required>
                            <InputLabel>S3 Connector Type</InputLabel>
                            <Select
                                value={s3ConnectorType}
                                label="S3 Connector Type"
                                onChange={(e) => setS3ConnectorType(e.target.value)}
                            >
                                {S3_CONNECTOR_TYPES.map((type) => (
                                    <MenuItem key={type.value} value={type.value}>
                                        {type.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <IconButton onClick={handleInfoClick}>
                            <InfoIcon />
                        </IconButton>
                    </Box>
                    <FormControl fullWidth required>
                        <InputLabel>S3 Integration Method</InputLabel>
                        <Select
                            value={configuration.integrationMethod || ''}
                            label="S3 Integration Method"
                            onChange={(e) => setConfiguration({ ...configuration, integrationMethod: e.target.value })}
                        >
                            {S3_INTEGRATION_METHODS.map((method) => (
                                <MenuItem key={method.value} value={method.value}>
                                    {method.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                    {bucketType === 'existing' && (
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                            <FormControl fullWidth required>
                                <InputLabel>S3 Bucket</InputLabel>
                                <Select
                                    value={configuration.bucket || ''}
                                    label="S3 Bucket"
                                    onChange={(e) => setConfiguration({ ...configuration, bucket: e.target.value })}
                                    disabled={isLoadingBuckets}
                                    startAdornment={
                                        isLoadingBuckets ? (
                                            <CircularProgress size={20} sx={{ ml: 1 }} />
                                        ) : null
                                    }
                                >
                                    {buckets.map((bucket) => (
                                        <MenuItem key={bucket} value={bucket}>
                                            {bucket}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                            <IconButton
                                onClick={() => refetchBuckets()}
                                disabled={isLoadingBuckets}
                                sx={{ mt: 1 }}
                            >
                                {isLoadingBuckets ? (
                                    <CircularProgress size={24} />
                                ) : (
                                    <RefreshIcon />
                                )}
                            </IconButton>
                        </Box>
                    )}
                    {bucketType === 'new' && (
                        <TextField
                            label="New Bucket Name"
                            value={configuration.bucket || ''}
                            onChange={(e) => setConfiguration({ ...configuration, bucket: e.target.value })}
                            fullWidth
                            required
                            helperText="Bucket name must be unique across all AWS accounts"
                        />
                    )}
                </>
            )}

            <Button
                onClick={() => setShowAdvanced(!showAdvanced)}
                startIcon={showAdvanced ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                sx={{ alignSelf: 'flex-start', mt: 1 }}
            >
                Advanced configuration
            </Button>

            <Collapse in={showAdvanced}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <TextField
                        label="Object Prefix"
                        value={configuration.objectPrefix || ''}
                        onChange={(e) => setConfiguration({ ...configuration, objectPrefix: e.target.value })}
                        fullWidth
                        helperText="Optional prefix to filter objects (e.g., 'folder/')"
                    />
                </Box>
            </Collapse>
        </Box>
    );

    const steps = ['Select Type', 'Select S3 Type', 'Configuration'];

    const renderStepContent = (step: number) => {
        switch (step) {
            case 0:
                return (
                    <Box sx={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: 2
                    }}>
                        {CONNECTOR_TYPES.map((connectorType) => {
                            const Icon = connectorType.icon;
                            return connectorType.value === 'empty' ? (
                                <Box key="empty" sx={{ visibility: 'hidden' }} />
                            ) : (
                                <Box
                                    key={connectorType.value}
                                    onClick={() => {
                                        setType(connectorType.value);
                                        handleNext();
                                    }}
                                    sx={{
                                        height: '120px',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                        border: `1px solid ${theme.palette.divider}`,
                                        borderRadius: '8px',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        '&:hover': {
                                            borderColor: connectorType.colorHex,
                                            backgroundColor: `${connectorType.colorHex}08`,
                                        },
                                    }}
                                >
                                    <Icon sx={{ color: connectorType.colorHex, fontSize: 40, mb: 1 }} />
                                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                        {connectorType.label}
                                    </Typography>
                                </Box>
                            );
                        })}
                    </Box>
                );
            case 1:
                return type === 's3' ? renderS3BucketTypeSelection() : null;
            case 2:
                return type === 's3' ? renderS3Configuration() : null;
            default:
                return null;
        }
    };

    return (
        <>
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
                            width: 40,
                            height: 40,
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
                        <Button onClick={handleBack} disabled={isCreating}>
                            Back
                        </Button>
                    )}
                    <Button onClick={onClose} color="inherit" disabled={isCreating}>
                        Cancel
                    </Button>
                    {(activeStep === steps.length - 1 || editingConnector) ? (
                        <Button
                            variant="contained"
                            onClick={handleSaveInternal}
                            disabled={isCreating}
                            startIcon={isCreating ? <CircularProgress size={20} /> : null}
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
                            disabled={!type || (activeStep === 1 && !bucketType) || isCreating}
                        >
                            Next
                        </Button>
                    )}
                </DialogActions>

                <Popover
                    open={Boolean(infoAnchorEl)}
                    anchorEl={infoAnchorEl}
                    onClose={handleInfoClose}
                    anchorOrigin={{
                        vertical: 'bottom',
                        horizontal: 'center',
                    }}
                    transformOrigin={{
                        vertical: 'top',
                        horizontal: 'center',
                    }}
                >
                    <Box sx={{ p: 2, maxWidth: 400 }}>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                            • MediaLake Non-Managed (If/when other remote storage systems are introduced this would be that category)
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 2 }}>
                            • Original files are kept on bucket, folder structure is not modified
                        </Typography>
                        <Typography variant="body2">
                            • Representations of files created, such as proxies, will be put in a MediaLake managed bucket with a shadow folder structure
                        </Typography>
                    </Box>
                </Popover>
            </Dialog>

        </>
    );
};

export default ConnectorModal;
