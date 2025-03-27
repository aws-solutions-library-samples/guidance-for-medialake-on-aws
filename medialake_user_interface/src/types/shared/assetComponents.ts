import { CellContext } from '@tanstack/react-table';

/**
 * Interface for asset table column configuration
 */
export interface AssetTableColumn<T> {
  id: string;
  label: string;
  visible: boolean;
  minWidth?: number;
  accessorFn?: (row: T) => any;
  cell?: (info: CellContext<T, any>) => React.ReactNode;
  sortable?: boolean;
  sortingFn?: (rowA: any, rowB: any) => number;
}

/**
 * Interface for asset field configuration
 */
export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

/**
 * Interface for asset view controls props
 */
export interface AssetViewControlsProps {
  viewMode: 'card' | 'table';
  onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
  title: string;
  sorting: any[];
  sortOptions: { id: string; label: string }[];
  onSortChange: (columnId: string) => void;
  fields: { id: string; label: string; visible: boolean }[];
  onFieldToggle: (fieldId: string) => void;
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  cardSize: 'small' | 'medium' | 'large';
  onCardSizeChange: (size: 'small' | 'medium' | 'large') => void;
  aspectRatio: 'vertical' | 'square' | 'horizontal';
  onAspectRatioChange: (ratio: 'vertical' | 'square' | 'horizontal') => void;
  thumbnailScale: 'fit' | 'fill';
  onThumbnailScaleChange: (scale: 'fit' | 'fill') => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
}
