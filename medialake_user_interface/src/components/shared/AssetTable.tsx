import React, { useRef, useState, useCallback, useEffect } from 'react';
import { Box, Typography, IconButton, TextField, Button, TableContainer, Checkbox } from '@mui/material';
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
import FavoriteIcon from '@mui/icons-material/Favorite';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import { AssetAudio } from '../asset';

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
    getAssetType?: (item: T) => string;
    editingId?: string;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onEditNameComplete?: (item: T, save: boolean) => void;
    onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: Array<{ columnId: string; value: string }>;
    onRemoveFilter?: (columnId: string) => void;
    isSelected?: (item: T) => boolean;
    onSelectToggle?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    isFavorite?: (item: T) => boolean;
    onFavoriteToggle?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
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
    getAssetType = () => 'Image', // Default to Image if not provided
    editingId,
    editedName,
    onEditNameChange,
    onEditNameComplete,
    onFilterClick,
    activeFilters = [],
    onRemoveFilter,
    isSelected = () => false,
    onSelectToggle,
    isFavorite = () => false,
    onFavoriteToggle,
}: AssetTableProps<T>): React.ReactElement {
    const containerRef = useRef<HTMLDivElement>(null);
    const columnHelper = createColumnHelper<T>();
    const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
    
    // Log props for debugging - keep this for now to help debugging
    console.log('AssetTable props:', {
        dataLength: data.length,
        isSelectedProvided: !!isSelected,
        onSelectToggleProvided: !!onSelectToggle,
        isFavoriteProvided: !!isFavorite,
        onFavoriteToggleProvided: !!onFavoriteToggle
    });
    
    // Add state to track if all rows are selected
    const [allSelected, setAllSelected] = useState(false);
    const [someSelected, setSomeSelected] = useState(false);
    
    // Function to handle selecting/deselecting all rows
    const handleSelectAll = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        console.log('handleSelectAll called with checked:', e.target.checked);
        if (onSelectToggle) {
            const visibleRows = data;
            visibleRows.forEach(row => {
                if (e.target.checked !== isSelected(row)) {
                    onSelectToggle(row, e as any);
                }
            });
        } else {
            console.log('onSelectToggle is not defined');
        }
    }, [data, onSelectToggle, isSelected]);
    
    // Update allSelected and someSelected states when data or isSelected changes
    useEffect(() => {
        if (data.length === 0) {
            setAllSelected(false);
            setSomeSelected(false);
            return;
        }
        
        const selectedCount = data.filter(row => isSelected(row)).length;
        setAllSelected(selectedCount === data.length);
        setSomeSelected(selectedCount > 0 && selectedCount < data.length);
    }, [data, isSelected]);

    const tableColumns = React.useMemo(() => {
        const visibleColumns = columns.filter(col => col.visible);
        return [
            // Selection checkbox column
            // Custom header component for the select column
            columnHelper.display({
                id: 'select',
                // Use a custom header component
                header: () => (
                    <Box sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Checkbox
                            size="small"
                            checked={allSelected}
                            indeterminate={someSelected}
                            onChange={(e) => {
                                e.stopPropagation();
                                handleSelectAll(e);
                            }}
                            sx={{
                                padding: 0,
                                '& .MuiSvgIcon-root': {
                                    fontSize: '1.2rem'
                                },
                                '&.Mui-checked': {
                                    color: 'primary.main'
                                },
                                '&.MuiCheckbox-indeterminate': {
                                    color: 'primary.main'
                                }
                            }}
                        />
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            Select All
                        </Typography>
                    </Box>
                ),
                enableSorting: false,
                size: 100,
                cell: info => (
                    <Box sx={{ p: 1, display: 'flex', justifyContent: 'center' }}>
                        {onSelectToggle ? (
                            <Checkbox
                                size="small"
                                checked={isSelected(info.row.original)}
                                onChange={(e) => {
                                    e.stopPropagation();
                                    console.log('Checkbox onChange in row cell');
                                    onSelectToggle(info.row.original, e as any);
                                }}
                                sx={{
                                    padding: 0,
                                    '& .MuiSvgIcon-root': {
                                        fontSize: '1.2rem'
                                    },
                                    '&.Mui-checked': {
                                        color: 'primary.main'
                                    }
                                }}
                            />
                        ) : (
                            <Typography variant="caption" color="text.secondary">
                                -
                            </Typography>
                        )}
                    </Box>
                )
            }),
            
            columnHelper.accessor(row => getThumbnailUrl(row), {
                id: 'preview',
                header: 'Preview',
                size: 100,
                enableSorting: false,
                cell: info => {
                    const assetType = getAssetType(info.row.original);
                    
                    if (assetType === 'Audio') {
                        return (
                            <Box sx={{ p: 1 }}>
                                <Box
                                    sx={{
                                        width: 150,
                                        height: 60,
                                        borderRadius: 1,
                                        overflow: 'hidden',
                                    }}
                                >
                                    <AssetAudio 
                                        src={info.getValue()} 
                                        alt={getName(info.row.original)}
                                        compact={true}
                                    />
                                </Box>
                            </Box>
                        );
                    }
                    
                    return (
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
                    );
                }
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
                                <Box sx={{ 
                                    display: 'flex', 
                                    alignItems: isEditing ? 'flex-start' : 'center', 
                                    gap: 1, 
                                    p: 1,
                                    minWidth: 0,
                                    width: '100%'
                                }}>
                                    {isEditing ? (
                                        <Box sx={{ 
                                            display: 'flex', 
                                            flexDirection: 'column',
                                            gap: 1, 
                                            width: '100%'
                                        }}>
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
                                                sx={{ 
                                                    flex: 1,
                                                    minWidth: '100%',
                                                    '& .MuiInputBase-root': {
                                                        width: '100%',
                                                        minHeight: '2.5em',
                                                        height: 'auto',
                                                    },
                                                    '& .MuiInputBase-input': {
                                                        whiteSpace: 'normal',
                                                        wordBreak: 'break-word',
                                                        overflow: 'visible',
                                                        textOverflow: 'clip',
                                                        width: '100%',
                                                        minHeight: '1.5em',
                                                        height: 'auto',
                                                        lineHeight: '1.5',
                                                    }
                                                }}
                                                multiline
                                                fullWidth
                                            />
                                            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', mt: 1 }}>
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
                size: 150,
                cell: info => (
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', p: 1 }}>
                        <IconButton
                            size="small"
                            onClick={(e) => {
                                e.stopPropagation();
                                if (onFavoriteToggle) {
                                    onFavoriteToggle(info.row.original, e);
                                }
                            }}
                            sx={{
                                padding: '4px',
                            }}
                        >
                            {isFavorite(info.row.original) ? (
                                <FavoriteIcon fontSize="small" color="error" />
                            ) : (
                                <FavoriteBorderIcon fontSize="small" />
                            )}
                        </IconButton>
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
    }, [columns, editingId, editedName, onSelectToggle, isSelected, allSelected, someSelected, handleSelectAll, onFavoriteToggle, isFavorite, columnHelper]);

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
