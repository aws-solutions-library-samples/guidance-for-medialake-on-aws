import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router";
import { useQueries } from "@tanstack/react-query";
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
import { apiClient } from "@/api/apiClient";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { AssetCarousel } from "../AssetCarousel";
import { useDashboardActions, useDashboardStore } from "../../store/dashboardStore";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { useAddItemToCollection } from "@/api/hooks/useCollections";
import ApiStatusModal from "@/components/ApiStatusModal";
import { useDashboardSelection } from "../../contexts/DashboardSelectionContext";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
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

// Shape of the resolved asset record returned by GET /assets/{id}. Kept
// permissive because we only read a handful of fields.
type ResolvedAssetRecord = {
  asset?: {
    InventoryID?: string;
    DigitalSourceAsset?: {
      Type?: string;
      CreateDate?: string;
      MainRepresentation?: {
        Format?: string;
        StorageInfo?: {
          PrimaryLocation?: {
            ObjectKey?: {
              Name?: string;
              FullPath?: string;
            };
            FileInfo?: { Size?: number };
          };
        };
      };
    };
    DerivedRepresentations?: Array<{
      Purpose?: string;
      URL?: string;
    }>;
  };
};

const findPurposeUrl = (
  resolved: ResolvedAssetRecord | undefined,
  purpose: "thumbnail" | "proxy"
): string => {
  const rep = resolved?.asset?.DerivedRepresentations?.find((r) => r?.Purpose === purpose);
  return rep?.URL ?? "";
};

const nameFromResolved = (resolved: ResolvedAssetRecord | undefined): string =>
  resolved?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey
    ?.Name ?? "";

const formatFromResolved = (resolved: ResolvedAssetRecord | undefined): string =>
  resolved?.asset?.DigitalSourceAsset?.MainRepresentation?.Format ?? "";

const typeFromResolved = (resolved: ResolvedAssetRecord | undefined): string =>
  resolved?.asset?.DigitalSourceAsset?.Type ?? "";

