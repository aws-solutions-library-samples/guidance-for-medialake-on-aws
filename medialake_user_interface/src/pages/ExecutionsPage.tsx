import React, { useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Typography,
    Button,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    useTheme,
    alpha,
    Chip,
    Menu,
    TextField,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    ColumnDef,
    SortingState,
    ColumnFiltersState,
    ColumnSizingState,
    ColumnResizeMode,
} from '@tanstack/react-table';

import { ExecutionsTable } from '../features/executions/components/ExecutionsTable';
import { TableCellContent } from '../components/common/table';
import { usePipelineExecutions } from '../api/hooks/usePipelinesExecutions';
import type { PipelineExecution, PipelineExecutionFilters } from '../api/types/pipelineExecutions.types';

const PAGE_SIZE = 20;

const ExecutionsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();

    const [sorting, setSorting] = useState<SortingState>([]);
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
    const [columnVisibility, setColumnVisibility] = useState({});
    const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
    const [statusFilter, setStatusFilter] = useState('');
    const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);
    const [filterColumn, setFilterColumn] = useState<string | null>(null);
    const [searchValue, setSearchValue] = useState('');
    const [dropdownValue, setDropdownValue] = useState('');

    const filters = useMemo<PipelineExecutionFilters>(() => ({
        status: statusFilter || undefined,
        sortBy: sorting[0]?.id || 'start_time',
        sortOrder: sorting[0]?.desc ? 'desc' as const : 'asc' as const
    }), [statusFilter, sorting]);

    const { data, isLoading, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } = usePipelineExecutions(PAGE_SIZE, filters);

    const handleSortingChange = useCallback((newSorting: SortingState) => {
        setSorting(newSorting);
    }, []);

    const handleFilterChange = useCallback((columnId: string, value: string, type: 'search' | 'dropdown') => {
        if (type === 'search') {
            setSearchValue(value);
        } else {
            setDropdownValue(value);
            if (columnId === 'status') {
                setStatusFilter(value);
            }
        }
    }, []);

    const getStatusColor = useCallback((status: string) => {
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
    }, [theme]);

    const formatDate = useCallback((dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    }, []);

    const formatDuration = useCallback((seconds: string | null | undefined) => {
        if (!seconds) return '';
        const duration = parseFloat(seconds);
        if (isNaN(duration)) return '';
        if (duration < 60) {
            return `${duration.toFixed(2)}s`;
        }
        const minutes = Math.floor(duration / 60);
        const remainingSeconds = (duration % 60).toFixed(2);
        return `${minutes}m ${remainingSeconds}s`;
    }, []);

    const handleRetryFromCurrent = useCallback((executionId: string) => {
        // TODO: Implement retry from current position
        console.log('Retry from current position:', executionId);
    }, []);

    const handleRetryFromStart = useCallback((executionId: string) => {
        // TODO: Implement retry from start
        console.log('Retry from start:', executionId);
    }, []);

    const handleViewDetails = useCallback((executionId: string) => {
        navigate(`/executions/${executionId}`);
    }, [navigate]);

    const handleFilterColumn = useCallback((event: React.MouseEvent<HTMLElement>, columnId: string) => {
        setFilterColumn(columnId);
        setFilterMenuAnchor(event.currentTarget);
    }, []);

    const handleFilterClose = useCallback(() => {
        setFilterMenuAnchor(null);
        setFilterColumn(null);
        setSearchValue('');
        setDropdownValue('');
    }, []);

    const handleFilterApply = useCallback(() => {
        if (filterColumn) {
            const newFilters = [];
            if (searchValue) {
                newFilters.push({ id: filterColumn, value: searchValue });
            }
            if (dropdownValue) {
                if (filterColumn === 'status') {
                    newFilters.push({ id: filterColumn, value: dropdownValue });
                } else {
                    newFilters.push({ id: `${filterColumn}_type`, value: dropdownValue });
                }
            }
            setColumnFilters(prev => [
                ...prev.filter(f => !f.id.startsWith(filterColumn)),
                ...newFilters
            ]);
        }
        handleFilterClose();
    }, [filterColumn, searchValue, dropdownValue, handleFilterClose]);

    const handleRemoveFilter = useCallback((columnId: string) => {
        setColumnFilters(prev => prev.filter(f => !f.id.startsWith(columnId)));
        if (columnId === 'status') {
            setStatusFilter('');
        }
    }, []);

    const columns = useMemo<ColumnDef<PipelineExecution>[]>(
        () => [
            {
                header: t('executions.columns.pipelineName'),
                accessorKey: 'pipeline_name',
                minSize: 120,
                size: 180,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="primary">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('executions.columns.status'),
                accessorKey: 'status',
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
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
                minSize: 150,
                size: 180,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {formatDate(getValue() as string)}
                    </TableCellContent>
                ),
            },
            {
                header: t('executions.columns.duration'),
                accessorKey: 'duration_seconds',
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {formatDuration(getValue() as string)}
                    </TableCellContent>
                ),
            },
            {
                id: 'actions',
                header: () => (
                    <Box sx={{ width: '100%', textAlign: 'center' }}>
                        {t('executions.columns.actions')}
                    </Box>
                ),
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: false,
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        {row.original.status === 'FAILED' && (
                            <>
                                <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => handleRetryFromCurrent(row.original.execution_id)}
                                    sx={{
                                        minWidth: 0,
                                        p: 1,
                                        borderRadius: '8px',
                                        borderColor: alpha(theme.palette.primary.main, 0.1),
                                        '&:hover': {
                                            borderColor: alpha(theme.palette.primary.main, 0.2),
                                        },
                                    }}
                                >
                                    {t('executions.actions.retryFromCurrent')}
                                </Button>
                                <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => handleRetryFromStart(row.original.execution_id)}
                                    sx={{
                                        minWidth: 0,
                                        p: 1,
                                        borderRadius: '8px',
                                        borderColor: alpha(theme.palette.primary.main, 0.1),
                                        '&:hover': {
                                            borderColor: alpha(theme.palette.primary.main, 0.2),
                                        },
                                    }}
                                >
                                    {t('executions.actions.retryFromStart')}
                                </Button>
                            </>
                        )}
                        {/* <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleViewDetails(row.original.execution_id)}
                            sx={{
                                minWidth: 0,
                                p: 1,
                                borderRadius: '8px',
                                borderColor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': {
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                },
                            }}
                        >
                            {t('executions.actions.viewDetails')}
                        </Button> */}
                    </Box>
                ),
            },
        ],
        [theme, t, getStatusColor, formatDate, formatDuration, handleRetryFromCurrent, handleRetryFromStart, handleViewDetails]
    );

    const executions = useMemo(() => {
        if (!data?.pages) return [];
        return data.pages.flatMap(page => page.data.executions);
    }, [data]);

    const table = useReactTable({
        data: executions,
        columns,
        state: {
            sorting,
            columnFilters,
            columnVisibility,
            columnSizing,
        },
        enableSorting: true,
        manualSorting: true,
        manualFiltering: true,
        onSortingChange: handleSortingChange,
        onColumnFiltersChange: setColumnFilters,
        onColumnVisibilityChange: setColumnVisibility,
        onColumnSizingChange: setColumnSizing,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        columnResizeMode: 'onChange' as ColumnResizeMode,
    });

    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                        <Typography variant="h4" sx={{
                            fontWeight: 700,
                            mb: 1,
                            color: theme.palette.primary.main,
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
                                value={statusFilter}
                                label={t('common.status')}
                                onChange={(e) => setStatusFilter(e.target.value)}
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

            <Box sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                minHeight: 0 // Important for proper flex behavior
            }}>
                <ExecutionsTable
                    table={table}
                    isLoading={isLoading}
                    data={executions}
                    onViewDetails={handleViewDetails}
                    onRetryFromCurrent={handleRetryFromCurrent}
                    onRetryFromStart={handleRetryFromStart}
                    onFilterColumn={handleFilterColumn}
                    activeFilters={columnFilters.map(f => ({ columnId: f.id, value: f.value as string }))}
                    onRemoveFilter={handleRemoveFilter}
                />

                {hasNextPage && (
                    <Box sx={{
                        p: 2,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                    }}>
                        <Button
                            onClick={() => fetchNextPage()}
                            disabled={!hasNextPage || isFetchingNextPage}
                            sx={{
                                textTransform: 'none',
                                borderRadius: '8px',
                                color: theme.palette.text.secondary,
                                '&:hover': {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                },
                            }}
                        >
                            {isFetchingNextPage
                                ? t('common.loading')
                                : t('common.loadMore')}
                        </Button>
                    </Box>
                )}
            </Box>

            <Menu
                anchorEl={filterMenuAnchor}
                open={Boolean(filterMenuAnchor)}
                onClose={handleFilterClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                <Box sx={{ p: 2, minWidth: 300 }}>
                    {filterColumn !== 'status' && (
                        <TextField
                            fullWidth
                            size="small"
                            label={t('common.searchValue')}
                            value={searchValue}
                            onChange={(e) => handleFilterChange(filterColumn!, e.target.value, 'search')}
                            sx={{ mb: 2 }}
                        />
                    )}
                    <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                        <InputLabel>{t('common.filterType')}</InputLabel>
                        <Select
                            value={dropdownValue}
                            label={t('common.filterType')}
                            onChange={(e) => handleFilterChange(filterColumn!, e.target.value, 'dropdown')}
                        >
                            <MenuItem value="">{t('common.all')}</MenuItem>
                            {filterColumn === 'status' && (
                                <>
                                    <MenuItem value="SUCCEEDED">{t('executions.status.succeeded')}</MenuItem>
                                    <MenuItem value="FAILED">{t('executions.status.failed')}</MenuItem>
                                    <MenuItem value="RUNNING">{t('executions.status.running')}</MenuItem>
                                    <MenuItem value="TIMED_OUT">{t('executions.status.timedOut')}</MenuItem>
                                    <MenuItem value="ABORTED">{t('executions.status.aborted')}</MenuItem>
                                </>
                            )}
                            {filterColumn === 'pipeline_name' && (
                                <>
                                    <MenuItem value="image">Image Pipeline</MenuItem>
                                    <MenuItem value="video">Video Pipeline</MenuItem>
                                </>
                            )}
                            {filterColumn === 'duration_seconds' && (
                                <>
                                    <MenuItem value="<60">Less than 1 minute</MenuItem>
                                    <MenuItem value="60-300">1-5 minutes</MenuItem>
                                    <MenuItem value=">300">More than 5 minutes</MenuItem>
                                </>
                            )}
                            {filterColumn === 'start_time' && (
                                <>
                                    <MenuItem value="today">Today</MenuItem>
                                    <MenuItem value="yesterday">Yesterday</MenuItem>
                                    <MenuItem value="last7days">Last 7 days</MenuItem>
                                    <MenuItem value="last30days">Last 30 days</MenuItem>
                                </>
                            )}
                        </Select>
                    </FormControl>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        <Button
                            size="small"
                            onClick={handleFilterClose}
                            sx={{ textTransform: 'none' }}
                        >
                            {t('common.cancel')}
                        </Button>
                        <Button
                            size="small"
                            variant="contained"
                            onClick={handleFilterApply}
                            sx={{ textTransform: 'none' }}
                        >
                            {t('common.apply')}
                        </Button>
                    </Box>
                </Box>
            </Menu>
        </Box>
    );
};

export default ExecutionsPage;
