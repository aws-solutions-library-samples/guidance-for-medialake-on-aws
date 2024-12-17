import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { QUERY_KEYS } from '@/api/queryKeys';
import { apiClient } from '@/api/apiClient';
import { logger } from '@/common/helpers/logger';
import { useErrorModal } from '@/hooks/useErrorModal';

interface Asset {
    asset: {
        InventoryID: string;
        DerivedRepresentations: Array<{
            Format: string;
            ID: string;
            Purpose: string;
            URL: string;
            StorageInfo: {
                PrimaryLocation: {
                    Bucket: string;
                    FileInfo: {
                        Size: number;
                    };
                    ObjectKey: {
                        FullPath: string;
                    };
                    Provider: string;
                    Status: string;
                    StorageType: string;
                };

            };
            Type: string;
            ImageSpec?: {
                Resolution: {
                    Height: number;
                    Width: number;
                };
            };
        }>;
        DigitalSourceAsset: {
            CreateDate: string;
            ID: string;
            MainRepresentation: {
                Format: string;
                ID: string;
                Purpose: string;
                StorageInfo: {
                    PrimaryLocation: {
                        Bucket: string;
                        FileInfo: {
                            CreateDate: string;
                            Hash: {
                                Algorithm: string;
                                Value: string;
                            };
                            Size: number;
                        };
                        ObjectKey: {
                            FullPath: string;
                            Name: string;
                            Path: string;
                        };
                        Status: string;
                        StorageType: string;
                    };
                };
            };
            Type: string;
        };
        Type: string;
        Metadata: {
            CustomMetadata: {
                EXIF: any;
                IPTC: any;
            };
        }
    },
}

interface AssetResponse {
    status: string;
    message: string;
    data: Asset;
}

interface DeleteAssetResponse {
    status: string;
    message: string;
    data: {
        InventoryID: string;
    };
}

// Hook to get a single asset by ID
export const useAsset = (inventoryId: string) => {
    const { showError } = useErrorModal();

    return useQuery({
        queryKey: QUERY_KEYS.ASSETS.detail(inventoryId),
        queryFn: async () => {
            try {
                const response = await apiClient.get<AssetResponse>(`assets/${inventoryId}`);
                return response.data;
            } catch (error) {
                logger.error('Error fetching asset details:', error);
                showError('Failed to fetch asset details');
                throw error;
            }
        },
        enabled: !!inventoryId,
        retry: 1,
    });
};

// Hook to delete an asset
export const useDeleteAsset = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation({
        mutationFn: async (inventoryId: string) => {
            try {
                const response = await apiClient.delete<DeleteAssetResponse>(`assets/${inventoryId}`);
                return response.data;
            } catch (error) {
                logger.error('Error deleting asset:', error);
                showError('Failed to delete asset');
                throw error;
            }
        },
        onSuccess: (_, inventoryId) => {
            queryClient.invalidateQueries({
                queryKey: QUERY_KEYS.ASSETS.all,
            });
            queryClient.removeQueries({
                queryKey: QUERY_KEYS.ASSETS.detail(inventoryId),
            });
            queryClient.invalidateQueries({
                queryKey: QUERY_KEYS.SEARCH.all,
            });
        },
        onError: (error) => {
            logger.error('Error in delete mutation:', error);
            showError('Failed to delete asset');
        },
    });
};

// Hook to rename an asset
export const useRenameAsset = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation({
        mutationFn: async ({ inventoryId, newName }: { inventoryId: string; newName: string }) => {
            try {
                const response = await apiClient.post<AssetResponse>(
                    `assets/${inventoryId}/rename`,
                    { newName }
                );
                return response.data;
            } catch (error) {
                logger.error('Error renaming asset:', error);
                showError('Failed to rename asset');
                throw error;
            }
        },
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({
                queryKey: QUERY_KEYS.ASSETS.detail(variables.inventoryId),
            });
            queryClient.invalidateQueries({
                queryKey: QUERY_KEYS.SEARCH.all,
            });
        },
        onError: (error) => {
            logger.error('Error in rename mutation:', error);
            showError('Failed to rename asset');
        },
    });
};

// Export types for use in components
export type { Asset, AssetResponse, DeleteAssetResponse };