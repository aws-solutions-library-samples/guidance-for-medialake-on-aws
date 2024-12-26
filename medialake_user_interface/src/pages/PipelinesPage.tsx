import React, { useMemo } from 'react';
import { Box, Snackbar, Alert } from '@mui/material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getPaginationRowModel,
    ColumnDef,
    FilterFn,
} from '@tanstack/react-table';
import { Pipeline } from '@/api/types/pipeline.types';
import { useTranslation } from 'react-i18next';
import {
    PipelineTable,
    PipelineToolbar,
    PipelineDeleteDialog,
    PipelineColumnMenu,
    PipelineFilterPopover,
} from '@/features/pipelines/components';
import { usePipelineManager } from '@/features/pipelines/hooks/usePipelineManager';

const containsFilter: FilterFn<any> = (row, columnId, value) => {
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;
    return String(cellValue)
        .toLowerCase()
        .includes(String(value).toLowerCase());
};

const PipelinesPage: React.FC = () => {
    const { t } = useTranslation();
    const {
        // State
        pipelines,
        isCreatingPipeline,
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
        hasNextPage,
        isFetchingNextPage,
        deletePipeline,

        // Actions
        setPagination,
        setGlobalFilter,
        setColumnFilters,
        setColumnVisibility,
        handleCloseSnackbar,
        handleEdit,
        handleAddNew,
        handleCreatePipeline,
        handleDeletePipeline,
        openDeleteDialog,
        closeDeleteDialog,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
        fetchNextPage,
        setDeleteDialogInput,
    } = usePipelineManager();

    const columns = useMemo<ColumnDef<Pipeline>[]>(
        () => [
            {
                header: t('pipelines.columns.name'),
                accessorKey: 'name',
            },
            {
                header: t('pipelines.columns.creationDate'),
                accessorKey: 'createdAt',
            },
            {
                header: t('pipelines.columns.system'),
                accessorKey: 'system',
            },
            {
                header: t('pipelines.columns.type'),
                accessorKey: 'type',
            },
            {
                id: 'actions',
                header: t('common.actions'),
            },
        ],
        [t]
    );

    const table = useReactTable({
        data: pipelines,
        columns,
        filterFns: {
            contains: containsFilter,
        },
        state: {
            globalFilter,
            columnFilters,
            columnVisibility,
            pagination,
        },
        onPaginationChange: setPagination,
        onGlobalFilterChange: setGlobalFilter,
        onColumnFiltersChange: setColumnFilters,
        onColumnVisibilityChange: setColumnVisibility,
        globalFilterFn: containsFilter,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
    });

    return (
        <Box sx={{ 
            height: '100%', 
            display: 'block',
            overflowX: 'auto',
            width: '100%',
            minWidth: 'max-content',
            '& > *': {
                minWidth: 'max-content'
            }
        }}>
            <PipelineToolbar
                isCreatingPipeline={isCreatingPipeline}
                globalFilter={globalFilter}
                onGlobalFilterChange={setGlobalFilter}
                onCreatePipeline={handleCreatePipeline}
                onAddNew={handleAddNew}
                onColumnMenuOpen={handleColumnMenuOpen}
            />

            <PipelineTable
                table={table}
                isLoading={isLoading}
                data={pipelines}
                showDeleteButton={showDeleteButton}
                hasNextPage={hasNextPage}
                isFetchingNextPage={isFetchingNextPage}
                onEdit={handleEdit}
                onDelete={openDeleteDialog}
                onFetchNextPage={fetchNextPage}
                onFilterColumn={handleFilterMenuOpen}
            />

            <PipelineColumnMenu
                anchorEl={columnMenuAnchor}
                columns={table.getAllLeafColumns()}
                onClose={handleColumnMenuClose}
            />

            <PipelineFilterPopover
                anchorEl={filterMenuAnchor}
                column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
                onClose={handleFilterMenuClose}
            />

            <PipelineDeleteDialog
                open={deleteDialog.open}
                pipelineName={deleteDialog.pipelineName}
                userInput={deleteDialog.userInput}
                isDeleting={deletePipeline.isPending}
                onClose={closeDeleteDialog}
                onConfirm={handleDeletePipeline}
                onUserInputChange={setDeleteDialogInput}
            />

            <Snackbar
                open={snackbar.open || deletePipeline.isPending}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                autoHideDuration={6000}
                onClose={handleCloseSnackbar}
            >
                <Alert
                    onClose={handleCloseSnackbar}
                    severity={deletePipeline.isPending ? 'info' : snackbar.severity}
                    sx={{ width: '100%' }}
                >
                    {deletePipeline.isPending ? t('pipelines.deleting') : snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default PipelinesPage;
