import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  Box,
  useTheme as useMuiTheme,
  InputBase,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { Button } from "@/components/common";
import {
  Search as SearchIcon,
  CloudUpload as CloudUploadIcon,
  FilterList as FilterListIcon,
  Chat as ChatIcon,
  Clear as ClearIcon,
} from "@mui/icons-material";
import { useChat } from "./contexts/ChatContext";
import { useNavigate, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import debounce from "lodash/debounce";
import { useTranslation } from "react-i18next";
import { useTheme } from "./hooks/useTheme";
import { useDirection } from "./contexts/DirectionContext";
import { S3UploaderModal } from "./features/upload";
import { useFeatureFlag } from "./contexts/FeatureFlagsContext";
import FilterModal from "./components/search/FilterModal";
import {
  useSearchFilters,
  useSearchQuery,
  useSemanticSearch,
  useDomainActions,
  useUIActions,
} from "./stores/searchStore";
import { NotificationCenter } from "./components/NotificationCenter";
import { QUERY_KEYS } from "./api/queryKeys";
import SemanticModeToggle from "./components/TopBar/SemanticModeToggle";
import SearchModeSelector from "./components/TopBar/SearchModeSelector";
import { useSemanticSearchStatus } from "./features/settings/system/hooks/useSystemSettings";

interface SearchTag {
  key: string;
  value: string;
}

function TopBar() {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  const [searchInput, setSearchInput] = useState("");
  const [searchTags, setSearchTags] = useState<SearchTag[]>([]);

  // Get search state from store
  const storeQuery = useSearchQuery();
  const storeIsSemantic = useSemanticSearch();
  const filters = useSearchFilters();
  const { setQuery, setIsSemantic } = useDomainActions();
  const { openFilterModal } = useUIActions();
  const [searchResults, setSearchResults] = useState<any>(null);
  const searchBoxRef = useRef<HTMLDivElement>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isSemanticConfigDialogOpen, setIsSemanticConfigDialogOpen] = useState(false);
  const isChatEnabled = useFeatureFlag("chat-enabled", true);
  const { toggleChat, isOpen: isChatOpen } = useChat();

  // Check semantic search configuration status
  const { isSemanticSearchEnabled, isConfigured, providerData } = useSemanticSearchStatus();
  const isMarengo30 = providerData?.data?.searchProvider?.type === "twelvelabs-bedrock-3-0";

  // Initialize semantic search from URL params on mount
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const semanticParam = params.get("semantic") === "true";

    // Update store if URL has semantic param and store doesn't match
    if (semanticParam !== storeIsSemantic) {
      setIsSemantic(semanticParam);
    }
  }, []); // Only run on mount

  // Sync search input with store query only when on search page
  useEffect(() => {
    // Only sync if we're on the search page and the store query differs from input
    if (location.pathname === "/search" && storeQuery && storeQuery !== searchInput) {
      setSearchInput(storeQuery);
    }
  }, [location.pathname, storeQuery]);

  const getSearchQuery = useCallback(() => {
    const tagPart = searchTags.map((tag) => `${tag.key}: ${tag.value}`).join(" ");
    return `${tagPart}${tagPart && searchInput ? " " : ""}${searchInput}`.trim();
  }, [searchTags, searchInput]);

  const debouncedSearch = useCallback(
    debounce((query: string) => {
      if (query.trim()) {
        // Update store state first
        setQuery(query);
        setIsSemantic(storeIsSemantic);

        // Build facet parameters for cache invalidation
        const facetParams = {
          type: filters.type,
          extension: filters.extension,
          asset_size_gte: filters.asset_size_gte,
          asset_size_lte: filters.asset_size_lte,
          ingested_date_gte: filters.ingested_date_gte,
          ingested_date_lte: filters.ingested_date_lte,
          filename: filters.filename,
        };

        // Remove undefined values from facetParams
        Object.keys(facetParams).forEach((key) => {
          if (facetParams[key as keyof typeof facetParams] === undefined) {
            delete facetParams[key as keyof typeof facetParams];
          }
        });

        // Invalidate search cache to force refetch
        queryClient.invalidateQueries({
          queryKey: QUERY_KEYS.SEARCH.list(query, 1, 50, storeIsSemantic, [], facetParams),
        });

        // Build URL with semantic parameter
        const params = new URLSearchParams();
        params.set("q", query);
        params.set("semantic", storeIsSemantic.toString());

        // Add filters to URL
        if (filters.type) params.set("type", filters.type);
        if (filters.extension) params.set("extension", filters.extension);
        if (filters.asset_size_gte) params.set("asset_size_gte", filters.asset_size_gte.toString());
        if (filters.asset_size_lte) params.set("asset_size_lte", filters.asset_size_lte.toString());
        if (filters.ingested_date_gte) params.set("ingested_date_gte", filters.ingested_date_gte);
        if (filters.ingested_date_lte) params.set("ingested_date_lte", filters.ingested_date_lte);
        if (filters.filename) params.set("filename", filters.filename);

        // Navigate with URL parameters
        navigate(`/search?${params.toString()}`);
      }
    }, 500),
    [navigate, storeIsSemantic, setQuery, setIsSemantic, filters, queryClient]
  );

  // Handle search results from session storage
  useEffect(() => {
    const handleStorageChange = () => {
      const storedResults = sessionStorage.getItem("searchResults");
      if (storedResults) {
        try {
          setSearchResults(JSON.parse(storedResults));
        } catch (e) {
          console.error("Error parsing search results from session storage", e);
        }
      }
    };
    handleStorageChange();
    window.addEventListener("storage", handleStorageChange);
    return () => {
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  const handleOpenUploadModal = () => {
    setIsUploadModalOpen(true);
  };

  const handleCloseUploadModal = () => {
    setIsUploadModalOpen(false);
  };

  const handleOpenFilterModal = () => {
    openFilterModal();
  };

  const createTagFromInput = (input: string): boolean => {
    if (input.includes(":")) {
      const [key, ...valueParts] = input.split(":");
      const value = valueParts.join(":").trim();
      if (key && value) {
        const newTag: SearchTag = {
          key: key.trim(),
          value: value,
        };
        setSearchTags((prev) => [...prev, newTag]);
        setSearchInput("");
        const searchQuery = getSearchQuery();

        // Build facet parameters for cache invalidation
        const facetParams = {
          type: filters.type,
          extension: filters.extension,
          asset_size_gte: filters.asset_size_gte,
          asset_size_lte: filters.asset_size_lte,
          ingested_date_gte: filters.ingested_date_gte,
          ingested_date_lte: filters.ingested_date_lte,
          filename: filters.filename,
        };

        // Remove undefined values from facetParams
        Object.keys(facetParams).forEach((key) => {
          if (facetParams[key as keyof typeof facetParams] === undefined) {
            delete facetParams[key as keyof typeof facetParams];
          }
        });

        // Invalidate search cache to force refetch
        queryClient.invalidateQueries({
          queryKey: QUERY_KEYS.SEARCH.list(searchQuery, 1, 50, storeIsSemantic, [], facetParams),
        });

        // Build URL with parameters
        const params = new URLSearchParams();
        params.set("q", searchQuery);
        params.set("semantic", storeIsSemantic.toString());

        navigate(`/search?${params.toString()}`);
        return true;
      }
    }
    return false;
  };

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSearchInput(value);

    if (value.endsWith(" ") && value.includes(":")) {
      const potentialTag = value.trim();
      if (createTagFromInput(potentialTag)) {
        return;
      }
    }

    if (!value.includes(":")) {
      const currentQuery = value.trim()
        ? `${searchTags.map((tag) => `${tag.key}: ${tag.value}`).join(" ")}${
            searchTags.length > 0 ? " " : ""
          }${value}`
        : searchTags.map((tag) => `${tag.key}: ${tag.value}`).join(" ");
      debouncedSearch(currentQuery);
    }
  };

  const handleSearchKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSearchSubmit();
    }
  };

  const handleSearchSubmit = () => {
    if (searchInput.includes(":")) {
      createTagFromInput(searchInput);
    } else if (searchInput.trim() || searchTags.length > 0) {
      const searchQuery = getSearchQuery();

      // Update store state first
      setQuery(searchQuery);
      setIsSemantic(storeIsSemantic);

      // Build facet parameters for cache invalidation
      const facetParams = {
        type: filters.type,
        extension: filters.extension,
        asset_size_gte: filters.asset_size_gte,
        asset_size_lte: filters.asset_size_lte,
        ingested_date_gte: filters.ingested_date_gte,
        ingested_date_lte: filters.ingested_date_lte,
        filename: filters.filename,
      };

      // Remove undefined values from facetParams
      Object.keys(facetParams).forEach((key) => {
        if (facetParams[key as keyof typeof facetParams] === undefined) {
          delete facetParams[key as keyof typeof facetParams];
        }
      });

      // Invalidate search cache to force refetch even with identical parameters
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SEARCH.list(searchQuery, 1, 50, storeIsSemantic, [], facetParams),
      });

      // Build URL with parameters
      const params = new URLSearchParams();
      params.set("q", searchQuery);
      params.set("semantic", storeIsSemantic.toString());

      // Add current filters to URL
      if (filters.type) params.set("type", filters.type);
      if (filters.extension) params.set("extension", filters.extension);
      if (filters.asset_size_gte) params.set("asset_size_gte", filters.asset_size_gte.toString());
      if (filters.asset_size_lte) params.set("asset_size_lte", filters.asset_size_lte.toString());
      if (filters.ingested_date_gte) params.set("ingested_date_gte", filters.ingested_date_gte);
      if (filters.ingested_date_lte) params.set("ingested_date_lte", filters.ingested_date_lte);
      if (filters.filename) params.set("filename", filters.filename);

      navigate(`/search?${params.toString()}`);

      // Clear the search input after navigation
      setSearchInput("");
    }
  };

  const handleDeleteTag = (tagToDelete: SearchTag) => {
    setSearchTags((prev) => {
      const newTags = prev.filter(
        (tag) => !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
      );
      const searchQuery = newTags.map((tag) => `${tag.key}: ${tag.value}`).join(" ");

      // Build facet parameters for cache invalidation
      const facetParams = {
        type: filters.type,
        extension: filters.extension,
        asset_size_gte: filters.asset_size_gte,
        asset_size_lte: filters.asset_size_lte,
        ingested_date_gte: filters.ingested_date_gte,
        ingested_date_lte: filters.ingested_date_lte,
        filename: filters.filename,
      };

      // Remove undefined values from facetParams
      Object.keys(facetParams).forEach((key) => {
        if (facetParams[key as keyof typeof facetParams] === undefined) {
          delete facetParams[key as keyof typeof facetParams];
        }
      });

      // Invalidate search cache to force refetch
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SEARCH.list(searchQuery, 1, 50, storeIsSemantic, [], facetParams),
      });

      // Build URL with parameters
      const params = new URLSearchParams();
      params.set("q", searchQuery);
      params.set("semantic", storeIsSemantic.toString());

      navigate(`/search?${params.toString()}`);
      return newTags;
    });
  };

  const handleClearSearch = () => {
    setSearchInput("");
    setSearchTags([]);
  };
  // Handle semantic search toggle
  const handleSemanticSearchToggle = (
    event: React.MouseEvent | React.ChangeEvent<HTMLInputElement>
  ) => {
    // Check if semantic search is properly configured
    if (!isSemanticSearchEnabled || !isConfigured) {
      // Show dialog to guide user to settings
      setIsSemanticConfigDialogOpen(true);
      return;
    }

    let newValue: boolean;

    if ("checked" in (event.target as HTMLInputElement)) {
      // Switch toggle
      newValue = (event.target as HTMLInputElement).checked;
    } else {
      // Icon/Button click
      newValue = !storeIsSemantic;
    }

    // Update store state
    setIsSemantic(newValue);

    // If we're on search page, update URL immediately
    if (location.pathname === "/search") {
      const params = new URLSearchParams(location.search);
      params.set("semantic", newValue.toString());
      navigate(`/search?${params.toString()}`, { replace: true });
    }
  };

  const handleCloseSemanticConfigDialog = () => {
    setIsSemanticConfigDialogOpen(false);
  };

  const handleNavigateToSettings = () => {
    setIsSemanticConfigDialogOpen(false);
    navigate("/settings/system");
  };

  const handleUploadComplete = (files: any[]) => {
    handleCloseUploadModal();
  };

  const hasActiveFilters = Object.keys(filters).filter((k) => k !== "date_range_option").length > 0;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        width: "100%",
        bgcolor: "transparent",
        justifyContent: "space-between",
        paddingRight: 0,
      }}
    >
      {/* Search area container */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "100%",
          position: "relative",
          mr: 2,
        }}
      >
        {/* Tags */}
        {searchTags.map((tag, index) => (
          <Chip
            key={index}
            label={`${tag.key}: ${tag.value}`}
            onDelete={() => handleDeleteTag(tag)}
            size="small"
            sx={{
              backgroundColor: muiTheme.palette.primary.light,
              color: muiTheme.palette.primary.contrastText,
              "& .MuiChip-deleteIcon": {
                color: muiTheme.palette.primary.contrastText,
              },
            }}
          />
        ))}

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "100%",
            maxWidth: "750px",
            mx: "auto",
            gap: 1,
          }}
        >
          {/* Unified search pill — mirrors Mantine Paper shadow="sm" radius="xl" withBorder */}
          <Box
            ref={searchBoxRef}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor:
                theme === "dark"
                  ? alpha(muiTheme.palette.background.paper, 0.85)
                  : muiTheme.palette.background.paper,
              borderRadius: "9999px",
              padding: "5px 6px",
              minHeight: 46,
              width: "100%",
              flexDirection: isRTL ? "row-reverse" : "row",
              border: `1px solid ${
                theme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.10)"
              }`,
              boxShadow:
                theme === "dark"
                  ? "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)"
                  : "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
              transition: "border-color 0.2s, box-shadow 0.2s",
              "&:focus-within": {
                borderColor: alpha(muiTheme.palette.primary.main, 0.5),
                boxShadow:
                  theme === "dark"
                    ? `0 0 0 2px ${alpha(muiTheme.palette.primary.main, 0.25)}`
                    : `0 0 0 2px ${alpha(muiTheme.palette.primary.main, 0.15)}`,
              },
            }}
          >
            {/* Full / Clip Segmented Control */}
            <SemanticModeToggle isVisible={storeIsSemantic} />

            {/* Search Input — unstyled, flex: 1 like Mantine TextInput variant="unstyled" */}
            <InputBase
              placeholder={
                storeIsSemantic
                  ? t("search.bar.placeholderSemantic", "Search (e.g., a peaceful place)")
                  : t("search.bar.placeholder", "Search (e.g., mountains)")
              }
              value={searchInput}
              onChange={handleSearchInputChange}
              onKeyUp={handleSearchKeyPress}
              fullWidth
              sx={{
                textAlign: isRTL ? "right" : "left",
                fontSize: "14px",
                color: theme === "dark" ? "#fff" : muiTheme.palette.text.primary,
                [isRTL ? "mr" : "ml"]: storeIsSemantic ? 0 : 1.5,
                "& input": {
                  padding: "8px 0",
                  "&::placeholder": {
                    color: theme === "dark" ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.38)",
                    opacity: 1,
                  },
                },
              }}
            />

            {/* Clear button */}
            {searchInput && (
              <IconButton
                size="small"
                onClick={handleClearSearch}
                sx={{
                  color: theme === "dark" ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.3)",
                  padding: "4px",
                  flexShrink: 0,
                  "&:hover": {
                    backgroundColor: "transparent",
                    color: theme === "dark" ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.55)",
                  },
                }}
                title={t("search.clear", "Clear search")}
              >
                <ClearIcon sx={{ fontSize: "18px" }} />
              </IconButton>
            )}

            {/* Right section: AI toggle + search button — matches Mantine rightSection */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                flexShrink: 0,
                [isRTL ? "ml" : "mr"]: "1px",
              }}
            >
              {/* Semantic label + Switch */}
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                  flexShrink: 0,
                }}
              >
                <Box
                  component="span"
                  sx={{
                    fontSize: "12px",
                    fontWeight: 500,
                    color: theme === "dark" ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.4)",
                    userSelect: "none",
                    lineHeight: 1,
                    whiteSpace: "nowrap",
                  }}
                >
                  {t("search.semantic.label", "Semantic")}
                </Box>
                <Box
                  role="switch"
                  aria-checked={storeIsSemantic}
                  aria-label={
                    storeIsSemantic
                      ? t("search.semantic.disable", "Disable semantic search")
                      : t("search.semantic.enable", "Enable semantic search")
                  }
                  tabIndex={0}
                  onClick={handleSemanticSearchToggle}
                  onKeyDown={(e: React.KeyboardEvent) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleSemanticSearchToggle(e as unknown as React.MouseEvent);
                    }
                  }}
                  sx={{
                    width: 34,
                    height: 19,
                    borderRadius: "10px",
                    backgroundColor: storeIsSemantic
                      ? muiTheme.palette.primary.main
                      : theme === "dark"
                        ? "rgba(255,255,255,0.18)"
                        : "rgba(0,0,0,0.14)",
                    position: "relative",
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                    flexShrink: 0,
                    "&:hover": {
                      backgroundColor: storeIsSemantic
                        ? muiTheme.palette.primary.dark
                        : theme === "dark"
                          ? "rgba(255,255,255,0.25)"
                          : "rgba(0,0,0,0.2)",
                    },
                    "&:focus-visible": {
                      outline: `2px solid ${muiTheme.palette.primary.main}`,
                      outlineOffset: "2px",
                    },
                    "&::after": {
                      content: '""',
                      position: "absolute",
                      top: "2px",
                      left: storeIsSemantic ? "17px" : "2px",
                      width: 15,
                      height: 15,
                      borderRadius: "50%",
                      backgroundColor: "#fff",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
                      transition: "left 0.2s ease",
                    },
                  }}
                />
              </Box>

              {/* Vertical divider */}
              <Box
                sx={{
                  width: "1px",
                  height: 16,
                  backgroundColor: theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.09)",
                  flexShrink: 0,
                }}
              />

              {/* Filter button — inside the pill, between Semantic and search */}
              <IconButton
                size="small"
                onClick={handleOpenFilterModal}
                sx={{
                  color: hasActiveFilters
                    ? muiTheme.palette.primary.main
                    : theme === "dark"
                      ? "rgba(255,255,255,0.45)"
                      : "rgba(0,0,0,0.35)",
                  padding: "5px",
                  flexShrink: 0,
                  position: "relative",
                  "&:hover": {
                    backgroundColor:
                      theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.04)",
                    color: hasActiveFilters
                      ? muiTheme.palette.primary.dark
                      : theme === "dark"
                        ? "rgba(255,255,255,0.7)"
                        : "rgba(0,0,0,0.55)",
                  },
                }}
                title={t("search.filters.title", "Filter Results")}
              >
                <FilterListIcon sx={{ fontSize: "20px" }} />
                {hasActiveFilters && (
                  <Box
                    sx={{
                      position: "absolute",
                      top: -3,
                      right: -3,
                      backgroundColor: muiTheme.palette.primary.main,
                      color: muiTheme.palette.primary.contrastText,
                      borderRadius: "50%",
                      width: 14,
                      height: 14,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "0.55rem",
                      fontWeight: 700,
                      lineHeight: 1,
                      border: `2px solid ${
                        theme === "dark"
                          ? muiTheme.palette.background.paper
                          : muiTheme.palette.background.paper
                      }`,
                      boxSizing: "content-box",
                    }}
                  >
                    {Object.keys(filters).filter((k) => k !== "date_range_option").length}
                  </Box>
                )}
              </IconButton>

              {/* Search mode selector (Visual/Audio/Transcript) — Marengo 3.0 only */}
              <SearchModeSelector isVisible={storeIsSemantic && isMarengo30} />

              {/* Search icon button */}
              <IconButton
                onClick={handleSearchSubmit}
                sx={{
                  backgroundColor: muiTheme.palette.primary.main,
                  color: "#fff",
                  width: 34,
                  height: 34,
                  flexShrink: 0,
                  transition: "background-color 0.15s, transform 0.1s",
                  "&:hover": {
                    backgroundColor: muiTheme.palette.primary.dark,
                  },
                  "&:active": {
                    transform: "scale(0.94)",
                  },
                }}
                title={t("common.search")}
              >
                <SearchIcon sx={{ fontSize: "18px" }} />
              </IconButton>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Right-aligned icons */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mr: 2,
        }}
      >
        {/* Upload Button */}
        <IconButton
          size="small"
          onClick={handleOpenUploadModal}
          sx={{
            color: theme === "dark" ? "rgba(255,255,255,0.7)" : "text.secondary",
            backgroundColor: theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.04)",
            borderRadius: "8px",
            padding: "8px",
            "&:hover": {
              backgroundColor: theme === "dark" ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.08)",
            },
          }}
        >
          <CloudUploadIcon />
        </IconButton>

        {/* Notification Center */}
        <NotificationCenter />

        {/* Chat Icon Button */}
        {isChatEnabled && (
          <IconButton
            size="small"
            onClick={toggleChat}
            sx={{
              color: isChatOpen
                ? muiTheme.palette.primary.main
                : theme === "dark"
                  ? "rgba(255,255,255,0.7)"
                  : "text.secondary",
              backgroundColor: isChatOpen
                ? alpha(muiTheme.palette.primary.main, 0.1)
                : theme === "dark"
                  ? "rgba(255,255,255,0.1)"
                  : "rgba(0,0,0,0.04)",
              borderRadius: "8px",
              padding: "8px",
              transition: (theme) =>
                theme.transitions.create(["color", "background-color"], {
                  duration: theme.transitions.duration.short,
                }),
              "&:hover": {
                backgroundColor: isChatOpen
                  ? alpha(muiTheme.palette.primary.main, 0.2)
                  : theme === "dark"
                    ? "rgba(255,255,255,0.2)"
                    : "rgba(0,0,0,0.08)",
              },
            }}
          >
            <ChatIcon />
          </IconButton>
        )}
      </Box>

      {/* Upload Modal */}
      <S3UploaderModal
        open={isUploadModalOpen}
        onClose={handleCloseUploadModal}
        onUploadComplete={handleUploadComplete}
        title={t("upload.title", "Upload Media Files")}
        description={t(
          "upload.description",
          "Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported."
        )}
      />

      {/* Filter Modal */}
      <FilterModal facetCounts={searchResults?.data?.searchMetadata?.facets} />

      {/* Semantic Search Configuration Dialog */}
      <Dialog
        open={isSemanticConfigDialogOpen}
        onClose={handleCloseSemanticConfigDialog}
        aria-labelledby="semantic-config-dialog-title"
        aria-describedby="semantic-config-dialog-description"
      >
        <DialogTitle id="semantic-config-dialog-title">
          {t("search.semantic.configDialog.title", "Semantic Search Not Configured")}
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="semantic-config-dialog-description">
            {t(
              "search.semantic.configDialog.description",
              "Semantic search is currently not configured or disabled. To enable this feature, go to System Settings > Search to configure a search provider, or press the button below."
            )}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseSemanticConfigDialog} color="inherit">
            {t("common.cancel", "Cancel")}
          </Button>
          <Button onClick={handleNavigateToSettings} variant="contained" color="primary" autoFocus>
            {t("search.semantic.configDialog.goToSettings", "Go to Search Settings")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default TopBar;
