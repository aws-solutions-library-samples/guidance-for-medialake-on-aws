import React, { useRef, useState } from 'react';
import { Box, Typography, IconButton, TextField, Button, TableContainer } from '@mui/material';
import {
    useReactTable,
    getCoreRowModel,
    getSortedRowModel,
    getFilteredRowModel,
    createColumnHelper,
    type SortingState,
    type ColumnFiltersState,
    type Row,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ResizableTable } from '../common/table';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { type AssetTableColumn } from '@/types/shared/assetComponents';

export interface AssetTableProps<T> {
    data: T[];
    columns: AssetTableColumn<T>[];
    sorting: SortingState;
    onSortingChange: (sorting: SortingState) => void;
    onDeleteClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onEditClick?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onAssetClick: (item: T) => void;
    getThumbnailUrl: (item: T) => string;
    getName: (item: T) => string;
    getId: (item: T) => string;
    editingId?: string;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onEditNameComplete?: (item: T, save: boolean) => void;
    onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: Array<{ columnId: string; value: string }>;
    onRemoveFilter?: (columnId: string) => void;
}

export function AssetTable<T>({
    data,
    columns,
    sorting,
    onSortingChange,
    onDeleteClick,
    onMenuClick,
    onEditClick,
    onAssetClick,
    getThumbnailUrl,
    getName,
    getId,
    editingId,
    editedName,
    onEditNameChange,
    onEditNameComplete,
    onFilterClick,
    activeFilters = [],
    onRemoveFilter,
}: AssetTableProps<T>): React.ReactElement {
    const containerRef = useRef<HTMLDivElement>(null);
    const columnHelper = createColumnHelper<T>();
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

    const tableColumns = React.useMemo(() => {
        const visibleColumns = columns.filter(col => col.visible);
        return [
            columnHelper.accessor(row => getThumbnailUrl(row), {
                id: 'preview',
                header: 'Preview',
                size: 100,
                enableSorting: false,
                cell: info => (
                    <Box sx={{ p: 1 }}>
                        <Box
                            component="img"
                            src={info.getValue()}
                            alt={getName(info.row.original)}
                            sx={{
                                width: 60,
                                height: 60,
                                objectFit: 'cover',
                                borderRadius: 1,
                                display: 'block'
                            }}
                        />
                    </Box>
                )
            }),
            ...visibleColumns.map(col => columnHelper.accessor(
                row => col.accessorFn ? col.accessorFn(row) : (row as any)[col.id],
                {
                    id: col.id,
                    header: col.label,
                    size: col.minWidth,
                    enableSorting: true,
                    cell: info => {
                        if (col.id === 'name' && onEditClick) {
                            const isEditing = editingId === getId(info.row.original);
                            return (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1 }}>
                                    {isEditing ? (
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                            <TextField
                                                value={editedName}
                                                onChange={onEditNameChange}
                                                onKeyPress={(e) => {
                                                    if (e.key === 'Enter') {
                                                        onEditNameComplete?.(info.row.original, true);
                                                    } else if (e.key === 'Escape') {
                                                        onEditNameComplete?.(info.row.original, false);
                                                    }
                                                }}
                                                onClick={(e) => e.stopPropagation()}
                                                autoFocus
                                                size="small"
                                                sx={{ flex: 1 }}
                                            />
                                            <Box sx={{ display: 'flex', gap: 1 }}>
                                                <Button
                                                    size="small"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onEditNameComplete?.(info.row.original, true);
                                                    }}
                                                    variant="contained"
                                                >
                                                    Save
                                                </Button>
                                                <Button
                                                    size="small"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onEditNameComplete?.(info.row.original, false);
                                                    }}
                                                >
                                                    Cancel
                                                </Button>
                                            </Box>
                                        </Box>
                                    ) : (
                                        <>
                                            <Typography>{info.getValue()}</Typography>
                                            <IconButton
                                                size="small"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onEditClick(info.row.original, e);
                                                }}
                                            >
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                        </>
                                    )}
                                </Box>
                            );
                        }
                        return (
                            <Box sx={{ p: 1 }}>
                                {col.cell ? col.cell(info) : info.getValue()}
                            </Box>
                        );
                    }
                }
            )),
            columnHelper.display({
                id: 'actions',
                header: 'Actions',
                size: 100,
                cell: info => (
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', p: 1 }}>
                        <IconButton
                            size="small"
                            onClick={(e) => onDeleteClick(info.row.original, e)}
                        >
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                            size="small"
                            onClick={(e) => onMenuClick(info.row.original, e)}
                            id={`asset-menu-button-${getId(info.row.original)}`}
                            aria-haspopup="true"
                            sx={{
                                position: 'relative',
                                zIndex: 1
                            }}
                        >
                            <MoreVertIcon fontSize="small" />
                        </IconButton>
                    </Box>
                )
            })
        ];
    }, [columns, editingId, editedName]);

    const table = useReactTable({
        data,
        columns: tableColumns,
        state: {
            sorting,
            columnFilters,
        },
        onSortingChange,
        onColumnFiltersChange: setColumnFilters,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        filterFns: {
            includesString: (row, columnId, filterValue) => {
                const value = String(row.getValue(columnId) || '').toLowerCase();
                return value.includes(String(filterValue).toLowerCase());
            }
        },
    });

    const { rows } = table.getRowModel();
    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 53,
        overscan: 20,
    });

    const handleRowClick = (row: Row<T>) => {
        if (!editingId) {
            onAssetClick(row.original);
        }
    };

    return (
        <TableContainer 
            sx={{ 
                maxHeight: '100%',
                overflowY: 'visible',
                width: '100%',
                border: 'none',
                '& .MuiTable-root': {
                    borderCollapse: 'separate',
                    borderSpacing: 0,
                }
            }}
        >
            <ResizableTable
                table={table}
                containerRef={containerRef}
                virtualizer={rowVirtualizer}
                rows={rows}
                onRowClick={handleRowClick}
                maxHeight="none"
                onFilterClick={onFilterClick}
                activeFilters={activeFilters}
                onRemoveFilter={onRemoveFilter}
            />
        </TableContainer>
    );
}

export default AssetTable;