// Helper to convert Favorite to asset-like object for useAssetOperations,
// preferring live-resolved data over the metadata snapshot stored at
// favorite-add time (which may have stale presigned thumbnail URLs, or may
// be entirely missing for favorites added via direct API calls).
const favoriteToAsset = (
  favorite: Favorite,
  resolved: ResolvedAssetRecord | undefined
): FavoriteAsset => ({
  InventoryID: favorite.itemId,
  DigitalSourceAsset: {
    Type: typeFromResolved(resolved) || favorite.metadata?.assetType || "Unknown",
    CreateDate:
      resolved?.asset?.DigitalSourceAsset?.CreateDate ||
      favorite.addedAt ||
      new Date().toISOString(),
    MainRepresentation: {
      Format: formatFromResolved(resolved) || favorite.metadata?.format || "unknown",
      StorageInfo: {
        PrimaryLocation: {
          ObjectKey: {
            Name: nameFromResolved(resolved) || favorite.metadata?.name || favorite.itemId,
            FullPath:
              resolved?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
                ?.ObjectKey?.FullPath ||
              favorite.metadata?.fullPath ||
              "",
          },
          FileInfo: {
            Size:
              resolved?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
                ?.FileInfo?.Size ??
              favorite.metadata?.size ??
              0,
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

  // Get widget instance from store to access customName
  const widgetInstance = useDashboardStore((state) =>
    state.layout.widgets.find((w) => w.id === widgetId)
  );
  const customName = widgetInstance?.customName;

  // Add to Collection state
  const [addToCollectionModalOpen, setAddToCollectionModalOpen] = useState(false);
  const [selectedFavoriteForCollection, setSelectedFavoriteForCollection] =
    useState<Favorite | null>(null);

  // Asset operations hook for delete, download
  const assetOperations = useAssetOperations<FavoriteAsset>();

  // Dashboard selection context for batch operations
  const dashboardSelection = useDashboardSelection();

  // Permission check for asset delete
  const deleteAssetPermission = useActionPermission("delete", "asset");

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

  // BUG-8: the previous implementation relied entirely on the metadata snapshot
  // stored at favorite-add time. That snapshot's thumbnailUrl is a 60-second S3
  // presigned URL that expires, and favorites added via the API directly carry
  // no metadata at all — both cases rendered a raw asset:uuid caption and the
  // generic SVG placeholder. Resolve each visible favorite against the live
  // GET /assets/{id} endpoint (fresh CloudFront-signed URLs, deduped/cached by
  // react-query) and fall back to the stored snapshot only if the fetch is
  // pending or fails (e.g. the asset was deleted — see BUG-9).
  const visibleFavorites = React.useMemo(() => favorites.slice(0, 20), [favorites]);

  const resolvedAssetQueries = useQueries({
    queries: visibleFavorites.map((favorite) => ({
      queryKey: QUERY_KEYS.ASSETS.detail(favorite.itemId),
      queryFn: async (): Promise<ResolvedAssetRecord | null> => {
        try {
          const inventoryId = getOriginalAssetId({
            InventoryID: favorite.itemId,
          });
          const response = await apiClient.get<{ data: ResolvedAssetRecord }>(
            `assets/${inventoryId}`
          );
          return response.data?.data ?? null;
        } catch (err) {
          logger.debug(
            "FavoritesWidget: failed to resolve favorite asset — falling back to stored metadata",
            { itemId: favorite.itemId, error: err }
          );
          return null;
        }
      },
      // Match useAsset() elsewhere in the app so cache is shared across pages.
      staleTime: 1000 * 60 * 30,
      gcTime: 1000 * 60 * 60,
      retry: 1,
      refetchOnMount: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })),
  });

  const resolvedByItemId = React.useMemo(() => {
    const map = new Map<string, ResolvedAssetRecord | undefined>();
    visibleFavorites.forEach((favorite, index) => {
      const query = resolvedAssetQueries[index];
      map.set(favorite.itemId, query?.data ?? undefined);
    });
    return map;
  }, [visibleFavorites, resolvedAssetQueries]);

  const handleAssetClick = useCallback(
    (assetId: string, assetType: string) => {
      const pathPrefix =
        assetType.toLowerCase() === "audio" ? "/audio/" : `/${assetType.toLowerCase()}s/`;
      const originalAssetId = getOriginalAssetId({ InventoryID: assetId });
      navigate(`${pathPrefix}${originalAssetId}`, {
        state: {
          assetType: assetType,
        },
      });
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
        items={visibleFavorites}
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
          const resolved = resolvedByItemId.get(favorite.itemId);
          const asset = favoriteToAsset(favorite, resolved);
          const isSelected = dashboardSelection?.isAssetSelected(favorite.itemId) ?? false;
          const thumbnailUrl =
            findPurposeUrl(resolved, "thumbnail") || favorite.metadata?.thumbnailUrl || "";
          const proxyUrl = findPurposeUrl(resolved, "proxy") || favorite.metadata?.proxyUrl || "";
          const displayName =
            nameFromResolved(resolved) || favorite.metadata?.name || favorite.itemId;
          const displayFormat = formatFromResolved(resolved) || favorite.metadata?.format || "";
          const displayType =
            typeFromResolved(resolved) || favorite.metadata?.assetType || "Unknown";
          return (
            <AssetCard
              id={favorite.itemId}
              name={displayName}
              thumbnailUrl={thumbnailUrl}
              proxyUrl={proxyUrl}
              assetType={displayType}
              fields={[
                { id: "name", label: "Name", visible: true },
                { id: "format", label: "Format", visible: true },
              ]}
              renderField={(fieldId) => {
                if (fieldId === "name") return displayName;
                if (fieldId === "format") {
                  return displayFormat ? displayFormat.toUpperCase() : "";
                }
                return "";
              }}
              onAssetClick={() => handleAssetClick(favorite.itemId, displayType)}
              onDeleteClick={(e) => assetOperations.handleDeleteClick(asset, e)}
              onDownloadClick={(e) => assetOperations.handleDownloadClick(asset, e)}
              onAddToCollectionClick={(e) => handleAddToCollectionClick(favorite, e)}
              isFavorite={true}
              onFavoriteToggle={(e) => handleFavoriteToggle(favorite.itemId, favorite.itemType, e)}
              isSelected={isSelected}
              onSelectToggle={
                dashboardSelection
                  ? (id, e) => {
                      e.stopPropagation();
                      dashboardSelection.handleSelectToggle(asset);
                    }
                  : undefined
              }
              canDelete={deleteAssetPermission.allowed}
              cardSize="medium"
              aspectRatio="square"
              thumbnailScale="fit"
              showMetadata={true}
              variant="compact"
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
        title={customName || t("dashboard.widgets.favorites.title", "Favorite Assets")}
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
