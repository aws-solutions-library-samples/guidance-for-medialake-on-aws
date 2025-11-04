import React, {
  useState,
  useMemo,
  useCallback,
  useEffect,
  ReactNode,
} from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  Tabs,
  Tab,
  alpha,
} from "@mui/material";
import {
  useAsset,
  useRelatedVersions,
  useTranscription,
} from "../../api/hooks/useAssets";
import { useRightSidebar } from "../common/RightSidebar";
import { useTrackRecentlyViewed } from "../../contexts/RecentlyViewedContext";
import AssetSidebar from "../asset/AssetSidebar";
import BreadcrumbNavigation from "../common/BreadcrumbNavigation";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import { RelatedItemsView } from "./RelatedItemsView";
import { AssetResponse } from "../../api/types/asset.types";
import type { RelatedVersionsResponse } from "../../api/hooks/useAssets";
import { formatFileSize } from "../../utils/imageUtils";
import TechnicalMetadataTab from "../TechnicalMetadataTab";
import TranscriptionTab from "./TranscriptionTab";
import TabContentContainer from "../common/TabContentContainer";

interface TabConfig {
  value: string;
  label: string;
  component: ReactNode;
}

interface BaseDetailPageProps {
  mediaType: "audio" | "video" | "image";
  assetTypeName: string;
  tabs: TabConfig[];
  renderMediaPlayer: (props: {
    proxyUrl: string;
    assetData: AssetResponse;
    mediaController?: any;
  }) => ReactNode;
  mediaPlayerHeight?: string;
  mediaPlayerMinHeight?: string;
  hasTranscription?: boolean;
  mediaController?: any;
  additionalSidebarProps?: Record<string, any>;
}

const RelatedItemsTab: React.FC<{
  assetId: string;
  relatedVersionsData: RelatedVersionsResponse | undefined;
  isLoading: boolean;
  onLoadMore: () => void;
}> = ({ assetId, relatedVersionsData, isLoading, onLoadMore }) => {
  const items = useMemo(() => {
    if (!relatedVersionsData?.data?.results) {
      return [];
    }

    return relatedVersionsData.data.results.map((result) => ({
      id: result.InventoryID,
      title:
        result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      type: result.DigitalSourceAsset.Type,
      thumbnail: result.thumbnailUrl,
      proxyUrl: result.proxyUrl,
      score: result.score,
      format: result.DigitalSourceAsset.MainRepresentation.Format,
      fileSize:
        result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .FileInfo.Size,
      createDate: result.DigitalSourceAsset.CreateDate,
    }));
  }, [relatedVersionsData]);

  const hasMore = useMemo(() => {
    if (!relatedVersionsData?.data?.searchMetadata) {
      return false;
    }

    const { totalResults, page, pageSize } =
      relatedVersionsData.data.searchMetadata;
    return totalResults > page * pageSize;
  }, [relatedVersionsData]);

  return (
    <RelatedItemsView
      items={items}
      isLoading={isLoading}
      onLoadMore={onLoadMore}
      hasMore={hasMore}
    />
  );
};

