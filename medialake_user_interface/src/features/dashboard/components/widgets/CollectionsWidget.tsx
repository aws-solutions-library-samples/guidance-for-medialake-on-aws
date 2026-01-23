import React, { useCallback, useMemo } from "react";
import { Box, Card, CardContent, Typography, Chip, alpha, useTheme } from "@mui/material";
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
import {
  useGetCollections,
  useGetCollectionTypes,
  useGetCollectionsSharedWithMe,
  useGetCollectionsSharedByMe,
} from "@/api/hooks/useCollections";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { CollectionCarousel } from "../CollectionCarousel";
import { useDashboardActions } from "../../store/dashboardStore";
import type { BaseWidgetProps, CollectionsWidgetConfig } from "../../types";
import { filterCollections, sortCollections } from "../../utils/collectionFilters";
import type { Collection } from "../../utils/collectionFilters";
import { fetchAuthSession } from "aws-amplify/auth";
import { jwtDecode } from "jwt-decode";
import { WidgetConfigPanel } from "./WidgetConfigPanel";

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

// Default configuration
const DEFAULT_CONFIG: CollectionsWidgetConfig = {
  viewType: "all",
  sorting: {
    sortBy: "name",
    sortOrder: "asc",
  },
};

// Collection type for the carousel
interface CollectionItem {
  id: string;
  name: string;
  description?: string;
  itemCount: number;
  childCollectionCount?: number;
  isPublic: boolean;
  collectionTypeId?: string;
}

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

interface JwtPayload {
  sub?: string;
  [key: string]: any;
}

/**
 * Get the current user ID from the JWT token
 */
