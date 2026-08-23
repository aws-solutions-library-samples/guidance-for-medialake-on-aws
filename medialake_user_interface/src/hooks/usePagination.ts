import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_PAGE_SIZE } from "@/constants/pagination";
import { stableKey } from "@/components/common/pagination/paginationKey";

export interface UsePaginationOptions {
  /** Defaults to DEFAULT_PAGE_SIZE. */
  initialPageSize?: number;
  /**
   * Values that should send the user back to page 1 when they change, such as
   * a search term or a set of filters. Without this, filtering while on page 5
   * leaves the user staring at an empty page.
   */
  resetOn?: unknown[];
}

export interface UsePaginationResult<T> {
  /** Current page, 1-indexed and always within range. */
  page: number;
  pageSize: number;
  pageCount: number;
  /** Length of the input list. */
  totalItems: number;
  /** The current page's slice of the input list. */
  paginatedItems: T[];
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
}

/**
 * Client-side pagination for lists that are not driven by TanStack Table.
 *
 * Use this for card grids and hand-rolled MUI tables. TanStack tables should
 * use `getPaginationRowModel()` plus `TablePaginationFooter` instead, so that
 * sorting and filtering keep running across the whole data set before the page
 * slice is taken.
 */
export function usePagination<T>(
  items: T[],
  options: UsePaginationOptions = {}
): UsePaginationResult<T> {
  const { initialPageSize = DEFAULT_PAGE_SIZE, resetOn } = options;

  const [page, setPageState] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  const totalItems = items.length;
  const pageCount = Math.max(1, Math.ceil(totalItems / pageSize));

  // Clamp during render so the slice is always valid, even on the render where
  // the list shrank (a delete, or a filter being applied).
  const safePage = Math.min(Math.max(page, 1), pageCount);

  const resetKey = stableKey(resetOn);
  const previousResetKey = useRef(resetKey);

  useEffect(() => {
    if (previousResetKey.current !== resetKey) {
      previousResetKey.current = resetKey;
      setPageState(1);
    }
  }, [resetKey]);

  // Keep state in step with the clamped value so the controls do not show a
  // page number that no longer exists.
  useEffect(() => {
    if (page !== safePage) {
      setPageState(safePage);
    }
  }, [page, safePage]);

  const setPage = useCallback((next: number) => {
    setPageState(Math.max(1, next));
  }, []);

  const setPageSize = useCallback((next: number) => {
    setPageSizeState(Math.max(1, next));
    // Row counts shift, so anchoring back to the first page is the predictable
    // behaviour here.
    setPageState(1);
  }, []);

  const paginatedItems = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, safePage, pageSize]);

  return {
    page: safePage,
    pageSize,
    pageCount,
    totalItems,
    paginatedItems,
    setPage,
    setPageSize,
  };
}

export default usePagination;
