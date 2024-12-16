import React, { useState } from 'react';
import {
    Box,
    Tabs,
    Tab,
    Typography,
    Paper,
    Button,
    useTheme,
    Alert,
} from '@mui/material';
import {
    Add as AddIcon,
    Storage as StorageIcon,
    Api as ApiIcon,
    Person as PersonIcon,
    AdminPanelSettings as AdminIcon,
    Group as GroupIcon,
} from '@mui/icons-material';
import { useGetConnectors, useCreateConnector, useUpdateConnector, useDeleteConnector } from '@/api/hooks/useConnectors';
import { Integration, ConnectorResponse, CreateConnectorRequest } from '@/api/types/api.types';
import { ConnectorsList } from '@/features/settings/connectors/components/ConnectorsList';
import ConnectorModal from '@/features/settings/connectors/components/ConnectorModal';
import UserProfile from '../components/settings/UserProfile';
import UserManagement from './settings/UserManagement';

interface TabPanelProps {
    readonly children?: React.ReactNode;
    readonly index: number;
    readonly value: number;
}

function TabPanel(props: Readonly<TabPanelProps>) {
    const { children, value, index, ...other } = props;

    return (
        <Box
            role="tabpanel"
            hidden={value !== index}
            id={`settings-tabpanel-${index}`}
            aria-labelledby={`settings-tab-${index}`}
            {...other}
            sx={{ pt: 3 }}
        >
            {value === index && children}
        </Box>
    );
}

const SettingsPage = () => {
    const theme = useTheme();
    const [activeTab, setActiveTab] = useState(0);
    const [openConnectorModal, setOpenConnectorModal] = useState(false);
    const [editingIntegration, setEditingIntegration] = useState<Integration | undefined>();
    const [editingConnector, setEditingConnector] = useState<ConnectorResponse | undefined>();
    const [integrations, setIntegrations] = useState<Integration[]>([]);
    const [error, setError] = useState<string | null>(null);

    const { data: connectorsData, isLoading: isLoadingConnectors } = useGetConnectors();
    const createConnector = useCreateConnector();
    const updateConnector = useUpdateConnector();
    const deleteConnector = useDeleteConnector();

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setActiveTab(newValue);
    };

    const handleAddConnector = () => {
        setEditingConnector(undefined);
        setOpenConnectorModal(true);
    };


    const handleSaveConnector = async (connectorData: CreateConnectorRequest) => {
        try {
            if (editingConnector) {
                await updateConnector.mutateAsync({
                    id: editingConnector.id,
                    data: {
                        name: connectorData.name,
                        type: connectorData.type,
                        configuration: connectorData.configuration,
                    }
                });
            } else {
                await createConnector.mutateAsync(connectorData);
            }
            setOpenConnectorModal(false);
            setEditingConnector(undefined);
        } catch (err) {
            setError('Failed to save connector. Please try again.');
        }
    };

    const handleDeleteConnector = async (id: string) => {
        try {
            await deleteConnector.mutateAsync(id);
        } catch (err) {
            setError('Failed to delete connector. Please try again.');
        }
    };

    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto', p: 3 }}>
            {/* Header */}
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Settings
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage your platform connections, integrations, and preferences
                </Typography>
            </Box>

            {error && (
                <Alert
                    severity="error"
                    sx={{ mb: 3 }}
                    onClose={() => setError(null)}
                >
                    {error}
                </Alert>
            )}

            {/* Main Content */}
            <Paper
                elevation={0}
                sx={{
                    borderRadius: '12px',
                    border: `1px solid ${theme.palette.divider}`,
                }}
            >
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs
                        value={activeTab}
                        onChange={handleTabChange}
                        sx={{ px: 2 }}
                    >
                        <Tab
                            icon={<StorageIcon sx={{ mr: 1 }} />}
                            label="Storage Connectors"
                            iconPosition="start"
                        />
                        <Tab
                            icon={<ApiIcon sx={{ mr: 1 }} />}
                            label="Integrations"
                            iconPosition="start"
                        />
                        <Tab
                            icon={<PersonIcon sx={{ mr: 1 }} />}
                            label="Profile"
                            iconPosition="start"
                        />
                        <Tab
                            icon={<GroupIcon sx={{ mr: 1 }} />}
                            label="User Management"
                            iconPosition="start"
                        />
                        <Tab
                            icon={<AdminIcon sx={{ mr: 1 }} />}
                            label="Admin"
                            iconPosition="start"
                        />
                    </Tabs>
                </Box>

                <TabPanel value={activeTab} index={0}>
                    <Box sx={{ px: 2 }}>
                        <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end' }}>
                            <Button
                                variant="contained"
                                startIcon={<AddIcon />}
                                onClick={handleAddConnector}
                            >
                                Add Connector
                            </Button>
                        </Box>
                        <ConnectorsList onAddConnector={handleAddConnector} />
                    </Box>
                </TabPanel>

                <TabPanel value={activeTab} index={2}>
                    <Box sx={{ px: 2 }}>
                        <UserProfile />
                    </Box>
                </TabPanel>

                <TabPanel value={activeTab} index={3}>
                    <Box sx={{ px: 2 }}>
                        <UserManagement />
                    </Box>
                </TabPanel>

            </Paper>

            {/* Modals */}
            <ConnectorModal
                open={openConnectorModal}
                onClose={() => {
                    setOpenConnectorModal(false);
                    setEditingConnector(undefined);
                }}
                onSave={handleSaveConnector}
                editingConnector={editingConnector}
            />
        </Box>
    );
};

export default SettingsPage;
