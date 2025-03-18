import React, { useState, useMemo } from 'react';
import { Box, Button, Snackbar, Alert } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
    useReactTable,
    getCoreRowModel,
    getSortedRowModel,
    getFilteredRowModel,
    ColumnFiltersState,
    SortingState,
    ColumnSizingState,
} from '@tanstack/react-table';

import { PageHeader, PageContent } from '@/components/common/layout';
import { BaseTableToolbar } from '@/components/common/table/BaseTableToolbar';
import { BaseFilterPopover } from '@/components/common/table/BaseFilterPopover';
import { ColumnVisibilityMenu } from '@/components/common/table/ColumnVisibilityMenu';
import ApiStatusModal from '@/components/ApiStatusModal';
import queryClient from '@/api/queryClient';
import { PipelinesService } from '../api/pipelinesService';
import {
    PipelineDeleteDialog,
} from '../components';
import PipelineList from '../components/PipelineList';
import { usePipelineManager } from '../hooks/usePipelineManager';
import { usePipelineColumns, defaultColumnVisibility } from '../hooks/usePipelineColumns';
import { TableFiltersProvider } from '../context/TableFiltersContext';

// Define query keys for prefetching
const PIPELINES_QUERY_KEYS = {
    all: ['pipelines'] as const,
    detail: (id: string) => ['pipelines', 'detail', id] as const,
};

