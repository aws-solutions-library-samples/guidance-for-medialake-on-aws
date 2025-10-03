export interface CardFieldConfig {
  id: string;
  label: string;
  visible: boolean;
}

interface DigitalSourceAsset {
  Type: string;
  CreateDate: string;
  ModifiedDate?: string;
  MainRepresentation: {
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
}

export interface AssetBase {
  InventoryID: string;
  DigitalSourceAsset: DigitalSourceAsset;
  thumbnailUrl?: string;
  proxyUrl?: string;
  score?: number; // Score for semantic search results (0.000 to 1.000)
}

export interface ImageItem extends AssetBase {
  DigitalSourceAsset: DigitalSourceAsset & {
    Type: "Image";
    MainRepresentation: {
      Format: string;
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: string;
            FullPath: string;
          };
          FileInfo: { Size: number };
        };
      };
    };
  };
}

export interface VideoItem extends AssetBase {
  DigitalSourceAsset: DigitalSourceAsset & {
    Type: "Video";
    MainRepresentation: {
      Format: string;
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: string;
            FullPath: string;
          };
          FileInfo: { Size: number };
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
  DigitalSourceAsset: DigitalSourceAsset & {
    Type: "Audio";
    MainRepresentation: {
      Format: string;
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: string;
            FullPath: string;
          };
          FileInfo: { Size: number };
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
