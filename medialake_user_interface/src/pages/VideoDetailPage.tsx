import React, {
  useState,
  useMemo,
  useCallback,
  useRef,
  useEffect,
} from "react";
import { useMediaController } from "../hooks/useMediaController";
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
  RelatedVersionsResponse,
} from "../api/hooks/useAssets";
import {
  RightSidebarProvider,
  useRightSidebar,
} from "../components/common/RightSidebar";
import {
  RecentlyViewedProvider,
  useTrackRecentlyViewed,
} from "../contexts/RecentlyViewedContext";
import AssetSidebar from "../components/asset/AssetSidebar";
import BreadcrumbNavigation from "../components/common/BreadcrumbNavigation";
import AssetVideo from "../components/asset/AssetVideo";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import { RelatedItemsView } from "../components/shared/RelatedItemsView";
import { AssetResponse } from "../api/types/asset.types";
import { formatFileSize } from "../utils/imageUtils";
import TechnicalMetadataTab from "../components/TechnicalMetadataTab";
import TranscriptionTab from "../components/shared/TranscriptionTab";
import DescriptiveTab from "../components/shared/DescriptiveTab";
import TabContentContainer from "../components/common/TabContentContainer";
import { VideoViewerRef } from "../components/common/VideoViewer";

const SummaryTab = ({ assetData }: { assetData: any }) => {
  const fileInfoColor = "#4299E1";
  const techDetailsColor = "#68D391";

  const s3Bucket =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.Bucket;
  const objectName =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.ObjectKey?.Name;
  const fullPath =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.ObjectKey?.FullPath;
  const s3Uri =
    s3Bucket && fullPath ? `s3://${s3Bucket}/${fullPath}` : "Unknown";

  // Extract metadata from API response
  const metadata = assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {};
  const generalMetadata = metadata.general || {};
  const videoMetadata = Array.isArray(metadata.video) ? metadata.video[0] : {};

  const fileSize =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.FileInfo?.Size || 0;
  const format =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format ||
    "Unknown";
  const duration = generalMetadata.Duration
    ? `${parseFloat(generalMetadata.Duration).toFixed(2)} s`
    : "Unknown";
  const width = videoMetadata.Width ?? "Unknown";
  const height = videoMetadata.Height ?? "Unknown";
  const frameRate = videoMetadata.FrameRate
    ? `${videoMetadata.FrameRate} FPS`
    : "Unknown";
  const bitRate =
    videoMetadata.OverallBitRate || videoMetadata.BitRate
      ? `${Math.round((videoMetadata.OverallBitRate || videoMetadata.BitRate) / 1000)} kbps`
      : "Unknown";
  const codec =
    videoMetadata.codec_name || metadata.general.Format || "Unknown";

  const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
    ? new Date(
        assetData.data.asset.DigitalSourceAsset.CreateDate,
      ).toLocaleDateString()
    : "Unknown";

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
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Type:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {assetData?.data?.asset?.DigitalSourceAsset?.Type || "Video"}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Size:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {formatFileSize(fileSize)}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Format:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {format}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            S3 Bucket:
          </Typography>
          <Typography
            sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}
          >
            {s3Bucket || "Unknown"}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Object Name:
          </Typography>
          <Typography
            sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}
          >
            {objectName || "Unknown"}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            S3 URI:
          </Typography>
          <Typography
            sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}
          >
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
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Duration:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {duration} seconds
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Resolution:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {width}x{height}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Frame Rate:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {frameRate} FPS
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Bit Rate:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {bitRate}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Codec:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {codec}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", mb: 1 }}>
          <Typography
            sx={{
              width: "120px",
              color: "text.secondary",
              fontSize: "0.875rem",
            }}
          >
            Created Date:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {createdDate}
          </Typography>
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
}> = ({ assetId, relatedVersionsData, isLoading, onLoadMore }) => {
  console.log("RelatedItemsTab - relatedVersionsData:", relatedVersionsData);

  const items = useMemo(() => {
    if (!relatedVersionsData?.data?.results) {
      console.log("No results found in relatedVersionsData");
      return [];
    }

    const mappedItems = relatedVersionsData.data.results.map((result) => ({
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
    console.log("Mapped items:", mappedItems);
    return mappedItems;
  }, [relatedVersionsData]);

  const hasMore = useMemo(() => {
    if (!relatedVersionsData?.data?.searchMetadata) {
      console.log("No searchMetadata found for hasMore calculation");
      return false;
    }

    const { totalResults, page, pageSize } =
      relatedVersionsData.data.searchMetadata;
    const hasMoreItems = totalResults > page * pageSize;
    console.log("Has more items:", hasMoreItems);
    return hasMoreItems;
  }, [relatedVersionsData]);

  console.log("Rendering RelatedItemsView with items:", items);
  return (
    <RelatedItemsView
      items={items}
      isLoading={isLoading}
      onLoadMore={onLoadMore}
      hasMore={hasMore}
    />
  );
};

const VideoDetailContent: React.FC<VideoDetailContentProps> = ({
  asset,
  assetType,
  searchTerm,
}) => {
  const videoViewerRef = useRef<VideoViewerRef>(null);
  const seekAttemptsRef = useRef<number>(0);
  const seekTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { isExpanded, closeSidebar } = useRightSidebar();
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
  const { data: relatedVersionsData, isLoading: isLoadingRelated } =
    useRelatedVersions(id || "", relatedPage);
  const { data: transcriptionData, isLoading: isLoadingTranscription } =
    useTranscription(id || "");
  const [showHeader, setShowHeader] = useState(true);

  // Video media controller for transcript synchronization
  const mediaController = useMediaController();

  // Register video element with media controller
  useEffect(() => {
    if (videoViewerRef.current) {
      mediaController.registerVideoElement(videoViewerRef);
    }
  }, [mediaController]);

  // Seek to clip start time if this is a clip result from CLIP mode
  useEffect(() => {
    // Check if this is a clip result (has clips array with exactly one clip)
    const clips = asset?.clips;
    if (!clips || !Array.isArray(clips) || clips.length !== 1) {
      return;
    }

    const clip = clips[0];
    let startTime: number | undefined;

    // Extract start time from either start (number) or start_timecode (string)
    if (typeof clip.start === "number") {
      startTime = clip.start;
    } else if (clip.start_timecode) {
      // Convert timecode (HH:MM:SS:FF) to seconds
      const timecodeToSeconds = (tc: string): number => {
        const [hh, mm, ss, ff] = tc.split(":").map(Number);
        const fps = 25; // default/fallback; adjust if actual fps available
        return hh * 3600 + mm * 60 + ss + (isNaN(ff) ? 0 : ff / fps);
      };
      startTime = timecodeToSeconds(clip.start_timecode);
    }

    // Seek to the clip start time when video is ready
    if (startTime === undefined || startTime < 0) {
      return;
    }

    // Poll to check if video is ready, then seek
    const maxAttempts = 20; // Try for up to 2 seconds (20 * 100ms)
    const pollInterval = 100; // Check every 100ms
    seekAttemptsRef.current = 0;

    // Clear any existing timeout
    if (seekTimeoutRef.current) {
      clearTimeout(seekTimeoutRef.current);
      seekTimeoutRef.current = null;
    }

    const seekToClipStart = () => {
      seekAttemptsRef.current++;

      if (!videoViewerRef.current) {
        if (seekAttemptsRef.current < maxAttempts) {
          seekTimeoutRef.current = setTimeout(seekToClipStart, pollInterval);
        }
        return;
      }

      try {
        // Try to get current time to verify video is ready
        const currentTime = videoViewerRef.current.getCurrentTime();
        // If we can get current time, video is ready
        videoViewerRef.current.seek(startTime!);
        console.log(`Seeked to clip start time: ${startTime}s for asset ${id}`);
        // Success - clear any pending timeouts
        if (seekTimeoutRef.current) {
          clearTimeout(seekTimeoutRef.current);
          seekTimeoutRef.current = null;
        }
      } catch (error) {
        // Video might not be ready yet, retry
        if (seekAttemptsRef.current < maxAttempts) {
          seekTimeoutRef.current = setTimeout(seekToClipStart, pollInterval);
        } else {
          console.warn(
            `Failed to seek to clip start time ${startTime}s after ${maxAttempts} attempts:`,
            error,
          );
        }
      }
    };

    // Start polling after a small initial delay
    seekTimeoutRef.current = setTimeout(seekToClipStart, 200);

    return () => {
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
        seekTimeoutRef.current = null;
      }
      seekAttemptsRef.current = 0;
    };
  }, [asset, videoViewerRef, id]);

  const [comments, setComments] = useState([
    {
      user: "John Doe",
      avatar: "https://mui.com/static/videos/avatar/1.jpg",
      content: "Great composition!",
      timestamp: "2023-06-15 09:30:22",
    },
    {
      user: "Jane Smith",
      avatar: "https://mui.com/static/videos/avatar/2.jpg",
      content: "The lighting is perfect",
      timestamp: "2023-06-15 10:15:43",
    },
    {
      user: "Mike Johnson",
      avatar: "https://mui.com/static/videos/avatar/3.jpg",
      content: "Can we adjust the contrast?",
      timestamp: "2023-06-15 11:22:17",
    },
  ]);

  // Scroll to top when component mounts
  useEffect(() => {
    // Find the scrollable container in the AppLayout
    const container = document.querySelector(
      '[class*="AppLayout"] [style*="overflow: auto"]',
    );
    if (container) {
      container.scrollTo(0, 0);
    } else {
      // Fallback to window scrolling
      window.scrollTo(0, 0);
    }
  }, [id]); // Include id in dependencies to ensure scroll reset when navigating between detail pages

  // Use the searchTerm prop or fallback to URL parameters
  const searchParams = new URLSearchParams(location.search);
  const urlSearchTerm =
    searchParams.get("q") || searchParams.get("searchTerm") || "";
  // Use the prop value if available, otherwise use the URL value
  const effectiveSearchTerm = searchTerm || urlSearchTerm;

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

  // All sub-categories that exist in this asset's EmbeddedMetadata
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
            assetData.data.asset.DigitalSourceAsset.MainRepresentation
              .StorageInfo.PrimaryLocation.ObjectKey.Name,
          type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "video",
          path: `/${assetData.data.asset.DigitalSourceAsset.Type.toLowerCase()}s/${
            assetData.data.asset.InventoryID
          }`,
          searchTerm: effectiveSearchTerm,
          metadata: {
            duration: "00:15",
            fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
            dimensions: "1920x1080",
            creator: "John Doe",
          },
        }
      : null,
  );

  // Handle keyboard navigation for tabs
  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const tabs = [
        "summary",
        "technical",
        "descriptive",
        "transcription",
        "related",
      ];
      const currentIndex = tabs.indexOf(activeTab);

      if (event.key === "ArrowRight") {
        const nextIndex = (currentIndex + 1) % tabs.length;
        setActiveTab(tabs[nextIndex]);
      } else if (event.key === "ArrowLeft") {
        const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        setActiveTab(tabs[prevIndex]);
      }
    },
    [activeTab],
  );

  const handleBack = useCallback(() => {
    // If we came from a specific location with state, go back to that location
    if (
      location.state &&
      (location.state.searchTerm || location.state.preserveSearch)
    ) {
      navigate(-1);
    } else {
      // Fallback to search page with search term if available
      navigate(
        `/search${effectiveSearchTerm ? `?q=${encodeURIComponent(effectiveSearchTerm)}` : ""}`,
      );
    }
  }, [navigate, location.state, effectiveSearchTerm]);

  // Track scroll position to hide/show header
  useEffect(() => {
    let lastScrollTop = 0;

    const handleScroll = () => {
      // Get scrollTop from the parent scrollable container instead
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

    // Listen to scroll on the parent container
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
        width: "100%",
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
            searchTerm={effectiveSearchTerm}
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
            assetType="Video"
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
              theme.transitions.create(["width", "max-width"], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
          }}
        >
          <AssetVideo
            ref={videoViewerRef}
            src={proxyUrl}
            alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
            onTimeUpdate={(time) => {
              mediaController.updateCurrentTime(time);
            }}
            onVideoElementReady={(ref) => {
              mediaController.registerVideoElement(ref);
            }}
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
                  transition: "all 0.2s",
                  "&:hover": {
                    backgroundColor: (theme) =>
                      alpha(theme.palette.secondary.main, 0.05),
                  },
                },
              }}
            >
              <Tab
                value="summary"
                label="Summary"
                id="tab-summary"
                aria-controls="tabpanel-summary"
              />
              <Tab
                value="technical"
                label="Technical Metadata"
                id="tab-technical"
                aria-controls="tabpanel-technical"
              />
              <Tab
                value="descriptive"
                label="Descriptive"
                id="tab-descriptive"
                aria-controls="tabpanel-descriptive"
              />
              <Tab
                value="transcription"
                label="Transcription"
                id="tab-transcription"
                aria-controls="tabpanel-transcription"
              />
              <Tab
                value="related"
                label="Related Items"
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
                outline: "none", // Remove outline when focused but keep it accessible
                borderRadius: 1,
                backgroundColor: (theme) =>
                  alpha(theme.palette.background.paper, 0.5),
                maxHeight: "none",
                overflow: "visible",
              }}
              role="tabpanel"
              id={`tabpanel-${activeTab}`}
              aria-labelledby={`tab-${activeTab}`}
              tabIndex={0} // Make the panel focusable
            >
              {activeTab === "summary" && <SummaryTab assetData={assetData} />}
              {activeTab === "technical" && (
                <TechnicalMetadataTab
                  metadataAccordions={metadataAccordions}
                  availableCategories={availableCategoryKeys}
                  mediaType="video"
                />
              )}
              {activeTab === "descriptive" && (
                <DescriptiveTab assetData={assetData} />
              )}
              {activeTab === "transcription" && (
                <TranscriptionTab
                  assetId={id || ""}
                  transcriptionData={transcriptionData}
                  isLoading={isLoadingTranscription}
                  assetData={assetData}
                  mediaType="video"
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
        videoViewerRef={videoViewerRef}
        assetId={assetData?.data?.asset?.InventoryID}
        asset={asset}
        assetType={assetType}
        searchTerm={effectiveSearchTerm}
      />
    </Box>
  );
};

interface VideoDetailContentProps {
  asset: any;
  assetType: string;
  searchTerm?: string;
}

const VideoDetailPage: React.FC = () => {
  const location = useLocation();
  const { assetType, searchTerm, asset } = location.state;
  return (
    <RecentlyViewedProvider>
      <RightSidebarProvider>
        <VideoDetailContent
          asset={asset}
          assetType={assetType}
          searchTerm={searchTerm}
        />
      </RightSidebarProvider>
    </RecentlyViewedProvider>
  );
};

export default VideoDetailPage;
