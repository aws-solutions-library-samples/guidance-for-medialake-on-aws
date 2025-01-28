import React, { useState } from 'react';
import {
    Box,
    Typography,
    Button,
    Alert,
    CircularProgress,
    useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import IntegrationList from '@/features/settings/integrations/components/IntegrationList/index';
import IntegrationForm from '@/features/settings/integrations/components/IntegrationForm';
import ApiStatusModal from '@/components/ApiStatusModal';
import { Integration } from '@/features/settings/integrations/components/IntegrationList/types';

// Sample data - will be replaced by API hooks
const sampleIntegrations: Integration[] = [
    {
        id: '1',
        nodeName: 'TwelveLabs Video Understanding',
        environment: 'Development',
        createdDate: '2023-12-12T10:00:00Z',
        modifiedDate: '2023-12-12T10:00:00Z',
    },
    {
        id: '2',
        nodeName: 'AWS Rekognition Analysis',
        environment: 'Production',
        createdDate: '2023-12-11T15:30:00Z',
        modifiedDate: '2023-12-11T15:30:00Z',
    },
];

const IntegrationsPage = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [openIntegrationForm, setOpenIntegrationForm] = useState(false);
    const [activeFilters, setActiveFilters] = useState<{ columnId: string; value: string }[]>([]);
    const [activeSorting, setActiveSorting] = useState<{ columnId: string; desc: boolean }[]>([]);
    const [apiStatus, setApiStatus] = useState<{
        show: boolean;
        status: 'loading' | 'success' | 'error';
        action: string;
        message?: string;
    }>({
        show: false,
        status: 'loading',
        action: '',
    });

    // In the future, these will be replaced with API hooks
    const [integrations, setIntegrations] = useState<Integration[]>(sampleIntegrations);
    const isLoading = false;
    const error = null;

    const handleAddIntegration = () => {
        setOpenIntegrationForm(true);
    };

    const handleEditIntegration = (integration: Integration) => {
        // Will be implemented when edit functionality is needed
        console.log('Edit integration:', integration);
    };

    const handleDeleteIntegration = async (id: string) => {
        setApiStatus({
            show: true,
            status: 'loading',
            action: t('integrations.status.deleting'),
        });

        try {
            // Simulating API call
            setIntegrations(prev => prev.filter(i => i.id !== id));

            setApiStatus({
                show: true,
                status: 'success',
                action: t('integrations.status.deleted'),
                message: t('integrations.status.deleted'),
            });
        } catch (error) {
            setApiStatus({
                show: true,
                status: 'error',
                action: t('integrations.status.deleteFailed'),
                message: error instanceof Error ? error.message : t('common.error'),
            });
        }
    };

    const handleSaveIntegration = async (data: any) => {
        setApiStatus({
            show: true,
            status: 'loading',
            action: t('integrations.status.creating'),
        });

        try {
            // Simulating API call
            const newIntegration: Integration = {
                id: Date.now().toString(),
                nodeName: data.nodeName,
                environment: data.environment,
                createdDate: new Date().toISOString(),
                modifiedDate: new Date().toISOString(),
            };

            setIntegrations(prev => [...prev, newIntegration]);
            setOpenIntegrationForm(false);

            setApiStatus({
                show: true,
                status: 'success',
                action: t('integrations.status.created'),
                message: t('integrations.status.created'),
            });
        } catch (error) {
            setApiStatus({
                show: true,
                status: 'error',
                action: t('integrations.status.createFailed'),
                message: error instanceof Error ? error.message : t('common.error'),
            });
        }
    };

    const handleCloseApiStatus = () => {
        setApiStatus(prev => ({ ...prev, show: false }));
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flex: 1,
            width: '100%',
            position: 'relative',
            maxWidth: '100%',
            p: 3,
        }}>
            <Box sx={{ mb: 4, flex: 'none', width: '100%' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                        <Typography variant="h4" sx={{
                            fontWeight: 700,
                            mb: 1,
                            color: theme.palette.primary.main,
                        }}>
                            {t('integrations.title')}
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            {t('integrations.description')}
                        </Typography>
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAddIntegration}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            backgroundColor: theme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.dark,
                            },
                        }}
                    >
                        {t('integrations.addIntegration')}
                    </Button>
                </Box>
            </Box>

            <Box sx={{
                flex: 1,
                minHeight: 0,
                width: '100%',
                overflow: 'hidden',
                position: 'relative',
                maxWidth: '100%',
            }}>
                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                ) : error ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {error instanceof Error ? error.message : t('common.error')}
                    </Alert>
                ) : (
                    <IntegrationList
                        integrations={integrations}
                        onEditIntegration={handleEditIntegration}
                        onDeleteIntegration={handleDeleteIntegration}
                        activeFilters={activeFilters}
                        activeSorting={activeSorting}
                        onFilterChange={(columnId, value) => {
                            setActiveFilters(filters => {
                                const newFilters = filters.filter(f => f.columnId !== columnId);
                                if (value) {
                                    newFilters.push({ columnId, value });
                                }
                                return newFilters;
                            });
                        }}
                        onSortChange={(columnId, desc) => {
                            setActiveSorting(sorts => {
                                const newSorts = sorts.filter(s => s.columnId !== columnId);
                                if (desc !== undefined) {
                                    newSorts.push({ columnId, desc });
                                }
                                return newSorts;
                            });
                        }}
                        onRemoveFilter={(columnId) => {
                            setActiveFilters(filters => filters.filter(f => f.columnId !== columnId));
                        }}
                        onRemoveSort={(columnId) => {
                            setActiveSorting(sorts => sorts.filter(s => s.columnId !== columnId));
                        }}
                    />
                )}
            </Box>

            <IntegrationForm
                open={openIntegrationForm}
                onClose={() => setOpenIntegrationForm(false)}
                onSave={handleSaveIntegration}
            />

            <ApiStatusModal
                open={apiStatus.show}
                status={apiStatus.status}
                action={apiStatus.action}
                message={apiStatus.message}
                onClose={handleCloseApiStatus}
            />
        </Box>
    );
};

IntegrationsPage.displayName = 'IntegrationsPage';

export default React.memo(IntegrationsPage);
