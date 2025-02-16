import { type SortingState } from '@tanstack/react-table';
import { type AssetBase } from '../types/search/searchResults';
import { type AssetTableColumn } from '../types/shared/assetComponents';
import { formatFileSize } from './fileSize';

export function sortAssets<T extends AssetBase>(
    assets: T[],
    sorting: SortingState,
    columns?: AssetTableColumn<T>[]
): T[] {
    if (!sorting.length) return assets;

    const { id: sortField, desc } = sorting[0];

    // Find the column definition for the sort field
    const column = columns?.find(col => col.id === sortField);

    return [...assets].sort((a, b) => {
        // Use column's custom sorting function if available
        if (column?.sortingFn) {
            const result = column.sortingFn(a, b);
            return desc ? -result : result;
        }

        // Use column's accessor if available
        if (column?.accessor) {
            const valueA = column.accessor(a);
            const valueB = column.accessor(b);

            if (valueA === valueB) return 0;
            if (valueA === null || valueA === undefined) return 1;
            if (valueB === null || valueB === undefined) return -1;

            const comparison = valueA < valueB ? -1 : 1;
            return desc ? -comparison : comparison;
        }

        // Fallback to default sorting logic
        let valueA: any;
        let valueB: any;

        switch (sortField) {
            case 'name':
                valueA = a.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
                valueB = b.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
                break;
            case 'format':
                valueA = a.DigitalSourceAsset.MainRepresentation.Format;
                valueB = b.DigitalSourceAsset.MainRepresentation.Format;
                break;
            case 'createDate':
                valueA = new Date(a.DigitalSourceAsset.CreateDate).getTime();
                valueB = new Date(b.DigitalSourceAsset.CreateDate).getTime();
                break;
            case 'fileSize':
                valueA = a.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
                valueB = b.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
                break;
            default:
                return 0;
        }

        if (valueA === valueB) return 0;
        if (valueA === null || valueA === undefined) return 1;
        if (valueB === null || valueB === undefined) return -1;

        const comparison = valueA < valueB ? -1 : 1;
        return desc ? -comparison : comparison;
    });
}