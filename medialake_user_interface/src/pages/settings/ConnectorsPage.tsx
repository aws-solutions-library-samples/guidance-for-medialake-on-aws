import React, { useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { ConnectorsList } from '../../components/ConnectorsList';
import ConnectorModal from '../../components/settings/ConnectorModal';
import { ConnectorResponse, CreateConnectorRequest } from '../../api/types/api.types';
import { useCreateConnector } from '../../api/hooks/useConnectors';

const ConnectorsPage: React.FC = () => {
    const [openConnectorModal, setOpenConnectorModal] = useState(false);
    const [editingConnector, setEditingConnector] = useState<ConnectorResponse | undefined>();
    const createConnector = useCreateConnector();

    const handleAddConnector = () => {
        console.log('Opening connector modal'); // Debug log
        setEditingConnector(undefined);
        setOpenConnectorModal(true);
    };

    const handleSaveConnector = async (connectorData: CreateConnectorRequest) => {
        try {
            await createConnector.mutateAsync(connectorData);
            setOpenConnectorModal(false);
            setEditingConnector(undefined);
        } catch (err) {
            console.error('Failed to save connector:', err);
        }
    };

    return (
        <Box>
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                        Storage Connectors
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Manage your storage connections and data sources
                    </Typography>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleAddConnector}
                >
                    Add Connector
                </Button>
            </Box>

            <ConnectorsList />

            <ConnectorModal
                open={openConnectorModal}
                onClose={() => {
                    console.log('Closing connector modal'); // Debug log
                    setOpenConnectorModal(false);
                    setEditingConnector(undefined);
                }}
                onSave={handleSaveConnector}
                editingConnector={editingConnector}
            />
        </Box>
    );
};

export default ConnectorsPage;
