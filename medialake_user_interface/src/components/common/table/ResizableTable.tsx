import React, { useCallback, useMemo } from 'react';
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
import { useTableDensity } from '../../../contexts/TableDensityContext';

interface ResizableTableProps<T> {
    table: TanStackTable<T>;
    containerRef: React.RefObject<HTMLDivElement>;
    virtualizer: Virtualizer<HTMLDivElement, Element>;
    rows: Row<T>[];
    maxHeight?: string;
    onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: Array<{ columnId: string; value: string }>;
    activeSorting?: Array<{ columnId: string; desc: boolean }>;
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
}

const useTableStyles = (theme: any, mode: 'compact' | 'normal') => {
    const isDark = theme.palette.mode === 'dark';

    return useMemo(() => ({
        filterTag: {
            display: 'inline-flex',
            alignItems: 'center',
            px: 2,
            py: 0.5,
            borderRadius: '16px',
            backgroundColor: alpha(theme.palette.primary.main, 0.1),
            color: theme.palette.primary.main,
        },
        closeButton: {
            cursor: 'pointer',
            fontSize: '1.2rem',
            lineHeight: 1,
            '&:hover': { opacity: 0.7 }
        },
        tableContainer: {
            maxHeight: 'calc(100vh - 300px)',
            overflowX: 'hidden',
            '&:hover': {
                overflowX: 'auto'
            },
            width: '100%',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            '&::-webkit-scrollbar': {
                height: 10,
            },
            '&::-webkit-scrollbar-track': {
                background: theme.palette.background.default,
            },
            '&::-webkit-scrollbar-thumb': {
                background: theme.palette.divider,
                borderRadius: 2,
                '&:hover': {
                    background: alpha(theme.palette.primary.main, 0.2),
                },
            },
        },
        table: {
            width: '100%',
            minWidth: '100%',
            tableLayout: 'fixed',
            backgroundColor: 'inherit',
            '& .MuiTableCell-root': {
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                py: mode === 'compact' ? 0.75 : 1.5,
                px: mode === 'compact' ? 1.5 : 2,
                height: mode === 'compact' ? '40px' : '48px',
                verticalAlign: 'top',
                whiteSpace: 'normal',
                overflow: 'visible',
                color: theme.palette.text.secondary,
                fontSize: mode === 'compact' ? '0.875rem' : '1rem',
                '& > *': {
                    wordBreak: 'break-word',
                    whiteSpace: 'normal',
                    overflow: 'visible',
                },
            },
            '& .MuiTableHead-root .MuiTableCell-root': {
                backgroundColor: isDark
                    ? alpha(theme.palette.background.paper, 0.3)
                    : alpha(theme.palette.background.paper, 0.04),
                borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
                fontWeight: 600,
                color: theme.palette.text.primary,
                height: mode === 'compact' ? '32px' : '40px',
            },
        },
        tableRow: {
            '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.04),
            },
            backgroundColor: 'inherit',
            transition: 'all 0.2s ease',
            cursor: 'pointer',
            '& .MuiTableCell-root': {
                position: 'relative',
                '& .MuiIconButton-root': {
                    position: 'relative',
                    zIndex: 2,
                    pointerEvents: 'auto'
                }
            }
        },
        paper: {
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            width: '100%',
            flex: 1,
            backgroundColor: theme.palette.mode === 'dark'
                ? alpha(theme.palette.background.paper, 0.2)
                : theme.palette.background.paper,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            borderRadius: '12px',
        }
    }), [theme.palette.mode, theme.palette.primary.main, mode]);
};

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
    const { mode } = useTableDensity();
    const styles = useTableStyles(theme, mode);
    const hasActiveTags = activeFilters.length > 0 || activeSorting.length > 0;

    const handleRemoveFilter = useCallback((columnId: string) => {
        onRemoveFilter?.(columnId);
    }, [onRemoveFilter]);

    const handleRemoveSort = useCallback((columnId: string) => {
        onRemoveSort?.(columnId);
    }, [onRemoveSort]);

    return (
        <Box
            sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}
            role="grid"
            aria-label="Data table"
        >
            {hasActiveTags && (
                <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {activeFilters.map(({ columnId, value }) => (
                        <Box
                            key={`filter-${columnId}`}
                            sx={styles.filterTag}
                            role="button"
                            aria-label={`Remove filter for ${columnId}`}
                        >
                            <Box component="span" sx={{ mr: 1 }}>
                                {`${columnId}: ${value}`}
                            </Box>
                            {onRemoveFilter && (
                                <Box
                                    component="span"
                                    onClick={() => handleRemoveFilter(columnId)}
                                    sx={styles.closeButton}
                                    role="button"
                                    tabIndex={0}
                                    onKeyPress={(e) => {
                                        if (e.key === 'Enter' || e.key === ' ') {
                                            handleRemoveFilter(columnId);
                                        }
                                    }}
                                >
                                    ×
                                </Box>
                            )}
                        </Box>
                    ))}
                </Box>
            )}
            <Paper elevation={0} sx={styles.paper}>
                <TableContainer
                    ref={containerRef}
                    sx={{ ...styles.tableContainer, maxHeight }}
                >
                    <Table
                        stickyHeader
                        sx={styles.table}
                        role="grid"
                    >
                        <TableHead>
                            {table.getHeaderGroups().map(headerGroup => (
                                <TableRow key={headerGroup.id} role="row">
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
                                        sx={styles.tableRow}
                                        role="row"
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
                                                        width: `${cell.column.getSize()}px`,
                                                        maxWidth: `${cell.column.getSize()}px`,
                                                        position: 'relative',
                                                        overflow: 'visible',
                                                    }}
                                                    role="gridcell"
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
