/**
 * Collection Group Widget
 * Displays collections from a specific collection group
 */

import React, { useState, useCallback, useMemo } from "react";
import {
  Box,
  Typography,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Chip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  FolderSpecial as FolderSpecialIcon,
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
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { WidgetContainer } from "../WidgetContainer";
import { CollectionCarousel } from "../CollectionCarousel";
import { EmptyState } from "../EmptyState";
import { CollectionGroupWidgetConfigPanel } from "./CollectionGroupWidgetConfigPanel";
import type { BaseWidgetProps, CollectionGroupWidgetConfig } from "../../types";
import { useDashboardStore, useDashboardActions } from "../../store/dashboardStore";
import { useCollectionGroup } from "@/features/collection-groups/hooks/useCollectionGroups";
import { useGetCollections, useGetCollectionTypes } from "@/api/hooks/useCollections";

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

const CARD_WIDTH = 240;
const CARD_HEIGHT = 200;

// Collection card props
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

// Collection card component matching CollectionsWidget style
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

interface CollectionGroupWidgetProps extends BaseWidgetProps {}

// Collection item type
interface CollectionItem {
  id: string;
  name: string;
  description?: string;
  itemCount: number;
  childCollectionCount?: number;
  isPublic: boolean;
  collectionTypeId?: string;
}

export const CollectionGroupWidget: React.FC<CollectionGroupWidgetProps> = ({
  widgetId,
  isExpanded = false,
  onDataLoad,
  onError,
}) => {
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();

  const widget = useDashboardStore((state) => state.layout.widgets.find((w) => w.id === widgetId));

  const config = widget?.config as CollectionGroupWidgetConfig | undefined;
  const customName = widget?.customName;

  // Fetch the group details
  const {
    data: groupData,
    isLoading: isLoadingGroup,
    error: groupError,
    refetch: refetchGroup,
  } = useCollectionGroup(config?.groupId || "");

  // Fetch collections filtered by this group
  const {
    data: collectionsData,
    isLoading: isLoadingCollections,
    error: collectionsError,
    refetch: refetchCollections,
  } = useGetCollections(config?.groupId ? { groupIds: config.groupId } : undefined);

  // Fetch collection types for icons and colors
  const { data: collectionTypesResponse, isLoading: isLoadingTypes } = useGetCollectionTypes();

  const isLoading = isLoadingGroup || isLoadingCollections;
  const error = groupError || collectionsError;

  React.useEffect(() => {
    if (!isLoading && !error) {
      onDataLoad?.();
    }
    if (error) {
      onError?.(error as Error);
    }
  }, [isLoading, error, onDataLoad, onError]);

  const handleRefresh = useCallback(() => {
    refetchGroup();
    refetchCollections();
  }, [refetchGroup, refetchCollections]);

  const handleConfigure = useCallback(() => {
    setConfigPanelOpen(true);
  }, []);

  const handleExpand = useCallback(() => {
    setExpandedWidget(widgetId);
  }, [setExpandedWidget, widgetId]);

  const handleRemove = useCallback(() => {
    removeWidget(widgetId);
  }, [removeWidget, widgetId]);

  const handleCollectionClick = useCallback(
    (collectionId: string) => {
      navigate(`/collections/${collectionId}/view`);
    },
    [navigate]
  );

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

  const group = groupData?.data;
  const collections = collectionsData?.data || [];

  // Determine widget title
  const widgetTitle =
    customName ||
    (group?.name
      ? `Group: ${group.name}`
      : t("dashboard.widgets.collectionGroup.title", "Collection Group"));

  return (
    <>
      <WidgetContainer
        widgetId={widgetId}
        title={widgetTitle}
        icon={<FolderSpecialIcon />}
        onExpand={handleExpand}
        onRefresh={handleRefresh}
        onRemove={handleRemove}
        onConfigure={handleConfigure}
        isLoading={isLoading || isLoadingTypes}
        isExpanded={isExpanded}
        error={error}
        onRetry={handleRefresh}
      >
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
          {error ? (
            <Alert severity="error">
              {t(
                "dashboard.widgets.collectionGroup.loadError",
                "Failed to load collection group. Please try again."
              )}
            </Alert>
          ) : !config?.groupId ? (
            <EmptyState
              icon={<FolderSpecialIcon sx={{ fontSize: 60 }} />}
              title={t("dashboard.widgets.collectionGroup.emptyTitle", "No Group Selected")}
              description={t(
                "dashboard.widgets.collectionGroup.emptyDescription",
                "Configure this widget to select a collection group"
              )}
              actionLabel={t("dashboard.actions.configure", "Configure")}
              onAction={handleConfigure}
            />
          ) : isLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" flex={1}>
              <CircularProgress />
            </Box>
          ) : collections.length === 0 ? (
            <EmptyState
              icon={<FolderSpecialIcon sx={{ fontSize: 60 }} />}
              title={t("dashboard.widgets.collectionGroup.noCollections", "No Collections")}
              description={t(
                "dashboard.widgets.collectionGroup.noCollectionsDescription",
                `The group "${group?.name}" doesn't have any collections yet`
              ).replace("${group?.name}", group?.name || "")}
            />
          ) : (
            <Box sx={{ flex: 1, overflow: "hidden" }}>
              {group?.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2, px: 2 }}>
                  {group.description}
                </Typography>
              )}
              <CollectionCarousel
                items={collections as CollectionItem[]}
                isLoading={isLoading || isLoadingTypes}
                cardWidth={CARD_WIDTH}
                cardHeight={CARD_HEIGHT}
                getItemKey={(collection: CollectionItem) => collection.id}
                renderCard={(collection: CollectionItem) => {
                  const typeInfo = getCollectionTypeInfo(collection.collectionTypeId);
                  return (
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
                  );
                }}
              />
            </Box>
          )}
        </Box>
      </WidgetContainer>

      {configPanelOpen && (
        <CollectionGroupWidgetConfigPanel
          open={configPanelOpen}
          onClose={() => setConfigPanelOpen(false)}
          widgetId={widgetId}
          config={config}
        />
      )}
    </>
  );
};
