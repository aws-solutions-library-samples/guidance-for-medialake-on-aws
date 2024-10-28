import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Grid,
    Card,
    CardContent,
    Button,
    Modal,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    IconButton,
    Pagination,
    SelectChangeEvent,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import { useCreateConnector, useUpdateConnector, useDeleteConnector, useGetConnectors } from './api/hooks/useConnectors';
import { ConnectorResponse, CreateConnectorRequest, Integration } from './api/types/api.types';
import { useAuth } from './common/hooks/auth-context';
import ConnectorCard from './components/settings/ConnectorCard';
import { ConnectorModal } from './components/settings/ConnectorModal';

const modalStyle = {
    position: 'absolute' as const,
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 400,
    bgcolor: 'background.paper',
    boxShadow: 24,
    p: 4,
    borderRadius: 2,
};

const SettingsComponent: React.FC = () => {
    const [openConnectorModal, setOpenConnectorModal] = useState<boolean>(false);
    const [openIntegrationModal, setOpenIntegrationModal] = useState<boolean>(false);
    const [integrationType, setIntegrationType] = useState<string>('');
    const [apiKey, setApiKey] = useState<string>('');
    const [connectors, setConnectors] = useState<ConnectorResponse[]>([]);
    const [integrations, setIntegrations] = useState<Integration[]>([]);
    const [name, setName] = useState<string>('');
    const [editingConnector, setEditingConnector] = useState<ConnectorResponse | null>(null);
    const [connectorPage, setConnectorPage] = useState<number>(1);
    const [integrationPage, setIntegrationPage] = useState<number>(1);

    const { isAuthenticated } = useAuth();
    const { data: connectorsData, refetch: refetchConnectors } = useGetConnectors();
    const { mutateAsync: createConnector } = useCreateConnector();
    const { mutateAsync: updateConnector } = useUpdateConnector();
    const { mutateAsync: deleteConnector } = useDeleteConnector();

    const itemsPerPage = 6;

    useEffect(() => {
        if (connectorsData?.data?.connectors) {
            setConnectors(Array.isArray(connectorsData.data.connectors) 
                ? connectorsData.data.connectors 
                : []);
        }
    }, [connectorsData]);

    const handleOpenConnectorModal = () => {
        setOpenConnectorModal(true);
        setEditingConnector(null);
    };

    const handleCloseConnectorModal = () => {
        setOpenConnectorModal(false);
        setEditingConnector(null);
    };

    const handleConnectorSave = async (connectorData: CreateConnectorRequest) => {
        try {
            if (editingConnector) {
                await updateConnector({
                    id: editingConnector.id,
                    data: connectorData
                });
            } else {
                await createConnector(connectorData);
            }
            await refetchConnectors();
            handleCloseConnectorModal();
        } catch (error) {
            console.error('Error saving connector:', error);
        }
    };

    const handleConnectorDelete = async (id: string) => {
        try {
            await deleteConnector(id);
            await refetchConnectors();
        } catch (error) {
            console.error('Error deleting connector:', error);
        }
    };

    const handleConnectorEdit = (connector: ConnectorResponse) => {
        setEditingConnector(connector);
        setOpenConnectorModal(true);
    };

    const handleOpenIntegrationModal = () => {
        setOpenIntegrationModal(true);
    };

    const handleCloseIntegrationModal = () => {
        setOpenIntegrationModal(false);
        setName('');
        setIntegrationType('');
        setApiKey('');
    };

    const handleIntegrationSave = () => {
        const newIntegration: Integration = {
            id: Date.now().toString(),
            type: integrationType,
            apiKey,
            name,
            createdDate: new Date().toISOString()
        };
        setIntegrations([...integrations, newIntegration]);
        handleCloseIntegrationModal();
    };

    const handleIntegrationDelete = (id: string) => {
        setIntegrations(integrations.filter(i => i.id !== id));
    };

    const renderConnectors = () => {
        if (!Array.isArray(connectors)) {
            return null;
        }
    
        const startIndex = (connectorPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const paginatedConnectors = connectors.slice(startIndex, endIndex);
    
        return paginatedConnectors.map((connector) => (
            <Grid item xs={12} sm={6} md={4} key={connector.id}>
                <ConnectorCard
                    connector={connector}
                    onEdit={handleConnectorEdit}
                    onDelete={handleConnectorDelete}
                />
            </Grid>
        ));
    };

    const renderIntegrations = () => {
        const startIndex = (integrationPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const paginatedIntegrations = integrations.slice(startIndex, endIndex);

        return paginatedIntegrations.map((integration) => (
            <Grid item xs={12} sm={6} md={4} key={integration.id}>
                <Card>
                    <CardContent>
                        <Typography variant="h6">{integration.name}</Typography>
                        <Typography>Type: {integration.type}</Typography>
                        <Typography>
                            Created: {new Date(integration.createdDate).toLocaleDateString()}
                        </Typography>
                        <Box sx={{ mt: 2 }}>
                            <IconButton
                                aria-label="delete"
                                onClick={() => handleIntegrationDelete(integration.id)}
                            >
                                <CloseIcon />
                            </IconButton>
                        </Box>
                    </CardContent>
                </Card>
            </Grid>
        ));
    };

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h5" gutterBottom>
                    Connectors
                </Typography>
                <Grid container spacing={2}>
                    {renderConnectors()}
                    {connectors.length < itemsPerPage && (
                        <Grid item xs={12} sm={6} md={4}>
                            <Card sx={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                <CardContent>
                                    <Button
                                        variant="outlined"
                                        startIcon={<AddIcon />}
                                        onClick={handleOpenConnectorModal}
                                    >
                                        Add new connector
                                    </Button>
                                </CardContent>
                            </Card>
                        </Grid>
                    )}
                </Grid>
                {connectors.length > itemsPerPage && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <Pagination
                            count={Math.ceil(connectors.length / itemsPerPage)}
                            page={connectorPage}
                            onChange={(event, value) => setConnectorPage(value)}
                            color="primary"
                        />
                    </Box>
                )}
            </Box>

            <Box sx={{ mb: 4, mt: 4 }}>
                <Typography variant="h5" gutterBottom>
                    Integrations
                </Typography>
                <Grid container spacing={2}>
                    {renderIntegrations()}
                    {integrations.length < itemsPerPage && (
                        <Grid item xs={12} sm={6} md={4}>
                            <Card sx={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                <CardContent>
                                    <Button
                                        variant="outlined"
                                        startIcon={<AddIcon />}
                                        onClick={handleOpenIntegrationModal}
                                    >
                                        Add new integration
                                    </Button>
                                </CardContent>
                            </Card>
                        </Grid>
                    )}
                </Grid>
                {integrations.length > itemsPerPage && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <Pagination
                            count={Math.ceil(integrations.length / itemsPerPage)}
                            page={integrationPage}
                            onChange={(event, value) => setIntegrationPage(value)}
                            color="primary"
                        />
                    </Box>
                )}
            </Box>

            <ConnectorModal
                open={openConnectorModal}
                onClose={handleCloseConnectorModal}
                onSave={handleConnectorSave}
                editingConnector={editingConnector || undefined}
            />

            <Modal open={openIntegrationModal} onClose={handleCloseIntegrationModal}>
                <Box sx={modalStyle}>
                    <IconButton
                        aria-label="close"
                        onClick={handleCloseIntegrationModal}
                        sx={{ position: 'absolute', right: 8, top: 8 }}
                    >
                        <CloseIcon />
                    </IconButton>
                    <Typography variant="h6" component="h2" gutterBottom>
                        Add New Integration
                    </Typography>
                    <TextField
                        fullWidth
                        label="Name"
                        variant="outlined"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        sx={{ mt: 2 }}
                    />
                    <FormControl fullWidth sx={{ mt: 2 }}>
                        <InputLabel>Type</InputLabel>
                        <Select
                            value={integrationType}
                            label="Type"
                            onChange={(e: SelectChangeEvent<string>) => setIntegrationType(e.target.value)}
                        >
                            <MenuItem value="twelveLabs">Twelve Labs Embeddings API</MenuItem>
                        </Select>
                    </FormControl>
                    {integrationType === 'twelveLabs' && (
                        <TextField
                            fullWidth
                            label="API Key"
                            variant="outlined"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            sx={{ mt: 2 }}
                        />
                    )}
                    <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                        <Button onClick={handleCloseIntegrationModal} sx={{ mr: 2 }}>
                            Cancel
                        </Button>
                        <Button variant="contained" onClick={handleIntegrationSave}>
                            Save
                        </Button>
                    </Box>
                </Box>
            </Modal>
        </Box>
    );
};

export default SettingsComponent;
