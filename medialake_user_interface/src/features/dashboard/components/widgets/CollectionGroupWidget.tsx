/**
 * Collection Group Widget
 * Displays collections from a specific collection group
 */

import React, { useState, useCallback } from "react";
import { Box, Typography, Alert, CircularProgress } from "@mui/material";
import { FolderSpecial as FolderSpecialIcon } from "@mui/icons-material";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { WidgetContainer } from "../WidgetContainer";
import { CollectionCarousel } from "../CollectionCarousel";
import { CollectionCardSimple } from "../CollectionCardSimple";
import { EmptyState } from "../EmptyState";
import { CollectionGroupWidgetConfigPanel } from "./CollectionGroupWidgetConfigPanel";
import type { BaseWidgetProps, CollectionGroupWidgetConfig } from "../../types";
import { useDashboardStore, useDashboardActions } from "../../store/dashboardStore";
import { useCollectionGroup } from "@/features/collection-groups/hooks/useCollectionGroups";
import { useGetCollections, useGetCollectionTypes } from "@/api/hooks/useCollections";

const CARD_WIDTH = 240;
const CARD_HEIGHT = 200;

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
  thumbnailType?: string;
  thumbnailValue?: string;
  thumbnailUrl?: string;
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
