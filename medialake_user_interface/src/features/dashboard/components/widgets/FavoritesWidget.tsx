import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from "@mui/material";
import { FavoriteBorder as FavoriteIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetFavorites, useRemoveFavorite } from "@/api/hooks/useFavorites";
import AssetCard from "@/components/shared/AssetCard";
import { getOriginalAssetId } from "@/utils/clipTransformation";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { AssetCarousel } from "../AssetCarousel";
import { useDashboardActions } from "../../store/dashboardStore";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { useAddItemToCollection } from "@/api/hooks/useCollections";
import ApiStatusModal from "@/components/ApiStatusModal";
import type { BaseWidgetProps } from "../../types";
import type { Favorite } from "@/api/hooks/useFavorites";

// Type for the synthetic asset object we create from favorites
type FavoriteAsset = {
  InventoryID: string;
  DigitalSourceAsset: {
    Type: string;
    CreateDate: string;
    MainRepresentation: {
      Format: string;
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: string;
            FullPath: string;
          };
          FileInfo: {
            Size: number;
          };
        };
      };
    };
  };
};

// Helper to convert Favorite to asset-like object for useAssetOperations
const favoriteToAsset = (favorite: Favorite): FavoriteAsset => ({
  InventoryID: favorite.itemId,
  DigitalSourceAsset: {
    Type: favorite.metadata?.assetType || "Unknown",
    CreateDate: favorite.addedAt || new Date().toISOString(),
    MainRepresentation: {
      Format: favorite.metadata?.format || "unknown",
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: favorite.metadata?.name || favorite.itemId,
            FullPath: favorite.metadata?.fullPath || "",
          },
          FileInfo: {
            Size: favorite.metadata?.size || 0,
          },
        },
      },
    },
  },
});

export const FavoritesWidget: React.FC<BaseWidgetProps> = ({ widgetId, isExpanded = false }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

  // Add to Collection state
  const [addToCollectionModalOpen, setAddToCollectionModalOpen] = useState(false);
  const [selectedFavoriteForCollection, setSelectedFavoriteForCollection] =
    useState<Favorite | null>(null);

  // Asset operations hook for delete, download
  const assetOperations = useAssetOperations<FavoriteAsset>();

  // Add to collection mutation
  const addItemToCollection = useAddItemToCollection();

  const {
    data: unsortedFavorites,
    isLoading,
    error: queryError,
    refetch,
  } = useGetFavorites("ASSET");

  const { mutate: removeFavorite } = useRemoveFavorite();

  // Sort favorites by addedAt timestamp in descending order (newest first)
  const favorites = React.useMemo(() => {
    if (!unsortedFavorites || !Array.isArray(unsortedFavorites)) return [];

    return [...unsortedFavorites].sort((a, b) => {
      if (a.addedAt && b.addedAt) {
        return new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime();
      }
      if (a.addedAt && !b.addedAt) return -1;
      if (!a.addedAt && b.addedAt) return 1;
      return 0;
    });
  }, [unsortedFavorites]);

  // Handle error gracefully - don't show error for empty/undefined data
  const error = queryError;

  const handleAssetClick = useCallback(
    (assetId: string, assetType: string) => {
      const pathPrefix =
        assetType.toLowerCase() === "audio" ? "/audio/" : `/${assetType.toLowerCase()}s/`;
      const originalAssetId = getOriginalAssetId({ InventoryID: assetId });
      navigate(`${pathPrefix}${originalAssetId}`);
    },
    [navigate]
  );

  const handleFavoriteToggle = useCallback(
    (assetId: string, itemType: string, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      removeFavorite({ itemId: assetId, itemType });
    },
    [removeFavorite]
  );

  // Handle Add to Collection click
  const handleAddToCollectionClick = useCallback(
    (favorite: Favorite, event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      setSelectedFavoriteForCollection(favorite);
      setAddToCollectionModalOpen(true);
    },
    []
  );

  // Handle actually adding the asset to a collection
  const handleAddToCollection = useCallback(
    async (collectionId: string) => {
      if (!selectedFavoriteForCollection) return;

      try {
        await addItemToCollection.mutateAsync({
          collectionId,
          data: {
            assetId: selectedFavoriteForCollection.itemId,
          },
        });
        setAddToCollectionModalOpen(false);
        setSelectedFavoriteForCollection(null);
      } catch (error) {
        console.error("Failed to add asset to collection:", error);
      }
    },
    [selectedFavoriteForCollection, addItemToCollection]
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
    if (!favorites || favorites.length === 0) {
      return (
        <EmptyState
          icon={<FavoriteIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.favorites.emptyTitle")}
          description={t("dashboard.widgets.favorites.emptyDescription")}
        />
      );
    }

    return (
      <AssetCarousel
        items={favorites.slice(0, 20)}
        isLoading={isLoading}
        getItemKey={(favorite: Favorite) => favorite.itemId}
        emptyState={
          <EmptyState
            icon={<FavoriteIcon sx={{ fontSize: 48 }} />}
            title={t("dashboard.widgets.favorites.emptyTitle")}
            description={t("dashboard.widgets.favorites.emptyDescription")}
          />
        }
        renderCard={(favorite: Favorite) => {
          const asset = favoriteToAsset(favorite);
          return (
            <AssetCard
              id={favorite.itemId}
              name={favorite.metadata?.name || favorite.itemId}
              thumbnailUrl={favorite.metadata?.thumbnailUrl || ""}
              assetType={favorite.metadata?.assetType || "Unknown"}
              fields={[
                { id: "name", label: "Name", visible: true },
                { id: "type", label: "Type", visible: true },
              ]}
              renderField={(fieldId) => {
                if (fieldId === "name") return favorite.metadata?.name || favorite.itemId;
                if (fieldId === "type") return favorite.metadata?.assetType || "Unknown";
                return "";
              }}
              onAssetClick={() =>
                handleAssetClick(favorite.itemId, favorite.metadata?.assetType || "Unknown")
              }
              onDeleteClick={(e) => assetOperations.handleDeleteClick(asset, e)}
              onDownloadClick={(e) => assetOperations.handleDownloadClick(asset, e)}
              onAddToCollectionClick={(e) => handleAddToCollectionClick(favorite, e)}
              isFavorite={true}
              onFavoriteToggle={(e) => handleFavoriteToggle(favorite.itemId, favorite.itemType, e)}
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
        title={t("dashboard.widgets.favorites.title")}
        icon={<FavoriteIcon />}
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
      {selectedFavoriteForCollection && (
        <AddToCollectionModal
          open={addToCollectionModalOpen}
          onClose={() => {
            setAddToCollectionModalOpen(false);
            setSelectedFavoriteForCollection(null);
          }}
          assetId={selectedFavoriteForCollection.itemId}
          assetName={
            selectedFavoriteForCollection.metadata?.name || selectedFavoriteForCollection.itemId
          }
          assetType={selectedFavoriteForCollection.metadata?.assetType || "Unknown"}
          onAddToCollection={handleAddToCollection}
        />
      )}
    </>
  );
};
