import { useEffect, useRef, useState } from "react";
import type { PaginationState } from "@tanstack/react-table";
import { DEFAULT_PAGE_SIZE } from "@/constants/pagination";
import { stableKey } from "../pagination/paginationKey";

export interface UseTablePaginationOptions {
  /** Defaults to DEFAULT_PAGE_SIZE. */
  initialPageSize?: number;
  /**
   * Values that should return the user to the first page when they change,
   * typically the global filter and column filters.
   */
  resetOn?: unknown[];
}

export interface UseTablePaginationResult {
  pagination: PaginationState;
  setPagination: React.Dispatch<React.SetStateAction<PaginationState>>;
  /**
   * Spread into `useReactTable`. Pins `autoResetPageIndex` to false, which
   * matters for any list on a refetch interval: TanStack's default would reset
   * the page to 1 on every poll, dragging the user back to the top.
   * Filter-driven resets are handled here instead, via `resetOn`.
   */
  autoResetPageIndex: false;
}

/**
 * Pagination state for a TanStack table.
 *
 * Pair with `getPaginationRowModel()` on the table and `enablePagination` on
 * `ResizableTable` (or `TablePaginationFooter` directly). Because TanStack
 * applies filtering and sorting before the pagination row model, both still
 * operate across the whole data set rather than the visible page.
 */
export function useTablePagination(
  options: UseTablePaginationOptions = {}
): UseTablePaginationResult {
  const { initialPageSize = DEFAULT_PAGE_SIZE, resetOn } = options;

  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: initialPageSize,
  });

  const resetKey = stableKey(resetOn);
  const previousResetKey = useRef(resetKey);

  useEffect(() => {
    if (previousResetKey.current !== resetKey) {
      previousResetKey.current = resetKey;
      setPagination((prev) => (prev.pageIndex === 0 ? prev : { ...prev, pageIndex: 0 }));
    }
  }, [resetKey]);

  return { pagination, setPagination, autoResetPageIndex: false };
}

export default useTablePagination;
