import React from 'react';
import { Box, Grid, Typography } from '@mui/material';
import { type ImageItem, type VideoItem, type AudioItem } from '@/types/search/searchResults';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetCard from '../shared/AssetCard';
import AssetTable from '../shared/AssetTable';
import AssetViewControls from '../shared/AssetViewControls';
import AssetPagination from '../shared/AssetPagination';
import { sortAssets } from '@/utils/sortAssets';

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
    DigitalSourceAsset: {
        Type: string;
    };
};

interface UnifiedResultsViewProps {
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
    onGroupByTypeChange: (checked: boolean) => void;
}

const UnifiedResultsView: React.FC<UnifiedResultsViewProps> = ({
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
    onGroupByTypeChange,
}) => {
    // Group results by type if needed
    const groupedResults = React.useMemo(() => {
        if (!groupByType) return { all: results };

        return results.reduce((acc, item) => {
            // Normalize the type to ensure consistent grouping
            const type = item.DigitalSourceAsset.Type.toLowerCase();
            const normalizedType = type === 'image' ? 'Image' :
                                 type === 'video' ? 'Video' :
                                 type === 'audio' ? 'Audio' : 'Other';
            
            if (!acc[normalizedType]) acc[normalizedType] = [];
            acc[normalizedType].push(item);
            return acc;
        }, {} as Record<string, AssetItem[]>);
    }, [results, groupByType]);

    const getGridSizes = () => {
        switch (cardSize) {
            case 'small':
                return { xs: 12, sm: 6, md: 3, lg: 2 };
            case 'large':
                return { xs: 12, sm: 12, md: 6, lg: 4 };
            default: // medium
                return { xs: 12, sm: 6, md: 4, lg: 3 };
        }
    };

    const renderAssetCard = (asset: AssetItem) => {
        const gridSizes = getGridSizes();
        return (
            <Grid item xs={gridSizes.xs} sm={gridSizes.sm} md={gridSizes.md} lg={gridSizes.lg} key={asset.InventoryID}>
                <AssetCard
                    cardSize={cardSize}
                    aspectRatio={aspectRatio}
                    id={asset.InventoryID}
                    name={asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                    thumbnailUrl={asset.thumbnailUrl}
                    proxyUrl={asset.proxyUrl}
                    assetType={asset.DigitalSourceAsset.Type}
                    fields={cardFields}
                    renderField={(fieldId) => {
                        switch (fieldId) {
                            case 'name':
                                return asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
                            case 'type':
                                return asset.DigitalSourceAsset.Type;
                            case 'format':
                                return asset.DigitalSourceAsset.MainRepresentation.Format;
                            case 'size':
                                const sizeInBytes = asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
                                const sizes = ['B', 'KB', 'MB', 'GB'];
                                let i = 0;
                                let size = sizeInBytes;
                                while (size >= 1024 && i < sizes.length - 1) {
                                    size /= 1024;
                                    i++;
                                }
                                return `${Math.round(size * 100) / 100} ${sizes[i]}`;
                            default:
                                return '';
                        }
                    }}
                    onAssetClick={() => onAssetClick(asset)}
                    onDeleteClick={(event) => {
                        event.stopPropagation();
                        onDeleteClick(asset, event);
                    }}
                    onMenuClick={(event) => {
                        event.stopPropagation();
                        onMenuClick(asset, event);
                    }}
                    onEditClick={(event) => {
                        event.stopPropagation();
                        onEditClick(asset, event);
                    }}
                    onImageError={() => console.error('Image failed to load')}
                    isEditing={editingAssetId === asset.InventoryID}
                    editedName={editedName}
                    onEditNameChange={onEditNameChange}
                    onEditNameComplete={(save) => onEditNameComplete(asset, save)}
                    thumbnailScale={thumbnailScale}
                    showMetadata={showMetadata}
                />
            </Grid>
        );
    };

    const renderContent = () => {
        if (viewMode === 'card') {
            // Sort assets within their groups or as a whole
            const sortedResults = groupByType
                ? Object.entries(groupedResults)
                    .filter(([type]) => ['Image', 'Video', 'Audio'].includes(type))
                    .map(([type, assets]) => ({
                        type,
                        assets: sortAssets(assets, sorting, columns)
                    }))
                : [{ type: 'all', assets: sortAssets(results, sorting, columns) }];

            if (!groupByType) {
                return (
                    <Grid container spacing={3}>
                        {sortedResults[0].assets.map(renderAssetCard)}
                    </Grid>
                );
            }

            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {sortedResults.map(({ type, assets }) => assets.length > 0 && (
                        <Box key={type}>
                            <Typography variant="h6" sx={{ mb: 2, px: 1, color: 'text.secondary' }}>
                                {type}
                            </Typography>
                            <Grid container spacing={3}>
                                {assets.map(renderAssetCard)}
                            </Grid>
                        </Box>
                    ))}
                </Box>
            );
        }

        // Table view
        const tableData = groupByType ? Object.values(groupedResults).flat() : results;
        return (
            <AssetTable
                data={tableData}
                columns={columns.map(col => ({
                    ...col,
                    getValue: (asset: AssetItem) => col.accessor ? col.accessor(asset) : '',
                }))}
                sorting={sorting}
                onSortingChange={onSortChange}
                getThumbnailUrl={(asset) => asset.thumbnailUrl || ''}
                getName={(asset) => asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                getId={(asset) => asset.InventoryID}
                onDeleteClick={(asset, event) => {
                    event.stopPropagation();
                    onDeleteClick(asset, event);
                }}
                onMenuClick={(asset, event) => {
                    event.stopPropagation();
                    onMenuClick(asset, event);
                }}
                onEditClick={(asset, event) => {
                    event.stopPropagation();
                    onEditClick(asset, event);
                }}
                onRowClick={(asset) => onAssetClick(asset)}
                editingId={editingAssetId}
                editedName={editedName}
                onEditNameChange={onEditNameChange}
                onEditNameComplete={(asset, save) => onEditNameComplete(asset, save)}
            />
        );
    };

    return (
        <Box>
            <AssetViewControls
                viewMode={viewMode}
                onViewModeChange={onViewModeChange}
                title="Results"
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
                fields={viewMode === 'card' ? cardFields : columns}
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

            {renderContent()}

            <AssetPagination
                page={searchMetadata.page}
                pageSize={searchMetadata.pageSize}
                totalResults={searchMetadata.totalResults}
                onPageChange={(_, page) => onPageChange(page)}
            />
        </Box>
    );
};

export default UnifiedResultsView;