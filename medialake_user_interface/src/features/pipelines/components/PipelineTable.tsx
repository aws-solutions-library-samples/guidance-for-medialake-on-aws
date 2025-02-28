import React, { useMemo, useRef, useState, useCallback } from 'react';
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
import { PipelineDeleteDialog } from './PipelineDeleteDialog';
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

    // Local state for the delete dialog
    const [deleteDialog, setDeleteDialog] = useState({
        open: false,
        pipelineName: '',
        pipelineId: '',
        userInput: '',
    });

    // Local state for deletion status
    const [isDeleting, setIsDeleting] = useState(false);

    // Simple handler for opening the delete dialog
    const handleOpenDeleteDialog = useCallback((id: string, name: string) => {
        // Set all dialog properties in a single update
        setDeleteDialog({
            open: true,
            pipelineName: name,
            pipelineId: id,
            userInput: '',
        });
    }, []);

    // Simple handler for closing the delete dialog
    const handleCloseDeleteDialog = useCallback(() => {
        setDeleteDialog(prev => ({
            ...prev,
            open: false,
        }));
    }, []);

    const handleDeleteDialogInputChange = useCallback((input: string) => {
        setDeleteDialog(prev => ({
            ...prev,
            userInput: input,
        }));
    }, []);

    // Simple handler for the actual deletion
    const handleDeletePipeline = useCallback(async () => {
        // Set deleting state
        setIsDeleting(true);

        try {
            // Get the auth token and base URL
            const token = localStorage.getItem('medialake-auth-token');
            const awsConfig = localStorage.getItem('medialake-aws-config');
            const baseURL = awsConfig ? JSON.parse(awsConfig)?.API?.REST?.RestApi?.endpoint || '' : '';

            // Call the API directly
            const response = await fetch(`${baseURL}/pipelinesv2/${deleteDialog.pipelineId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : '',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                },
            });

            if (response.ok) {
                // Show success message
                alert('Pipeline deleted successfully');
                // Refresh the page
                window.location.reload();
            } else {
                // Show error message
                alert('Failed to delete pipeline');
            }
        } catch (error) {
            console.error("Error deleting pipeline:", error);
            // Show error message
            alert(`Error deleting pipeline: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            // Reset deleting state
            setIsDeleting(false);
        }
    }, [deleteDialog.pipelineId]);

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
                        <span>
                            <IconButton
                                size="small"
                                onClick={() => tableActions.handleEdit(info.row.original.id)}
                            >
                                <EditIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Delete Pipeline">
                        <span>
                            <IconButton
                                size="small"
                                onClick={() => {

                                    try {
                                        // Prevent default behavior
                                        event.preventDefault();
                                        event.stopPropagation();

                                        // Use the browser's native confirm dialog directly
                                        console.log('[PERF] Using native confirm dialog directly');
                                        if (window.confirm(`Are you sure you want to delete pipeline "${info.row.original.name}"? This action cannot be undone.`)) {
                                            console.log('[PERF] Native confirm dialog confirmed, executing deletion');

                                            // Set deleting state
                                            setIsDeleting(true);

                                            try {
                                                // Get the auth token and base URL
                                                const token = localStorage.getItem('medialake-auth-token');
                                                const awsConfig = localStorage.getItem('medialake-aws-config');
                                                const baseURL = awsConfig ? JSON.parse(awsConfig)?.API?.REST?.RestApi?.endpoint || '' : '';

                                                // Call the API directly
                                                fetch(`${baseURL}/pipelinesv2/${info.row.original.id}`, {
                                                    method: 'DELETE',
                                                    headers: {
                                                        'Content-Type': 'application/json',
                                                        'Authorization': token ? `Bearer ${token}` : '',
                                                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                                                        'Pragma': 'no-cache',
                                                        'Expires': '0'
                                                    },
                                                })
                                                    .then(response => {
                                                        if (response.ok) {
                                                            // Show success message
                                                            alert('Pipeline deleted successfully');
                                                            // Refresh the page
                                                            window.location.reload();
                                                        } else {
                                                            // Show error message
                                                            alert('Failed to delete pipeline');
                                                            setIsDeleting(false);
                                                        }
                                                    })
                                                    .catch(error => {
                                                        console.error("Error deleting pipeline:", error);
                                                        // Show error message
                                                        alert(`Error deleting pipeline: ${error instanceof Error ? error.message : 'Unknown error'}`);
                                                        setIsDeleting(false);
                                                    });
                                            } catch (error) {
                                                console.error('[PERF] Error in deletion:', error);
                                                setIsDeleting(false);
                                            }
                                        } else {
                                            console.log('[PERF] Native confirm dialog cancelled');
                                        }
                                    } catch (error) {
                                        console.error('[PERF] Error in delete button click handler:', error);
                                    }

                                }}
                                disabled={info.row.original.system}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Start Pipeline">
                        <span>
                            <IconButton
                                size="small"
                                onClick={() => onStartPipeline(info.row.original.id)}
                            >
                                <PlayIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Stop Pipeline">
                        <span>
                            <IconButton
                                size="small"
                                onClick={() => onStopPipeline(info.row.original.id)}
                            >
                                <StopIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Box>
            ),
            size: 200
        })
    ], [tableActions, onStartPipeline, onStopPipeline, handleOpenDeleteDialog]);

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
        <>
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

            {/* Render the delete dialog directly in this component */}
            <PipelineDeleteDialog
                open={deleteDialog.open}
                pipelineName={deleteDialog.pipelineName}
                userInput={deleteDialog.userInput}
                onClose={handleCloseDeleteDialog}
                onConfirm={handleDeletePipeline}
                onUserInputChange={handleDeleteDialogInputChange}
                isDeleting={isDeleting}
            />
        </>
    );
};
