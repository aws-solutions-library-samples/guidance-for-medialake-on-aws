export interface CardFieldConfig {
    id: string;
    label: string;
    visible: boolean;
}

export interface AssetBase {
    InventoryID: string;
    thumbnailUrl?: string;
    proxyUrl?: string;
    DigitalSourceAsset: {
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
}

export interface ImageItem extends AssetBase {
    DigitalSourceAsset: {
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
}

export interface VideoItem extends AssetBase {
    DigitalSourceAsset: {
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
            TechnicalMetadata: {
                Duration: number;
                Width: number;
                Height: number;
            };
        };
    };
}

export interface AudioItem extends AssetBase {
    DigitalSourceAsset: {
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
            TechnicalMetadata: {
                Duration: number;
                BitRate: number;
                SampleRate: number;
                Channels: number;
            };
        };
    };
}
