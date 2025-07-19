import React, { useCallback, useMemo } from "react";
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
} from "@mui/material";
import { Table as TanStackTable, flexRender, Row } from "@tanstack/react-table";
import { Virtualizer } from "@tanstack/react-virtual";
import { TableHeader } from "./TableHeader";
import { TableCellContent } from "./TableCellContent";
import { useTableDensity } from "../../../contexts/TableDensityContext";
import { Table as MUITable } from "@mui/material";

interface ResizableTableProps<T> {
  table: TanStackTable<T>;
  containerRef: React.RefObject<HTMLDivElement>;
  virtualizer: Virtualizer<HTMLDivElement, Element>;
  rows: Row<T>[];
  maxHeight?: string;
  onRowClick?: (row: Row<T>) => void;
  onFilterClick?: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
  activeFilters?: Array<{ columnId: string; value: string }>;
  activeSorting?: Array<{ columnId: string; desc: boolean }>;
  onRemoveFilter?: (columnId: string) => void;
  onRemoveSort?: (columnId: string) => void;
  // For pipeline toggle functionality
  togglingPipelines?: Record<string, boolean>;
  onToggleActive?: (id: string, active: boolean) => void;
}

type TableProps = React.ComponentProps<typeof MUITable>;

const useTableStyles = (
  theme: any,
  mode: "compact" | "normal",
  hasRowClick: boolean,
  rowCount: number,
) => {
  const isDark = theme.palette.mode === "dark";

  return useMemo(
    () => ({
      filterTag: {
        display: "inline-flex",
        alignItems: "center",
        px: 2,
        py: 0.5,
        borderRadius: "16px",
        backgroundColor: alpha(theme.palette.primary.main, 0.1),
        color: theme.palette.primary.main,
      },
      closeButton: {
        cursor: "pointer",
        fontSize: "1.2rem",
        lineHeight: 1,
        "&:hover": { opacity: 0.7 },
      },
      tableContainer: {
        overflow: "auto",
        width: "100%",
        flex: "none",
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        minHeight: rowCount > 0 ? 0 : "auto",
        maxHeight: rowCount > 0 ? "100%" : "auto",
        position: "relative",
        willChange: "transform",
        "&::-webkit-scrollbar": {
          width: 8,
          height: 8,
        },
        "&::-webkit-scrollbar-track": {
          background: theme.palette.background.default,
        },
        "&::-webkit-scrollbar-thumb": {
          background: theme.palette.divider,
          borderRadius: 4,
          "&:hover": {
            background: alpha(theme.palette.primary.main, 0.2),
          },
        },
      },
      table: {
        width: "100%",
        minWidth: "100%",
        tableLayout: "fixed",
        backgroundColor: "inherit",
        borderSpacing: 0,
        "& .MuiTableCell-root": {
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          py: mode === "compact" ? 0.5 : 1.5, // Add padding for the table cells/rows
          px: mode === "compact" ? 1.5 : 2,
          height: mode === "compact" ? "40px" : "48px",
          lineHeight: mode === "compact" ? "38px" : "46px",
          verticalAlign: "middle",
          whiteSpace: "normal",
          overflow: "visible",
          color: theme.palette.text.secondary,
          fontSize: mode === "compact" ? "0.875rem" : "1rem",
          backgroundColor: "transparent",
          "& > *": {
            wordBreak: "break-word",
            whiteSpace: "normal",
            overflow: "visible",
            lineHeight: "inherit",
            cursor: "text",
          },
          "& .MuiIconButton-root, & .MuiChip-root": {
            cursor: "pointer",
          },
        },
        "& .MuiTableHead-root .MuiTableCell-root": {
          backgroundColor: isDark
            ? alpha(theme.palette.background.default, 0.95)
            : alpha(theme.palette.background.paper, 0.95),
          borderBottom: `2px solid ${alpha(theme.palette.divider, 0.1)}`,
          fontWeight: 600,
          color: theme.palette.text.primary,
          height: mode === "compact" ? "32px" : "40px",
          position: "sticky",
          top: 0,
          zIndex: 2,
        },
      },
      tableRow: {
        backgroundColor: "inherit",
        transition: "all 0.2s ease",
        cursor: hasRowClick ? "pointer" : "default",
        "&:hover": hasRowClick
          ? {
              bgcolor: "action.hover",
            }
          : {},
        "& .MuiTableCell-root": {
          position: "relative",
          userSelect: "text",
          "& .MuiIconButton-root": {
            position: "relative",
            zIndex: 2,
            pointerEvents: "auto",
          },
        },
      },
      paper: {
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        width: "100%",
        flex: 1,
        backgroundColor: isDark
          ? alpha(theme.palette.background.paper, 0.2)
          : theme.palette.background.paper,
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        borderRadius: "12px",
      },
    }),
    [
      theme.palette.mode,
      theme.palette.primary.main,
      mode,
      isDark,
      hasRowClick,
      rowCount,
    ],
  );
};

