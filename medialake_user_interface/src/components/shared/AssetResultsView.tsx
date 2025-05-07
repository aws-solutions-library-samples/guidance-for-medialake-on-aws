import React from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetViewControls from './AssetViewControls';
import AssetPagination from './AssetPagination';
import AssetGridView from './AssetGridView';
import AssetTableView from './AssetTableView';
import ErrorDisplay from './ErrorDisplay';

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
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  viewMode: 'card' | 'table';
  onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
  cardSize: 'small' | 'medium' | 'large';
  onCardSizeChange: (size: 'small' | 'medium' | 'large') => void;
  aspectRatio: 'vertical' | 'square' | 'horizontal';
  onAspectRatioChange: (ratio: 'vertical' | 'square' | 'horizontal') => void;
  thumbnailScale: 'fit' | 'fill';
  onThumbnailScaleChange: (scale: 'fit' | 'fill') => void;
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
  onMenuClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: T, save: boolean) => void;
  editingAssetId?: string;
  editedName?: string;
  // Favorite functionality
  isAssetFavorited?: (assetId: string) => boolean;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  // Selection functionality
  isAssetSelected?: (assetId: string) => boolean;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  error?: { status: string; message: string } | null;
  isLoading?: boolean;
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
  title = 'Results',
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
  onMenuClick,
  onEditClick,
  onEditNameChange,
  onEditNameComplete,
  editingAssetId,
  editedName,
  isAssetFavorited,
  onFavoriteToggle,
  isAssetSelected,
  onSelectToggle,
  error,
  isLoading,
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
              background: theme => `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              color: 'transparent',
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
            .filter(col => col.sortable)
            .map(col => ({
              id: col.id,
              label: col.label
            }))
          }
          onSortChange={(columnId) => {
            const currentSort = sorting[0];
            const desc = currentSort?.id === columnId ? !currentSort.desc : false;
            onSortChange([{ id: columnId, desc }]);
          }}
          fields={viewMode === 'card' 
            ? cardFields 
            : columns.map(col => ({
              id: col.id,
              label: col.label,
              visible: col.visible
            }))}
          onFieldToggle={viewMode === 'card' ? onCardFieldToggle : onColumnToggle}
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
    <Box sx={{ mt: 1 }}>  {/* Changed from -2 to 1 to move the view controller down */}
      {isLoading && (
        <LinearProgress
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999
          }}
        />
      )}

      <Box sx={{ mb: 2 }}>
        <Typography
          variant="h4"
          component="h1"
          sx={{
            fontWeight: 700,
            background: theme => `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            color: 'transparent',
            display: 'block',
            visibility: 'visible',
            position: 'relative',
            zIndex: 1,
          }}
        >
          {title} {searchMetadata?.totalResults > 0 && searchTerm && (
            <Typography 
              component="span" 
              sx={{ 
                fontWeight: 300, 
                fontSize: '0.5em',
                color: 'text.secondary',
                opacity: 0.75
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
          .filter(col => col.sortable)
          .map(col => ({
            id: col.id,
            label: col.label
          }))
        }
        onSortChange={(columnId) => {
          const currentSort = sorting[0];
          const desc = currentSort?.id === columnId ? !currentSort.desc : false;
          onSortChange([{ id: columnId, desc }]);
        }}
        fields={viewMode === 'card' 
          ? cardFields 
          : columns.map(col => ({
            id: col.id,
            label: col.label,
            visible: col.visible
          }))}
        onFieldToggle={viewMode === 'card' ? onCardFieldToggle : onColumnToggle}
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
      />

      {viewMode === 'card' ? (
        <AssetGridView
          results={results}
          groupByType={groupByType}
          cardSize={cardSize}
          aspectRatio={aspectRatio}
          thumbnailScale={thumbnailScale}
          showMetadata={showMetadata}
          cardFields={cardFields.filter(f => f.visible)}
          onAssetClick={onAssetClick}
          onDeleteClick={onDeleteClick}
          onMenuClick={onMenuClick}
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
        />
      ) : (
        <AssetTableView
          results={results}
          columns={columns}
          sorting={sorting}
          onSortChange={onSortChange}
          groupByType={groupByType}
          onAssetClick={onAssetClick}
          onDeleteClick={onDeleteClick}
          onMenuClick={onMenuClick}
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
        />
      )}

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
