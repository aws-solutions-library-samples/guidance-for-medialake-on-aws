import React, { useState } from 'react';
import {
    Card,
    CardHeader,
    CardContent,
    CardActions,
    Stack,
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
    AccessTime as AccessTimeIcon,
} from '@mui/icons-material';
import { ConnectorResponse } from '@/api/types/api.types';
import ConnectorEditModal from '@/features/settings/connectors/components/ConnectorEditModal';
import { useDateFormat } from '@/shared/hooks/useDateFormat';

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
    showSeconds?: boolean;
    allowSecondsToggle?: boolean;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({
    connector,
    onEdit,
    onDelete,
    onToggleStatus,
    showSeconds: initialShowSeconds = false,
    allowSecondsToggle = true,
}) => {
    const theme = useTheme();
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [editModalOpen, setEditModalOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    
    const { 
        formattedDate, 
        absoluteDate,
        showSeconds,
        toggleSeconds,
        canToggleSeconds
    } = useDateFormat(connector.updatedAt, {
        showRelative: false,
        showSeconds: initialShowSeconds,
        allowSecondsToggle,
        updateInterval: 60000,
    });

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
        if (type === 's3') {
            return <CloudUploadIcon sx={{ color: '#FF9900' }} />;
        }
        return null;
    };

    const getConnectorTypeLabel = (type: string) => {
        if (type === 's3') {
            return 'Amazon S3';
        }
        return type;
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

                <CardHeader

                    title={
                        <Stack direction="row" alignItems="center" spacing={1}>
                            {getConnectorIcon(connector.type)}
                            <Typography variant="h5">{connector.name}</Typography>
                        </Stack>
                    }
                    subheader={
                        <Stack direction="row" sx={{
                            justifyContent: "space-between",
                            alignItems: "center",
                        }} spacing={1}>
                            {getConnectorTypeLabel(connector.type)}
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
                        </Stack>
                    }
                    titleTypographyProps={{ marginBottom: 1 }}
                    subheaderTypographyProps={{ marginTop: 1 }}
                />
                {/* <CardHeader

                    action={
                        <Stack direction="row" spacing={2}>
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

                            > <EditIcon fontSize="small" /></IconButton>
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
                        </Stack>
                    }

                /> */}
                <CardContent sx={{ flexGrow: 1 }}>

                    <Typography variant="body2" >
                        <strong>Bucket:</strong> {connector.storageIdentifier}
                    </Typography>
                    {connector.region && (
                        <Typography variant="body2">
                            <strong>Region:</strong> {connector.region}
                        </Typography>
                    )}
                    {connector.description && (
                        <Typography variant="body2" >
                            <strong>Description:</strong> {connector.description}
                        </Typography>
                    )}

                    <Box sx={{ mt: 2 }}>
                        {connector.usage?.total !== undefined && (
                            <Typography variant="body2" >
                                <strong>Storage:</strong> {formatBytes(connector.usage.total)}
                            </Typography>
                        )}
                        <Typography 
                            variant="body2" 
                            onClick={canToggleSeconds ? toggleSeconds : undefined}
                            sx={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: 0.5,
                                cursor: canToggleSeconds ? 'pointer' : 'default',
                                ...(canToggleSeconds && {
                                    '&:hover': {
                                        color: theme.palette.primary.main,
                                    },
                                }),
                            }}
                        >
                            <Tooltip 
                                title={canToggleSeconds ? `Click to ${showSeconds ? 'hide' : 'show'} seconds` : absoluteDate}
                                arrow 
                                placement="top"
                                enterDelay={200}
                                leaveDelay={200}
                            >
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <AccessTimeIcon 
                                        sx={{ 
                                            fontSize: 16, 
                                            color: showSeconds ? theme.palette.primary.main : theme.palette.text.secondary 
                                        }} 
                                    />
                                    <strong>Last Updated:</strong> {formattedDate}
                                </Box>
                            </Tooltip>
                        </Typography>
                    </Box>
                </CardContent>

                <CardActions
                    sx={{
                        justifyContent: "flex-end",
                        alignItems: "flex-end",
                        borderTop: `1px solid ${theme.palette.divider}`,
                        pt: 2
                    }} >
                    <Stack direction="row"
                        spacing={2}
                    >
                        {/* <IconButton
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

                        > <EditIcon fontSize="small" /></IconButton>
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
                        </IconButton> */}
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
                    </Stack>
                </CardActions>
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
