/**
 * Collection Group Widget
 * Displays collections from a specific collection group
 */

import React, { useState } from "react";
import { Box, Typography, Alert, CircularProgress } from "@mui/material";
import { FolderSpecial as FolderSpecialIcon } from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import { WidgetContainer } from "../WidgetContainer";
import { CollectionCarousel } from "../CollectionCarousel";
import { EmptyState } from "../EmptyState";
import { CollectionGroupWidgetConfigPanel } from "./CollectionGroupWidgetConfigPanel";
import type { BaseWidgetProps, CollectionGroupWidgetConfig } from "../../types";
import { useDashboardStore } from "../../store/dashboardStore";
import { useCollectionGroup } from "@/features/collection-groups/hooks/useCollectionGroups";
import { useGetCollections } from "@/api/hooks/useCollections";

interface CollectionGroupWidgetProps extends BaseWidgetProps {}

export const CollectionGroupWidget: React.FC<CollectionGroupWidgetProps> = ({
  widgetId,
  isExpanded = false,
  onDataLoad,
  onError,
}) => {
  const [configPanelOpen, setConfigPanelOpen] = useState(false);

  const widget = useDashboardStore((state) => state.layout.widgets.find((w) => w.id === widgetId));

  const config = widget?.config as CollectionGroupWidgetConfig | undefined;
  const customName = widget?.customName;

  // Fetch the group details
  const {
    data: groupData,
    isLoading: isLoadingGroup,
    error: groupError,
  } = useCollectionGroup(config?.groupId || "");

  // Fetch collections filtered by this group
  const {
    data: collectionsData,
    isLoading: isLoadingCollections,
    error: collectionsError,
    refetch,
  } = useGetCollections(config?.groupId ? { groupIds: config.groupId } : undefined);

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

  const handleRefresh = () => {
    refetch();
  };

  const handleConfigure = () => {
    setConfigPanelOpen(true);
  };

  const group = groupData?.data;
  const collections = collectionsData?.data || [];

  // Determine widget title
  const widgetTitle = customName || (group?.name ? `Group: ${group.name}` : "Collection Group");

  return (
    <>
      <WidgetContainer
        widgetId={widgetId}
        title={widgetTitle}
        icon={<FolderSpecialIcon />}
        onRefresh={handleRefresh}
        onConfigure={handleConfigure}
        isLoading={isLoading}
        isExpanded={isExpanded}
      >
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
          {error ? (
            <Alert severity="error">Failed to load collection group. Please try again.</Alert>
          ) : !config?.groupId ? (
            <EmptyState
              icon={<FolderSpecialIcon sx={{ fontSize: 60 }} />}
              title="No Group Selected"
              description="Configure this widget to select a collection group"
              actionLabel="Configure"
              onAction={handleConfigure}
            />
          ) : isLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" flex={1}>
              <CircularProgress />
            </Box>
          ) : collections.length === 0 ? (
            <EmptyState
              icon={<FolderSpecialIcon sx={{ fontSize: 60 }} />}
              title="No Collections"
              description={`The group "${group?.name}" doesn't have any collections yet`}
            />
          ) : (
            <Box sx={{ flex: 1, overflow: "hidden" }}>
              {group?.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2, px: 2 }}>
                  {group.description}
                </Typography>
              )}
              <CollectionCarousel
                items={collections}
                isLoading={isLoading}
                getItemKey={(collection: any) => collection.id}
                renderCard={(collection: any) => <div>{collection.name}</div>}
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