export const BaseDetailPage: React.FC<BaseDetailPageProps> = ({
  mediaType,
  assetTypeName,
  tabs,
  renderMediaPlayer,
  mediaPlayerHeight = "50vh",
  mediaPlayerMinHeight = "400px",
  hasTranscription = false,
  mediaController,
  additionalSidebarProps = {},
}) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { isExpanded } = useRightSidebar();
  const {
    data: assetData,
    isLoading,
    error,
  } = useAsset(id || "") as {
    data: AssetResponse | undefined;
    isLoading: boolean;
    error: any;
  };
  const [activeTab, setActiveTab] = useState<string>(
    tabs[0]?.value || "summary",
  );
  const [relatedPage, setRelatedPage] = useState(1);
  const { data: relatedVersionsData, isLoading: isLoadingRelated } =
    useRelatedVersions(id || "", relatedPage);
  const { data: transcriptionData, isLoading: isLoadingTranscription } =
    hasTranscription
      ? useTranscription(id || "")
      : { data: undefined, isLoading: false };
  const [showHeader, setShowHeader] = useState(true);

  const [comments, setComments] = useState([
    {
      user: "John Doe",
      avatar: "https://mui.com/static/images/avatar/1.jpg",
      content: "Great quality!",
      timestamp: "2023-06-15 09:30:22",
    },
    {
      user: "Jane Smith",
      avatar: "https://mui.com/static/images/avatar/2.jpg",
      content: "Perfect!",
      timestamp: "2023-06-15 10:15:43",
    },
    {
      user: "Mike Johnson",
      avatar: "https://mui.com/static/images/avatar/3.jpg",
      content: "Can we adjust this?",
      timestamp: "2023-06-15 11:22:17",
    },
  ]);

  useEffect(() => {
    const container = document.querySelector(
      '[class*="AppLayout"] [style*="overflow: auto"]',
    );
    if (container) {
      container.scrollTo(0, 0);
    } else {
      window.scrollTo(0, 0);
    }
  }, [id]);

  useEffect(() => {
    let lastScrollTop = 0;

    const handleScroll = () => {
      const currentScrollTop =
        document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]')
          ?.scrollTop || 0;

      if (currentScrollTop <= 10) {
        setShowHeader(true);
      } else if (currentScrollTop > lastScrollTop) {
        setShowHeader(false);
      } else if (currentScrollTop < lastScrollTop) {
        setShowHeader(true);
      }

      lastScrollTop = currentScrollTop;
    };

    const container = document.querySelector(
      '[class*="AppLayout"] [style*="overflow: auto"]',
    );
    if (container) {
      container.addEventListener("scroll", handleScroll, { passive: true });
    }

    return () => {
      if (container) {
        container.removeEventListener("scroll", handleScroll);
      }
    };
  }, []);

  const searchParams = new URLSearchParams(location.search);
  const searchTerm =
    searchParams.get("q") || searchParams.get("searchTerm") || "";

  const versions = useMemo(() => {
    if (!assetData?.data?.asset) return [];
    return [
      {
        id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
        src: assetData.data.asset.DigitalSourceAsset.MainRepresentation
          .StorageInfo.PrimaryLocation.ObjectKey.FullPath,
        type: "Original",
        format:
          assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format,
        fileSize:
          assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size.toString(),
        description: "Original high resolution version",
      },
      ...assetData.data.asset.DerivedRepresentations.map((rep) => ({
        id: rep.ID,
        src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
        type: rep.Purpose.charAt(0).toUpperCase() + rep.Purpose.slice(1),
        format: rep.Format,
        fileSize: rep.StorageInfo.PrimaryLocation.FileInfo.Size.toString(),
        description: `${rep.Purpose} version`,
      })),
    ];
  }, [assetData]);

  const transformMetadata = (metadata: any) => {
    if (!metadata) return [];

    return Object.entries(metadata).map(([parentCategory, parentData]) => ({
      category: parentCategory,
      subCategories: Object.entries(parentData as object).map(
        ([subCategory, data]) => ({
          category: subCategory,
          data: data,
          count:
            typeof data === "object"
              ? Array.isArray(data)
                ? data.length
                : Object.keys(data).length
              : 1,
        }),
      ),
      count: Object.keys(parentData as object).length,
    }));
  };

  const metadataAccordions = useMemo(() => {
    if (!assetData?.data?.asset?.Metadata) return [];
    return transformMetadata(assetData.data.asset.Metadata);
  }, [assetData]);

  const recentlyViewedItem = useMemo(() => {
    if (!id || !assetData?.data?.asset) return null;
    const asset = assetData.data.asset;
    return {
      id,
      title:
        asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      type: asset.DigitalSourceAsset.Type.toLowerCase() as
        | "video"
        | "image"
        | "audio",
      path: `/${mediaType}/${id}`,
      searchTerm: searchTerm,
      metadata: {
        fileSize: formatFileSize(
          asset.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.FileInfo.Size,
        ),
      },
    };
  }, [id, assetData, mediaType, searchTerm]);

  useTrackRecentlyViewed(recentlyViewedItem);

  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const tabValues = tabs.map((t) => t.value);
      const currentIndex = tabValues.indexOf(activeTab);

      if (event.key === "ArrowRight") {
        const nextIndex = (currentIndex + 1) % tabValues.length;
        setActiveTab(tabValues[nextIndex]);
      } else if (event.key === "ArrowLeft") {
        const prevIndex =
          (currentIndex - 1 + tabValues.length) % tabValues.length;
        setActiveTab(tabValues[prevIndex]);
      }
    },
    [activeTab, tabs],
  );

  const handleBack = useCallback(() => {
    if (
      location.state &&
      (location.state.searchTerm || location.state.preserveSearch)
    ) {
      navigate(-1);
    } else {
      navigate(
        `/search${searchTerm ? `?q=${encodeURIComponent(searchTerm)}` : ""}`,
      );
    }
  }, [navigate, location.state, searchTerm]);

  const handleAddComment = (comment: string) => {
    const now = new Date().toISOString();
    const formattedTimestamp = formatLocalDateTime(now, { showSeconds: true });

    const newComment = {
      user: "Current User",
      avatar: "https://mui.com/static/images/avatar/1.jpg",
      content: comment,
      timestamp: formattedTimestamp,
    };
    setComments([...comments, newComment]);
  };

  if (isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error || !assetData) {
    return (
      <Box sx={{ p: 3 }}>
        <BreadcrumbNavigation
          searchTerm={searchTerm}
          currentResult={48}
          totalResults={156}
          onBack={handleBack}
          onPrevious={() => navigate(-1)}
          onNext={() => navigate(1)}
        />
      </Box>
    );
  }

  const proxyUrl = (() => {
    const proxyRep = assetData.data.asset.DerivedRepresentations.find(
      (rep) => rep.Purpose === "proxy",
    );
    return (
      proxyRep?.URL ||
      assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo
        .PrimaryLocation.ObjectKey.FullPath
    );
  })();

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        maxWidth: isExpanded ? "calc(100% - 300px)" : "100%",
        transition: (theme) =>
          theme.transitions.create(["max-width"], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        bgcolor: "transparent",
      }}
    >
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 1000,
          transform: showHeader ? "translateY(0)" : "translateY(-100%)",
          transition: "transform 0.3s ease-in-out",
          visibility: showHeader ? "visible" : "hidden",
          opacity: showHeader ? 1 : 0,
        }}
      >
        <Box sx={{ py: 0, mb: 0 }}>
          <BreadcrumbNavigation
            searchTerm={searchTerm}
            currentResult={48}
            totalResults={156}
            onBack={handleBack}
            onPrevious={() => navigate(-1)}
            onNext={() => navigate(1)}
            assetName={
              assetData.data.asset.DigitalSourceAsset.MainRepresentation
                .StorageInfo.PrimaryLocation.ObjectKey.Name
            }
            assetId={assetData.data.asset.InventoryID}
            assetType={assetTypeName}
          />
        </Box>
      </Box>

      <Box
        sx={{
          px: 3,
          pt: 0,
          pb: 3,
          height: mediaPlayerHeight,
          minHeight: mediaPlayerMinHeight,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            background: "transparent",
            position: "relative",
            height: "100%",
          }}
        >
          {renderMediaPlayer({ proxyUrl, assetData, mediaController })}
        </Paper>
      </Box>

      <Box sx={{ px: 3, pb: 3 }}>
        <Box sx={{ mt: 1 }}>
          <Paper
            elevation={0}
            sx={{
              p: 0,
              borderRadius: 2,
              overflow: "visible",
              background: "transparent",
            }}
          >
            <Tabs
              value={activeTab}
              onChange={(e, newValue) => setActiveTab(newValue)}
              onKeyDown={handleTabKeyDown}
              textColor="secondary"
              indicatorColor="secondary"
              aria-label="metadata tabs"
              sx={{
                px: 2,
                pt: 1,
                "& .MuiTab-root": {
                  minWidth: "auto",
                  px: 2,
                  py: 1.5,
                  fontWeight: 500,
                  transition: "all 0.2s",
                  "&:hover": {
                    backgroundColor: (theme) =>
                      alpha(theme.palette.secondary.main, 0.05),
                  },
                },
              }}
            >
              {tabs.map((tab) => (
                <Tab
                  key={tab.value}
                  value={tab.value}
                  label={tab.label}
                  id={`tab-${tab.value}`}
                  aria-controls={`tabpanel-${tab.value}`}
                />
              ))}
            </Tabs>
            <Box
              sx={{
                mt: 3,
                mx: 3,
                mb: 3,
                pt: 2,
                outline: "none",
                borderRadius: 1,
                backgroundColor: (theme) =>
                  alpha(theme.palette.background.paper, 0.5),
                maxHeight: "none",
                overflow: "visible",
              }}
              role="tabpanel"
              id={`tabpanel-${activeTab}`}
              aria-labelledby={`tab-${activeTab}`}
              tabIndex={0}
            >
              {tabs.map((tab) => {
                if (tab.value === activeTab) {
                  if (
                    (tab.value === "summary" || tab.value === "descriptive") &&
                    tab.component
                  ) {
                    return React.cloneElement(
                      tab.component as React.ReactElement,
                      {
                        key: tab.value,
                        assetData,
                      },
                    );
                  } else if (tab.value === "technical") {
                    return (
                      <TechnicalMetadataTab
                        key={tab.value}
                        metadataAccordions={metadataAccordions}
                        availableCategories={Object.keys(
                          assetData?.data?.asset?.Metadata?.EmbeddedMetadata ||
                            {},
                        )}
                        mediaType={mediaType}
                      />
                    );
                  } else if (
                    tab.value === "transcription" &&
                    hasTranscription &&
                    (mediaType === "audio" || mediaType === "video")
                  ) {
                    return (
                      <TranscriptionTab
                        key={tab.value}
                        assetId={id || ""}
                        transcriptionData={transcriptionData}
                        isLoading={isLoadingTranscription}
                        assetData={assetData}
                        mediaType={mediaType as "audio" | "video"}
                        mediaController={mediaController}
                      />
                    );
                  } else if (tab.value === "related") {
                    return (
                      <RelatedItemsTab
                        key={tab.value}
                        assetId={id || ""}
                        relatedVersionsData={relatedVersionsData}
                        isLoading={isLoadingRelated}
                        onLoadMore={() => setRelatedPage((prev) => prev + 1)}
                      />
                    );
                  }
                  return tab.component;
                }
                return null;
              })}
            </Box>
          </Paper>
        </Box>
      </Box>

      <AssetSidebar
        versions={versions}
        comments={comments}
        onAddComment={handleAddComment}
        assetId={assetData?.data?.asset?.InventoryID}
        {...additionalSidebarProps}
      />
    </Box>
  );
};
