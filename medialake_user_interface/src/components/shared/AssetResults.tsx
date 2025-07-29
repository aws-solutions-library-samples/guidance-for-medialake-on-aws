import React, { useState, useMemo } from "react";
import { Box, Grid, Paper, Typography, Snackbar, Alert } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { ConfirmationModal } from "../common/ConfirmationModal";
import { RenameDialog } from "../common/RenameDialog";
import {
  type AssetBase,
  type CardFieldConfig,
} from "@/types/search/searchResults";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import AssetCard from "./AssetCard";
import AssetTable from "./AssetTable";
import AssetViewControls from "./AssetViewControls";
import { PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";
import AssetPagination from "./AssetPagination";
import AssetActionsMenu from "./AssetActionsMenu";
import { useAssetResults } from "@/hooks/useAssetResults";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { sortAssets } from "@/utils/sortAssets";
import { type AssetViewControlsProps } from "@/types/shared/assetComponents";

export interface AssetResultsConfig<T extends AssetBase> {
  assetType: string;
  defaultCardFields: CardFieldConfig[];
  defaultColumns: AssetTableColumn<T>[];
  sortOptions: { id: string; label: string }[];
  renderCardField: (fieldId: string, asset: T) => string;
  placeholderImage?: string;
}

interface AssetResultsProps<T extends AssetBase> {
  assets: T[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  config: AssetResultsConfig<T>;
  searchTerm: string;
  actions?: Array<{
    id: string;
    label: string;
  }>;
  cardSize: "small" | "medium" | "large";
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  aspectRatio: "vertical" | "square" | "horizontal";
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

type AssetWithHeader<T> = T | { isHeader: true; type: string };

function AssetResults<T extends AssetBase>({
  assets,
  searchMetadata,
  onPageChange,
  config,
  searchTerm,
  actions,
  cardSize = "medium",
  onCardSizeChange,
  aspectRatio = "square",
  onAspectRatioChange,
  thumbnailScale = "fill",
  onThumbnailScaleChange,
  showMetadata = true,
  onShowMetadataChange,
  onPageSizeChange,
}: AssetResultsProps<T>) {
  const navigate = useNavigate();
  const [currentAsset, setCurrentAsset] = useState<T | null>(null);
  const [columnFilters, setColumnFilters] = useState<
    Array<{ columnId: string; value: string }>
  >([]);
  const [groupByType, setGroupByType] = useState(true);

  const {
    assetType,
    defaultCardFields,
    defaultColumns,
    sortOptions,
    renderCardField,
    placeholderImage = PLACEHOLDER_IMAGE,
  } = config;

  // Initialize asset results state and handlers
  const {
    viewMode,
    sorting,
    setSorting,
    page,
    cardFields,
    columns,
    failedAssets,
    handleViewModeChange,
    handleRequestSort,
    handlePageChange,
    handleCardFieldToggle,
    handleColumnToggle,
    handleAssetError,
  } = useAssetResults<T>({
    assets,
    searchMetadata,
    onPageChange,
    defaultCardFields,
    defaultColumns,
  });

  // Group and sort assets
  const displayedAssets = useMemo(() => {
    let result = [...assets];

    // Apply sorting first
    result = sortAssets(result, sorting);

    // Apply grouping if enabled
    if (groupByType) {
      // Group by format
      const groups = result.reduce(
        (acc, asset) => {
          const format =
            asset.DigitalSourceAsset.MainRepresentation.Format.toLowerCase();
          if (!acc[format]) {
            acc[format] = [];
          }
          acc[format].push(asset);
          return acc;
        },
        {} as Record<string, T[]>,
      );

      // Convert groups back to array, maintaining format-based ordering
      result = Object.entries(groups)
        .sort(([formatA], [formatB]) => formatA.localeCompare(formatB))
        .flatMap(([_, assets]) => assets);
    }

    return result;
  }, [assets, groupByType, sorting]);

  // Add section headers for grouped view
  const assetsWithHeaders = useMemo(() => {
    if (!groupByType) return displayedAssets;

    const result: AssetWithHeader<T>[] = [];
    let currentFormat = "";

    displayedAssets.forEach((asset) => {
      const format =
        asset.DigitalSourceAsset.MainRepresentation.Format.toLowerCase();
      if (format !== currentFormat) {
        result.push({ isHeader: true, type: format });
        currentFormat = format;
      }
      result.push(asset);
    });

    return result;
  }, [displayedAssets, groupByType]);

  const {
    selectedAsset,
    menuAnchorEl,
    isDeleteModalOpen,
    assetToDelete,
    editingAssetId,
    editedName,
    isRenameDialogOpen,
    alert,
    handleMenuOpen,
    handleMenuClose,
    handleAction,
    handleDeleteClick,
    handleDeleteConfirm,
    handleStartEditing,
    handleNameChange,
    handleNameEditComplete,
    handleRenameConfirm,
    handleDeleteCancel,
    handleRenameCancel,
    handleAlertClose,
    isLoading,
  } = useAssetOperations<T>();

  const handleNavigationPageChange = (newPage: number) => {
    handlePageChange({} as React.ChangeEvent<unknown>, newPage);
  };

  const handleAssetClick = (asset: T) => {
    const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
    navigate(
      `/${assetType}s/${asset.InventoryID}${
        searchTerm ? `?searchTerm=${encodeURIComponent(searchTerm)}` : ""
      }`,
    );
  };

  const handleFilterClick = (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => {
    const value = window.prompt(`Enter filter value for ${columnId}`);
    if (value) {
      setColumnFilters((prev) => [
        ...prev.filter((f) => f.columnId !== columnId),
        { columnId, value },
      ]);
    }
  };

  const handleRemoveFilter = (columnId: string) => {
    setColumnFilters((prev) => prev.filter((f) => f.columnId !== columnId));
  };

  const renderAsset = (asset: T) => (
    <Grid item xs={12} sm={6} md={4} lg={3} key={asset.InventoryID}>
      <AssetCard
        id={asset.InventoryID}
        name={
          asset.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.ObjectKey.Name
        }
        thumbnailUrl={asset.thumbnailUrl}
        proxyUrl={asset.proxyUrl}
        assetType={assetType}
        fields={cardFields}
        renderField={(fieldId) => renderCardField(fieldId, asset)}
        onAssetClick={() => handleAssetClick(asset)}
        onDeleteClick={(e) => handleDeleteClick(asset, e)}
        onDownloadClick={(e) => handleMenuOpen(asset, e)}
        onEditClick={(e) => handleStartEditing(asset, e)}
        onImageError={handleAssetError}
        isEditing={editingAssetId === asset.InventoryID}
        isRenaming={isLoading.rename && editingAssetId === asset.InventoryID}
        editedName={editedName}
        onEditNameChange={handleNameChange}
        onEditNameComplete={(save, value) => {
          console.log(
            "🎯 AssetResults onEditNameComplete - save:",
            save,
            "value:",
            value,
          );
          console.log(
            "🎯 AssetResults calling handleNameEditComplete with asset:",
            asset.InventoryID,
            "save:",
            save,
            "value:",
            value,
          );
          handleNameEditComplete(asset, save, value);
        }}
        isFavorite={false} // Default to false since we don't have favorite info here
        onFavoriteToggle={(e) =>
          console.log("Favorite toggle not implemented in AssetResults")
        }
      />
    </Grid>
  );

  return (
    <Paper
      elevation={0}
      sx={{
        bgcolor: "transparent", // Make background transparent
        // Remove any padding if present
        p: 0,
      }}
    >
      <Box>
        <AssetViewControls
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
          title={assetType}
          sorting={sorting}
          sortOptions={sortOptions}
          onSortChange={handleRequestSort}
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
            viewMode === "card" ? handleCardFieldToggle : handleColumnToggle
          }
          groupByType={groupByType}
          onGroupByTypeChange={setGroupByType}
          cardSize={cardSize}
          onCardSizeChange={onCardSizeChange}
          aspectRatio={aspectRatio}
          onAspectRatioChange={onAspectRatioChange}
          thumbnailScale={thumbnailScale}
          onThumbnailScaleChange={onThumbnailScaleChange}
          showMetadata={showMetadata}
          onShowMetadataChange={onShowMetadataChange}
        />

        {viewMode === "card" ? (
          <Box>
            {groupByType ? (
              assetsWithHeaders.map((item, index) => {
                if ("isHeader" in item) {
                  return (
                    <Box
                      key={`header-${item.type}`}
                      sx={{
                        mt: index > 0 ? 4 : 0,
                        mb: 2,
                        px: 1,
                        typography: "h6",
                        color: "text.secondary",
                        textTransform: "capitalize",
                      }}
                    >
                      {item.type}
                    </Box>
                  );
                }
                return (
                  <Grid container spacing={3} key={item.InventoryID}>
                    {renderAsset(item)}
                  </Grid>
                );
              })
            ) : (
              <Grid container spacing={3}>
                {displayedAssets.map((asset) => renderAsset(asset))}
              </Grid>
            )}
          </Box>
        ) : (
          <AssetTable<T>
            data={displayedAssets}
            columns={columns}
            sorting={sorting}
            onSortingChange={setSorting}
            onDeleteClick={handleDeleteClick}
            onDownloadClick={handleMenuOpen}
            onEditClick={handleStartEditing}
            onAssetClick={handleAssetClick}
            getThumbnailUrl={(asset) => asset.thumbnailUrl || placeholderImage}
            getName={(asset) =>
              asset.DigitalSourceAsset.MainRepresentation.StorageInfo
                .PrimaryLocation.ObjectKey.Name
            }
            getId={(asset) => asset.InventoryID}
            editingId={editingAssetId}
            editedName={editedName}
            onEditNameChange={handleNameChange}
            onEditNameComplete={(asset, save, value) =>
              handleNameEditComplete(asset, save, value)
            }
            onFilterClick={handleFilterClick}
            activeFilters={columnFilters}
            onRemoveFilter={handleRemoveFilter}
          />
        )}

        <AssetPagination
          page={page}
          pageSize={searchMetadata.pageSize}
          totalResults={searchMetadata.totalResults}
          onPageChange={handlePageChange}
          onPageSizeChange={onPageSizeChange}
        />

        <AssetActionsMenu
          anchorEl={menuAnchorEl}
          selectedAsset={selectedAsset}
          onClose={handleMenuClose}
          onAction={handleAction}
          actions={actions}
          isLoading={isLoading}
        />

        <ConfirmationModal
          open={isDeleteModalOpen}
          title={`Delete ${assetType}`}
          message={`Are you sure you want to delete "${assetToDelete?.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}"? This action cannot be undone.`}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
          confirmText={`Delete ${assetType}`}
          isLoading={isLoading.delete}
        />

        <RenameDialog
          open={isRenameDialogOpen}
          title="Rename Asset"
          currentName={
            selectedAsset?.DigitalSourceAsset.MainRepresentation.StorageInfo
              .PrimaryLocation.ObjectKey.Name || ""
          }
          onConfirm={handleRenameConfirm}
          onCancel={handleRenameCancel}
          isLoading={isLoading.rename}
        />

        <Snackbar
          open={!!alert}
          autoHideDuration={6000}
          onClose={handleAlertClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        >
          <Alert
            onClose={handleAlertClose}
            severity={alert?.severity}
            sx={{ width: "100%" }}
          >
            {alert?.message}
          </Alert>
        </Snackbar>
      </Box>
    </Paper>
  );
}

export default AssetResults;
