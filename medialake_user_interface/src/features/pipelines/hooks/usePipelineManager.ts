import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
    ColumnFiltersState,
    PaginationState,
} from '@tanstack/react-table';
import { useGetPipelines, useDeletePipeline, useStartPipeline, useStopPipeline } from '../api/pipelinesController';
import type { Pipeline, PipelinesResponse } from '../types/pipelines.types';

const PAGE_SIZE = 20;

export const usePipelineManager = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [showDeleteButton, setShowDeleteButton] = useState(false);
    const [globalFilter, setGlobalFilter] = useState('');
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
    const [columnVisibility, setColumnVisibility] = useState({});
    const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);
    const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);
    const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(null);
    const [pagination, setPagination] = useState<PaginationState>({
        pageIndex: 0,
        pageSize: PAGE_SIZE,
    });

    const [deleteDialog, setDeleteDialog] = useState({
        open: false,
        pipelineId: '',
        pipelineName: '',
        userInput: '',
    });

    const [filters, setFilters] = useState({
        type: '',
        name: '',
        system: '',
        sortBy: 'createdAt',
        sortOrder: 'desc' as 'asc' | 'desc'
    });

    const [snackbar, setSnackbar] = useState({
        open: false,
        message: '',
        severity: 'success' as 'success' | 'error',
    });

    const {
        data: pipelinesResponse,
        isLoading,
        error,
        refetch
    } = useGetPipelines();

    const deletePipelineMutation = useDeletePipeline();
    const startPipelineMutation = useStartPipeline();
    const stopPipelineMutation = useStopPipeline();

    // Keyboard shortcut effect for delete button
    useEffect(() => {
        let keySequence: string[] = [];
        let shiftKeyPressed = false;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.shiftKey) {
                shiftKeyPressed = true;
            }

            if (shiftKeyPressed && ['d', 'e', 'l'].includes(event.key.toLowerCase())) {
                keySequence.push(event.key.toLowerCase());
                if (keySequence.join('') === 'del') {
                    event.preventDefault();
                    setShowDeleteButton(prev => !prev);
                    keySequence = [];
                }
            } else if (shiftKeyPressed) {
                keySequence = [];
            }
        };

        const handleKeyUp = (event: KeyboardEvent) => {
            if (event.key === 'Shift') {
                shiftKeyPressed = false;
                keySequence = [];
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        window.addEventListener('keyup', handleKeyUp);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            window.removeEventListener('keyup', handleKeyUp);
        };
    }, []);

    const handleCloseSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    const handleEdit = (id: string) => {
        navigate(`/pipelines/${id}`);
    };

    // We don't need the handleDeletePipeline function anymore since we're using the mutation directly in PipelinesPage.tsx

    const openDeleteDialog = (id: string, name: string) => {
        setDeleteDialog({
            open: true,
            pipelineId: id,
            pipelineName: name,
            userInput: '',
        });
    };

    const closeDeleteDialog = () => {
        setDeleteDialog({
            open: false,
            pipelineId: '',
            pipelineName: '',
            userInput: '',
        });
    };

    const setDeleteDialogInput = (value: string) => {
        setDeleteDialog(prev => ({ ...prev, userInput: value }));
    };

    const handleColumnMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setColumnMenuAnchor(event.currentTarget);
    };

    const handleColumnMenuClose = () => {
        setColumnMenuAnchor(null);
    };

    const handleFilterMenuOpen = (event: React.MouseEvent<HTMLElement>, columnId: string) => {
        setFilterMenuAnchor(event.currentTarget);
        setActiveFilterColumn(columnId);
    };

    const handleFilterMenuClose = () => {
        setFilterMenuAnchor(null);
        setActiveFilterColumn(null);
    };

    const pipelines = pipelinesResponse?.data?.s || [];
    const searchMetadata = pipelinesResponse?.data?.searchMetadata || {
        totalResults: 0,
        pageSize: PAGE_SIZE,
        nextToken: null
    };

    return {
        // State
        pipelines,
        searchMetadata,
        showDeleteButton,
        globalFilter,
        columnFilters,
        columnVisibility,
        columnMenuAnchor,
        filterMenuAnchor,
        activeFilterColumn,
        pagination,
        deleteDialog,
        snackbar,
        isLoading,
        error,
        isDeleting: deletePipelineMutation.isPending,
        // Wrap the mutation in a function that handles errors and timeouts
        deletePipeline: async (id: string) => {
            console.log(`[usePipelineManager] Starting delete operation for pipeline ID: ${id}`);

            // Create a timeout promise to prevent hanging
            const timeoutPromise = new Promise<never>((_, reject) => {
                setTimeout(() => {
                    console.error(`[usePipelineManager] Delete operation timed out after 30 seconds for pipeline ID: ${id}`);
                    reject(new Error('Delete operation timed out after 30 seconds'));
                }, 30000);
            });

            try {
                // Race the deletion against the timeout
                await Promise.race([
                    deletePipelineMutation.mutateAsync(id),
                    timeoutPromise
                ]);

                console.log(`[usePipelineManager] Delete operation completed successfully for pipeline ID: ${id}`);

                // Refresh the pipeline list
                await refetch();

                return true;
            } catch (error) {
                console.error(`[usePipelineManager] Error in delete operation for pipeline ID: ${id}`, error);

                // Still try to refresh the list in case the deletion actually succeeded
                try {
                    await refetch();
                } catch (refetchError) {
                    console.error(`[usePipelineManager] Error refreshing pipeline list after deletion:`, refetchError);
                }

                throw error;
            }
        },
        startPipeline: startPipelineMutation.mutate,
        stopPipeline: stopPipelineMutation.mutate,
        refetch,

        // Actions
        setPagination,
        setGlobalFilter,
        setColumnFilters,
        setColumnVisibility,
        handleCloseSnackbar,
        handleEdit,
        openDeleteDialog,
        closeDeleteDialog,
        setDeleteDialogInput,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
    };
};
