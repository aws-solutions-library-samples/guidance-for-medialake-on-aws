import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    Paper,
    useTheme,
    alpha,
    Card,
    CardContent,
    Grid,
    Skeleton,
    Chip,
    Divider,
    Tooltip,
    Badge,
    Avatar,
    List,
    ListItem,
    ListItemAvatar,
    ListItemText,
    ListItemButton,
    InputAdornment,
    TextField,
    IconButton,
} from '@mui/material';
import {
    Storage as StorageIcon,
    CloudQueue as CloudIcon,
    CheckCircle as CheckCircleIcon,
    Search as SearchIcon,
    Clear as ClearIcon,
} from '@mui/icons-material';
import { useGetConnectors } from '../api/hooks/useConnectors';
import AssetExplorer from '../features/assets/AssetExplorer';

const AssetsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [selectedConnector, setSelectedConnector] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState<string>('');
    
    const { data: connectorsResponse, isLoading } = useGetConnectors();
    const connectors = connectorsResponse?.data.connectors || [];
    
    const handleConnectorSelect = (connectorId: string) => {
        console.log('[AssetsPage] Connector selected:', connectorId);
        
        // Find the selected connector to check for prefix
        const selectedConnectorData = connectors.find(c => c.id === connectorId);
        if (selectedConnectorData) {
            // Log connector details including any prefix information
            console.log('[AssetsPage] Selected connector details:', {
                name: selectedConnectorData.name,
                type: selectedConnectorData.type,
                storageIdentifier: selectedConnectorData.storageIdentifier,
                // Log the objectPrefix property
                objectPrefix: selectedConnectorData.objectPrefix || 'No objectPrefix property found',
                // Log the entire object to see all available properties
                fullObject: selectedConnectorData
            });
        }
        
        setSelectedConnector(connectorId);
    };

    // Function to get a connector type icon
    const getConnectorTypeIcon = (type: string) => {
        switch (type.toLowerCase()) {
            case 's3':
                return <CloudIcon fontSize="small" />;
            default:
                return <StorageIcon fontSize="small" />;
        }
    };

    // Filter connectors based on search term
    const filteredConnectors = connectors.filter(connector => 
        connector.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        connector.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        connector.storageIdentifier?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h4" sx={{
                fontWeight: 700,
                mb: 3,
                background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
            }}>
                {t('assets.title')}
            </Typography>

            <Box sx={{ display: 'flex', gap: 3, height: 'calc(100% - 60px)' }}>
                {/* Left panel - Connectors list */}
                <Paper elevation={0} sx={{
                    width: 280,
                    borderRadius: '12px',
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    backgroundColor: theme.palette.background.paper,
                    display: 'flex',
                    flexDirection: 'column',
                }}>
                    <Box sx={{ p: 1.5, borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}` }}>
                        <Box sx={{ 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center',
                            mb: 1.5
                        }}>
                            <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                {t('assets.connectedStorage')}
                            </Typography>
                            <Chip 
                                label={`${connectors.length}`}
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                        </Box>
                        
                        <TextField
                            placeholder="Search connectors..."
                            size="small"
                            fullWidth
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon fontSize="small" color="action" />
                                    </InputAdornment>
                                ),
                                endAdornment: searchTerm && (
                                    <InputAdornment position="end">
                                        <IconButton 
                                            size="small" 
                                            onClick={() => setSearchTerm('')}
                                            edge="end"
                                        >
                                            <ClearIcon fontSize="small" />
                                        </IconButton>
                                    </InputAdornment>
                                ),
                                sx: {
                                    borderRadius: '8px',
                                    backgroundColor: alpha(theme.palette.common.black, 0.03),
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.common.black, 0.05),
                                    },
                                }
                            }}
                            sx={{
                                '& .MuiOutlinedInput-notchedOutline': {
                                    border: 'none',
                                }
                            }}
                        />
                    </Box>
                    
                    {isLoading ? (
                        <Box sx={{ p: 2 }}>
                            {[1, 2, 3, 4, 5].map((item) => (
                                <Skeleton 
                                    key={item}
                                    variant="rectangular" 
                                    height={60} 
                                    sx={{ borderRadius: '8px', mb: 1 }} 
                                />
                            ))}
                        </Box>
                    ) : (
                        <List sx={{ 
                            overflow: 'auto',
                            flex: 1,
                            p: 0,
                            '& .MuiListItemButton-root': {
                                borderRadius: 0,
                                py: 0.75,
                                px: 1.5,
                                minHeight: '48px',
                            }
                        }}>
                            {filteredConnectors.length === 0 ? (
                                <Box sx={{ p: 3, textAlign: 'center' }}>
                                    <Typography color="text.secondary">
                                        No connectors found
                                    </Typography>
                                </Box>
                            ) : (
                                filteredConnectors.map((connector) => (
                                    <ListItemButton
                                        key={connector.id}
                                        selected={selectedConnector === connector.id}
                                        onClick={() => handleConnectorSelect(connector.id)}
                                        sx={{
                                            borderLeft: selectedConnector === connector.id 
                                                ? `3px solid ${theme.palette.primary.main}` 
                                                : '3px solid transparent',
                                            backgroundColor: selectedConnector === connector.id
                                                ? alpha(theme.palette.primary.main, 0.05)
                                                : 'transparent',
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.03),
                                            },
                                        }}
                                    >
                                        <ListItemAvatar sx={{ minWidth: '40px' }}>
                                            <Badge
                                                variant="dot"
                                                color="success"
                                                overlap="circular"
                                                anchorOrigin={{
                                                    vertical: 'bottom',
                                                    horizontal: 'right',
                                                }}
                                                sx={{
                                                    '& .MuiBadge-badge': {
                                                        backgroundColor: connector.status === 'active' 
                                                            ? theme.palette.success.main 
                                                            : theme.palette.warning.main,
                                                    }
                                                }}
                                            >
                                                <Avatar
                                                    sx={{
                                                        bgcolor: alpha(theme.palette.primary.main, 0.1),
                                                        color: theme.palette.primary.main,
                                                        width: 28,
                                                        height: 28,
                                                    }}
                                                >
                                                    {getConnectorTypeIcon(connector.type)}
                                                </Avatar>
                                            </Badge>
                                        </ListItemAvatar>
                                        <ListItemText
                                            primary={
                                                <Tooltip title={connector.name} arrow placement="top">
                                                    <Typography 
                                                        variant="body2" 
                                                        sx={{
                                                            fontWeight: 500,
                                                            color: selectedConnector === connector.id
                                                                ? theme.palette.primary.main
                                                                : theme.palette.text.primary,
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                        }}
                                                    >
                                                        {connector.name}
                                                    </Typography>
                                                </Tooltip>
                                            }
                                            secondary={
                                                <Box sx={{ 
                                                    display: 'flex', 
                                                    alignItems: 'center', 
                                                    justifyContent: 'space-between',
                                                    mt: 0.25
                                                }}>
                                                        <Typography 
                                                        variant="caption" 
                                                        color="text.secondary"
                                                        sx={{ 
                                                            display: 'block',
                                                            textTransform: 'uppercase',
                                                            fontSize: '0.6rem',
                                                            letterSpacing: 0.5,
                                                        }}
                                                    >
                                                        {connector.type}
                                                    </Typography>
                                                    <Tooltip title={connector.storageIdentifier || ''} arrow placement="top">
                                                        <Typography 
                                                            variant="caption" 
                                                            color="text.secondary"
                                                            sx={{ 
                                                                maxWidth: '100px',
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'nowrap',
                                                                display: 'block',
                                                                fontSize: '0.6rem',
                                                            }}
                                                        >
                                                            {connector.storageIdentifier || 'N/A'}
                                                        </Typography>
                                                    </Tooltip>
                                                </Box>
                                            }
                                        />
                                        {selectedConnector === connector.id && (
                                            <CheckCircleIcon 
                                                color="primary" 
                                                fontSize="small" 
                                                sx={{ ml: 1 }}
                                            />
                                        )}
                                    </ListItemButton>
                                ))
                            )}
                        </List>
                    )}
                </Paper>

                {/* Right panel - Connector Details */}
                {selectedConnector ? (
                    <Paper elevation={0} sx={{
                        flex: 1,
                        borderRadius: '12px',
                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        backgroundColor: theme.palette.background.paper,
                        overflow: 'hidden',
                    }}>
                        {(() => {
                            const connector = connectors.find(c => c.id === selectedConnector);
                            const storageId = connector?.storageIdentifier || '';
                            console.log('[AssetsPage] Using storageIdentifier for AssetExplorer:', storageId);
                            return <AssetExplorer storageIdentifier={storageId} />;
                        })()}
                    </Paper>
                ) : (
                    <Paper elevation={0} sx={{
                        flex: 1,
                        borderRadius: '12px',
                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        backgroundColor: theme.palette.background.paper,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        <Box sx={{ textAlign: 'center', p: 3 }}>
                            <StorageIcon sx={{ fontSize: 60, color: alpha(theme.palette.text.secondary, 0.3), mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                Select a connector to view its contents
                            </Typography>
                        </Box>
                    </Paper>
                )}
            </Box>
        </Box>
    );
};

export default AssetsPage;
