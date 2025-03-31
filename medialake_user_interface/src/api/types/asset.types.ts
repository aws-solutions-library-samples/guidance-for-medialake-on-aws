export interface RelatedVersionsResponse {
    data: {
        hits: Array<{
            InventoryID: string;
            DigitalSourceAsset: {
                ID: string;
                Type: string;
                CreateDate: string;
                MainRepresentation: {
                    ID: string;
                    Format: string;
                    StorageInfo: {
                        PrimaryLocation: {
                            ObjectKey: {
                                Name: string;
                                FullPath: string;
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
        }>;
        totalResults: number;
        page: number;
        pageSize: number;
    };
}

export interface Asset {
    InventoryID: string;
    DigitalSourceAsset: {
        ID: string;
        Type: string;
        CreateDate: string;
        MainRepresentation: {
            ID: string;
            Format: string;
            StorageInfo: {
                PrimaryLocation: {
                    ObjectKey: {
                        Name: string;
                        FullPath: string;
                    };
                    FileInfo: {
                        Size: number;
                    };
                };
            };
        };
        DerivedRepresentations: Array<{
            ID: string;
            Format: string;
            Purpose: string;
            StorageInfo: {
                PrimaryLocation: {
                    ObjectKey: {
                        Name: string;
                        FullPath: string;
                    };
                    FileInfo: {
                        Size: number;
                    };
                };
            };
            URL?: string;
        }>;
        Metadata?: any;
    };
    DerivedRepresentations: Array<{
        ID: string;
        Format: string;
        Purpose: string;
        StorageInfo: {
            PrimaryLocation: {
                ObjectKey: {
                    Name: string;
                    FullPath: string;
                };
                FileInfo: {
                    Size: number;
                };
            };
        };
        URL?: string;
    }>;
    Metadata?: any;
    relatedVersionsData?: RelatedVersionsResponse;
}

export interface AssetResponse {
    data: {
        asset: Asset;
    };
}

export interface RelatedItem {
    id: string;
    title: string;
    type: string;
    thumbnail?: string;
    proxyUrl?: string;
    score: number;
    format: string;
    fileSize: number;
    createDate: string;
} 