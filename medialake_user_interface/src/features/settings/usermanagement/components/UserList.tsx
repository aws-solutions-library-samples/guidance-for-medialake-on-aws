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
            const sort = newSorting[0];
            onSortChange(sort.id, sort.desc);
        } else if (onSortChange) {
            onSortChange('', false);
        }
    };

    const handleFilterChange = (newFilters: ColumnFiltersState) => {
        setColumnFilters(newFilters);
        if (onFilterChange && newFilters.length > 0) {
            const filter = newFilters[0];
            onFilterChange(filter.id, filter.value as string);
        }
    };
    const [globalFilter, setGlobalFilter] = useState('');
    const [columnVisibility, setColumnVisibility] = useState({
        username: false,
    });
    const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
    const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null);
    const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);
    const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(null);

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString(undefined, {
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const columns = useMemo<ColumnDef<User>[]>(
        () => [
            {
                header: t('users.columns.username'),
                accessorKey: 'username',
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
                header: t('users.columns.firstName'),
                accessorKey: 'name',
                minSize: 120,
                size: 180,
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
                header: t('users.columns.lastName'),
                accessorKey: 'family_name',
                minSize: 120,
                size: 180,
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
                header: t('users.columns.email'),
                accessorKey: 'email',
                minSize: 200,
                size: 350,
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
                header: t('users.columns.status'),
                accessorKey: 'enabled',
                minSize: 100,
                size: 150,
                enableResizing: true,
                enableSorting: true,
                enableFiltering: true,
                cell: ({ getValue }) => {
                    const enabled = getValue() as boolean;
                    return (
                        <Chip
                            label={enabled ? t('users.status.active') : t('users.status.inactive')}
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
                header: t('users.columns.groups'),
                accessorKey: 'groups',
                minSize: 150,
                size: 250,
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
                                    {t('common.noGroups')}
                                </TableCellContent>
                            )}
                        </Box>
                    );
                },
            },
            {
                header: t('users.columns.created'),
                accessorKey: 'created',
                minSize: 150,
                size: 200,
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
                header: t('users.columns.modified'),
                accessorKey: 'modified',
                minSize: 150,
                size: 200,
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
                id: 'actions',
                header: t('users.columns.actions'),
                minSize: 120,
                size: 160,
                enableResizing: true,
                cell: ({ row }) => (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                        <Tooltip title={t('users.actions.edit')}>
                            <IconButton
                                size="small"
                                onClick={() => onEditUser(row.original)}
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
                        <Tooltip title={row.original.enabled ? t('users.actions.deactivate') : t('users.actions.activate')}>
                            <IconButton
                                size="small"
                                onClick={() => onToggleUserStatus(row.original.username, !row.original.enabled)}
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
                        <Tooltip title={t('users.actions.delete')}>
                            <IconButton
                                size="small"
                                onClick={() => onDeleteUser(row.original.username)}
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
        ],
        [theme, t, onEditUser, onDeleteUser, onToggleUserStatus]
    );

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

    return (
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
    );
};

export default UserList;