export function ResizableTable<T>({
  table,
  containerRef,
  virtualizer,
  rows,
  maxHeight = "100%",
  onRowClick,
  onFilterClick,
  activeFilters = [],
  activeSorting = [],
  onRemoveFilter,
  onRemoveSort,
  togglingPipelines = {},
  onToggleActive,
}: ResizableTableProps<T>) {
  const theme = useTheme();
  const { mode } = useTableDensity();
  const styles = useTableStyles(theme, mode, Boolean(onRowClick), rows.length);

  const handleRowClick = useCallback(
    (row: Row<T>, event: React.MouseEvent<HTMLElement>) => {
      // Prevent row click when clicking on action buttons or checkboxes
      if (
        !(event.target as HTMLElement).closest(".action-buttons") &&
        !(event.target as HTMLElement).closest(".MuiCheckbox-root") &&
        !(event.target as HTMLElement).closest('input[type="checkbox"]') &&
        !(event.target as HTMLElement).closest(".checkbox-cell")
      ) {
        onRowClick?.(row);
      }
    },
    [onRowClick],
  );

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
      role="grid"
      aria-label="Data table"
    >
      <Paper
        elevation={0}
        sx={{
          ...styles.paper,
          height: "auto",
          minHeight:
            rows.length > 0
              ? `${rows.length * (mode === "compact" ? 40 : 48) + (mode === "compact" ? 32 : 40)}px`
              : 0,
          flex: "none",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <TableContainer
          ref={containerRef}
          sx={{
            ...styles.tableContainer,
            height: "auto",
            maxHeight: rows.length <= 3 ? undefined : "100%",
            minHeight:
              rows.length > 0
                ? `${
                    rows.length * (mode === "compact" ? 40 : 48) +
                    (mode === "compact" ? 32 : 40)
                  }px`
                : "auto",
            overflow: rows.length <= 3 ? "visible" : "auto",
            display: "flex",
            flexDirection: "column",
            flex: "none",
          }}
          component={Box}
        >
          <Table stickyHeader sx={styles.table} role="grid">
            <TableHead>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} role="row">
                  {headerGroup.headers.map((header) => (
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
              {rows.map((row) => (
                <TableRow
                  hover
                  key={row.id}
                  onClick={(e) => handleRowClick(row, e)}
                  sx={{
                    cursor: "pointer",
                    "&:hover": {
                      backgroundColor: (theme) =>
                        theme.palette.mode === "light"
                          ? alpha(theme.palette.primary.main, 0.04)
                          : alpha(theme.palette.primary.main, 0.08),
                    },
                  }}
                >
                  {row.getVisibleCells().map((cell) => {
                    const content = flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext(),
                    );

                    return (
                      <TableCell
                        key={cell.id}
                        sx={{
                          width: `${cell.column.getSize()}px`,
                          maxWidth: `${cell.column.getSize()}px`,
                          position: "relative",
                          overflow: "visible",
                        }}
                        role="gridcell"
                      >
                        {React.isValidElement(content) ? (
                          content
                        ) : (
                          <TableCellContent>{content}</TableCellContent>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
}
