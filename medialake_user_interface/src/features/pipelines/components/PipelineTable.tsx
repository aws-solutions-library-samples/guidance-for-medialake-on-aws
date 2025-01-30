import React, { useMemo } from 'react';
import {
    Box,
    IconButton,
    Paper,
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
    flexRender,
    createColumnHelper,
    ColumnDef
} from '@tanstack/react-table';
import { BaseTable } from '@/components/common/table/BaseTable';
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
                        >
                            <PlayIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Stop Pipeline">
                        <IconButton
                            size="small"
                            onClick={() => onStopPipeline(info.row.original.id)}
                        >
                            <StopIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            ),
            size: 200
        })
    ], [tableActions, onStartPipeline, onStopPipeline]);

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
        <BaseTable
            data={data}
            columns={columns}
            activeFilters={tableState.columnFilters}
            activeSorting={[]}
            onFilterChange={(columnId, value) => {
                tableActions.setColumnFilters([...tableState.columnFilters, { id: columnId, value }]);
            }}
            onRemoveFilter={(columnId) => {
                tableActions.setColumnFilters(
                    tableState.columnFilters.filter(filter => filter.id !== columnId)
                );
            }}
            getUniqueValues={(columnId, data) => {
                const values = new Set<string>();
                data.forEach(item => {
                    const value = item[columnId as keyof Pipeline];
                    if (value != null) {
                        values.add(String(value));
                    }
                });
                return Array.from(values).sort();
            }}
            formatValue={(columnId, value) => {
                if (columnId === 'system') {
                    return value === 'true' ? 'Yes' : 'No';
                }
                return value;
            }}
            searchPlaceholder="Search pipelines..."
            initialColumnVisibility={{
                name: true,
                type: true,
                system: true,
                createdAt: true,
                updatedAt: true,
                actions: true
            }}
        />
    );
};
