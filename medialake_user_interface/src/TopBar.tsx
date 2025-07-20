import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  Box,
  useTheme as useMuiTheme,
  InputBase,
  Stack,
  Chip,
  IconButton,
  FormControlLabel,
  Switch,
  Typography,
  Paper,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { Button } from "@/components/common";
import {
  Search as SearchIcon,
  CloudUpload as CloudUploadIcon,
  FilterList as FilterListIcon,
  Chat as ChatIcon,
  Notifications as NotificationsIcon,
  Psychology as PsychologyIcon,
} from "@mui/icons-material";
import { useChat } from "./contexts/ChatContext";
import { useNavigate, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import debounce from "lodash/debounce";
import { useTranslation } from "react-i18next";
import { useTheme } from "./hooks/useTheme";
import { useSidebar } from "./contexts/SidebarContext";
import { useDirection } from "./contexts/DirectionContext";
import { drawerWidth, collapsedDrawerWidth } from "./constants";
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

interface SearchTag {
  key: string;
  value: string;
}

function TopBar() {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const { isCollapsed } = useSidebar();
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
  const { setQuery, setIsSemantic, setFilters } = useDomainActions();
  const { openFilterModal } = useUIActions();
  const [searchResults, setSearchResults] = useState<any>(null);
  const [searchBoxWidth, setSearchBoxWidth] = useState<number>(0);
  const searchBoxRef = useRef<HTMLDivElement>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const isFileUploadEnabled = useFeatureFlag("file-upload-enabled", true);
  const isChatEnabled = useFeatureFlag("chat-enabled", true);
  const isNotificationEnabled = useFeatureFlag("notification-enabled", true);
  const { toggleChat, isOpen: isChatOpen } = useChat();

  // Initialize semantic search from URL params on mount
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const semanticParam = params.get("semantic") === "true";

    // Update store if URL has semantic param and store doesn't match
    if (semanticParam !== storeIsSemantic) {
      setIsSemantic(semanticParam);
    }
  }, []); // Only run on mount

  // Sync search input with store query when store changes
  useEffect(() => {
    if (storeQuery && storeQuery !== searchInput) {
      setSearchInput(storeQuery);
    }
  }, [storeQuery]);

  const getSearchQuery = useCallback(() => {
    const tagPart = searchTags
      .map((tag) => `${tag.key}: ${tag.value}`)
      .join(" ");
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
          queryKey: QUERY_KEYS.SEARCH.list(
            query,
            1,
            50,
            storeIsSemantic,
            [],
            facetParams,
          ),
        });

        // Build URL with semantic parameter
        const params = new URLSearchParams();
        params.set("q", query);
        params.set("semantic", storeIsSemantic.toString());

        // Add filters to URL
        if (filters.type) params.set("type", filters.type);
        if (filters.extension) params.set("extension", filters.extension);
        if (filters.asset_size_gte)
          params.set("asset_size_gte", filters.asset_size_gte.toString());
        if (filters.asset_size_lte)
          params.set("asset_size_lte", filters.asset_size_lte.toString());
        if (filters.ingested_date_gte)
          params.set("ingested_date_gte", filters.ingested_date_gte);
        if (filters.ingested_date_lte)
          params.set("ingested_date_lte", filters.ingested_date_lte);
        if (filters.filename) params.set("filename", filters.filename);

        // Navigate with URL parameters
        navigate(`/search?${params.toString()}`);
      }
    }, 500),
    [navigate, storeIsSemantic, setQuery, setIsSemantic, filters, queryClient],
  );

  const handleApplyFilters = (newFilters: any) => {
    setFilters(newFilters);
    // Trigger search with the new filters
    const searchQuery = getSearchQuery();

    // Build facet parameters for cache invalidation
    const facetParams = {
      type: newFilters.type,
      extension: newFilters.extension,
      asset_size_gte: newFilters.asset_size_gte,
      asset_size_lte: newFilters.asset_size_lte,
      ingested_date_gte: newFilters.ingested_date_gte,
      ingested_date_lte: newFilters.ingested_date_lte,
      filename: newFilters.filename,
    };

    // Remove undefined values from facetParams
    Object.keys(facetParams).forEach((key) => {
      if (facetParams[key as keyof typeof facetParams] === undefined) {
        delete facetParams[key as keyof typeof facetParams];
      }
    });

    // Invalidate search cache to force refetch with new filters
    queryClient.invalidateQueries({
      queryKey: QUERY_KEYS.SEARCH.list(
        searchQuery,
        1,
        50,
        storeIsSemantic,
        [],
        facetParams,
      ),
    });

    // Build URLSearchParams
    const queryParams = new URLSearchParams();
    queryParams.set("q", searchQuery);
    queryParams.set("semantic", storeIsSemantic.toString());
    if (newFilters.type) queryParams.set("type", newFilters.type);
    if (newFilters.extension)
      queryParams.set("extension", newFilters.extension);
    if (newFilters.asset_size_lte)
      queryParams.set("asset_size_lte", newFilters.asset_size_lte.toString());
    if (newFilters.asset_size_gte)
      queryParams.set("asset_size_gte", newFilters.asset_size_gte.toString());
    if (newFilters.ingested_date_lte)
      queryParams.set("ingested_date_lte", newFilters.ingested_date_lte);
    if (newFilters.ingested_date_gte)
      queryParams.set("ingested_date_gte", newFilters.ingested_date_gte);
    if (newFilters.filename) queryParams.set("filename", newFilters.filename);

    navigate(`/search?${queryParams.toString()}`);
  };

  // Measure search box width
  useEffect(() => {
    const updateWidth = () => {
      if (searchBoxRef.current) {
        const width = searchBoxRef.current.offsetWidth;
        setSearchBoxWidth(width);
        // console.log('Search box width measured:', width);
      }
    };

    // Initial measurement after a short delay
    setTimeout(updateWidth, 100);
    window.addEventListener("resize", updateWidth);
    const observer = new ResizeObserver(() => {
      updateWidth();
    });
    if (searchBoxRef.current) {
      observer.observe(searchBoxRef.current);
    }
    return () => {
      window.removeEventListener("resize", updateWidth);
      observer.disconnect();
    };
  }, []);

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
          queryKey: QUERY_KEYS.SEARCH.list(
            searchQuery,
            1,
            50,
            storeIsSemantic,
            [],
            facetParams,
          ),
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

  const handleSearchInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
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
        queryKey: QUERY_KEYS.SEARCH.list(
          searchQuery,
          1,
          50,
          storeIsSemantic,
          [],
          facetParams,
        ),
      });

      // Build URL with parameters
      const params = new URLSearchParams();
      params.set("q", searchQuery);
      params.set("semantic", storeIsSemantic.toString());

      // Add current filters to URL
      if (filters.type) params.set("type", filters.type);
      if (filters.extension) params.set("extension", filters.extension);
      if (filters.asset_size_gte)
        params.set("asset_size_gte", filters.asset_size_gte.toString());
      if (filters.asset_size_lte)
        params.set("asset_size_lte", filters.asset_size_lte.toString());
      if (filters.ingested_date_gte)
        params.set("ingested_date_gte", filters.ingested_date_gte);
      if (filters.ingested_date_lte)
        params.set("ingested_date_lte", filters.ingested_date_lte);
      if (filters.filename) params.set("filename", filters.filename);

      navigate(`/search?${params.toString()}`);
    }
  };

  const handleDeleteTag = (tagToDelete: SearchTag) => {
    setSearchTags((prev) => {
      const newTags = prev.filter(
        (tag) =>
          !(tag.key === tagToDelete.key && tag.value === tagToDelete.value),
      );
      const searchQuery = newTags
        .map((tag) => `${tag.key}: ${tag.value}`)
        .join(" ");

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
        queryKey: QUERY_KEYS.SEARCH.list(
          searchQuery,
          1,
          50,
          storeIsSemantic,
          [],
          facetParams,
        ),
      });

      // Build URL with parameters
      const params = new URLSearchParams();
      params.set("q", searchQuery);
      params.set("semantic", storeIsSemantic.toString());

      navigate(`/search?${params.toString()}`);
      return newTags;
    });
  };

  // Handle semantic search toggle
  const handleSemanticSearchToggle = (
    event: React.MouseEvent | React.ChangeEvent<HTMLInputElement>,
  ) => {
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

  const handleUploadComplete = (files: any[]) => {
    console.log("Upload completed:", files);
    handleCloseUploadModal();
    // Add any feedback if needed
  };

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
            maxWidth: "700px",
            mx: "auto",
          }}
        >
          <Box
            ref={searchBoxRef}
            sx={{
              display: "flex",
              alignItems: "center",
              backgroundColor:
                theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.04)",
              borderRadius: "24px",
              padding: "8px 16px",
              width: "100%",
              flexDirection: isRTL ? "row-reverse" : "row",
              boxShadow:
                theme === "dark" ? "0 2px 5px rgba(0,0,0,0.2)" : "none",
            }}
          >
            <SearchIcon
              sx={{
                color:
                  theme === "dark" ? "rgba(255,255,255,0.7)" : "text.secondary",
                [isRTL ? "ml" : "mr"]: 1.5,
                fontSize: "20px",
              }}
            />
            <InputBase
              placeholder={t("common.search")}
              value={searchInput}
              onChange={handleSearchInputChange}
              onKeyUp={handleSearchKeyPress}
              fullWidth
              sx={{
                textAlign: isRTL ? "right" : "left",
                fontSize: "16px",
                color:
                  theme === "dark" ? "white" : muiTheme.palette.text.primary,
                "& input": {
                  padding: "6px 0",
                  "&::placeholder": {
                    color:
                      theme === "dark" ? "rgba(255,255,255,0.7)" : "inherit",
                    opacity: 1,
                  },
                },
              }}
            />

            {/* Filter Button */}
            <IconButton
              size="small"
              onClick={handleOpenFilterModal}
              sx={{
                color:
                  Object.keys(filters).length > 0
                    ? muiTheme.palette.primary.main
                    : theme === "dark"
                      ? "rgba(255,255,255,0.5)"
                      : "rgba(0,0,0,0.4)",
                position: "relative",
                "&:hover": {
                  backgroundColor: "transparent",
                  color:
                    Object.keys(filters).length > 0
                      ? muiTheme.palette.primary.dark
                      : theme === "dark"
                        ? "rgba(255,255,255,0.7)"
                        : "rgba(0,0,0,0.6)",
                },
                mr: 1,
              }}
              title={t("search.filters.title", "Filter Results")}
            >
              <FilterListIcon />
              {Object.keys(filters).length > 0 && (
                <Box
                  sx={{
                    position: "absolute",
                    top: -2,
                    right: -2,
                    backgroundColor: muiTheme.palette.primary.main,
                    color: muiTheme.palette.primary.contrastText,
                    borderRadius: "50%",
                    width: 16,
                    height: 16,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.75rem",
                    fontWeight: "bold",
                  }}
                >
                  {Object.keys(filters).length}
                </Box>
              )}
            </IconButton>
          </Box>

          {/* Search Button */}
          <Button
            variant="contained"
            onClick={handleSearchSubmit}
            sx={{
              minWidth: "80px",
              [isRTL ? "mr" : "ml"]: 2,
              borderRadius: "20px",
              height: "40px",
            }}
          >
            {t("common.search")}
          </Button>

          {/* Semantic Search Button */}
          <Button
            variant={storeIsSemantic ? "contained" : "outlined"}
            onClick={handleSemanticSearchToggle}
            sx={{
              minWidth: "100px",
              [isRTL ? "mr" : "ml"]: 2,
              borderRadius: "20px",
              height: "40px",
              color: storeIsSemantic
                ? muiTheme.palette.primary.contrastText
                : theme === "dark"
                  ? "rgba(255,255,255,0.7)"
                  : "text.secondary",
              backgroundColor: storeIsSemantic
                ? muiTheme.palette.primary.main
                : "transparent",
              borderColor: storeIsSemantic
                ? muiTheme.palette.primary.main
                : theme === "dark"
                  ? "rgba(255,255,255,0.3)"
                  : "rgba(0,0,0,0.23)",
              transition: (theme) =>
                theme.transitions.create(
                  ["color", "background-color", "border-color", "transform"],
                  {
                    duration: theme.transitions.duration.short,
                  },
                ),
              "&:hover": {
                backgroundColor: storeIsSemantic
                  ? muiTheme.palette.primary.dark
                  : theme === "dark"
                    ? "rgba(255,255,255,0.08)"
                    : "rgba(0,0,0,0.04)",
                transform: "scale(1.02)",
              },
              "&:focus": {
                outline: `2px solid ${
                  storeIsSemantic
                    ? muiTheme.palette.primary.main
                    : "rgba(0,0,0,0.2)"
                }`,
                outlineOffset: "2px",
              },
              boxShadow: storeIsSemantic
                ? `0 0 8px ${alpha(muiTheme.palette.primary.main, 0.4)}`
                : "none",
            }}
            title={
              storeIsSemantic
                ? t("search.semantic.disable", "Disable semantic search")
                : t("search.semantic.enable", "Enable semantic search")
            }
            aria-pressed={storeIsSemantic}
          >
            {t("search.semantic.label", "Semantic")}
          </Button>
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
        {isFileUploadEnabled && (
          <IconButton
            size="small"
            onClick={handleOpenUploadModal}
            sx={{
              color:
                theme === "dark" ? "rgba(255,255,255,0.7)" : "text.secondary",
              backgroundColor:
                theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.04)",
              borderRadius: "8px",
              padding: "8px",
              "&:hover": {
                backgroundColor:
                  theme === "dark"
                    ? "rgba(255,255,255,0.2)"
                    : "rgba(0,0,0,0.08)",
              },
            }}
          >
            <CloudUploadIcon />
          </IconButton>
        )}

        {/* Notification Center */}
        {isNotificationEnabled && <NotificationCenter />}

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
      {isFileUploadEnabled && (
        <S3UploaderModal
          open={isUploadModalOpen}
          onClose={handleCloseUploadModal}
          onUploadComplete={handleUploadComplete}
          title={t("upload.title", "Upload Media Files")}
          description={t(
            "upload.description",
            "Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported.",
          )}
        />
      )}

      {/* Filter Modal */}
      <FilterModal facetCounts={searchResults?.data?.searchMetadata?.facets} />
    </Box>
  );
}

export default TopBar;
