import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
    Box,
    IconButton,
    Chip,
    Paper,
    alpha,
    useTheme,
    CircularProgress,
    Button,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    FilterList as FilterListIcon,
} from '@mui/icons-material';
import { flexRender, type Table as TanStackTable } from '@tanstack/react-table';
import type { Pipeline } from '@/api/types/pipeline.types';
import { useTranslation } from 'react-i18next';

interface PipelineTableProps {
    table: TanStackTable<Pipeline>;
    isLoading: boolean;
    data: any;
    showDeleteButton: boolean;
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    onEdit: (id: string) => void;
    onDelete: (id: string, name: string) => void;
    onFetchNextPage: () => void;
    onFilterColumn: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
}

const getChipColor = (type: string, theme: any) => {
    switch (type.toLowerCase()) {
        case 'ingest triggered':
            return theme.palette.primary.main;
        case 'manual triggered':
            return theme.palette.secondary.main;
        case 'analysis triggered':
            return theme.palette.success.main;
        default:
            return theme.palette.grey[500];
    }
};

export const PipelineTable: React.FC<PipelineTableProps> = ({
    table,
    isLoading,
    data,
    showDeleteButton,
    hasNextPage,
    isFetchingNextPage,
    onEdit,
    onDelete,
    onFetchNextPage,
    onFilterColumn,
}) => {
    const theme = useTheme();
    const { t } = useTranslation();

    return (
        <Paper elevation={0} sx={{
            display: 'block',
            width: 'max-content',
            minWidth: 'max-content',
            maxWidth: 'none',
            borderRadius: '12px',
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            overflow: 'hidden',
            backgroundColor: theme.palette.background.paper,
        }}>
            <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)', overflowX: 'auto', width: 'fit-content' }}>
                <Table stickyHeader sx={{ width: 'fit-content', minWidth: 'fit-content' }}>
                    <TableHead>
                        {table.getHeaderGroups().map(headerGroup => (
                            <TableRow key={headerGroup.id}>
                                {headerGroup.headers.map(header => (
                                    <TableCell
                                        key={header.id}
                                        sx={{
                                            backgroundColor: theme.palette.background.paper,
                                            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                            py: 2,
                                            whiteSpace: 'nowrap',
                                            width: 'auto',
                                            minWidth: 'fit-content',
                                        }}
                                    >
                                        <Box sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            cursor: 'pointer',
                                            userSelect: 'none',
                                        }}>
                                            <Box
                                                onClick={header.column.getToggleSortingHandler()}
                                                sx={{ flex: 1 }}
                                            >
                                                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                                    {flexRender(
                                                        header.column.columnDef.header,
                                                        header.getContext()
                                                    )}
                                                    {{
                                                        asc: ' ↑',
                                                        desc: ' ↓',
                                                    }[header.column.getIsSorted() as string] ?? null}
                                                </Typography>
                                            </Box>
                                            {header.column.getCanFilter() && (
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => onFilterColumn(e, header.column.id)}
                                                    sx={{
                                                        ml: 1,
                                                        color: header.column.getFilterValue()
                                                            ? theme.palette.primary.main
                                                            : theme.palette.text.secondary,
                                                    }}
                                                >
                                                    <FilterListIcon fontSize="small" />
                                                </IconButton>
                                            )}
                                        </Box>
                                    </TableCell>
                                ))}
                            </TableRow>
                        ))}
                    </TableHead>
                    <TableBody>
                        {isLoading || !data ? (
                            <TableRow>
                                <TableCell colSpan={5} align="center">
                                    <CircularProgress />
                                </TableCell>
                            </TableRow>
                        ) : table.getRowModel().rows.map(row => (
                            <TableRow
                                key={row.id}
                                sx={{
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                    },
                                    transition: 'background-color 0.2s ease',
                                }}
                            >
                                {row.getVisibleCells().map(cell => (
                                    <TableCell
                                        key={cell.id}
                                        sx={{
                                            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                            py: 2,
                                            whiteSpace: 'nowrap',
                                            width: 'auto',
                                            minWidth: 'fit-content'
                                        }}
                                    >
                                        {cell.column.id === 'type' ? (
                                            <Chip
                                                label={cell.getValue() as string}
                                                size="small"
                                                sx={{
                                                    backgroundColor: alpha(getChipColor(cell.getValue() as string, theme), 0.1),
                                                    color: getChipColor(cell.getValue() as string, theme),
                                                    fontWeight: 600,
                                                    borderRadius: '6px',
                                                    height: '24px',
                                                    '& .MuiChip-label': {
                                                        px: 1.5,
                                                    },
                                                }}
                                            />
                                        ) : cell.column.id === 'actions' ? (
                                            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, width: 'auto', minWidth: 'fit-content' }}>
                                                {!row.original.system && (
                                                    <IconButton
                                                        size="small"
                                                        color="primary"
                                                        onClick={() => onEdit(row.original.id)}
                                                        sx={{
                                                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                                            '&:hover': {
                                                                backgroundColor: alpha(theme.palette.primary.main, 0.2),
                                                            },
                                                        }}
                                                    >
                                                        <EditIcon fontSize="small" />
                                                    </IconButton>
                                                )}
                                                {showDeleteButton && (
                                                    <IconButton
                                                        size="small"
                                                        color="error"
                                                        onClick={() => onDelete(row.original.id, row.original.name)}
                                                        sx={{
                                                            backgroundColor: alpha(theme.palette.error.main, 0.1),
                                                            '&:hover': {
                                                                backgroundColor: alpha(theme.palette.error.main, 0.2),
                                                            },
                                                        }}
                                                    >
                                                        <DeleteIcon fontSize="small" />
                                                    </IconButton>
                                                )}
                                            </Box>
                                        ) : (
                                            flexRender(cell.column.columnDef.cell, cell.getContext())
                                        )}
                                    </TableCell>
                                ))}
                            </TableRow>
                        ))}
                        {!isLoading && data && table.getRowModel().rows.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={5} align="center">
                                    {t('pipelines.noPipelinesFound')}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            <Box sx={{
                p: 2,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            }}>
                {hasNextPage && (
                    <Button
                        onClick={onFetchNextPage}
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
                )}
            </Box>
        </Paper>
    );
};
