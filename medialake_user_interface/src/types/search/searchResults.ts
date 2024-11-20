export interface ImageItem {
    inventoryId: string;
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
    score: number;
    thumbnailUrl: string | null;
}

export interface SearchResults {
    images: ImageItem[];
    total: number;
}

export interface ImageResultsProps {
    images: ImageItem[];
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
export type OrderBy = 'path' | 'format' | 'createDate' | 'fileSize' | 'dimensions';
