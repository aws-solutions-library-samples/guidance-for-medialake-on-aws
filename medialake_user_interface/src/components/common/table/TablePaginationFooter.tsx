import React, { useEffect } from "react";
import { Table as TanStackTable } from "@tanstack/react-table";
import { PaginationFooter, PaginationFooterProps } from "../pagination/PaginationFooter";

export interface TablePaginationFooterProps<T> extends Pick<
  PaginationFooterProps,
  "pageSizeOptions" | "hideOnSinglePage" | "hasMore" | "sx"
> {
  table: TanStackTable<T>;
}

/**
 * Pagination footer for a TanStack table.
 *
 * Reads and writes the table's own pagination state, so the table stays the
 * single source of truth. Counts come from the filtered row model, which means
 * sorting and filtering apply across the entire data set and only then get
 * sliced into pages.
 *
 * The table must be created with `getPaginationRowModel()` for this to do
 * anything.
 */
export function TablePaginationFooter<T>({
  table,
  pageSizeOptions,
  hideOnSinglePage,
  hasMore,
  sx,
}: TablePaginationFooterProps<T>) {
  const { pageIndex, pageSize } = table.getState().pagination;
  const pageCount = table.getPageCount();

  // With `autoResetPageIndex` disabled (see useTablePagination), a shrinking
  // data set can leave pageIndex past the end and render an empty table. Pull
  // it back to the last real page. Skipped while more pages may still arrive,
  // since paging ahead of the loaded window is expected there.
  useEffect(() => {
    if (!hasMore && pageCount > 0 && pageIndex > pageCount - 1) {
      table.setPageIndex(pageCount - 1);
    }
  }, [table, pageIndex, pageCount, hasMore]);

  return (
    <PaginationFooter
      // TanStack is 0-indexed, the footer is 1-indexed.
      page={pageIndex + 1}
      pageSize={pageSize}
      totalItems={table.getFilteredRowModel().rows.length}
      onPageChange={(page) => table.setPageIndex(page - 1)}
      onPageSizeChange={(size) => {
        table.setPageSize(size);
        table.setPageIndex(0);
      }}
      pageSizeOptions={pageSizeOptions}
      hideOnSinglePage={hideOnSinglePage}
      hasMore={hasMore}
      sx={sx}
    />
  );
}

export default TablePaginationFooter;
