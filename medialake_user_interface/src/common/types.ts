export interface NavigationPanelState {
  collapsed?: boolean;
  collapsedSections?: Record<number, boolean>;
}

export enum SearchType {
  ASSETS = "assets",
  TITLE = "title",
  RIGHTS = "rights",
  QC = "qc",
}

export enum AssetType {
  VIDEO = "video",
  CLIP = "clip",
}

export interface Query {
  query: string;
  search_types: SearchType[];
}

export interface SearchResult {
  status: boolean;
  data: {
    Assets: {
      clips: Asset[];
      videos: Asset[];
    };
    Rights: {
      right: RightItem[];
    };
    Titles: {
      title: TitleItem[];
    };
  };
}

export interface RightItem {
  rightsId: number;
  recordId: string;
  title: string;
  catalogId: string;
  rightsStatus: string;
  dealStatus: string;
  rightsStartDate: string;
  rightsEndDate: string;
  rightsTerritory: string;
  rightsLanguages: string;
  rightsMedia: string;
  contentType: string;
  deliveryPlatform: string;
  score: number;
}

export interface VideoItem {
  assetId: string;
  recordId: string;
  name: string;
  dateCreated: string;
  duration: string;
  videoFormat: string;
  audioFormat: string;
  audioChannels: string;
  sourceLocation: {
    bucket: string;
    path: string;
  };
  score: number;
  timecode: string;
  frameRate: number;
  frameCount: number;
  type: string;
  startTime?: number;
  endTime?: number;
}

export interface ClipItem {
  assetId: string;
  recordId: string;
  clipScore: number;
  inSeconds: number;
  outSeconds: number;
  startTime?: number;
  endTime?: number;
  type: string;
}

export interface Asset {
  score: number;
  recordId: string;
  source: {
    assetId: string;
    type: string;
    name: string;
    startTime?: number;
    endTime?: number;
    dateCreated: string;
    sourceLocation: {
      bucket: string;
      path: string;
    };
    encoding: {
      Video?: {
        Duration?: number;
        Format?: string;
        FrameRate?: number;
        FrameCount?: number;
      };
      Audio?: {
        Duration?: number;
        Format?: string;
        Channels?: number;
      };
      Container?: {
        Duration?: number;
      };
    };
  };
}

export interface TitleItem {
  recordId: string;
  score: number;
  titleId: string;
  type: string;
  tenantCode: string;
  parentIds: string[];
  parentContentType: string;
  name: string;
  releaseYear: string;
  contentType: string;
  contentSubType: string;
  metadataStatus: string;
  categories: string[];
  eidrTitleId: string;
  msvAssociationId: string[];
  countryOfOrigin: string;
  boxOfficeOpen: boolean;
  animated: boolean;
  originalLanguage: string;
  castCrew: {
    id: string;
    name: string;
    nameEn: string;
    language: string;
    personType: string;
    order: number;
  }[];
  imdbLink: string;
  seriesTitleName?: string;
  totalNumberOfEpisodes?: number;
  seasonNumber?: string;
  embedding: any[];
}

export interface Review {
  reviewID: string;
  status: string;
  type: string;
  createdDate: string;
  ingestedAsset: {
    name: string;
    sourceLocation: {
      bucket: string;
      path: string;
    };
    id: string;
  };
  similarAssets: Array<{
    id: string;
    name: string;
    cosineSimilarity: string;
    sourceLocation: {
      bucket: string;
      path: string;
    };
    clips: Array<{
      clipId: string;
      clipName: string;
      cosineSimilarity: string;
      timeRange: {
        startTime: string;
        stopTime: string;
      };
    }>;
  }>;
}

export interface ReviewsResponse {
  status: boolean;
  reviews: Review[];
}

export interface PatchReviewResponse {
  status: boolean;
  updated_review: Review;
}
