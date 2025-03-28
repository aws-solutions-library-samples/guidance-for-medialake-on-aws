import React, { useMemo, useState, useRef } from 'react';
import {
    Box,
    Typography,
    Chip,
    Tooltip,
    IconButton,
    useTheme,
    alpha,
} from '@mui/material';
import {
    useReactTable,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    ColumnDef,
    SortingState,
    ColumnFiltersState,
    FilterFn,
    ColumnResizeMode,
    ColumnSizingState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import { User } from '@/api/types/api.types';
import { useTranslation } from 'react-i18next';
import { UserFilterPopover } from './UserFilterPopover';
import { ResizableTable, ColumnVisibilityMenu, TableCellContent } from '@/components/common/table';
import { UserTableToolbar } from './UserTableToolbar';
import { TableFiltersProvider, TableFilter, TableSort } from '@/components/common/table/context/TableFiltersContext';

interface UserListProps {
    users: User[];
    onEditUser: (user: User) => void;
    onDeleteUser: (username: string) => void;
    onToggleUserStatus: (username: string, newStatus: boolean) => void;
    activeFilters?: { columnId: string; value: string }[];
    activeSorting?: { columnId: string; desc: boolean }[];
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
    onFilterChange?: (columnId: string, value: string) => void;
    onSortChange?: (columnId: string, desc: boolean) => void;
}

const containsFilter: FilterFn<any> = (row, columnId, filterValue) => {
    const cellValue = row.getValue(columnId);
    if (cellValue == null) return false;

    // Handle date filtering
    if (typeof filterValue === 'object' && filterValue.filterDate) {
        const cellDate = new Date(cellValue as string);
        const dateStr = cellDate.toLocaleDateString();
        return dateStr === filterValue.value;
    }

    return String(cellValue)
        .toLowerCase()
        .includes(String(filterValue).toLowerCase());
};

const UserList: React.FC<UserListProps> = ({
    users,
    onEditUser,
    onDeleteUser,
    onToggleUserStatus,
    activeFilters = [],
    activeSorting = [],
    onRemoveFilter,
    onRemoveSort,
    onFilterChange,
    onSortChange,
}) => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [sorting, setSorting] = useState<SortingState>([]);
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

    // Sync external state with internal state
    React.useEffect(() => {
        if (activeSorting) {
            setSorting(activeSorting.map(sort => ({
                id: sort.columnId,
                desc: sort.desc
            })));
        }
    }, [activeSorting]);

    React.useEffect(() => {
        if (activeFilters) {
            setColumnFilters(activeFilters.map(filter => ({
                id: filter.columnId,
                value: filter.value
            })));
        }
    }, [activeFilters]);

    // Handle internal state changes
    const handleSortingChange = (newSorting: SortingState) => {
        setSorting(newSorting);
        if (onSortChange && newSorting.length > 0) {
            newSorting.forEach(sort => {
                onSortChange(sort.id, sort.desc);
            });
        } else if (onSortChange) {
            onSortChange('', false);
        }
    };

    const handleFilterChange = (newFilters: ColumnFiltersState) => {
        setColumnFilters(newFilters);
        if (onFilterChange && newFilters.length > 0) {
            newFilters.forEach(filter => {
                onFilterChange(filter.id, filter.value as string);
            });
        }
    };
    const [globalFilter, setGlobalFilter] = useState('');
    const [columnVisibility, setColumnVisibility] = useState({
        username: false,
        modified: false,
    });
    const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
    const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);
    const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);
    const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(null);

    const formatDate = (dateString: string, includeTime: boolean = false) => {
        const date = new Date(dateString);
        if (includeTime) {
            return date.toLocaleString(undefined, {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            });
        }
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    };

    const columns = useMemo<ColumnDef<User>[]>(() => {
        console.log('Theme in columns useMemo:', theme);
        return [
            {
                header: t('translation.common.columns.username'),
                accessorKey: 'username',
                minSize: 120,
                size: 180,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    console.log('Cell theme:', theme);
                    return (
                        <TableCellContent variant="primary">
                            {getValue() as string}
                        </TableCellContent>
                    );
                },
            },
            {
                header: t('translation.common.columns.firstName'),
                accessorKey: 'name',
                minSize: 100,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string || '-'}
                    </TableCellContent>
                ),
            },
            {
                header: t('translation.common.columns.lastName'),
                accessorKey: 'family_name',
                minSize: 120,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary">
                        {getValue() as string || '-'}
                    </TableCellContent>
                ),
            },
            {
                header: t('translation.common.columns.email'),
                accessorKey: 'email',
                minSize: 150,
                size: 275,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="secondary" wordBreak="break-all">
                        {getValue() as string}
                    </TableCellContent>
                ),
            },
            {
                header: t('translation.common.columns.status'),
                accessorKey: 'enabled',
                minSize: 100,
                size: 100,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const enabled = getValue() as boolean;
                    return (
                        <Chip
                            label={enabled ? t('translation.common.status.active') : t('translation.common.status.inactive')}
                            size="small"
                            sx={{
                                backgroundColor: enabled
                                    ? alpha(theme.palette.success.main, 0.1)
                                    : alpha(theme.palette.grey[500], 0.1),
                                color: enabled
                                    ? theme.palette.success.main
                                    : theme.palette.grey[500],
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
                header: t('translation.common.columns.groups'),
                accessorKey: 'groups',
                minSize: 120,
                size: 160,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const groups = getValue() as string[];
                    return (
                        <Box sx={{
                            display: 'flex',
                            gap: 1,
                            flexWrap: 'wrap',
                        }}>
                            {groups.length > 0 ? (
                                groups.map((group) => (
                                    <Chip
                                        key={group}
                                        label={group}
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
                                ))
                            ) : (
                                <TableCellContent variant="secondary">
                                    {t('translation.common.noGroups')}
                                </TableCellContent>
                            )}
                        </Box>
                    );
                },
            },
            {
                header: t('translation.common.columns.created'),
                accessorKey: 'created',
                minSize: 120,
                size: 120,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    return (
                        <Tooltip title={formatDate(dateValue, true)} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {formatDate(dateValue)}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                header: t('translation.common.columns.modified'),
                accessorKey: 'modified',
                minSize: 150,
                size: 200,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue() as string;
                    return (
                        <Tooltip title={formatDate(dateValue, true)} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {formatDate(dateValue)}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            },
            {
                id: 'actions',
                header: () => (
                    <Box sx={{ width: '100%', textAlign: 'center' }}>
                        {t('translation.common.columns.actions')}
                    </Box>
                ),
                minSize: 100,
                size: 120,
                enableResizing: true,
                enableSorting: false,
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        <Tooltip title={t('translation.common.actions.edit')}>
                            <IconButton
                                size="small"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onEditUser(row.original);
                                }}
                                sx={{
                                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                    },
                                }}
                            >
                                <EditIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={row.original.enabled ? t('translation.common.actions.deactivate') : t('translation.common.actions.activate')}>
                            <IconButton
                                size="small"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onToggleUserStatus(row.original.username, !row.original.enabled);
                                }}
                                sx={{
                                    backgroundColor: row.original.enabled
                                        ? alpha(theme.palette.success.main, 0.1)
                                        : alpha(theme.palette.grey[500], 0.1),
                                    '&:hover': {
                                        backgroundColor: row.original.enabled
                                            ? alpha(theme.palette.success.main, 0.2)
                                            : alpha(theme.palette.grey[500], 0.2),
                                    },
                                }}
                            >
                                {row.original.enabled ? <LockOpenIcon fontSize="small" /> : <LockIcon fontSize="small" />}
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={t('translation.common.actions.delete')}>
                            <IconButton
                                size="small"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteUser(row.original.username);
                                }}
                                sx={{
                                    backgroundColor: alpha(theme.palette.error.main, 0.1),
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.error.main, 0.2),
                                    },
                                }}
                            >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>
                ),
            },
        ];
    }, [theme, t, onEditUser, onDeleteUser, onToggleUserStatus]);

    const table = useReactTable({
        data: users,
        columns,
        filterFns: {
            contains: containsFilter,
        },
        state: {
            sorting,
            columnFilters,
            globalFilter,
            columnVisibility,
            columnSizing,
        },
        onSortingChange: handleSortingChange,
        onColumnFiltersChange: handleFilterChange,
        onGlobalFilterChange: setGlobalFilter,
        onColumnVisibilityChange: setColumnVisibility,
        onColumnSizingChange: setColumnSizing,
        getCoreRowModel: getCoreRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getSortedRowModel: getSortedRowModel(),
        columnResizeMode: 'onChange' as ColumnResizeMode,
    });

    const { rows } = table.getRowModel();
    const containerRef = useRef<HTMLDivElement>(null);

    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 53,
        overscan: 10,
    });

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

    const tableFiltersValue = useMemo(() => ({
        activeFilters: columnFilters.map(f => ({
            columnId: f.id,
            value: f.value as string
        })) as TableFilter[],
        activeSorting: sorting.map(s => ({
            columnId: s.id,
            desc: s.desc
        })) as TableSort[],
        onRemoveFilter,
        onRemoveSort,
        onFilterChange: (columnId: string, value: string) => {
            const newFilters = columnFilters.map(f => 
                f.id === columnId ? { ...f, value } : f
            );
            handleFilterChange(newFilters);
        },
        onSortChange: (columnId: string, desc: boolean) => {
            const newSorting = sorting.map(s => 
                s.id === columnId ? { ...s, desc } : s
            );
            handleSortingChange(newSorting);
        }
    }), [columnFilters, sorting, onRemoveFilter, onRemoveSort, handleFilterChange, handleSortingChange]);

    return (
        <TableFiltersProvider {...tableFiltersValue}>
            <Box sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
            }}>
                <UserTableToolbar
                    globalFilter={globalFilter}
                    onGlobalFilterChange={setGlobalFilter}
                    onColumnMenuOpen={handleColumnMenuOpen}
                    activeFilters={activeFilters}
                    activeSorting={activeSorting}
                    onRemoveFilter={onRemoveFilter}
                    onRemoveSort={onRemoveSort}
                />

                <ResizableTable
                    table={table}
                    containerRef={containerRef}
                    virtualizer={rowVirtualizer}
                    rows={rows}
                    onFilterClick={handleFilterMenuOpen}
                    activeFilters={activeFilters}
                    activeSorting={activeSorting}
                    onRemoveFilter={onRemoveFilter}
                    onRemoveSort={onRemoveSort}
                />

                <ColumnVisibilityMenu
                    anchorEl={columnMenuAnchor}
                    columns={table.getAllLeafColumns()}
                    onClose={handleColumnMenuClose}
                />

                <UserFilterPopover
                    anchorEl={filterMenuAnchor}
                    column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
                    onClose={handleFilterMenuClose}
                    users={users}
                />
            </Box>
        </TableFiltersProvider>
    );
};

export default UserList;