const PipelinesPage: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();

    // API Status Modal state
    const [apiStatus, setApiStatus] = useState({
        open: false,
        status: 'loading' as 'loading' | 'success' | 'error',
        action: '',
        message: ''
    });

    // Delete dialog state
    const [deleteDialog, setDeleteDialog] = useState({
        open: false,
        pipelineName: '',
        pipelineId: '',
        userInput: '',
    });

    // Table state
    const [sorting, setSorting] = useState<SortingState>([]);
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
    const [columnVisibility, setColumnVisibility] = useState(() => {
        try {
            const saved = localStorage.getItem('pipelineTableColumns');
            return saved && saved !== 'undefined' ? JSON.parse(saved) : defaultColumnVisibility;
        } catch (error) {
            console.error('Error parsing column visibility from localStorage:', error);
            return defaultColumnVisibility;
        }
    });
    const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
    const [globalFilter, setGlobalFilter] = useState('');
    const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);
    const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);
    const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(null);
    const [isDeletingInProgress, setIsDeletingInProgress] = useState(false);
    const [snackbar, setSnackbar] = useState({
        open: false,
        severity: 'info' as 'info' | 'success' | 'error' | 'warning',
        message: '',
    });

    // Function to handle closing the ApiStatusModal
    const handleCloseApiStatus = () => {
        setApiStatus(prev => ({ ...prev, open: false }));
    };

    const {
        pipelines,
        isLoading,
        error,
        deletePipeline,
        isDeleting,
        startPipeline,
        stopPipeline
    } = usePipelineManager();

    // Handle edit pipeline
    const handleEdit = (id: string) => {
        // Show loading modal
        setApiStatus({
            open: true,
            status: 'loading',
            action: 'Loading pipeline data...',
            message: ''
        });
        
        // Start prefetching in the background
        queryClient.prefetchQuery({
            queryKey: PIPELINES_QUERY_KEYS.detail(id),
            queryFn: () => PipelinesService.getPipeline(id),
            staleTime: 30000, // Consider data fresh for 30 seconds
        })
        .finally(() => {
            // Close the modal regardless of prefetch result
            setApiStatus(prev => ({ ...prev, open: false }));
        });
        
        // Navigate immediately without waiting for prefetch
        navigate(`/settings/pipelines/edit/${id}`);
    };

    // Handle delete pipeline
    const handleDeletePipeline = async (id: string) => {
        // If deletion is already in progress, do nothing
        if (isDeletingInProgress) {
            return;
        }

        // Set deletion in progress
        setIsDeletingInProgress(true);

        // Close the dialog first to prevent UI freezing
        setDeleteDialog(prev => ({ ...prev, open: false }));

        // Show ApiStatusModal in "loading" state
        setApiStatus({
            open: true,
            status: 'loading',
            action: 'Deleting pipeline...',
            message: '',
        });

        try {
            await deletePipeline(id);
            
            // Show success modal
            setApiStatus({
                open: true,
                status: 'success',
                action: 'Pipeline deleted successfully',
                message: 'The pipeline has been deleted.',
            });

            // Auto-close the modal after a few seconds
            setTimeout(() => {
                setApiStatus(prev => ({ ...prev, open: false }));
            }, 2000);
        } catch (error) {
            // Show error modal
            setApiStatus({
                open: true,
                status: 'error',
                action: 'Error deleting pipeline',
                message: error instanceof Error ? error.message : 'An unknown error occurred',
            });
        } finally {
            // Reset deletion in progress
            setIsDeletingInProgress(false);
        }
    };

    // Open delete dialog
    const openDeleteDialog = (id: string, name: string) => {
        setDeleteDialog({
            open: true,
            pipelineId: id,
            pipelineName: name,
            userInput: '',
        });
    };

    // Close delete dialog
    const closeDeleteDialog = () => {
        setDeleteDialog(prev => ({ ...prev, open: false }));
    };

    // Handle delete confirmation
    const handleDeleteConfirm = () => {
        const pipelineId = deleteDialog.pipelineId;
        if (!pipelineId) {
            console.error('No pipeline ID found in delete dialog state');
            return;
        }
        
        handleDeletePipeline(pipelineId);
    };

    // Handle filter column
    const handleFilterColumn = (event: React.MouseEvent<HTMLElement>, columnId: string) => {
        setActiveFilterColumn(columnId);
        setFilterMenuAnchor(event.currentTarget);
    };

    // Handle filter menu close
    const handleFilterMenuClose = () => {
        setFilterMenuAnchor(null);
        setActiveFilterColumn(null);
    };

    // Handle column visibility changes with persistence
    const handleColumnVisibilityChange = (updatedVisibility: Record<string, boolean>) => {
        if (!updatedVisibility) return;
        setColumnVisibility(updatedVisibility);
        try {
            if (Object.keys(updatedVisibility).length > 0) {
                localStorage.setItem('pipelineTableColumns', JSON.stringify(updatedVisibility));
            }
        } catch (error) {
            console.error('Error saving column visibility to localStorage:', error);
        }
    };

    // Handle snackbar close
    const handleCloseSnackbar = () => {
        setSnackbar(prev => ({ ...prev, open: false }));
    };

    // Set delete dialog input
    const setDeleteDialogInput = (input: string) => {
        setDeleteDialog(prev => ({ ...prev, userInput: input }));
    };

    // Create table filters context value
    const tableFiltersValue = useMemo(() => ({
        activeFilters: columnFilters.map(f => ({ columnId: f.id, value: f.value as string })),
        activeSorting: sorting.map(s => ({ columnId: s.id, desc: s.desc })),
        onRemoveFilter: (columnId: string) => {
            setColumnFilters(prev => prev.filter(f => f.id !== columnId));
        },
        onRemoveSort: (columnId: string) => {
            setSorting(prev => prev.filter(s => s.id !== columnId));
        },
        onFilterChange: (columnId: string, value: string) => {
            setColumnFilters(prev => {
                const existing = prev.find(f => f.id === columnId);
                if (existing) {
                    return prev.map(f => f.id === columnId ? { ...f, value } : f);
                }
                return [...prev, { id: columnId, value }];
            });
        },
        onSortChange: (columnId: string, desc: boolean) => {
            setSorting(prev => {
                const existing = prev.find(s => s.id === columnId);
                if (existing) {
                    return prev.map(s => s.id === columnId ? { ...s, desc } : s);
                }
                return [...prev, { id: columnId, desc }];
            });
        },
    }), [columnFilters, sorting]);

    // Create columns
    const columns = usePipelineColumns({
        onEdit: handleEdit,
        onDelete: openDeleteDialog,
        onStart: startPipeline,
        onStop: stopPipeline
    });

    // Create table
    const table = useReactTable({
        data: pipelines || [],
        columns,
        state: {
            sorting,
            columnFilters,
            columnVisibility,
            columnSizing,
            globalFilter,
        },
        enableSorting: true,
        enableColumnFilters: true,
        onSortingChange: setSorting,
        onColumnFiltersChange: setColumnFilters,
        onColumnVisibilityChange: handleColumnVisibilityChange,
        onColumnSizingChange: setColumnSizing,
        onGlobalFilterChange: setGlobalFilter,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        filterFns: {
            includesString: (row, columnId, filterValue) => {
                const value = String(row.getValue(columnId) || '').toLowerCase();
                return value.includes(String(filterValue).toLowerCase());
            }
        },
    });

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

            <TableFiltersProvider {...tableFiltersValue}>
                <BaseTableToolbar
                    globalFilter={globalFilter}
                    onGlobalFilterChange={setGlobalFilter}
                    onColumnMenuOpen={(event) => setColumnMenuAnchor(event.currentTarget)}
                    activeFilters={tableFiltersValue.activeFilters}
                    activeSorting={tableFiltersValue.activeSorting}
                    onRemoveFilter={tableFiltersValue.onRemoveFilter}
                    onRemoveSort={tableFiltersValue.onRemoveSort}
                    searchPlaceholder={t('pipelines.searchPlaceholder')}
                />

                <PageContent
                    isLoading={isLoading}
                    error={error as Error}
                >
                    <PipelineList
                        table={table}
                        onFilterColumn={handleFilterColumn}
                    />
                </PageContent>

                <BaseFilterPopover
                    anchorEl={filterMenuAnchor}
                    column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
                    onClose={handleFilterMenuClose}
                    data={pipelines || []}
                    getUniqueValues={(columnId, data) => {
                        return Array.from(new Set(data.map(item => {
                            const value = item[columnId as keyof typeof item];
                            return value ? String(value) : '';
                        }))).filter(Boolean);
                    }}
                />

                <ColumnVisibilityMenu
                    anchorEl={columnMenuAnchor}
                    onClose={() => setColumnMenuAnchor(null)}
                    columns={table.getAllColumns()}
                />

                <PipelineDeleteDialog
                    open={deleteDialog.open}
                    pipelineName={deleteDialog.pipelineName}
                    userInput={deleteDialog.userInput}
                    onClose={closeDeleteDialog}
                    onConfirm={handleDeleteConfirm}
                    onUserInputChange={setDeleteDialogInput}
                    isDeleting={isDeleting || isDeletingInProgress}
                />

                <Snackbar
                    open={snackbar.open}
                    autoHideDuration={6000}
                    onClose={handleCloseSnackbar}
                >
                    <Alert
                        onClose={handleCloseSnackbar}
                        severity={snackbar.severity}
                        sx={{ width: '100%' }}
                    >
                        {snackbar.message}
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
            </TableFiltersProvider>
        </Box>
    );
};

export default PipelinesPage;
