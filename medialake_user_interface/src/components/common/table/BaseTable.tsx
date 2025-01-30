import React, { useRef } from 'react';
import { Box } from '@mui/material';
import { ColumnDef, FilterFn } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useTable } from '@/hooks/useTable';
import { ResizableTable } from './ResizableTable';
import { ColumnVisibilityMenu } from './ColumnVisibilityMenu';
import { BaseTableToolbar } from './BaseTableToolbar';
import { BaseFilterPopover } from './BaseFilterPopover';

export interface BaseTableProps<T> {
    data: T[];
    columns: ColumnDef<T, any>[];
    activeFilters?: { columnId: string; value: string }[];
    activeSorting?: { columnId: string; desc: boolean }[];
    onFilterChange?: (columnId: string, value: string) => void;
    onSortChange?: (columnId: string, desc: boolean) => void;
    onRemoveFilter?: (columnId: string) => void;
    onRemoveSort?: (columnId: string) => void;
    getUniqueValues: (columnId: string, data: T[]) => string[];
    formatValue?: (columnId: string, value: string) => string;
    filterFns?: Record<string, FilterFn<any>>;
    searchPlaceholder?: string;
    initialColumnVisibility?: Record<string, boolean>;
}

export function BaseTable<T>({
    data,
    columns,
    activeFilters = [],
    activeSorting = [],
    onFilterChange,
    onSortChange,
    onRemoveFilter,
    onRemoveSort,
    getUniqueValues,
    formatValue,
    filterFns,
    searchPlaceholder,
    initialColumnVisibility,
}: BaseTableProps<T>) {
    const containerRef = useRef<HTMLDivElement>(null);

    const {
        table,
        globalFilter,
        columnMenuAnchor,
        filterMenuAnchor,
        activeFilterColumn,
        setGlobalFilter,
        handleColumnMenuOpen,
        handleColumnMenuClose,
        handleFilterMenuOpen,
        handleFilterMenuClose,
    } = useTable({
        data,
        columns,
        activeFilters,
        activeSorting,
        onFilterChange,
        onSortChange,
        filterFns,
        initialColumnVisibility,
    });

    const { rows } = table.getRowModel();
    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => containerRef.current,
        estimateSize: () => 48,
        overscan: 10,
    });

    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
        }}>
            <BaseTableToolbar
                globalFilter={globalFilter}
                onGlobalFilterChange={setGlobalFilter}
                onColumnMenuOpen={handleColumnMenuOpen}
                activeFilters={activeFilters}
                activeSorting={activeSorting}
                onRemoveFilter={onRemoveFilter}
                onRemoveSort={onRemoveSort}
                searchPlaceholder={searchPlaceholder}
            />

            <Box sx={{
                flex: 1,
                minHeight: 0,
                width: '100%',
                overflow: 'hidden',
                position: 'relative',
                maxWidth: '100%',
            }}>
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
            </Box>

            <ColumnVisibilityMenu
                anchorEl={columnMenuAnchor}
                columns={table.getAllLeafColumns()}
                onClose={handleColumnMenuClose}
            />

            <BaseFilterPopover
                anchorEl={filterMenuAnchor}
                column={activeFilterColumn ? table.getColumn(activeFilterColumn) : null}
                onClose={handleFilterMenuClose}
                data={data}
                getUniqueValues={getUniqueValues}
                formatValue={formatValue}
            />
        </Box>
    );
}
