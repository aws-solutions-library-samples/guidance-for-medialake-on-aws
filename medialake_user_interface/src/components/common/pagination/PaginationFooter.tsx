import React from "react";
import {
  Box,
  FormControl,
  MenuItem,
  Pagination,
  Select,
  SelectChangeEvent,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { PAGE_SIZE_OPTIONS } from "@/constants/pagination";

export interface PaginationFooterProps {
  /** Current page, 1-indexed. */
  page: number;
  pageSize: number;
  /** Total number of items across all pages, after any filtering. */
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  /** Defaults to PAGE_SIZE_OPTIONS. */
  pageSizeOptions?: number[];
  /**
   * When true, the count is described as filtered. Useful when `totalItems`
   * reflects a client-side filter rather than the full data set.
   */
  isFiltered?: boolean;
  /** Hide the whole footer when there is only one page. Defaults to false. */
  hideOnSinglePage?: boolean;
  /**
   * For cursor/token paginated sources where the true total is unknown and
   * `totalItems` only counts what has been loaded so far. Keeps one extra page
   * available so the user can page forward, and shows the count as "N+".
   */
  hasMore?: boolean;
  /** Extra styles merged onto the wrapper. */
  sx?: object;
}

/**
 * Shared pagination footer: item range, page-size selector, page navigation.
 *
 * This is the single presentational component behind every paginated list in
 * the app. It is intentionally state-free -- callers own `page`/`pageSize`, via
 * `usePagination` for plain lists or `TablePaginationFooter` for TanStack
 * tables.
 */
export const PaginationFooter: React.FC<PaginationFooterProps> = ({
  page,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  isFiltered = false,
  hideOnSinglePage = false,
  hasMore = false,
  sx,
}) => {
  const { t } = useTranslation();

  const loadedPageCount = Math.max(1, Math.ceil(totalItems / pageSize));
  // One speculative page so a cursor-paginated source can be advanced into.
  const pageCount = hasMore ? loadedPageCount + 1 : loadedPageCount;

  if (totalItems === 0) {
    return null;
  }
  if (hideOnSinglePage && pageCount <= 1) {
    return null;
  }

  const handlePageSizeChange = (event: SelectChangeEvent<number>) => {
    onPageSizeChange(Number(event.target.value));
  };

  // Clamp so a stale page never renders a nonsense range such as "101 - 150 of 20".
  const safePage = Math.min(Math.max(page, 1), pageCount);
  const lastItem = Math.min(safePage * pageSize, totalItems);
  // Also clamped to lastItem so the speculative `hasMore` page never shows an
  // inverted range such as "51 - 50 of 50+".
  const firstItem = Math.min((safePage - 1) * pageSize + 1, lastItem);
  // Signals "at least this many" when the true total is not known yet.
  const totalLabel = hasMore ? `${totalItems}+` : `${totalItems}`;

  // Offer the configured sizes plus whatever is currently applied, so a value
  // set elsewhere (a saved preference, say) does not render a blank Select.
  const options = pageSizeOptions.includes(pageSize)
    ? pageSizeOptions
    : [...pageSizeOptions, pageSize].sort((a, b) => a - b);

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 2,
        mt: 2,
        mb: 1,
        backgroundColor: "transparent",
        ...sx,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Typography variant="body2" color="text.secondary">
          {isFiltered
            ? t("common.pagination.showingFiltered", {
                count: totalItems,
                defaultValue: `Showing ${totalItems} filtered results`,
              })
            : t("common.pagination.showingRange", {
                first: firstItem,
                last: lastItem,
                total: totalLabel,
                defaultValue: `Showing ${firstItem} - ${lastItem} of ${totalLabel} results`,
              })}
        </Typography>
        <FormControl size="small" variant="outlined">
          <Select
            value={pageSize}
            onChange={handlePageSizeChange}
            inputProps={{
              "aria-label": t("common.pagination.rowsPerPage", {
                defaultValue: "Rows per page",
              }),
            }}
            sx={{
              minWidth: 80,
              height: 32,
              "& .MuiSelect-select": { py: 0.5, px: 1.5 },
            }}
          >
            {options.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
      <Pagination
        count={pageCount}
        page={safePage}
        onChange={(_event, value) => onPageChange(value)}
        color="primary"
        size="medium"
        shape="circular"
        showFirstButton
        showLastButton
        getItemAriaLabel={(type, pageNumber) => {
          if (type === "page") {
            return t("common.pagination.goToPage", {
              page: pageNumber,
              defaultValue: `Go to page ${pageNumber}`,
            });
          }
          return t(`common.pagination.${type}`, { defaultValue: `Go to ${type} page` });
        }}
        sx={{
          "& .MuiPaginationItem-root": {
            borderRadius: "50%",
            minWidth: 40,
            height: 40,
            "&.Mui-selected": {
              fontWeight: "bold",
              backgroundColor: "primary.main",
              color: "white",
              "&:hover": { backgroundColor: "primary.dark" },
            },
          },
        }}
      />
    </Box>
  );
};

export default PaginationFooter;
