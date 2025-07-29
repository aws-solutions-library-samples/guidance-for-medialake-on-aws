import React from "react";
import { ImageItem, CardFieldConfig } from "@/types/search/searchResults";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import AssetResults from "@/components/shared/AssetResults";
import { formatFileSize } from "@/utils/fileSize";
import { formatDate } from "@/utils/dateFormat";
import { RecentlyViewedProvider } from "@/contexts/RecentlyViewedContext";
import { PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";

interface ImageResultsProps {
  images: ImageItem[];
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
  { id: "fileSize", label: "File Size", visible: false },
];

const defaultColumns: AssetTableColumn<ImageItem>[] = [
  {
    id: "name",
    label: "Object Name",
    visible: true,
    minWidth: 300,
    accessorFn: (image) =>
      image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name,
    cell: (info) => info.getValue() as string,
  },
  {
    id: "format",
    label: "Format",
    visible: true,
    minWidth: 100,
    accessorFn: (image) => image.DigitalSourceAsset.MainRepresentation.Format,
    cell: (info) => info.getValue() as string,
  },
  {
    id: "createDate",
    label: "Date Created",
    visible: true,
    minWidth: 160,
    accessorFn: (image) => image.DigitalSourceAsset.CreateDate,
    cell: (info) => formatDate(info.getValue() as string),
  },
  {
    id: "fileSize",
    label: "Size",
    visible: false,
    minWidth: 100,
    accessorFn: (image) =>
      image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
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

const renderCardField = (fieldId: string, image: ImageItem): string => {
  switch (fieldId) {
    case "name":
      return image.DigitalSourceAsset.MainRepresentation.StorageInfo
        .PrimaryLocation.ObjectKey.Name;
    case "format":
      return image.DigitalSourceAsset.MainRepresentation.Format;
    case "createDate":
      return formatDate(image.DigitalSourceAsset.CreateDate);
    case "fileSize":
      return formatFileSize(
        image.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
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

const ImageResults: React.FC<ImageResultsProps> = ({
  images,
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
        assets={images}
        searchMetadata={searchMetadata}
        onPageChange={onPageChange}
        config={{
          assetType: "Image",
          defaultCardFields,
          defaultColumns,
          sortOptions,
          renderCardField,
          placeholderImage: PLACEHOLDER_IMAGE,
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

export default ImageResults;
