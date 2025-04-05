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

interface RelatedVersionHit {
    InventoryID: string;
    DigitalSourceAsset: {
        ID: string;
        Type: string;
        CreateDate: string;
        MainRepresentation: {
            Format: string;
            StorageInfo: {
                PrimaryLocation: {
                    ObjectKey: {
                        Name: string;
                    };
                    FileInfo: {
                        Size: number;
                    };
                };
            };
        };
    };
    thumbnailUrl?: string;
    proxyUrl?: string;
    score: number;
}

interface TranscriptionResponse {
    status: string;
    message: string;
    data: {
        jobName: string;
        status: string;
        results: {
            language_code: string;
            transcripts: Array<{
                transcript: string;
            }>;
            items: Array<{
                id: number;
                start_time: number;
                end_time: number;
                type: string;
                alternatives: Array<{
                    confidence: string;
                    content: string;
                }>;
            }>;
        }
    };
}

export interface RelatedVersionsResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: {
            totalResults: number;
            page: number;
            pageSize: number;
            searchTerm: string;
        };
        results: Array<{
            InventoryID: string;
            DigitalSourceAsset: {
                Type: string;
                MainRepresentation: {
                    Format: string;
                    StorageInfo: {
                        PrimaryLocation: {
                            FileInfo: {
                                Size: number;
                                Hash?: {
                                    Value: string;
                                    MD5Hash: string;
                                    Algorithm: string;
                                };
                                CreateDate: string;
                            };
                            ObjectKey: {
                                Path: string;
                                FullPath: string;
                                Name: string;
                            };
                        };
                    };
                };
                CreateDate: string;
            };
            DerivedRepresentations: Array<{
                StorageInfo: {
                    PrimaryLocation: {
                        Status: string;
                        StorageType: string;
                        FileInfo: {
                            Size: number;
                        };
                        Bucket: string;
                        ObjectKey: {
                            FullPath: string;
                        };
                        Provider: string;
                    };
                };
                Purpose: string;
            }>;
            FileHash: string;
            Metadata: Record<string, any>;
            score: number;
            thumbnailUrl: string;
            proxyUrl: string;
        }>;
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
        onSuccess: (data, variables) => {
            // Update the specific asset cache
            queryClient.setQueryData(
                QUERY_KEYS.ASSETS.detail(variables.inventoryId),
                data
            );

            // Update asset in any search results cache
            queryClient.getQueriesData({ queryKey: QUERY_KEYS.SEARCH.all }).forEach(([queryKey, queryData]: any) => {
                if (queryData?.data?.results) {
                    // Filter out any possible duplicates by InventoryID and update the target asset
                    const updatedResults = queryData.data.results
                        .filter((asset: any) => 
                            // Keep only one instance of the renamed asset
                            // (in case there's a duplicate with the same ID)
                            asset.InventoryID !== variables.inventoryId || 
                            asset === queryData.data.results.find((a: any) => a.InventoryID === variables.inventoryId)
                        )
                        .map((asset: any) => {
                            if (asset.InventoryID === variables.inventoryId) {
                                // Create a deep copy of the asset
                                const updatedAsset = JSON.parse(JSON.stringify(asset));
                                // Update the name property
                                updatedAsset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name = variables.newName;
                                return updatedAsset;
                            }
                            return asset;
                        });
                    
                    // Update the cache with the modified results
                    queryClient.setQueryData(queryKey, {
                        ...queryData,
                        data: {
                            ...queryData.data,
                            results: updatedResults
                        }
                    });
                }
            });

            // Removed invalidation to avoid eventual consistency issues
        },
        onError: (error) => {
            logger.error('Error in rename mutation:', error);
            showError('Failed to rename asset');
        },
    });
};

export const useRelatedVersions = (assetId: string, page: number = 1, pageSize: number = 50) => {
    console.log('useRelatedVersions - Called with assetId:', assetId, 'page:', page);
    
    return useQuery<RelatedVersionsResponse, Error>({
        queryKey: ['relatedVersions', assetId, page, pageSize],
        queryFn: async (): Promise<RelatedVersionsResponse> => {
            console.log('useRelatedVersions - Fetching data for assetId:', assetId);
            const response = await apiClient.get<RelatedVersionsResponse>(`/assets/${assetId}/relatedversions`, {
                params: {
                    page,
                    pageSize,
                    min_score: 0.01
                }
            });
            console.log('useRelatedVersions - Received response:', response.data);
            return response.data;
        },
        enabled: !!assetId,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};

// Hook to get a single asset by ID
export const useTranscription = (inventoryId: string) => {
    const { showError } = useErrorModal();

    return useQuery({
        queryKey: QUERY_KEYS.ASSETS.detail(inventoryId),
        queryFn: async () => {
            try {
                const response = await apiClient.get<TranscriptionResponse>(`assets/${inventoryId}/transcript`);
                return response.data;
            } catch (error) {
                logger.error('Error fetching asset transcript:', error);
                showError('Failed to fetch asset transcript');
                throw error;
            }
        },
        enabled: !!inventoryId,
        retry: 1,
    });
};

// Export types for use in components
export type { Asset, AssetResponse, DeleteAssetResponse, TranscriptionResponse };