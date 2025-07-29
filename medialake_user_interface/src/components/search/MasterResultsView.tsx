import React from "react";
import {
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import { formatFileSize } from "@/utils/fileSize";
import { formatDate } from "@/utils/dateFormat";
import AssetResultsView from "../shared/AssetResultsView";

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
};

interface MasterResultsViewProps {
  // Results data
  results: AssetItem[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  searchTerm: string;
  error?: { status: string; message: string } | null;
  isLoading?: boolean;

  // Search fields
  selectedFields: string[];
  availableFields: Array<{
    name: string;
    displayName: string;
    description: string;
    type: string;
    isDefault: boolean;
  }>;
  onFieldsChange: (event: any) => void;

  // View preferences
  viewMode: "card" | "table";
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
  groupByType: boolean;
  sorting: SortingState;
  cardFields: { id: string; label: string; visible: boolean }[];
  columns: AssetTableColumn<AssetItem>[];

  // Event handlers for view preferences
  onViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
  ) => void;
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  onShowMetadataChange: (show: boolean) => void;
  onGroupByTypeChange: (checked: boolean) => void;
  onSortChange: (sorting: SortingState) => void;
  onCardFieldToggle: (fieldId: string) => void;
  onColumnToggle: (columnId: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (newPageSize: number) => void;

  // Asset state
  selectedAssets?: string[];
  editingAssetId?: string;
  editedName?: string;

  // Asset action handlers
  onAssetClick: (asset: AssetItem) => void;
  onDeleteClick: (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => void;
  onMenuClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: AssetItem, save: boolean, value?: string) => void;
  onSelectToggle?: (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => void;
  onFavoriteToggle?: (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => void;

  // Select all functionality
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;

  // Asset state accessors
  isAssetFavorited?: (assetId: string) => boolean;

  // Loading states
  isRenaming?: boolean;
  renamingAssetId?: string;
}

const MasterResultsView: React.FC<MasterResultsViewProps> = ({
  results,
  searchMetadata,
  searchTerm,
  error,
  isLoading,

  // Search fields
  selectedFields,
  availableFields,
  onFieldsChange,

  // View preferences
  viewMode,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  groupByType,
  sorting,
  cardFields,
  columns,

  // Event handlers for view preferences
  onViewModeChange,
  onCardSizeChange,
  onAspectRatioChange,
  onThumbnailScaleChange,
  onShowMetadataChange,
  onGroupByTypeChange,
  onSortChange,
  onCardFieldToggle,
  onColumnToggle,
  onPageChange,
  onPageSizeChange,

  // Asset state
  selectedAssets,
  editingAssetId,
  editedName,

  // Asset action handlers
  onAssetClick,
  onDeleteClick,
  onMenuClick,
  onEditClick,
  onEditNameChange,
  onEditNameComplete,
  onSelectToggle,
  onFavoriteToggle,

  // Select all functionality
  hasSelectedAssets,
  selectAllState,
  onSelectAllToggle,

  // Asset state accessors
  isAssetFavorited,

  // Loading states
  isRenaming = false,
  renamingAssetId,
}) => {
  // Function to render card fields
  const renderCardField = (
    fieldId: string,
    asset: AssetItem,
  ): React.ReactNode => {
    // console.log('Rendering field:', fieldId, 'for asset:', asset.InventoryID);

    switch (fieldId) {
      case "name":
        return asset.DigitalSourceAsset.MainRepresentation.StorageInfo
          .PrimaryLocation.ObjectKey.Name;
      case "type":
        return asset.DigitalSourceAsset.Type;
      case "format":
        return asset.DigitalSourceAsset.MainRepresentation.Format;
      case "size":
        const sizeInBytes =
          asset.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.FileInfo.Size;
        return formatFileSize(sizeInBytes);
      case "createdAt":
        return formatDate(asset.DigitalSourceAsset.CreateDate);
      case "modifiedAt":
        return formatDate(
          asset.DigitalSourceAsset.ModifiedDate ||
            asset.DigitalSourceAsset.CreateDate,
        );
      case "fullPath":
        return asset.DigitalSourceAsset.MainRepresentation.StorageInfo
          .PrimaryLocation.ObjectKey.FullPath;
      default:
        console.log("Unknown field ID:", fieldId);
        return "";
    }
  };

  // Function to check if an asset is selected
  const isAssetSelected =
    selectedAssets && selectedAssets.length > 0
      ? (assetId: string) => selectedAssets.includes(assetId)
      : undefined;

  return (
    <AssetResultsView
      results={results}
      searchMetadata={searchMetadata}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      selectedFields={selectedFields}
      availableFields={availableFields}
      onFieldsChange={onFieldsChange}
      searchTerm={searchTerm}
      title="Results"
      groupByType={groupByType}
      onGroupByTypeChange={onGroupByTypeChange}
      viewMode={viewMode}
      onViewModeChange={onViewModeChange}
      cardSize={cardSize}
      onCardSizeChange={onCardSizeChange}
      aspectRatio={aspectRatio}
      onAspectRatioChange={onAspectRatioChange}
      thumbnailScale={thumbnailScale}
      onThumbnailScaleChange={onThumbnailScaleChange}
      showMetadata={showMetadata}
      onShowMetadataChange={onShowMetadataChange}
      sorting={sorting}
      onSortChange={onSortChange}
      cardFields={cardFields}
      onCardFieldToggle={onCardFieldToggle}
      columns={columns}
      onColumnToggle={onColumnToggle}
      onAssetClick={onAssetClick}
      onDeleteClick={onDeleteClick}
      onDownloadClick={onMenuClick}
      onEditClick={onEditClick}
      onEditNameChange={onEditNameChange}
      onEditNameComplete={onEditNameComplete}
      editingAssetId={editingAssetId}
      editedName={editedName}
      isAssetFavorited={isAssetFavorited}
      onFavoriteToggle={onFavoriteToggle}
      isAssetSelected={isAssetSelected}
      onSelectToggle={onSelectToggle}
      hasSelectedAssets={hasSelectedAssets}
      selectAllState={selectAllState}
      onSelectAllToggle={onSelectAllToggle}
      error={error}
      isLoading={isLoading}
      isRenaming={isRenaming}
      renamingAssetId={renamingAssetId}
      getAssetId={(asset) => asset.InventoryID}
      getAssetName={(asset) =>
        asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name
      }
      getAssetType={(asset) => asset.DigitalSourceAsset.Type}
      getAssetThumbnail={(asset) => asset.thumbnailUrl || ""}
      getAssetProxy={(asset) => asset.proxyUrl || ""}
      renderCardField={renderCardField}
    />
  );
};

export default MasterResultsView;
