import React from 'react';
import { Box, Typography } from '@mui/material';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import { AssetTable } from './AssetTable';

interface AssetTableViewProps<T> {
  results: T[];
  columns: AssetTableColumn<T>[];
  sorting: SortingState;
  onSortChange: (sorting: SortingState) => void;
  groupByType: boolean;
  onAssetClick: (asset: T) => void;
  onDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: T, save: boolean) => void;
  editingAssetId?: string;
  editedName?: string;
  // Functions to extract data from asset objects
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  // Selection and favorite handlers
  isSelected?: (asset: T) => boolean;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  isFavorite?: (asset: T) => boolean;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
}

function AssetTableView<T>({
  results,
  columns,
  sorting,
  onSortChange,
  groupByType,
  onAssetClick,
  onDeleteClick,
  onMenuClick,
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
}: AssetTableViewProps<T>) {
  // Group results by type if needed
  const groupedResults = React.useMemo(() => {
    if (!groupByType) return { all: results };

    return results.reduce((acc, item) => {
      const type = getAssetType(item).toLowerCase();
      const normalizedType = type === 'image' ? 'Image' :
                           type === 'video' ? 'Video' :
                           type === 'audio' ? 'Audio' : 'Other';
      
      if (!acc[normalizedType]) acc[normalizedType] = [];
      acc[normalizedType].push(item);
      return acc;
    }, {} as Record<string, T[]>);
  }, [results, groupByType, getAssetType]);

  if (groupByType) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Object.entries(groupedResults)
          .filter(([type, assets]) => assets.length > 0)
          .map(([type, assets]) => (
            <Box key={type}>
              <Typography variant="h6" sx={{ 
                mb: 2, 
                px: 1, 
                background: theme => `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                fontWeight: 600
              }}>
                {type}
              </Typography>
              <AssetTable
                data={assets}
                columns={columns}
                sorting={sorting}
                onSortingChange={onSortChange}
                onDeleteClick={onDeleteClick}
                onMenuClick={onMenuClick}
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
              />
            </Box>
          ))}
      </Box>
    );
  }

  // Non-grouped table view
  return (
    <AssetTable
      data={results}
      columns={columns}
      sorting={sorting}
      onSortingChange={onSortChange}
      onDeleteClick={onDeleteClick}
      onMenuClick={onMenuClick}
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
    />
  );
}

export default AssetTableView;
