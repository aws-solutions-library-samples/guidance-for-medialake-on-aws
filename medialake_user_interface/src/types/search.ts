export interface SearchFilters {
  creationDate?: {
    before?: string;
    after?: string;
  };
  media?: {
    video?: string[];
    images?: string[];
    audio?: string[];
  };
  metadata?: {
    title?: string[];
    rights?: string[];
  };
}

export interface SearchResult {
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
  proxyUrl: string | null;
}

export interface SearchResponse {
  status: string;
  message: string;
  data: {
    searchMetadata: {
      totalResults: number;
      page: number;
      pageSize: number;
      searchTerm: string;
      facets: {
        file_types: {
          doc_count_error_upper_bound: number;
          sum_other_doc_count: number;
          buckets: Array<{
            key: string;
            doc_count: number;
          }>;
        };
      };
    };
    results: SearchResult[];
  };
}

export interface SearchOptions {
  page?: number;
  pageSize?: number;
  filters?: SearchFilters;
}
