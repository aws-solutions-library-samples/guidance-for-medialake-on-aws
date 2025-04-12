import React, { useState, useMemo } from 'react';
import { Box, Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import WarningIcon from '@mui/icons-material/Warning';
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
import { IntegrationsNodesService } from '@/features/settings/integrations/services/integrations-nodes.service';

const IntegrationsPage = () => {
    const { t } = useTranslation();
    const [openIntegrationForm, setOpenIntegrationForm] = useState(false);
    const [activeFilters, setActiveFilters] = useState<IntegrationFilters[]>([]);
    const [activeSorting, setActiveSorting] = useState<IntegrationSorting[]>([]);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [integrationToDelete, setIntegrationToDelete] = useState<string | null>(null);

    // Fetch nodes using React Query
    const { nodes, isLoading: isLoadingNodes, error: nodesError } = IntegrationsNodesService.useNodes();
    
    // Filter nodes to only include those with nodeType === "INTEGRATION"
    // and transform them to the expected IntegrationNode format
    const integrationNodes = useMemo(() => {
        return nodes
            .filter(node => node.info?.nodeType === "INTEGRATION")
            .map(node => ({
                nodeId: node.nodeId || '',
                info: {
                    title: node.info?.title || '',
                    description: node.info?.description || '',
                },
                auth: node.auth ? {
                    authMethod: node.auth.authMethod as 'awsIam' | 'apiKey'
                } : undefined
            }));
    }, [nodes]);
    
    // Fetch integrations using React Query
    const { data: integrationsData, isLoading: isLoadingIntegrations, error: integrationsError } = useGetIntegrations();
    const createIntegration = useCreateIntegration();
    
    // Combine loading and error states
    const isLoading = isLoadingNodes || isLoadingIntegrations;
    const error = nodesError || integrationsError;

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
        // Open the confirmation dialog and set the integration ID to delete
        setIntegrationToDelete(id);
        setDeleteDialogOpen(true);
    };

    const confirmDeleteIntegration = async () => {
        if (integrationToDelete) {
            try {
                await integrationsController.deleteIntegration(integrationToDelete);
                // Close the dialog after successful deletion
                setDeleteDialogOpen(false);
                setIntegrationToDelete(null);
            } catch (error) {
                console.error('Failed to delete integration:', error);
                // Keep the dialog open if there's an error
            }
        }
    };

    const cancelDeleteIntegration = () => {
        setDeleteDialogOpen(false);
        setIntegrationToDelete(null);
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
                filteredNodes={integrationNodes}
            />

            {/* Confirmation Dialog for Integration Deletion */}
            <Dialog
                open={deleteDialogOpen}
                onClose={cancelDeleteIntegration}
                aria-labelledby="alert-dialog-title"
                aria-describedby="alert-dialog-description"
            >
                <DialogTitle id="alert-dialog-title" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <WarningIcon color="warning" />
                    {t('integrations.deleteConfirmation.title')}
                </DialogTitle>
                <DialogContent>
                    <DialogContentText id="alert-dialog-description">
                        {t('integrations.deleteConfirmation.message')}
                    </DialogContentText>
                    <DialogContentText sx={{ mt: 2, fontWeight: 'bold', color: 'error.main' }}>
                        {t('integrations.deleteConfirmation.warning')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={cancelDeleteIntegration} color="primary">
                        {t('common.cancel')}
                    </Button>
                    <Button onClick={confirmDeleteIntegration} color="error" variant="contained" autoFocus>
                        {t('common.delete')}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

IntegrationsPage.displayName = 'IntegrationsPage';

export default React.memo(IntegrationsPage);