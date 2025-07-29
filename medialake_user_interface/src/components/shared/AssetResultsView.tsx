import React from "react";
import { Box, Typography, LinearProgress } from "@mui/material";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import AssetViewControls from "./AssetViewControls";
import AssetPagination from "./AssetPagination";
import AssetGridView from "./AssetGridView";
import AssetTableView from "./AssetTableView";
import ErrorDisplay from "./ErrorDisplay";

export interface AssetField {
  id: string;
  label: string;
  visible: boolean;
}

export interface AssetResultsViewProps<T> {
  results: T[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
  searchTerm?: string;
  title?: string;

  // Search fields
  selectedFields?: string[];
  availableFields?: Array<{
    name: string;
    displayName: string;
    description: string;
    type: string;
    isDefault: boolean;
  }>;
  onFieldsChange?: (event: any) => void;

  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  viewMode: "card" | "table";
  onViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
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
  // Asset action handlers
  onAssetClick: (asset: T) => void;
  onDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: T, save: boolean, value?: string) => void;
  editingAssetId?: string;
  editedName?: string;
  // Favorite functionality
  isAssetFavorited?: (assetId: string) => boolean;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  // Selection functionality
  isAssetSelected?: (assetId: string) => boolean;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  // Select all functionality
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;
  error?: { status: string; message: string } | null;
  isLoading?: boolean;
  isRenaming?: boolean; // Add isRenaming prop for loading state
  renamingAssetId?: string; // ID of the asset currently being renamed
  // Functions to extract data from asset objects
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  getAssetProxy?: (asset: T) => string;
  renderCardField: (fieldId: string, asset: T) => React.ReactNode;
}

