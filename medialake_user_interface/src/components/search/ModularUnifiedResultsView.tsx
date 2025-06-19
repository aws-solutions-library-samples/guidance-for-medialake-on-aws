import React, { useState, useMemo, useEffect } from 'react';
import { useFeatureFlag } from '@/utils/featureFlags';
import { type ImageItem, type VideoItem, type AudioItem } from '@/types/search/searchResults';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import { useNavigate, useLocation } from 'react-router-dom';
import { formatFileSize } from '@/utils/fileSize';
import { formatDate } from '@/utils/dateFormat';
import AssetResultsView from '../shared/AssetResultsView';

type AssetItem = ImageItem | VideoItem | AudioItem;

interface ModularUnifiedResultsViewProps {
  results: AssetItem[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  searchTerm: string;
  groupByType: boolean;
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
  cardFields: { id: string; label: string; visible: boolean; }[];
  onCardFieldToggle: (fieldId: string) => void;
  columns: AssetTableColumn<AssetItem>[];
  onColumnToggle: (columnId: string) => void;
  // Asset action handlers
  onAssetClick: (asset: AssetItem) => void;
  onDeleteClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: AssetItem, save: boolean) => void;
  editingAssetId?: string;
  editedName?: string;
  // Favorite functionality
  isAssetFavorited?: (assetId: string) => boolean;
  onFavoriteToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  // Selection functionality
  selectedAssets?: string[];
  onSelectToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onGroupByTypeChange: (checked: boolean) => void;
  onPageSizeChange: (newPageSize: number) => void;
  error?: { status: string; message: string } | null;
  isLoading?: boolean;
  clipType?: 'clip' | 'full';
}

const ModularUnifiedResultsView: React.FC<ModularUnifiedResultsViewProps> = ({
  results,
  searchMetadata,
  onPageChange,
  searchTerm,
  groupByType,
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
  selectedAssets,
  onSelectToggle,
  onGroupByTypeChange,
  onPageSizeChange,
  error,
  isLoading,
  clipType,
}) => {
  const multiSelectFeature = useFeatureFlag('search-multi-select-enabled', false);
  const [scoreFilter, setScoreFilter] = useState('0.000');

  // Reset scoreFilter when switching to non-clip mode
  useEffect(() => {
    if (clipType !== 'clip' && scoreFilter !== '0.000') {
      setScoreFilter('0.000');
    }
  }, [clipType]);

  // Filter results by score in parent
  const filteredResults = useMemo(() => {
    if (clipType === 'clip' && !isNaN(parseFloat(scoreFilter))) {
      const threshold = parseFloat(scoreFilter);
      return results.filter(
        (r: any) => typeof r.score === 'number' && r.score >= threshold
      );
    }
    return results;
  }, [results, clipType, scoreFilter]);

  const renderCardField = (fieldId: string, asset: AssetItem): React.ReactNode => {
    switch (fieldId) {
      case 'name':
        return asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
      case 'type':
        return asset.DigitalSourceAsset.Type;
      case 'format':
        return asset.DigitalSourceAsset.MainRepresentation.Format;
      case 'size':
        const sizeInBytes = asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
        return formatFileSize(sizeInBytes);
      case 'createdAt':
        return formatDate(asset.DigitalSourceAsset.CreateDate);
      case 'modifiedAt':
        return formatDate(asset.DigitalSourceAsset.ModifiedDate || asset.DigitalSourceAsset.CreateDate);
      default:
        return '';
    }
  };

  // Function to check if an asset is selected - only if multi-select feature is enabled
  const isAssetSelected = (multiSelectFeature.value && selectedAssets && selectedAssets.length > 0)
    ? (assetId: string) => selectedAssets.includes(assetId)
    : undefined;

  return (
    <AssetResultsView
      results={filteredResults}
      searchMetadata={searchMetadata}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
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
      onEditClick={onEditClick}
      onEditNameChange={onEditNameChange}
      onEditNameComplete={onEditNameComplete}
      editingAssetId={editingAssetId}
      editedName={editedName}
      isAssetFavorited={isAssetFavorited}
      onFavoriteToggle={onFavoriteToggle}
      isAssetSelected={isAssetSelected}
      onSelectToggle={onSelectToggle}
      error={error}
      isLoading={isLoading}
      getAssetId={(asset) => asset.InventoryID}
      getAssetName={(asset) => asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
      getAssetType={(asset) => asset.DigitalSourceAsset.Type}
      getAssetThumbnail={(asset) => asset.thumbnailUrl || ''}
      getAssetProxy={(asset) => asset.proxyUrl || ''}
      renderCardField={renderCardField}
      clipType={clipType}
      scoreFilter={clipType === 'clip' ? scoreFilter : undefined}
      onScoreFilterChange={clipType === 'clip' ? setScoreFilter : undefined}
    />
  );
};

export default ModularUnifiedResultsView;
