import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../apiClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';

type S3Bucket = string[];

export const useGetS3Buckets = () => {
    return useQuery<S3Bucket[], Error>({
        queryKey: [QUERY_KEYS.CONNECTORS, 's3list'],
        queryFn: async () => {
            try {
                const response = await apiClient.get<S3Bucket[]>(`${API_ENDPOINTS.CONNECTORS}/s3list`);
                return response.data;
            } catch (error) {
                throw new Error('Failed to fetch S3 buckets');
            }
        },
    });
};
