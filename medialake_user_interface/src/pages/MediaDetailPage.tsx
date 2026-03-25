import React, { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useMediaController } from "../hooks/useMediaController";
import { useParams, useNavigate, useLocation } from "react-router";
import { Box, CircularProgress, Typography, Paper, Tabs, Tab, alpha } from "@mui/material";
import {
  useAsset,
  useRelatedVersions,
  useTranscription,
  RelatedVersionsResponse,
} from "../api/hooks/useAssets";
import { RightSidebarProvider, useRightSidebar } from "../components/common/RightSidebar";
import { RecentlyViewedProvider, useTrackRecentlyViewed } from "../contexts/RecentlyViewedContext";
import AssetSidebar from "../components/asset/AssetSidebar";
import BreadcrumbNavigation from "../components/common/BreadcrumbNavigation";
import { OmakaseDetailPlayer } from "../components/player/OmakaseDetailPlayer";
import type { UseDetailPlayerResult } from "../components/player/useDetailPlayer";
import { getPlayerCurrentTime } from "../components/player/playerTimeStore";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import { RelatedItemsView } from "../components/shared/RelatedItemsView";
import { AssetResponse } from "../api/types/asset.types";
import { formatFileSize } from "../utils/imageUtils";
import TechnicalMetadataTab from "../components/TechnicalMetadataTab";
import TranscriptionTab from "../components/shared/TranscriptionTab";
import DescriptiveTab from "../components/shared/DescriptiveTab";
import TabContentContainer from "../components/common/TabContentContainer";
import { springEasing } from "@/constants";
import { zIndexTokens } from "@/theme/tokens";
import { useTheme as useMuiTheme } from "@mui/material/styles";

