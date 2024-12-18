import React, { useState } from 'react';
import {
    Card,
    CardContent,
    Typography,
    Box,
    IconButton,
    Tooltip,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Popover,
    FormGroup,
    FormControlLabel,
    Checkbox,
    TextField,
    useTheme,
    alpha,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    CloudUpload as CloudUploadIcon,
} from '@mui/icons-material';
import { ConnectorResponse } from '../../../../api/types/api.types';

const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

interface ConnectorCardProps {
    connector: ConnectorResponse;
    onEdit: (connector: ConnectorResponse) => void;
    onDelete: (id: string) => Promise<void>;
}

interface CardFieldConfig {
    id: string;
    label: string;
    visible: boolean;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({
    connector,
    onEdit,
    onDelete,
}) => {
    const theme = useTheme();
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [cardFieldsAnchor, setCardFieldsAnchor] = useState<null | HTMLElement>(null);
    const [isViewDetailsOpen, setIsViewDetailsOpen] = useState(false);
    const [editedDescription, setEditedDescription] = useState(connector.description);
    const [cardFields, setCardFields] = useState<CardFieldConfig[]>([
        { id: 'name', label: 'Name', visible: true },
        { id: 'type', label: 'Type', visible: true },
        { id: 'bucket', label: 'Bucket', visible: true },
        { id: 'storage', label: 'Storage', visible: true },
        { id: 'lastUpdated', label: 'Last Updated', visible: true },
        { id: 'status', label: 'Status', visible: true },
    ]);

    const handleDeleteClick = () => {
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        try {
            setIsDeleting(true);
            await onDelete(connector.id);
        } finally {
            setIsDeleting(false);
            setDeleteDialogOpen(false);
        }
    };

    const getConnectorIcon = (type: string) => {
        switch (type) {
            case 's3':
                return <CloudUploadIcon sx={{ color: '#FF9900' }} />;
            default:
                return null;
        }
    };

    const getConnectorTypeLabel = (type: string) => {
        switch (type) {
            case 's3':
                return 'Amazon S3';
            default:
                return type;
        }
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    const handleCardFieldToggle = (fieldId: string) => {
        setCardFields(cardFields.map(field =>
            field.id === fieldId ? { ...field, visible: !field.visible } : field
        ));
    };

    const handleViewDetails = () => {
        setIsViewDetailsOpen(true);
    };

    const handleSaveDescription = async () => {
        // Implement save description API call here
        setIsViewDetailsOpen(false);
    };

    const CardFieldsMenu = () => (
        <Popover
            open={Boolean(cardFieldsAnchor)}
            anchorEl={cardFieldsAnchor}
            onClose={() => setCardFieldsAnchor(null)}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
            }}
        >
            <Box sx={{ p: 2, minWidth: 200 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                    Show Fields
                </Typography>
                <FormGroup>
                    {cardFields.map((field) => (
                        <FormControlLabel
                            key={field.id}
                            control={
                                <Checkbox
                                    checked={field.visible}
                                    onChange={() => handleCardFieldToggle(field.id)}
                                    size="small"
                                />
                            }
                            label={field.label}
                        />
                    ))}
                </FormGroup>
            </Box>
        </Popover>
    );

    const ViewDetailsDialog = () => (
        <Dialog
            open={isViewDetailsOpen}
            onClose={() => setIsViewDetailsOpen(false)}
            maxWidth="sm"
            fullWidth
        >
            <DialogTitle sx={{ fontWeight: 600 }}>Connector Details</DialogTitle>
            <DialogContent>
                <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <TextField
                        label="Name"
                        value={connector.name}
                        fullWidth
                        disabled
                    />
                    <TextField
                        label="Bucket"
                        value={connector.storageIdentifier || ''}
                        fullWidth
                        disabled
                    />
                    {connector.settings?.region && (
                        <TextField
                            label="Region"
                            value={connector.region}
                            fullWidth
                            disabled
                        />
                    )}
                    {connector.settings?.path && (
                        <TextField
                            label="Path"
                            value={connector.settings.path}
                            fullWidth
                            disabled
                        />
                    )}
                    <TextField
                        label="Description"
                        value={editedDescription}
                        onChange={(e) => setEditedDescription(e.target.value)}
                        fullWidth
                        multiline
                        rows={4}
                    />
                </Box>
            </DialogContent>
            <DialogActions>
                <Button
                    onClick={() => setIsViewDetailsOpen(false)}
                    sx={{
                        color: theme.palette.text.secondary,
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                        },
                    }}
                >
                    Cancel
                </Button>
                <Button
                    onClick={handleSaveDescription}
                    variant="contained"
                    sx={{
                        backgroundColor: theme.palette.primary.main,
                        '&:hover': {
                            backgroundColor: theme.palette.primary.dark,
                        },
                    }}
                >
                    Save Changes
                </Button>
            </DialogActions>
        </Dialog>
    );

    return (
        <>
            <Card
                sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: '12px',
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    backgroundColor: theme.palette.background.paper,
                    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                    '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: `0 4px 20px ${alpha(theme.palette.common.black, 0.1)}`,
                    },
                }}
                elevation={0}
            >
                <CardContent sx={{ flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getConnectorIcon(connector.type)}
                            <Box>
                                {cardFields.find(f => f.id === 'name')?.visible && (
                                    <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.primary.main }}>
                                        {connector.name}
                                    </Typography>
                                )}
                                {cardFields.find(f => f.id === 'type')?.visible && (
                                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                        {getConnectorTypeLabel(connector.type)}
                                    </Typography>
                                )}
                            </Box>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Tooltip title="Edit">
                                <IconButton
                                    onClick={handleViewDetails}
                                    size="small"
                                    sx={{
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                        width: 40,
                                        height: 40,
                                        '&:hover': {
                                            backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                            width: 40,
                                            height: 40,
                                        },
                                    }}
                                >
                                    <EditIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete">
                                <IconButton
                                    onClick={handleDeleteClick}
                                    size="small"
                                    sx={{
                                        backgroundColor: alpha(theme.palette.error.main, 0.1),
                                        width: 40,
                                        height: 40,
                                        '&:hover': {
                                            backgroundColor: alpha(theme.palette.error.main, 0.2),
                                            width: 40,
                                            height: 40,
                                        },
                                    }}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>
                    {cardFields.find(f => f.id === 'bucket')?.visible && connector.settings?.bucket && (
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary }} gutterBottom>
                            Bucket: {connector.storageIdentifier}
                        </Typography>
                    )}
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }} gutterBottom>
                        {connector.description || 'No description provided'}
                    </Typography>

                    <Box sx={{ mt: 2 }}>
                        {cardFields.find(f => f.id === 'storage')?.visible && (
                            <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                Storage: {formatBytes(connector.usage?.total || 0)}
                            </Typography>
                        )}
                        {cardFields.find(f => f.id === 'lastUpdated')?.visible && (
                            <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                Last Updated: {formatDate(connector.updatedAt)}
                            </Typography>
                        )}
                        {cardFields.find(f => f.id === 'status')?.visible && (
                            <Box sx={{ mt: 1 }}>
                                <Chip
                                    size="small"
                                    label={connector.status || 'active'}
                                    sx={{
                                        backgroundColor: connector.status === 'error'
                                            ? alpha(theme.palette.error.main, 0.1)
                                            : alpha(theme.palette.success.main, 0.1),
                                        color: connector.status === 'error'
                                            ? theme.palette.error.main
                                            : theme.palette.success.main,
                                        fontWeight: 600,
                                        borderRadius: '6px',
                                        height: '24px',
                                        textTransform: 'capitalize',
                                        '& .MuiChip-label': {
                                            px: 1.5,
                                        },
                                    }}
                                />
                            </Box>
                        )}
                    </Box>
                </CardContent>
            </Card>
            <CardFieldsMenu />
            <ViewDetailsDialog />

            <Dialog
                open={deleteDialogOpen}
                onClose={() => setDeleteDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ fontWeight: 600 }}>Delete Connector</DialogTitle>
                <DialogContent>
                    <Typography sx={{ color: theme.palette.text.secondary }}>
                        Are you sure you want to delete the connector "{connector.name}"? This action cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={() => setDeleteDialogOpen(false)}
                        disabled={isDeleting}
                        sx={{
                            color: theme.palette.text.secondary,
                            '&:hover': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            },
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleDeleteConfirm}
                        color="error"
                        variant="contained"
                        disabled={isDeleting}
                        sx={{
                            backgroundColor: theme.palette.error.main,
                            '&:hover': {
                                backgroundColor: theme.palette.error.dark,
                            },
                        }}
                    >
                        {isDeleting ? 'Deleting...' : 'Delete'}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default ConnectorCard;
