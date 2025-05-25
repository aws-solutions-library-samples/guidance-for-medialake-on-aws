import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useBulkDownload, useBulkDownloadStatus } from '@/api/hooks/useAssets';

/**
 * Hook for managing asset selection and bulk operations.
 *
 * To use with notifications for bulk downloads:
 *
 * ```typescript
 * import { useNotifications } from '@/components/NotificationCenter';
 * import { useProcessNotifications } from '@/hooks/useProcessNotifications';
 * import { useBulkDownloadStatus } from '@/api/hooks/useAssets';
 *
 * const { bulkDownloadJobId, handleBatchDownload } = useAssetSelection({...});
 * const { add: addNotification, dismiss: dismissNotification } = useNotifications();
 * const { data: downloadStatus } = useBulkDownloadStatus(bulkDownloadJobId || '', !!bulkDownloadJobId);
 *
 * useProcessNotifications({
 *   processId: bulkDownloadJobId,
 *   processType: 'bulk-download',
 *   status: downloadStatus?.data,
 *   addNotification,
 *   dismissNotification,
 * });
 * ```
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
}: {
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedAssets, setSelectedAssets] = useState<SelectedAsset[]>([]);
  const [bulkDownloadJobId, setBulkDownloadJobId] = useState<string | null>(null);
  
  // Bulk download hooks
  const bulkDownloadMutation = useBulkDownload();

  // Load selections from localStorage on component mount
  useEffect(() => {
    const savedSelections = localStorage.getItem('selectedAssets');
    if (savedSelections) {
      try {
        const parsedSelections = JSON.parse(savedSelections) as SelectedAsset[];
        if (Array.isArray(parsedSelections) && parsedSelections.length > 0) {
          setSelectedAssets(parsedSelections);
          
          // Update URL parameter
          searchParams.set('selected', 'true');
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
      localStorage.setItem('selectedAssets', JSON.stringify(selectedAssets));
    } else {
      localStorage.removeItem('selectedAssets');
    }
  }, [selectedAssets]);

  // Handle selection toggle
  const handleSelectToggle = useCallback((asset: T, event: React.MouseEvent<HTMLElement>) => {
    console.log('handleSelectToggle called with asset:', getAssetId(asset));
    
    const assetId = getAssetId(asset);
    const selectedAsset: SelectedAsset = {
      id: assetId,
      name: getAssetName(asset),
      type: getAssetType(asset),
      inventoryID: assetId
    };
    
    setSelectedAssets(prev => {
      // Check if this asset is already selected
      const isSelected = prev.some(item => item.id === assetId);
      const newSelectedAssets = isSelected
        ? prev.filter(item => item.id !== assetId)
        : [...prev, selectedAsset];
            
      // Update URL parameter
      if (newSelectedAssets.length > 0) {
        searchParams.set('selected', 'true');
      } else {
        searchParams.delete('selected');
        // Clear from localStorage when empty
        localStorage.removeItem('selectedAssets');
      }
      setSearchParams(searchParams);
      
      return newSelectedAssets;
    });
  }, [searchParams, setSearchParams, getAssetId, getAssetName, getAssetType]);

  // Handle removing a single asset from selection
  const handleRemoveAsset = useCallback((assetId: string) => {
    console.log('Removing single asset from selection:', assetId);
    setSelectedAssets(prev => {
      const newSelectedAssets = prev.filter(item => item.id !== assetId);
      
      // Update URL parameter
      if (newSelectedAssets.length > 0) {
        searchParams.set('selected', 'true');
      } else {
        searchParams.delete('selected');
      }
      setSearchParams(searchParams);
      
      return newSelectedAssets;
    });
  }, [searchParams, setSearchParams]);

  // Handle clearing all selections
  const handleClearSelection = useCallback(() => {
    setSelectedAssets([]);
    searchParams.delete('selected');
    setSearchParams(searchParams);
    localStorage.removeItem('selectedAssets');
  }, [searchParams, setSearchParams]);

  // Check if an asset is selected
  const isAssetSelected = useCallback((assetId: string) => {
    return selectedAssets.some(item => item.id === assetId);
  }, [selectedAssets]);

  // Handle batch operations
  const handleBatchDelete = useCallback(() => {
    console.log('Batch delete:', selectedAssets);
    // Implement batch delete functionality
    // After deletion, clear selection
    handleClearSelection();
  }, [selectedAssets, handleClearSelection]);

  const handleBatchDownload = useCallback(async () => {
    if (selectedAssets.length === 0) {
      console.warn('No assets selected for download');
      return;
    }

    try {
      console.log('Starting batch download for:', selectedAssets);
      
      // Extract asset IDs from selected assets
      const assetIds = selectedAssets.map(asset => asset.id);
      
      // Initiate bulk download
      const response = await bulkDownloadMutation.mutateAsync({
        assetIds,
        options: {
          format: 'zip',
          includeMetadata: false
        }
      });

      if (response.data?.jobId) {
        setBulkDownloadJobId(response.data.jobId);
        console.log('Bulk download job started:', response.data.jobId);
      }
    } catch (error) {
      console.error('Failed to start bulk download:', error);
    }
  }, [selectedAssets, bulkDownloadMutation]);

  const handleBatchShare = useCallback(() => {
    console.log('Batch share:', selectedAssets);
    // Implement batch share functionality
  }, [selectedAssets]);

  return {
    selectedAssets,
    selectedAssetIds: selectedAssets.map(asset => asset.id),
    handleSelectToggle,
    handleRemoveAsset,
    handleClearSelection,
    isAssetSelected,
    handleBatchDelete,
    handleBatchDownload,
    handleBatchShare,
    // Bulk download state
    bulkDownloadJobId,
    isDownloadInProgress: !!bulkDownloadJobId,
  };
}