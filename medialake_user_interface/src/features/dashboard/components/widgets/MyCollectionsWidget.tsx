import React, { useCallback, useMemo } from "react";
import {
  Box,
  Grid,
  Skeleton,
  Card,
  CardContent,
  Typography,
  Chip,
  alpha,
  useTheme,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen as CollectionIcon,
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Work,
  Campaign,
  Assignment,
  Archive,
  PhotoLibrary as PhotoLibraryIcon,
  Label,
  Movie,
  Collections as CollectionsIcon,
  Dashboard,
  Storage,
  Inventory,
  Category,
  BookmarkBorder,
  LocalOffer,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetCollections, useGetCollectionTypes } from "@/api/hooks/useCollections";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { useDashboardActions } from "../../store/dashboardStore";
import type { BaseWidgetProps } from "../../types";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <FolderIcon />,
  FolderOpen: <FolderOpenIcon />,
  Work: <Work />,
  Campaign: <Campaign />,
  Assignment: <Assignment />,
  Archive: <Archive />,
  PhotoLibrary: <PhotoLibraryIcon />,
  Label: <Label />,
  Movie: <Movie />,
  Collections: <CollectionsIcon />,
  Dashboard: <Dashboard />,
  Storage: <Storage />,
  Inventory: <Inventory />,
  Category: <Category />,
  BookmarkBorder: <BookmarkBorder />,
  LocalOffer: <LocalOffer />,
};

// Simple collection card for the widget
interface CollectionCardProps {
  id: string;
  name: string;
  description?: string;
  itemCount: number;
  childCollectionCount?: number;
  isPublic: boolean;
  iconName?: string;
  color?: string;
  onClick: () => void;
}

const CollectionCardSimple: React.FC<CollectionCardProps> = ({
  name,
  description,
  itemCount,
  childCollectionCount = 0,
  isPublic,
  iconName,
  color,
  onClick,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  // Get the icon component
  const IconComponent = useMemo(() => {
    if (iconName && ICON_MAP[iconName]) {
      return React.cloneElement(ICON_MAP[iconName], {
        sx: { fontSize: 40, color: color || "grey.400" },
      });
    }
    return <CollectionIcon sx={{ fontSize: 40, color: color || "grey.400" }} />;
  }, [iconName, color]);

  const borderColor = color || theme.palette.divider;

  return (
    <Card
      onClick={onClick}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        cursor: "pointer",
        borderRadius: 2,
        border: "2px solid",
        borderColor: borderColor,
        backgroundColor: alpha(theme.palette.background.paper, 0.8),
        transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: `0 4px 12px ${alpha(borderColor, 0.3)}`,
        },
      }}
    >
      {/* Icon Header */}
      <Box
        sx={{
          height: 80,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: color ? alpha(color, 0.1) : alpha(theme.palette.grey[500], 0.1),
        }}
      >
        {IconComponent}
      </Box>

      <CardContent sx={{ flexGrow: 1, p: 1.5, "&:last-child": { pb: 1.5 } }}>
        {/* Collection Name */}
        <Typography variant="subtitle2" component="h4" noWrap sx={{ fontWeight: 600, mb: 0.5 }}>
          {name}
        </Typography>

        {/* Public/Private Badge */}
        <Box sx={{ mb: 1 }}>
          <Chip
            size="small"
            icon={
              isPublic ? (
                <PublicIcon sx={{ fontSize: 14 }} />
              ) : (
                <PrivateIcon sx={{ fontSize: 14 }} />
              )
            }
            label={isPublic ? t("common.public", "Public") : t("common.private", "Private")}
            sx={{
              height: 20,
              fontSize: "0.7rem",
              backgroundColor: isPublic
                ? alpha(theme.palette.success.main, 0.1)
                : alpha(theme.palette.info.main, 0.1),
              color: isPublic ? theme.palette.success.main : theme.palette.info.main,
              border: `1px solid ${
                isPublic ? theme.palette.success.main : theme.palette.info.main
              }`,
              "& .MuiChip-icon": {
                color: "inherit",
              },
            }}
          />
        </Box>

        {/* Item Count */}
        <Typography variant="caption" color="text.secondary">
          {itemCount} {t("common.items", "items")}
          {childCollectionCount > 0 &&
            ` • ${childCollectionCount} ${t("common.subCollections", "sub-collections")}`}
        </Typography>

        {/* Description */}
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
  const theme = useTheme();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

  const { data: collectionsResponse, isLoading, error, refetch } = useGetCollections();

  const { data: collectionTypesResponse, isLoading: isLoadingTypes } = useGetCollectionTypes();

  const collections = collectionsResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  // Helper to get collection type info
  const getCollectionTypeInfo = useCallback(
    (collectionTypeId?: string) => {
      if (!collectionTypeId || isLoadingTypes) {
        return { iconName: undefined, color: undefined };
      }

      const collectionType = collectionTypes.find((type) => type.id === collectionTypeId);
      if (!collectionType) {
        return { iconName: undefined, color: undefined };
      }

      return {
        iconName: collectionType.icon,
        color: collectionType.color,
      };
    },
    [collectionTypes, isLoadingTypes]
  );

  const handleCollectionClick = useCallback(
    (collectionId: string) => {
      navigate(`/collections/${collectionId}/view`);
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
        {collections.slice(0, 8).map((collection) => {
          const typeInfo = getCollectionTypeInfo(collection.collectionTypeId);
          return (
            <Grid item xs={6} sm={4} md={3} key={collection.id}>
              <CollectionCardSimple
                id={collection.id}
                name={collection.name}
                description={collection.description}
                itemCount={collection.itemCount}
                childCollectionCount={collection.childCollectionCount}
                isPublic={collection.isPublic}
                iconName={typeInfo.iconName}
                color={typeInfo.color}
                onClick={() => handleCollectionClick(collection.id)}
              />
            </Grid>
          );
        })}
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
      isLoading={isLoading || isLoadingTypes}
      error={error}
      onRetry={handleRefresh}
    >
      {renderContent()}
    </WidgetContainer>
  );
};
