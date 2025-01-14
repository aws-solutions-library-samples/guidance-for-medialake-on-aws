import React, { useRef } from 'react';
import {
    Box,
    IconButton,
    Chip,
    alpha,
    useTheme,
    CircularProgress,
    Tooltip,
    Theme,
} from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
} from '@mui/icons-material';
import { type Table as TanStackTable } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Pipeline } from '../../../api/types/pipeline.types';
import { useTranslation } from 'react-i18next';
import { ResizableTable, TableCellContent } from '../../../components/common/table';

interface PipelineTableProps {
    table: TanStackTable<Pipeline>;
    isLoading: boolean;
    data: Pipeline[];
    showDeleteButton: boolean;
    onEdit: (id: string) => void;
    onDelete: (id: string, name: string) => void;
    onFilterColumn: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: { columnId: string; value: string }[];
    activeSorting?: { columnId: string; desc: boolean }[];
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
}

const getChipColor = (type: string, theme: Theme): string => {
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
    onEdit,
    onDelete,
    onFilterColumn,
    activeFilters = [],
    activeSorting = [],
    onRemoveFilter,
    onRemoveSort,
}) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const containerRef = useRef<HTMLDivElement>(null);

    const { rows } = table.getRowModel();
    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 53,
        overscan: 10,
    });

    if (isLoading || !data) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            height: 'auto',
        }}>
            <ResizableTable
                table={table}
                containerRef={containerRef}
                virtualizer={rowVirtualizer}
                rows={rows}
                onFilterClick={onFilterColumn}
                activeFilters={activeFilters}
                activeSorting={activeSorting}
                onRemoveFilter={onRemoveFilter}
                onRemoveSort={onRemoveSort}
                maxHeight="none"
            />
        </Box>
    );
};
