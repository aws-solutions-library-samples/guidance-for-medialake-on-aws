import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "../types/shared/assetComponents";
import { resolveDotPath } from "./dotPathResolve";

export function sortAssets<T>(
  assets: T[],
  sorting: SortingState,
  columns?: AssetTableColumn<T>[]
): T[] {
  if (!sorting.length) return assets;

  const { id: sortField, desc } = sorting[0];
  const column = columns?.find((col) => col.id === sortField);

  return [...assets].sort((a, b) => {
    let valueA: unknown;
    let valueB: unknown;

    if (column?.accessorFn) {
      valueA = column.accessorFn(a);
      valueB = column.accessorFn(b);
    } else {
      // Fallback: resolve custom metadata dot-path fields
      valueA = resolveDotPath(a, sortField);
      valueB = resolveDotPath(b, sortField);
      // Flatten arrays to first value for comparison
      if (Array.isArray(valueA)) valueA = valueA[0];
      if (Array.isArray(valueB)) valueB = valueB[0];
    }

    if (valueA === valueB) return 0;
    if (valueA == null) return 1;
    if (valueB == null) return -1;

    if (typeof valueA === "string" && typeof valueB === "string") {
      // Try numeric comparison for numeric strings
      const numA = Number(valueA);
      const numB = Number(valueB);
      if (!isNaN(numA) && !isNaN(numB)) {
        return (numA - numB) * (desc ? -1 : 1);
      }
      const ISO_DATE_RE =
        /^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/;

      // Try date comparison for date strings
      if (ISO_DATE_RE.test(valueA) && ISO_DATE_RE.test(valueB)) {
        const dateA = Date.parse(valueA);
        const dateB = Date.parse(valueB);
        return (dateA - dateB) * (desc ? -1 : 1);
      }
      return valueA.localeCompare(valueB) * (desc ? -1 : 1);
    }

    if (typeof valueA === "number" && typeof valueB === "number") {
      return (valueA - valueB) * (desc ? -1 : 1);
    }

    if (valueA instanceof Date && valueB instanceof Date) {
      return (valueA.getTime() - valueB.getTime()) * (desc ? -1 : 1);
    }

    const comparison = valueA < valueB ? -1 : 1;
    return desc ? -comparison : comparison;
  });
}
