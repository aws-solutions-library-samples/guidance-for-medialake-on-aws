import React, { useCallback, useMemo } from "react";
import { Box } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { FolderOpen as CollectionIcon } from "@mui/icons-material";
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
import { CollectionCardSimple } from "../CollectionCardSimple";
import { useDashboardActions, useDashboardStore } from "../../store/dashboardStore";
import type { BaseWidgetProps, CollectionsWidgetConfig } from "../../types";
import { filterCollections, sortCollections } from "../../utils/collectionFilters";
import type { Collection } from "../../utils/collectionFilters";
import { fetchAuthSession } from "aws-amplify/auth";
import { jwtDecode } from "jwt-decode";
import { WidgetConfigPanel } from "./WidgetConfigPanel";

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
  thumbnailType?: "icon" | "upload" | "asset" | "frame";
  thumbnailValue?: string;
  thumbnailUrl?: string;
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
  const { removeWidget, setExpandedWidget, updateWidgetConfig, updateWidgetCustomName } =
    useDashboardActions();

  // Get widget instance from store to access customName
  const widgetInstance = useDashboardStore((state) =>
    state.layout.widgets.find((w) => w.id === widgetId)
  );
  const customName = widgetInstance?.customName;

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

  // Handle custom name changes
  const handleCustomNameChange = useCallback(
    (newCustomName: string | undefined) => {
      updateWidgetCustomName(widgetId, newCustomName);
    },
    [widgetId, updateWidgetCustomName]
  );

  // Handle toggle configuration panel
  const handleToggleConfig = useCallback(() => {
    setIsConfigOpen((prev) => !prev);
  }, []);

  // Determine which API endpoint to use based on viewType
  const viewType = config.viewType;

  // Fetch collections from appropriate endpoint based on viewType
  const collectionsParams = useMemo(() => {
    const params: any = {};
    if (config.groupIds && config.groupIds.length > 0) {
      params.groupIds = config.groupIds.join(",");
    }
    return params;
  }, [config.groupIds]);

  const {
    data: standardCollectionsResponse,
    isLoading: isLoadingStandard,
    error: errorStandard,
    refetch: refetchStandard,
  } = useGetCollections(collectionsParams);

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
    const filtered = filterCollections(rawCollections, viewType, currentUserId);
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

  // Get widget title based on viewType or use custom name
  const getWidgetTitle = useCallback(() => {
    if (customName) {
      return customName;
    }
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
  }, [viewType, customName, t]);

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
              name={collection.name}
              itemCount={collection.itemCount}
              childCollectionCount={collection.childCollectionCount}
              isPublic={collection.isPublic}
              iconName={typeInfo.iconName}
              color={typeInfo.color}
              thumbnailType={collection.thumbnailType}
              thumbnailValue={collection.thumbnailValue}
              thumbnailUrl={collection.thumbnailUrl}
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
          <WidgetConfigPanel
            widgetId={widgetId}
            customName={customName}
            config={config}
            onChange={handleConfigChange}
            onCustomNameChange={handleCustomNameChange}
            onClose={handleToggleConfig}
          />
        </Box>
      )}
      {renderContent()}
    </WidgetContainer>
  );
};
