import { SortingState } from '@tanstack/react-table';
import { AssetTableColumn } from '@/types/shared/assetComponents';

/**
 * Sort assets based on the current sorting state
 * @param assets Array of assets to sort
 * @param sorting Current sorting state
 * @param columns Column definitions with sorting functions (optional)
 * @returns Sorted array of assets
 */
export const sortAssets = <T>(
  assets: T[],
  sorting: SortingState,
  columns?: AssetTableColumn<T>[]
): T[] => {
  if (!sorting.length || !assets.length) {
    return assets;
  }

  const sortColumn = sorting[0];
  
  // If columns are provided, use their sorting functions
  if (columns) {
    const column = columns.find(col => col.id === sortColumn.id);

    if (!column || !column.sortingFn) {
      return assets;
    }

    // Create a copy of the array to avoid mutating the original
    const sortedAssets = [...assets];

    // Sort the assets using the column's sorting function
    sortedAssets.sort((a, b) => {
      const result = column.sortingFn(
        { original: a } as any,
        { original: b } as any
      );
      return sortColumn.desc ? -result : result;
    });

    return sortedAssets;
  }
  
  // Default sorting if no columns are provided
  return [...assets].sort((a, b) => {
    // Try to access the property using the sort column id
    const aValue = (a as any)[sortColumn.id];
    const bValue = (b as any)[sortColumn.id];
    
    if (aValue === bValue) return 0;
    if (aValue === undefined) return 1;
    if (bValue === undefined) return -1;
    
    // Compare based on type
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortColumn.desc 
        ? bValue.localeCompare(aValue) 
        : aValue.localeCompare(bValue);
    }
    
    return sortColumn.desc 
      ? (bValue > aValue ? 1 : -1)
      : (aValue > bValue ? 1 : -1);
  });
};
