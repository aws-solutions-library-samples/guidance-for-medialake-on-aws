import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { QUERY_KEYS } from '../queryKeys';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { logger } from '../../common/helpers/logger';
import { useErrorModal } from '../../hooks/useErrorModal';


interface Asset {
    id: string;
    assetId: string;
    assetType: string;
    createDate: string;
    mainRepresentation: {
        id: string;
        type: string;
        format: string;
        purpose: string;
        storage: {
            storageType: string;
            bucket: string;
            path: string;
            status: string;
            fileSize: number;
            hashValue: string;
        };
        imageSpec?: {
            colorSpace: string | null;
            width: number | null;
            height: number | null;
            dpi: number | null;
        };
    };
    derivedRepresentations: Array<{
        id: string;
        type: string;
        format: string;
        purpose: string;
        storage: {
            storageType: string;
            bucket: string;
            path: string;
            status: string;
            fileSize: number;
            hashValue: string | null;
        };
        imageSpec?: {
            colorSpace: string | null;
            width: number | null;
            height: number | null;
            dpi: number | null;
        };
    }>;
    metadata: any;
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
        assetId: string;
    };
}

interface RenameAssetRequest {
    oldName: string;
    newName: string;
}

// Hook to get a single asset by ID
export const useAsset = (assetId: string) => {
    return useQuery({
        queryKey: QUERY_KEYS.ASSETS.detail(assetId),
        queryFn: async () => {
            const response = await apiClient.get<AssetResponse>(`/assets/${assetId}`);
            return response.data;
        },
        enabled: !!assetId,
    });
};

// Hook to delete an asset
export const useDeleteAsset = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (assetId: string) => {
            const response = await apiClient.delete<DeleteAssetResponse>(`/assets/${assetId}`);
            return response.data;
        },
        onSuccess: (_, assetId) => {
            // Invalidate relevant queries
            queryClient.invalidateQueries({
                queryKey: QUERY_KEYS.ASSETS.all,
            });
            queryClient.removeQueries({
                queryKey: QUERY_KEYS.ASSETS.detail(assetId),
            });
        },
    });
};

// Hook to rename an asset
export const useRenameAsset = () => {
    const queryClient = useQueryClient();
    const { showError } = useErrorModal();

    return useMutation({
        mutationFn: async ({ assetId, oldName, newName }: { assetId: string; oldName: string; newName: string }) => {
            try {
                const response = await apiClient.post<AssetResponse>(
                    `${API_ENDPOINTS.ASSETS}/${assetId}/rename`,
                    { oldName, newName }
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
                queryKey: QUERY_KEYS.ASSETS.detail(variables.assetId),
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