import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/apiClient';
import { API_ENDPOINTS } from '@/api/endpoints';
import { logger } from '@/common/helpers/logger';
import { QUERY_KEYS } from '@/api/queryKeys';
import axios from 'axios';

interface AssetExplorerParams {
    storageIdentifier?: string;
    page?: number;
    pageSize?: number;
}

interface AssetExplorerResponseData {
    items: Array<{
        id: string;
        filename: string;
        path: string;
        fullPath?: string;
        size: number;
        lastModified: string;
        contentType: string;
        thumbnailUrl?: string;
        presignedUrl?: string;
        metadata?: Record<string, any>;
    }>;
    folders: Array<string>;
    totalItems: number;
    nextContinuationToken?: string;
}

export interface AssetExplorerResponseType {
    status: string;
    message: string;
    data: AssetExplorerResponseData;
}

export interface AssetExplorerError extends Error {
    apiResponse?: AssetExplorerResponseType;
}

export const useAssetExplorer = ({
    storageIdentifier = '',
    page = 1,
    pageSize = 25
}: AssetExplorerParams) => {
        // Try alternative query formats if the standard one isn't working
        const constructQuery = () => {
            let query = '';
            
            // Always filter by Connector when storage identifier is provided
            if (storageIdentifier) {
                query = `connector:${storageIdentifier}`;
            }
            
            // Add sort by creation date
            if (query) query += ' ';
            query += `sort:desc:DigitalSourceAsset.CreateDate`;
            
            logger.info(`[AssetExplorer] Constructed query: ${query}`);
            return query;
        };

    return useQuery<AssetExplorerResponseType, AssetExplorerError>({
        queryKey: QUERY_KEYS.ASSETS.explorer(storageIdentifier, page, pageSize),
        queryFn: async ({ signal }) => {
            try {
                const query = constructQuery();
                logger.info(`[AssetExplorer] Executing search with query: ${query}`);
                
                // Log the full URL for debugging
                const searchUrl = `${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&page=${page}&pageSize=${pageSize}`;
                logger.info(`[AssetExplorer] Full search URL: ${searchUrl}`);
                
                const response = await apiClient.get<any>(
                    searchUrl,
                    { signal }
                );

                // Log the response for debugging
                logger.info(`[AssetExplorer] Search response:`, response.data);
                
                // Process the search results to match our expected format
                const searchResults = response.data?.data?.results || [];
                const processedData: AssetExplorerResponseData = {
                    items: [],
                    folders: [],
                    totalItems: response.data?.data?.searchMetadata?.totalResults || 0
                };
                // Process files
                searchResults.forEach((item: any) => {
                    // Extract ObjectKey information
                    const objectKey = item.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey || 
                                     item.ObjectKey || {};
                    
                    const fullPath = objectKey.FullPath || '';
                    const itemPath = objectKey.Path ? objectKey.Path + '/' : '';
                    const filename = objectKey.Name || '';
                    
                    // Skip if no fullPath
                    if (!fullPath) {
                        return;
                    }
                    
                    // Extract the path parts
                    const pathParts = fullPath.split('/');
                
                    // Always add the item directly for latest assets
                    processedData.items.push({
                        id: item.InventoryID || item.id || fullPath,
                        filename: filename,
                        path: itemPath,
                        fullPath: fullPath,
                        size: item.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 
                              item.size || 0,
                        lastModified: item.DigitalSourceAsset?.CreateDate || 
                                     item.lastModified || 
                                     new Date().toISOString(),
                        contentType: item.contentType || 'application/octet-stream',
                        thumbnailUrl: item.thumbnailUrl,
                        presignedUrl: item.proxyUrl,
                        metadata: item.Metadata || item.metadata
                    });
                });
                
                return {
                    status: response.data.status || '200',
                    message: response.data.message || 'Success',
                    data: processedData
                };
            } catch (error) {
                logger.error('Asset Explorer error:', error);
                
                // Handle axios errors
                if (axios.isAxiosError(error) && error.response?.data) {
                    const apiError = new Error(
                        error.response.data.message || 'Asset Explorer request failed'
                    ) as AssetExplorerError;
                    apiError.apiResponse = error.response.data;
                    throw apiError;
                }
                
                // Rethrow the error to be handled by the component
                throw error;
            }
        },
        staleTime: 1000 * 60, // Cache for 1 minute
        gcTime: 1000 * 60 * 5 // Keep unused data for 5 minutes
    });
};
