import React from "react";
import { Box, Typography } from "@mui/material";
import { type SortingState } from "@tanstack/react-table";
import { AssetTable } from "./AssetTable";
import { type FieldInfo } from "@/api/hooks/useSearchFields";
import { groupAssetsByType } from "@/utils/groupAssetsByType";

interface AssetTableViewProps<T> {
  results: T[];
  columns: any[];
  sorting: SortingState;
  onSortChange: (sorting: SortingState) => void;
  groupByType: boolean;
  onAssetClick: (asset: T) => void;
  onDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  showRemoveButton?: boolean;
  onEditClick?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (asset: T, save: boolean, value?: string) => void;
  editingAssetId?: string;
  editedName?: string;
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  /**
   * Display-only name override. Defaults to `getAssetName`. Kept separate because
   * `getAssetName` is also the value fed to bin/favorites records and rename flows, so
   * pages that want a decorated label (e.g. a clip's timecode range) must not change it.
   */
  getAssetDisplayName?: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  isSelected?: (asset: T) => boolean;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  isFavorite?: (asset: T) => boolean;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  selectedSearchFields?: string[];
  availableFields?: FieldInfo[];
  isRenaming?: boolean;
  renamingAssetId?: string;
  canDelete?: boolean;
}

function AssetTableView<T>({
  results,
  columns,
  sorting,
  onSortChange,
  groupByType,
  onAssetClick,
  onDeleteClick,
  onDownloadClick,
  onAddToCollectionClick,
  showRemoveButton = false,
  onEditClick,
  onEditNameChange,
  onEditNameComplete,
  editingAssetId,
  editedName,
  getAssetId,
  getAssetName,
  getAssetDisplayName,
  getAssetType,
  getAssetThumbnail,
  isSelected,
  onSelectToggle,
  isFavorite,
  onFavoriteToggle,
  selectedSearchFields,
  availableFields,
  isRenaming,
  renamingAssetId,
  canDelete = true,
}: AssetTableViewProps<T>) {
  // Group results by type if needed
  const groupedResults = React.useMemo(() => {
    if (!groupByType) return {};
    return groupAssetsByType(results, getAssetType);
  }, [results, groupByType, getAssetType]);

  if (!groupByType) {
    return (
      <AssetTable
        data={results}
        columns={columns}
        sorting={sorting}
        onSortingChange={onSortChange}
        onDeleteClick={onDeleteClick}
        onDownloadClick={onDownloadClick}
        onAddToCollectionClick={onAddToCollectionClick}
        showRemoveButton={showRemoveButton}
        onEditClick={onEditClick}
        onAssetClick={onAssetClick}
        getThumbnailUrl={getAssetThumbnail}
        getName={getAssetDisplayName ?? getAssetName}
        getId={getAssetId}
        getAssetType={getAssetType}
        editingId={editingAssetId}
        editedName={editedName}
        onEditNameChange={onEditNameChange}
        onEditNameComplete={onEditNameComplete}
        isSelected={isSelected}
        onSelectToggle={onSelectToggle}
        isFavorite={isFavorite}
        onFavoriteToggle={onFavoriteToggle}
        selectedSearchFields={selectedSearchFields}
        availableFields={availableFields}
        isRenaming={isRenaming}
        renamingAssetId={renamingAssetId}
        canDelete={canDelete}
      />
    );
  }

  return (
    <React.Fragment>
      {Object.entries(groupedResults)
        .filter(([type]) => groupedResults[type].length > 0)
        .map(([type, assets]) => (
          <Box key={type} sx={{ mb: "2rem" }}>
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
            <AssetTable<T>
              data={assets}
              columns={columns}
              sorting={sorting}
              onSortingChange={onSortChange}
              onDeleteClick={onDeleteClick}
              onDownloadClick={onDownloadClick}
              onAddToCollectionClick={onAddToCollectionClick}
              showRemoveButton={showRemoveButton}
              onEditClick={onEditClick}
              onAssetClick={onAssetClick}
              getThumbnailUrl={getAssetThumbnail}
              getName={getAssetDisplayName ?? getAssetName}
              getId={getAssetId}
              getAssetType={getAssetType}
              editingId={editingAssetId}
              editedName={editedName}
              onEditNameChange={onEditNameChange}
              onEditNameComplete={onEditNameComplete}
              isSelected={isSelected}
              onSelectToggle={onSelectToggle}
              isFavorite={isFavorite}
              onFavoriteToggle={onFavoriteToggle}
              selectedSearchFields={selectedSearchFields}
              availableFields={availableFields}
              isRenaming={isRenaming}
              renamingAssetId={renamingAssetId}
              canDelete={canDelete}
            />
          </Box>
        ))}
    </React.Fragment>
  );
}

export default AssetTableView;
