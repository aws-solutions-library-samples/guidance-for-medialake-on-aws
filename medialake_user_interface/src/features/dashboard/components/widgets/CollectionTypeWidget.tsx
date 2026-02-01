import React, { useState } from "react";
import { Box, Typography, Alert, CircularProgress, Chip } from "@mui/material";
import { Category as CategoryIcon } from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import { WidgetContainer } from "../WidgetContainer";
import { CollectionCarousel } from "../CollectionCarousel";
import { EmptyState } from "../EmptyState";
import { CollectionTypeWidgetConfigPanel } from "./CollectionTypeWidgetConfigPanel";
import type { BaseWidgetProps, CollectionTypeWidgetConfig } from "../../types";
import { useDashboardStore } from "../../store/dashboardStore";
import { useGetCollections, useGetCollectionTypes } from "@/api/hooks/useCollections";

interface CollectionTypeWidgetProps extends BaseWidgetProps {}

export const CollectionTypeWidget: React.FC<CollectionTypeWidgetProps> = ({
  widgetId,
  isExpanded = false,
  onDataLoad,
  onError,
}) => {
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  
  const widget = useDashboardStore(
    (state) => state.layout.widgets.find((w) => w.id === widgetId)
  );

  const config = widget?.config as CollectionTypeWidgetConfig | undefined;
  const customName = widget?.customName;

  // Fetch collection types
  const { data: typesData } = useGetCollectionTypes();
  const collectionTypes = typesData?.data || [];
  
  // Find the specific type
  const collectionType = collectionTypes.find((t: any) => t.id === config?.collectionTypeId);

  // Fetch collections filtered by this type
  const {
    data: collectionsData,
    isLoading: isLoadingCollections,
    error: collectionsError,
    refetch,
  } = useGetCollections(
    config?.collectionTypeId ? { collectionTypeId: config.collectionTypeId } : undefined
  );

  const isLoading = isLoadingCollections;
  const error = collectionsError;

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

  const collections = collectionsData?.data || [];

  // Determine widget title
  const widgetTitle = customName || (collectionType?.name ? `Type: ${collectionType.name}` : "Collection Type");

  return (
    <>
      <WidgetContainer
        widgetId={widgetId}
        title={widgetTitle}
        icon={<CategoryIcon />}
        onRefresh={handleRefresh}
        onConfigure={handleConfigure}
        isLoading={isLoading}
        isExpanded={isExpanded}
      >
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
          {error ? (
            <Alert severity="error">
              Failed to load collection type. Please try again.
            </Alert>
          ) : !config?.collectionTypeId ? (
            <EmptyState
              icon={<CategoryIcon sx={{ fontSize: 60 }} />}
              title="No Type Selected"
              description="Configure this widget to select a collection type"
              actionLabel="Configure"
              onAction={handleConfigure}
            />
          ) : isLoading ? (
            <Box display="flex" justifyContent="center" alignItems="center" flex={1}>
              <CircularProgress />
            </Box>
          ) : collections.length === 0 ? (
            <EmptyState
              icon={<CategoryIcon sx={{ fontSize: 60 }} />}
              title="No Collections"
              description={`No collections of type "${collectionType?.name}" exist yet`}
            />
          ) : (
            <Box sx={{ flex: 1, overflow: "hidden" }}>
              {collectionType && (
                <Box sx={{ mb: 2, px: 2, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
                  {collectionType.color && (
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        backgroundColor: collectionType.color,
                        border: "1px solid",
                        borderColor: "divider",
                      }}
                    />
                  )}
                  {collectionType.description && (
                    <Typography variant="body2" color="text.secondary">
                      {collectionType.description}
                    </Typography>
                  )}
                  {collectionType.isSystem && (
                    <Chip label="System" size="small" variant="outlined" />
                  )}
                </Box>
              )}
              <CollectionCarousel
                items={collections}
                isLoading={isLoading}
                getItemKey={(collection: any) => collection.id}
                renderCard={(collection: any) => (
                  <div>{collection.name}</div>
                )}
              />
            </Box>
          )}
        </Box>
      </WidgetContainer>

      {configPanelOpen && (
        <CollectionTypeWidgetConfigPanel
          open={configPanelOpen}
          onClose={() => setConfigPanelOpen(false)}
          widgetId={widgetId}
          config={config}
        />
      )}
    </>
  );
};
