import React from "react";
import { Box } from "@mui/material";
import {
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";
import ImageResults from "./ImageResults";
import VideoResults from "./VideoResults";
import AudioResults from "./AudioResults";

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
};

interface UnifiedAssetResultsProps {
  results: AssetItem[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  searchTerm: string;
  groupByType: boolean;
  cardSize: "small" | "medium" | "large";
  onCardSizeChange: (size: "small" | "medium" | "large") => void;
  aspectRatio: "vertical" | "square" | "horizontal";
  onAspectRatioChange: (ratio: "vertical" | "square" | "horizontal") => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  onAssetClick: (asset: AssetItem) => void;
  onDeleteClick: (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => void;
  onMenuClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => void;
  onPageSizeChange: (newPageSize: number) => void;
}

const UnifiedAssetResults: React.FC<UnifiedAssetResultsProps> = ({
  results,
  searchMetadata,
  onPageChange,
  searchTerm,
  groupByType,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange,
  onAssetClick,
  onDeleteClick,
  onMenuClick,
  onEditClick,
  onPageSizeChange,
}) => {
  // Split results by type if grouping is enabled
  const imageResults = results.filter(
    (item) => item.DigitalSourceAsset.Type === "Image",
  ) as ImageItem[];
  const videoResults = results.filter(
    (item) => item.DigitalSourceAsset.Type === "Video",
  ) as VideoItem[];
  const audioResults = results.filter(
    (item) => item.DigitalSourceAsset.Type === "Audio",
  ) as AudioItem[];

  const commonProps = {
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
    onAssetClick,
    onDeleteClick,
    onMenuClick,
    onEditClick,
    onPageSizeChange,
  };

  if (groupByType) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {imageResults.length > 0 && (
          <Box
            sx={{
              "& .MuiPaper-root": {
                bgcolor: "transparent",
                boxShadow: "none",
                p: 0,
              },
            }}
          >
            <ImageResults images={imageResults} {...commonProps} />
          </Box>
        )}
        {videoResults.length > 0 && (
          <Box
            sx={{
              "& .MuiPaper-root": {
                bgcolor: "transparent",
                boxShadow: "none",
                p: 0,
              },
            }}
          >
            <VideoResults videos={videoResults} {...commonProps} />
          </Box>
        )}
        {audioResults.length > 0 && (
          <Box
            sx={{
              "& .MuiPaper-root": {
                bgcolor: "transparent",
                boxShadow: "none",
                p: 0,
              },
            }}
          >
            <AudioResults audios={audioResults} {...commonProps} />
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        "& .MuiPaper-root": {
          bgcolor: "transparent",
          boxShadow: "none",
          p: 0,
        },
      }}
    >
      <ImageResults images={results as ImageItem[]} {...commonProps} />
    </Box>
  );
};

export default UnifiedAssetResults;
