import React, { useCallback } from "react";
import { Box, Grid, Skeleton, Card, CardContent, CardMedia, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { FolderOpen as CollectionIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetCollections } from "@/api/hooks/useCollections";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { useDashboardActions } from "../../store/dashboardStore";
import type { BaseWidgetProps } from "../../types";

// Simple collection card for the widget
interface CollectionCardProps {
  id: string;
  name: string;
  description?: string;
  thumbnailUrl?: string;
  itemCount: number;
  childCollectionCount?: number;
  onClick: () => void;
}

const CollectionCardSimple: React.FC<CollectionCardProps> = ({
  name,
  description,
  thumbnailUrl,
  itemCount,
  childCollectionCount = 0,
  onClick,
}) => {
  return (
    <Card
      onClick={onClick}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        cursor: "pointer",
        borderRadius: 2,
        border: "1px solid",
        borderColor: "divider",
        transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: 2,
        },
      }}
    >
      <CardMedia
        component="div"
        sx={{
          height: 100,
          backgroundColor: thumbnailUrl ? "transparent" : "grey.200",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {!thumbnailUrl && <CollectionIcon sx={{ fontSize: 40, color: "grey.400" }} />}
        {thumbnailUrl && (
          <img
            src={thumbnailUrl}
            alt={name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </CardMedia>
      <CardContent sx={{ flexGrow: 1, p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Typography variant="subtitle2" component="h4" noWrap sx={{ fontWeight: 600 }}>
          {name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {itemCount} assets
          {childCollectionCount > 0 ? ` • ${childCollectionCount} sub-collections` : ""}
        </Typography>
        {description && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: "-webkit-box",
              WebkitLineClamp: 1,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              mt: 0.5,
            }}
          >
            {description}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export const MyCollectionsWidget: React.FC<BaseWidgetProps> = ({ widgetId }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

  const {
    data: collectionsResponse,
    isLoading,
    error,
    refetch,
  } = useGetCollections({ "filter[type]": "private" });

  const collections = collectionsResponse?.data || [];

  const handleCollectionClick = useCallback(
    (collectionId: string) => {
      navigate(`/collections/${collectionId}`);
    },
    [navigate]
  );

  const handleCreateCollection = useCallback(() => {
    navigate("/collections?action=create");
  }, [navigate]);

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
        <Grid container spacing={2}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={6} sm={4} md={3} key={i}>
              <Skeleton variant="rectangular" height={160} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
      );
    }

    if (!collections || collections.length === 0) {
      return (
        <EmptyState
          icon={<CollectionIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.myCollections.emptyTitle")}
          description={t("dashboard.widgets.myCollections.emptyDescription")}
          actionLabel={t("dashboard.widgets.myCollections.createCollection")}
          onAction={handleCreateCollection}
        />
      );
    }

    return (
      <Grid container spacing={2}>
        {collections.slice(0, 8).map((collection) => (
          <Grid item xs={6} sm={4} md={3} key={collection.id}>
            <CollectionCardSimple
              id={collection.id}
              name={collection.name}
              description={collection.description}
              itemCount={collection.itemCount}
              childCollectionCount={collection.childCollectionCount}
              onClick={() => handleCollectionClick(collection.id)}
            />
          </Grid>
        ))}
      </Grid>
    );
  };

  return (
    <WidgetContainer
      widgetId={widgetId}
      title={t("dashboard.widgets.myCollections.title")}
      icon={<CollectionIcon />}
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