async function getCurrentUserId(): Promise<string> {
  try {
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();
    if (token) {
      const decoded = jwtDecode<JwtPayload>(token);
      return decoded.sub || "";
    }
    return "";
  } catch (error) {
    console.error("Failed to get current user ID:", error);
    return "";
  }
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

interface CollectionsWidgetProps extends BaseWidgetProps {
  config?: CollectionsWidgetConfig;
}

export const CollectionsWidget: React.FC<CollectionsWidgetProps> = ({
  widgetId,
  isExpanded = false,
  config = DEFAULT_CONFIG,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget, updateWidgetConfig } = useDashboardActions();

  const [currentUserId, setCurrentUserId] = React.useState<string>("");
  const [isConfigOpen, setIsConfigOpen] = React.useState<boolean>(false);

  // Get current user ID on mount
  React.useEffect(() => {
    getCurrentUserId().then(setCurrentUserId);
  }, []);

  // Handle configuration changes
  const handleConfigChange = useCallback(
    (newConfig: CollectionsWidgetConfig) => {
      updateWidgetConfig(widgetId, newConfig);
    },
    [widgetId, updateWidgetConfig]
  );

  // Handle toggle configuration panel
  const handleToggleConfig = useCallback(() => {
    setIsConfigOpen((prev) => !prev);
  }, []);

  // Determine which API endpoint to use based on viewType
  const viewType = config.viewType;

  // Fetch collections from appropriate endpoint based on viewType
  // Note: We conditionally enable queries based on viewType to avoid unnecessary API calls
  const {
    data: standardCollectionsResponse,
    isLoading: isLoadingStandard,
    error: errorStandard,
    refetch: refetchStandard,
  } = useGetCollections(undefined);

  const {
    data: sharedWithMeResponse,
    isLoading: isLoadingSharedWithMe,
    error: errorSharedWithMe,
    refetch: refetchSharedWithMe,
  } = useGetCollectionsSharedWithMe();

  const {
    data: sharedByMeResponse,
    isLoading: isLoadingSharedByMe,
    error: errorSharedByMe,
    refetch: refetchSharedByMe,
  } = useGetCollectionsSharedByMe();

  const { data: collectionTypesResponse, isLoading: isLoadingTypes } = useGetCollectionTypes();

  // Select the appropriate data based on viewType
  const rawCollections = useMemo(() => {
    if (viewType === "shared-with-me") {
      return (sharedWithMeResponse?.data || []) as Collection[];
    } else if (viewType === "my-shared") {
      return (sharedByMeResponse?.data || []) as Collection[];
    } else {
      return (standardCollectionsResponse?.data || []) as Collection[];
    }
  }, [viewType, sharedWithMeResponse, sharedByMeResponse, standardCollectionsResponse]);

  // Determine loading and error states
  const isLoading =
    viewType === "shared-with-me"
      ? isLoadingSharedWithMe
      : viewType === "my-shared"
        ? isLoadingSharedByMe
        : isLoadingStandard;

  const error =
    viewType === "shared-with-me"
      ? errorSharedWithMe
      : viewType === "my-shared"
        ? errorSharedByMe
        : errorStandard;

  // Apply filtering and sorting
  const processedCollections = useMemo(() => {
    if (!rawCollections || !currentUserId) {
      return [];
    }

    // Apply filtering based on viewType
    const filtered = filterCollections(rawCollections, viewType, currentUserId);

    // Apply sorting
    const sorted = sortCollections(filtered, config.sorting);

    return sorted;
  }, [rawCollections, viewType, currentUserId, config.sorting]);

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
    if (viewType === "shared-with-me") {
      refetchSharedWithMe();
    } else if (viewType === "my-shared") {
      refetchSharedByMe();
    } else {
      refetchStandard();
    }
  }, [viewType, refetchSharedWithMe, refetchSharedByMe, refetchStandard]);

  const handleExpand = useCallback(() => {
    setExpandedWidget(widgetId);
  }, [setExpandedWidget, widgetId]);

  const handleRemove = useCallback(() => {
    removeWidget(widgetId);
  }, [removeWidget, widgetId]);

  // Get widget title based on viewType
  const getWidgetTitle = useCallback(() => {
    switch (viewType) {
      case "all":
        return t("dashboard.widgets.collections.allTitle", "All Collections");
      case "public":
        return t("dashboard.widgets.collections.publicTitle", "Public Collections");
      case "private":
        return t("dashboard.widgets.collections.privateTitle", "Private Collections");
      case "my-collections":
        return t("dashboard.widgets.collections.myCollectionsTitle", "My Collections");
      case "shared-with-me":
        return t("dashboard.widgets.collections.sharedWithMeTitle", "Shared With Me");
      case "my-shared":
        return t("dashboard.widgets.collections.mySharedTitle", "My Shared Collections");
      default:
        return t("dashboard.widgets.collections.title", "Collections");
    }
  }, [viewType, t]);

  const renderContent = () => {
    if (!processedCollections || processedCollections.length === 0) {
      return (
        <EmptyState
          icon={<CollectionIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.collections.emptyTitle", "No collections found")}
          description={t(
            "dashboard.widgets.collections.emptyDescription",
            "Create a collection to get started"
          )}
          actionLabel={t("dashboard.widgets.collections.createCollection", "Create Collection")}
          onAction={handleCreateCollection}
        />
      );
    }

    return (
      <CollectionCarousel
        items={processedCollections.slice(0, 20) as CollectionItem[]}
        isLoading={isLoading || isLoadingTypes}
        cardWidth={CARD_WIDTH}
        cardHeight={CARD_HEIGHT}
        getItemKey={(collection: CollectionItem) => collection.id}
        emptyState={
          <EmptyState
            icon={<CollectionIcon sx={{ fontSize: 48 }} />}
            title={t("dashboard.widgets.collections.emptyTitle", "No collections found")}
            description={t(
              "dashboard.widgets.collections.emptyDescription",
              "Create a collection to get started"
            )}
            actionLabel={t("dashboard.widgets.collections.createCollection", "Create Collection")}
            onAction={handleCreateCollection}
          />
        }
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
    );
  };

  return (
    <WidgetContainer
      widgetId={widgetId}
      title={getWidgetTitle()}
      icon={<CollectionIcon />}
      onExpand={handleExpand}
      onRefresh={handleRefresh}
      onRemove={handleRemove}
      onConfigure={handleToggleConfig}
      isLoading={isLoading || isLoadingTypes}
      isExpanded={isExpanded}
      error={error}
      onRetry={handleRefresh}
    >
      {isConfigOpen && (
        <Box
          sx={{
            mb: 2,
            p: 2,
            borderRadius: 1,
            backgroundColor: (theme) => theme.palette.background.paper,
            border: (theme) => `1px solid ${theme.palette.divider}`,
          }}
        >
          <WidgetConfigPanel config={config} onChange={handleConfigChange} />
        </Box>
      )}
      {renderContent()}
    </WidgetContainer>
  );
};
