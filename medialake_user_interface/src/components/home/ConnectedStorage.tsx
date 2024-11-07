import React from 'react';
import { Grid, Typography, Box, CircularProgress, useTheme, Alert } from '@mui/material';
import { useGetConnectors } from '../../api/hooks/useConnectors';
import { ConnectorCard } from './ConnectorCard';
import StorageIcon from '@mui/icons-material/Storage';

export const ConnectedStorage: React.FC = () => {
    const theme = useTheme();
    const { data, isLoading, error } = useGetConnectors();

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: 200,
                    width: '100%'
                }}
            >
                <CircularProgress
                    size={40}
                    thickness={4}
                    sx={{
                        color: theme.palette.primary.main
                    }}
                />
            </Box>
        );
    }

    if (error) {
        return (
            <Alert
                severity="error"
                sx={{
                    borderRadius: 2,
                    '& .MuiAlert-icon': {
                        fontSize: 28
                    }
                }}
            >
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                    Error loading connectors
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {error.message}
                </Typography>
            </Alert>
        );
    }

    // Add error handling for missing or malformed data
    if (!data?.data) {
        return (
            <Alert
                severity="error"
                sx={{
                    borderRadius: 2,
                    '& .MuiAlert-icon': {
                        fontSize: 28
                    }
                }}
            >
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                    Invalid data format
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                    Unable to load connectors due to invalid data format
                </Typography>
            </Alert>
        );
    }

    const connectors = data.data.connectors || [];

    return (
        <Box>
            <Typography
                variant="h5"
                component="h2"
                gutterBottom
                sx={{
                    fontWeight: 600,
                    color: theme.palette.primary.main,
                    mb: 3,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1
                }}
            >
                <StorageIcon sx={{ fontSize: 28 }} />
                Connected Storage
            </Typography>

            {connectors.length === 0 ? (
                <Alert
                    severity="info"
                    sx={{
                        borderRadius: 2,
                        backgroundColor: 'rgba(2, 136, 209, 0.08)',
                        '& .MuiAlert-icon': {
                            fontSize: 28
                        }
                    }}
                >
                    <Typography variant="body1">
                        No storage connectors found. Add a new storage connector to get started.
                    </Typography>
                </Alert>
            ) : (
                <Grid
                    container
                    spacing={3}
                    sx={{
                        '& .MuiGrid-item': {
                            display: 'flex'
                        }
                    }}
                >
                    {connectors.map((connector) => (
                        <Grid
                            item
                            xs={12}
                            sm={6}
                            md={4}
                            key={connector.id}
                        >
                            <Box sx={{ width: '100%' }}>
                                <ConnectorCard connector={connector} />
                            </Box>
                        </Grid>
                    ))}
                </Grid>
            )}
        </Box>
    );
};
