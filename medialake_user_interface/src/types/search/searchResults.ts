export interface ImageItem {
    InventoryID: string;
    DigitalSourceAsset: {
        Type: string;
        MainRepresentation: {
            Type: string;
            Format: string;
            StorageInfo: {
                PrimaryLocation: {
                    Status: string;
                    StorageType: string;
                    FileInfo: {
                        Size: number;
                        Hash: {
                            Value: string;
                            MD5Hash: string;
                            Algorithm: string;
                        };
                        CreateDate: string;
                    };
                    Bucket: string;
                    ObjectKey: {
                        Path: string;
                        FullPath: string;
                        Name: string;
                    };
                };
            };
            Purpose: string;
            ID: string;
        };
        ID: string;
        CreateDate: string;
    };
    FileHash: string;
    Metadata: {
        Embedded: {
            S3: {
                LastModified: string;
                ContentType: string;
                Metadata: Record<string, any>;
            };
            ExtractedDate: string;
        };
    };
    score: number;
    thumbnailUrl: string;
}


export interface SearchResults {
    images: ImageItem[];
    total: number;
}

export interface ImageResultsProps {
    images: ImageItem[];
    searchMetadata: SearchMetadata;
    onPageChange: (page: number) => void;
}

export interface ImageToRename {
    image: ImageItem;
    newName: string;
}

export interface ColumnConfig {
    id: string;
    label: string;
    visible: boolean;
    minWidth?: number;
    align?: 'right' | 'left' | 'center';
    format?: (value: any) => string;
}

export interface CardFieldConfig {
    id: string;
    label: string;
    visible: boolean;
}

export type Order = 'asc' | 'desc';
export type OrderBy = 'name' | 'format' | 'createDate' | 'fileSize' | 'dimensions';

export interface SearchMetadata {
    totalResults: number;
    page: number;
    pageSize: number;
    searchTerm: string;
    facets?: {
        file_types: {
            doc_count_error_upper_bound: number;
            sum_other_doc_count: number;
            buckets: Array<{
                key: string;
                doc_count: number;
            }>;
        };
    };
}
