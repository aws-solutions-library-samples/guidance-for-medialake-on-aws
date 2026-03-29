import React, { useCallback, useRef } from "react";
import { Box, Typography } from "@mui/material";
import { useWindowVirtualizer } from "@tanstack/react-virtual";
import {
  useAssetAccessors,
  useAssetActions,
  useAssetEditingState,
} from "@/contexts/AssetItemContext";
import AssetCard, { type AssetField } from "./AssetCard";
import { groupAssetsByType } from "@/utils/groupAssetsByType";

interface AssetGridViewProps<T> {
  results: T[];
  groupByType: boolean;
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
  cardFields: AssetField[];
}

// ─── Column count by card size ───
function useColumnsForSize(cardSize: "small" | "medium" | "large"): number {
  switch (cardSize) {
    case "small":
      return 5;
    case "large":
      return 3;
    default:
      return 4;
  }
}

// ─── Estimate row height ───
function estimateRowHeight(
  cardSize: "small" | "medium" | "large",
  aspectRatio: "vertical" | "square" | "horizontal",
  showMetadata: boolean
): number {
  const baseHeight = aspectRatio === "vertical" ? 300 : aspectRatio === "square" ? 200 : 150;
  const multiplier = cardSize === "small" ? 0.8 : cardSize === "large" ? 1.4 : 1.1;
  const thumbnailHeight = baseHeight * multiplier;
  const actionBarHeight = 40;
  const metadataHeight = showMetadata ? 140 : 0;
  const gap = 16;
  return thumbnailHeight + actionBarHeight + metadataHeight + gap;
}

/**
 * AssetGridItem — the actual card renderer, wrapped in React.memo.
 *
 * CRITICAL: This component does NOT read from any React context.
 * All per-card editing state is passed as props so React.memo can
 * skip re-renders when the editing state doesn't affect this card.
 * The parent (AssetGridItemWrapper) reads context and passes props.
 */
