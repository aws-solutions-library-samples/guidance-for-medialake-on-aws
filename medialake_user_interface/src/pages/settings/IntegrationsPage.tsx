import React, { useState } from 'react';
import { Box, Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import { PageHeader, PageContent } from '@/components/common/layout';
import IntegrationList from '@/features/settings/integrations/components/IntegrationList/index';
import IntegrationForm from '@/features/settings/integrations/components/IntegrationForm/IntegrationForm';
import {
    IntegrationFilters,
    IntegrationSorting,
    IntegrationsResponse
} from '@/features/settings/integrations/types/integrations.types';
import {
    useGetIntegrations,
    useCreateIntegration,
    integrationsController
} from '@/features/settings/integrations/api/integrations.controller';

const IntegrationsPage = () => {
    const { t } = useTranslation();
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
            <PageHeader
                title={t('integrations.title')}
                description={t('integrations.description')}
                action={
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAddIntegration}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            height: 40
                        }}
                    >
                        {t('integrations.addIntegration')}
                    </Button>
                }
            />

            <PageContent
                isLoading={isLoading}
                error={error as Error}
            >
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
                                newFilters.push({ id: columnId, columnId, value });
                            }
                            return newFilters;
                        });
                    }}
                    onSortChange={(columnId, desc) => {
                        setActiveSorting(sorts => {
                            const newSorts = sorts.filter(s => s.columnId !== columnId);
                            if (desc !== undefined) {
                                newSorts.push({ id: columnId, columnId, desc });
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
            </PageContent>

            <IntegrationForm
                open={openIntegrationForm}
                onClose={handleCloseIntegrationForm}
            />
        </Box>
    );
};

IntegrationsPage.displayName = 'IntegrationsPage';

export default React.memo(IntegrationsPage);