const SummaryTab = ({ assetData, mediaType }: { assetData: any; mediaType: "video" | "audio" }) => {
  const theme = useMuiTheme();
  const fileInfoColor = theme.palette.primary.main;
  const techDetailsColor = (theme.palette as any).accent?.main ?? theme.palette.primary.main;

  const s3Bucket =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
      ?.Bucket;
  const objectName =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
      ?.ObjectKey?.Name;
  const fullPath =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
      ?.ObjectKey?.FullPath;
  const s3Uri = s3Bucket && fullPath ? `s3://${s3Bucket}/${fullPath}` : "Unknown";

  const metadata = assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {};
  const generalMetadata = metadata.general || {};

  const fileSize =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation
      ?.FileInfo?.Size || 0;
  const format =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format || "Unknown";
  const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
    ? new Date(assetData.data.asset.DigitalSourceAsset.CreateDate).toLocaleDateString()
    : "Unknown";

  // Video-specific extraction
  const videoMetadata = Array.isArray(metadata.video) ? metadata.video[0] : {};
  const videoDuration = generalMetadata.Duration
    ? `${parseFloat(generalMetadata.Duration).toFixed(2)}`
    : "Unknown";
  const width = videoMetadata.Width ?? "Unknown";
  const height = videoMetadata.Height ?? "Unknown";
  const frameRate = videoMetadata.FrameRate ? `${videoMetadata.FrameRate} FPS` : "Unknown";
  const videoBitRate =
    videoMetadata.OverallBitRate || videoMetadata.BitRate
      ? `${Math.round((videoMetadata.OverallBitRate || videoMetadata.BitRate) / 1000)} kbps`
      : "Unknown";
  const videoCodec = videoMetadata.codec_name || generalMetadata.Format || "Unknown";

  // Audio-specific extraction
  const audioMeta = Array.isArray(metadata.audio) ? metadata.audio[0] : {};
  const audioDuration =
    audioMeta.duration != null
      ? parseFloat(String(audioMeta.duration)).toFixed(2)
      : generalMetadata.Duration
        ? parseFloat(generalMetadata.Duration).toFixed(2)
        : "Unknown";
  const sampleRate = audioMeta.sample_rate
    ? (parseInt(String(audioMeta.sample_rate), 10) / 1000).toFixed(1)
    : "Unknown";
  const bitDepth = audioMeta.BitsPerSample || audioMeta.bit_depth || "Unknown";
  const channels = audioMeta.channels || audioMeta.Channels || "Unknown";
  const audioBitRate = audioMeta.bit_rate
    ? `${Math.round(Number(audioMeta.bit_rate) / 1000)} kbps`
    : "Unknown";
  const audioCodec = audioMeta.codec_name || generalMetadata.Format || "Unknown";

  const duration = mediaType === "video" ? videoDuration : audioDuration;
  const bitRate = mediaType === "video" ? videoBitRate : audioBitRate;
  const codec = mediaType === "video" ? videoCodec : audioCodec;

  return (
    <TabContentContainer>
      {/* File Information Section */}
      <Box sx={{ mb: 3 }}>
        <Typography
          sx={{
            color: fileInfoColor,
            fontSize: "0.875rem",
            fontWeight: 600,
            mb: 0.5,
          }}
        >
          File Information
        </Typography>
        <Box
          sx={{
            width: "100%",
            height: "1px",
            bgcolor: fileInfoColor,
            mb: 2,
          }}
        />

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Type:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {assetData?.data?.asset?.DigitalSourceAsset?.Type ||
              (mediaType === "video" ? "Video" : "Audio")}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Size:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{formatFileSize(fileSize)}</Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Format:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{format}</Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            S3 Bucket:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
            {s3Bucket || "Unknown"}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Object Name:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
            {objectName || "Unknown"}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            S3 URI:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
            {s3Uri}
          </Typography>
        </Box>
      </Box>

      {/* Technical Details Section */}
      <Box sx={{ mb: 3 }}>
        <Typography
          sx={{
            color: techDetailsColor,
            fontSize: "0.875rem",
            fontWeight: 600,
            mb: 0.5,
          }}
        >
          Technical Details
        </Typography>
        <Box
          sx={{
            width: "100%",
            height: "1px",
            bgcolor: techDetailsColor,
            mb: 2,
          }}
        />

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Duration:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{duration} seconds</Typography>
        </Box>

        {mediaType === "video" && (
          <>
            <Box sx={{ display: "flex", mb: 1 }}>
              <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
                Resolution:
              </Typography>
              <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
                {width}x{height}
              </Typography>
            </Box>
            <Box sx={{ display: "flex", mb: 1 }}>
              <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
                Frame Rate:
              </Typography>
              <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{frameRate} FPS</Typography>
            </Box>
          </>
        )}

        {mediaType === "audio" && (
          <>
            <Box sx={{ display: "flex", mb: 1 }}>
              <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
                Sample Rate:
              </Typography>
              <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{sampleRate} kHz</Typography>
            </Box>
            <Box sx={{ display: "flex", mb: 1 }}>
              <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
                Bit Depth:
              </Typography>
              <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{bitDepth} bit</Typography>
            </Box>
            <Box sx={{ display: "flex", mb: 1 }}>
              <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
                Channels:
              </Typography>
              <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{channels}</Typography>
            </Box>
          </>
        )}

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Bit Rate:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{bitRate}</Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Codec:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{codec}</Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
            Created Date:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>{createdDate}</Typography>
        </Box>
      </Box>
    </TabContentContainer>
  );
};

