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
import { useDebounce } from "@/hooks/useDebounce";
import AssetResultsView from "../shared/AssetResultsView";
import {
  transformResultsToClipMode,
  getClipDisplayName,
  isClipAsset,
} from "@/utils/clipTransformation";
import { useSemanticMode } from "@/stores/searchStore";

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

  // Semantic search confidence filtering
  isSemantic?: boolean;
  confidenceThreshold?: number;
  onConfidenceThresholdChange?: (threshold: number) => void;

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
  onAddToCollectionClick?: (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => void;
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

  // Semantic search confidence filtering
  isSemantic = false,
  confidenceThreshold = 0.57,
  onConfidenceThresholdChange,

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
  onAddToCollectionClick,
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
  // Debug: Check if we're receiving the onAddToCollectionClick prop
  console.log(
    "MasterResultsView: onAddToCollectionClick prop is:",
    typeof onAddToCollectionClick,
    onAddToCollectionClick,
  );

  // Get semantic mode from store
  const semanticMode = useSemanticMode();

  // Pre-compute and store the transformed results (expensive operation)
  // This only recalculates when results, isSemantic, semanticMode, or pagination change
  const { transformedResults, adjustedSearchMetadata } = React.useMemo(() => {
    console.log("🔄 Transforming results to clip mode...", {
      resultsCount: results.length,
      isSemantic,
      semanticMode,
      page: searchMetadata.page,
      pageSize: searchMetadata.pageSize,
    });

    const transformation = transformResultsToClipMode(
      results,
      isSemantic,
      semanticMode,
      // Only apply pagination in clip mode
      isSemantic && semanticMode === "clip"
        ? {
            page: searchMetadata.page,
            pageSize: searchMetadata.pageSize,
          }
        : undefined,
    );

    // Adjust search metadata for clip mode
    const adjustedMetadata = {
      ...searchMetadata,
      totalResults:
        isSemantic && semanticMode === "clip"
          ? transformation.totalClips
          : searchMetadata.totalResults,
    };

    return {
      transformedResults: transformation.results,
      adjustedSearchMetadata: adjustedMetadata,
    };
  }, [results, isSemantic, semanticMode, searchMetadata]);

  // Function to render card fields - memoized to prevent unnecessary re-renders
  const renderCardField = React.useCallback(
    (fieldId: string, asset: AssetItem): React.ReactNode => {
      // console.log('Rendering field:', fieldId, 'for asset:', asset.InventoryID);

      switch (fieldId) {
        case "name":
          // Use clip display name for clip assets
          return isClipAsset(asset)
            ? getClipDisplayName(asset)
            : asset.DigitalSourceAsset.MainRepresentation.StorageInfo
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
    },
    [],
  ); // No dependencies since this function is pure

  // Function to check if an asset is selected
  const isAssetSelected =
    selectedAssets && selectedAssets.length > 0
      ? (assetId: string) => selectedAssets.includes(assetId)
      : undefined;

  // Debounce the confidence threshold to reduce rapid filtering during slider interaction
  // Reduced debounce time for more responsive UI
  const debouncedConfidenceThreshold = useDebounce(
    confidenceThreshold || 0,
    100,
  );

  // Filter results based on confidence threshold for semantic search
  // This is a lightweight operation that only filters the pre-computed results
  const filteredResults = React.useMemo(() => {
    const startTime = performance.now();

    if (
      !isSemantic ||
      debouncedConfidenceThreshold === undefined ||
      debouncedConfidenceThreshold === 0
    ) {
      console.log("🔍 No filtering needed - returning all transformed results");
      return transformedResults;
    }

    const filtered = transformedResults.filter((asset) => {
      const score = asset.score ?? 1; // Default to 1 if no score (non-semantic results)
      const passesThreshold = score >= debouncedConfidenceThreshold;

      // Debug logging for clips starting at 00:00:00
      if (
        isClipAsset(asset) &&
        asset.clipData.start_timecode === "00:00:00:00"
      ) {
        console.log(`🔍 Confidence filtering clip starting at 00:00:00:00:`, {
          assetId: asset.InventoryID,
          score,
          threshold: debouncedConfidenceThreshold,
          passesThreshold,
        });
      }

      return passesThreshold;
    });

    const endTime = performance.now();
    console.log(
      `🔍 Confidence filtering completed in ${(endTime - startTime).toFixed(2)}ms`,
      {
        originalCount: transformedResults.length,
        filteredCount: filtered.length,
        threshold: debouncedConfidenceThreshold,
      },
    );

    return filtered;
  }, [transformedResults, isSemantic, debouncedConfidenceThreshold]);

  return (
    <AssetResultsView
      results={filteredResults}
      originalResults={transformedResults}
      isSemantic={isSemantic}
      confidenceThreshold={confidenceThreshold}
      onConfidenceThresholdChange={onConfidenceThresholdChange}
      searchMetadata={adjustedSearchMetadata}
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
      onAddToCollectionClick={onAddToCollectionClick}
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
      getAssetId={React.useCallback((asset) => asset.InventoryID, [])}
      getAssetName={React.useCallback(
        (asset) =>
          isClipAsset(asset)
            ? getClipDisplayName(asset)
            : asset.DigitalSourceAsset.MainRepresentation.StorageInfo
                .PrimaryLocation.ObjectKey.Name,
        [],
      )}
      getAssetType={React.useCallback(
        (asset) => asset.DigitalSourceAsset.Type,
        [],
      )}
      getAssetThumbnail={React.useCallback(
        (asset) => asset.thumbnailUrl || "",
        [],
      )}
      getAssetProxy={React.useCallback((asset) => asset.proxyUrl || "", [])}
      renderCardField={renderCardField}
    />
  );
};

export default MasterResultsView;
