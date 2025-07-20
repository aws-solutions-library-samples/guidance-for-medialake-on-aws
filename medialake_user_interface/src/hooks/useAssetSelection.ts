import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useBulkDownload } from "@/api/hooks/useAssets";

/**
 * Hook for managing asset selection and bulk operations.
 *
 * Bulk download notifications are now handled automatically by the global
 * notification system. When you call handleBatchDownload, the job will be
 * tracked automatically and notifications will appear in the NotificationCenter.
 *
 * The JobNotificationSync component polls for all user jobs every 15 seconds
 * and syncs them with the notification system.
 */

interface SelectedAsset {
  id: string;
  name: string;
  type: string;
  inventoryID: string;
}

export function useAssetSelection<T>({
  getAssetId,
  getAssetName,
  getAssetType,
  onDownloadSuccess,
}: {
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  onDownloadSuccess?: () => void; // Callback to close side panel
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedAssets, setSelectedAssets] = useState<SelectedAsset[]>([]);
  const [bulkDownloadJobId, setBulkDownloadJobId] = useState<string | null>(
    null,
  );
  const [isDownloadLoading, setIsDownloadLoading] = useState(false);

  // Modal state for API status
  const [modalState, setModalState] = useState<{
    open: boolean;
    status: "loading" | "success" | "error";
    action: string;
    message?: string;
  }>({
    open: false,
    status: "loading",
    action: "",
    message: "",
  });

  // Hooks
  const bulkDownloadMutation = useBulkDownload();

  // Load selections from localStorage on component mount
  useEffect(() => {
    const savedSelections = localStorage.getItem("selectedAssets");
    if (savedSelections) {
      try {
        const parsedSelections = JSON.parse(savedSelections) as SelectedAsset[];
        if (Array.isArray(parsedSelections) && parsedSelections.length > 0) {
          setSelectedAssets(parsedSelections);

          // Update URL parameter
          searchParams.set("selected", "true");
          setSearchParams(searchParams);
        }
      } catch (e) {
        console.error("Error parsing saved selections:", e);
      }
    }
  }, []);

  // Save selections to localStorage whenever they change
  useEffect(() => {
    if (selectedAssets.length > 0) {
      localStorage.setItem("selectedAssets", JSON.stringify(selectedAssets));
    } else {
      localStorage.removeItem("selectedAssets");
    }
  }, [selectedAssets]);

  // Handle selection toggle
  const handleSelectToggle = useCallback(
    (asset: T, event: React.MouseEvent<HTMLElement>) => {
      console.log("handleSelectToggle called with asset:", getAssetId(asset));

      const assetId = getAssetId(asset);
      const selectedAsset: SelectedAsset = {
        id: assetId,
        name: getAssetName(asset),
        type: getAssetType(asset),
        inventoryID: assetId,
      };

      setSelectedAssets((prev) => {
        // Check if this asset is already selected
        const isSelected = prev.some((item) => item.id === assetId);
        const newSelectedAssets = isSelected
          ? prev.filter((item) => item.id !== assetId)
          : [...prev, selectedAsset];

        // Update URL parameter
        if (newSelectedAssets.length > 0) {
          searchParams.set("selected", "true");
        } else {
          searchParams.delete("selected");
          // Clear from localStorage when empty
          localStorage.removeItem("selectedAssets");
        }
        setSearchParams(searchParams);

        return newSelectedAssets;
      });
    },
    [searchParams, setSearchParams, getAssetId, getAssetName, getAssetType],
  );

  // Handle removing a single asset from selection
  const handleRemoveAsset = useCallback(
    (assetId: string) => {
      console.log("Removing single asset from selection:", assetId);
      setSelectedAssets((prev) => {
        const newSelectedAssets = prev.filter((item) => item.id !== assetId);

        // Update URL parameter
        if (newSelectedAssets.length > 0) {
          searchParams.set("selected", "true");
        } else {
          searchParams.delete("selected");
        }
        setSearchParams(searchParams);

        return newSelectedAssets;
      });
    },
    [searchParams, setSearchParams],
  );

  // Handle clearing all selections
  const handleClearSelection = useCallback(() => {
    setSelectedAssets([]);
    searchParams.delete("selected");
    setSearchParams(searchParams);
    localStorage.removeItem("selectedAssets");
  }, [searchParams, setSearchParams]);

  // Check if an asset is selected
  const isAssetSelected = useCallback(
    (assetId: string) => {
      return selectedAssets.some((item) => item.id === assetId);
    },
    [selectedAssets],
  );

  // Handle select all functionality - additive across pages
  const handleSelectAll = useCallback(
    (currentPageAssets: T[]) => {
      const currentPageAssetIds = currentPageAssets.map((asset) =>
        getAssetId(asset),
      );

      setSelectedAssets((prev) => {
        // Check if all current page assets are already selected
        const allCurrentPageSelected = currentPageAssetIds.every((id) =>
          prev.some((selected) => selected.id === id),
        );

        let newSelectedAssets;
        if (allCurrentPageSelected) {
          // If all current page assets are selected, deselect only the current page assets
          newSelectedAssets = prev.filter(
            (selected) => !currentPageAssetIds.includes(selected.id),
          );
        } else {
          // Add current page assets to selection (avoiding duplicates)
          const newAssets = currentPageAssets
            .filter(
              (asset) =>
                !prev.some((selected) => selected.id === getAssetId(asset)),
            )
            .map((asset) => ({
              id: getAssetId(asset),
              name: getAssetName(asset),
              type: getAssetType(asset),
              inventoryID: getAssetId(asset),
            }));

          newSelectedAssets = [...prev, ...newAssets];
        }

        // Update URL parameter based on new selection state
        if (newSelectedAssets.length > 0) {
          searchParams.set("selected", "true");
        } else {
          searchParams.delete("selected");
        }
        setSearchParams(searchParams);

        return newSelectedAssets;
      });
    },
    [searchParams, setSearchParams, getAssetId, getAssetName, getAssetType],
  );

  // Get select all state for current page
  const getSelectAllState = useCallback(
    (currentPageAssets: T[]): "none" | "some" | "all" => {
      if (selectedAssets.length === 0) return "none";

      const currentPageAssetIds = currentPageAssets.map((asset) =>
        getAssetId(asset),
      );
      const selectedCurrentPageAssets = currentPageAssetIds.filter((id) =>
        selectedAssets.some((selected) => selected.id === id),
      );

      if (selectedCurrentPageAssets.length === 0) return "none";
      if (selectedCurrentPageAssets.length === currentPageAssetIds.length)
        return "all";
      return "some";
    },
    [selectedAssets, getAssetId],
  );

  // Handle batch operations
  const handleBatchDelete = useCallback(() => {
    console.log("Batch delete:", selectedAssets);
    // Implement batch delete functionality
    // After deletion, clear selection
    handleClearSelection();
  }, [selectedAssets, handleClearSelection]);

  const handleBatchDownload = useCallback(async () => {
    if (selectedAssets.length === 0) {
      setModalState({
        open: true,
        status: "error",
        action: "Download Failed",
        message: "No assets selected for download",
      });
      return;
    }

    if (isDownloadLoading) {
      return; // Prevent multiple simultaneous requests
    }

    setIsDownloadLoading(true);

    // Show loading modal
    setModalState({
      open: true,
      status: "loading",
      action: "Starting bulk download...",
    });

    try {
      console.log("Starting batch download for:", selectedAssets);

      // Extract asset IDs from selected assets
      const assetIds = selectedAssets.map((asset) => asset.id);

      // Initiate bulk download
      const response = await bulkDownloadMutation.mutateAsync({
        assetIds,
        options: {
          format: "zip",
          includeMetadata: false,
        },
      });

      if (response.data?.jobId) {
        setBulkDownloadJobId(response.data.jobId);
        console.log("Bulk download job started:", response.data.jobId);

        // Success: Clear selection and close side panel
        handleClearSelection();

        // Show success modal
        setModalState({
          open: true,
          status: "success",
          action: "Download Started",
          message: `Bulk download started for ${selectedAssets.length} assets. You'll be notified when it's ready.`,
        });

        // Call the callback to close side panel if provided
        if (onDownloadSuccess) {
          onDownloadSuccess();
        }
      } else {
        throw new Error("No job ID returned from server");
      }
    } catch (error) {
      console.error("Failed to start bulk download:", error);

      // Show error message to user
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Failed to start bulk download. Please try again.";

      setModalState({
        open: true,
        status: "error",
        action: "Download Failed",
        message: errorMessage,
      });
    } finally {
      setIsDownloadLoading(false);
    }
  }, [
    selectedAssets,
    bulkDownloadMutation,
    isDownloadLoading,
    handleClearSelection,
    onDownloadSuccess,
  ]);

  const handleBatchShare = useCallback(() => {
    console.log("Batch share:", selectedAssets);
    // Implement batch share functionality
  }, [selectedAssets]);

  const handleModalClose = useCallback(() => {
    setModalState((prev) => ({ ...prev, open: false }));
  }, []);

  return {
    selectedAssets,
    selectedAssetIds: selectedAssets.map((asset) => asset.id),
    handleSelectToggle,
    handleRemoveAsset,
    handleClearSelection,
    isAssetSelected,
    handleSelectAll,
    getSelectAllState,
    handleBatchDelete,
    handleBatchDownload,
    handleBatchShare,
    // Bulk download state
    bulkDownloadJobId,
    isDownloadInProgress: !!bulkDownloadJobId,
    isDownloadLoading,
    // Modal state
    modalState,
    handleModalClose,
  };
}
