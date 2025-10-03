import React from "react";
import { VIDEO_PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";
import { VideoItem, CardFieldConfig } from "@/types/search/searchResults";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import AssetResults from "@/components/shared/AssetResults";
import { formatFileSize } from "@/utils/fileSize";
import { formatDate } from "@/utils/dateFormat";
import { RecentlyViewedProvider } from "@/contexts/RecentlyViewedContext";

interface VideoResultsProps {
  videos: VideoItem[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  searchTerm: string;
  cardSize: "small" | "medium" | "large";
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  aspectRatio: "vertical" | "square" | "horizontal";
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

const defaultCardFields: CardFieldConfig[] = [
  { id: "name", label: "Object Name", visible: true },
  { id: "format", label: "Format", visible: true },
  { id: "createDate", label: "Date Created", visible: true },
  { id: "fileSize", label: "File Size", visible: true },
];

const defaultColumns: AssetTableColumn<VideoItem>[] = [
  {
    id: "name",
    label: "Object Name",
    visible: true,
    minWidth: 300,
    accessorFn: (video) =>
      video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name,
    cell: (info) => info.getValue() as string,
  },
  {
    id: "format",
    label: "Format",
    visible: true,
    minWidth: 100,
    accessorFn: (video) => video.DigitalSourceAsset.MainRepresentation.Format,
    cell: (info) => info.getValue() as string,
  },
  {
    id: "createDate",
    label: "Date Created",
    visible: true,
    minWidth: 160,
    accessorFn: (video) => video.DigitalSourceAsset.CreateDate,
    cell: (info) => formatDate(info.getValue() as string),
  },
  {
    id: "fileSize",
    label: "Size",
    visible: false,
    minWidth: 100,
    accessorFn: (video) =>
      video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .FileInfo.Size,
    cell: (info) => formatFileSize(info.getValue() as number),
  },
];

const sortOptions = [
  { id: "createDate", label: "Date Created" },
  { id: "name", label: "Object Name" },
  { id: "format", label: "Format" },
  { id: "fileSize", label: "File Size" },
];

const renderCardField = (fieldId: string, video: VideoItem): string => {
  switch (fieldId) {
    case "name":
      return video.DigitalSourceAsset.MainRepresentation.StorageInfo
        .PrimaryLocation.ObjectKey.Name;
    case "format":
      return video.DigitalSourceAsset.MainRepresentation.Format;
    case "createDate":
      return formatDate(video.DigitalSourceAsset.CreateDate);
    case "fileSize":
      return formatFileSize(
        video.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .FileInfo.Size,
      );
    default:
      return "";
  }
};

const actions = [
  { id: "rename", label: "Rename" },
  { id: "download", label: "Download" },
  { id: "share", label: "Share" },
];

const VideoResults: React.FC<VideoResultsProps> = ({
  videos,
  searchMetadata,
  onPageChange,
  searchTerm,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange,
  onPageSizeChange,
}) => {
  return (
    <RecentlyViewedProvider>
      <AssetResults
        assets={videos}
        searchMetadata={searchMetadata}
        onPageChange={onPageChange}
        config={{
          assetType: "Video",
          defaultCardFields,
          defaultColumns,
          sortOptions,
          renderCardField,
          placeholderImage: VIDEO_PLACEHOLDER_IMAGE,
        }}
        searchTerm={searchTerm}
        actions={actions}
        cardSize={cardSize}
        onCardSizeChange={onCardSizeChange}
        aspectRatio={aspectRatio}
        onAspectRatioChange={onAspectRatioChange}
        thumbnailScale={thumbnailScale}
        onThumbnailScaleChange={onThumbnailScaleChange}
        showMetadata={showMetadata}
        onShowMetadataChange={onShowMetadataChange}
        onPageSizeChange={onPageSizeChange}
      />
    </RecentlyViewedProvider>
  );
};

export default VideoResults;
