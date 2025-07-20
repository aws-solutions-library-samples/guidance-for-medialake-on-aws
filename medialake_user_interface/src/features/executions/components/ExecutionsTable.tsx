import React, { useRef } from "react";
import { Box, CircularProgress } from "@mui/material";
import { type Table as TanStackTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { PipelineExecution } from "../types/pipelineExecutions.types";
import { ResizableTable } from "@/components/common/table";

interface ExecutionsTableProps {
  table: TanStackTable<PipelineExecution>;
  isLoading: boolean;
  data: PipelineExecution[];
  onViewDetails: (execution: PipelineExecution) => void;
  onRetryFromCurrent: (executionId: string) => void;
  onRetryFromStart: (executionId: string) => void;
  onFilterColumn: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
  activeFilters?: { columnId: string; value: string }[];
  activeSorting?: { columnId: string; desc: boolean }[];
  onRemoveFilter?: (columnId: string) => void;
  onRemoveSort?: (columnId: string) => void;
}

export const ExecutionsTable: React.FC<ExecutionsTableProps> = ({
  table,
  isLoading,
  data,
  onFilterColumn,
  activeFilters = [],
  activeSorting = [],
  onRemoveFilter,
  onRemoveSort,
}) => {
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
      <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

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
        virtualizer={rowVirtualizer}
        rows={rows}
        onFilterClick={onFilterColumn}
        // Comment out these props to remove the tags
        activeFilters={activeFilters}
        activeSorting={activeSorting}
        onRemoveFilter={onRemoveFilter}
        onRemoveSort={onRemoveSort}
        maxHeight="none"
      />
    </Box>
  );
};
