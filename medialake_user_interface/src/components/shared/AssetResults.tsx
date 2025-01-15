import React, { useState } from 'react';
import { Box, Grid } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { ConfirmationModal } from '../common/ConfirmationModal';
import { RenameDialog } from '../common/RenameDialog';
import { type AssetBase, type CardFieldConfig } from '../../types/search/searchResults';
import { type AssetTableColumn } from '../../types/shared/assetComponents';
import AssetCard from './AssetCard';
import AssetTable from './AssetTable';
import AssetViewControls from './AssetViewControls';
import AssetPagination from './AssetPagination';
import AssetActionsMenu from './AssetActionsMenu';
import { useAssetResults } from '../../hooks/useAssetResults';
import { useAssetOperations } from '../../hooks/useAssetOperations';

export interface AssetResultsConfig<T extends AssetBase> {
    assetType: string;
    defaultCardFields: CardFieldConfig[];
    defaultColumns: AssetTableColumn<T>[];
    sortOptions: Array<{ id: string; label: string }>;
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
}

function AssetResults<T extends AssetBase>({
    assets,
    searchMetadata,
    onPageChange,
    config,
    searchTerm,
    actions,
}: AssetResultsProps<T>) {
    const navigate = useNavigate();
    const [currentAsset, setCurrentAsset] = useState<T | null>(null);

    const {
        assetType,
        defaultCardFields,
        defaultColumns,
        sortOptions,
        renderCardField,
        placeholderImage = 'https://placehold.co/300x200',
    } = config;

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
    } = useAssetResults({
        assets,
        searchMetadata,
        onPageChange,
        defaultCardFields,
        defaultColumns,
    });

    const {
        selectedAsset,
        menuAnchorEl,
        isDeleteModalOpen,
        assetToDelete,
        editingAssetId,
        editedName,
        isRenameDialogOpen,
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
        isLoading,
    } = useAssetOperations<T>();

    const handleNavigationPageChange = (newPage: number) => {
        handlePageChange({} as React.ChangeEvent<unknown>, newPage);
    };

    const handleAssetClick = (asset: T) => {
        setCurrentAsset(asset);
        navigate(`/${assetType.toLowerCase()}s/${asset.InventoryID}?searchTerm=${encodeURIComponent(searchTerm)}`);
    };

    return (
        <Box>
            <AssetViewControls
                viewMode={viewMode}
                onViewModeChange={handleViewModeChange}
                title={assetType}
                sorting={sorting}
                sortOptions={sortOptions}
                onSortChange={handleRequestSort}
                fields={viewMode === 'card' ? cardFields : columns}
                onFieldToggle={viewMode === 'card' ? handleCardFieldToggle : handleColumnToggle}
            />

            {viewMode === 'card' ? (
                <Grid container spacing={3}>
                    {assets.map((asset) => (
                        <Grid item xs={12} sm={6} md={4} lg={3} key={asset.InventoryID}>
                            <AssetCard
                                id={asset.InventoryID}
                                name={asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                                thumbnailUrl={asset.thumbnailUrl}
                                fields={cardFields}
                                renderField={(fieldId) => renderCardField(fieldId, asset)}
                                onImageClick={() => handleAssetClick(asset)}
                                onDeleteClick={(e) => handleDeleteClick(asset, e)}
                                onMenuClick={(e) => handleMenuOpen(asset, e)}
                                onEditClick={(e) => handleStartEditing(asset, e)}
                                onImageError={handleAssetError}
                                isEditing={editingAssetId === asset.InventoryID}
                                editedName={editedName}
                                onEditNameChange={handleNameChange}
                                onEditNameComplete={(save) => handleNameEditComplete(asset, save)}
                            />
                        </Grid>
                    ))}
                </Grid>
            ) : (
                <AssetTable
                    data={assets}
                    columns={columns}
                    sorting={sorting}
                    onSortingChange={setSorting}
                    onDeleteClick={handleDeleteClick}
                    onMenuClick={handleMenuOpen}
                    onEditClick={handleStartEditing}
                    onRowClick={handleAssetClick}
                    getThumbnailUrl={(asset) => asset.thumbnailUrl || placeholderImage}
                    getName={(asset) => asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                    getId={(asset) => asset.InventoryID}
                    editingId={editingAssetId}
                    editedName={editedName}
                    onEditNameChange={handleNameChange}
                    onEditNameComplete={handleNameEditComplete}
                />
            )}

            <AssetPagination
                page={page}
                pageSize={searchMetadata.pageSize}
                totalResults={searchMetadata.totalResults}
                onPageChange={handlePageChange}
            />

            <AssetActionsMenu
                anchorEl={menuAnchorEl}
                selectedAsset={selectedAsset}
                onClose={handleMenuClose}
                onAction={handleAction}
                actions={actions}
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
                currentName={selectedAsset?.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name || ''}
                onConfirm={handleRenameConfirm}
                onCancel={handleRenameCancel}
                isLoading={isLoading.rename}
            />
        </Box>
    );
}

export default AssetResults;
