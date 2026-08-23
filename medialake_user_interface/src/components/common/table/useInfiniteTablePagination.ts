import { useEffect } from "react";
import { useTablePagination, UseTablePaginationOptions } from "./useTablePagination";

export interface UseInfiniteTablePaginationOptions extends UseTablePaginationOptions {
  /** How many rows have been accumulated from the server so far. */
  loadedCount: number;
  /** Whether the server reports another page. */
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
}

export interface UseInfiniteTablePaginationResult {
  pagination: { pageIndex: number; pageSize: number };
  setPagination: React.Dispatch<React.SetStateAction<{ pageIndex: number; pageSize: number }>>;
  autoResetPageIndex: false;
  /** Pass to the footer so it can offer a page beyond the loaded window. */
  hasMore: boolean;
}

/**
 * Page controls over a cursor/token paginated source.
 *
 * Some lists cannot be fetched in full -- pipeline executions grow without
 * bound, so pulling everything is not an option. This keeps the server-side
 * infinite query but presents it as numbered pages: when the user navigates
 * past what has been loaded, the next server page is fetched automatically.
 *
 * Prefer plain `useTablePagination` whenever the full data set is available;
 * only reach for this when it genuinely is not.
 */
export function useInfiniteTablePagination({
  loadedCount,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  ...paginationOptions
}: UseInfiniteTablePaginationOptions): UseInfiniteTablePaginationResult {
  const { pagination, setPagination, autoResetPageIndex } = useTablePagination(paginationOptions);

  const { pageIndex, pageSize } = pagination;

  useEffect(() => {
    const rowsNeeded = (pageIndex + 1) * pageSize;
    if (rowsNeeded > loadedCount && hasNextPage && !isFetchingNextPage) {
      // Runs again after loadedCount grows, so a page larger than the server's
      // page size fills over several fetches.
      fetchNextPage();
    }
  }, [pageIndex, pageSize, loadedCount, hasNextPage, isFetchingNextPage, fetchNextPage]);

  return { pagination, setPagination, autoResetPageIndex, hasMore: hasNextPage };
}

export default useInfiniteTablePagination;
