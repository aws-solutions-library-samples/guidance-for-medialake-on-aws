import React from 'react';
import {
    Card,
    CardContent,
    Typography,
    Box,
    IconButton,
    Chip,
    useTheme,
    Tooltip,
    Button,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    Api as ApiIcon,
    YouTube as YouTubeIcon,
    Cloud as CloudIcon,
    PhotoLibrary as PhotoIcon,
    Settings as SettingsIcon,
    Check as CheckIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import { Integration } from '@/api/types/api.types';

interface IntegrationCardProps {
    integration: Integration;
    onEdit: (integration: Integration) => void;
    onDelete: (id: string) => void;
    onConfigure: (integration: Integration) => void;
}

const IntegrationCard: React.FC<IntegrationCardProps> = ({
    integration,
    onEdit,
    onDelete,
    onConfigure,
}) => {
    const theme = useTheme();

    const getIntegrationIcon = (type: string) => {
        switch (type.toLowerCase()) {
            case 'youtube':
                return <YouTubeIcon />;
            case 'cloudinary':
                return <CloudIcon />;
            case 'shutterstock':
                return <PhotoIcon />;
            default:
                return <ApiIcon />;
        }
    };

    const getIntegrationColor = (type: string) => {
        switch (type.toLowerCase()) {
            case 'youtube':
                return '#FF0000';
            case 'cloudinary':
                return '#3448C5';
            case 'shutterstock':
                return '#EE2B24';
            default:
                return theme.palette.primary.main;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'active':
                return theme.palette.success.main;
            case 'warning':
                return theme.palette.warning.main;
            case 'error':
                return theme.palette.error.main;
            default:
                return theme.palette.grey[500];
        }
    };

    return (
        <Card
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: theme.shadows[4],
                },
            }}
        >
            <CardContent sx={{ flex: 1, pb: 2 }}>
                {/* Header */}
                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box
                            sx={{
                                backgroundColor: `${getIntegrationColor(integration.type)}15`,
                                borderRadius: '8px',
                                p: 1,
                                display: 'flex',
                                alignItems: 'center',
                                color: getIntegrationColor(integration.type),
                            }}
                        >
                            {getIntegrationIcon(integration.type)}
                        </Box>
                        <Box>
                            <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                {integration.name}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                                {integration.type} Integration
                            </Typography>
                        </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title="Edit integration">
                            <IconButton
                                size="small"
                                onClick={() => onEdit(integration)}
                                sx={{ color: theme.palette.text.secondary }}
                            >
                                <EditIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete integration">
                            <IconButton
                                size="small"
                                onClick={() => onDelete(integration.id)}
                                sx={{ color: theme.palette.error.main }}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>
                </Box>

                {/* Status and Info */}
                <Box sx={{ mb: 3 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <Chip
                            icon={<CheckIcon fontSize="small" />}
                            label="Connected"
                            size="small"
                            sx={{
                                backgroundColor: `${theme.palette.success.main}15`,
                                color: theme.palette.success.main,
                                fontWeight: 500,
                            }}
                        />
                        <Typography variant="caption" color="text.secondary">
                            Last synced: {new Date(integration.createdAt).toLocaleDateString()}
                        </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        API Key: •••••••••{integration.apiKey.slice(-4)}
                    </Typography>
                </Box>

                {/* Actions */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 'auto' }}>
                    <Button
                        variant="outlined"
                        size="small"
                        startIcon={<SettingsIcon />}
                        onClick={() => onConfigure(integration)}
                        sx={{
                            borderColor: getIntegrationColor(integration.type),
                            color: getIntegrationColor(integration.type),
                            '&:hover': {
                                borderColor: getIntegrationColor(integration.type),
                                backgroundColor: `${getIntegrationColor(integration.type)}10`,
                            },
                        }}
                    >
                        Configure
                    </Button>
                    <Typography variant="caption" color="text.secondary">
                        Created {new Date(integration.createdAt).toLocaleDateString()}
                    </Typography>
                </Box>
            </CardContent>
        </Card>
    );
};

export default IntegrationCard;
