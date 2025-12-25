import React, { useCallback, useMemo, useRef, useEffect, useState } from "react";
import { Box, Stack, Skeleton } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { Schedule as RecentIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useSearch } from "@/api/hooks/useSearch";
import AssetCard from "@/components/shared/AssetCard";
import { getOriginalAssetId } from "@/utils/clipTransformation";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { useDashboardActions } from "../../store/dashboardStore";
import type { BaseWidgetProps } from "../../types";

const CARD_WIDTH = 200;
const CARD_GAP = 16;

export const RecentAssetsWidget: React.FC<BaseWidgetProps> = ({ widgetId }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleCards, setVisibleCards] = useState(5);

  // Search for recent assets - using wildcard query sorted by date
  const {
    data: searchResponse,
    isLoading,
    error,
    refetch,
  } = useSearch("*", {
    pageSize: 20,
    isSemantic: false,
  });

  const assets = useMemo(() => {
    const results = searchResponse?.data?.results || [];
    // Sort by ingestion date descending (most recent first)
    return [...results].sort((a, b) => {
      const dateA = new Date(a.createDate || a.ingestedDate || 0).getTime();
      const dateB = new Date(b.createDate || b.ingestedDate || 0).getTime();
      return dateB - dateA;
    });
  }, [searchResponse]);

  // Calculate visible cards based on container width
  useEffect(() => {
    const calculateVisibleCards = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.offsetWidth;
        const cardsCount = Math.floor((containerWidth + CARD_GAP) / (CARD_WIDTH + CARD_GAP));
        setVisibleCards(Math.max(1, cardsCount));
      }
    };

    calculateVisibleCards();

    const resizeObserver = new ResizeObserver(calculateVisibleCards);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, []);

  const handleAssetClick = useCallback(
    (assetId: string, assetType: string) => {
      const pathPrefix =
        assetType?.toLowerCase() === "audio"
          ? "/audio/"
          : `/${assetType?.toLowerCase() || "image"}s/`;
      const originalAssetId = getOriginalAssetId({ InventoryID: assetId });
      navigate(`${pathPrefix}${originalAssetId}`);
    },
    [navigate]
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
          {Array.from({ length: visibleCards }).map((_, i) => (
            <Skeleton
              key={i}
              variant="rectangular"
              width={CARD_WIDTH}
              height={200}
              sx={{ borderRadius: 2, flexShrink: 0 }}
            />
          ))}
        </Stack>
      );
    }

    if (!assets || assets.length === 0) {
      return (
        <EmptyState
          icon={<RecentIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.recentAssets.emptyTitle")}
          description={t("dashboard.widgets.recentAssets.emptyDescription")}
        />
      );
    }

    return (
      <Box ref={containerRef} sx={{ width: "100%" }}>
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
          {assets.slice(0, Math.max(visibleCards * 2, 10)).map((asset) => (
            <Box
              key={asset.InventoryID || asset.id}
              sx={{
                minWidth: CARD_WIDTH,
                maxWidth: CARD_WIDTH,
                flexShrink: 0,
              }}
            >
              <AssetCard
                id={asset.InventoryID || asset.id}
                name={asset.filename || asset.name || "Untitled"}
                thumbnailUrl={asset.thumbnailUrl || asset.thumbnail || ""}
                assetType={asset.type || asset.assetType || "Image"}
                fields={[
                  { id: "name", label: "Name", visible: true },
                  { id: "type", label: "Type", visible: true },
                ]}
                renderField={(fieldId) => {
                  if (fieldId === "name") return asset.filename || asset.name || "Untitled";
                  if (fieldId === "type") return asset.type || asset.assetType || "Image";
                  return "";
                }}
                onAssetClick={() =>
                  handleAssetClick(
                    asset.InventoryID || asset.id,
                    asset.type || asset.assetType || "Image"
                  )
                }
                onDeleteClick={() => {}}
                onDownloadClick={() => {}}
                cardSize="small"
                aspectRatio="square"
                thumbnailScale="fill"
                showMetadata={true}
              />
            </Box>
          ))}
        </Stack>
      </Box>
    );
  };

  return (
    <WidgetContainer
      widgetId={widgetId}
      title={t("dashboard.widgets.recentAssets.title")}
      icon={<RecentIcon />}
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
