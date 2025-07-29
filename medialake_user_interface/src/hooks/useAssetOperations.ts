import { useState, useMemo } from "react";
import { useRenameAsset, useDeleteAsset } from "../api/hooks/useAssets";
import { useGeneratePresignedUrl } from "../api/hooks/usePresignedUrl";
import { type AssetBase } from "../types/search/searchResults";

interface UseAssetOperationsReturn<T extends AssetBase> {
  selectedAsset: T | null;
  menuAnchorEl: HTMLElement | null;
  isDeleteModalOpen: boolean;
  assetToDelete: T | null;
  editingAssetId: string | null;
  editedName: string;
  isRenameDialogOpen: boolean;
  alert: { message: string; severity: "success" | "error" } | null;
  handleMenuOpen: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  handleMenuClose: () => void;
  handleAction: (action: string) => void;
  handleDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  handleDeleteConfirm: () => Promise<void>;
  handleStartEditing: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  handleNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleNameEditComplete: (asset: T, save: boolean, value?: string) => void;
  handleRenameConfirm: (newName: string) => Promise<void>;
  handleDeleteCancel: () => void;
  handleRenameCancel: () => void;
  handleDownloadClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  handleAlertClose: () => void;
  isLoading: {
    rename: boolean;
    delete: boolean;
    download: boolean;
  };
  renamingAssetId?: string;
}

export function useAssetOperations<
  T extends AssetBase,
>(): UseAssetOperationsReturn<T> {
  const [menuAnchorEl, setMenuAnchorEl] = useState<HTMLElement | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<T | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [assetToDelete, setAssetToDelete] = useState<T | null>(null);
  const [editingAssetId, setEditingAssetId] = useState<string | null>(null);
  const [editedName, setEditedName] = useState<string>("");
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [downloadingAssetId, setDownloadingAssetId] = useState<string | null>(
    null,
  );
  const [alert, setAlert] = useState<{
    message: string;
    severity: "success" | "error";
  } | null>(null);

  const handleRenameError = (message: string) => {
    setAlert({ message, severity: "error" });
  };

  const renameAsset = useRenameAsset(handleRenameError);
  const deleteAsset = useDeleteAsset();
  const generatePresignedUrl = useGeneratePresignedUrl();

  const handleMenuOpen = (asset: T, event: React.MouseEvent<HTMLElement>) => {
    // Make sure to stop propagation to prevent the card click
    event.stopPropagation();
    event.preventDefault();
    console.log("Menu opened for asset:", asset.InventoryID);
    setMenuAnchorEl(event.currentTarget);
    setSelectedAsset(asset);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedAsset(null);
  };

  const handleAction = async (action: string) => {
    if (!selectedAsset) return;

    // Close the menu immediately for all actions
    handleMenuClose();

    switch (action) {
      case "rename":
        setEditingAssetId(selectedAsset.InventoryID);
        setEditedName(
          selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.ObjectKey.Name,
        );
        setIsRenameDialogOpen(true);
        break;
      case "share":
        console.log(
          "Share:",
          selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.ObjectKey.Name,
        );
        break;
      case "download":
        try {
          // Set the downloading asset ID to show loading state
          setDownloadingAssetId(selectedAsset.InventoryID);

          // Always generate a presigned URL
          // Determine the purpose based on asset type (use 'original' as default)
          const purpose = "original";

          const fileName =
            selectedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo
              .PrimaryLocation.ObjectKey.Name;
          const result = await generatePresignedUrl.mutateAsync({
            inventoryId: selectedAsset.InventoryID,
            expirationTime: 60, // 1 minute in seconds
            purpose: purpose, // Pass the purpose to get the correct representation
          });

          const link = document.createElement("a");
          link.href = result.presigned_url;
          link.setAttribute("download", fileName);
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch (error) {
          console.error("Error downloading file:", error);
        } finally {
          // Reset the downloading asset ID
          setDownloadingAssetId(null);
        }
        break;
    }
  };

  const handleDownloadClick = async (
    asset: T,
    event: React.MouseEvent<HTMLElement>,
  ) => {
    // Make sure to stop propagation to prevent the card click
    event.stopPropagation();
    event.preventDefault();

    try {
      // Set the downloading asset ID to show loading state
      setDownloadingAssetId(asset.InventoryID);

      // Always generate a presigned URL
      // Determine the purpose based on asset type (use 'original' as default)
      const purpose = "original";

      const fileName =
        asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name;
      const result = await generatePresignedUrl.mutateAsync({
        inventoryId: asset.InventoryID,
        expirationTime: 60, // 1 minute in seconds
        purpose: purpose, // Pass the purpose to get the correct representation
      });

      const link = document.createElement("a");
      link.href = result.presigned_url;
      link.setAttribute("download", fileName);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error("Error downloading file:", error);
    } finally {
      // Reset the downloading asset ID
      setDownloadingAssetId(null);
    }
  };

  const handleDeleteClick = (
    asset: T,
    event: React.MouseEvent<HTMLElement>,
  ) => {
    // Make sure to stop propagation to prevent the card click
    event.stopPropagation();
    event.preventDefault();
    console.log("Delete clicked for asset:", asset.InventoryID);
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

  const handleStartEditing = (
    asset: T,
    event: React.MouseEvent<HTMLElement>,
  ) => {
    event.stopPropagation();
    setEditingAssetId(asset.InventoryID);
    setEditedName(
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name,
    );
  };

  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEditedName(event.target.value);
  };

  const handleNameEditComplete = (asset: T, save: boolean, value?: string) => {
    console.log(
      "🔍 handleNameEditComplete - save:",
      save,
      "value:",
      value,
      "editedName:",
      editedName,
    );
    console.log(
      "🔍 Original name:",
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name,
    );

    // Use the passed value if available, otherwise fall back to editedName
    const nameToUse = value || editedName;
    console.log("🔍 Name to use:", nameToUse);

    if (
      save &&
      nameToUse !==
        asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name
    ) {
      console.log("🔍 Names different - calling API");
      handleRenameConfirm(nameToUse);
    } else if (save) {
      console.log("🔍 Names same - NOT calling API");
    }

    setEditingAssetId(null);
    if (!save) {
      setEditedName(
        asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      );
    }
  };

  const handleRenameConfirm = async (newName: string) => {
    if (editingAssetId) {
      try {
        const response = await renameAsset.mutateAsync({
          inventoryId: editingAssetId,
          newName,
        });

        // The actual update to the UI will now happen automatically through React Query cache updates

        setEditedName("");
        setIsRenameDialogOpen(false);
        setSelectedAsset(null);
        setEditingAssetId(null);
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

  const handleAlertClose = () => {
    setAlert(null);
  };

  return {
    selectedAsset,
    menuAnchorEl,
    isDeleteModalOpen,
    assetToDelete,
    editingAssetId,
    editedName,
    isRenameDialogOpen,
    alert,
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
    handleDownloadClick,
    handleAlertClose,
    isLoading: {
      rename: renameAsset.isPending,
      delete: deleteAsset.isPending,
      download:
        generatePresignedUrl.isPending ||
        (selectedAsset && selectedAsset.InventoryID === downloadingAssetId),
    },
    renamingAssetId: renameAsset.variables?.inventoryId,
  };
}
