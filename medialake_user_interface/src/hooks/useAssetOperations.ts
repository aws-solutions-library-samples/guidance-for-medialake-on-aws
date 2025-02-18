import { useState, useEffect } from 'react';
import { useRenameAsset, useDeleteAsset } from '../api/hooks/useAssets';
import { type AssetBase } from '../types/search/searchResults';

interface UseAssetOperationsReturn<T extends AssetBase> {
    selectedAsset: T | null;
    menuAnchorEl: HTMLElement | null;
    isDeleteModalOpen: boolean;
    assetToDelete: T | null;
    editingAssetId: string | null;
    editedName: string;
    isRenameDialogOpen: boolean;
    handleMenuOpen: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
    handleMenuClose: () => void;
    handleAction: (action: string) => void;
    handleDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
    handleDeleteConfirm: () => Promise<void>;
    handleStartEditing: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
    handleNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    handleNameEditComplete: (asset: T, save: boolean) => void;
    handleRenameConfirm: (newName: string) => Promise<void>;
    handleDeleteCancel: () => void;
    handleRenameCancel: () => void;
    isLoading: {
        rename: boolean;
        delete: boolean;
    };
}

export function useAssetOperations<T extends AssetBase>(): UseAssetOperationsReturn<T> {
    const [menuAnchorEl, setMenuAnchorEl] = useState<HTMLElement | null>(null);
    const [selectedAsset, setSelectedAsset] = useState<T | null>(null);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [assetToDelete, setAssetToDelete] = useState<T | null>(null);
    const [editingAssetId, setEditingAssetId] = useState<string | null>(null);
    const [editedName, setEditedName] = useState<string>('');
    const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);

    const renameAsset = useRenameAsset();
    const deleteAsset = useDeleteAsset();


    const handleMenuOpen = (asset: T, event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        setMenuAnchorEl(event.currentTarget);
        setSelectedAsset(asset);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setSelectedAsset(null);
    };

    const handleAction = (action: string) => {
        if (!selectedAsset) return;

        switch (action) {
            case 'rename':
                setEditingAssetId(selectedAsset.InventoryID);
                setEditedName(selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name);
                setIsRenameDialogOpen(true);
                break;
            case 'share':
                console.log('Share:', selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name);
                break;
            case 'download':
                const fileName = selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
                fetch(selectedAsset.proxyUrl)
                    .then(response => response.blob())
                    .then(blob => {
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = fileName;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        window.URL.revokeObjectURL(url);
                    })
                    .catch(error => console.error('Download failed:', error));
                break;

        }
        handleMenuClose();
    };

    const handleDeleteClick = (asset: T, event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        setAssetToDelete(asset);
        setIsDeleteModalOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (assetToDelete) {
            try {
                await deleteAsset.mutateAsync(assetToDelete.InventoryID);
                setIsDeleteModalOpen(false);
                setAssetToDelete(null);
            } catch (error) {
                // Error handling is done in the mutation
                setIsDeleteModalOpen(false);
                setAssetToDelete(null);
            }
        }
    };

    const handleStartEditing = (asset: T, event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        setEditingAssetId(asset.InventoryID);
        setEditedName(asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name);
    };

    const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setEditedName(event.target.value);
    };

    const handleNameEditComplete = (asset: T, save: boolean) => {
        if (save && editedName !== asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name) {
            handleRenameConfirm(editedName);
        }
        setEditingAssetId(null);
        if (!save) {
            setEditedName(asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name);
        }
    };

    const handleRenameConfirm = async (newName: string) => {
        if (editingAssetId) {
            try {

                await renameAsset.mutateAsync({
                    inventoryId: editingAssetId,
                    newName
                });
                setEditedName(null)
                setIsRenameDialogOpen(false);
                setSelectedAsset(null);
                setEditingAssetId(null)

            } catch (error) {
                // Error handling is done in the mutation
            }
        }
    };

    const handleDeleteCancel = () => {
        setIsDeleteModalOpen(false);
        setAssetToDelete(null);
    };

    const handleRenameCancel = () => {
        setIsRenameDialogOpen(false);
        setSelectedAsset(null);
        setEditedName(null);
        setEditingAssetId(null);
    };

    return {
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
        isLoading: {
            rename: renameAsset.isPending,
            delete: deleteAsset.isPending,
        },
    };
}
