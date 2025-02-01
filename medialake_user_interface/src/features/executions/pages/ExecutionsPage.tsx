import React, { useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Box, Button, useTheme, alpha, Chip, Popover } from '@mui/material';
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

import { PageHeader, PageContent } from '@/components/common/layout';
import { BaseTableToolbar } from '@/components/common/table/BaseTableToolbar';
import { ExecutionsTable } from '../components/ExecutionsTable';
import { TableCellContent } from '@/components/common/table';
import { BaseFilterPopover } from '@/components/common/table/BaseFilterPopover';
import { usePipelineExecutions } from '../api/hooks/usePipelineExecutions';
import type { PipelineExecution, PipelineExecutionFilters } from '../types/pipelineExecutions.types';

const PAGE_SIZE = 20;

const ExecutionsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();

    const [sorting, setSorting] = useState<SortingState>([]);
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
    const [columnVisibility, setColumnVisibility] = useState({});
    const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
    const [globalFilter, setGlobalFilter] = useState('');
    const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);
    const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(null);

    const filters = useMemo<PipelineExecutionFilters>(() => ({
        sortBy: sorting[0]?.id || 'start_time',
        sortOrder: sorting[0]?.desc ? 'desc' as const : 'asc' as const,
        ...columnFilters.reduce((acc, filter) => ({
            ...acc,
            [filter.id]: filter.value
        }), {})
    }), [sorting, columnFilters]);

    const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } = usePipelineExecutions(PAGE_SIZE, filters);

    const handleSortingChange = useCallback((newSorting: SortingState) => {
        setSorting(newSorting);
    }, []);

    const handleFilterColumn = useCallback((event: React.MouseEvent<HTMLElement>, columnId: string) => {
        setActiveFilterColumn(columnId);
        setColumnMenuAnchor(event.currentTarget);
    }, []);

    const handleFilterMenuClose = useCallback(() => {
        setColumnMenuAnchor(null);
        setActiveFilterColumn(null);
    }, []);

    const handleFilterChange = useCallback((columnId: string, value: string) => {
        setColumnFilters(prev => {
            const existing = prev.find(f => f.id === columnId);
            if (existing) {
                return prev.map(f => f.id === columnId ? { ...f, value } : f);
            }
            return [...prev, { id: columnId, value }];
        });
        setColumnMenuAnchor(null);
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
                filterFn: 'includesString',
                filter: 'includesString',
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
                    </Box>
                ),
            },
        ],
        [theme, t, getStatusColor, formatDate, formatDuration, handleRetryFromCurrent, handleRetryFromStart]
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
            globalFilter,
        },
        enableSorting: true,
        enableFilters: true,
        manualSorting: true,
        manualFiltering: true,
        onSortingChange: handleSortingChange,
        onColumnFiltersChange: setColumnFilters,
        onColumnVisibilityChange: setColumnVisibility,
        onColumnSizingChange: setColumnSizing,
        onGlobalFilterChange: setGlobalFilter,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        columnResizeMode: 'onChange' as ColumnResizeMode,
        filterFns: {
            includesString: (row, columnId, filterValue) => {
                const value = String(row.getValue(columnId) || '').toLowerCase();
                return value.includes(String(filterValue).toLowerCase());
            }
        },
    });

    const activeColumn = activeFilterColumn ? table.getColumn(activeFilterColumn) : null;

    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <PageHeader
                title={t('executions.title')}
                description={t('executions.description')}
            />

            <BaseTableToolbar
                globalFilter={globalFilter}
                onGlobalFilterChange={setGlobalFilter}
                onColumnMenuOpen={(event) => setColumnMenuAnchor(event.currentTarget)}
                activeFilters={columnFilters.map(f => ({ columnId: f.id, value: f.value as string }))}
                activeSorting={sorting.map(s => ({ columnId: s.id, desc: s.desc }))}
                onRemoveFilter={(columnId) => {
                    setColumnFilters(prev => prev.filter(f => f.id !== columnId));
                }}
                onRemoveSort={(columnId) => {
                    setSorting(prev => prev.filter(s => s.id !== columnId));
                }}
                searchPlaceholder={t('executions.searchPlaceholder')}
            />

            <PageContent
                isLoading={isLoading}
                error={error as Error}
            >
                <ExecutionsTable
                    table={table}
                    isLoading={isLoading}
                    data={executions}
                    onViewDetails={handleViewDetails}
                    onRetryFromCurrent={handleRetryFromCurrent}
                    onRetryFromStart={handleRetryFromStart}
                    onFilterColumn={handleFilterColumn}
                    activeFilters={columnFilters.map(f => ({ columnId: f.id, value: f.value as string }))}
                    activeSorting={sorting.map(s => ({ columnId: s.id, desc: s.desc }))}
                    onRemoveFilter={(columnId) => {
                        setColumnFilters(prev => prev.filter(f => f.id !== columnId));
                    }}
                    onRemoveSort={(columnId) => {
                        setSorting(prev => prev.filter(s => s.id !== columnId));
                    }}
                />

                <BaseFilterPopover
                    anchorEl={columnMenuAnchor}
                    column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
                    onClose={handleFilterMenuClose}
                    data={executions}
                    getUniqueValues={(columnId, data) => {
                        return Array.from(new Set(data.map(item => {
                            const value = item[columnId as keyof PipelineExecution];
                            return value ? String(value) : '';
                        }))).filter(Boolean);
                    }}
                    formatValue={(columnId, value) => {
                        switch (columnId) {
                            case 'start_time':
                                return formatDate(value);
                            case 'duration_seconds':
                                return formatDuration(value);
                            default:
                                return value;
                        }
                    }}
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
            </PageContent>
        </Box>
    );
};

export default ExecutionsPage;