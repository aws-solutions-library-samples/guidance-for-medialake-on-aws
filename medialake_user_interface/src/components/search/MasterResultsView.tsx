import React from "react";
import { useTranslation } from "react-i18next";
import { type ImageItem, type VideoItem, type AudioItem } from "@/types/search/searchResults";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import { formatFileSize } from "@/utils/fileSize";
import { formatDate } from "@/utils/dateFormat";
import { useDebounce } from "@/hooks/useDebounce";
import AssetResultsView from "../shared/AssetResultsView";
import { AssetItemProvider } from "@/contexts/AssetItemContext";
import { ChipArrayField } from "@/components/common/ChipArrayField";
import { resolveDotPath } from "@/utils/dotPathResolve";
import {
  transformResultsToClipMode,
  getClipDisplayName,
  isClipAsset,
} from "@/utils/clipTransformation";
import { useSemanticMode } from "@/stores/searchStore";
import { useSemanticSearchStatus } from "@/features/settings/system/hooks/useSystemSettings";
import { useMetadataFieldPreferences } from "@/hooks/useMetadataFieldPreferences";
import { useSearchFields } from "@/api/hooks/useSearchFields";

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
    newMode: "card" | "table" | null
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
  onDeleteClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: AssetItem, save: boolean, value?: string) => void;
  onSelectToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onFavoriteToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;

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
  const { t } = useTranslation();

  // Get semantic mode from store
  const semanticMode = useSemanticMode();

  // Get selected/available fields for custom card field computation
  const { selectedFields, setSelectedFields } = useMetadataFieldPreferences();
  const { data: fieldsData } = useSearchFields();
  const availableFields = fieldsData?.data?.availableFields ?? [];

  // Pre-compute and store the transformed results (expensive operation)
  // This only recalculates when results, isSemantic, semanticMode, or pagination change
  const { transformedResults, adjustedSearchMetadata } = React.useMemo(() => {
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
        : undefined
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

  // Known field IDs from the standard fieldMapping (used to identify custom fields)
  const knownFieldMappingKeys = React.useMemo(
    () =>
      new Set([
        "id",
        "assetType",
        "format",
        "createdAt",
        "objectName",
        "fileSize",
        "fullPath",
        "bucket",
        "FileHash",
        "DigitalSourceAsset.Type",
        "DigitalSourceAsset.MainRepresentation.Format",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate",
        "DigitalSourceAsset.CreateDate",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath",
        "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket",
        "Metadata.Consolidated",
        "InventoryID",
      ]),
    []
  );

  // Function to render card fields - memoized to prevent unnecessary re-renders
  const renderCardField = React.useCallback(
    (fieldId: string, asset: AssetItem): React.ReactNode => {
      switch (fieldId) {
        case "name":
          // Use clip display name for clip assets
          return isClipAsset(asset)
            ? getClipDisplayName(asset)
            : asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey
                .Name;
        case "type":
          return asset.DigitalSourceAsset.Type;
        case "format":
          return asset.DigitalSourceAsset.MainRepresentation.Format;
        case "size": {
          const sizeInBytes =
            asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
          return formatFileSize(sizeInBytes);
        }
        case "createdAt":
          return formatDate(asset.DigitalSourceAsset.CreateDate);
        case "modifiedAt":
          return formatDate(
            asset.DigitalSourceAsset.ModifiedDate || asset.DigitalSourceAsset.CreateDate
          );
        case "fullPath":
          return asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey
            .FullPath;
        default: {
          // Array-aware dot-path traversal for custom fields
          const value = resolveDotPath(asset, fieldId);
          if (value == null) return "—";
          if (Array.isArray(value)) {
            if (value.length === 0) return "—";
            return <ChipArrayField values={value.map(String)} />;
          }
          return String(value);
        }
      }
    },
    []
  );

  // Compute custom card fields from selectedFields that aren't in the standard fieldMapping
  const customCardFields = React.useMemo(() => {
    return selectedFields
      .filter((f) => !knownFieldMappingKeys.has(f))
      .map((fieldPath) => ({
        id: fieldPath,
        label:
          availableFields.find((af) => af.name === fieldPath)?.displayName ??
          fieldPath.split(".").at(-1) ??
          fieldPath,
        visible: true,
      }));
  }, [selectedFields, availableFields, knownFieldMappingKeys]);

  const mergedCardFields = React.useMemo(
    () => [...cardFields, ...customCardFields],
    [cardFields, customCardFields]
  );

  // Function to check if an asset is selected
  const isAssetSelected = React.useMemo(
    () =>
      selectedAssets && selectedAssets.length > 0
        ? (assetId: string) => selectedAssets.includes(assetId)
        : undefined,
    [selectedAssets]
  );

  // Debounce the confidence threshold to reduce rapid filtering during slider interaction
  // Reduced debounce time for more responsive UI
  const debouncedConfidenceThreshold = useDebounce(confidenceThreshold || 0, 100);

  // Detect model version and provider type from system settings for threshold calculation
  const { providerData } = useSemanticSearchStatus();
  const providerType = providerData?.data?.searchProvider?.type;
  const isCoactiveProvider = providerType === "coactive";
  const detectedModelVersion = React.useMemo(() => {
    if (providerType === "twelvelabs-bedrock-3-0") {
      return "3.0";
    }
    return "2.7";
  }, [providerType]);

  // Filter results based on confidence threshold for semantic search
  // Coactive provider does not support confidence scoring, so skip filtering
  // This is a lightweight operation that only filters the pre-computed results
  const filteredResults = React.useMemo(() => {
    if (
      isCoactiveProvider ||
      !isSemantic ||
      debouncedConfidenceThreshold === undefined ||
      debouncedConfidenceThreshold === 0
    ) {
      return transformedResults;
    }

    const filtered = transformedResults.filter((asset) => {
      const score = asset.score ?? 1; // Default to 1 if no score (non-semantic results)
      const passesThreshold = score >= debouncedConfidenceThreshold;

      return passesThreshold;
    });

    return filtered;
  }, [transformedResults, isSemantic, isCoactiveProvider, debouncedConfidenceThreshold]);

  // Stable accessor functions
  const getAssetId = React.useCallback((asset: AssetItem) => asset.InventoryID, []);
  const getAssetName = React.useCallback(
    (asset: AssetItem) =>
      isClipAsset(asset)
        ? getClipDisplayName(asset)
        : asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
    []
  );
  const getAssetType = React.useCallback((asset: AssetItem) => asset.DigitalSourceAsset.Type, []);
  const getAssetThumbnail = React.useCallback((asset: AssetItem) => asset.thumbnailUrl || "", []);
  const getAssetProxy = React.useCallback((asset: AssetItem) => asset.proxyUrl || "", []);

  const itemActions = React.useMemo(
    () => ({
      onAssetClick,
      onDeleteClick,
      onDownloadClick: onMenuClick,
      onAddToCollectionClick,
      onEditClick,
      onEditNameChange,
      onEditNameComplete,
      editingAssetId,
      editedName,
      isAssetFavorited,
      onFavoriteToggle,
      isAssetSelected,
      onSelectToggle,
      isRenaming,
      renamingAssetId,
      isSemantic,
      confidenceThreshold,
      getAssetId,
      getAssetName,
      getAssetType,
      getAssetThumbnail,
      getAssetProxy,
      renderCardField,
    }),
    [
      onAssetClick,
      onDeleteClick,
      onMenuClick,
      onAddToCollectionClick,
      onEditClick,
      onEditNameChange,
      onEditNameComplete,
      editingAssetId,
      editedName,
      isAssetFavorited,
      onFavoriteToggle,
      isAssetSelected,
      onSelectToggle,
      isRenaming,
      renamingAssetId,
      isSemantic,
      confidenceThreshold,
      getAssetId,
      getAssetName,
      getAssetType,
      getAssetThumbnail,
      getAssetProxy,
      renderCardField,
    ]
  );

  return (
    <AssetItemProvider value={itemActions}>
      <AssetResultsView
        results={filteredResults}
        originalResults={transformedResults}
        isSemantic={isSemantic}
        confidenceThreshold={confidenceThreshold}
        onConfidenceThresholdChange={onConfidenceThresholdChange}
        detectedModelVersion={detectedModelVersion}
        hideConfidenceSlider={isCoactiveProvider}
        searchMetadata={adjustedSearchMetadata}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        searchTerm={searchTerm}
        title={t("search.results.title")}
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
        cardFields={mergedCardFields}
        onCardFieldToggle={onCardFieldToggle}
        columns={columns}
        onColumnToggle={onColumnToggle}
        selectedSearchFields={isCoactiveProvider ? undefined : selectedFields}
        availableFields={availableFields}
        onSelectedFieldsChange={isCoactiveProvider ? undefined : setSelectedFields}
        hasSelectedAssets={hasSelectedAssets}
        selectAllState={selectAllState}
        onSelectAllToggle={onSelectAllToggle}
        error={error}
        isLoading={isLoading}
      />
    </AssetItemProvider>
  );
};

export default MasterResultsView;
