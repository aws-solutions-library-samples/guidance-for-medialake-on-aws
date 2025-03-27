import React, { useState } from 'react';
import { 
    Box, 
    Typography, 
    Grid, 
    Menu, 
    MenuItem, 
    Dialog, 
    DialogTitle, 
    DialogContent, 
    DialogContentText, 
    DialogActions, 
    Button,
    alpha,
    useTheme
} from '@mui/material';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import { type AssetBase } from '@/types/search/searchResults';
import AssetCard from './AssetCard';
import { AssetTable } from './AssetTable';
import AssetViewControls from './AssetViewControls';
import AssetPagination from './AssetPagination';
import { sortAssets } from '@/utils/sortAssets';
import { useAssetOperations } from '@/hooks/useAssetOperations';
import ErrorDisplay from './ErrorDisplay';
import { formatFileSize } from '@/utils/fileSize';
import { formatDate } from '@/utils/dateFormat';

export interface AssetDisplayProps<T extends AssetBase> {
    // Data
    assets: T[];
    totalCount: number;
    page: number;
    pageSize: number;
    
    // Display options
    viewMode: 'card' | 'table';
    cardSize: 'small' | 'medium' | 'large';
    aspectRatio: 'vertical' | 'square' | 'horizontal';
    thumbnailScale: 'fit' | 'fill';
    showMetadata: boolean;
    groupByType: boolean;
    
    // Field configuration
    cardFields: { id: string; label: string; visible: boolean; }[];
    columns: AssetTableColumn<T>[];
    
    // Sorting
    sorting: SortingState;
    
    // Accessors
    getId: (asset: T) => string;
    getName: (asset: T) => string;
    getType: (asset: T) => string;
    getThumbnailUrl: (asset: T) => string | undefined;
    getProxyUrl: (asset: T) => string | undefined;
    getField: (fieldId: string, asset: T) => React.ReactNode;
    
    // Event handlers
    onAssetClick: (asset: T) => void;
    onPageChange: (page: number) => void;
    onPageSizeChange: (pageSize: number) => void;
    onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
    onCardSizeChange: (size: 'small' | 'medium' | 'large') => void;
    onAspectRatioChange: (ratio: 'vertical' | 'square' | 'horizontal') => void;
    onThumbnailScaleChange: (scale: 'fit' | 'fill') => void;
    onShowMetadataChange: (show: boolean) => void;
    onGroupByTypeChange: (checked: boolean) => void;
    onCardFieldToggle: (fieldId: string) => void;
    onColumnToggle: (columnId: string) => void;
    onSortChange: (sorting: SortingState) => void;
    
    // Optional
    title?: string | React.ReactNode;
    error?: { status: string; message: string } | null;
    isLoading?: boolean;
}

