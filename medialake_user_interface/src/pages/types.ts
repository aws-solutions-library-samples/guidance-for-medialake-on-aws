import {
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";

export type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
};

export interface LocationState {
  query?: string;
  isSemantic?: boolean;
  preserveSearch?: boolean;
  viewMode?: "card" | "table";
  cardSize?: "small" | "medium" | "large";
  aspectRatio?: "vertical" | "square" | "horizontal";
  thumbnailScale?: "fit" | "fill";
  showMetadata?: boolean;
  groupByType?: boolean;
  type?: string;
  extension?: string;
  LargerThan?: number;
  asset_size_lte?: number;
  asset_size_gte?: number;
  ingested_date_lte?: string;
  ingested_date_gte?: string;
  filename?: string;
}

export interface Filters {
  mediaTypes: {
    videos: boolean;
    images: boolean;
    audio: boolean;
  };
  time: {
    recent: boolean;
    lastWeek: boolean;
    lastMonth: boolean;
    lastYear: boolean;
  };
}

export interface ExpandedSections {
  mediaTypes: boolean;
  time: boolean;
  status: boolean;
}
