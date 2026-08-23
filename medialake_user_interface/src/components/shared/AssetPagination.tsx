import React from "react";
import { PaginationFooter } from "@/components/common/pagination/PaginationFooter";

/**
 * Page-size choices for asset browsing.
 *
 * Deliberately wider than the shared PAGE_SIZE_OPTIONS: asset grids are
 * routinely scanned in large batches, so the bigger steps are kept.
 */
const ASSET_PAGE_SIZE_OPTIONS = [20, 50, 75, 100, 150, 200, 250];

interface AssetPaginationProps {
  page: number;
  pageSize: number;
  totalResults: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
  isFiltered?: boolean;
}

/**
 * Asset-flavoured wrapper around the shared PaginationFooter.
 *
 * Keeps the wider asset page-size options; `onPageChange` receives just the
 * 1-indexed page number, matching PaginationFooter.
 */
const AssetPagination: React.FC<AssetPaginationProps> = ({
  page,
  pageSize,
  totalResults,
  onPageChange,
  onPageSizeChange,
  isFiltered = false,
}) => (
  <PaginationFooter
    page={page}
    pageSize={pageSize}
    totalItems={totalResults}
    onPageChange={onPageChange}
    onPageSizeChange={onPageSizeChange}
    pageSizeOptions={ASSET_PAGE_SIZE_OPTIONS}
    isFiltered={isFiltered}
    sx={{ mt: 6, mb: 2 }}
  />
);

export default AssetPagination;
