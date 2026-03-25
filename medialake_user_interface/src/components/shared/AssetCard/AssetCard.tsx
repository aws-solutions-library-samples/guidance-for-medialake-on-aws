/**
 * AssetCard — slim orchestrator that composes sub-components.
 * Decomposed from the original 1,519-line god component.
 *
 * Sub-components:
 * - AssetCardThumbnail: image/video/audio thumbnail rendering
 * - AssetCardActions: bottom action bar (full variant)
 * - AssetCardSelection: checkbox overlay for bulk selection
 * - AssetCardMetadata: field grid with inline editing (full variant)
 * - AssetCardCompactInfo: name + fields + menu (compact variant)
 * - useOmakasePlayer: video/audio player lifecycle hook
 */
import React, { useState, useEffect, useRef, useId, useMemo } from "react";
import { Box } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useSemanticMode } from "@/stores/searchStore";
import { getVisibleFields } from "@/utils/assetFieldMapping";
import type { AssetField } from "@/types/shared/assetComponents";
export type { AssetField };

import { useOmakasePlayer } from "./useOmakasePlayer";
import type { ClipData } from "./markerHelpers";
import AssetCardThumbnail from "./AssetCardThumbnail";
import AssetCardActions from "./AssetCardActions";
import AssetCardSelection from "./AssetCardSelection";
import AssetCardMetadata from "./AssetCardMetadata";
import AssetCardCompactInfo from "./AssetCardCompactInfo";

export interface AssetCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  proxyUrl?: string;
  assetType?: string;
  clips?: ClipData[];
  fields: AssetField[];
  isRenaming?: boolean;
  renderField: (fieldId: string) => string | React.ReactNode;
  onAssetClick: () => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (event: React.MouseEvent<HTMLElement>) => void;
  showRemoveButton?: boolean;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  placeholderImage?: string;
  onImageError?: (event: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  isEditing?: boolean;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean, value?: string) => void;
  cardSize?: "small" | "medium" | "large";
  aspectRatio?: "vertical" | "square" | "horizontal";
  thumbnailScale?: "fit" | "fill";
  showMetadata?: boolean;
  menuOpen?: boolean;
  isFavorite?: boolean;
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void;
  isSelected?: boolean;
  onSelectToggle?: (id: string, event: React.MouseEvent<HTMLElement>) => void;
  selectedSearchFields?: string[];
  isSemantic?: boolean;
  confidenceThreshold?: number;
  variant?: "compact" | "full";
}

const AssetCard = React.memo<AssetCardProps>(
  ({
    id,
    name,
    thumbnailUrl,
    proxyUrl,
    assetType,
    clips,
    fields,
    renderField,
    onAssetClick,
    onDeleteClick,
    onDownloadClick,
    onAddToCollectionClick,
    showRemoveButton = false,
    onEditClick,
    placeholderImage,
    onImageError,
    isRenaming = false,
    isEditing,
    editedName,
    onEditNameChange,
    onEditNameComplete,
    cardSize = "medium",
    aspectRatio = "square",
    thumbnailScale = "fill",
    showMetadata = true,
    menuOpen = false,
    isFavorite = false,
    onFavoriteToggle,
    isSelected = false,
    onSelectToggle,
    selectedSearchFields,
    isSemantic = false,
    confidenceThreshold = 0.57,
    variant = "full",
  }) => {
    const [isHovering, setIsHovering] = useState(false);
    const cardContainerRef = useRef<HTMLDivElement>(null);
    const reactId = useId();
    const instanceSuffix = reactId.replace(/:/g, "-");

    const semanticMode = useSemanticMode();
    const isClipMode = isSemantic && semanticMode === "clip";
    const isCompact = variant === "compact";

    // Omakase player lifecycle (video/audio only)
    // Auto-loads in visual order when card enters viewport, destroys on scroll-out
    const { isInViewport, videoLoadError, playerId, isMediaAsset, isPlayerActive } =
      useOmakasePlayer({
        id,
        instanceSuffix,
        assetType,
        proxyUrl,
        thumbnailUrl,
        thumbnailScale,
        clips,
        isSemantic,
        confidenceThreshold,
        variant,
        cardContainerRef,
      });

    const visibleFields = useMemo(
      () => getVisibleFields(fields, selectedSearchFields),
      [fields, selectedSearchFields]
    );

    // Card dimensions
    const thumbnailHeight = isCompact
      ? 140
      : (() => {
          const baseHeight =
            aspectRatio === "vertical" ? 300 : aspectRatio === "square" ? 200 : 150;
          const multiplier = cardSize === "small" ? 0.8 : cardSize === "large" ? 1.4 : 1.1;
          return baseHeight * multiplier;
        })();

    return (
      <Box
        ref={cardContainerRef}
        sx={{
          position: "relative",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          cursor: "pointer",
          borderRadius: 3,
          overflow: "hidden",
          border: "1px solid",
          borderColor: (theme) => alpha(theme.palette.divider, 0.1),
          bgcolor: "background.paper",
          transition:
            "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          "&:hover": {
            transform: "translateY(-4px)",
            boxShadow: (theme) => `0 8px 32px ${alpha(theme.palette.common.black, 0.15)}`,
          },
        }}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        <AssetCardThumbnail
          id={id}
          name={name}
          assetType={assetType}
          thumbnailUrl={thumbnailUrl}
          proxyUrl={proxyUrl}
          thumbnailScale={thumbnailScale}
          height={thumbnailHeight}
          playerId={playerId}
          videoLoadError={videoLoadError}
          isMediaAsset={isMediaAsset}
          isPlayerActive={isPlayerActive}
          isInViewport={isInViewport}
          placeholderImage={placeholderImage}
          onAssetClick={onAssetClick}
          onImageError={onImageError}
        />

        {!isCompact && (
          <AssetCardActions
            isClipMode={isClipMode}
            isFavorite={isFavorite}
            showRemoveButton={showRemoveButton}
            onAssetClick={onAssetClick}
            onDeleteClick={onDeleteClick}
            onDownloadClick={onDownloadClick}
            onAddToCollectionClick={onAddToCollectionClick}
            onFavoriteToggle={onFavoriteToggle}
          />
        )}

        <AssetCardSelection
          id={id}
          isSelected={isSelected}
          visible={isHovering}
          onSelectToggle={onSelectToggle}
        />

        {showMetadata && isCompact && (
          <AssetCardCompactInfo
            id={id}
            name={name}
            fields={visibleFields}
            renderField={renderField}
            isEditing={isEditing}
            editedName={editedName}
            isRenaming={isRenaming}
            isClipMode={isClipMode}
            isFavorite={isFavorite}
            showRemoveButton={showRemoveButton}
            onAssetClick={onAssetClick}
            onEditClick={onEditClick}
            onEditNameChange={onEditNameChange}
            onEditNameComplete={onEditNameComplete}
            onDeleteClick={onDeleteClick}
            onDownloadClick={onDownloadClick}
            onAddToCollectionClick={onAddToCollectionClick}
            onFavoriteToggle={onFavoriteToggle}
          />
        )}

        {showMetadata && !isCompact && (
          <AssetCardMetadata
            id={id}
            fields={visibleFields}
            renderField={renderField}
            isEditing={isEditing}
            editedName={editedName}
            isRenaming={isRenaming}
            onEditClick={onEditClick}
            onEditNameChange={onEditNameChange}
            onEditNameComplete={onEditNameComplete}
          />
        )}
      </Box>
    );
  }
);

AssetCard.displayName = "AssetCard";
export default AssetCard;
