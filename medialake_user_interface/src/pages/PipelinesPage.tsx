import React, { useMemo } from 'react';
import { Box, Snackbar, Alert, Chip, alpha, useTheme, Typography } from '@mui/material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getPaginationRowModel,
    ColumnDef,
    FilterFn,
} from '@tanstack/react-table';
import { Pipeline } from '../api/types/pipeline.types';
import { useTranslation } from 'react-i18next';
import {
    PipelineTable,
    PipelineToolbar,
    PipelineDeleteDialog,
    PipelineColumnMenu,
    PipelineFilterPopover,
} from '../features/pipelines/components';
import { usePipelineManager } from '../features/pipelines/hooks/usePipelineManager';
import { TableCellContent } from '../components/common/table';

const containsFilter: FilterFn<any> = (row, columnId, value) => {
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;
    return String(cellValue)
        .toLowerCase()
        .includes(String(value).toLowerCase());
};

const PipelinesPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const {
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
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
        setDeleteDialogInput,
    } = usePipelineManager();

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    };

    const columns = useMemo<ColumnDef<Pipeline>[]>(
        () => [
            {
                header: t('pipelines.columns.name'),
                accessorKey: 'name',
                size: 200,
                minSize: 150,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="primary">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('pipelines.columns.creationDate'),
                accessorKey: 'createdAt',
                size: 180,
                minSize: 150,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {formatDate(getValue() as string)}
                    </TableCellContent>
                ),
            },
            {
                header: t('pipelines.columns.system'),
                accessorKey: 'system',
                size: 150,
                minSize: 120,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('pipelines.columns.type'),
                accessorKey: 'type',
                size: 180,
                minSize: 150,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const type = getValue() as string;
                    return (
                        <Chip
                            label={type}
                            size="small"
                            sx={{
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                color: theme.palette.primary.main,
                                fontWeight: 600,
                                borderRadius: '6px',
                                height: '24px',
                                '& .MuiChip-label': {
                                    px: 1.5,
                                },
                            }}
                        />
                    );
                },
            },
            {
                id: 'actions',
                header: t('common.actions'),
                size: 120,
                minSize: 100,
                enableSorting: false,
                enableFiltering: false,
            },
        ],
        [t, theme]
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
                            background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                            backgroundClip: 'text',
                            WebkitBackgroundClip: 'text',
                            color: 'transparent',
                        }}>
                            {t('pipelines.title')}
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            {t('pipelines.description')}
                        </Typography>
                    </Box>
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
                <PipelineToolbar
                    globalFilter={globalFilter}
                    onGlobalFilterChange={setGlobalFilter}
                    onColumnMenuOpen={handleColumnMenuOpen}
                />

                <PipelineTable
                    table={table}
                    isLoading={isLoading}
                    data={pipelines}
                    showDeleteButton={showDeleteButton}
                    onEdit={handleEdit}
                    onDelete={openDeleteDialog}
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
        </Box>
    );
};

export default PipelinesPage;
