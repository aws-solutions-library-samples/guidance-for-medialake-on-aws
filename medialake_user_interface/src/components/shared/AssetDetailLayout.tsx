/**
 * AssetDetailLayout — shared layout for Video, Image, and Audio detail pages.
 *
 * Extracts the common patterns:
 * - Scroll-to-top on mount
 * - Scroll-hide/show header
 * - Breadcrumb navigation
 * - Tab structure with tabpanel
 * - Sidebar integration
 * - Recently viewed tracking
 */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Box, Paper, Tabs, Tab, alpha } from "@mui/material";
import { useRightSidebar } from "../common/RightSidebar";
import BreadcrumbNavigation from "../common/BreadcrumbNavigation";
import { springEasing } from "@/constants";
import { zIndexTokens } from "@/theme/tokens";

export interface AssetDetailTab {
  value: string;
  label: string;
  content: React.ReactNode;
}

interface AssetDetailLayoutProps {
  /** The asset ID from URL params */
  assetId: string;
  /** Display name of the asset */
  assetName: string;
  /** Asset type label for breadcrumb (e.g. "Video", "Image", "Audio") */
  assetType: string;
  /** Search term from navigation state */
  searchTerm?: string;
  /** Current result index in search results */
  currentResult?: number;
  /** Total results count */
  totalResults?: number;
  /** The main media viewer component */
  mediaViewer: React.ReactNode;
  /** Min height for the media viewer section */
  mediaViewerMinHeight?: string;
  /** Height for the media viewer section */
  mediaViewerHeight?: string;
  /** Tab definitions */
  tabs: AssetDetailTab[];
  /** Default active tab value */
  defaultTab?: string;
  /** Sidebar component */
  sidebar: React.ReactNode;
}

const AssetDetailLayout: React.FC<AssetDetailLayoutProps> = ({
  assetId,
  assetName,
  assetType,
  searchTerm = "",
  currentResult = 1,
  totalResults = 0,
  mediaViewer,
  mediaViewerMinHeight,
  mediaViewerHeight,
  tabs,
  defaultTab,
  sidebar,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isExpanded } = useRightSidebar();
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.value || "summary");
  const [showHeader, setShowHeader] = useState(true);

  // Scroll to top when component mounts or asset changes
  useEffect(() => {
    const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
    if (container) {
      container.scrollTo(0, 0);
    } else {
      window.scrollTo(0, 0);
    }
  }, [assetId]);

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

  // Effective search term from props or URL
  const searchParams = new URLSearchParams(location.search);
  const urlSearchTerm = searchParams.get("q") || searchParams.get("searchTerm") || "";
  const effectiveSearchTerm = searchTerm || urlSearchTerm;

  const handleBack = useCallback(() => {
    if (location.state && (location.state.searchTerm || location.state.preserveSearch)) {
      navigate(-1);
    } else {
      navigate(
        `/search${effectiveSearchTerm ? `?q=${encodeURIComponent(effectiveSearchTerm)}` : ""}`
      );
    }
  }, [navigate, location.state, effectiveSearchTerm]);

  // Keyboard navigation for tabs
  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const tabValues = tabs.map((t) => t.value);
      const currentIndex = tabValues.indexOf(activeTab);

      if (event.key === "ArrowRight") {
        setActiveTab(tabValues[(currentIndex + 1) % tabValues.length]);
      } else if (event.key === "ArrowLeft") {
        setActiveTab(tabValues[(currentIndex - 1 + tabValues.length) % tabValues.length]);
      }
    },
    [activeTab, tabs]
  );

  const activeTabContent = tabs.find((t) => t.value === activeTab)?.content;

  // Determine if media viewer uses full-height layout (video/audio) or content-height (image)
  const isFullHeightMedia = !!mediaViewerHeight;

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
      {/* Sticky header with breadcrumb */}
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
            currentResult={currentResult}
            totalResults={totalResults}
            onBack={handleBack}
            assetName={assetName}
            assetId={assetId}
            assetType={assetType}
          />
        </Box>
      </Box>

      {/* Media viewer section */}
      {isFullHeightMedia ? (
        <Box
          sx={{
            px: 3,
            pt: 0,
            pb: 0,
            mt: 0,
            height: mediaViewerHeight,
            minHeight: mediaViewerMinHeight || "600px",
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
            {mediaViewer}
          </Paper>
        </Box>
      ) : (
        <Box sx={{ px: 3, pt: 0, pb: 3, minHeight: "60vh" }}>
          <Box sx={{ overflow: "hidden", borderRadius: 2, position: "relative" }}>
            {mediaViewer}
          </Box>
        </Box>
      )}

      {/* Metadata tabs section */}
      <Box sx={{ px: 3, pb: 3 }}>
        <Paper
          elevation={0}
          sx={{ p: 0, borderRadius: 2, overflow: "visible", background: "transparent" }}
        >
          <Tabs
            value={activeTab}
            onChange={(_, newValue) => setActiveTab(newValue)}
            onKeyDown={handleTabKeyDown}
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
                transition: "background-color 0.2s, color 0.2s",
                "&:hover": {
                  backgroundColor: (theme) => alpha(theme.palette.secondary.main, 0.05),
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
              backgroundColor: (theme) => alpha(theme.palette.background.paper, 0.5),
              maxHeight: "none",
              overflow: "visible",
            }}
            role="tabpanel"
            id={`tabpanel-${activeTab}`}
            aria-labelledby={`tab-${activeTab}`}
            tabIndex={0}
          >
            {activeTabContent}
          </Box>
        </Paper>
      </Box>

      {/* Sidebar */}
      {sidebar}
    </Box>
  );
};

export default AssetDetailLayout;
