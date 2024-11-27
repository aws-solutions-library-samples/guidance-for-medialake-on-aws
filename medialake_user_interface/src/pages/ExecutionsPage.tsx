import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
    Tooltip,
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    Visibility as VisibilityIcon,
    PlayArrow as PlayArrowIcon,
    RestartAlt as RestartIcon,
} from '@mui/icons-material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    getPaginationRowModel,
    flexRender,
    ColumnDef,
} from '@tanstack/react-table';
import { usePipelineExecutions } from '../api/hooks/usePipelinesExecutions';
import type { PipelineExecution } from '../api/types/pipelineExecutions.types';
import { useTimezone } from '../contexts/TimezoneContext';

const PAGE_SIZE = 20;

const ExecutionsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const { timezone } = useTimezone();
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
        return new Date(dateString).toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    const formatDuration = (seconds: string | null | undefined) => {
        if (!seconds) return '';
        const duration = parseFloat(seconds);
        if (isNaN(duration)) return '';
        if (duration < 60) {
            return `${duration.toFixed(2)}s`;
        }
        const minutes = Math.floor(duration / 60);
        const remainingSeconds = (duration % 60).toFixed(2);
        return `${minutes}m ${remainingSeconds}s`;
    };

    const handleRetryFromCurrent = (executionId: string) => {
        // TODO: Implement retry from current position
        console.log('Retry from current position:', executionId);
    };

    const handleRetryFromStart = (executionId: string) => {
        // TODO: Implement retry from start
        console.log('Retry from start:', executionId);
    };

    const columns = useMemo<ColumnDef<PipelineExecution>[]>(
        () => [
            {
                header: t('executions.columns.pipelineName'),
                accessorKey: 'pipeline_name',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ fontWeight: 500, color: theme.palette.primary.main }}>
                        {getValue() as string}
                    </Typography>
                ),
            },
            {
                header: t('executions.columns.status'),
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
                header: t('executions.columns.startTime'),
                accessorKey: 'start_time',
                cell: ({ getValue }) => (
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        {formatDate(getValue() as string)}
                    </Typography>
                ),
            },
            {
                header: t('executions.columns.duration'),
                accessorKey: 'duration_seconds',
                cell: ({ getValue }) => {
                    const duration = formatDuration(getValue() as string);
                    return duration ? (
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                            {duration}
                        </Typography>
                    ) : null;
                },
            },
            {
                header: t('executions.columns.actions'),
                id: 'actions',
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, position: 'relative' }}>
                        {row.original.status === 'FAILED' && (
                            <>
                                <Tooltip title={t('executions.actions.retryFromCurrent')}>
                                    <IconButton
                                        size="small"
                                        color="primary"
                                        onClick={() => handleRetryFromCurrent(row.original.execution_id)}
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
                                </Tooltip>
                                <Tooltip title={t('executions.actions.retryFromStart')}>
                                    <IconButton
                                        size="small"
                                        color="primary"
                                        onClick={() => handleRetryFromStart(row.original.execution_id)}
                                        sx={{
                                            position: 'relative',
                                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                            },
                                        }}
                                    >
                                        <RestartIcon fontSize="small" />
                                    </IconButton>
                                </Tooltip>
                            </>
                        )}
                        <IconButton
                            size="small"
                            color="primary"
                            title={t('executions.actions.viewDetails')}
                            sx={{
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                },
                            }}
                        >
                            <VisibilityIcon fontSize="small" />
                        </IconButton>
                    </Box>
                ),
            },
        ],
        [theme, t]
    );

    const executions = useMemo(() => {
        return data?.pages.flatMap(page => page.data.executions) || [];
    }, [data]);

    const table = useReactTable({
        data: executions,
        columns,
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
                            background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                            backgroundClip: 'text',
                            WebkitBackgroundClip: 'text',
                            color: 'transparent',
                        }}>
                            {t('executions.title')}
                        </Typography>
                        <Typography variant="body1" sx={{ color: theme.palette.text.secondary }}>
                            {t('executions.description')}
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
                            <InputLabel>{t('common.status')}</InputLabel>
                            <Select
                                value={filters.status}
                                label={t('common.status')}
                                onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
                            >
                                <MenuItem value="">{t('common.all')}</MenuItem>
                                <MenuItem value="SUCCEEDED">{t('executions.status.succeeded')}</MenuItem>
                                <MenuItem value="FAILED">{t('executions.status.failed')}</MenuItem>
                                <MenuItem value="RUNNING">{t('executions.status.running')}</MenuItem>
                                <MenuItem value="TIMED_OUT">{t('executions.status.timedOut')}</MenuItem>
                                <MenuItem value="ABORTED">{t('executions.status.aborted')}</MenuItem>
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
                            {t('common.refresh')}
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
                            {t('common.previous')}
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
                            {t('common.next')}
                        </Button>
                    </Box>
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                        {t('executions.pagination.page', {
                            page: table.getState().pagination.pageIndex + 1,
                            total: table.getPageCount()
                        })}
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
                                {t('executions.pagination.showEntries', { count: pageSize })}
                            </MenuItem>
                        ))}
                    </Select>
                </Box>
            </Paper>
        </Box>
    );
};

export default ExecutionsPage;