const RelatedItemsTab: React.FC<{
  assetId: string;
  relatedVersionsData: RelatedVersionsResponse | undefined;
  isLoading: boolean;
  onLoadMore: () => void;
}> = ({ relatedVersionsData, isLoading, onLoadMore }) => {
  const items = useMemo(() => {
    if (!relatedVersionsData?.data?.results) {
      return [];
    }

    const mappedItems = relatedVersionsData.data.results.map((result) => ({
      id: result.InventoryID,
      title:
        result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
      type: result.DigitalSourceAsset.Type,
      thumbnail: result.thumbnailUrl,
      proxyUrl: result.proxyUrl,
      score: result.score,
      format: result.DigitalSourceAsset.MainRepresentation.Format,
      fileSize:
        result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
      createDate: result.DigitalSourceAsset.CreateDate,
    }));
    return mappedItems;
  }, [relatedVersionsData]);

  const hasMore = useMemo(() => {
    if (!relatedVersionsData?.data?.searchMetadata) {
      return false;
    }

    const { totalResults, page, pageSize } = relatedVersionsData.data.searchMetadata;
    const hasMoreItems = totalResults > page * pageSize;
    return hasMoreItems;
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

interface MediaDetailContentProps {
  asset: any;
  searchTerm?: string;
}

const MediaDetailContent: React.FC<MediaDetailContentProps> = ({ asset, searchTerm }) => {
  const location = useLocation();
  const mediaType: "video" | "audio" = location.pathname.startsWith("/audio") ? "audio" : "video";

  const { t } = useTranslation();
  const playerResultRef = useRef<UseDetailPlayerResult | null>(null);
  const [markerReady, setMarkerReady] = useState(false);
  const playerSeekRef = useRef<((time: number) => void) | null>(null);
  // Throttle mediaController time updates to ~10 Hz (transcript highlighting doesn't need 60 Hz)
  const lastMediaControllerUpdate = useRef(0);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
  const [activeTab, setActiveTab] = useState<string>("summary");
  const [relatedPage, setRelatedPage] = useState(1);
  const { data: relatedVersionsData, isLoading: isLoadingRelated } = useRelatedVersions(
    id || "",
    relatedPage
  );
  const { data: transcriptionData, isLoading: isLoadingTranscription } = useTranscription(id || "");
  const [showHeader, setShowHeader] = useState(true);

  const mediaController = useMediaController();

  const handlePlayerReady = useCallback(
    (result: UseDetailPlayerResult) => {
      playerResultRef.current = result;
      setMarkerReady(result.isMarkerReady);
      playerSeekRef.current = result.seek;
      const refLike = {
        current: { seek: result.seek, getCurrentTime: () => getPlayerCurrentTime() },
      };
      mediaController.registerVideoElement(refLike as any);
    },
    [mediaController.registerVideoElement]
  );

  const [comments, setComments] = useState<
    Array<{
      user: string;
      avatar: string;
      content: string;
      timestamp: string;
    }>
  >([]);

  // Scroll to top when component mounts
  useEffect(() => {
    const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
    if (container) {
      container.scrollTo(0, 0);
    } else {
      window.scrollTo(0, 0);
    }
  }, [id]);

  // Track scroll position to hide/show header
  useEffect(() => {
    let lastScrollTop = 0;

    const handleScroll = () => {
      const currentScrollTop =
        document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]')?.scrollTop || 0;

      if (currentScrollTop <= 10) {
        setShowHeader(true);
      } else if (currentScrollTop > lastScrollTop) {
        setShowHeader(false);
      } else if (currentScrollTop < lastScrollTop) {
        setShowHeader(true);
      }

      lastScrollTop = currentScrollTop;
    };

    const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
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
  const urlSearchTerm = searchParams.get("q") || searchParams.get("searchTerm") || "";
  const effectiveSearchTerm = searchTerm || urlSearchTerm;

  const versions = useMemo(() => {
    if (!assetData?.data?.asset) return [];
    return [
      {
        id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
        src: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.FullPath,
        type: "Original",
        format: assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format,
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
      subCategories: Object.entries(parentData as object).map(([subCategory, data]) => ({
        category: subCategory,
        data: data,
        count:
          typeof data === "object"
            ? Array.isArray(data)
              ? data.length
              : Object.keys(data).length
            : 1,
      })),
      count: Object.keys(parentData as object).length,
    }));
  };

  const metadataAccordions = useMemo(() => {
    if (!assetData?.data?.asset?.Metadata) return [];
    return transformMetadata(assetData.data.asset.Metadata);
  }, [assetData]);

  const availableCategoryKeys = useMemo(() => {
    const embedded = assetData?.data?.asset?.Metadata?.EmbeddedMetadata ?? {};
    return Object.keys(embedded);
  }, [assetData]);

  const handleAddComment = (comment: string) => {
    const now = new Date().toISOString();
    const formattedTimestamp = formatLocalDateTime(now, { showSeconds: true });

    const newComment = {
      user: "Current User",
      avatar: "https://mui.com/static/videos/avatar/1.jpg",
      content: comment,
      timestamp: formattedTimestamp,
    };
    setComments([...comments, newComment]);
  };

  // Track this asset in recently viewed
  useTrackRecentlyViewed(
    assetData
      ? {
          id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
          title:
            assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
              .ObjectKey.Name,
          type:
            mediaType === "audio"
              ? ("audio" as const)
              : (assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "video"),
          path:
            mediaType === "audio"
              ? `/audio/${assetData.data.asset.InventoryID}`
              : `/${assetData.data.asset.DigitalSourceAsset.Type.toLowerCase()}s/${
                  assetData.data.asset.InventoryID
                }`,
          searchTerm: effectiveSearchTerm,
          metadata:
            mediaType === "audio"
              ? {
                  duration: "42:18",
                  fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
                  creator: "John Doe",
                }
              : {
                  duration: "00:15",
                  fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
                  dimensions: "1920x1080",
                  creator: "John Doe",
                },
        }
      : null
  );

  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const tabs = ["summary", "technical", "descriptive", "transcription", "related"];
      const currentIndex = tabs.indexOf(activeTab);

      if (event.key === "ArrowRight") {
        const nextIndex = (currentIndex + 1) % tabs.length;
        setActiveTab(tabs[nextIndex]);
      } else if (event.key === "ArrowLeft") {
        const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        setActiveTab(tabs[prevIndex]);
      }
    },
    [activeTab]
  );

  const handleBack = useCallback(() => {
    if (location.state && (location.state.searchTerm || location.state.preserveSearch)) {
      navigate(-1);
    } else {
      navigate(
        `/search${effectiveSearchTerm ? `?q=${encodeURIComponent(effectiveSearchTerm)}` : ""}`
      );
    }
  }, [navigate, location.state, effectiveSearchTerm]);

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
          searchTerm={effectiveSearchTerm}
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
      (rep) => rep.Purpose === "proxy"
    );
    return (
      proxyRep?.URL ||
      assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.FullPath
    );
  })();

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        maxWidth: isExpanded ? "calc(100% - 300px)" : "100%",
        width: "100%",
        transition: (theme) =>
          `max-width ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
        bgcolor: "transparent",
      }}
    >
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: zIndexTokens.stickyHeader,
          transform: showHeader ? "translateY(0)" : "translateY(-100%)",
          transition: "transform 0.3s ease-in-out",
          visibility: showHeader ? "visible" : "hidden",
          opacity: showHeader ? 1 : 0,
        }}
      >
        <Box sx={{ py: 0, mb: 0 }}>
          <BreadcrumbNavigation
            searchTerm={effectiveSearchTerm}
            currentResult={48}
            totalResults={156}
            onBack={handleBack}
            onPrevious={() => navigate(-1)}
            onNext={() => navigate(1)}
            assetName={
              assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
                .ObjectKey.Name
            }
            assetId={assetData.data.asset.InventoryID}
            assetType={mediaType === "video" ? "Video" : "Audio"}
          />
        </Box>
      </Box>

      <Box
        sx={{
          px: 3,
          pt: 0,
          pb: 0,
          mt: 0,
          height: "75vh",
          minHeight: "600px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
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
            width: "100%",
            maxWidth: isExpanded ? "calc(100% - 10px)" : "100%",
            transition: (theme) =>
              `width ${theme.transitions.duration.enteringScreen}ms ${springEasing}, max-width ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
          }}
        >
          <OmakaseDetailPlayer
            src={proxyUrl}
            mediaType={mediaType}
            assetId={id || ""}
            onTimeUpdate={(time) => {
              const now = performance.now();
              if (now - lastMediaControllerUpdate.current > 100) {
                lastMediaControllerUpdate.current = now;
                mediaController.updateCurrentTime(time);
              }
            }}
            onPlayerReady={handlePlayerReady}
          />
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
                  transition: "background-color 0.2s, color 0.2s",
                  "&:hover": {
                    backgroundColor: (theme) => alpha(theme.palette.secondary.main, 0.05),
                  },
                },
              }}
            >
              <Tab
                value="summary"
                label={t("detailPages.tabs.summary")}
                id="tab-summary"
                aria-controls="tabpanel-summary"
              />
              <Tab
                value="technical"
                label={t("detailPages.tabs.technical")}
                id="tab-technical"
                aria-controls="tabpanel-technical"
              />
              <Tab
                value="descriptive"
                label={t("detailPages.tabs.descriptive")}
                id="tab-descriptive"
                aria-controls="tabpanel-descriptive"
              />
              <Tab
                value="transcription"
                label={t("detailPages.tabs.transcription")}
                id="tab-transcription"
                aria-controls="tabpanel-transcription"
              />
              <Tab
                value="related"
                label={t("detailPages.tabs.relatedItems")}
                id="tab-related"
                aria-controls="tabpanel-related"
              />
            </Tabs>
            <Box
              sx={{
                mt: 3,
                mx: 3,
                mb: 3,
                pt: 2,
                outline: "none",
                borderRadius: 1,
                backgroundColor: (theme) => alpha(theme.palette.background.paper, 0.5),
                maxHeight: "none",
                overflow: "visible",
              }}
              role="tabpanel"
              id={`tabpanel-${activeTab}`}
              aria-labelledby={`tab-${activeTab}`}
              tabIndex={0}
            >
              {activeTab === "summary" && (
                <SummaryTab assetData={assetData} mediaType={mediaType} />
              )}
              {activeTab === "technical" && (
                <TechnicalMetadataTab
                  metadataAccordions={metadataAccordions}
                  availableCategories={availableCategoryKeys}
                  mediaType={mediaType}
                />
              )}
              {activeTab === "descriptive" && <DescriptiveTab assetData={assetData} />}
              {activeTab === "transcription" && (
                <TranscriptionTab
                  assetId={id || ""}
                  transcriptionData={transcriptionData}
                  isLoading={isLoadingTranscription}
                  assetData={assetData}
                  mediaType={mediaType}
                  mediaController={mediaController}
                />
              )}
              {activeTab === "related" && (
                <RelatedItemsTab
                  assetId={id || ""}
                  relatedVersionsData={relatedVersionsData}
                  isLoading={isLoadingRelated}
                  onLoadMore={() => setRelatedPage((prev) => prev + 1)}
                />
              )}
            </Box>
          </Paper>
        </Box>
      </Box>

      <AssetSidebar
        versions={versions}
        comments={comments}
        onAddComment={handleAddComment}
        markerAdapter={playerResultRef.current?.markerAdapter}
        isMarkerReady={markerReady}
        seek={playerSeekRef.current ?? undefined}
        assetId={assetData?.data?.asset?.InventoryID}
        asset={asset}
        assetType={mediaType === "video" ? "Video" : "Audio"}
        searchTerm={effectiveSearchTerm}
      />
    </Box>
  );
};

const MediaDetailPage: React.FC = () => {
  const location = useLocation();
  const { searchTerm, asset } = location.state || {};
  return (
    <RecentlyViewedProvider>
      <RightSidebarProvider>
        <MediaDetailContent asset={asset} searchTerm={searchTerm} />
      </RightSidebarProvider>
    </RecentlyViewedProvider>
  );
};

export default MediaDetailPage;
