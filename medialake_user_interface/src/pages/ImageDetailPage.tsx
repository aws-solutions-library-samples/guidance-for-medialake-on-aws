import React, { useState, useMemo, useCallback, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Box, CircularProgress, Typography, Paper, Button, Tabs, Tab, alpha } from "@mui/material";
import { useAsset, useRelatedVersions, RelatedVersionsResponse } from "../api/hooks/useAssets";
import { RightSidebarProvider, useRightSidebar } from "../components/common/RightSidebar";
import { RecentlyViewedProvider, useTrackRecentlyViewed } from "../contexts/RecentlyViewedContext";
import { formatFileSize } from "../utils/imageUtils";
import ImageViewer from "../components/common/ImageViewer";
import BreadcrumbNavigation from "../components/common/BreadcrumbNavigation";
import AssetSidebar from "../components/asset/AssetSidebar";
import CommentPopper from "../components/common/CommentPopper";
import { RelatedItemsView } from "../components/shared/RelatedItemsView";
import TechnicalMetadataTab from "../components/TechnicalMetadataTab";
import TabContentContainer from "../components/common/TabContentContainer";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";

const SummaryTab = ({ assetData }: { assetData: any }) => {
  const asset = assetData?.data?.asset;
  const fileInfoColor = "#4299E1";
  const techDetailsColor = "#68D391";

  // Extract metadata from API response
  const metadata = asset?.Metadata?.EmbeddedMetadata || {};
  const generalMetadata = metadata?.General || {};
  const imageMetadata = metadata?.Image?.[0] || {};

  // Create a helper function to render a field only if it exists in the API response
  const renderField = (label: string, value: any, formatter?: (val: any) => string) => {
    if (value === undefined || value === null) return null;

    return (
      <Box sx={{ display: "flex", mb: 1 }}>
        <Typography sx={{ width: "120px", color: "text.secondary", fontSize: "0.875rem" }}>
          {label}:
        </Typography>
        <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
          {formatter ? formatter(value) : value}
        </Typography>
      </Box>
    );
  };

  // File Information fields
  const fileSize =
    asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size;
  const fileType = asset?.DigitalSourceAsset?.Type;
  const fileFormat = asset?.DigitalSourceAsset?.MainRepresentation?.Format;
  const s3Bucket =
    asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.Bucket;
  const objectName =
    asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name;
  const objectFullPath =
    asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey
      ?.FullPath;
  const s3Uri = s3Bucket && objectFullPath ? `s3://${s3Bucket}/${objectFullPath}` : undefined;

  // Technical details
  const width = imageMetadata?.Width || generalMetadata?.ImageWidth;
  const height = imageMetadata?.Height || generalMetadata?.ImageHeight;
  const dimensions = width && height ? `${width}x${height}` : undefined;
  const colorDepth = imageMetadata?.BitDepth || imageMetadata?.Bitdepth;
  const colorSpace = imageMetadata?.ColorSpace || imageMetadata?.Colorspace;
  const compression = imageMetadata?.Compression || imageMetadata?.CompressionAlgorithm;
  const createdDate = asset?.DigitalSourceAsset?.CreateDate
    ? new Date(asset.DigitalSourceAsset.CreateDate).toLocaleDateString()
    : undefined;

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

        {renderField("Type", fileType)}
        {renderField("Size", fileSize, formatFileSize)}
        {renderField("Format", fileFormat)}
        {renderField("S3 Bucket", s3Bucket)}
        {renderField("Object Name", objectName)}
        {renderField("S3 URI", s3Uri)}
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

        {renderField("Dimensions", dimensions)}
        {renderField("Color Depth", colorDepth, (val) => `${val} bit`)}
        {renderField("Color Space", colorSpace)}
        {renderField("Compression", compression)}
        {renderField("Created Date", createdDate)}
      </Box>
    </TabContentContainer>
  );
};

