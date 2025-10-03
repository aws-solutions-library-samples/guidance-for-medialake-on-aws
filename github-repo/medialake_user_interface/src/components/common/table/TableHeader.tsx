import React, { useCallback, useMemo } from "react";
import { TableCell, Box, useTheme, alpha, Stack } from "@mui/material";
import {
  FilterList as FilterListIcon,
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  UnfoldMore as UnfoldMoreIcon,
} from "@mui/icons-material";
import { Header } from "@tanstack/react-table";
import { Theme } from "@mui/material/styles";
import { ColumnResizer } from "./ColumnResizer";
import { TableCellContent } from "./TableCellContent";

interface TableHeaderProps<T> {
  header: Header<T, unknown>;
  onFilterClick?: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
}

const useHeaderStyles = (theme: Theme) => {
  const isDark = theme.palette.mode === "dark";

  return useMemo(
    () => ({
      headerCell: {
        border: "none",
        p: 2,
        height: "auto",
        position: "relative",
        verticalAlign: "top",
        userSelect: "none",
        backgroundColor: isDark
          ? alpha(theme.palette.background.default, 0.95)
          : alpha(theme.palette.background.paper, 0.95),
        "&:hover .column-resizer": {
          opacity: 1,
        },
        "&:hover": {
          backgroundColor: isDark
            ? alpha(theme.palette.background.paper, 0.4)
            : alpha(theme.palette.primary.main, 0.02),
        },
      },
      headerContent: {
        display: "flex",
        alignItems: "flex-start",
        minHeight: "32px",
        position: "relative",
      },
      sortIcon: {
        display: "flex",
        alignItems: "center",
        fontSize: 18,
        transition: "transform 0.2s ease",
      },
      iconWrapper: (isActive: boolean) => ({
        display: "flex",
        alignItems: "center",
        color: isActive
          ? theme.palette.primary.main
          : isDark
            ? alpha(theme.palette.text.primary, 0.7)
            : alpha(theme.palette.text.secondary, 0.7),
        opacity: isActive ? 1 : 0.8,
        transition: "all 0.2s ease",
        "&:hover": {
          color: theme.palette.primary.main,
          opacity: 1,
          transform: "scale(1.1)",
        },
      }),
      columnResizer: {
        opacity: 0,
        transition: "all 0.2s ease",
        backgroundColor: alpha(theme.palette.text.secondary, 0.3),
        "&:hover": {
          backgroundColor: theme.palette.primary.main,
        },
      },
    }),
    [theme.palette.mode, theme.palette.primary.main],
  );
};

export function TableHeader<T>({ header, onFilterClick }: TableHeaderProps<T>) {
  const theme = useTheme();
  const styles = useHeaderStyles(theme);

  const handleSortClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const handler = header.column.getToggleSortingHandler();
      if (handler) {
        handler(e);
      }
    },
    [header.column],
  );

  const handleFilterClick = useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      e.stopPropagation();
      e.preventDefault();
      if (onFilterClick) {
        onFilterClick(e, header.column.id);
      }
    },
    [header.column.id, onFilterClick],
  );

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent, action: () => void) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        action();
      }
    },
    [],
  );

  const sortDirection = header.column.getIsSorted();
  const canSort = header.column.getCanSort();

  const sortIcon = useMemo(() => {
    if (!sortDirection) return <UnfoldMoreIcon sx={styles.sortIcon} />;
    return sortDirection === "asc" ? (
      <ArrowUpwardIcon sx={styles.sortIcon} />
    ) : (
      <ArrowDownwardIcon sx={styles.sortIcon} />
    );
  }, [sortDirection, styles.sortIcon]);

  return (
    <TableCell
      sx={{
        ...styles.headerCell,
        width: header.getSize(),
        minWidth: header.getSize(),
      }}
      role="columnheader"
      aria-sort={
        sortDirection
          ? sortDirection === "asc"
            ? "ascending"
            : "descending"
          : "none"
      }
    >
      <Box
        sx={{
          ...styles.headerContent,
          pr: header.column.getCanFilter() ? 4 : 0,
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{ flex: 1, cursor: canSort ? "pointer" : "default" }}
          onClick={canSort ? handleSortClick : undefined}
        >
          {typeof header.column.columnDef.header === "function" ? (
            // If header is a function, call it with the header context
            header.column.columnDef.header(header.getContext())
          ) : (
            // Otherwise render it as a string
            <TableCellContent
              variant="primary"
              wordBreak="normal"
              aria-label={`${header.column.columnDef.header as string} column`}
            >
              {header.column.columnDef.header as string}
            </TableCellContent>
          )}
          <Stack direction="row" alignItems="center" spacing={0.5}>
            {canSort && (
              <Box
                onClick={handleSortClick}
                onKeyPress={(e) =>
                  handleKeyPress(e, () => handleSortClick(e as any))
                }
                sx={styles.iconWrapper(Boolean(sortDirection))}
                role="button"
                tabIndex={0}
                aria-label={`Sort by ${header.column.columnDef.header as string}`}
              >
                {sortIcon}
              </Box>
            )}
            {header.column.getCanFilter() && onFilterClick && (
              <Box
                onClick={handleFilterClick}
                onKeyPress={(e) =>
                  handleKeyPress(e, () => handleFilterClick(e as any))
                }
                sx={styles.iconWrapper(Boolean(header.column.getFilterValue()))}
                role="button"
                tabIndex={0}
                aria-label={`Filter ${header.column.columnDef.header as string}`}
              >
                <FilterListIcon sx={styles.sortIcon} />
              </Box>
            )}
          </Stack>
        </Stack>
      </Box>
      <ColumnResizer
        header={header}
        className="column-resizer"
        sx={styles.columnResizer}
      />
    </TableCell>
  );
}
