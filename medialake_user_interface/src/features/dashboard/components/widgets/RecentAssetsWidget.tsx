import React, { useCallback, useMemo, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { Schedule as RecentIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useSearch } from "@/api/hooks/useSearch";
import AssetCard from "@/components/shared/AssetCard";
import { getOriginalAssetId } from "@/utils/clipTransformation";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { AssetCarousel } from "../AssetCarousel";
import { useDashboardActions } from "../../store/dashboardStore";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { useAddFavorite, useRemoveFavorite, useGetFavorites } from "@/api/hooks/useFavorites";
import { useAddItemToCollection } from "@/api/hooks/useCollections";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import ApiStatusModal from "@/components/ApiStatusModal";
import type { BaseWidgetProps } from "../../types";
import type { ImageItem, VideoItem, AudioItem } from "@/types/search/searchResults";

type AssetItem = ImageItem | VideoItem | AudioItem;

// Helper to safely extract asset properties from the nested structure
const getAssetName = (asset: any): string => {
  return (
    asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name ||
    asset?.filename ||
    asset?.name ||
    "Untitled"
  );
};

const getAssetType = (asset: any): string => {
  return asset?.DigitalSourceAsset?.Type || asset?.type || asset?.assetType || "Image";
};

const getAssetThumbnail = (asset: any): string => {
  return asset?.thumbnailUrl || asset?.thumbnail || "";
};

const getAssetId = (asset: any): string => {
  return asset?.InventoryID || asset?.id || "";
};

const getAssetCreateDate = (asset: any): number => {
  const dateStr = asset?.DigitalSourceAsset?.CreateDate || asset?.createDate || asset?.ingestedDate;
  return dateStr ? new Date(dateStr).getTime() : 0;
};

const getAssetFormat = (asset: any): string => {
  return asset?.DigitalSourceAsset?.MainRepresentation?.Format || "";
};

export const RecentAssetsWidget: React.FC<BaseWidgetProps> = ({ widgetId, isExpanded = false }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

  // Add to Collection state
  const [addToCollectionModalOpen, setAddToCollectionModalOpen] = useState(false);
  const [selectedAssetForCollection, setSelectedAssetForCollection] = useState<AssetItem | null>(
    null
  );

  // Asset operations hook for delete, download, rename
  const assetOperations = useAssetOperations<AssetItem>();

  // Favorites
  const { data: favorites } = useGetFavorites("ASSET");
  const { mutate: addFavorite } = useAddFavorite();
  const { mutate: removeFavorite } = useRemoveFavorite();

  // Add to collection mutation
  const addItemToCollection = useAddItemToCollection();

  // Search for recent assets - using wildcard query sorted by date
  const {
    data: searchResponse,
    isLoading,
    error,
    refetch,
  } = useSearch("*", {
    pageSize: 20,
    isSemantic: false,
  });

  const assets = useMemo(() => {
    const results = searchResponse?.data?.results || [];
    // Sort by creation date descending (most recent first)
    return [...results].sort((a, b) => {
      return getAssetCreateDate(b) - getAssetCreateDate(a);
    });
  }, [searchResponse]);

  // Check if asset is favorited
  const isAssetFavorited = useCallback(
    (assetId: string) => {
      return favorites?.some((fav) => fav.itemId === assetId) || false;
    },
    [favorites]
  );

  // Handle favorite toggle
  const handleFavoriteToggle = useCallback(
    (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      const assetId = getAssetId(asset);
      const isFavorited = isAssetFavorited(assetId);

      if (isFavorited) {
        removeFavorite({ itemId: assetId, itemType: "ASSET" });
      } else {
        addFavorite({
          itemId: assetId,
          itemType: "ASSET",
          metadata: {
            name: getAssetName(asset),
            assetType: getAssetType(asset),
            thumbnailUrl: getAssetThumbnail(asset),
          },
        });
      }
    },
    [isAssetFavorited, addFavorite, removeFavorite]
  );

  const handleAssetClick = useCallback(
    (assetId: string, assetType: string) => {
      const pathPrefix =
        assetType?.toLowerCase() === "audio"
          ? "/audio/"
          : `/${assetType?.toLowerCase() || "image"}s/`;
      const originalAssetId = getOriginalAssetId({ InventoryID: assetId });
      navigate(`${pathPrefix}${originalAssetId}`);
    },
    [navigate]
  );

  // Handle Add to Collection click
  const handleAddToCollectionClick = useCallback(
    (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      setSelectedAssetForCollection(asset);
      setAddToCollectionModalOpen(true);
    },
    []
  );

  // Handle actually adding the asset to a collection
  const handleAddToCollection = useCallback(
    async (collectionId: string) => {
      if (!selectedAssetForCollection) return;

      try {
        await addItemToCollection.mutateAsync({
          collectionId,
          data: {
            assetId: selectedAssetForCollection.InventoryID,
          },
        });
        setAddToCollectionModalOpen(false);
        setSelectedAssetForCollection(null);
      } catch (error) {
        console.error("Failed to add asset to collection:", error);
      }
    },
    [selectedAssetForCollection, addItemToCollection]
  );

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleExpand = useCallback(() => {
    setExpandedWidget(widgetId);
  }, [setExpandedWidget, widgetId]);

  const handleRemove = useCallback(() => {
    removeWidget(widgetId);
  }, [removeWidget, widgetId]);

  const renderContent = () => {
    if (!assets || assets.length === 0) {
      return (
        <EmptyState
          icon={<RecentIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.recentAssets.emptyTitle")}
          description={t("dashboard.widgets.recentAssets.emptyDescription")}
        />
      );
    }

    return (
      <AssetCarousel
        items={assets.slice(0, 20)}
        isLoading={isLoading}
        getItemKey={(asset: AssetItem) => getAssetId(asset)}
        emptyState={
          <EmptyState
            icon={<RecentIcon sx={{ fontSize: 48 }} />}
            title={t("dashboard.widgets.recentAssets.emptyTitle")}
            description={t("dashboard.widgets.recentAssets.emptyDescription")}
          />
        }
        renderCard={(asset: AssetItem) => {
          const assetId = getAssetId(asset);
          const assetName = getAssetName(asset);
          const assetType = getAssetType(asset);
          const thumbnailUrl = getAssetThumbnail(asset);
          const format = getAssetFormat(asset);
          const isFavorited = isAssetFavorited(assetId);

          return (
            <AssetCard
              id={assetId}
              name={assetName}
              thumbnailUrl={thumbnailUrl}
              assetType={assetType}
              fields={[
                { id: "name", label: "Name", visible: true },
                { id: "type", label: "Type", visible: true },
              ]}
              renderField={(fieldId) => {
                if (fieldId === "name") return assetName;
                if (fieldId === "type") return assetType;
                if (fieldId === "format") return format;
                return "";
              }}
              onAssetClick={() => handleAssetClick(assetId, assetType)}
              onDeleteClick={(e) => assetOperations.handleDeleteClick(asset, e)}
              onDownloadClick={(e) => assetOperations.handleDownloadClick(asset, e)}
              onAddToCollectionClick={(e) => handleAddToCollectionClick(asset, e)}
              isFavorite={isFavorited}
              onFavoriteToggle={(e) => handleFavoriteToggle(asset, e)}
              cardSize="medium"
              aspectRatio="square"
              thumbnailScale="fit"
              showMetadata={true}
            />
          );
        }}
      />
    );
  };

  return (
    <>
      <WidgetContainer
        widgetId={widgetId}
        title={t("dashboard.widgets.recentAssets.title")}
        icon={<RecentIcon />}
        onExpand={handleExpand}
        onRefresh={handleRefresh}
        onRemove={handleRemove}
        isLoading={isLoading}
        isExpanded={isExpanded}
        error={error}
        onRetry={handleRefresh}
      >
        {renderContent()}
      </WidgetContainer>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={assetOperations.isDeleteModalOpen}
        onClose={assetOperations.handleDeleteCancel}
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-description"
      >
        <DialogTitle id="delete-dialog-title">{t("assetExplorer.deleteDialog.title")}</DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-dialog-description">
            {t("assetExplorer.deleteDialog.description")}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={assetOperations.handleDeleteCancel}>{t("common.cancel")}</Button>
          <Button onClick={assetOperations.handleDeleteConfirm} color="error" autoFocus>
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* API Status Modal for delete operation */}
      <ApiStatusModal
        open={assetOperations.deleteModalState.open}
        onClose={assetOperations.handleDeleteModalClose}
        status={assetOperations.deleteModalState.status}
        action={assetOperations.deleteModalState.action}
        message={assetOperations.deleteModalState.message}
      />

      {/* Add to Collection Modal */}
      {selectedAssetForCollection && (
        <AddToCollectionModal
          open={addToCollectionModalOpen}
          onClose={() => {
            setAddToCollectionModalOpen(false);
            setSelectedAssetForCollection(null);
          }}
          assetId={selectedAssetForCollection.InventoryID}
          assetName={
            selectedAssetForCollection.DigitalSourceAsset.MainRepresentation.StorageInfo
              .PrimaryLocation.ObjectKey.Name
          }
          assetType={selectedAssetForCollection.DigitalSourceAsset.Type}
          onAddToCollection={handleAddToCollection}
        />
      )}
    </>
  );
};
