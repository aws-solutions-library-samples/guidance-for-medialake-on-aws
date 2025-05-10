import React, { useState, useCallback } from 'react';
import { Box, Grid, Typography, Paper, Alert, AlertTitle } from '@mui/material';
import { type ImageItem, type VideoItem, type AudioItem } from '@/types/search/searchResults';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetCard from '../shared/AssetCard';
import { AssetTable } from '../shared/AssetTable';
import AssetViewControls from '../shared/AssetViewControls';
import AssetPagination from '../shared/AssetPagination';
import { sortAssets } from '@/utils/sortAssets';
import { useNavigate, useLocation } from 'react-router-dom';
import UnifiedAssetResults from './UnifiedAssetResults';
import { formatFileSize } from '@/utils/fileSize';
import { formatDate } from '@/utils/dateFormat';
import ErrorDisplay from '../shared/ErrorDisplay';
import RightSidebar from '../common/RightSidebar/RightSidebar';
import FilterAndBatchOperations from '../common/RightSidebar/FilterAndBatchOperations';

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
    onPageSizeChange: (newPageSize: number) => void;
    error?: { status: string; message: string } | null;
    isLoading?: boolean;
    // Selection and favorite handlers
    selectedAssets?: string[];
    onSelectToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
    favoriteAssets?: string[];
    onFavoriteToggle?: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
    filterComponent?: React.ReactNode;
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
    onPageSizeChange,
    error,
    isLoading,
    selectedAssets: initialSelectedAssets = [],
    onSelectToggle: externalOnSelectToggle,
    favoriteAssets = [],
    onFavoriteToggle,
    filterComponent,
}) => {
    const navigate = useNavigate();
    const location = useLocation();
    const locationState = location.state as { filters?: unknown; isSemantic?: boolean } | null;
    
    // Internal state for selected assets
    const [internalSelectedAssets, setInternalSelectedAssets] = useState<string[]>(initialSelectedAssets);
    
    // Use either external or internal state for selected assets
    const selectedAssets = externalOnSelectToggle ? initialSelectedAssets : internalSelectedAssets;
    
    // Handle selection toggle
    const handleSelectToggle = useCallback((asset: AssetItem, event: React.MouseEvent<HTMLElement> | React.ChangeEvent<HTMLInputElement>) => {
        console.log('handleSelectToggle called with asset:', asset.InventoryID);
        console.log('Current selectedAssets:', selectedAssets);
        console.log('Is asset currently selected:', selectedAssets.includes(asset.InventoryID));
        console.log('Event type:', event.type);
        
        if (externalOnSelectToggle) {
            // Use external handler if provided
            console.log('Using external handler');
            externalOnSelectToggle(asset, event as React.MouseEvent<HTMLElement>);
            
            // Log after external handler (will show on next render cycle)
            setTimeout(() => {
                console.log('After external handler, selectedAssets:', 
                    Array.isArray(initialSelectedAssets) ? initialSelectedAssets : 'Not an array');
            }, 0);
        } else {
            // Otherwise use internal state
            console.log('Using internal state');
            setInternalSelectedAssets(prev => {
                const assetId = asset.InventoryID;
                if (prev.includes(assetId)) {
                    console.log('Removing asset from selection:', assetId);
                    return prev.filter(id => id !== assetId);
                } else {
                    console.log('Adding asset to selection:', assetId);
                    return [...prev, assetId];
                }
            });
            
            // Log the updated state (will show on next render cycle)
            setTimeout(() => {
                console.log('After internal state update, selectedAssets:', selectedAssets);
            }, 0);
        }
    }, [externalOnSelectToggle, selectedAssets, initialSelectedAssets]);
    
    // Handle clearing all selections
    const handleClearSelection = useCallback(() => {
        if (externalOnSelectToggle) {
            // If using external state, we need to clear each item individually
            selectedAssets.forEach(assetId => {
                const asset = results.find(a => a.InventoryID === assetId);
                if (asset) {
                    externalOnSelectToggle(asset, {} as React.MouseEvent<HTMLElement>);
                }
            });
        } else {
            // Clear internal state
            setInternalSelectedAssets([]);
        }
    }, [externalOnSelectToggle, selectedAssets, results]);
    
    // Handle batch operations
    const handleBatchDelete = useCallback(() => {
        console.log('Batch delete:', selectedAssets);
        // Implement batch delete functionality
        // After deletion, clear selection
        handleClearSelection();
    }, [selectedAssets, handleClearSelection]);
    
    const handleBatchDownload = useCallback(() => {
        console.log('Batch download:', selectedAssets);
        // Implement batch download functionality
    }, [selectedAssets]);
    
    const handleBatchShare = useCallback(() => {
        console.log('Batch share:', selectedAssets);
        // Implement batch share functionality
    }, [selectedAssets]);
    
    // Create selected assets objects for the batch operations component
    const selectedAssetsObjects = React.useMemo(() => {
        return selectedAssets.map(assetId => {
            const asset = results.find(a => a.InventoryID === assetId);
            return asset ? {
                id: asset.InventoryID,
                name: asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
                type: asset.DigitalSourceAsset.Type
            } : null;
        }).filter(Boolean) as Array<{
            id: string;
            name: string;
            type: string;
        }>;
    }, [selectedAssets, results]);

    const handleAssetClick = (asset: AssetItem) => {
        const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
        navigate(`/${assetType}s/${asset.InventoryID}`, {
            state: {
                searchTerm,
                page: searchMetadata.page,
                viewMode,
                cardSize,
                aspectRatio,
                thumbnailScale,
                showMetadata,
                groupByType,
                filters: locationState?.filters,
                sorting,
                isSemantic: locationState?.isSemantic,
                currentResult: results.findIndex(r => r.InventoryID === asset.InventoryID) + 1,
                totalResults: searchMetadata.totalResults
            }
        });
    };

    // Group results by type if needed
    const groupedResults = React.useMemo(() => {
        if (!groupByType) return { all: results };

        return results.reduce((acc, item) => {
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
                        Results
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
                    title="Search Error" 
                    message="There was a problem searching for content." 
                    detailedMessage={error.message}
                />
            </Box>
        );
    }

    // If loading, you could add a loading state here
    if (isLoading) {
        // Return loading UI
    }

    const renderContent = () => {
        if (viewMode === 'card') {
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
                        {sortedResults[0].assets.map(asset => (
                            <Grid item {...getGridSizes()} key={asset.InventoryID}>
                                <AssetCard
                                    id={asset.InventoryID}
                                    name={asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                                    thumbnailUrl={asset.thumbnailUrl}
                                    proxyUrl={asset.proxyUrl}
                                    assetType={asset.DigitalSourceAsset.Type}
                                    fields={cardFields.filter(f => f.visible)}
                                    renderField={(fieldId) => renderCardField(fieldId, asset)}
                                    onAssetClick={() => onAssetClick(asset)}
                                    onDeleteClick={(e) => onDeleteClick(asset, e)}
                                    onMenuClick={(e) => onMenuClick(asset, e)}
                                    onEditClick={(e) => onEditClick(asset, e)}
                                    isEditing={editingAssetId === asset.InventoryID}
                                    editedName={editedName}
                                    onEditNameChange={onEditNameChange}
                                    onEditNameComplete={(save) => onEditNameComplete(asset, save)}
                                    cardSize={cardSize}
                                    aspectRatio={aspectRatio}
                                    thumbnailScale={thumbnailScale}
                                    showMetadata={showMetadata}
                                    isSelected={selectedAssets.includes(asset.InventoryID)}
                                    onSelectToggle={(id, e) => handleSelectToggle(asset, e)}
                                    isFavorite={favoriteAssets.includes(asset.InventoryID)}
                                    onFavoriteToggle={onFavoriteToggle ? (e) => onFavoriteToggle(asset, e) : undefined}
                                />
                            </Grid>
                        ))}
                    </Grid>
                );
            }

            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {sortedResults.map(({ type, assets }) => assets.length > 0 && (
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
                            <Grid container spacing={3}>
                                {assets.map(asset => (
                                    <Grid item {...getGridSizes()} key={asset.InventoryID}>
                                        <AssetCard
                                            id={asset.InventoryID}
                                            name={asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                                            thumbnailUrl={asset.thumbnailUrl}
                                            proxyUrl={asset.proxyUrl}
                                            assetType={asset.DigitalSourceAsset.Type}
                                            fields={cardFields.filter(f => f.visible)}
                                            renderField={(fieldId) => renderCardField(fieldId, asset)}
                                            onAssetClick={() => onAssetClick(asset)}
                                            onDeleteClick={(e) => onDeleteClick(asset, e)}
                                            onMenuClick={(e) => onMenuClick(asset, e)}
                                            onEditClick={(e) => onEditClick(asset, e)}
                                            isEditing={editingAssetId === asset.InventoryID}
                                            editedName={editedName}
                                            onEditNameChange={onEditNameChange}
                                            onEditNameComplete={(save) => onEditNameComplete(asset, save)}
                                            cardSize={cardSize}
                                            aspectRatio={aspectRatio}
                                            thumbnailScale={thumbnailScale}
                                            showMetadata={showMetadata}
                                            isSelected={selectedAssets.includes(asset.InventoryID)}
                                            onSelectToggle={(id, e) => handleSelectToggle(asset, e)}
                                            isFavorite={favoriteAssets.includes(asset.InventoryID)}
                                            onFavoriteToggle={onFavoriteToggle ? (e) => onFavoriteToggle(asset, e) : undefined}
                                        />
                                    </Grid>
                                ))}
                            </Grid>
                        </Box>
                    ))}
                </Box>
            );
        }

        // Table view
        if (groupByType) {
            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {Object.entries(groupedResults)
                        .filter(([type]) => ['Image', 'Video', 'Audio'].includes(type) && groupedResults[type].length > 0)
                        .map(([type, assets]) => (
                            <Box key={type}>
                                <Typography variant="h6" sx={{ mb: 2, px: 1, color: 'text.secondary' }}>
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
                                    getThumbnailUrl={(asset) => asset.thumbnailUrl || ''}
                                    getName={(asset) => asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                                    getId={(asset) => asset.InventoryID}
                                    getAssetType={(asset) => asset.DigitalSourceAsset.Type}
                                    editingId={editingAssetId}
                                    editedName={editedName}
                                    onEditNameChange={onEditNameChange}
                                    onEditNameComplete={(asset) => onEditNameComplete(asset, true)}
                                    isSelected={(asset) => selectedAssets.includes(asset.InventoryID)}
                                    onSelectToggle={(asset, e) => handleSelectToggle(asset, e)}
                                    isFavorite={(asset) => favoriteAssets.includes(asset.InventoryID)}
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
                getThumbnailUrl={(asset) => asset.thumbnailUrl || ''}
                getName={(asset) => asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                getId={(asset) => asset.InventoryID}
                getAssetType={(asset) => asset.DigitalSourceAsset.Type}
                editingId={editingAssetId}
                editedName={editedName}
                onEditNameChange={onEditNameChange}
                onEditNameComplete={(asset) => onEditNameComplete(asset, true)}
                isSelected={(asset) => selectedAssets.includes(asset.InventoryID)}
                onSelectToggle={(asset, e) => handleSelectToggle(asset, e)}
                isFavorite={(asset) => favoriteAssets.includes(asset.InventoryID)}
                onFavoriteToggle={onFavoriteToggle}
            />
        );
    };

    return (
        <React.Fragment>
            {/* Right Sidebar with Filter and Batch Operations */}
            <RightSidebar>
                <FilterAndBatchOperations
                    selectedAssets={selectedAssetsObjects}
                    onBatchDelete={handleBatchDelete}
                    onBatchDownload={handleBatchDownload}
                    onBatchShare={handleBatchShare}
                    onClearSelection={handleClearSelection}
                    filterComponent={filterComponent}
                />
            </RightSidebar>
            
            <Box sx={{ mt: -2 }}>
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
                        display: 'block', // Ensure the text is displayed
                        visibility: 'visible', // Make sure it's visible
                        position: 'relative', // Establish positioning context
                        zIndex: 1, // Ensure it's above other elements
                    }}
                >
                    Results {searchMetadata?.totalResults > 0 && (
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

            {renderContent()}

            <AssetPagination
                page={searchMetadata.page}
                pageSize={searchMetadata.pageSize}
                totalResults={searchMetadata.totalResults}
                onPageChange={(_, page) => onPageChange(page)}
                onPageSizeChange={onPageSizeChange}
            />
            </Box>
        </React.Fragment>
    );
};

export default UnifiedResultsView;