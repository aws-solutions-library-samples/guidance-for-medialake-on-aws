import React from "react";
import { type SortingState } from "@tanstack/react-table";
import { AssetTable } from "./AssetTable";

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
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  isSelected?: (asset: T) => boolean;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  isFavorite?: (asset: T) => boolean;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  selectedSearchFields?: string[];
  isRenaming?: boolean;
  renamingAssetId?: string;
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
  getAssetType,
  getAssetThumbnail,
  isSelected,
  onSelectToggle,
  isFavorite,
  onFavoriteToggle,
  selectedSearchFields,
  isRenaming,
  renamingAssetId,
}: AssetTableViewProps<T>) {
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
      {} as Record<string, T[]>
    );
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
        getName={getAssetName}
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
        isRenaming={isRenaming}
        renamingAssetId={renamingAssetId}
      />
    );
  }

  return (
    <React.Fragment>
      {Object.entries(groupedResults)
        .filter(
          ([type]) => ["Image", "Video", "Audio"].includes(type) && groupedResults[type].length > 0
        )
        .map(([type, assets]) => (
          <div key={type} style={{ marginBottom: "2rem" }}>
            <h3
              style={{
                marginBottom: "1rem",
                background: "linear-gradient(45deg, #1976d2, #9c27b0)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                fontWeight: 600,
              }}
            >
              {type}
            </h3>
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
              getName={getAssetName}
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
              isRenaming={isRenaming}
              renamingAssetId={renamingAssetId}
            />
          </div>
        ))}
    </React.Fragment>
  );
}

export default AssetTableView;
