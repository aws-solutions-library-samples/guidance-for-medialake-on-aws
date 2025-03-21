import React, { useMemo, useState } from 'react';
import { formatLocalDateTime } from '@/shared/utils/dateUtils';
import {
    Box,
    Typography,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    IconButton,
    useTheme,
    Button,
    CircularProgress,
    TableSortLabel,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    alpha,
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    Visibility as VisibilityIcon,
    PlayArrow as PlayArrowIcon,
} from '@mui/icons-material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getPaginationRowModel,
    flexRender,
    ColumnDef,
    FilterFn,
} from '@tanstack/react-table';
import { usePipelineExecutions } from '../api/hooks/usePipelinesExecutions';
import type { PipelineExecution } from '../api/types/pipelineExecutions.types';

const PAGE_SIZE = 20;

const containsFilter: FilterFn<any> = (row, columnId, value) => {
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;
    return String(cellValue)
        .toLowerCase()
        .includes(String(value).toLowerCase());
};

const ExecutionStatusPage: React.FC = () => {
    const theme = useTheme();
    const [filters, setFilters] = useState({
        status: '',
        sortBy: 'start_time',
        sortOrder: 'desc' as 'asc' | 'desc'
    });

    const { data, isLoading, refetch } = usePipelineExecutions(PAGE_SIZE, {
        status: filters.status || undefined,
        sortBy: filters.sortBy,
        sortOrder: filters.sortOrder
    });

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'RUNNING':
                return theme.palette.info.main;
            case 'SUCCEEDED':
                return theme.palette.success.main;
            case 'FAILED':
                return theme.palette.error.main;
            case 'TIMED_OUT':
            case 'ABORTED':
                return theme.palette.warning.main;
            default:
                return theme.palette.grey[500];
        }
    };

    const formatDate = (dateString: string) => {
        return formatLocalDateTime(dateString, { showSeconds: true });
    };

    const formatDuration = (seconds: string) => {
        const duration = parseFloat(seconds);
        if (duration < 60) {
            return `${duration.toFixed(2)}s`;
        }
        const minutes = Math.floor(duration / 60);
        const remainingSeconds = (duration % 60).toFixed(2);
        return `${minutes}m ${remainingSeconds}s`;
    };

    const columns = useMemo<ColumnDef<PipelineExecution>[]>(
        () => [
            {
                header: 'Pipeline Name',
                accessorKey: 'pipeline_name',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ fontWeight: 500, color: theme.palette.primary.main }}>
                        {getValue() as string}
                    </Typography>
                ),
            },
            {
                header: 'Status',
                accessorKey: 'status',
                cell: ({ getValue }) => {
                    const status = getValue() as string;
                    const color = getStatusColor(status);
                    return (
                        <Chip
                            label={status}
                            size="small"
                            sx={{
                                backgroundColor: alpha(color, 0.1),
                                color: color,
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
                header: 'Start Time',
                accessorKey: 'start_time',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        {formatDate(getValue() as string)}
                    </Typography>
                ),
            },
            {
                header: 'Duration',
                accessorKey: 'duration_seconds',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        {formatDuration(getValue() as string)}
                    </Typography>
                ),
            },
            {
                header: 'Actions',
                id: 'actions',
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, position: 'relative' }}>
                        {row.original.status === 'FAILED' && (
                            <IconButton
                                size="small"
                                color="primary"
                                title="Retry"
                                sx={{
                                    position: 'relative',
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                    },
                                }}
                            >
                                <PlayArrowIcon fontSize="small" />
                            </IconButton>
                        )}
                        {/* <IconButton
                            size="small"
                            color="primary"
                            title="View Details"
                            sx={{
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                },
                            }}
                        >
                            <VisibilityIcon fontSize="small" />
                        </IconButton> */}
                    </Box>
                ),
            },
        ],
        [theme]
    );

    const executions = useMemo(() => {
        return data?.pages.flatMap(page => page.data.executions) || [];
    }, [data]);

    const table = useReactTable({
        data: executions,
        columns,
        filterFns: {
            contains: containsFilter,
        },
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        initialState: {
            pagination: {
                pageSize: PAGE_SIZE,
            },
        },
    });

    return (
        <Box sx={{ px: 4, py: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                        <Typography variant="h4" sx={{
                            fontWeight: 700,
                            mb: 1,
                            color: theme.palette.primary.main,
                        }}>
                            Pipeline Execution Status
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            Monitor and manage your pipeline execution status
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                        <FormControl size="small" sx={{
                            minWidth: 120,
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '8px',
                                backgroundColor: theme.palette.background.paper,
                            }
                        }}>
                            <InputLabel>Status</InputLabel>
                            <Select
                                value={filters.status}
                                label="Status"
                                onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
                            >
                                <MenuItem value="">All</MenuItem>
                                <MenuItem value="SUCCEEDED">Succeeded</MenuItem>
                                <MenuItem value="FAILED">Failed</MenuItem>
                                <MenuItem value="RUNNING">Running</MenuItem>
                                <MenuItem value="TIMED_OUT">Timed Out</MenuItem>
                                <MenuItem value="ABORTED">Aborted</MenuItem>
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            startIcon={<RefreshIcon />}
                            onClick={() => refetch()}
                            sx={{
                                borderRadius: '8px',
                                textTransform: 'none',
                                px: 3,
                                backgroundColor: theme.palette.primary.main,
                                '&:hover': {
                                    backgroundColor: theme.palette.primary.dark,
                                },
                            }}
                        >
                            Refresh
                        </Button>
                    </Box>
                </Box>
            </Box>

            <Paper elevation={0} sx={{
                flex: 1,
                borderRadius: '12px',
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                overflow: 'hidden',
                backgroundColor: theme.palette.background.paper,
            }}>
                <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)' }}>
                    <Table stickyHeader>
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <TableCell
                                            key={header.id}
                                            sx={{
                                                backgroundColor: theme.palette.background.paper,
                                                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                py: 2,
                                            }}
                                        >
                                            {header.isPlaceholder ? null : (
                                                <TableSortLabel
                                                    active={header.column.getIsSorted() !== false}
                                                    direction={header.column.getIsSorted() === 'desc' ? 'desc' : 'asc'}
                                                    onClick={header.column.getToggleSortingHandler()}
                                                    sx={{
                                                        fontWeight: 600,
                                                        color: theme.palette.text.primary,
                                                    }}
                                                >
                                                    {flexRender(
                                                        header.column.columnDef.header,
                                                        header.getContext()
                                                    )}
                                                </TableSortLabel>
                                            )}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableHead>
                        <TableBody>
                            {isLoading ? (
                                <TableRow>
                                    <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                                        <CircularProgress size={32} />
                                    </TableCell>
                                </TableRow>
                            ) : (
                                table.getRowModel().rows.map(row => (
                                    <TableRow
                                        key={row.id}
                                        sx={{
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                            },
                                            transition: 'background-color 0.2s ease',
                                        }}
                                    >
                                        {row.getVisibleCells().map(cell => (
                                            <TableCell
                                                key={cell.id}
                                                sx={{
                                                    borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                    py: 2,
                                                }}
                                            >
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>

                <Box sx={{
                    p: 2,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                }}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            onClick={() => table.previousPage()}
                            disabled={!table.getCanPreviousPage()}
                            sx={{
                                textTransform: 'none',
                                borderRadius: '8px',
                                color: theme.palette.text.secondary,
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                },
                            }}
                        >
                            Previous
                        </Button>
                        <Button
                            onClick={() => table.nextPage()}
                            disabled={!table.getCanNextPage()}
                            sx={{
                                textTransform: 'none',
                                borderRadius: '8px',
                                color: theme.palette.text.secondary,
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                },
                            }}
                        >
                            Next
                        </Button>
                    </Box>
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                    </Typography>
                    <Select
                        value={table.getState().pagination.pageSize}
                        onChange={e => table.setPageSize(Number(e.target.value))}
                        size="small"
                        sx={{
                            minWidth: 120,
                            borderRadius: '8px',
                            '& .MuiOutlinedInput-notchedOutline': {
                                borderColor: alpha(theme.palette.divider, 0.2),
                            },
                        }}
                    >
                        {[10, 20, 50].map(pageSize => (
                            <MenuItem key={pageSize} value={pageSize}>
                                Show {pageSize}
                            </MenuItem>
                        ))}
                    </Select>
                </Box>
            </Paper>
        </Box>
    );
};

export default ExecutionStatusPage;
