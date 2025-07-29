export interface AssetStorageInfo {
  PrimaryLocation: {
    StorageType: string;
    Bucket: string;
    ObjectKey: {
      Name: string;
      Path: string;
      FullPath: string;
    };
    Status: string;
    FileInfo: {
      Size: number;
      Hash: {
        Algorithm: string;
        Value: string;
      };
      CreateDate: string;
    };
  };
}

export interface AssetMetadata {
  ObjectMetadata: {
    // ExtractedDate: string;
    S3: {
      // Metadata: Record<string, any>;
      ContentType: string;
      LastModified: string;
    };
  };
}

export interface AssetRepresentation {
  ID: string;
  Type: string;
  Format: string;
  Purpose: string;
  StorageInfo: AssetStorageInfo;
}

export interface DigitalSourceAsset {
  ID: string;
  Type: string;
  CreateDate: string;
  MainRepresentation: AssetRepresentation;
}

export interface AssetRecord {
  InventoryID: string;
  DigitalSourceAsset: DigitalSourceAsset;
  DerivedRepresentations?: AssetRepresentation[];
  Metadata?: AssetMetadata;
}
