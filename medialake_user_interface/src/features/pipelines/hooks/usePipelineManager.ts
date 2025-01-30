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

    const handleDeletePipeline = async () => {
        if (deleteDialog.userInput !== deleteDialog.pipelineName) {
            setSnackbar({
                open: true,
                message: t('pipelines.deleteNameMismatch'),
                severity: 'error'
            });
            return;
        }

        try {
            await deletePipelineMutation.mutateAsync(deleteDialog.pipelineId);
            setSnackbar({
                open: true,
                message: t('pipelines.deleteSuccess'),
                severity: 'success'
            });
            refetch();
        } catch (error) {
            setSnackbar({
                open: true,
                message: t('pipelines.deleteFailed'),
                severity: 'error'
            });
        } finally {
            closeDeleteDialog();
        }
    };

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
        deletePipeline: deletePipelineMutation.mutate,
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
        handleDeletePipeline,
        openDeleteDialog,
        closeDeleteDialog,
        setDeleteDialogInput,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
    };
};