const AssetGridItem = React.memo(function AssetGridItem<T>({
  asset,
  cardFields,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  // Per-card editing state (passed as props, not from context)
  isEditing,
  editedName,
  isFavorite,
  isSelected,
  isCardRenaming,
  isSemantic,
  confidenceThreshold,
  // Stable accessors and actions (from parent)
  getAssetId,
  getAssetName,
  getAssetType,
  getAssetThumbnail,
  getAssetProxy,
  renderCardField,
  onAssetClick,
  onDeleteClick,
  onDownloadClick,
  onAddToCollectionClick,
  showRemoveButton,
  onEditClick,
  onEditNameChange,
  onEditNameComplete,
  onFavoriteToggle,
  onSelectToggle,
}: {
  asset: T;
  cardFields: AssetField[];
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
  isEditing: boolean;
  editedName?: string;
  isFavorite: boolean;
  isSelected: boolean;
  isCardRenaming: boolean;
  isSemantic: boolean;
  confidenceThreshold: number;
  getAssetId: (a: T) => string;
  getAssetName: (a: T) => string;
  getAssetType: (a: T) => string;
  getAssetThumbnail: (a: T) => string;
  getAssetProxy?: (a: T) => string;
  renderCardField: (fieldId: string, a: T) => React.ReactNode;
  onAssetClick: (a: T) => void;
  onDeleteClick: (a: T, e: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (a: T, e: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (a: T, e: React.MouseEvent<HTMLElement>) => void;
  showRemoveButton: boolean;
  onEditClick: (a: T, e: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (a: T, save: boolean, value?: string) => void;
  onFavoriteToggle?: (a: T, e: React.MouseEvent<HTMLElement>) => void;
  onSelectToggle?: (a: T, e: React.MouseEvent<HTMLElement>) => void;
}) {
  const assetId = getAssetId(asset);

  const handleClick = useCallback(() => onAssetClick(asset), [onAssetClick, asset]);
  const handleDelete = useCallback(
    (e: React.MouseEvent<HTMLElement>) => onDeleteClick(asset, e),
    [onDeleteClick, asset]
  );
  const handleDownload = useCallback(
    (e: React.MouseEvent<HTMLElement>) => onDownloadClick(asset, e),
    [onDownloadClick, asset]
  );
  const handleAddToCollection = useCallback(
    (e: React.MouseEvent<HTMLElement>) => onAddToCollectionClick?.(asset, e),
    [onAddToCollectionClick, asset]
  );
  const handleEdit = useCallback(
    (e: React.MouseEvent<HTMLElement>) => onEditClick(asset, e),
    [onEditClick, asset]
  );
  const handleEditComplete = useCallback(
    (save: boolean, value?: string) => onEditNameComplete(asset, save, value),
    [onEditNameComplete, asset]
  );
  const handleFavorite = useCallback(
    (e: React.MouseEvent<HTMLElement>) => onFavoriteToggle?.(asset, e),
    [onFavoriteToggle, asset]
  );
  const handleSelect = useCallback(
    (_id: string, e: React.MouseEvent<HTMLElement>) => onSelectToggle?.(asset, e),
    [onSelectToggle, asset]
  );
  const handleRenderField = useCallback(
    (fieldId: string) => renderCardField(fieldId, asset),
    [renderCardField, asset]
  );

  return (
    <AssetCard
      id={assetId}
      name={getAssetName(asset)}
      thumbnailUrl={getAssetThumbnail(asset)}
      proxyUrl={getAssetProxy ? getAssetProxy(asset) : undefined}
      assetType={getAssetType(asset)}
      clips={(asset as any).clips}
      fields={cardFields}
      renderField={handleRenderField}
      onAssetClick={handleClick}
      onDeleteClick={handleDelete}
      onDownloadClick={handleDownload}
      onAddToCollectionClick={onAddToCollectionClick ? handleAddToCollection : undefined}
      showRemoveButton={showRemoveButton}
      onEditClick={handleEdit}
      isEditing={isEditing}
      editedName={editedName}
      onEditNameChange={onEditNameChange}
      onEditNameComplete={handleEditComplete}
      cardSize={cardSize}
      aspectRatio={aspectRatio}
      thumbnailScale={thumbnailScale}
      showMetadata={showMetadata}
      isFavorite={isFavorite}
      onFavoriteToggle={onFavoriteToggle ? handleFavorite : undefined}
      isSelected={isSelected}
      onSelectToggle={onSelectToggle ? handleSelect : undefined}
      isRenaming={isCardRenaming}
      isSemantic={isSemantic}
      confidenceThreshold={confidenceThreshold}
    />
  );
}) as <T>(props: any) => React.ReactElement;

/**
 * AssetGridItemWrapper — thin wrapper that reads context and passes
 * per-card editing state as props to the memoized AssetGridItem.
 * This component re-renders on every context change, but the inner
 * AssetGridItem only re-renders when its specific props change.
 */
function AssetGridItemWrapper<T>({
  asset,
  cardFields,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
}: {
  asset: T;
  cardFields: AssetField[];
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
}) {
  const accessors = useAssetAccessors<T>();
  const actions = useAssetActions<T>();
  const editing = useAssetEditingState();

  const assetId = accessors.getAssetId(asset);

  // Derive per-card booleans so React.memo on the inner component
  // can skip re-renders when another card's editing state changes
  const isEditing = editing.editingAssetId === assetId;
  const isFavorite = editing.isAssetFavorited ? editing.isAssetFavorited(assetId) : false;
  const isSelected = editing.isAssetSelected ? editing.isAssetSelected(assetId) : false;
  const isCardRenaming = !!(editing.isRenaming && editing.renamingAssetId === assetId);

  return (
    <AssetGridItem
      asset={asset}
      cardFields={cardFields}
      cardSize={cardSize}
      aspectRatio={aspectRatio}
      thumbnailScale={thumbnailScale}
      showMetadata={showMetadata}
      isEditing={isEditing}
      editedName={isEditing ? editing.editedName : undefined}
      isFavorite={isFavorite}
      isSelected={isSelected}
      isCardRenaming={isCardRenaming}
      isSemantic={editing.isSemantic ?? false}
      confidenceThreshold={editing.confidenceThreshold ?? 0}
      {...accessors}
      {...actions}
      showRemoveButton={actions.showRemoveButton ?? false}
    />
  );
}

// ─── Virtualized Grid ───
function VirtualizedAssetGrid<T>({
  assets,
  cardFields,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  getAssetId,
}: {
  assets: T[];
  cardFields: AssetField[];
  cardSize: "small" | "medium" | "large";
  aspectRatio: "vertical" | "square" | "horizontal";
  thumbnailScale: "fit" | "fill";
  showMetadata: boolean;
  getAssetId: (asset: T) => string;
}) {
  const columns = useColumnsForSize(cardSize);
  const rowHeight = estimateRowHeight(cardSize, aspectRatio, showMetadata);
  const gap = 16;

  const rows = React.useMemo(() => {
    const result: T[][] = [];
    for (let i = 0; i < assets.length; i += columns) {
      result.push(assets.slice(i, i + columns));
    }
    return result;
  }, [assets, columns]);

  const parentRef = useRef<HTMLDivElement>(null);
  const parentOffsetRef = useRef(0);

  React.useLayoutEffect(() => {
    parentOffsetRef.current = parentRef.current?.offsetTop ?? 0;
  }, []);

  const virtualizer = useWindowVirtualizer({
    count: rows.length,
    estimateSize: () => rowHeight,
    overscan: 2,
    scrollMargin: parentOffsetRef.current,
    measureElement: (el) => el.getBoundingClientRect().height,
  });

  const itemProps = { cardFields, cardSize, aspectRatio, thumbnailScale, showMetadata };

  return (
    <div ref={parentRef} style={{ position: "relative" }}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const row = rows[virtualRow.index];
          return (
            <div
              key={virtualRow.index}
              ref={virtualizer.measureElement}
              data-index={virtualRow.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start - virtualizer.options.scrollMargin}px)`,
                paddingBottom: `${gap}px`,
                display: "grid",
                gridTemplateColumns: `repeat(${columns}, 1fr)`,
                columnGap: `${gap / 2}px`,
                alignItems: "start",
              }}
            >
              {row.map((asset) => (
                <div key={getAssetId(asset)} data-testid={`asset-card-${getAssetId(asset)}`}>
                  <AssetGridItemWrapper asset={asset} {...itemProps} />
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main Component ───
function AssetGridView<T>({
  results,
  groupByType,
  cardSize,
  aspectRatio,
  thumbnailScale,
  showMetadata,
  cardFields,
}: AssetGridViewProps<T>) {
  const { getAssetId, getAssetType } = useAssetAccessors<T>();

  const groupedResults = React.useMemo(() => {
    if (!groupByType) return {};
    return groupAssetsByType(results, getAssetType);
  }, [results, groupByType, getAssetType]);

  const gridProps = { cardFields, cardSize, aspectRatio, thumbnailScale, showMetadata, getAssetId };

  if (!groupByType) {
    return <VirtualizedAssetGrid assets={results} {...gridProps} />;
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Object.entries(groupedResults).map(
        ([type, assets]) =>
          assets.length > 0 && (
            <Box key={type}>
              <Typography
                variant="h6"
                sx={{
                  mb: 2,
                  px: 1,
                  background: (theme) =>
                    `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                  backgroundClip: "text",
                  WebkitBackgroundClip: "text",
                  color: "transparent",
                  fontWeight: 600,
                }}
              >
                {type}
              </Typography>
              <VirtualizedAssetGrid assets={assets} {...gridProps} />
            </Box>
          )
      )}
    </Box>
  );
}

export default AssetGridView;
