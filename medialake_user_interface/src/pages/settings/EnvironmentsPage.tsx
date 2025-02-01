import React, { useState } from 'react';
import {
    Box,
    Typography,
    Button,
    CircularProgress,
    useTheme,
    Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import EnvironmentList from '@/features/settings/environments/components/EnvironmentList';
import { EnvironmentForm } from '@/features/settings/environments/components/EnvironmentForm';
import ApiStatusModal from '@/components/ApiStatusModal';
import {
    useEnvironmentsQuery,
    useCreateEnvironmentMutation,
    useUpdateEnvironmentMutation,
    useDeleteEnvironmentMutation
} from '@/features/settings/environments/hooks/useEnvironmentsQuery';
import { Environment, EnvironmentCreate, EnvironmentUpdate } from '@/types/environment';

const EnvironmentsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [openEnvironmentForm, setOpenEnvironmentForm] = useState(false);
    const [editingEnvironment, setEditingEnvironment] = useState<Environment | undefined>();
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

    // API Hooks
    const { data: environments, isLoading: isLoadingEnvironments, error: environmentsError } = useEnvironmentsQuery();
    const createEnvironmentMutation = useCreateEnvironmentMutation();
    const updateEnvironmentMutation = useUpdateEnvironmentMutation();
    const deleteEnvironmentMutation = useDeleteEnvironmentMutation();

    const handleAddEnvironment = () => {
        setEditingEnvironment(undefined);
        setOpenEnvironmentForm(true);
    };

    const handleEditEnvironment = (environment: Environment) => {
        setEditingEnvironment(environment);
        setOpenEnvironmentForm(true);
    };

    const handleSaveEnvironment = async (environmentData: EnvironmentCreate) => {
        const isNewEnvironment = !editingEnvironment;
        const action = isNewEnvironment ? 'Creating environment...' : 'Updating environment...';

        setApiStatus({
            show: true,
            status: 'loading',
            action,
        });
        setOpenEnvironmentForm(false);

        try {
            if (editingEnvironment) {
                const updateData: EnvironmentUpdate = {
                    name: environmentData.name,
                    region: environmentData.region,
                    status: environmentData.status,
                    tags: environmentData.tags,
                };
                await updateEnvironmentMutation.mutateAsync({
                    id: editingEnvironment.environment_id,
                    data: updateData
                });

                setApiStatus({
                    show: true,
                    status: 'success',
                    action: 'Environment Updated',
                    message: t('settings.environments.updateSuccess'),
                });
            } else {
                await createEnvironmentMutation.mutateAsync(environmentData);

                setApiStatus({
                    show: true,
                    status: 'success',
                    action: 'Environment Created',
                    message: t('settings.environments.createSuccess'),
                });
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : t('settings.environments.submitError');
            setApiStatus({
                show: true,
                status: 'error',
                action: isNewEnvironment ? 'Environment Creation Failed' : 'Environment Update Failed',
                message: errorMessage,
            });
            console.error('Error saving environment:', error);
            throw error;
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
                            {t('settings.environments.title')}
                        </Typography>
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleAddEnvironment}
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
                        {t('settings.environments.addButton')}
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
                {isLoadingEnvironments ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                        <CircularProgress />
                    </Box>
                ) : environmentsError ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {environmentsError instanceof Error ? environmentsError.message : t('common.error')}
                    </Alert>
                ) : (
                    <EnvironmentList
                        environments={(environments?.data?.environments || []).map(env => ({
                            ...env,
                            status: env.status || 'active', // Ensure status is always present
                            tags: {
                                'cost-center': env.tags?.['cost-center'] || '',
                                team: env.tags?.team || '',
                                ...env.tags
                            }
                        }))}
                        onEditEnvironment={handleEditEnvironment}
                        onDeleteEnvironment={async (id) => {
                            try {
                                await deleteEnvironmentMutation.mutateAsync(id);
                                setApiStatus({
                                    show: true,
                                    status: 'success',
                                    action: 'Environment Deleted',
                                    message: t('settings.environments.deleteSuccess'),
                                });
                            } catch (error) {
                                setApiStatus({
                                    show: true,
                                    status: 'error',
                                    action: 'Environment Deletion Failed',
                                    message: error instanceof Error ? error.message : t('settings.environments.deleteError'),
                                });
                            }
                        }}
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

            <EnvironmentForm
                open={openEnvironmentForm}
                onClose={() => setOpenEnvironmentForm(false)}
                onSave={handleSaveEnvironment}
                environment={editingEnvironment}
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

export default EnvironmentsPage;
