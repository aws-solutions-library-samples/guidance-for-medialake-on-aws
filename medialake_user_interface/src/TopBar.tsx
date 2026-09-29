import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
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
import { useNavigate, useLocation } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import debounce from "lodash/debounce";
import { useTranslation } from "react-i18next";
import { useTheme } from "./hooks/useTheme";
import { useDirection } from "./contexts/DirectionContext";
import { S3UploaderModal } from "./features/upload";
import { useMyAssetsConnector } from "./api/hooks/useMyAssetsConnector";
import { usePermission } from "./permissions";
import { useFeatureFlag } from "./contexts/FeatureFlagsContext";
import FilterModal from "./components/search/FilterModal";
import {
  useSearchFilters,
  useSearchQuery,
  useSemanticSearch,
  useDomainActions,
  useUIActions,
  useActiveFilterCount,
  useSearchStore,
} from "./stores/searchStore";
import type { FacetFilters } from "./types/facetSearch";
import {
  definitionToSearchParams,
  SEARCH_DEFINITION_VERSION,
} from "./features/search-history/searchDefinition";
import {
  useRunSearch,
  useSearchSuggestions,
  type SuggestionItem,
} from "./features/search-history/hooks";
import { useClearSearchHistory, useRemoveHistoryEntry } from "./features/search-history/api";
import {
  SearchSuggestionsPanel,
  SUGGESTIONS_LISTBOX_ID,
  suggestionOptionId,
} from "./features/search-history/components/SearchSuggestionsPanel";
import { NotificationCenter } from "./components/NotificationCenter";
import { QUERY_KEYS } from "./api/queryKeys";
import SemanticModeToggle from "./components/TopBar/SemanticModeToggle";
import SearchModeSelector from "./components/TopBar/SearchModeSelector";
import { useSemanticSearchStatus } from "./features/settings/system/hooks/useSystemSettings";

interface SearchTag {
  key: string;
  value: string;
}

/** Filter values that identify a cached search result list. */
function facetParamsFor(filters: FacetFilters): Record<string, unknown> {
  const facetParams: Record<string, unknown> = {
    type: filters.type,
    extension: filters.extension,
    asset_size_gte: filters.asset_size_gte,
    asset_size_lte: filters.asset_size_lte,
    ingested_date_gte: filters.ingested_date_gte,
    ingested_date_lte: filters.ingested_date_lte,
    filename: filters.filename,
    customMetadataFilters: filters.customMetadataFilters,
  };
  Object.keys(facetParams).forEach((key) => {
    if (facetParams[key] === undefined) delete facetParams[key];
  });
  return facetParams;
}

