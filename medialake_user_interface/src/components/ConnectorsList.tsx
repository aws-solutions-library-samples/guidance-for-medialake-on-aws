import { Suspense } from 'react';
import { Box, CircularProgress, Typography, Grid } from '@mui/material';
import { useGetConnectors, useDeleteConnector } from '../api/hooks/useConnectors';
import { ConnectorCard } from './settings/ConnectorCard';
import { ConnectorResponse, ConnectorListResponse } from '../api/types/api.types';
import { UseQueryResult } from '@tanstack/react-query';

export const ConnectorsList = () => {
    return (
        <Suspense fallback={<LoadingSpinner />}>
            <ConnectorsListContent />
        </Suspense>
    );
};

const LoadingSpinner = () => (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
    </Box>
);

const ConnectorsListContent = () => {
    const { 
        data: connectorsData, 
        isLoading, 
        error 
    }: UseQueryResult<ConnectorListResponse, Error> = useGetConnectors();
    
    const deleteConnector = useDeleteConnector();

    const handleEdit = (connector: ConnectorResponse) => {
        // TODO: Implement edit functionality
        console.log('Edit connector:', connector);
    };

    const handleDelete = async (id: string) => {
        try {
            await deleteConnector.mutateAsync(id);
        } catch (error) {
            console.error('Failed to delete connector:', error);
        }
    };

    if (isLoading) {
        return <LoadingSpinner />;
    }

    if (error) {
        return (
            <Box p={3}>
                <Typography color="error">
                    Error loading connectors: {error.message}
                </Typography>
            </Box>
        );
    }

    const connectors = connectorsData?.data?.connectors || [];

    if (connectors.length === 0) {
        return (
            <Box p={3}>
                <Typography>No connectors found.</Typography>
            </Box>
        );
    }

    return (
        <Box p={3}>
            <Grid container spacing={3}>
                {connectors.map(connector => (
                    <Grid item xs={12} sm={6} md={4} key={connector.id}>
                        <ConnectorCard
                            connector={connector}
                            onEdit={handleEdit}
                            onDelete={handleDelete}
                        />
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};
