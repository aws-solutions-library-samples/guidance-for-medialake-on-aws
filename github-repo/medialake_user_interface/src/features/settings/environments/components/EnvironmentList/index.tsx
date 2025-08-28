import React, { useRef, memo } from "react";
import { Box } from "@mui/material";
import { type Table as TanStackTable } from "@tanstack/react-table";
import { Environment } from "@/types/environment";
import { ResizableTable } from "@/components/common/table";
import { useTableVirtualizer } from "../../hooks/useTableVirtualizer";
import { useTableFilters } from "../../context/TableFiltersContext";

interface EnvironmentListProps {
  table: TanStackTable<Environment>;
  onFilterColumn: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
}

const EnvironmentList: React.FC<EnvironmentListProps> = memo(
  ({ table, onFilterColumn }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const { rows } = table.getRowModel();
    const virtualizer = useTableVirtualizer(rows, containerRef);
    const { activeFilters, activeSorting, onRemoveFilter, onRemoveSort } =
      useTableFilters();

    return (
      <Box
        sx={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          flex: 1,
          overflow: "hidden",
          position: "relative",
          minHeight: 0,
          "& > *": {
            minHeight: 0,
            flex: 1,
          },
        }}
      >
        <ResizableTable
          table={table}
          containerRef={containerRef}
          virtualizer={virtualizer}
          rows={rows}
          onFilterClick={onFilterColumn}
          activeFilters={activeFilters}
          activeSorting={activeSorting}
          onRemoveFilter={onRemoveFilter}
          onRemoveSort={onRemoveSort}
        />
      </Box>
    );
  },
);

EnvironmentList.displayName = "EnvironmentList";

export default EnvironmentList;
