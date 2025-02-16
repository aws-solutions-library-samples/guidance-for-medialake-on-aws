import { type AssetBase } from '../search/searchResults';
import { type SortingState } from '@tanstack/react-table';

export interface AssetField {
    id: string;
    label: string;
    visible: boolean;
}

export interface AssetTableColumn<T> {
    id: string;
    label: string;
    visible: boolean;
    minWidth: number;
    format?: (value: any) => string | React.ReactNode;
    accessor?: (row: T) => any;
    sortable?: boolean;
    sortingFn?: (a: T, b: T) => number;
}

export interface AssetCardProps {
    id: string;
    name: string;
    thumbnailUrl?: string;
    proxyUrl?: string;
    fields: AssetField[];
    renderField: (fieldId: string) => string | React.ReactNode;
    onAssetClick: () => void;
    onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
    placeholderImage?: string;
    onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
}

export interface AssetTableProps<T> {
    data: T[];
    columns: AssetTableColumn<T>[];
    sorting: SortingState;
    onSortingChange: (sorting: SortingState) => void;
    onDeleteClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onMenuClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    onEditClick?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
    getThumbnailUrl: (item: T) => string;
    getName: (item: T) => string;
    getId: (item: T) => string;
    editingId?: string;
    editedName?: string;
    onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onEditNameComplete?: (item: T) => void;
}

export interface AssetViewControlsProps {
    viewMode: 'card' | 'table';
    onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
    title: string;
    sorting: SortingState;
    sortOptions: SortOption[];
    onSortChange: (columnId: string) => void;
    fields: AssetField[];
    onFieldToggle: (fieldId: string) => void;
}

export interface SortOption {
    id: string;
    label: string;
}
