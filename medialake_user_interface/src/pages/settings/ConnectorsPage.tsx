import React, { useState } from 'react';
import { Grid, Typography, Button, Box, Snackbar, Alert } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import ConnectorCard from '@/features/settings/connectors/components/ConnectorCard';
import ConnectorModal from '@/features/settings/connectors/components/ConnectorModal';
import { useGetConnectors, useDeleteConnector } from '@/api/hooks/useConnectors';
import { ConnectorResponse, CreateConnectorRequest } from '@/api/types/api.types';
import { useQueryClient } from '@tanstack/react-query';

const ConnectorsPage: React.FC = () => {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingConnector, setEditingConnector] = useState<ConnectorResponse | undefined>();
    const [alert, setAlert] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);
    const queryClient = useQueryClient();

    const { data: connectorsResponse, isLoading } = useGetConnectors();
    const { mutateAsync: deleteConnector } = useDeleteConnector();

    const handleAddClick = () => {
        setEditingConnector(undefined);
        setIsModalOpen(true);
    };

    const handleEditClick = (connector: ConnectorResponse) => {
        setEditingConnector(connector);
        setIsModalOpen(true);
    };

    const handleModalClose = () => {
        setIsModalOpen(false);
        setEditingConnector(undefined);
    };

    const handleDelete = async (id: string) => {
        try {
            await deleteConnector(id);
            // Invalidate the connectors query to trigger a refresh
            await queryClient.invalidateQueries({ queryKey: ['connectors'] });
            setAlert({ message: 'Connector deleted successfully', severity: 'success' });
        } catch (error) {
            setAlert({ message: 'Failed to delete connector', severity: 'error' });
        }
    };

    const handleSave = async (connectorData: CreateConnectorRequest): Promise<void> => {
        // try {
        //     const response = await fetch('/api/connectors', {
        //         method: 'POST',
        //         headers: {
        //             'Content-Type': 'application/json',
        //         },
        //         body: JSON.stringify(connectorData),
        //     });

        //     const data = await response.json();

        //     if (response.status === 200 && data.status === 200 && data.message === 'ok') {
        //         setAlert({ message: 'Connector created successfully', severity: 'success' });
        //         // Invalidate the connectors query to trigger a refresh
        //         await queryClient.invalidateQueries({ queryKey: ['connectors'] });
        //         handleModalClose();
        //     } else {
        //         setAlert({ message: 'Connector creation failed', severity: 'error' });
        //     }
        // } catch (error) {
        //     setAlert({ message: 'Connector creation failed', severity: 'error' });
        // }
    };

    const handleAlertClose = () => {
        setAlert(null);
    };

    if (isLoading) {
        return <div>Loading...</div>;
    }

    const connectors = connectorsResponse?.data?.connectors || [];

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h5">Connectors</Typography>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAddClick}
                >
                    Add Connector
                </Button>
            </Box>

            <Grid container spacing={3}>
                {connectors.map((connector) => (
                    <Grid item xs={12} sm={6} md={4} key={connector.id}>
                        <ConnectorCard
                            connector={connector}
                            onEdit={handleEditClick}
                            onDelete={handleDelete}
                        />
                    </Grid>
                ))}
            </Grid>

            <ConnectorModal
                open={isModalOpen}
                onClose={handleModalClose}
                onSave={handleSave}
                editingConnector={editingConnector}
            />

            <Snackbar
                open={!!alert}
                autoHideDuration={6000}
                onClose={handleAlertClose}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert
                    onClose={handleAlertClose}
                    severity={alert?.severity}
                    sx={{ width: '100%' }}
                >
                    {alert?.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default ConnectorsPage;
