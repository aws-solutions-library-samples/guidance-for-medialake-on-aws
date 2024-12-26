import React from 'react';
import {
    TableCell,
    Box,
    IconButton,
    useTheme,
    alpha,
    Stack,
} from '@mui/material';
import {
    FilterList as FilterListIcon,
    ArrowUpward as ArrowUpwardIcon,
    ArrowDownward as ArrowDownwardIcon,
    UnfoldMore as UnfoldMoreIcon
} from '@mui/icons-material';
import { Header, flexRender } from '@tanstack/react-table';
import { ColumnResizer } from './ColumnResizer';
import { TableCellContent } from './TableCellContent';

interface TableHeaderProps {
    header: Header<any, unknown>;
    onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
}

export const TableHeader: React.FC<TableHeaderProps> = ({
    header,
    onFilterClick,
}) => {
    const theme = useTheme();

    return (
        <TableCell
            sx={{
                backgroundColor: theme.palette.background.paper,
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                p: 1.5,
                height: 'auto',
                width: header.getSize(),
                minWidth: header.getSize(),
                position: 'relative',
                verticalAlign: 'top',
                userSelect: 'none',
                '&:hover .column-resizer': {
                    opacity: 1,
                },
            }}
        >
            <Box sx={{
                display: 'flex',
                alignItems: 'flex-start',
                minHeight: '32px',
                position: 'relative',
                pr: header.column.getCanFilter() ? 4 : 0, // Space for filter icon
            }}>
                <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    sx={{
                        flex: 1,
                        cursor: 'pointer',
                    }}
                >
                    <TableCellContent variant="primary" wordBreak="normal">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                    </TableCellContent>
                    <Stack direction="row" alignItems="center" spacing={0.5}>
                        <Box
                            onClick={header.column.getToggleSortingHandler()}
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                color: header.column.getIsSorted()
                                    ? theme.palette.primary.main
                                    : theme.palette.text.secondary,
                                '&:hover': {
                                    color: theme.palette.primary.main,
                                }
                            }}
                        >
                            {header.column.getIsSorted() ? (
                                header.column.getIsSorted() === 'asc' ? (
                                    <ArrowUpwardIcon sx={{ fontSize: 18 }} />
                                ) : (
                                    <ArrowDownwardIcon sx={{ fontSize: 18 }} />
                                )
                            ) : (
                                <UnfoldMoreIcon sx={{ fontSize: 18 }} />
                            )}
                        </Box>
                        {header.column.getCanFilter() && onFilterClick && (
                            <Box
                                onClick={(e) => onFilterClick(e, header.column.id)}
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    color: header.column.getFilterValue()
                                        ? theme.palette.primary.main
                                        : theme.palette.text.secondary,
                                    '&:hover': {
                                        color: theme.palette.primary.main,
                                    }
                                }}
                            >
                                <FilterListIcon sx={{ fontSize: 18 }} />
                            </Box>
                        )}
                    </Stack>
                </Stack>
            </Box>
            <ColumnResizer
                header={header}
                className="column-resizer"
                sx={{
                    opacity: 0,
                    transition: 'opacity 0.2s ease',
                }}
            />
        </TableCell>
    );
};
