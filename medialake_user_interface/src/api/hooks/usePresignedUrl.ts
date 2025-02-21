import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../apiClient';

interface GeneratePresignedUrlParams {
    inventoryId: string;
    expirationTime?: number;
}

interface PresignedUrlResponse {
    presigned_url: string;
    expires_in: number;
    asset_id: string;
}

export const useGeneratePresignedUrl = () => {
    return useMutation({
        mutationFn: async ({ inventoryId, expirationTime }: GeneratePresignedUrlParams) => {
            const response = await apiClient.post<{ data: PresignedUrlResponse }>(
                '/assets/generate-presigned-url',
                {
                    inventory_id: inventoryId,
                    expiration_time: expirationTime
                }
            );
            return response.data.data;
        }
    });
};
