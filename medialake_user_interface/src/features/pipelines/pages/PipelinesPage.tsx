import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { Box, Button, Snackbar, Alert, useTheme } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { PageHeader, PageContent } from '@/components/common/layout';
import ApiStatusModal from '@/components/ApiStatusModal';
import queryClient from '@/api/queryClient';
import { PipelinesService } from '../api/pipelinesService';
import {
    PipelineTable,
    PipelineDeleteDialog,
    PipelineColumnMenu,
    PipelineFilterPopover,
} from '../components';
import { usePipelineManager } from '../hooks/usePipelineManager';
import type { Pipeline } from '../types/pipelines.types';
import type { TableState, TableActions } from '../types/table.types';

// Define query keys for prefetching
const PIPELINES_QUERY_KEYS = {
    all: ['pipelines'] as const,
    detail: (id: string) => ['pipelines', 'detail', id] as const,
};

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

    // Add a state flag for deletion in progress
    const [isDeletingInProgress, setIsDeletingInProgress] = useState(false);

    // API Status Modal state
    const [apiStatus, setApiStatus] = useState({
        open: false,
        status: 'loading' as 'loading' | 'success' | 'error',
        action: '',
        message: ''
    });

    // Function to handle closing the ApiStatusModal
    const handleCloseApiStatus = () => {
        setApiStatus(prev => ({ ...prev, open: false }));
    };

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

    // Monitor re-renders with data
    useEffect(() => {
        console.log('[PERF-PAGE] PipelinesPage render with data:', {
            pipelinesCount: pipelines?.length || 0,
            isLoading,
            hasError: !!error,
            location: location.pathname
        });
    }, [pipelines, isLoading, error, location.pathname]);

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

    // Define callbacks separately to avoid hooks rules violations
    const setPagination = useCallback((pagination) =>
        setTableState(prev => ({ ...prev, pagination })), []);
        
    const setGlobalFilter = useCallback((filter) =>
        setTableState(prev => ({ ...prev, globalFilter: filter })), []);
        
    const setColumnFilters = useCallback((filters) =>
        setTableState(prev => ({ ...prev, columnFilters: filters })), []);
        
    const setColumnVisibility = useCallback((visibility) =>
        setTableState(prev => ({ ...prev, columnVisibility: visibility })), []);
        
    const handleCloseSnackbar = useCallback(() =>
        setTableState(prev => ({ ...prev, snackbar: { ...prev.snackbar, open: false } })), []);
        
    const handleEdit = useCallback(async (id) => {
        // Show loading modal
        setApiStatus({
            open: true,
            status: 'loading',
            action: 'Loading pipeline data...',
            message: ''
        });
        
        try {
            // Prefetch the pipeline data
            await queryClient.prefetchQuery({
                queryKey: PIPELINES_QUERY_KEYS.detail(id),
                queryFn: () => PipelinesService.getPipeline(id)
            });
            
            // Close the modal
            setApiStatus(prev => ({ ...prev, open: false }));
            
            // Navigate to the editor page
            navigate(`/settings/pipelines/${id}/edit`);
        } catch (error) {
            console.error(`Error fetching pipeline data: ${error}`);
            
            // Show error modal
            setApiStatus({
                open: true,
                status: 'error',
                action: 'Error loading pipeline data',
                message: error instanceof Error ? error.message : 'An unknown error occurred'
            });
        }
    }, [navigate]);
    
    // Simplified openDeleteDialog function
    const openDeleteDialog = useCallback((id, name) => {
        // Simple logging without performance monitoring
        console.log(`Opening delete dialog for pipeline: ${id}, ${name}`);
        
        // Set dialog properties
        setTableState(prev => ({
            ...prev,
            deleteDialog: {
                open: true,
                pipelineName: name,
                pipelineId: id,
                userInput: '',
            },
        }));
    }, []);
    
    const closeDeleteDialog = useCallback(() => setTableState(prev => ({
        ...prev,
        deleteDialog: { ...prev.deleteDialog, open: false },
    })), []);
    
    const handleColumnMenuOpen = useCallback((event) => setTableState(prev => ({
        ...prev,
        columnMenuAnchor: event.currentTarget,
    })), []);
    
    const handleColumnMenuClose = useCallback(() => setTableState(prev => ({
        ...prev,
        columnMenuAnchor: null,
    })), []);
    
    const handleFilterMenuOpen = useCallback((event, columnId) => setTableState(prev => ({
        ...prev,
        filterMenuAnchor: event.currentTarget,
        activeFilterColumn: columnId,
    })), []);
    
    const handleFilterMenuClose = useCallback(() => setTableState(prev => ({
        ...prev,
        filterMenuAnchor: null,
        activeFilterColumn: null,
    })), []);
    
    const setDeleteDialogInput = useCallback((input) => setTableState(prev => ({
        ...prev,
        deleteDialog: { ...prev.deleteDialog, userInput: input },
    })), []);

    // Direct delete function that mimics the edit function's approach
    const handleDirectDelete = useCallback(async (id, name) => {
        // If deletion is already in progress, do nothing
        if (isDeletingInProgress) {
            return;
        }
        
        // Set deletion in progress
        setIsDeletingInProgress(true);
        
        // Show loading modal
        setApiStatus({
            open: true,
            status: 'loading',
            action: `Deleting pipeline "${name}"...`,
            message: ''
        });
        
        try {
            // Call the deletePipeline function
            await deletePipeline(id);
            
            // Show success modal
            setApiStatus({
                open: true,
                status: 'success',
                action: 'Pipeline deleted successfully',
                message: `The pipeline "${name}" has been deleted.`
            });
            
            // Auto-close the success modal after 2 seconds
            setTimeout(() => {
                setApiStatus(prev => ({ ...prev, open: false }));
            }, 2000);
            
        } catch (error) {
            console.error(`Error deleting pipeline ${id}:`, error);
            
            // Show error modal
            setApiStatus({
                open: true,
                status: 'error',
                action: 'Error deleting pipeline',
                message: error instanceof Error ? error.message : 'An unknown error occurred'
            });
        } finally {
            // Reset deletion in progress
            setIsDeletingInProgress(false);
        }
    }, [deletePipeline, isDeletingInProgress]);

    // Now create the tableActions object with the memoized callbacks
    const tableActions: TableActions = useMemo(() => ({
        setPagination,
        setGlobalFilter,
        setColumnFilters,
        setColumnVisibility,
        handleCloseSnackbar,
        handleEdit,
        openDeleteDialog,
        closeDeleteDialog,
        handleDirectDelete,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
        setDeleteDialogInput,
    }), [
        setPagination,
        setGlobalFilter,
        setColumnFilters,
        setColumnVisibility,
        handleCloseSnackbar,
        handleEdit,
        openDeleteDialog,
        closeDeleteDialog,
        handleDirectDelete,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
        setDeleteDialogInput,
    ]);

    // Simplified handleDeletePipeline function with deletion state flag
    const handleDeletePipeline = useCallback(async (id: string) => {
        // If deletion is already in progress, do nothing
        if (isDeletingInProgress) {
            return;
        }
        
        // Set deletion in progress
        setIsDeletingInProgress(true);
        
        // Close the dialog first to prevent UI freezing
        setTableState(prev => ({
            ...prev,
            deleteDialog: { ...prev.deleteDialog, open: false },
        }));

        try {
            // Simple logging without performance monitoring
            console.log(`Starting pipeline deletion for ID: ${id}`);
            
            // Call the deletePipeline function
            await deletePipeline(id);
            
            // Show success message
            setTableState(prev => ({
                ...prev,
                snackbar: {
                    open: true,
                    severity: 'success',
                    message: t('pipelines.messages.deleteSuccess'),
                },
            }));
        } catch (error) {
            console.error(`Error deleting pipeline ${id}:`, error);
            
            // Show error message
            setTableState(prev => ({
                ...prev,
                snackbar: {
                    open: true,
                    severity: 'error',
                    message: t('pipelines.messages.deleteError'),
                },
            }));
        } finally {
            // Reset deletion in progress
            setIsDeletingInProgress(false);
        }
    }, [deletePipeline, t, isDeletingInProgress]);

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

            <ErrorBoundary fallback={<div>Something went wrong with the pipeline table. Please refresh the page.</div>}>
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
                    isDeleting={isDeleting || isDeletingInProgress}
                />
            </ErrorBoundary>

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

            {/* API Status Modal */}
            <ApiStatusModal
                open={apiStatus.open}
                onClose={handleCloseApiStatus}
                status={apiStatus.status}
                action={apiStatus.action}
                message={apiStatus.message}
            />
        </Box>
    );
};

export default PipelinesPage;
