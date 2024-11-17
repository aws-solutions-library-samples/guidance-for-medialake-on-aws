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
    Menu,
    MenuItem,
    Popover,
    FormGroup,
    FormControlLabel,
    Checkbox,
    TextField,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    CloudUpload as CloudUploadIcon,
    Sort as SortIcon,
    ViewColumn as ViewColumnIcon,
} from '@mui/icons-material';
import { ConnectorResponse } from '@/api/types/api.types';

// First, let's create a utility function for formatting bytes
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

// interface ConnectorResponse {
//     id: string;
//     name: string;
//     type: string;
//     usage?: {
//         total: number;
//     };
//     updatedAt: string;
//     status?: string;
//     bucket?: string;
//     description: string;
//     settings?: {
//         bucket: string;
//         region?: string;
//         path?: string;
//     };
// }

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
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [cardFieldsAnchor, setCardFieldsAnchor] = useState<null | HTMLElement>(null);
    const [cardSortAnchor, setCardSortAnchor] = useState<null | HTMLElement>(null);
    const [cardSortBy, setCardSortBy] = useState<string>('name');
    const [cardSortOrder, setCardSortOrder] = useState<'asc' | 'desc'>('asc');
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
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const handleCardFieldToggle = (fieldId: string) => {
        setCardFields(cardFields.map(field =>
            field.id === fieldId ? { ...field, visible: !field.visible } : field
        ));
    };

    const handleCardSortChange = (field: string) => {
        if (cardSortBy === field) {
            setCardSortOrder(cardSortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setCardSortBy(field);
            setCardSortOrder('asc');
        }
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
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
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

    const CardSortMenu = () => (
        <Popover
            open={Boolean(cardSortAnchor)}
            anchorEl={cardSortAnchor}
            onClose={() => setCardSortAnchor(null)}
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
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Sort By
                </Typography>
                {cardFields.map((field) => (
                    <MenuItem
                        key={field.id}
                        onClick={() => {
                            handleCardSortChange(field.id);
                            setCardSortAnchor(null);
                        }}
                    >
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                            {field.label}
                            {cardSortBy === field.id && (
                                <Typography variant="caption">
                                    {cardSortOrder === 'asc' ? '↑' : '↓'}
                                </Typography>
                            )}
                        </Box>
                    </MenuItem>
                ))}
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
            <DialogTitle>Connector Details</DialogTitle>
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
                        value={connector.settings?.bucket || ''}
                        fullWidth
                        disabled
                    />
                    {connector.settings?.region && (
                        <TextField
                            label="Region"
                            value={connector.settings.region}
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
                <Button onClick={() => setIsViewDetailsOpen(false)}>Cancel</Button>
                <Button onClick={handleSaveDescription} variant="contained">
                    Save Changes
                </Button>
            </DialogActions>
        </Dialog>
    );

    return (
        <>
            <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getConnectorIcon(connector.type)}
                            <Box>
                                {cardFields.find(f => f.id === 'name')?.visible && (
                                    <Typography variant="h6" component="div">
                                        {connector.name}
                                    </Typography>
                                )}
                                {cardFields.find(f => f.id === 'type')?.visible && (
                                    <Typography variant="caption" color="text.secondary">
                                        {getConnectorTypeLabel(connector.type)}
                                    </Typography>
                                )}
                            </Box>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <IconButton
                                size="small"
                                onClick={(e) => setCardSortAnchor(e.currentTarget)}
                            >
                                <SortIcon />
                            </IconButton>
                            <IconButton
                                size="small"
                                onClick={(e) => setCardFieldsAnchor(e.currentTarget)}
                            >
                                <ViewColumnIcon />
                            </IconButton>
                            <Tooltip title="Edit">
                                <IconButton onClick={handleViewDetails} size="small">
                                    <EditIcon />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete">
                                <IconButton onClick={handleDeleteClick} size="small">
                                    <DeleteIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>

                    {cardFields.find(f => f.id === 'bucket')?.visible && connector.settings?.bucket && (
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            Bucket: {connector.settings.bucket}
                        </Typography>
                    )}

                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        {connector.description || 'No description provided'}
                    </Typography>

                    <Box sx={{ mt: 2 }}>
                        {cardFields.find(f => f.id === 'storage')?.visible && (
                            <Typography variant="body2" color="text.secondary">
                                Storage: {formatBytes(connector.usage?.total || 0)}
                            </Typography>
                        )}
                        {cardFields.find(f => f.id === 'lastUpdated')?.visible && (
                            <Typography variant="body2" color="text.secondary">
                                Last Updated: {formatDate(connector.updatedAt)}
                            </Typography>
                        )}
                        {cardFields.find(f => f.id === 'status')?.visible && (
                            <Box sx={{ mt: 1 }}>
                                <Chip
                                    size="small"
                                    label={connector.status || 'active'}
                                    color={connector.status === 'error' ? 'error' : 'success'}
                                    sx={{ textTransform: 'capitalize' }}
                                />
                            </Box>
                        )}
                    </Box>
                </CardContent>
            </Card>

            <CardFieldsMenu />
            <CardSortMenu />
            <ViewDetailsDialog />

            {/* Delete Confirmation Dialog */}
            <Dialog
                open={deleteDialogOpen}
                onClose={() => setDeleteDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Delete Connector</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete the connector "{connector.name}"? This action cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={() => setDeleteDialogOpen(false)}
                        disabled={isDeleting}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleDeleteConfirm}
                        color="error"
                        variant="contained"
                        disabled={isDeleting}
                    >
                        {isDeleting ? 'Deleting...' : 'Delete'}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default ConnectorCard;

