import React, {
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { useMediaController } from "../hooks/useMediaController";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  List,
  ListItem,
  Divider,
  Button,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  Chip,
  useTheme,
  alpha,
} from "@mui/material";
import {
  useAsset,
  useRelatedVersions,
  useTranscription,
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
import AssetHeader from "../components/asset/AssetHeader";
import { AssetAudio } from "../components/asset";
import { formatCamelCase } from "../utils/stringUtils";
import { TruncatedTextWithTooltip } from "../components/common/TruncatedTextWithTooltip";
import { formatLocalDateTime } from "@/shared/utils/dateUtils";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { Chip as MuiChip } from "@mui/material";
import { RelatedItemsView } from "../components/shared/RelatedItemsView";
import { AssetResponse } from "../api/types/asset.types";
import type {
  RelatedVersionsResponse,
  TranscriptionResponse,
} from "../api/hooks/useAssets";
import { formatFileSize } from "../utils/imageUtils";

// MUI Icons
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import LinkOutlinedIcon from "@mui/icons-material/LinkOutlined";
import SubtitlesOutlinedIcon from "@mui/icons-material/SubtitlesOutlined";
import MarkdownRenderer from "../components/common/MarkdownRenderer";
import TechnicalMetadataTab, {
  categoryMapping,
} from "../components/TechnicalMetadataTab";
import MetadataContent, { outputFilters } from "../components/MetadataContent";

interface MetadataContentProps {
  data: any;
  depth?: number;
  showAll: boolean;
  category?: string;
}

// Tab content components
const SummaryTab = ({
  metadataFields,
  assetData,
}: {
  metadataFields: any;
  assetData: any;
}) => {
  const theme = useTheme();
  const fileInfoColor = "#4299E1"; // Blue
  const techDetailsColor = "#68D391"; // Green/teal
  const descKeywordsColor = "#F6AD55"; // Orange

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
  const general = metadata.general || {};
  const audio = Array.isArray(metadata.audio) ? metadata.audio[0] : {};

  const fileSize =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.FileInfo?.Size || 0;
  const format =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format ||
    "Unknown";

  // Audio-specific metadata fields
  const duration =
    audio.duration != null
      ? audio.duration.toFixed(2)
      : general.Duration
        ? parseFloat(general.Duration).toFixed(2)
        : "Unknown";
  const sampleRate = audio.sample_rate
    ? (parseInt(audio.sample_rate, 10) / 1000).toFixed(1)
    : "Unknown";
  const bitDepth = audio.BitsPerSample || audio.bit_depth || "Unknown";

  const channels = audio.channels || audio.Channels || "Unknown";

  const bitRate = audio.bit_rate
    ? `${Math.round(audio.bit_rate / 1000)} kbps`
    : "Unknown";

  const codec = audio.codec_name || general.Format || "Unknown";

  const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
    ? new Date(
        assetData.data.asset.DigitalSourceAsset.CreateDate,
      ).toLocaleDateString()
    : "Unknown";

  return (
    <Box>
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
            {assetData?.data?.asset?.DigitalSourceAsset?.Type || "Audio"}
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
            Sample Rate:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {sampleRate} kHz
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
            Bit Depth:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {bitDepth} bit
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
            Channels:
          </Typography>
          <Typography sx={{ flex: 1, fontSize: "0.875rem" }}>
            {channels}
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

      {/* Description & Keywords Section */}
      {/* <Box sx={{ mb: 3 }}>
                <Typography
                    sx={{
                        color: descKeywordsColor,
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        mb: 0.5
                    }}
                >
                    Description & Keywords
                </Typography>
                <Box sx={{
                    width: '100%',
                    height: '1px',
                    bgcolor: descKeywordsColor,
                    mb: 2
                }} />

                <Typography sx={{ fontSize: '0.875rem', mb: 2 }}>
                    {metadataFields.descriptive.find((item: any) => item.label === 'Description')?.value || 'No description available'}
                </Typography>

                <Box sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 0.75
                }}>
                    {(metadataFields.descriptive.find((item: any) => item.label === 'Keywords')?.value || 'audio,sound')
                        .split(',')
                        .map((keyword: string, index: number) => (
                            <Chip
                                key={index}
                                label={keyword.trim()}
                                size="small"
                                sx={{
                                    bgcolor: '#1E2732',
                                    color: '#fff',
                                    borderRadius: '16px',
                                    fontSize: '0.75rem'
                                }}
                            />
                        ))}
                </Box>
            </Box> */}
    </Box>
  );
};

// Import the shared TranscriptionTab component
import TranscriptionTab from "../components/shared/TranscriptionTab";

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

const AudioDetailContent: React.FC = () => {
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

  // Media controller for transcript synchronization
  const mediaController = useMediaController();

  const [expandedMetadata, setExpandedMetadata] = useState<{
    [key: string]: boolean;
  }>({});
  const [comments, setComments] = useState([
    {
      user: "John Doe",
      avatar: "https://mui.com/static/videos/avatar/1.jpg",
      content: "Great audio quality!",
      timestamp: "2023-06-15 09:30:22",
    },
    {
      user: "Jane Smith",
      avatar: "https://mui.com/static/videos/avatar/2.jpg",
      content: "The mix is perfect",
      timestamp: "2023-06-15 10:15:43",
    },
    {
      user: "Mike Johnson",
      avatar: "https://mui.com/static/videos/avatar/3.jpg",
      content: "Can we adjust the levels?",
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

  const metadataFields = useMemo(() => {
    if (!assetData?.data?.asset)
      return {
        summary: [],
        descriptive: [],
        technical: [],
      };

    return {
      summary: [
        { label: "Title", value: "Media Futures Podcast: Three Big Questions" },
        { label: "Type", value: "Audio" },
        { label: "Duration", value: "42:18" },
      ],
      descriptive: [
        {
          label: "Description",
          value:
            "Industry experts discuss three fundamental questions facing the media and entertainment industry: the future of streaming platforms, content monetization strategies, and the impact of AI on creative workflows.",
        },
        {
          label: "Keywords",
          value:
            "podcast, media industry, streaming, monetization, AI, entertainment",
        },
        { label: "Location", value: "NAB 2025" },
      ],
      technical: [
        {
          label: "Format",
          value:
            assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format,
        },
        {
          label: "File Size",
          value:
            assetData.data.asset.DigitalSourceAsset.MainRepresentation
              .StorageInfo.PrimaryLocation.FileInfo.Size,
        },
        { label: "Date Created", value: "2024-05-15" },
      ],
    };
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

  const toggleMetadataExpansion = (key: string) => {
    setExpandedMetadata((prev) => ({ ...prev, [key]: !prev[key] }));
  };
  const activityLog = [
    {
      user: "John Doe",
      action: "Uploaded audio",
      timestamp: "2024-01-07 09:30:22",
    },
    {
      user: "AI Pipeline",
      action: "Generated metadata",
      timestamp: "2024-01-07 09:31:05",
    },
    {
      user: "Jane Smith",
      action: "Added tags",
      timestamp: "2024-01-07 10:15:43",
    },
  ];

  // Track this asset in recently viewed
  useTrackRecentlyViewed(
    assetData
      ? {
          id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
          title:
            assetData.data.asset.DigitalSourceAsset.MainRepresentation
              .StorageInfo.PrimaryLocation.ObjectKey.Name,
          type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "audio",
          path: `/audio/${assetData.data.asset.InventoryID}`,
          searchTerm: searchTerm,
          metadata: {
            duration: "42:18",
            fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
            creator: "John Doe",
          },
        }
      : null,
  );

  // Handle keyboard navigation for tabs
  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const tabs = ["summary", "technical", "transcription", "related"];
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
        `/search${searchTerm ? `?q=${encodeURIComponent(searchTerm)}` : ""}`,
      );
    }
  }, [navigate, location.state, searchTerm]);

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
          zIndex: 1200,
          background: (theme) => alpha(theme.palette.background.default, 0.8),
          backdropFilter: "blur(8px)",
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
            assetType="Audio"
          />
        </Box>
      </Box>

      {/* Audio player section */}
      <Box sx={{ px: 3, pt: 0, pb: 3, height: "50vh", minHeight: "400px" }}>
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
          <AssetAudio
            src={proxyUrl}
            alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
            onAudioElementReady={mediaController.registerAudioElement}
          />
        </Paper>
      </Box>

      {/* Metadata section */}
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
              {activeTab === "summary" && (
                <SummaryTab
                  metadataFields={metadataFields}
                  assetData={assetData}
                />
              )}
              {activeTab === "technical" && (
                <TechnicalMetadataTab
                  metadataAccordions={metadataAccordions}
                  availableCategories={Object.keys(
                    assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {},
                  )}
                  mediaType="audio"
                />
              )}
              {activeTab === "transcription" && (
                <TranscriptionTab
                  assetId={id || ""}
                  transcriptionData={transcriptionData}
                  isLoading={isLoadingTranscription}
                  assetData={assetData}
                  mediaType="audio"
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
        assetId={assetData?.data?.asset?.InventoryID}
      />
    </Box>
  );
};

const AudioDetailPage: React.FC = () => {
  return (
    <RecentlyViewedProvider>
      <RightSidebarProvider>
        <AudioDetailContent />
      </RightSidebarProvider>
    </RecentlyViewedProvider>
  );
};

export default AudioDetailPage;
