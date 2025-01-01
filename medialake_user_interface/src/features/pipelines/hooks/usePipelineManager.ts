import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
    ColumnFiltersState,
    PaginationState,
} from '@tanstack/react-table';
import { PipelineResponse, Pipeline } from '../../../api/types/pipeline.types';
import { usePipeline, useDeletePipeline } from '../../../api/hooks/usePipelines';

const PAGE_SIZE = 20;

export const usePipelineManager = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const deletePipeline = useDeletePipeline();
    const [pipelines, setPipelines] = useState<Pipeline[]>([]);
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

    const { data, isLoading, refetch } = usePipeline(PAGE_SIZE, {
        status: filters.type === "" ? undefined : filters.type,
        system: filters.system === "" ? undefined : filters.system,
        sortBy: filters.sortBy,
        sortOrder: filters.sortOrder
    });

    useEffect(() => {
        if (data?.pages) {
            const allPipelines = data.pages.flatMap(page => page.data.s);
            setPipelines(allPipelines);
        }
    }, [data]);

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
            await deletePipeline.mutateAsync(deleteDialog.pipelineId);
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

    return {
        // State
        pipelines,
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
        deletePipeline,

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
        refetch,
    };
};
