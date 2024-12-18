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
    useTheme,
    alpha,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    CloudUpload as CloudUploadIcon,
    PowerSettingsNew as PowerIcon,
} from '@mui/icons-material';
import { ConnectorResponse } from '@/api/types/api.types';
import ConnectorEditModal from '@/features/settings/connectors/components/ConnectorEditModal';

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
    onToggleStatus: (id: string, enabled: boolean) => Promise<void>;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({
    connector,
    onEdit,
    onDelete,
    onToggleStatus,
}) => {
    const theme = useTheme();
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [editModalOpen, setEditModalOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

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

    const handleToggleStatus = async () => {
        await onToggleStatus(connector.id, connector.status === 'disabled');
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
                                <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.primary.main }}>
                                    {connector.name}
                                </Typography>
                                <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                    {getConnectorTypeLabel(connector.type)}
                                </Typography>
                            </Box>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Tooltip title="Edit">
                                <IconButton
                                    onClick={() => setEditModalOpen(true)}
                                    size="small"
                                    sx={{
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                        width: 40,
                                        height: 40,
                                        '&:hover': {
                                            backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                        },
                                    }}
                                >
                                    <EditIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title={connector.status === 'disabled' ? 'Enable' : 'Disable'}>
                                <IconButton
                                    onClick={handleToggleStatus}
                                    size="small"
                                    sx={{
                                        backgroundColor: alpha(
                                            connector.status === 'disabled'
                                                ? theme.palette.success.main
                                                : theme.palette.warning.main,
                                            0.1
                                        ),
                                        width: 40,
                                        height: 40,
                                        '&:hover': {
                                            backgroundColor: alpha(
                                                connector.status === 'disabled'
                                                    ? theme.palette.success.main
                                                    : theme.palette.warning.main,
                                                0.2
                                            ),
                                        },
                                    }}
                                >
                                    <PowerIcon fontSize="small" />
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
                                        },
                                    }}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Box>
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary, mb: 1 }}>
                        Bucket: {connector.storageIdentifier}
                    </Typography>
                    {connector.region && (
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary, mb: 1 }}>
                            Region: {connector.region}
                        </Typography>
                    )}
                    {connector.description && (
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary, mb: 1 }}>
                            {connector.description}
                        </Typography>
                    )}

                    <Box sx={{ mt: 2 }}>
                        {connector.usage?.total !== undefined && (
                            <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                Storage: {formatBytes(connector.usage.total)}
                            </Typography>
                        )}
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                            Last Updated: {formatDate(connector.updatedAt)}
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                            <Chip
                                size="small"
                                label={connector.status || 'active'}
                                sx={{
                                    backgroundColor:
                                        connector.status === 'error'
                                            ? alpha(theme.palette.error.main, 0.1)
                                            : connector.status === 'disabled'
                                                ? alpha(theme.palette.warning.main, 0.1)
                                                : alpha(theme.palette.success.main, 0.1),
                                    color:
                                        connector.status === 'error'
                                            ? theme.palette.error.main
                                            : connector.status === 'disabled'
                                                ? theme.palette.warning.main
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
                    </Box>
                </CardContent>
            </Card>

            <ConnectorEditModal
                open={editModalOpen}
                connector={connector}
                onClose={() => setEditModalOpen(false)}
                onSave={onEdit}
            />

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
