import React, { useState } from 'react';
import { Typography, Button, Box, Snackbar, Alert } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import ConnectorCard from '@/features/settings/connectors/components/ConnectorCard';
import ConnectorModal from '@/features/settings/connectors/components/ConnectorModal';
import { useGetConnectors, useDeleteConnector, useToggleConnector, useCreateS3Connector } from '@/api/hooks/useConnectors';
import { ConnectorResponse, CreateConnectorRequest } from '@/api/types/api.types';
import queryClient from '@/api/queryClient';

const ConnectorsPage: React.FC = () => {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingConnector, setEditingConnector] = useState<ConnectorResponse | undefined>();
    const [alert, setAlert] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

    const { data: connectorsResponse, isLoading } = useGetConnectors();
    const { mutateAsync: deleteConnector } = useDeleteConnector();
    const { mutateAsync: toggleConnector } = useToggleConnector();
    const { mutateAsync: createS3Connector, isPending: isCreatingConnector } = useCreateS3Connector();

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
            await queryClient.invalidateQueries({ queryKey: ['connectors'] });
            setAlert({ message: 'Connector deleted successfully', severity: 'success' });
        } catch (error) {
            setAlert({ message: 'Failed to delete connector', severity: 'error' });
        }
    };

    const handleToggleStatus = async (id: string, enabled: boolean) => {
        try {
            await toggleConnector({ id, enabled });
            setAlert({
                message: `Connector ${enabled ? 'enabled' : 'disabled'} successfully`,
                severity: 'success'
            });
        } catch (error) {
            setAlert({
                message: `Failed to ${enabled ? 'enable' : 'disable'} connector`,
                severity: 'error'
            });
        }
    };

    const handleSave = async (connectorData: CreateConnectorRequest): Promise<void> => {
        try {
            if (connectorData.type === 's3') {
                const response = await createS3Connector(connectorData);
                console.log('API Response:', response);
                if (response && response.data) {
                    handleModalClose();
                    setAlert({
                        message: 'Connector created successfully',
                        severity: 'success'
                    });
                } else {
                    throw new Error('Invalid response from server');
                }
            }
        } catch (error) {
            console.error('Error creating connector:', error);
            setAlert({
                message: 'Failed to create connector',
                severity: 'error'
            });
        }
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

            <Box sx={{
                display: 'grid',
                gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(auto-fill, minmax(300px, 1fr))',
                    md: 'repeat(auto-fill, minmax(350px, 1fr))'
                },
                gap: 3
            }}>
                {connectors.map((connector) => {
                    console.log('Connector data:', JSON.stringify(connector, null, 2));
                    return (
                        <Box key={connector.id}>
                            <ConnectorCard
                                connector={connector}
                                onEdit={handleEditClick}
                                onDelete={handleDelete}
                                onToggleStatus={handleToggleStatus}
                            />
                        </Box>
                    );
                })}
            </Box>

            <ConnectorModal
                open={isModalOpen}
                onClose={handleModalClose}
                editingConnector={editingConnector}
                onSave={handleSave}
                isCreating={isCreatingConnector}
            />

            <Snackbar
                open={!!alert}
                autoHideDuration={6000}
                onClose={handleAlertClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
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
