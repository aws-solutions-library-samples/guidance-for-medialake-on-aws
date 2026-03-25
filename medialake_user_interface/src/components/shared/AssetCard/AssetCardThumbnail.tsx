/**
 * AssetCardThumbnail — renders the thumbnail area (image or video/audio player container).
 *
 * Renders the player div when the card is in viewport (so the hook has a DOM target),
 * but keeps the thumbnail image on top until the player has fully loaded.
 * Once isPlayerActive is true, the player div takes visual priority.
 */
import React, { useCallback, useMemo } from "react";
import { Box } from "@mui/material";
import { Theme } from "@mui/material/styles";
import { PLACEHOLDER_IMAGE, VIDEO_PLACEHOLDER_IMAGE } from "@/utils/placeholderSvg";

interface AssetCardThumbnailProps {
  id: string;
  name: string;
  assetType?: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  thumbnailScale: "fit" | "fill";
  height: number | string;
  playerId: string;
  videoLoadError: boolean;
  isMediaAsset: boolean;
  isPlayerActive: boolean;
  isInViewport: boolean;
  placeholderImage?: string;
  onAssetClick: () => void;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
}

const createImageErrorHandler =
  (assetType?: string, placeholderImage?: string) =>
  (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
    event.currentTarget.src =
      assetType === "Video" ? VIDEO_PLACEHOLDER_IMAGE : placeholderImage ?? PLACEHOLDER_IMAGE;
  };

const AssetCardThumbnail: React.FC<AssetCardThumbnailProps> = React.memo(
  ({
    id,
    name,
    assetType,
    thumbnailUrl,
    proxyUrl,
    thumbnailScale,
    height,
    playerId,
    videoLoadError,
    isMediaAsset,
    isPlayerActive,
    isInViewport,
    placeholderImage = PLACEHOLDER_IMAGE,
    onAssetClick,
    onImageError,
  }) => {
    const defaultImageErrorHandler = useCallback(
      createImageErrorHandler(assetType, placeholderImage),
      [assetType, placeholderImage]
    );

    const imgSx = useMemo(
      () => ({
        cursor: "pointer",
        width: "100%",
        height: "100%",
        objectFit: thumbnailScale === "fit" ? ("contain" as const) : ("cover" as const),
      }),
      [thumbnailScale]
    );

    // Render the player div when in viewport (so the DOM target exists for the hook),
    // but keep the thumbnail image on top until the player has actually loaded.
    const shouldRenderPlayerDiv = isMediaAsset && proxyUrl && !videoLoadError && isInViewport;

    return (
      <Box sx={{ p: 0, pb: 0, position: "relative" }}>
        <Box
          sx={{
            height,
            overflow: "hidden",
            bgcolor: (theme: Theme) => `${theme.palette.primary.main}0a`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
          }}
        >
          {/* Player div — rendered on hover so the DOM target exists for OmakasePlayer init */}
          {shouldRenderPlayerDiv && (
            <div
              id={`${assetType?.toLowerCase()}-asset-${id}`}
              className={`asset-card-${assetType?.toLowerCase()}`}
              style={{
                width: "100%",
                height: "100%",
                backgroundColor: "rgba(0,0,0,0.03)",
                cursor: "pointer",
                position: "absolute",
                top: 0,
                left: 0,
                zIndex: isPlayerActive ? 1 : 0,
              }}
            >
              <div id={playerId} style={{ width: "100%", height: "100%" }} />
            </div>
          )}

          {/* Thumbnail image — always rendered, sits on top until player is active */}
          {!isPlayerActive && (
            <Box
              onClick={onAssetClick}
              component="img"
              src={
                isMediaAsset
                  ? thumbnailUrl || VIDEO_PLACEHOLDER_IMAGE
                  : thumbnailUrl || placeholderImage
              }
              alt={name}
              onError={onImageError || defaultImageErrorHandler}
              data-image-id={id}
              sx={{
                ...imgSx,
                position: shouldRenderPlayerDiv ? "relative" : undefined,
                zIndex: shouldRenderPlayerDiv ? 1 : undefined,
              }}
            />
          )}
        </Box>
      </Box>
    );
  }
);

AssetCardThumbnail.displayName = "AssetCardThumbnail";
export default AssetCardThumbnail;