export function AssetDisplay<T extends AssetBase>({
    assets,
    totalCount,
    page,
    pageSize,
    viewMode,
    cardSize,
    aspectRatio,
    thumbnailScale,
    showMetadata,
    groupByType,
    cardFields,
    columns,
    sorting,
    getId,
    getName,
    getType,
    getThumbnailUrl,
    getProxyUrl,
    getField,
    onAssetClick,
    onPageChange,
    onPageSizeChange,
    onViewModeChange,
    onCardSizeChange,
    onAspectRatioChange,
    onThumbnailScaleChange,
    onShowMetadataChange,
    onGroupByTypeChange,
    onCardFieldToggle,
    onColumnToggle,
    onSortChange,
    title,
    error,
    isLoading
}: AssetDisplayProps<T>) {
    const theme = useTheme();
    
    // Asset operations (menu, delete, edit)
    const {
        handleDeleteClick,
        handleMenuOpen,
        handleStartEditing,
        handleNameChange,
        handleNameEditComplete,
        handleMenuClose,
        handleAction,
        handleDeleteConfirm,
        handleDeleteCancel,
        editingAssetId,
        editedName,
        isDeleteModalOpen,
        menuAnchorEl,
        selectedAsset,
    } = useAssetOperations<T>();

    // Group results by type if needed
    const groupedAssets = React.useMemo(() => {
        if (!groupByType) return { all: assets };

        return assets.reduce((acc, item) => {
            const type = getType(item);
            const normalizedType = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
            
            if (!acc[normalizedType]) acc[normalizedType] = [];
            acc[normalizedType].push(item);
            return acc;
        }, {} as Record<string, T[]>);
    }, [assets, groupByType, getType]);

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

    // If there's an error, display the error component
    if (error) {
        return (
            <Box>
                <AssetViewControls
                    viewMode={viewMode}
                    onViewModeChange={onViewModeChange}
                    title={title}
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
                    message="There was a problem loading content." 
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
            const sortedAssets = groupByType
                ? Object.entries(groupedAssets)
                    .filter(([type]) => type !== 'all')
                    .map(([type, items]) => ({
                        type,
                        assets: sortAssets(items, sorting, columns)
                    }))
                : [{ type: 'all', assets: sortAssets(assets, sorting, columns) }];

            if (!groupByType) {
                return (
                    <Grid container spacing={3}>
                        {sortedAssets[0].assets.map(asset => (
                            <Grid item {...getGridSizes()} key={getId(asset)}>
                                <AssetCard
                                    id={getId(asset)}
                                    name={getName(asset)}
                                    thumbnailUrl={getThumbnailUrl(asset)}
                                    proxyUrl={getProxyUrl(asset)}
                                    assetType={getType(asset)}
                                    fields={cardFields.filter(f => f.visible)}
                                    renderField={(fieldId) => getField(fieldId, asset)}
                                    onAssetClick={() => onAssetClick(asset)}
                                    onDeleteClick={(e) => handleDeleteClick(asset, e)}
                                    onMenuClick={(e) => handleMenuOpen(asset, e)}
                                    onEditClick={(e) => handleStartEditing(asset, e)}
                                    isEditing={editingAssetId === getId(asset)}
                                    editedName={editedName}
                                    onEditNameChange={handleNameChange}
                                    onEditNameComplete={(save) => handleNameEditComplete(asset, save)}
                                    cardSize={cardSize}
                                    aspectRatio={aspectRatio}
                                    thumbnailScale={thumbnailScale}
                                    showMetadata={showMetadata}
                                />
                            </Grid>
                        ))}
                    </Grid>
                );
            }

            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {sortedAssets.map(({ type, assets }) => assets.length > 0 && (
                        <Box key={type}>
                            <Typography variant="h6" sx={{ mb: 2, px: 1, color: 'text.secondary' }}>
                                {type}
                            </Typography>
                            <Grid container spacing={3}>
                                {assets.map(asset => (
                                    <Grid item {...getGridSizes()} key={getId(asset)}>
                                        <AssetCard
                                            id={getId(asset)}
                                            name={getName(asset)}
                                            thumbnailUrl={getThumbnailUrl(asset)}
                                            proxyUrl={getProxyUrl(asset)}
                                            assetType={getType(asset)}
                                            fields={cardFields.filter(f => f.visible)}
                                            renderField={(fieldId) => getField(fieldId, asset)}
                                            onAssetClick={() => onAssetClick(asset)}
                                            onDeleteClick={(e) => handleDeleteClick(asset, e)}
                                            onMenuClick={(e) => handleMenuOpen(asset, e)}
                                            onEditClick={(e) => handleStartEditing(asset, e)}
                                            isEditing={editingAssetId === getId(asset)}
                                            editedName={editedName}
                                            onEditNameChange={handleNameChange}
                                            onEditNameComplete={(save) => handleNameEditComplete(asset, save)}
                                            cardSize={cardSize}
                                            aspectRatio={aspectRatio}
                                            thumbnailScale={thumbnailScale}
                                            showMetadata={showMetadata}
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
                    {Object.entries(groupedAssets)
                        .filter(([type]) => type !== 'all' && groupedAssets[type].length > 0)
                        .map(([type, items]) => (
                            <Box key={type}>
                                <Typography variant="h6" sx={{ mb: 2, px: 1, color: 'text.secondary' }}>
                                    {type}
                                </Typography>
                                <AssetTable
                                    data={items}
                                    columns={columns}
                                    sorting={sorting}
                                    onSortingChange={onSortChange}
                                    onDeleteClick={handleDeleteClick}
                                    onMenuClick={handleMenuOpen}
                                    onEditClick={handleStartEditing}
                                    onAssetClick={onAssetClick}
                                    getThumbnailUrl={getThumbnailUrl}
                                    getName={getName}
                                    getId={getId}
                                    getAssetType={getType}
                                    editingId={editingAssetId}
                                    editedName={editedName}
                                    onEditNameChange={handleNameChange}
                                    onEditNameComplete={(asset) => handleNameEditComplete(asset, true)}
                                />
                            </Box>
                        ))}
                </Box>
            );
        }

        // Non-grouped table view
        return (
            <AssetTable
                data={assets}
                columns={columns}
                sorting={sorting}
                onSortingChange={onSortChange}
                onDeleteClick={handleDeleteClick}
                onMenuClick={handleMenuOpen}
                onEditClick={handleStartEditing}
                onAssetClick={onAssetClick}
                getThumbnailUrl={getThumbnailUrl}
                getName={getName}
                getId={getId}
                getAssetType={getType}
                editingId={editingAssetId}
                editedName={editedName}
                onEditNameChange={handleNameChange}
                onEditNameComplete={(asset) => handleNameEditComplete(asset, true)}
            />
        );
    };

    return (
        <Box sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            height: '100%',
            overflow: 'hidden' // Prevent outer container from scrolling
        }}>
            <AssetViewControls
                viewMode={viewMode}
                onViewModeChange={onViewModeChange}
                title={title}
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

            {/* Content area with fixed position and scrollable content */}
            <Box sx={{ 
                flex: 1,
                overflow: 'auto', // This container scrolls
                position: 'relative',
                pt: 1, // Add padding at the top to prevent collision with the top bar
                px: 1  // Add padding on the sides
            }}>
                {renderContent()}
            </Box>

            <Box sx={{ position: 'sticky', bottom: 0, backgroundColor: 'background.paper', zIndex: 2, pt: 1 }}>
                <AssetPagination
                    page={page}
                    pageSize={pageSize}
                    totalResults={totalCount}
                    onPageChange={(_, page) => onPageChange(page)}
                    onPageSizeChange={onPageSizeChange}
                />
            </Box>

            {/* Asset Menu */}
            <Menu
                anchorEl={menuAnchorEl}
                open={Boolean(menuAnchorEl)}
                onClose={handleMenuClose}
                MenuListProps={{
                    'aria-labelledby': selectedAsset ? `asset-menu-button-${getId(selectedAsset)}` : undefined
                }}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        borderRadius: '8px',
                        minWidth: 200,
                        mt: 1,
                        border: theme => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                        backgroundColor: theme => theme.palette.background.paper,
                        overflow: 'visible',
                        position: 'absolute',
                        zIndex: 1400,
                    },
                }}
                slotProps={{
                    paper: {
                        sx: {
                            overflow: 'visible',
                            position: 'absolute',
                        }
                    }
                }}
            >
                <MenuItem onClick={() => handleAction('rename')}>Rename</MenuItem>
                <MenuItem onClick={() => handleAction('share')}>Share</MenuItem>
                <MenuItem onClick={() => handleAction('download')}>Download</MenuItem>
            </Menu>

            {/* Delete Confirmation Dialog */}
            <Dialog
                open={isDeleteModalOpen}
                onClose={handleDeleteCancel}
                aria-labelledby="delete-dialog-title"
                aria-describedby="delete-dialog-description"
            >
                <DialogTitle id="delete-dialog-title">
                    Confirm Delete
                </DialogTitle>
                <DialogContent>
                    <DialogContentText id="delete-dialog-description">
                        Are you sure you want to delete this asset? This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleDeleteCancel}>Cancel</Button>
                    <Button onClick={handleDeleteConfirm} color="error" autoFocus>
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}

export default AssetDisplay;
