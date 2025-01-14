import React, { useRef, useEffect } from 'react';
import { Box, Typography, IconButton, TextField, Button } from '@mui/material';
import {
    useReactTable,
    getCoreRowModel,
    getSortedRowModel,
    createColumnHelper,
    type SortingState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ResizableTable } from '../common/table';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import MoreVertIcon from '@mui/icons-material/MoreVert';

export interface AssetTableColumn<T> {
    id: string;
    label: string;
    visible: boolean;
    minWidth: number;
    format?: (value: any) => string | React.ReactNode;
    accessor?: (row: T) => any;
}

export interface AssetTableProps<T> {
    data: T[];
    columns: AssetTableColumn<T>[];
    sorting: SortingState;
    onSortingChange: (sorting: SortingState) => void;
    onDeleteClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onEditClick?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onRowClick?: (item: T) => void;
    getThumbnailUrl: (item: T) => string;
    getName: (item: T) => string;
    getId: (item: T) => string;
    editingId?: string;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
    onEditNameComplete?: (item: T, save: boolean) => void;
}

function AssetTable<T>({
    data,
    columns,
    sorting,
    onSortingChange,
    onDeleteClick,
    onMenuClick,
    onEditClick,
    onRowClick,
    getThumbnailUrl,
    getName,
    getId,
    editingId,
    editedName,
    onEditNameChange,
    onEditNameComplete,
}: AssetTableProps<T>) {
    const containerRef = useRef<HTMLDivElement>(null);
    const columnHelper = createColumnHelper<T>();
    const cursorPositionRef = useRef<number | null>(null);

    const handleDeleteClick = (item: T) => (event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        onDeleteClick(item, event);
    };

    const handleMenuClick = (item: T) => (event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        onMenuClick(item, event);
    };

    const handleEditClick = (item: T) => (event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        onEditClick?.(item, event);
    };

    useEffect(() => {
        if (cursorPositionRef.current !== null) {
            const input = document.querySelector(`input[value="${editedName}"]`) as HTMLInputElement;
            if (input) {
                input.setSelectionRange(cursorPositionRef.current, cursorPositionRef.current);
            }
            cursorPositionRef.current = null;
        }
    }, [editedName]);

    const tableColumns = React.useMemo(() => {
        const visibleColumns = columns.filter(col => col.visible);
        return [
            columnHelper.accessor(row => getThumbnailUrl(row), {
                id: 'preview',
                header: 'Preview',
                size: 100,
                cell: (info) => (
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
            ...visibleColumns.map(col =>
                columnHelper.accessor(
                    row => col.accessor ? col.accessor(row) : (row as any)[col.id],
                    {
                        id: col.id,
                        header: col.label,
                        size: col.minWidth,
                        cell: (info) => {
                            if (col.id === 'name' && onEditClick) {
                                const isEditing = editingId === getId(info.row.original);
                                return (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1 }}>
                                        {isEditing ? (
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                                <TextField
                                                    value={editedName}
                                                    onChange={(e) => {
                                                        cursorPositionRef.current = e.target.selectionStart;
                                                        onEditNameChange?.(e);
                                                    }}
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
                                                    inputRef={(input) => {
                                                        if (input && cursorPositionRef.current !== null) {
                                                            input.setSelectionRange(cursorPositionRef.current, cursorPositionRef.current);
                                                        }
                                                    }}
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
                                                    onClick={handleEditClick(info.row.original)}
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
                                    {col.format ? col.format(info.getValue()) : info.getValue()}
                                </Box>
                            );
                        }
                    }
                )
            ),
            columnHelper.display({
                id: 'actions',
                header: 'Actions',
                size: 100,
                cell: (info) => (
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', p: 1 }}>
                        <IconButton
                            size="small"
                            onClick={handleDeleteClick(info.row.original)}
                        >
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                            size="small"
                            onClick={handleMenuClick(info.row.original)}
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
            sorting
        },
        onSortingChange,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel()
    });

    const rowVirtualizer = useVirtualizer({
        count: table.getRowModel().rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 76, // Increased to account for padding
        overscan: 10,
    });

    return (
        <ResizableTable
            table={table}
            containerRef={containerRef}
            virtualizer={rowVirtualizer}
            rows={table.getRowModel().rows}
            maxHeight="none"
            onRowClick={onRowClick ? (row) => onRowClick(row.original) : undefined}
        />
    );
}

export default AssetTable;
