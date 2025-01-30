import React, { useState } from 'react';
import {
    Box,
    Typography,
    Button,
    useTheme,
    CircularProgress,
    Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import IntegrationList from '@/features/settings/integrations/components/IntegrationList/index';
import IntegrationForm from '@/features/settings/integrations/components/IntegrationForm/IntegrationForm';
import {
    IntegrationFilters,
    IntegrationSorting,
    Integration,
    IntegrationsResponse
} from '@/features/settings/integrations/types/integrations.types';
import {
    useGetIntegrations,
    useCreateIntegration,
    integrationsController
} from '@/features/settings/integrations/api/integrations.controller';

const IntegrationsPage = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [openIntegrationForm, setOpenIntegrationForm] = useState(false);
    const [activeFilters, setActiveFilters] = useState<IntegrationFilters[]>([]);
    const [activeSorting, setActiveSorting] = useState<IntegrationSorting[]>([]);

    // Fetch integrations using React Query
    const { data: integrationsData, isLoading, error } = useGetIntegrations();
    const createIntegration = useCreateIntegration();

    const handleAddIntegration = () => {
        setOpenIntegrationForm(true);
    };

    const handleCloseIntegrationForm = () => {
        setOpenIntegrationForm(false);
    };

    const handleEditIntegration = async (id: string, data: any) => {
        try {
            await integrationsController.updateIntegration(id, data);
        } catch (error) {
            console.error('Failed to update integration:', error);
        }
    };

    const handleDeleteIntegration = async (id: string) => {
        try {
            await integrationsController.deleteIntegration(id);
        } catch (error) {
            console.error('Failed to delete integration:', error);
        }
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">
                    {t('integrations.errorLoading')}
                </Alert>
            </Box>
        );
    }

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
                <IntegrationList
                    integrations={(integrationsData as IntegrationsResponse)?.data || []}
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
            </Box>

            <IntegrationForm
                open={openIntegrationForm}
                onClose={handleCloseIntegrationForm}
            />
        </Box>
    );
};

IntegrationsPage.displayName = 'IntegrationsPage';

export default React.memo(IntegrationsPage);