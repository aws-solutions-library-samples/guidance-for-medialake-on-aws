import React from "react";
import { Box, Grid, Typography } from "@mui/material";
import AssetCard, { AssetField } from "./AssetCard";

interface AssetGridViewProps<T> {
  results: T[];
  groupByType: boolean;
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
  cardFields: AssetField[];
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
  // Functions to extract data from asset objects
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  getAssetProxy?: (asset: T) => string;
  renderCardField: (fieldId: string, asset: T) => React.ReactNode;
  // Search fields
  selectedSearchFields?: string[];
  isRenaming?: boolean; // Add isRenaming prop for loading state
  renamingAssetId?: string; // ID of the asset currently being renamed
}

function AssetGridView<T>({
  results,
  groupByType,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  cardFields,
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
  getAssetId,
  getAssetName,
  getAssetType,
  getAssetThumbnail,
  getAssetProxy,
  renderCardField,
  selectedSearchFields,
  isRenaming,
  renamingAssetId,
}: AssetGridViewProps<T>) {
  // Group results by type if needed
  const groupedResults = React.useMemo(() => {
    if (!groupByType) return { all: results };

    return results.reduce(
      (acc, item) => {
        const type = getAssetType(item).toLowerCase();
        const normalizedType =
          type === "image"
            ? "Image"
            : type === "video"
              ? "Video"
              : type === "audio"
                ? "Audio"
                : "Other";

        if (!acc[normalizedType]) acc[normalizedType] = [];
        acc[normalizedType].push(item);
        return acc;
      },
      {} as Record<string, T[]>,
    );
  }, [results, groupByType, getAssetType]);

  const getGridSizes = () => {
    switch (cardSize) {
      case "small":
        return { xs: 12, sm: 6, md: 3, lg: 2 };
      case "large":
        return { xs: 12, sm: 12, md: 6, lg: 4 };
      default: // medium
        return { xs: 12, sm: 6, md: 4, lg: 3 };
    }
  };

  if (!groupByType) {
    return (
      <Grid container spacing={3}>
        {results.map((asset) => (
          <Grid item {...getGridSizes()} key={getAssetId(asset)}>
            <AssetCard
              id={getAssetId(asset)}
              name={getAssetName(asset)}
              thumbnailUrl={getAssetThumbnail(asset)}
              proxyUrl={getAssetProxy ? getAssetProxy(asset) : undefined}
              assetType={getAssetType(asset)}
              fields={cardFields}
              renderField={(fieldId) => renderCardField(fieldId, asset)}
              onAssetClick={() => onAssetClick(asset)}
              onDeleteClick={(e) => onDeleteClick(asset, e)}
              onDownloadClick={(e) => onDownloadClick(asset, e)}
              onEditClick={(e) => onEditClick(asset, e)}
              isEditing={editingAssetId === getAssetId(asset)}
              editedName={editedName}
              onEditNameChange={onEditNameChange}
              onEditNameComplete={(save, value) =>
                onEditNameComplete(asset, save, value)
              }
              cardSize={cardSize}
              aspectRatio={aspectRatio}
              thumbnailScale={thumbnailScale}
              showMetadata={showMetadata}
              isFavorite={
                isAssetFavorited ? isAssetFavorited(getAssetId(asset)) : false
              }
              onFavoriteToggle={
                onFavoriteToggle ? (e) => onFavoriteToggle(asset, e) : undefined
              }
              isSelected={
                isAssetSelected ? isAssetSelected(getAssetId(asset)) : false
              }
              onSelectToggle={
                onSelectToggle ? (id, e) => onSelectToggle(asset, e) : undefined
              }
              selectedSearchFields={selectedSearchFields}
              isRenaming={isRenaming && renamingAssetId === getAssetId(asset)}
            />
          </Grid>
        ))}
      </Grid>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Object.entries(groupedResults).map(
        ([type, assets]) =>
          assets.length > 0 && (
            <Box key={type}>
              <Typography
                variant="h6"
                sx={{
                  mb: 2,
                  px: 1,
                  background: (theme) =>
                    `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                  backgroundClip: "text",
                  WebkitBackgroundClip: "text",
                  color: "transparent",
                  fontWeight: 600,
                }}
              >
                {type}
              </Typography>
              <Grid container spacing={3}>
                {assets.map((asset) => (
                  <Grid item {...getGridSizes()} key={getAssetId(asset)}>
                    <AssetCard
                      id={getAssetId(asset)}
                      name={getAssetName(asset)}
                      thumbnailUrl={getAssetThumbnail(asset)}
                      proxyUrl={
                        getAssetProxy ? getAssetProxy(asset) : undefined
                      }
                      assetType={getAssetType(asset)}
                      fields={cardFields}
                      renderField={(fieldId) => renderCardField(fieldId, asset)}
                      onAssetClick={() => onAssetClick(asset)}
                      onDeleteClick={(e) => onDeleteClick(asset, e)}
                      onDownloadClick={(e) => onDownloadClick(asset, e)}
                      onEditClick={(e) => onEditClick(asset, e)}
                      isEditing={editingAssetId === getAssetId(asset)}
                      editedName={editedName}
                      onEditNameChange={onEditNameChange}
                      onEditNameComplete={(save, value) =>
                        onEditNameComplete(asset, save, value)
                      }
                      cardSize={cardSize}
                      aspectRatio={aspectRatio}
                      thumbnailScale={thumbnailScale}
                      showMetadata={showMetadata}
                      isFavorite={
                        isAssetFavorited
                          ? isAssetFavorited(getAssetId(asset))
                          : false
                      }
                      onFavoriteToggle={
                        onFavoriteToggle
                          ? (e) => onFavoriteToggle(asset, e)
                          : undefined
                      }
                      isSelected={
                        isAssetSelected
                          ? isAssetSelected(getAssetId(asset))
                          : false
                      }
                      onSelectToggle={
                        onSelectToggle
                          ? (id, e) => onSelectToggle(asset, e)
                          : undefined
                      }
                      selectedSearchFields={selectedSearchFields}
                      isRenaming={
                        isRenaming && renamingAssetId === getAssetId(asset)
                      }
                    />
                  </Grid>
                ))}
              </Grid>
            </Box>
          ),
      )}
    </Box>
  );
}

export default AssetGridView;
