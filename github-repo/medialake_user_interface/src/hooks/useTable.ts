import { useState, useEffect, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  ColumnResizeMode,
  ColumnSizingState,
  FilterFn,
} from "@tanstack/react-table";

interface UseTableProps<T> {
  data: T[];
  columns: ColumnDef<T, any>[];
  activeFilters?: { columnId: string; value: string }[];
  activeSorting?: { columnId: string; desc: boolean }[];
  onFilterChange?: (columnId: string, value: string) => void;
  onSortChange?: (columnId: string, desc: boolean) => void;
  filterFns?: Record<string, FilterFn<any>>;
  initialColumnVisibility?: Record<string, boolean>;
}

interface UseTableReturn<T> {
  table: ReturnType<typeof useReactTable<T>>;
  sorting: SortingState;
  columnFilters: ColumnFiltersState;
  globalFilter: string;
  columnVisibility: Record<string, boolean>;
  columnSizing: ColumnSizingState;
  columnMenuAnchor: HTMLElement | null;
  filterMenuAnchor: HTMLElement | null;
  activeFilterColumn: string | null;
  handleSortingChange: (newSorting: SortingState) => void;
  handleFilterChange: (newFilters: ColumnFiltersState) => void;
  setGlobalFilter: (value: string) => void;
  handleColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
  handleColumnMenuClose: () => void;
  handleFilterMenuOpen: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
  handleFilterMenuClose: () => void;
}

export function useTable<T>({
  data,
  columns,
  activeFilters = [],
  activeSorting = [],
  onFilterChange,
  onSortChange,
  filterFns,
  initialColumnVisibility = {},
}: UseTableProps<T>): UseTableReturn<T> {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnVisibility, setColumnVisibility] = useState(
    initialColumnVisibility,
  );
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<HTMLElement | null>(
    null,
  );
  const [filterMenuAnchor, setFilterMenuAnchor] = useState<HTMLElement | null>(
    null,
  );
  const [activeFilterColumn, setActiveFilterColumn] = useState<string | null>(
    null,
  );

  // Sync external state with internal state
  useEffect(() => {
    if (activeSorting) {
      setSorting(
        activeSorting.map((sort) => ({
          id: sort.columnId,
          desc: sort.desc,
        })),
      );
    }
  }, [activeSorting]);

  useEffect(() => {
    if (activeFilters) {
      setColumnFilters(
        activeFilters.map((filter) => ({
          id: filter.columnId,
          value: filter.value,
        })),
      );
    }
  }, [activeFilters]);

  // Handle internal state changes
  const handleSortingChange = (newSorting: SortingState) => {
    setSorting(newSorting);
    if (onSortChange) {
      if (newSorting.length > 0) {
        const sort = newSorting[0];
        onSortChange(sort.id, sort.desc ?? false);
      } else {
        onSortChange("", false);
      }
    }
  };

  const handleFilterChange = (newFilters: ColumnFiltersState) => {
    setColumnFilters(newFilters);
    if (onFilterChange && newFilters.length > 0) {
      const filter = newFilters[0];
      onFilterChange(filter.id, filter.value as string);
    }
  };

  const handleColumnMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setColumnMenuAnchor(event.currentTarget);
  };

  const handleColumnMenuClose = () => {
    setColumnMenuAnchor(null);
  };

  const handleFilterMenuOpen = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    setFilterMenuAnchor(event.currentTarget);
    setActiveFilterColumn(columnId);
  };

  const handleFilterMenuClose = () => {
    setFilterMenuAnchor(null);
    setActiveFilterColumn(null);
  };

  const table = useReactTable({
    data,
    columns,
    filterFns: {
      ...filterFns,
    },
    state: {
      sorting,
      columnFilters,
      globalFilter,
      columnVisibility,
      columnSizing,
    },
    onSortingChange: handleSortingChange,
    onColumnFiltersChange: handleFilterChange,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange" as ColumnResizeMode,
  });

  return {
    table,
    sorting,
    columnFilters,
    globalFilter,
    columnVisibility,
    columnSizing,
    columnMenuAnchor,
    filterMenuAnchor,
    activeFilterColumn,
    handleSortingChange,
    handleFilterChange,
    setGlobalFilter,
    handleColumnMenuOpen,
    handleColumnMenuClose,
    handleFilterMenuOpen,
    handleFilterMenuClose,
  };
}
