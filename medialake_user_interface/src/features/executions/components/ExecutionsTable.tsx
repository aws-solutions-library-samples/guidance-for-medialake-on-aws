import React, { useRef } from 'react';
import {
    Box,
    IconButton,
    Chip,
    alpha,
    useTheme,
    CircularProgress,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Visibility as VisibilityIcon,
    PlayArrow as PlayArrowIcon,
    RestartAlt as RestartIcon,
} from '@mui/icons-material';
import { type Table as TanStackTable } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { PipelineExecution } from '../../../api/types/pipelineExecutions.types';
import { useTranslation } from 'react-i18next';
import { ResizableTable, TableCellContent } from '../../../components/common/table';

interface ExecutionsTableProps {
    table: TanStackTable<PipelineExecution>;
    isLoading: boolean;
    data: PipelineExecution[];
    onViewDetails: (executionId: string) => void;
    onRetryFromCurrent: (executionId: string) => void;
    onRetryFromStart: (executionId: string) => void;
    onFilterColumn: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
    activeFilters?: { columnId: string; value: string }[];
    activeSorting?: { columnId: string; desc: boolean }[];
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
}

export const ExecutionsTable: React.FC<ExecutionsTableProps> = ({
    table,
    isLoading,
    data,
    onViewDetails,
    onRetryFromCurrent,
    onRetryFromStart,
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
        overscan: 20,
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
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            overflow: 'hidden',
            position: 'relative',
            minHeight: 0,
            '& > *': {
                minHeight: 0,
                flex: 1,
            }
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
