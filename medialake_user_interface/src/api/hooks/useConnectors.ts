// src/api/hooks/useConnectors.ts

import { useQuery } from '@tanstack/react-query';
import axiosClient from '../axiosClient';
import { API_ENDPOINTS } from '../endpoints';
import { QUERY_KEYS } from '../queryKeys';

type S3BucketsResponse = {
    buckets: string[];
    count: number;
};

export const useGetS3Buckets = () => {
    return useQuery<S3BucketsResponse, Error>({
        queryKey: [QUERY_KEYS.CONNECTORS, 's3list'],
        queryFn: async () => {
            try {
                const response = await axiosClient.get<S3BucketsResponse>(`${API_ENDPOINTS.CONNECTORS}/s3list`);
                return response.data;
            } catch (error) {
                if (error instanceof Error) {
                    throw error;
                }
                throw new Error('Failed to fetch S3 buckets');
            }
        },
    });
};
