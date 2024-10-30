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
    CircularProgress,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useGetS3Buckets } from '../../api/hooks/useConnectors';
import { ConnectorResponse, CreateConnectorRequest } from '../../api/types/api.types';
import { useCreateS3Connector, useCreateGCSConnector } from '../../api/hooks/useConnectors';

interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (connector: CreateConnectorRequest) => void;
    editingConnector?: ConnectorResponse;
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

export const ConnectorModal: React.FC<ConnectorModalProps> = ({
    open,
    onClose,
    onSave,
    editingConnector,
}) => {
    const [name, setName] = useState('');
    const [connectorType, setConnectorType] = useState('');
    const [bucket, setBucket] = useState('');
    const { data: s3BucketsData, refetch: fetchS3Buckets, isLoading: isLoadingS3Buckets } = useGetS3Buckets();
    const createS3Connector = useCreateS3Connector();
    const createGCSConnector = useCreateGCSConnector();

    useEffect(() => {
        if (editingConnector) {
            setName(editingConnector.name);
            setConnectorType(editingConnector.type);
            setBucket(editingConnector.configuration?.bucket || '');
        } else {
            setName('');
            setConnectorType('');
            setBucket('');
        }
    }, [editingConnector]);

    useEffect(() => {
        if (open && connectorType === 'amazonS3') {
            fetchS3Buckets();
        }
    }, [open, connectorType, fetchS3Buckets]);

    const handleSave = async () => {
        const connectorData: CreateConnectorRequest = {
            name,
            type: connectorType,
            configuration: {
                bucket
            }
        };

        try {
            let response;
            if (connectorType === 'amazonS3') {
                response = await createS3Connector.mutateAsync(connectorData);
            } else if (connectorType === 'googleCloudStorage') {
                response = await createGCSConnector.mutateAsync(connectorData);
            }

            if (response) {
                onSave(connectorData);
                onClose();
            }
        } catch (error) {
            console.error('Error creating connector:', error);
            // You might want to add error handling/display here
        }
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
                    {editingConnector ? 'Edit Connector' : 'Add New Connector'}
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
                        value={connectorType}
                        label="Type"
                        onChange={(e: SelectChangeEvent<string>) => setConnectorType(e.target.value)}
                    >
                        <MenuItem value="amazonS3">Amazon S3</MenuItem>
                        <MenuItem value="googleCloudStorage">Google Cloud Storage</MenuItem>
                    </Select>
                </FormControl>
                {connectorType === 'amazonS3' && (
                    <FormControl fullWidth sx={{ mt: 2 }}>
                        <InputLabel>Bucket</InputLabel>
                        <Select
                            value={bucket}
                            label="Bucket"
                            onChange={(e: SelectChangeEvent<string>) => setBucket(e.target.value)}
                        >
                            {isLoadingS3Buckets ? (
                                <MenuItem value="">
                                    <CircularProgress size={20} /> Loading buckets...
                                </MenuItem>
                            ) : s3BucketsData?.data?.buckets && s3BucketsData.data.buckets.length > 0 ? (
                                s3BucketsData.data.buckets.map((bucketName) => (
                                    <MenuItem key={bucketName} value={bucketName}>
                                        {bucketName}
                                    </MenuItem>
                                ))
                            ) : (
                                <MenuItem value="">No buckets available</MenuItem>
                            )}
                        </Select>
                    </FormControl>
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