function AssetResultsView<T>({
  results,
  searchMetadata,
  onPageChange,
  onPageSizeChange,
  searchTerm,
  title = "Results",
  // Search fields
  selectedFields,
  availableFields,
  onFieldsChange,
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
  onAssetClick,
  onDeleteClick,
  onDownloadClick,
  onEditClick,
  onEditNameChange,
  onEditNameComplete,
  editingAssetId,
  editedName,
  isAssetFavorited,
  onFavoriteToggle,
  isAssetSelected,
  onSelectToggle,
  // Select all functionality
  hasSelectedAssets,
  selectAllState,
  onSelectAllToggle,
  error,
  isLoading,
  isRenaming,
  renamingAssetId,
  getAssetId,
  getAssetName,
  getAssetType,
  getAssetThumbnail,
  getAssetProxy,
  renderCardField,
}: AssetResultsViewProps<T>) {
  // If there's an error, display the error component
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

        <AssetViewControls
          viewMode={viewMode}
          onViewModeChange={onViewModeChange}
          title=""
          sorting={sorting}
          sortOptions={columns
            .filter((col) => col.sortable)
            .map((col) => ({
              id: col.id,
              label: col.label,
            }))}
          onSortChange={(columnId) => {
            const currentSort = sorting[0];
            const desc =
              currentSort?.id === columnId ? !currentSort.desc : false;
            onSortChange([{ id: columnId, desc }]);
          }}
          fields={
            viewMode === "card"
              ? cardFields
              : columns.map((col) => ({
                  id: col.id,
                  label: col.label,
                  visible: col.visible,
                }))
          }
          onFieldToggle={
            viewMode === "card" ? onCardFieldToggle : onColumnToggle
          }
          selectedFields={selectedFields}
          availableFields={availableFields}
          onFieldsChange={onFieldsChange}
          groupByType={groupByType}
          onGroupByTypeChange={onGroupByTypeChange}
          cardSize={cardSize}
          onCardSizeChange={onCardSizeChange}
          aspectRatio={aspectRatio}
          onAspectRatioChange={onAspectRatioChange}
          thumbnailScale={thumbnailScale}
          onThumbnailScaleChange={onThumbnailScaleChange}
          showMetadata={showMetadata}
          onShowMetadataChange={onShowMetadataChange}
          hasSelectedAssets={hasSelectedAssets}
          selectAllState={selectAllState}
          onSelectAllToggle={onSelectAllToggle}
        />

        <ErrorDisplay
          title="Error"
          message="There was a problem retrieving content."
          detailedMessage={error.message}
        />
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 1 }}>
      {" "}
      {/* Changed from -2 to 1 to move the view controller down */}
      {isLoading && (
        <LinearProgress
          sx={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
          }}
        />
      )}
      <Box sx={{ mb: 2 }}>
        <Typography
          variant="h4"
          component="h1"
          sx={{
            fontWeight: 700,
            background: (theme) =>
              `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            color: "transparent",
            display: "block",
            visibility: "visible",
            position: "relative",
            zIndex: 1,
          }}
        >
          {title}{" "}
          {searchMetadata?.totalResults > 0 && searchTerm && (
            <Typography
              component="span"
              sx={{
                fontWeight: 300,
                fontSize: "0.5em",
                color: "text.secondary",
                opacity: 0.75,
              }}
            >
              (Found {searchMetadata.totalResults} results for "{searchTerm}")
            </Typography>
          )}
        </Typography>
      </Box>
      <AssetViewControls
        viewMode={viewMode}
        onViewModeChange={onViewModeChange}
        title=""
        sorting={sorting}
        sortOptions={columns
          .filter((col) => col.sortable)
          .map((col) => ({
            id: col.id,
            label: col.label,
          }))}
        onSortChange={(columnId) => {
          const currentSort = sorting[0];
          const desc = currentSort?.id === columnId ? !currentSort.desc : false;
          onSortChange([{ id: columnId, desc }]);
        }}
        fields={
          viewMode === "card"
            ? cardFields
            : columns.map((col) => ({
                id: col.id,
                label: col.label,
                visible: col.visible,
              }))
        }
        onFieldToggle={viewMode === "card" ? onCardFieldToggle : onColumnToggle}
        selectedFields={selectedFields}
        availableFields={availableFields}
        onFieldsChange={onFieldsChange}
        groupByType={groupByType}
        onGroupByTypeChange={onGroupByTypeChange}
        cardSize={cardSize}
        onCardSizeChange={onCardSizeChange}
        aspectRatio={aspectRatio}
        onAspectRatioChange={onAspectRatioChange}
        thumbnailScale={thumbnailScale}
        onThumbnailScaleChange={onThumbnailScaleChange}
        showMetadata={showMetadata}
        onShowMetadataChange={onShowMetadataChange}
        hasSelectedAssets={hasSelectedAssets}
        selectAllState={selectAllState}
        onSelectAllToggle={onSelectAllToggle}
      />
      {/* Sort the results based on the current sorting state */}
      {(() => {
        // Sort the results if sorting is specified
        const sortedResults = [...results];
        if (sorting.length > 0) {
          const { id: sortField, desc } = sorting[0];
          sortedResults.sort((a, b) => {
            let valueA, valueB;

            // Get values based on field ID
            switch (sortField) {
              case "name":
                valueA = getAssetName(a);
                valueB = getAssetName(b);
                break;
              case "type":
                valueA = getAssetType(a);
                valueB = getAssetType(b);
                break;
              case "size":
                // Assuming there's a way to get size from the asset
                const sizeFieldA = a as any;
                const sizeFieldB = b as any;
                valueA =
                  sizeFieldA?.DigitalSourceAsset?.MainRepresentation
                    ?.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 0;
                valueB =
                  sizeFieldB?.DigitalSourceAsset?.MainRepresentation
                    ?.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 0;
                break;
              case "date":
                // Assuming there's a way to get date from the asset
                const dateFieldA = a as any;
                const dateFieldB = b as any;
                valueA = dateFieldA?.DigitalSourceAsset?.CreateDate
                  ? new Date(dateFieldA.DigitalSourceAsset.CreateDate).getTime()
                  : 0;
                valueB = dateFieldB?.DigitalSourceAsset?.CreateDate
                  ? new Date(dateFieldB.DigitalSourceAsset.CreateDate).getTime()
                  : 0;
                break;
              default:
                valueA = (a as any)[sortField];
                valueB = (b as any)[sortField];
            }

            // Compare values
            if (valueA === valueB) return 0;

            // Handle string comparison
            if (typeof valueA === "string" && typeof valueB === "string") {
              return desc
                ? valueB.localeCompare(valueA)
                : valueA.localeCompare(valueB);
            }

            // Handle number comparison
            return desc ? valueB - valueA : valueA - valueB;
          });
        }

        // Return the appropriate view based on viewMode
        return viewMode === "card" ? (
          <AssetGridView
            results={sortedResults}
            groupByType={groupByType}
            cardSize={cardSize}
            aspectRatio={aspectRatio}
            thumbnailScale={thumbnailScale}
            showMetadata={showMetadata}
            cardFields={cardFields.filter((f) => f.visible)}
            onAssetClick={onAssetClick}
            onDeleteClick={onDeleteClick}
            onDownloadClick={onDownloadClick}
            onEditClick={onEditClick}
            onEditNameChange={onEditNameChange}
            onEditNameComplete={onEditNameComplete}
            editingAssetId={editingAssetId}
            editedName={editedName}
            isAssetFavorited={isAssetFavorited}
            onFavoriteToggle={onFavoriteToggle}
            isAssetSelected={isAssetSelected}
            onSelectToggle={onSelectToggle}
            getAssetId={getAssetId}
            getAssetName={getAssetName}
            getAssetType={getAssetType}
            getAssetThumbnail={getAssetThumbnail}
            getAssetProxy={getAssetProxy}
            renderCardField={renderCardField}
            selectedSearchFields={selectedFields}
            isRenaming={isRenaming}
            renamingAssetId={renamingAssetId}
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
            onEditClick={onEditClick}
            onEditNameChange={onEditNameChange}
            onEditNameComplete={onEditNameComplete}
            editingAssetId={editingAssetId}
            editedName={editedName}
            getAssetId={getAssetId}
            getAssetName={getAssetName}
            getAssetType={getAssetType}
            getAssetThumbnail={getAssetThumbnail}
            isSelected={
              isAssetSelected
                ? (asset) => isAssetSelected(getAssetId(asset))
                : undefined
            }
            onSelectToggle={onSelectToggle}
            isFavorite={
              isAssetFavorited
                ? (asset) => isAssetFavorited(getAssetId(asset))
                : undefined
            }
            onFavoriteToggle={onFavoriteToggle}
            selectedSearchFields={selectedFields}
            isRenaming={isRenaming}
            renamingAssetId={renamingAssetId}
          />
        );
      })()}
      <AssetPagination
        page={searchMetadata.page}
        pageSize={searchMetadata.pageSize}
        totalResults={searchMetadata.totalResults}
        onPageChange={(_, page) => onPageChange(page)}
        onPageSizeChange={onPageSizeChange}
      />
    </Box>
  );
}

export default AssetResultsView;
