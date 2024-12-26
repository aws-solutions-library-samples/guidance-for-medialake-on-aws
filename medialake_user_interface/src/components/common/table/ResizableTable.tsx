import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Box,
    useTheme,
    alpha,
} from '@mui/material';
import {
    Table as TanStackTable,
    flexRender,
    Row,
} from '@tanstack/react-table';
import { Virtualizer } from '@tanstack/react-virtual';
import { TableHeader } from './TableHeader';
import { TableCellContent } from './TableCellContent';

interface ResizableTableProps<T> {
    table: TanStackTable<T>;
    containerRef: React.RefObject<HTMLDivElement>;
    virtualizer: Virtualizer<HTMLDivElement, Element>;
    rows: Row<T>[];
    maxHeight?: string;
    onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: { columnId: string; value: string }[];
    activeSorting?: { columnId: string; desc: boolean }[];
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
}

export function ResizableTable<T>({
    table,
    containerRef,
    virtualizer,
    rows,
    maxHeight = 'calc(100vh - 300px)',
    onFilterClick,
    activeFilters = [],
    activeSorting = [],
    onRemoveFilter,
    onRemoveSort,
}: ResizableTableProps<T>) {
    const theme = useTheme();

    // Calculate total width of all columns
    const totalWidth = table.getAllColumns().reduce((acc, column) => {
        return acc + (column.getSize() || 0);
    }, 0);

    const hasActiveTags = activeFilters.length > 0 || activeSorting.length > 0;

    return (
        <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
            {hasActiveTags && (
                <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {activeFilters.map(({ columnId, value }) => (
                        <Box
                            key={`filter-${columnId}`}
                            sx={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                px: 2,
                                py: 0.5,
                                borderRadius: '16px',
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                color: theme.palette.primary.main,
                            }}
                        >
                            <Box component="span" sx={{ mr: 1 }}>
                                {`${columnId}: ${value}`}
                            </Box>
                            {onRemoveFilter && (
                                <Box
                                    component="span"
                                    onClick={() => onRemoveFilter(columnId)}
                                    sx={{
                                        cursor: 'pointer',
                                        fontSize: '1.2rem',
                                        lineHeight: 1,
                                        '&:hover': { opacity: 0.7 }
                                    }}
                                >
                                    ×
                                </Box>
                            )}
                        </Box>
                    ))}
                    {activeSorting.map(({ columnId, desc }) => (
                        <Box
                            key={`sort-${columnId}`}
                            sx={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                px: 2,
                                py: 0.5,
                                borderRadius: '16px',
                                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                color: theme.palette.secondary.main,
                            }}
                        >
                            <Box component="span" sx={{ mr: 1 }}>
                                {`Sorted by: ${columnId} (${desc ? 'desc' : 'asc'})`}
                            </Box>
                            {onRemoveSort && (
                                <Box
                                    component="span"
                                    onClick={() => onRemoveSort(columnId)}
                                    sx={{
                                        cursor: 'pointer',
                                        fontSize: '1.2rem',
                                        lineHeight: 1,
                                        '&:hover': { opacity: 0.7 }
                                    }}
                                >
                                    ×
                                </Box>
                            )}
                        </Box>
                    ))}
                </Box>
            )}
            <Paper
                elevation={0}
                sx={{
                    borderRadius: '12px',
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    overflow: 'hidden',
                    backgroundColor: theme.palette.background.paper,
                    display: 'flex',
                    flexDirection: 'column',
                    width: '100%',
                    flex: 1,
                }}
            >
                <TableContainer
                    ref={containerRef}
                    sx={{
                        maxHeight,
                        overflowX: 'auto',
                        width: '100%',
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        minWidth: 0, // Important for proper flex behavior
                    }}
                >
                    <Table
                        stickyHeader
                        sx={{
                            width: '100%',
                            minWidth: '100%',
                            tableLayout: 'fixed',
                            borderCollapse: 'separate',
                            borderSpacing: 0,
                            '& .MuiTableCell-root': {
                                py: 1,
                                px: 1.5,
                                height: 'auto',
                                verticalAlign: 'top',
                                whiteSpace: 'normal',
                                overflow: 'visible',
                                '& > *': {
                                    wordBreak: 'break-word',
                                    whiteSpace: 'normal',
                                    overflow: 'visible',
                                },
                            },
                        }}
                    >
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <TableHeader
                                            key={header.id}
                                            header={header}
                                            onFilterClick={onFilterClick}
                                        />
                                    ))}
                                </TableRow>
                            ))}
                        </TableHead>
                        <TableBody>
                            {virtualizer.getVirtualItems().map(virtualRow => {
                                const row = rows[virtualRow.index];
                                return (
                                    <TableRow
                                        key={row.id}
                                        sx={{
                                            '&:hover': {
                                                backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                            },
                                            transition: 'background-color 0.2s ease',
                                        }}
                                    >
                                        {row.getVisibleCells().map(cell => {
                                            const content = flexRender(
                                                cell.column.columnDef.cell,
                                                cell.getContext()
                                            );

                                            return (
                                                <TableCell
                                                    key={cell.id}
                                                    sx={{
                                                        borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                                        width: `${cell.column.getSize()}px`,
                                                        maxWidth: `${cell.column.getSize()}px`,
                                                        position: 'relative',
                                                        overflow: 'visible',
                                                        '&::after': {
                                                            content: '""',
                                                            position: 'absolute',
                                                            right: 0,
                                                            top: 0,
                                                            width: 1,
                                                            height: '100%',
                                                            backgroundColor: alpha(theme.palette.divider, 0.1),
                                                        },
                                                    }}
                                                >
                                                    {React.isValidElement(content) ? (
                                                        content
                                                    ) : (
                                                        <TableCellContent>
                                                            {content}
                                                        </TableCellContent>
                                                    )}
                                                </TableCell>
                                            );
                                        })}
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Box>
    );
}