function TopBar() {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const isDark = theme === "dark";
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

  // Fetch My Assets connector for upload pre-selection
  const { connector: myAssetsConnector } = useMyAssetsConnector();
  const myAssetsEnabled = useFeatureFlag("my-assets-enabled", false);

  // Only users with upload permission see the upload entry point.
  const { can } = usePermission();
  const canUpload = can("upload", "asset");

  // Keep a ref to the latest filters so the debounced callback always reads
  // the current value instead of a stale closure capture.
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  // Same for storeIsSemantic — the debounced callback should read the latest value.
  const storeIsSemanticRef = useRef(storeIsSemantic);
  storeIsSemanticRef.current = storeIsSemantic;

  /**
   * Navigate to /search for `query` with the current semantic options and
   * filters. The URL carries everything needed to reproduce the search,
   * including Full/Clip and the Visual/Audio/Transcript modes.
   */
  const goToSearch = useCallback(
    (query: string) => {
      const currentFilters = filtersRef.current;
      const currentIsSemantic = storeIsSemanticRef.current;
      const { semanticMode, searchModes } = useSearchStore.getState();

      setQuery(query);
      setIsSemantic(currentIsSemantic);

      // Invalidate so re-submitting identical parameters still refetches.
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.SEARCH.list(
          query,
          1,
          50,
          currentIsSemantic,
          [],
          facetParamsFor(currentFilters)
        ),
      });

      const params = definitionToSearchParams({
        v: SEARCH_DEFINITION_VERSION,
        q: query,
        semantic: currentIsSemantic,
        semanticMode,
        searchModes,
        // Raw filters, not normalized: the live search keeps its absolute dates.
        filters: currentFilters,
      });
      navigate(`/search?${params.toString()}`);
    },
    [navigate, setQuery, setIsSemantic, queryClient]
  );

  // ── Saved / recent searches dropdown ──
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null);
  const skipNextEnterRef = useRef(false);
  const suggestions = useSearchSuggestions(searchInput);
  const runSearch = useRunSearch();
  const removeHistoryEntry = useRemoveHistoryEntry();
  const clearHistory = useClearSearchHistory();
  const showSuggestions = suggestionsOpen && suggestions.items.length > 0;

  const closeSuggestions = useCallback(() => {
    setSuggestionsOpen(false);
    setActiveSuggestionId(null);
  }, []);

  const handleSelectSuggestion = useCallback(
    (item: SuggestionItem) => {
      closeSuggestions();
      setSearchTags([]);
      setSearchInput("");
      runSearch(item.definition);
    },
    [closeSuggestions, runSearch]
  );

  const handleSearchKeyDown = (event: React.KeyboardEvent) => {
    const items = suggestions.items;
    if (event.key === "Escape") {
      if (suggestionsOpen) {
        event.preventDefault();
        closeSuggestions();
      }
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!items.length) return;
      event.preventDefault();
      setSuggestionsOpen(true);
      const index = items.findIndex((i) => i.id === activeSuggestionId);
      const next =
        event.key === "ArrowDown"
          ? (index + 1) % items.length
          : index <= 0
            ? items.length - 1
            : index - 1;
      setActiveSuggestionId(items[next].id);
      return;
    }
    const active = showSuggestions ? items.find((i) => i.id === activeSuggestionId) : undefined;
    if (event.key === "Enter" && active) {
      event.preventDefault();
      skipNextEnterRef.current = true;
      handleSelectSuggestion(active);
      return;
    }
    if (event.key === "Delete" && active?.kind === "history" && event.shiftKey) {
      event.preventDefault();
      removeHistoryEntry.mutate(active.entry.fingerprint);
    }
  };

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
    // Sync the search input from the store when on the search page.
    // Use !== null to allow empty string (browse-all) to clear the input.
    if (location.pathname === "/search" && storeQuery !== null && storeQuery !== searchInput) {
      setSearchInput(storeQuery);
    }
  }, [location.pathname, storeQuery]);

  const getSearchQuery = useCallback(() => {
    const tagPart = searchTags.map((tag) => `${tag.key}: ${tag.value}`).join(" ");
    return `${tagPart}${tagPart && searchInput ? " " : ""}${searchInput}`.trim();
  }, [searchTags, searchInput]);

  const debouncedSearch = useMemo(
    () =>
      debounce((query: string) => {
        if (query.trim()) {
          goToSearch(query);
        }
      }, 500),
    [goToSearch]
  );

  // Handle search results from session storage
  useEffect(() => {
    // Cancel any pending debounced search on unmount
    return () => {
      debouncedSearch.cancel();
    };
  }, [debouncedSearch]);

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
        goToSearch(getSearchQuery());
        return true;
      }
    }
    return false;
  };

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setSearchInput(value);
    setSuggestionsOpen(true);
    setActiveSuggestionId(null);

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
    if (event.key === "Enter" && skipNextEnterRef.current) {
      // The keydown already ran the highlighted saved/recent search.
      skipNextEnterRef.current = false;
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      handleSearchSubmit();
    }
  };

  const handleSearchSubmit = () => {
    closeSuggestions();
    if (searchInput.includes(":")) {
      createTagFromInput(searchInput);
    } else {
      // An empty search box (no text, no tags) is allowed: it submits an empty
      // query, which the backend treats as "match all" and returns every asset
      // (any active filters are still applied). The box is cleared after
      // navigating, so it stays blank.
      goToSearch(getSearchQuery());

      // Clear the search input after navigation
      setSearchInput("");
    }
  };

  const handleDeleteTag = (tagToDelete: SearchTag) => {
    setSearchTags((prev) => {
      const newTags = prev.filter(
        (tag) => !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
      );
      goToSearch(newTags.map((tag) => `${tag.key}: ${tag.value}`).join(" "));
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

  const activeFilterCount = useActiveFilterCount();
  const hasActiveFilters = activeFilterCount > 0;

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
              border: `1px solid ${alpha(muiTheme.palette.divider, isDark ? 0.12 : 0.1)}`,
              boxShadow: isDark
                ? `0 1px 3px ${alpha(muiTheme.palette.common.black, 0.4)}, 0 1px 2px ${alpha(
                    muiTheme.palette.common.black,
                    0.3
                  )}`
                : `0 1px 3px ${alpha(muiTheme.palette.common.black, 0.08)}, 0 1px 2px ${alpha(
                    muiTheme.palette.common.black,
                    0.06
                  )}`,
              transition: "border-color 0.2s, box-shadow 0.2s",
              "&:focus-within": {
                borderColor: alpha(muiTheme.palette.primary.main, 0.5),
                boxShadow: `0 0 0 2px ${alpha(
                  muiTheme.palette.primary.main,
                  isDark ? 0.25 : 0.15
                )}`,
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
              onKeyDown={handleSearchKeyDown}
              onFocus={() => setSuggestionsOpen(true)}
              onBlur={closeSuggestions}
              inputProps={{
                role: "combobox",
                "aria-label": t("search.bar.label", "Search"),
                "aria-autocomplete": "list",
                "aria-expanded": showSuggestions,
                "aria-controls": showSuggestions ? SUGGESTIONS_LISTBOX_ID : undefined,
                "aria-activedescendant":
                  showSuggestions && activeSuggestionId
                    ? suggestionOptionId(
                        suggestions.items.find((i) => i.id === activeSuggestionId)!
                      )
                    : undefined,
              }}
              fullWidth
              sx={{
                textAlign: isRTL ? "right" : "left",
                fontSize: "14px",
                color: muiTheme.palette.text.primary,
                [isRTL ? "mr" : "ml"]: storeIsSemantic ? 0 : 1.5,
                "& input": {
                  padding: "8px 0",
                  "&::placeholder": {
                    color: muiTheme.palette.text.disabled,
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
                  color: alpha(muiTheme.palette.text.secondary, 0.6),
                  padding: "4px",
                  flexShrink: 0,
                  "&:hover": {
                    backgroundColor: "transparent",
                    color: muiTheme.palette.text.secondary,
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
                    color: alpha(muiTheme.palette.text.secondary, 0.7),
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
                      : alpha(muiTheme.palette.action.active, isDark ? 0.18 : 0.14),
                    position: "relative",
                    cursor: "pointer",
                    transition: "background-color 0.2s",
                    flexShrink: 0,
                    "&:hover": {
                      backgroundColor: storeIsSemantic
                        ? muiTheme.palette.primary.dark
                        : alpha(muiTheme.palette.action.active, isDark ? 0.25 : 0.2),
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
                      backgroundColor: muiTheme.palette.common.white,
                      boxShadow: `0 1px 2px ${alpha(muiTheme.palette.common.black, 0.2)}`,
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
                  backgroundColor: alpha(muiTheme.palette.divider, isDark ? 0.15 : 0.12),
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
                    : alpha(muiTheme.palette.text.secondary, 0.7),
                  padding: "5px",
                  flexShrink: 0,
                  position: "relative",
                  "&:hover": {
                    backgroundColor: alpha(muiTheme.palette.action.active, 0.06),
                    color: hasActiveFilters
                      ? muiTheme.palette.primary.dark
                      : muiTheme.palette.text.secondary,
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
                      border: `2px solid ${muiTheme.palette.background.paper}`,
                      boxSizing: "content-box",
                    }}
                  >
                    {activeFilterCount}
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
                  color: muiTheme.palette.primary.contrastText,
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
        {/* Upload Button — only for users who can upload */}
        {canUpload && (
          <IconButton
            size="small"
            onClick={handleOpenUploadModal}
            sx={{
              color: muiTheme.palette.text.secondary,
              backgroundColor: alpha(muiTheme.palette.action.active, isDark ? 0.1 : 0.04),
              borderRadius: "8px",
              padding: "8px",
              "&:hover": {
                backgroundColor: alpha(muiTheme.palette.action.active, isDark ? 0.2 : 0.08),
              },
            }}
          >
            <CloudUploadIcon />
          </IconButton>
        )}

        {/* Notification Center */}
        <NotificationCenter />

        {/* Chat Icon Button */}
        {isChatEnabled && (
          <IconButton
            size="small"
            onClick={toggleChat}
            sx={{
              color: isChatOpen ? muiTheme.palette.primary.main : muiTheme.palette.text.secondary,
              backgroundColor: isChatOpen
                ? alpha(muiTheme.palette.primary.main, 0.1)
                : alpha(muiTheme.palette.action.active, isDark ? 0.1 : 0.04),
              borderRadius: "8px",
              padding: "8px",
              transition: (theme) =>
                theme.transitions.create(["color", "background-color"], {
                  duration: theme.transitions.duration.short,
                }),
              "&:hover": {
                backgroundColor: isChatOpen
                  ? alpha(muiTheme.palette.primary.main, 0.2)
                  : alpha(muiTheme.palette.action.active, isDark ? 0.2 : 0.08),
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
          "Select a destination and upload your media files. Only audio, video, image, HLS, and MPEG-DASH formats are supported."
        )}
        defaultConnectorId={myAssetsEnabled ? myAssetsConnector?.id : undefined}
        defaultObjectPrefix={myAssetsEnabled ? myAssetsConnector?.objectPrefix : undefined}
      />

      {/* Saved and recent searches (renders nothing when the user has none) */}
      <SearchSuggestionsPanel
        open={showSuggestions}
        anchorEl={searchBoxRef.current}
        savedItems={suggestions.savedItems}
        historyItems={suggestions.historyItems}
        totalSaved={suggestions.totalSaved}
        activeId={activeSuggestionId}
        onSelect={handleSelectSuggestion}
        onRemoveHistory={(fingerprint) => removeHistoryEntry.mutate(fingerprint)}
        onClearHistory={() => clearHistory.mutate()}
        onManage={() => {
          closeSuggestions();
          navigate("/settings/profile#saved-searches");
        }}
        onClose={closeSuggestions}
        onHover={setActiveSuggestionId}
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
