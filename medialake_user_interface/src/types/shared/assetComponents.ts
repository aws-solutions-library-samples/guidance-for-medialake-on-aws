import { type AssetBase } from "../search/searchResults";
import {
  type SortingState,
  type ColumnDef,
  type CellContext,
} from "@tanstack/react-table";
import type React from "react";

export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

export interface AssetTableColumn<T>
  extends Omit<ColumnDef<T>, "accessorKey" | "accessorFn"> {
  id: string;
  label: string;
  minWidth: number;
  visible: boolean;
  sortable?: boolean;
  accessorFn: (row: T) => unknown;
  cell?: (info: CellContext<T, unknown>) => React.ReactNode;
}

export interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType: string;
  fields: AssetField[];
  renderField: (fieldId: string) => React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (event: React.MouseEvent<HTMLElement>) => void;
  isEditing?: boolean;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean) => void;
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
}

export interface AssetTableProps<T> {
  data: T[];
  columns: AssetTableColumn<T>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onDeleteClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onAssetClick: (item: T) => void;
  getThumbnailUrl: (item: T) => string;
  getName: (item: T) => string;
  getId: (item: T) => string;
  editingId?: string;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (item: T) => void;
}

export type CardSize = "small" | "medium" | "large";
export type AspectRatio = "vertical" | "square" | "horizontal";
export type ThumbnailScale = "fit" | "fill";

export interface AssetViewControlsProps {
  viewMode: "card" | "table";
  onViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
  ) => void;
  title: string;
  sorting: SortingState;
  sortOptions: Array<{ id: string; label: string }>;
  onSortChange: (columnId: string) => void;
  fields: Array<{ id: string; label: string; visible: boolean }>;
  onFieldToggle: (fieldId: string) => void;
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  cardSize: "small" | "medium" | "large";
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  aspectRatio: "vertical" | "square" | "horizontal";
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  // Selection props
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;
}

export interface SortOption {
  id: string;
  label: string;
}
