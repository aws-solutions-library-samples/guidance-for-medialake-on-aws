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

    // Define non-blocking callbacks separately to avoid hooks rules violations
    const setPagination = useCallback((pagination) => {
        setTimeout(() => {
            setTableState(prev => ({ ...prev, pagination }));
        }, 0);
    }, []);
        
    const setGlobalFilter = useCallback((filter) => {
        setTimeout(() => {
            setTableState(prev => ({ ...prev, globalFilter: filter }));
        }, 0);
    }, []);
        
    const setColumnFilters = useCallback((filters) => {
        setTimeout(() => {
            setTableState(prev => ({ ...prev, columnFilters: filters }));
        }, 0);
    }, []);
        
    const setColumnVisibility = useCallback((visibility) => {
        setTimeout(() => {
            setTableState(prev => ({ ...prev, columnVisibility: visibility }));
        }, 0);
    }, []);
        
    // Non-blocking handleCloseSnackbar function
    const handleCloseSnackbar = useCallback(() => {
        // Use setTimeout to make this operation non-blocking
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                snackbar: { ...prev.snackbar, open: false }
            }));
        }, 0);
    }, []);
        
    const handleEdit = useCallback((id) => {
        // Log performance start time
        const startTime = performance.now();
        console.log(`[PERF] Starting pipeline edit operation for ID: ${id}`);
        
        // Show loading modal - use setTimeout to make it non-blocking
        setTimeout(() => {
            setApiStatus({
                open: true,
                status: 'loading',
                action: 'Loading pipeline data...',
                message: ''
            });
            console.log(`[PERF] Loading modal shown in ${performance.now() - startTime}ms`);
        }, 0);
        
        // Start prefetching in the background but don't await it
        const prefetchPromise = queryClient.prefetchQuery({
            queryKey: PIPELINES_QUERY_KEYS.detail(id),
            queryFn: () => PipelinesService.getPipeline(id),
            staleTime: 30000, // Consider data fresh for 30 seconds
        });
        
        // Add timeout to the prefetch operation
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => {
                reject(new Error('Pipeline data loading timed out after 5 seconds'));
            }, 5000); // 5 second timeout
        });
        
        // Race the prefetch against the timeout, but don't block navigation
        Promise.race([prefetchPromise, timeoutPromise])
            .then(() => {
                const endTime = performance.now();
                console.log(`[PERF] Prefetch completed successfully in ${endTime - startTime}ms`);
            })
            .catch(error => {
                console.error(`[PERF] Prefetch error after ${performance.now() - startTime}ms:`, error);
            })
            .finally(() => {
                // Close the modal regardless of prefetch result
                setApiStatus(prev => ({ ...prev, open: false }));
                console.log(`[PERF] Edit operation UI flow completed in ${performance.now() - startTime}ms`);
            });
        
        // Navigate immediately without waiting for prefetch
        console.log(`[PERF] Navigating to edit page for pipeline ID: ${id}`);
        navigate(`/settings/pipelines/${id}/edit`);
    }, [navigate]);
    
    // Non-blocking openDeleteDialog function
    const openDeleteDialog = useCallback((id, name) => {
        // Log performance start time
        const startTime = performance.now();
        console.log(`[PERF] Opening delete dialog for pipeline: ${id}, name: ${name}`);
        
        // Use setTimeout to make this operation non-blocking
        setTimeout(() => {
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
            
            console.log(`[PERF] Delete dialog opened in ${performance.now() - startTime}ms`);
        }, 0);
    }, []);
    
    // Non-blocking closeDeleteDialog function
    const closeDeleteDialog = useCallback(() => {
        // Use setTimeout to make this operation non-blocking
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                deleteDialog: { ...prev.deleteDialog, open: false },
            }));
        }, 0);
    }, []);
    
    // Non-blocking column menu functions
    const handleColumnMenuOpen = useCallback((event) => {
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                columnMenuAnchor: event.currentTarget,
            }));
        }, 0);
    }, []);
    
    const handleColumnMenuClose = useCallback(() => {
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                columnMenuAnchor: null,
            }));
        }, 0);
    }, []);
    
    // Non-blocking filter menu functions
    const handleFilterMenuOpen = useCallback((event, columnId) => {
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                filterMenuAnchor: event.currentTarget,
                activeFilterColumn: columnId,
            }));
        }, 0);
    }, []);
    
    const handleFilterMenuClose = useCallback(() => {
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                filterMenuAnchor: null,
                activeFilterColumn: null,
            }));
        }, 0);
    }, []);
    
    // Non-blocking setDeleteDialogInput function
    const setDeleteDialogInput = useCallback((input) => {
        // Use setTimeout to make this operation non-blocking
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                deleteDialog: { ...prev.deleteDialog, userInput: input },
            }));
        }, 0);
    }, []);

    // Direct delete function with non-blocking approach
    const handleDirectDelete = useCallback((id, name) => {
        // If deletion is already in progress, do nothing
        if (isDeletingInProgress) {
            return;
        }
        
        // Log performance start time
        const startTime = performance.now();
        console.log(`[PERF] Starting direct pipeline deletion for ID: ${id}, name: ${name}`);
        
        // Set deletion in progress - use setTimeout to make it non-blocking
        setTimeout(() => {
            setIsDeletingInProgress(true);
            console.log(`[PERF] Set deletion in progress in ${performance.now() - startTime}ms`);
        }, 0);
        
        // Show loading modal - use setTimeout to make it non-blocking
        setTimeout(() => {
            setApiStatus({
                open: true,
                status: 'loading',
                action: `Deleting pipeline "${name}"...`,
                message: ''
            });
            console.log(`[PERF] Loading modal shown in ${performance.now() - startTime}ms`);
        }, 0);
        
        // Create a timeout promise
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => {
                reject(new Error('Pipeline deletion timed out after 10 seconds'));
            }, 10000); // 10 second timeout
        });
        
        // Start deletion in the background but don't await it
        Promise.race([
            deletePipeline(id),
            timeoutPromise
        ])
            .then(() => {
                const endTime = performance.now();
                console.log(`[PERF] Pipeline deletion completed successfully in ${endTime - startTime}ms`);
                
                // Show success modal - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setApiStatus({
                        open: true,
                        status: 'success',
                        action: 'Pipeline deleted successfully',
                        message: `The pipeline "${name}" has been deleted.`
                    });
                    console.log(`[PERF] Success modal shown in ${performance.now() - startTime}ms`);
                    
                    // Auto-close the success modal after 2 seconds
                    setTimeout(() => {
                        setApiStatus(prev => ({ ...prev, open: false }));
                        console.log(`[PERF] Success modal auto-closed in ${performance.now() - startTime}ms`);
                    }, 2000);
                }, 0);
            })
            .catch(error => {
                console.error(`[PERF] Pipeline deletion error after ${performance.now() - startTime}ms:`, error);
                
                // Show error modal - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setApiStatus({
                        open: true,
                        status: 'error',
                        action: 'Error deleting pipeline',
                        message: error instanceof Error ? error.message : 'An unknown error occurred'
                    });
                    console.log(`[PERF] Error modal shown in ${performance.now() - startTime}ms`);
                }, 0);
            })
            .finally(() => {
                // Reset deletion in progress - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setIsDeletingInProgress(false);
                    console.log(`[PERF] Delete operation UI flow completed in ${performance.now() - startTime}ms`);
                }, 0);
            });
    }, [deletePipeline, isDeletingInProgress]);
    
    // Non-blocking handleDeletePipeline function with performance monitoring
    const handleDeletePipeline = useCallback((id: string) => {
        // If deletion is already in progress, do nothing
        if (isDeletingInProgress) {
            return;
        }
        
        // Log performance start time
        const startTime = performance.now();
        console.log(`[PERF] Starting pipeline deletion from dialog for ID: ${id}`);
        
        // Set deletion in progress - use setTimeout to make it non-blocking
        setTimeout(() => {
            setIsDeletingInProgress(true);
            console.log(`[PERF] Set deletion in progress in ${performance.now() - startTime}ms`);
        }, 0);
        
        // Close the dialog first to prevent UI freezing - use setTimeout to make it non-blocking
        setTimeout(() => {
            setTableState(prev => ({
                ...prev,
                deleteDialog: { ...prev.deleteDialog, open: false },
            }));
            console.log(`[PERF] Dialog closed in ${performance.now() - startTime}ms`);
        }, 0);

        // Create a timeout promise
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => {
                reject(new Error('Pipeline deletion timed out after 10 seconds'));
            }, 10000); // 10 second timeout
        });
        
        // Start deletion in the background but don't await it
        Promise.race([
            deletePipeline(id),
            timeoutPromise
        ])
            .then(() => {
                const endTime = performance.now();
                console.log(`[PERF] Pipeline deletion completed successfully in ${endTime - startTime}ms`);
                
                // Show success message - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setTableState(prev => ({
                        ...prev,
                        snackbar: {
                            open: true,
                            severity: 'success',
                            message: t('pipelines.messages.deleteSuccess'),
                        },
                    }));
                    console.log(`[PERF] Success message shown in ${performance.now() - startTime}ms`);
                }, 0);
            })
            .catch(error => {
                console.error(`[PERF] Pipeline deletion error after ${performance.now() - startTime}ms:`, error);
                
                // Show error message - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setTableState(prev => ({
                        ...prev,
                        snackbar: {
                            open: true,
                            severity: 'error',
                            message: t('pipelines.messages.deleteError'),
                        },
                    }));
                    console.log(`[PERF] Error message shown in ${performance.now() - startTime}ms`);
                }, 0);
            })
            .finally(() => {
                // Reset deletion in progress - use setTimeout to make it non-blocking
                setTimeout(() => {
                    setIsDeletingInProgress(false);
                    console.log(`[PERF] Delete dialog operation UI flow completed in ${performance.now() - startTime}ms`);
                }, 0);
            });
    }, [deletePipeline, t, isDeletingInProgress]);
    
    // Create a dedicated non-blocking callback for the delete confirmation
    const handleDeleteConfirm = useCallback(() => {
        // Log performance start time
        const startTime = performance.now();
        console.log(`[PERF] Starting delete confirmation`);
        
        // Use setTimeout to make this operation non-blocking
        setTimeout(() => {
            // Get the pipeline ID from the current state
            const pipelineId = tableState.deleteDialog.pipelineId;
            if (!pipelineId) {
                console.error('No pipeline ID found in delete dialog state');
                return;
            }
            
            console.log(`[PERF] Delete confirmation processing in ${performance.now() - startTime}ms`);
            
            // Call the non-blocking delete function
            handleDeletePipeline(pipelineId);
        }, 0);
    }, [tableState.deleteDialog.pipelineId, handleDeletePipeline]);

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
        handleDeleteConfirm,
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
        handleDeleteConfirm,
    ]);


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
                    onConfirm={handleDeleteConfirm}
                    onUserInputChange={tableActions.setDeleteDialogInput}
                    isDeleting={isDeleting || isDeletingInProgress}
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
