import React, { useCallback } from "react";
import { Box, Stack, Skeleton } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { FavoriteBorder as FavoriteIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetFavorites, useRemoveFavorite } from "@/api/hooks/useFavorites";
import AssetCard from "@/components/shared/AssetCard";
import { getOriginalAssetId } from "@/utils/clipTransformation";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { useDashboardActions } from "../../store/dashboardStore";
import type { BaseWidgetProps } from "../../types";

export const FavoritesWidget: React.FC<BaseWidgetProps> = ({ widgetId }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

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
    if (isLoading) {
      return (
        <Stack direction="row" spacing={2} sx={{ overflowX: "auto", pb: 1 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton
              key={i}
              variant="rectangular"
              width={200}
              height={200}
              sx={{ borderRadius: 2, flexShrink: 0 }}
            />
          ))}
        </Stack>
      );
    }

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
      <Stack
        direction="row"
        spacing={2}
        sx={{
          overflowX: "auto",
          pb: 1,
          "&::-webkit-scrollbar": {
            height: "6px",
          },
          "&::-webkit-scrollbar-track": {
            backgroundColor: "rgba(0,0,0,0.05)",
            borderRadius: "3px",
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: "rgba(0,0,0,0.2)",
            borderRadius: "3px",
          },
        }}
      >
        {favorites.slice(0, 10).map((favorite) => (
          <Box
            key={favorite.itemId}
            sx={{
              minWidth: 200,
              maxWidth: 200,
              flexShrink: 0,
            }}
          >
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
              onDeleteClick={() => {}}
              onDownloadClick={() => {}}
              isFavorite={true}
              onFavoriteToggle={(e) => handleFavoriteToggle(favorite.itemId, favorite.itemType, e)}
              cardSize="small"
              aspectRatio="square"
              thumbnailScale="fill"
              showMetadata={true}
            />
          </Box>
        ))}
      </Stack>
    );
  };

  return (
    <WidgetContainer
      widgetId={widgetId}
      title={t("dashboard.widgets.favorites.title")}
      icon={<FavoriteIcon />}
      onExpand={handleExpand}
      onRefresh={handleRefresh}
      onRemove={handleRemove}
      isLoading={isLoading}
      error={error}
      onRetry={handleRefresh}
    >
      {renderContent()}
    </WidgetContainer>
  );
};
