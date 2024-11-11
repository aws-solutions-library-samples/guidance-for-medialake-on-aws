import React, { useState } from 'react';
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
    IconButton,
    CircularProgress,
} from '@mui/material';
import {
    Info as InfoIcon,
} from '@mui/icons-material';
import { ErrorModal } from './ErrorModal';
import { useErrorModal } from '../hooks/useErrorModal';
import { useGetS3Buckets, useCreateS3Connector } from '../api/hooks/useConnectors';
import type { CreateConnectorRequest } from '../api/types/api.types';

export interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (data: CreateConnectorRequest) => void;
    connector?: any;
}

const S3_CONNECTOR_TYPES = [
    { value: 'non-managed', label: 'MediaLake Non-Managed' },
];

export const ConnectorModal: React.FC<ConnectorModalProps> = ({
    open,
    onClose,
    onSave,
    connector
}) => {
    const { showError } = useErrorModal();
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [s3ConnectorType, setS3ConnectorType] = useState('');
    const [configuration, setConfiguration] = useState<Record<string, string>>({});
    const [error, setError] = useState('');

    const { data: s3BucketsResponse, isLoading: isLoadingBuckets } = useGetS3Buckets();
    const { mutateAsync: createS3Connector, isPending: isCreating } = useCreateS3Connector();

    const buckets = s3BucketsResponse?.data?.buckets || [];

    const handleSave = async () => {
        try {
            if (!name || !s3ConnectorType || !configuration.bucket) {
                setError('Please fill in all required fields');
                return;
            }

            const connectorData: CreateConnectorRequest = {
                name,
                type: 's3',
                description,
                configuration: {
                    ...configuration,
                    connectorType: s3ConnectorType,
                },
            };

            const result = await createS3Connector(connectorData);

            if (!result) {
                throw new Error('Failed to create connector');
            }

            // Only call onSave if we have a successful result
            onSave(connectorData);

            // Clear any existing errors
            setError('');

            // Close the modal
            onClose();
        } catch (err: any) {
            const errorMessage = err?.message || 'Error Creating S3 Connector';
            showError(errorMessage);
            setError(errorMessage);
        }
    };

    const handleClose = () => {
        // Clear form state
        setName('');
        setDescription('');
        setS3ConnectorType('');
        setConfiguration({});
        setError('');
        onClose();
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                {connector ? 'Edit Connector' : 'New S3 Connector'}
            </DialogTitle>
            <DialogContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <TextField
                        label="Connector Name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        fullWidth
                        required
                        error={!name && error !== ''}
                        helperText={!name && error !== '' ? 'Name is required' : ''}
                    />
                    <TextField
                        label="Description"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        fullWidth
                        multiline
                        rows={2}
                    />
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FormControl fullWidth required error={!s3ConnectorType && error !== ''}>
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
                            {!s3ConnectorType && error !== '' && (
                                <Typography variant="caption" color="error">
                                    Connector type is required
                                </Typography>
                            )}
                        </FormControl>
                        <IconButton>
                            <InfoIcon />
                        </IconButton>
                    </Box>
                    <FormControl fullWidth required error={!configuration.bucket && error !== ''}>
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
                        {!configuration.bucket && error !== '' && (
                            <Typography variant="caption" color="error">
                                Bucket selection is required
                            </Typography>
                        )}
                    </FormControl>
                    {error && (
                        <Alert severity="error" onClose={() => setError('')}>
                            {error}
                        </Alert>
                    )}
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} disabled={isCreating}>
                    Cancel
                </Button>
                <Button
                    onClick={handleSave}
                    variant="contained"
                    disabled={isCreating}
                    startIcon={isCreating ? <CircularProgress size={20} /> : null}
                >
                    Save
                </Button>
            </DialogActions>
        </Dialog>
    );
};
