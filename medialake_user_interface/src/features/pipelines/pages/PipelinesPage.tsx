import React from 'react';
import { Box, Button, Snackbar, Alert, useTheme, Paper, Container, Typography } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
    PipelineTable,
    PipelineToolbar,
    PipelineDeleteDialog,
    PipelineColumnMenu,
    PipelineFilterPopover,
} from '../components';
import { usePipelineManager } from '../hooks/usePipelineManager';
import type { Pipeline } from '../types/pipelines.types';
import type { TableState, TableActions } from '../types/table.types';

const PipelinesPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();

    const {
        pipelines,
        searchMetadata,
        isLoading,
        error,
        deletePipeline,
        isDeleting,
        startPipeline,
        stopPipeline
    } = usePipelineManager();

    // Table state
    const [tableState, setTableState] = React.useState<TableState>({
        globalFilter: '',
        columnFilters: [],
        columnVisibility: {},
        columnMenuAnchor: null,
        filterMenuAnchor: null,
        activeFilterColumn: null,
        pagination: {
            pageIndex: 0,
            pageSize: searchMetadata?.pageSize || 10,
        },
        deleteDialog: {
            open: false,
            pipelineName: '',
            pipelineId: '',
            userInput: '',
        },
        snackbar: {
            open: false,
            severity: 'info',
            message: '',
        },
    });

    // Table actions
    const tableActions: TableActions = {
        setPagination: (pagination) => setTableState(prev => ({ ...prev, pagination })),
        setGlobalFilter: (filter) => setTableState(prev => ({ ...prev, globalFilter: filter })),
        setColumnFilters: (filters) => setTableState(prev => ({ ...prev, columnFilters: filters })),
        setColumnVisibility: (visibility) => setTableState(prev => ({ ...prev, columnVisibility: visibility })),
        handleCloseSnackbar: () => setTableState(prev => ({ ...prev, snackbar: { ...prev.snackbar, open: false } })),
        handleEdit: (id) => navigate(`/settings/pipelines/${id}/edit`),
        openDeleteDialog: (id, name) => {
            setTableState(prev => ({
                ...prev,
                deleteDialog: {
                    open: true,
                    pipelineName: name,
                    pipelineId: id,
                    userInput: '',
                },
            }));
        },
        closeDeleteDialog: () => setTableState(prev => ({
            ...prev,
            deleteDialog: { ...prev.deleteDialog, open: false },
        })),
        handleColumnMenuOpen: (event) => setTableState(prev => ({
            ...prev,
            columnMenuAnchor: event.currentTarget,
        })),
        handleColumnMenuClose: () => setTableState(prev => ({
            ...prev,
            columnMenuAnchor: null,
        })),
        handleFilterMenuOpen: (event, columnId) => setTableState(prev => ({
            ...prev,
            filterMenuAnchor: event.currentTarget,
            activeFilterColumn: columnId,
        })),
        handleFilterMenuClose: () => setTableState(prev => ({
            ...prev,
            filterMenuAnchor: null,
            activeFilterColumn: null,
        })),
        setDeleteDialogInput: (input) => setTableState(prev => ({
            ...prev,
            deleteDialog: { ...prev.deleteDialog, userInput: input },
        })),
    };

    const handleDeletePipeline = async (id: string) => {
        try {
            await deletePipeline(id);
            setTableState(prev => ({
                ...prev,
                snackbar: {
                    open: true,
                    severity: 'success',
                    message: t('pipelines.messages.deleteSuccess'),
                },
            }));
        } catch (error) {
            setTableState(prev => ({
                ...prev,
                snackbar: {
                    open: true,
                    severity: 'error',
                    message: t('pipelines.messages.deleteError'),
                },
            }));
        }
    };

    if (error) {
        return (
            <Container maxWidth="xl">
                <Alert severity="error" sx={{ mt: 2 }}>
                    {t('pipelines.messages.loadError')}
                </Alert>
            </Container>
        );
    }

    return (
        <Container maxWidth="xl">
            <Paper elevation={0} sx={{ p: 3 }}>
                <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h4" component="h1">
                        {t('pipelines.title')}
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => navigate('/settings/pipelines/new')}
                    >
                        {t('pipelines.actions.create')}
                    </Button>
                </Box>

                <Box sx={{ mb: 2 }}>
                    <PipelineToolbar
                        onFilterChange={tableActions.setGlobalFilter}
                        onColumnMenuOpen={tableActions.handleColumnMenuOpen}
                    />
                </Box>

                <PipelineTable
                    data={pipelines}
                    isLoading={isLoading}
                    tableState={tableState}
                    tableActions={tableActions}
                    onStartPipeline={startPipeline}
                    onStopPipeline={stopPipeline}
                />

                <PipelineDeleteDialog
                    open={tableState.deleteDialog.open}
                    pipelineName={tableState.deleteDialog.pipelineName}
                    userInput={tableState.deleteDialog.userInput}
                    onClose={tableActions.closeDeleteDialog}
                    onConfirm={() => handleDeletePipeline(tableState.deleteDialog.pipelineId)}
                    onUserInputChange={tableActions.setDeleteDialogInput}
                    isDeleting={isDeleting}
                />

                <PipelineColumnMenu
                    anchorEl={tableState.columnMenuAnchor}
                    onClose={tableActions.handleColumnMenuClose}
                    visibility={tableState.columnVisibility}
                    onVisibilityChange={tableActions.setColumnVisibility}
                />

                <PipelineFilterPopover
                    anchorEl={tableState.filterMenuAnchor}
                    column={tableState.activeFilterColumn}
                    onClose={tableActions.handleFilterMenuClose}
                    onFilterChange={tableActions.setColumnFilters}
                />

                <Snackbar
                    open={tableState.snackbar.open}
                    autoHideDuration={6000}
                    onClose={tableActions.handleCloseSnackbar}
                >
                    <Alert
                        onClose={tableActions.handleCloseSnackbar}
                        severity={tableState.snackbar.severity}
                        sx={{ width: '100%' }}
                    >
                        {tableState.snackbar.message}
                    </Alert>
                </Snackbar>
            </Paper>
        </Container>
    );
};

export default PipelinesPage; 