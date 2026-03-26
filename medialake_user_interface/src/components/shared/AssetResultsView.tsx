import React from "react";
import { Box, Typography, LinearProgress } from "@mui/material";
import { useTranslation } from "react-i18next";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn, type AssetField } from "@/types/shared/assetComponents";
import {
  useAssetAccessors,
  useAssetActions,
  useAssetEditingState,
} from "@/contexts/AssetItemContext";
import AssetViewControls from "./AssetViewControls";
import AssetPagination from "./AssetPagination";
import AssetGridView from "./AssetGridView";
import AssetTableView from "./AssetTableView";
import ErrorDisplay from "./ErrorDisplay";
import { sortAssets } from "@/utils/sortAssets";
import ConfidenceSlider from "./ConfidenceSlider";
import { zIndexTokens } from "@/theme/tokens";
import { type FieldInfo } from "@/api/hooks/useSearchFields";

export type { AssetField };

export interface AssetResultsViewProps<T> {
  // Data
  results: T[];
  originalResults?: T[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
  searchTerm?: string;
  title?: string;
  error?: { status: string; message: string } | null;
  isLoading?: boolean;

  // Semantic search confidence filtering
  isSemantic?: boolean;
  confidenceThreshold?: number;
  onConfidenceThresholdChange?: (threshold: number) => void;
  detectedModelVersion?: string;
  hideConfidenceSlider?: boolean;

  // View preferences
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  viewMode: "card" | "table";
  onViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null
  ) => void;
  cardSize: "small" | "medium" | "large";
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  aspectRatio: "vertical" | "square" | "horizontal";
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  sorting: SortingState;
  onSortChange: (sorting: SortingState) => void;
  cardFields: AssetField[];
  onCardFieldToggle: (fieldId: string) => void;
  columns: AssetTableColumn<T>[];
  onColumnToggle: (columnId: string) => void;

  // Metadata field filtering
  selectedSearchFields?: string[];
  availableFields?: FieldInfo[];
  onSelectedFieldsChange?: (fields: string[]) => void;

  // Select all (used by AssetViewControls toolbar)
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;
}

