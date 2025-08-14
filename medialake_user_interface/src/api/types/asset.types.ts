export interface RelatedVersionsResponse {
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
        CreateDate: string;
      };
      DerivedRepresentations: Array<{
        Purpose: string;
        StorageInfo: {
          PrimaryLocation: {
            StorageType: string;
            Bucket: string;
            ObjectKey: {
              FullPath: string;
            };
          };
        };
      }>;
      FileHash: string;
      Metadata: {
        Consolidated: {
          type: string;
        };
      };
      score: number;
      thumbnailUrl?: string;
      proxyUrl?: string;
    }>;
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
