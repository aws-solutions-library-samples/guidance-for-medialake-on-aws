import React from 'react';
import { Connector } from '../../api/types/api.types';
import {
    Card,
    CardContent,
    Typography,
    Box,
    useTheme,
    Chip,
    CircularProgress,
    CardActionArea,
    Tooltip
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useS3Explorer } from '../../api/hooks/useS3Explorer';
import StorageIcon from '@mui/icons-material/Storage';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CategoryIcon from '@mui/icons-material/Category';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

interface ConnectorCardProps {
    connector: Connector;
}

export const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector }) => {
    const theme = useTheme();
    const navigate = useNavigate();

    const { isLoading } = useS3Explorer({
        connectorId: connector.id,
        prefix: '',
        delimiter: '/',
        continuationToken: null
    });

    const handleClick = () => {

        if (connector.type === 's3' && !isLoading) {
            navigate(`/s3/explorer/${connector.id}`);
        }
    };

    const getConnectorTypeColor = (type: string) => {
        switch (type.toLowerCase()) {
            case 's3':
                return theme.palette.primary.main;
            default:
                return theme.palette.secondary.main;
        }
    };

    return (
        <Card
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'all 0.3s ease-in-out',
                borderRadius: 2,
                overflow: 'hidden',
                border: '1px solid',
                borderColor: theme.palette.divider,
                opacity: isLoading ? 0.7 : 1,
                position: 'relative',
                '&:hover': {
                    transform: isLoading ? 'none' : 'translateY(-4px)',
                    boxShadow: isLoading ? theme.shadows[1] : theme.shadows[8],
                    '& .arrow-icon': {
                        transform: isLoading ? 'none' : 'translateX(4px)',
                    }
                }
            }}
        >
            <CardActionArea
                onClick={handleClick}
                disabled={isLoading}
                sx={{
                    height: '100%',
                    cursor: isLoading ? 'wait' : 'pointer'
                }}
            >
                <CardContent sx={{ p: 3, height: '100%' }}>
                    {isLoading && (
                        <Box
                            sx={{
                                position: 'absolute',
                                top: '50%',
                                left: '50%',
                                transform: 'translate(-50%, -50%)',
                                zIndex: 1
                            }}
                        >
                            <CircularProgress size={40} />
                        </Box>
                    )}

                    <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <StorageIcon
                                sx={{
                                    fontSize: 28,
                                    color: getConnectorTypeColor(connector.type)
                                }}
                            />
                            <Typography
                                variant="h6"
                                component="div"
                                sx={{
                                    fontWeight: 500,
                                    color: theme.palette.text.primary
                                }}
                            >
                                {connector.name}
                            </Typography>
                        </Box>
                        <ArrowForwardIcon
                            className="arrow-icon"
                            sx={{
                                color: theme.palette.text.secondary,
                                transition: 'transform 0.3s ease-in-out'
                            }}
                        />
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <CategoryIcon sx={{ fontSize: 20, color: theme.palette.text.secondary }} />
                            <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                            >
                                Type:
                                <Chip
                                    label={connector.type}
                                    size="small"
                                    sx={{
                                        backgroundColor: `${getConnectorTypeColor(connector.type)}15`,
                                        color: getConnectorTypeColor(connector.type),
                                        fontWeight: 500
                                    }}
                                />
                            </Typography>
                        </Box>

                        <Tooltip title={new Date(connector.createdAt).toLocaleString()}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AccessTimeIcon sx={{ fontSize: 20, color: theme.palette.text.secondary }} />
                                <Typography variant="body2" color="text.secondary">
                                    Created: {new Date(connector.createdAt).toLocaleDateString()}
                                </Typography>
                            </Box>
                        </Tooltip>
                    </Box>
                </CardContent>
            </CardActionArea>
        </Card>
    );
};