function AssetResultsView<T>({
  results,
  originalResults,
  searchMetadata,
  onPageChange,
  onPageSizeChange,
  searchTerm,
  title = "Results",
  error,
  isLoading,

  // Semantic search
  isSemantic = false,
  confidenceThreshold = 0.57,
  onConfidenceThresholdChange,
  detectedModelVersion,
  hideConfidenceSlider = false,

  // View preferences
  groupByType,
  onGroupByTypeChange,
  viewMode,
  onViewModeChange,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange,
  sorting,
  onSortChange,
  cardFields,
  onCardFieldToggle,
  columns,
  onColumnToggle,

  // Metadata field filtering
  selectedSearchFields,
  availableFields,
  onSelectedFieldsChange,

  // Select all
  hasSelectedAssets,
  selectAllState,
  onSelectAllToggle,
}: AssetResultsViewProps<T>) {
  const { t } = useTranslation();

  // Pull action handlers + accessors from split contexts for better performance
  const {
    getAssetId,
    getAssetName,
    getAssetType,
    getAssetThumbnail,
    getAssetProxy,
    renderCardField,
  } = useAssetAccessors<T>();

  const {
    onAssetClick,
    onDeleteClick,
    onDownloadClick,
    onAddToCollectionClick,
    showRemoveButton = false,
    onEditClick,
    onEditNameChange,
    onEditNameComplete,
    onFavoriteToggle,
    onSelectToggle,
  } = useAssetActions<T>();

  const {
    editingAssetId,
    editedName,
    isAssetFavorited,
    isAssetSelected,
    isRenaming,
    renamingAssetId,
  } = useAssetEditingState();

  // Memoize sorted results to prevent video player unmount/remount
  const sortedResults = React.useMemo(
    () => sortAssets(results, sorting, columns),
    [results, sorting, columns]
  );

  const isConfidenceFiltered =
    isSemantic &&
    !hideConfidenceSlider &&
    confidenceThreshold > 0 &&
    !!originalResults &&
    results.length !== originalResults.length;

  // Build sort options: standard sortable columns + selected custom metadata fields
  const customSortOptions = React.useMemo(() => {
    if (!selectedSearchFields || !availableFields || selectedSearchFields.length === 0) return [];
    // IDs already covered by standard columns
    const standardColumnIds = new Set(columns.map((col) => col.id));
    // Known API field names that map to standard columns
    const knownApiFields = new Set([
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
    ]);
    return selectedSearchFields
      .filter((f) => !knownApiFields.has(f) && !standardColumnIds.has(f))
      .map((fieldPath) => ({
        id: fieldPath,
        label:
          availableFields.find((af) => af.name === fieldPath)?.displayName ??
          fieldPath.split(".").at(-1) ??
          fieldPath,
      }));
  }, [selectedSearchFields, availableFields, columns]);

  // Shared controls props (used in both error and success paths)
  const controlsProps = {
    viewMode,
    onViewModeChange,
    title: "" as const,
    sorting,
    sortOptions: [
      ...columns.filter((col) => col.sortable).map((col) => ({ id: col.id, label: col.label })),
      ...customSortOptions,
    ],
    onSortChange: (columnId: string) => {
      const currentSort = sorting[0];
      const desc = currentSort?.id === columnId ? !currentSort.desc : false;
      onSortChange([{ id: columnId, desc }]);
    },
    fields:
      viewMode === "card"
        ? cardFields
        : columns.map((col) => ({ id: col.id, label: col.label, visible: col.visible })),
    onFieldToggle: viewMode === "card" ? onCardFieldToggle : onColumnToggle,
    groupByType,
    onGroupByTypeChange,
    cardSize,
    onCardSizeChange,
    aspectRatio,
    onAspectRatioChange,
    thumbnailScale,
    onThumbnailScaleChange,
    showMetadata,
    onShowMetadataChange,
    hasSelectedAssets,
    selectAllState,
    onSelectAllToggle,
    availableFields,
    selectedSearchFields,
    onSelectedFieldsChange,
  };

  if (error) {
    return (
      <Box>
        <Box sx={{ mb: 4 }}>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontWeight: 700,
              mb: 1,
              background: (theme) =>
                `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              color: "transparent",
            }}
          >
            {title}
          </Typography>
        </Box>
        <AssetViewControls {...controlsProps} />
        <ErrorDisplay
          title={t("search.results.error")}
          message={t("search.results.errorMessage")}
          detailedMessage={error.message}
        />
      </Box>
    );
  }

  return (
    <Box>
      {isLoading && (
        <LinearProgress
          sx={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: zIndexTokens.overlay }}
        />
      )}
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            mb: 2,
            flexWrap: "wrap",
            gap: 2,
          }}
        >
          <Box>
            <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "primary.main" }}>
              {title}
            </Typography>
            {searchMetadata?.totalResults > 0 && searchTerm && (
              <Typography variant="body1" sx={{ color: "text.secondary", mt: 0.5 }}>
                {t("search.results.found", {
                  count: isConfidenceFiltered ? results.length : searchMetadata.totalResults,
                  term: searchTerm,
                })}
              </Typography>
            )}
          </Box>

          {isSemantic && !hideConfidenceSlider && (
            <ConfidenceSlider
              value={confidenceThreshold}
              modelVersion={detectedModelVersion}
              onChange={() => {}}
              onChangeCommitted={(value) => onConfidenceThresholdChange?.(value)}
            />
          )}
        </Box>
      </Box>

      <AssetViewControls {...controlsProps} />

      {viewMode === "card" ? (
        <AssetGridView
          results={sortedResults}
          groupByType={groupByType}
          cardSize={cardSize}
          aspectRatio={aspectRatio}
          thumbnailScale={thumbnailScale}
          showMetadata={showMetadata}
          cardFields={cardFields.filter((f) => f.visible)}
          selectedSearchFields={selectedSearchFields}
        />
      ) : (
        <AssetTableView
          results={sortedResults}
          columns={columns}
          sorting={sorting}
          onSortChange={onSortChange}
          groupByType={groupByType}
          onAssetClick={onAssetClick}
          onDeleteClick={onDeleteClick}
          onDownloadClick={onDownloadClick}
          onAddToCollectionClick={onAddToCollectionClick}
          showRemoveButton={showRemoveButton}
          onEditClick={onEditClick}
          onEditNameChange={onEditNameChange}
          onEditNameComplete={onEditNameComplete}
          editingAssetId={editingAssetId}
          editedName={editedName}
          getAssetId={getAssetId}
          getAssetName={getAssetName}
          getAssetType={getAssetType}
          getAssetThumbnail={getAssetThumbnail}
          isSelected={isAssetSelected ? (asset) => isAssetSelected(getAssetId(asset)) : undefined}
          onSelectToggle={onSelectToggle}
          isFavorite={isAssetFavorited ? (asset) => isAssetFavorited(getAssetId(asset)) : undefined}
          onFavoriteToggle={onFavoriteToggle}
          selectedSearchFields={selectedSearchFields}
          availableFields={availableFields}
          isRenaming={isRenaming}
          renamingAssetId={renamingAssetId}
        />
      )}

      <AssetPagination
        page={searchMetadata.page}
        pageSize={searchMetadata.pageSize}
        totalResults={isConfidenceFiltered ? results.length : searchMetadata.totalResults}
        onPageChange={(_, page) => onPageChange(page)}
        onPageSizeChange={onPageSizeChange}
        isFiltered={isConfidenceFiltered}
      />
    </Box>
  );
}

export default AssetResultsView;
