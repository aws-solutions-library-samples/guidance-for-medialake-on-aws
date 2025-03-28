import React, { useMemo, useRef } from 'react';
import {
    Box,
    IconButton,
    CircularProgress,
    Tooltip,
    Typography,
    Chip
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    PlayArrow as PlayIcon,
    Stop as StopIcon
} from '@mui/icons-material';
import {
    useReactTable,
    getCoreRowModel,
    getSortedRowModel,
    getFilteredRowModel,
    getPaginationRowModel,
    createColumnHelper,
    ColumnDef
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { BaseTableToolbar } from '@/components/common/table/BaseTableToolbar';
import { ResizableTable } from '@/components/common/table/ResizableTable';
import { TableCellContent } from '@/components/common/table/TableCellContent';
import type { Pipeline } from '../types/pipelines.types';
import type { TableState, TableActions } from '../types/table.types';

interface PipelineTableProps {
    data: Pipeline[];
    isLoading: boolean;
    tableState: TableState;
    tableActions: TableActions;
    onStartPipeline: (id: string) => void;
    onStopPipeline: (id: string) => void;
}

const columnHelper = createColumnHelper<Pipeline>();

export const PipelineTable: React.FC<PipelineTableProps> = ({
    data,
    isLoading,
    tableState,
    tableActions,
    onStartPipeline,
    onStopPipeline
}) => {
    const containerRef = useRef<HTMLDivElement>(null);

    const columns = useMemo<ColumnDef<Pipeline, any>[]>(() => [
        columnHelper.accessor('name', {
            header: 'Name',
            cell: info => (
                <TableCellContent variant="primary">
                    {info.getValue()}
                </TableCellContent>
            ),
            enableSorting: true,
            size: 200
        }),
        columnHelper.accessor('type', {
            header: 'Type',
            cell: info => (
                <TableCellContent variant="secondary">
                    <Chip
                        label={info.getValue()}
                        size="small"
                        color={info.getValue() === 'Ingest Triggered' ? 'primary' : 'default'}
                    />
                </TableCellContent>
            ),
            enableSorting: true,
            size: 150
        }),
        columnHelper.accessor('system', {
            header: 'System',
            cell: info => (
                <TableCellContent variant="secondary">
                    <Chip
                        label={info.getValue() ? 'Yes' : 'No'}
                        size="small"
                        color={info.getValue() ? 'success' : 'default'}
                    />
                </TableCellContent>
            ),
            enableSorting: true,
            size: 100
        }),
        columnHelper.accessor('deploymentStatus', {
            header: 'Status',
            cell: info => {
                const status = info.getValue();
                let color: 'text.secondary' | 'success.main' | 'info.main' | 'error.main' = 'text.secondary';
                
                if (status === 'DEPLOYED') {
                    color = 'success.main';
                } else if (status === 'CREATING') {
                    color = 'info.main';
                } else if (status === 'FAILED') {
                    color = 'error.main';
                }
                
                return (
                    <TableCellContent variant="secondary">
                        <Typography
                            variant="body2"
                            sx={{
                                color: color,
                                fontWeight: 'medium'
                            }}
                        >
                            {status || 'N/A'}
                        </Typography>
                    </TableCellContent>
                );
            },
            enableSorting: true,
            size: 120
        }),
        columnHelper.accessor('createdAt', {
            header: 'Created',
            cell: info => (
                <TableCellContent variant="secondary">
                    {new Date(info.getValue()).toLocaleString()}
                </TableCellContent>
            ),
            enableSorting: true,
            size: 180
        }),
        columnHelper.accessor('updatedAt', {
            header: 'Updated',
            cell: info => (
                <TableCellContent variant="secondary">
                    {new Date(info.getValue()).toLocaleString()}
                </TableCellContent>
            ),
            enableSorting: true,
            size: 180
        }),
        columnHelper.display({
            id: 'actions',
            header: 'Actions',
            cell: info => (
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title="Edit Pipeline">
                        <IconButton
                            size="small"
                            onClick={() => tableActions.handleEdit(info.row.original.id)}
                            // disabled={info.row.original.system}
                        >
                            <EditIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Pipeline">
                        <IconButton
                            size="small"
                            onClick={() => tableActions.openDeleteDialog(info.row.original.id, info.row.original.name)}
                            disabled={info.row.original.system}
                        >
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Start Pipeline">
                        <IconButton
                            size="small"
                            onClick={() => onStartPipeline(info.row.original.id)}
                            disabled={true}
                        >
                            <PlayIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Stop Pipeline">
                        <IconButton
                            size="small"
                            onClick={() => onStopPipeline(info.row.original.id)}
                            disabled={true}
                        >
                            <StopIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            ),
            size: 200
        })
    ], [tableActions, onStartPipeline, onStopPipeline]);

    const table = useReactTable({
        data,
        columns,
        state: {
            sorting: [],
            columnFilters: tableState.columnFilters,
            columnVisibility: tableState.columnVisibility,
            globalFilter: tableState.globalFilter,
        },
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
    });

    const { rows } = table.getRowModel();

    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 53,
        overscan: 20,
    });

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!data || data.length === 0) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <Typography variant="body1" color="text.secondary">
                    No pipelines found
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <BaseTableToolbar
                globalFilter={tableState.globalFilter}
                onGlobalFilterChange={tableActions.setGlobalFilter}
                onColumnMenuOpen={tableActions.handleColumnMenuOpen}
                activeFilters={tableState.columnFilters.map(f => ({ columnId: f.id, value: f.value as string }))}
                onRemoveFilter={(columnId) => {
                    tableActions.setColumnFilters(
                        tableState.columnFilters.filter(f => f.id !== columnId)
                    );
                }}
                searchPlaceholder="Search pipelines..."
            />
            <ResizableTable
                table={table}
                containerRef={containerRef}
                virtualizer={rowVirtualizer}
                rows={rows}
                onFilterClick={tableActions.handleFilterMenuOpen}
            />
        </Box>
    );
};
