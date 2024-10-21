import React, { useState } from 'react';
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
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

const modalStyle = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 400,
    bgcolor: 'background.paper',
    boxShadow: 24,
    p: 4,
    borderRadius: 2,
};

const SettingsComponent = () => {
    const [openConnectorModal, setOpenConnectorModal] = useState(false);
    const [openIntegrationModal, setOpenIntegrationModal] = useState(false);
    const [connectorType, setConnectorType] = useState('');
    const [bucket, setBucket] = useState('');
    const [integrationType, setIntegrationType] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [connectors, setConnectors] = useState([]);
    const [integrations, setIntegrations] = useState([]);
    const [name, setName] = useState('');
    const [editingItem, setEditingItem] = useState(null);
    const [connectorPage, setConnectorPage] = useState(1);
    const [integrationPage, setIntegrationPage] = useState(1);

    const itemsPerPage = 6; // 2 rows of 3 cards

    const handleOpenConnectorModal = () => {
        setOpenConnectorModal(true);
        setEditingItem(null);
    };
    const handleCloseConnectorModal = () => {
        setOpenConnectorModal(false);
        resetForm();
    };
    const handleOpenIntegrationModal = () => {
        setOpenIntegrationModal(true);
        setEditingItem(null);
    };
    const handleCloseIntegrationModal = () => {
        setOpenIntegrationModal(false);
        resetForm();
    };

    const resetForm = () => {
        setConnectorType('');
        setBucket('');
        setIntegrationType('');
        setApiKey('');
        setName('');
        setEditingItem(null);
    };

    const handleConnectorSave = () => {
        const newConnector = {
            type: connectorType,
            bucket,
            name,
            createdDate: new Date().toISOString()
        };
        if (editingItem !== null) {
            const updatedConnectors = [...connectors];
            updatedConnectors[editingItem] = newConnector;
            setConnectors(updatedConnectors);
        } else {
            setConnectors([...connectors, newConnector]);
        }
        handleCloseConnectorModal();
    };

    const handleIntegrationSave = () => {
        const newIntegration = {
            type: integrationType,
            apiKey,
            name,
            createdDate: new Date().toISOString()
        };
        if (editingItem !== null) {
            const updatedIntegrations = [...integrations];
            updatedIntegrations[editingItem] = newIntegration;
            setIntegrations(updatedIntegrations);
        } else {
            setIntegrations([...integrations, newIntegration]);
        }
        handleCloseIntegrationModal();
    };

    const handleDelete = (index, isConnector) => {
        if (isConnector) {
            setConnectors(connectors.filter((_, i) => i !== index));
        } else {
            setIntegrations(integrations.filter((_, i) => i !== index));
        }
    };

    const handleEdit = (index, isConnector) => {
        const item = isConnector ? connectors[index] : integrations[index];
        setName(item.name);
        if (isConnector) {
            setConnectorType(item.type);
            setBucket(item.bucket);
            setOpenConnectorModal(true);
        } else {
            setIntegrationType(item.type);
            setApiKey(item.apiKey);
            setOpenIntegrationModal(true);
        }
        setEditingItem(index);
    };

    const renderCards = (items, isConnector) => {
        const startIndex = ((isConnector ? connectorPage : integrationPage) - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const paginatedItems = items.slice(startIndex, endIndex);

        return paginatedItems.map((item, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
                <Card>
                    <CardContent>
                        <Typography variant="h6">{item.name}</Typography>
                        <Typography>Type: {item.type}</Typography>
                        <Typography>Created: {new Date(item.createdDate).toLocaleDateString()}</Typography>
                        <Box sx={{ mt: 2 }}>
                            <IconButton aria-label="edit" onClick={() => handleEdit(startIndex + index, isConnector)}>
                                <EditIcon />
                            </IconButton>
                            <IconButton aria-label="delete" onClick={() => handleDelete(startIndex + index, isConnector)}>
                                <DeleteIcon />
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
                    {renderCards(connectors, true)}
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
                    {renderCards(integrations, false)}
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

            {/* Connector Modal */}
            <Modal open={openConnectorModal} onClose={handleCloseConnectorModal}>
                <Box sx={modalStyle}>
                    <IconButton
                        aria-label="close"
                        onClick={handleCloseConnectorModal}
                        sx={{ position: 'absolute', right: 8, top: 8 }}
                    >
                        <CloseIcon />
                    </IconButton>
                    <Typography variant="h6" component="h2" gutterBottom>
                        {editingItem !== null ? 'Edit Connector' : 'Add New Connector'}
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
                            value={connectorType}
                            label="Type"
                            onChange={(e) => setConnectorType(e.target.value)}
                        >
                            <MenuItem value="amazonS3">Amazon S3</MenuItem>
                            <MenuItem value="googleCloudStorage">Google Cloud Storage</MenuItem>
                        </Select>
                    </FormControl>
                    {connectorType === 'amazonS3' && (
                        <FormControl fullWidth sx={{ mt: 2 }}>
                            <InputLabel>Bucket</InputLabel>
                            <Select
                                value={bucket}
                                label="Bucket"
                                onChange={(e) => setBucket(e.target.value)}
                            >
                                <MenuItem value="bucket1">Sample Bucket 1</MenuItem>
                                <MenuItem value="bucket2">Sample Bucket 2</MenuItem>
                                <MenuItem value="bucket3">Sample Bucket 3</MenuItem>
                            </Select>
                        </FormControl>
                    )}
                    <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                        <Button onClick={handleCloseConnectorModal} sx={{ mr: 2 }}>
                            Cancel
                        </Button>
                        <Button variant="contained" onClick={handleConnectorSave}>
                            Save
                        </Button>
                    </Box>
                </Box>
            </Modal>

            {/* Integration Modal */}
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
                        {editingItem !== null ? 'Edit Integration' : 'Add New Integration'}
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
                            onChange={(e) => setIntegrationType(e.target.value)}
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
