import React, { useEffect, useRef } from 'react';
import { Box, Button, Snackbar, Alert, useTheme } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { PageHeader, PageContent } from '@/components/common/layout';
import {
    PipelineTable,
    PipelineDeleteDialog,
    PipelineColumnMenu,
    PipelineFilterPopover,
} from '../components';
import { usePipelineManager } from '../hooks/usePipelineManager';
import type { Pipeline } from '../types/pipelines.types';
import type { TableState, TableActions } from '../types/table.types';

// Performance monitoring helper
const logPerf = (message: string, startTime?: number) => {
    const now = window.performance.now();
    const timeInfo = startTime ? ` (took ${(now - startTime).toFixed(2)}ms)` : '';
    console.log(`[PERF-PAGE] ${message}${timeInfo} at ${now.toFixed(2)}ms`);
    return now;
};

const PipelinesPage: React.FC = () => {
    // Performance monitoring
    const perfMarks = useRef({
        pageLoad: window.performance.now(),
        deleteStart: 0,
        deleteEnd: 0
    });

    // Log when component mounts
    useEffect(() => {
        logPerf('PipelinesPage mounted', perfMarks.current.pageLoad);

        // Log memory usage if available (Chrome only)
        const performanceWithMemory = window.performance as any;
        if (performanceWithMemory.memory) {
            const memoryInfo = performanceWithMemory.memory;
            console.log('[PERF-PAGE] Initial memory usage:', {
                totalJSHeapSize: Math.round(memoryInfo.totalJSHeapSize / (1024 * 1024)) + ' MB',
                usedJSHeapSize: Math.round(memoryInfo.usedJSHeapSize / (1024 * 1024)) + ' MB'
            });
        }

        return () => {
            logPerf('PipelinesPage unmounting');
        };
    }, []);
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
        // Ultra-simplified openDeleteDialog function
        openDeleteDialog: (id, name) => {
            logPerf(`Opening delete dialog for pipeline: ${id}, ${name}`);

            try {
                // Set all dialog properties in a single update with no frills
                setTableState(prev => ({
                    ...prev,
                    deleteDialog: {
                        open: true,
                        pipelineName: name,
                        pipelineId: id,
                        userInput: '',
                    },
                }));
            } catch (error) {
                console.error('[PERF-PAGE] Error opening delete dialog:', error);
            }
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

    // Optimized handleDeletePipeline function with performance monitoring
    const handleDeletePipeline = async (id: string) => {
        perfMarks.current.deleteStart = logPerf(`Starting pipeline deletion process for ID: ${id}`);

        // Log memory before deletion
        const performanceWithMemory = window.performance as any;
        if (performanceWithMemory.memory) {
            const memoryInfo = performanceWithMemory.memory;
            console.log('[PERF-PAGE] Memory before deletion:', {
                totalJSHeapSize: Math.round(memoryInfo.totalJSHeapSize / (1024 * 1024)) + ' MB',
                usedJSHeapSize: Math.round(memoryInfo.usedJSHeapSize / (1024 * 1024)) + ' MB'
            });
        }

        // Note: The dialog is already closed by the PipelineDeleteDialog component
        // before calling this function, so we don't need to close it here
        logPerf('Dialog should be closed at this point');

        try {
            const apiCallStart = logPerf(`Calling deletePipeline for ID: ${id}`);
            await deletePipeline(id);
            logPerf(`Pipeline deletion API call completed for ID: ${id}`, apiCallStart);

            // Show success message
            const snackbarStart = logPerf('Setting success snackbar');
            setTableState(prev => {
                logPerf('Inside success snackbar setState callback');
                return {
                    ...prev,
                    snackbar: {
                        open: true,
                        severity: 'success',
                        message: t('pipelines.messages.deleteSuccess'),
                    },
                };
            });
            logPerf('After setting success snackbar', snackbarStart);
        } catch (error) {
            logPerf(`Error deleting pipeline ${id}:`, perfMarks.current.deleteStart);
            console.error(`Error deleting pipeline ${id}:`, error);

            // Show error message
            const snackbarStart = logPerf('Setting error snackbar');
            setTableState(prev => {
                logPerf('Inside error snackbar setState callback');
                return {
                    ...prev,
                    snackbar: {
                        open: true,
                        severity: 'error',
                        message: t('pipelines.messages.deleteError'),
                    },
                };
            });
            logPerf('After setting error snackbar', snackbarStart);
        } finally {
            perfMarks.current.deleteEnd = logPerf('Pipeline deletion process completed', perfMarks.current.deleteStart);

            // Log memory after deletion
            if (performanceWithMemory.memory) {
                const memoryInfo = performanceWithMemory.memory;
                console.log('[PERF-PAGE] Memory after deletion:', {
                    totalJSHeapSize: Math.round(memoryInfo.totalJSHeapSize / (1024 * 1024)) + ' MB',
                    usedJSHeapSize: Math.round(memoryInfo.usedJSHeapSize / (1024 * 1024)) + ' MB'
                });
            }
        }
    };

    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <PageHeader
                title={t('pipelines.title')}
                description={t('pipelines.description')}
                action={
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => navigate('/settings/pipelines/new')}
                        sx={{
                            borderRadius: '8px',
                            textTransform: 'none',
                            px: 3,
                            height: 40
                        }}
                    >
                        {t('pipelines.actions.create')}
                    </Button>
                }
            />

            <PageContent
                isLoading={isLoading}
                error={error as Error}
            >
                <PipelineTable
                    data={pipelines}
                    isLoading={isLoading}
                    tableState={tableState}
                    tableActions={tableActions}
                    onStartPipeline={startPipeline}
                    onStopPipeline={stopPipeline}
                />
            </PageContent>

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
        </Box>
    );
};

export default PipelinesPage;
