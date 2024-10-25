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
import { useGetS3Buckets } from './api/hooks/useConnectors';

interface Connector {
    type: string;
    bucket: string;
    name: string;
    createdDate: string;
}

interface ConnectorModalProps {
    open: boolean;
    onClose: () => void;
    onSave: (connector: Connector) => void;
    editingConnector?: Connector;
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
    const [s3Buckets, setS3Buckets] = useState<string[]>([]);
    const [isLoadingS3Buckets, setIsLoadingS3Buckets] = useState(false);

    const { refetch: fetchS3Buckets } = useGetS3Buckets();

    useEffect(() => {
        if (editingConnector) {
            setName(editingConnector.name);
            setConnectorType(editingConnector.type);
            setBucket(editingConnector.bucket);
        } else {
            setName('');
            setConnectorType('');
            setBucket('');
        }
    }, [editingConnector]);

    useEffect(() => {
        if (open && connectorType === 'amazonS3' && s3Buckets.length === 0) {
            loadS3Buckets();
        }
    }, [open, connectorType]);

    const loadS3Buckets = async () => {
        setIsLoadingS3Buckets(true);
        try {
            const result = await fetchS3Buckets();
            if (result.data && result.data.buckets) {
                setS3Buckets(result.data.buckets);
            }
        } catch (error) {
            console.error('Error fetching S3 buckets:', error);
        } finally {
            setIsLoadingS3Buckets(false);
        }
    };

    const handleSave = () => {
        const newConnector: Connector = {
            type: connectorType,
            bucket,
            name,
            createdDate: editingConnector?.createdDate || new Date().toISOString(),
        };
        onSave(newConnector);
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
                            ) : s3Buckets.length > 0 ? (
                                s3Buckets.map((bucketName) => (
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
