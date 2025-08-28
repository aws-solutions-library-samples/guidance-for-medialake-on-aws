import React, { useRef } from "react";
import { Box } from "@mui/material";
import { ColumnDef, FilterFn } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useTable } from "@/hooks/useTable";
import { useTableDensity } from "@/contexts/TableDensityContext";
import { ResizableTable } from "./ResizableTable";
import { ColumnVisibilityMenu } from "./ColumnVisibilityMenu";
import { BaseTableToolbar } from "./BaseTableToolbar";
import { BaseFilterPopover } from "./BaseFilterPopover";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
} from "@mui/material";
import {
  type Table as TanStackTable,
  type ColumnSort,
  type ColumnFilter,
  type ColumnDefTemplate,
  type CellContext,
  type HeaderContext,
  flexRender,
} from "@tanstack/react-table";
import { Virtualizer } from "@tanstack/react-virtual";

export interface BaseTableProps<T> {
  table: TanStackTable<T>;
  virtualizer: Virtualizer<HTMLDivElement, Element>;
  isLoading?: boolean;
  activeFilters: ColumnFilter[];
  activeSorting: ColumnSort[];
  onRemoveFilter: (id: string) => void;
  onRemoveSort: (id: string) => void;
  searchPlaceholder?: string;
}

export const BaseTable = <T extends object>({
  table,
  virtualizer,
  isLoading,
  activeFilters,
  activeSorting,
  onRemoveFilter,
  onRemoveSort,
  searchPlaceholder,
}: BaseTableProps<T>) => {
  const { rows } = table.getRowModel();
  const paddingTop = virtualizer.getVirtualItems()[0]?.start || 0;
  const paddingBottom =
    virtualizer.getTotalSize() -
    (virtualizer.getVirtualItems()[virtualizer.getVirtualItems().length - 1]
      ?.end || 0);

  return (
    <TableContainer component={Paper}>
      {isLoading && (
        <Box sx={{ width: "100%" }}>
          <LinearProgress />
        </Box>
      )}
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableCell
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  sx={{
                    cursor: header.column.getCanSort() ? "pointer" : "default",
                  }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header as ColumnDefTemplate<
                          HeaderContext<T, unknown>
                        >,
                        header.getContext(),
                      )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableHead>
        <TableBody>
          {paddingTop > 0 && (
            <TableRow>
              <TableCell style={{ height: `${paddingTop}px` }} />
            </TableRow>
          )}
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = rows[virtualRow.index];
            return (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(
                      cell.column.columnDef.cell as ColumnDefTemplate<
                        CellContext<T, unknown>
                      >,
                      cell.getContext(),
                    )}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
          {paddingBottom > 0 && (
            <TableRow>
              <TableCell style={{ height: `${paddingBottom}px` }} />
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default BaseTable;
