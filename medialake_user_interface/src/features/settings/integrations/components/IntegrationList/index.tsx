import React, { useRef } from "react";
import { Box } from "@mui/material";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
} from "@tanstack/react-table";
import { ResizableTable } from "@/components/common/table";
import { BaseTableToolbar } from "@/components/common/table";
import { useTableVirtualizer } from "@/features/settings/integrations/hooks/useTableVirtualizer";
import { useColumns } from "@/features/settings/integrations/hooks/useColumns";
import { IntegrationListProps, ColumnSort, ColumnFilter } from "./types";

const IntegrationList: React.FC<IntegrationListProps> = ({
  integrations,
  onEditIntegration,
  onDeleteIntegration,
  activeFilters,
  activeSorting,
  onFilterChange,
  onSortChange,
  onRemoveFilter,
  onRemoveSort,
  isLoading,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const columns = useColumns({ onEditIntegration, onDeleteIntegration });

  const table = useReactTable({
    data: integrations,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      sorting: activeSorting,
      columnFilters: activeFilters,
    },
    onSortingChange: (updater) => {
      const newSorting =
        typeof updater === "function" ? updater(activeSorting) : updater;
      if (newSorting.length === 0 && activeSorting.length > 0) {
        onRemoveSort(activeSorting[0].id);
      } else if (newSorting.length > 0) {
        onSortChange(newSorting[0].id, newSorting[0].desc);
      }
    },
    onColumnFiltersChange: (updater) => {
      const newFilters =
        typeof updater === "function" ? updater(activeFilters) : updater;
      if (newFilters.length > 0) {
        const lastFilter = newFilters[newFilters.length - 1];
        onFilterChange(lastFilter.id, lastFilter.value as string);
      }
    },
  });

  const { rows } = table.getRowModel();
  const virtualizer = useTableVirtualizer(rows, containerRef);

  const mappedActiveFilters: ColumnFilter[] = activeFilters.map((filter) => ({
    columnId: filter.id,
    value: filter.value as string,
  }));

  const mappedActiveSorting: ColumnSort[] = activeSorting.map((sort) => ({
    columnId: sort.id,
    desc: sort.desc,
  }));

  const handleFilterClick = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    // Handle filter click if needed
  };

  const handleRemoveSort = (columnId: string) => {
    onRemoveSort(columnId);
    table.setSorting([]);
  };

  return (
    <Box ref={containerRef} sx={{ height: "100%", overflow: "auto" }}>
      <BaseTableToolbar
        globalFilter={table.getState().globalFilter}
        onGlobalFilterChange={(value) => table.setGlobalFilter(value)}
        activeFilters={mappedActiveFilters}
        activeSorting={mappedActiveSorting}
        onRemoveFilter={onRemoveFilter}
        onRemoveSort={handleRemoveSort}
        searchPlaceholder="Search integrations..."
        onColumnMenuOpen={() => {}}
      />
      {isLoading ? (
        <Box sx={{ p: 2, textAlign: "center" }}>Loading...</Box>
      ) : (
        <ResizableTable
          table={table}
          containerRef={containerRef}
          virtualizer={virtualizer}
          rows={rows}
          onFilterClick={handleFilterClick}
          activeFilters={mappedActiveFilters}
          activeSorting={mappedActiveSorting}
          onRemoveFilter={onRemoveFilter}
          onRemoveSort={handleRemoveSort}
        />
      )}
    </Box>
  );
};

export default React.memo(IntegrationList);