const RelatedItemsTab: React.FC<{
  relatedVersionsData: RelatedVersionsResponse | undefined;
  isLoading: boolean;
  onLoadMore: () => void;
}> = ({ relatedVersionsData, isLoading, onLoadMore }) => {
  console.log("RelatedItemsTab - relatedVersionsData:", relatedVersionsData);

  const items = useMemo(() => {
    if (!relatedVersionsData?.data?.results) {
      console.log("No results found in relatedVersionsData");
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
    console.log("Mapped items:", mappedItems);
    return mappedItems;
  }, [relatedVersionsData]);

  const hasMore = useMemo(() => {
    if (!relatedVersionsData?.data?.searchMetadata) {
      console.log("No searchMetadata found for hasMore calculation");
      return false;
    }

    const { totalResults, page, pageSize } = relatedVersionsData.data.searchMetadata;
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

const ImageDetailContent: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [activeTab, setActiveTab] = useState("summary");
  const [relatedPage, setRelatedPage] = useState(1);
  const { data: assetData, isLoading: isLoadingAsset } = useAsset(id || "");
  const { data: relatedVersionsData, isLoading: isLoadingRelated } = useRelatedVersions(
    id || "",
    relatedPage
  );
  const { isExpanded } = useRightSidebar();
  const [commentAnchorEl, setCommentAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedComment, setSelectedComment] = useState<number | null>(null);
  const [showHeader, setShowHeader] = useState(true);
  const [comments, setComments] = useState([
    {
      user: "John Doe",
      avatar: "https://mui.com/static/images/avatar/1.jpg",
      content: "Great composition!",
      timestamp: "2023-06-15 09:30:22",
    },
    {
      user: "Jane Smith",
      avatar: "https://mui.com/static/images/avatar/2.jpg",
      content: "The lighting is perfect!",
      timestamp: "2023-06-15 10:15:45",
    },
    {
      user: "Mike Johnson",
      avatar: "https://mui.com/static/images/avatar/3.jpg",
      content: "Love the color palette!",
      timestamp: "2023-06-15 11:00:12",
    },
  ]);

  // Scroll to top when component mounts
  useEffect(() => {
    // Find the scrollable container in the AppLayout
    const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
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

    // Listen to scroll on the parent container
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

  const recentlyViewedItem = useMemo(() => {
    if (!id || !assetData?.data?.asset) return null;
    const asset = assetData.data.asset;
    return {
      id,
      title: asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
      type: asset.DigitalSourceAsset.Type.toLowerCase() as "video" | "image" | "audio",
      path: location.pathname,
      searchTerm: "",
      metadata: {
        fileSize: formatFileSize(
          asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size
        ),
      },
    };
  }, [id, assetData, location.pathname]);

  useTrackRecentlyViewed(recentlyViewedItem);

  // Get all the search state from location.state
  const {
    searchTerm = "",
    page = 1,
    viewMode = "card",
    cardSize = "medium",
    aspectRatio = "square",
    thumbnailScale = "fit",
    showMetadata = true,
    groupByType = false,
    filters = {},
    sorting = [],
    isSemantic = false,
    currentResult = 1,
    totalResults = 0,
  } = location.state || {};

  const transformMetadata = useCallback((metadata: any) => {
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
  }, []);

  const metadataAccordions = useMemo(() => {
    if (!assetData?.data?.asset?.Metadata) return [];
    return transformMetadata(assetData.data.asset.Metadata);
  }, [assetData, transformMetadata]);

  // All sub-categories that exist in this asset’s EmbeddedMetadata
  const availableCategoryKeys = useMemo(() => {
    const embedded = assetData?.data?.asset?.Metadata?.EmbeddedMetadata ?? {};
    return Object.keys(embedded);
  }, [assetData]);

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
        type: rep.Purpose,
        format: rep.Format,
        fileSize: formatFileSize(rep.StorageInfo.PrimaryLocation.FileInfo.Size),
        description: `${rep.Format} file - ${formatFileSize(
          rep.StorageInfo.PrimaryLocation.FileInfo.Size
        )}${
          rep.ImageSpec?.Resolution
            ? ` - ${rep.ImageSpec.Resolution.Width}x${rep.ImageSpec.Resolution.Height}`
            : ""
        }`,
      })),
    ];
  }, [assetData]);

  const proxyUrl = useMemo(() => {
    if (!assetData?.data?.asset) return "";
    const proxyRep = assetData.data.asset.DerivedRepresentations.find(
      (rep) => rep.Purpose === "proxy"
    );
    return (
      proxyRep?.URL ||
      assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.FullPath
    );
  }, [assetData]);

  const handleBack = useCallback(() => {
    // Construct query parameters
    const queryParams = new URLSearchParams();
    if (searchTerm) {
      queryParams.set("q", searchTerm);
    }
    if (page > 1) {
      queryParams.set("page", page.toString());
    }
    if (isSemantic) {
      queryParams.set("semantic", "true");
    }

    // Navigate back to search with all state preserved
    const previousPath = location.pathname;
    navigate({
      pathname: previousPath,
      search: queryParams.toString(),
      state: {
        preserveSearch: true,
        searchTerm,
        page,
        viewMode,
        cardSize,
        aspectRatio,
        thumbnailScale,
        showMetadata,
        groupByType,
        filters,
        sorting,
        isSemantic,
        currentResult,
        totalResults,
      },
    } as any); // Type assertion needed due to React Router types
  }, [
    navigate,
    searchTerm,
    page,
    viewMode,
    cardSize,
    aspectRatio,
    thumbnailScale,
    showMetadata,
    groupByType,
    filters,
    sorting,
    isSemantic,
    currentResult,
    totalResults,
    location.pathname,
  ]);

  const handleAddComment = useCallback((content: string) => {
    const newCommentObj = {
      user: "Current User",
      avatar: "https://mui.com/static/images/avatar/4.jpg",
      content: content,
      timestamp: new Date().toISOString(),
    };
    setComments((prev) => [...prev, newCommentObj]);
  }, []);

  console.log("ImageDetailContent - activeTab:", activeTab);
  console.log("ImageDetailContent - relatedVersionsData:", relatedVersionsData);
  console.log("ImageDetailContent - isLoadingRelated:", isLoadingRelated);

  const renderTabContent = () => {
    console.log("renderTabContent - activeTab:", activeTab);
    switch (activeTab) {
      case "summary":
        return <SummaryTab assetData={assetData} />;
      case "technical":
        return (
          <TechnicalMetadataTab
            metadataAccordions={metadataAccordions}
            availableCategories={availableCategoryKeys}
            mediaType="image"
          />
        );
      case "related":
        console.log("Rendering RelatedItemsTab");
        return (
          <RelatedItemsTab
            relatedVersionsData={relatedVersionsData}
            isLoading={isLoadingRelated}
            onLoadMore={() => setRelatedPage((prev) => prev + 1)}
          />
        );
      default:
        return null;
    }
  };

  if (isLoadingAsset) {
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

  if (!assetData) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h5" color="error">
          Error loading asset data
        </Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
          Go Back
        </Button>
      </Box>
    );
  }

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
        <Box sx={{ px: 0, py: 0, mb: 0 }}>
          <BreadcrumbNavigation
            searchTerm={searchTerm}
            currentResult={currentResult}
            totalResults={totalResults}
            onBack={handleBack}
            assetName={
              assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
                .ObjectKey.Name
            }
            assetId={assetData.data.asset.InventoryID}
            assetType="Image"
          />
        </Box>
      </Box>

      {/* Image viewer section */}
      <Box sx={{ px: 3, pt: 0, pb: 3, minHeight: "60vh" }}>
        <Box
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            position: "relative",
          }}
        >
          <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
        </Box>
      </Box>

      {/* Metadata section */}
      <Box sx={{ px: 3, pb: 3 }}>
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
            textColor="secondary"
            indicatorColor="secondary"
            aria-label="metadata tabs"
            variant="scrollable"
            scrollButtons="auto"
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
            {renderTabContent()}
          </Box>
        </Paper>
      </Box>

      <AssetSidebar
        versions={versions}
        comments={comments}
        onAddComment={handleAddComment}
        assetId={assetData?.data?.asset?.InventoryID}
        asset={assetData?.data?.asset}
      />

      {selectedComment !== null && (
        <CommentPopper
          id={commentAnchorEl ? "comment-popper" : undefined}
          open={Boolean(commentAnchorEl)}
          anchorEl={commentAnchorEl}
          comment={comments[selectedComment]}
          onClose={() => {
            setCommentAnchorEl(null);
            setSelectedComment(null);
          }}
        />
      )}
    </Box>
  );
};

const ImageDetailPage: React.FC = () => {
  return (
    <RecentlyViewedProvider>
      <RightSidebarProvider>
        <ImageDetailContent />
      </RightSidebarProvider>
    </RecentlyViewedProvider>
  );
};

export default ImageDetailPage;
