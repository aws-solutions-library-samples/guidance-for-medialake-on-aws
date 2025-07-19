import { type SortingState } from "@tanstack/react-table";
import { type AssetBase } from "../types/search/searchResults";
import { type AssetTableColumn } from "../types/shared/assetComponents";
import { formatFileSize } from "./fileSize";

export function sortAssets<T extends AssetBase>(
  assets: T[],
  sorting: SortingState,
  columns?: AssetTableColumn<T>[],
): T[] {
  if (!sorting.length) return assets;

  const { id: sortField, desc } = sorting[0];
  const column = columns?.find((col) => col.id === sortField);

  return [...assets].sort((a, b) => {
    // Use accessorFn for all sorting
    if (column?.accessorFn) {
      const valueA = column.accessorFn(a);
      const valueB = column.accessorFn(b);

      if (valueA === valueB) return 0;
      if (valueA === null || valueA === undefined) return 1;
      if (valueB === null || valueB === undefined) return -1;

      if (typeof valueA === "string" && typeof valueB === "string") {
        return valueA.localeCompare(valueB) * (desc ? -1 : 1);
      }

      if (typeof valueA === "number" && typeof valueB === "number") {
        return (valueA - valueB) * (desc ? -1 : 1);
      }

      // Handle dates
      if (valueA instanceof Date && valueB instanceof Date) {
        return (valueA.getTime() - valueB.getTime()) * (desc ? -1 : 1);
      }

      // Try to convert to dates if they're date strings
      if (typeof valueA === "string" && typeof valueB === "string") {
        const dateA = new Date(valueA);
        const dateB = new Date(valueB);
        if (!isNaN(dateA.getTime()) && !isNaN(dateB.getTime())) {
          return (dateA.getTime() - dateB.getTime()) * (desc ? -1 : 1);
        }
      }

      const comparison = valueA < valueB ? -1 : 1;
      return desc ? -comparison : comparison;
    }

    if (column?.accessorFn) {
      const valueA = column.accessorFn(a);
      const valueB = column.accessorFn(b);

      if (valueA === valueB) return 0;
      if (valueA === null || valueA === undefined) return 1;
      if (valueB === null || valueB === undefined) return -1;

      const comparison = valueA < valueB ? -1 : 1;
      return desc ? -comparison : comparison;
    }

    return 0;
  });
}
