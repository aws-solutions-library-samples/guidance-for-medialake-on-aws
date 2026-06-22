import React, { useState, useRef, useMemo } from "react";
import {
  Box,
  ButtonBase,
  Chip,
  InputBase,
  Popover,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  FolderOpen as FolderOpenIcon,
  Add as AddIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

import CollectionSection, { SECTION_ITEM_LIMIT } from "./CollectionSection";
import {
  useRecentCollections,
  useGetAllCollections,
  useGetCollections,
  useCreateCollection,
  isAddable,
  type Collection,
} from "@/api/hooks/useCollections";
import { useGetFavorites } from "@/api/hooks/useFavorites";
import { useDebounce } from "@/hooks/useDebounce";

/**
 * Minimal shape representing a selected collection in the upload flow.
 * Only carries the data required by the upload directive (id + display name).
 */
export interface CollectionRef {
  id: string;
  name: string;
}

export interface CollectionSelectorProps {
  value: CollectionRef[];
  onChange: (value: CollectionRef[]) => void;
  disabled?: boolean;
}

/**
 * CollectionSelector — click-to-open popover that lets the uploader pick target collections.
 *
 * Data sources (task 6.4):
 * - Recent: `useRecentCollections` (cursor-paged infinite query)
 * - Favorites: `useGetFavorites("COLLECTION")` resolved via `useGetAllCollections`, filtered by `isAddable`
 * - Search: `useGetCollections` gated by debounced search text (300ms)
 *
 * All sections defensively re-apply `isAddable`. An empty-state message is shown when both
 * Recent and Favorites resolve to zero Addable collections. Search shows an inline error on failure.
 *
 * Design refs: §3.3, §3.4, §3.5
 */
const CollectionSelector: React.FC<CollectionSelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [searchText, setSearchText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const open = Boolean(anchorEl);

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    if (disabled) return;
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
    setSearchText("");
  };

  const hasSearch = searchText.trim().length > 0;

  // Debounce search text at 300ms before issuing the query (Req 3.2)
  const debouncedSearch = useDebounce(searchText.trim(), 300);

  // --- Data sources ---

  // Recent collections (cursor-paged infinite query)
  const {
    data: recentData,
    isLoading: recentLoading,
    fetchNextPage: fetchNextRecentPage,
    hasNextPage: recentHasNextPage,
  } = useRecentCollections(SECTION_ITEM_LIMIT);

  // Favorites: ids from useGetFavorites, resolved via useGetAllCollections
  const { data: favoritesData, isLoading: favoritesLoading } = useGetFavorites("COLLECTION");
  const { data: allCollectionsData } = useGetAllCollections();

  // Search: server-paged query gated by debounced search text
  const [searchPage, setSearchPage] = useState(1);
  const {
    data: searchData,
    isLoading: searchQueryLoading,
    isError: searchIsError,
    isFetching: searchIsFetching,
  } = useGetCollections({
    search: debouncedSearch,
    page: searchPage,
    pageSize: SECTION_ITEM_LIMIT,
    enabled: debouncedSearch.length > 0,
  });

  // --- Derived data: defensively apply isAddable to every section ---

  // Recent: flatten infinite query pages and filter by isAddable
  const recentItems = useMemo(() => {
    if (!recentData?.pages) return [];
    const allItems = recentData.pages.flatMap((page) => page.data ?? []);
    return allItems.filter(isAddable);
  }, [recentData]);

  // Favorites: resolve favorite ids against allCollections, filter by isAddable
  const favoritesItems = useMemo(() => {
    if (!favoritesData || !allCollectionsData?.data) return [];
    const allCollections = allCollectionsData.data;
    const favoriteIds = new Set(favoritesData.map((f) => f.itemId));
    return allCollections.filter((c) => favoriteIds.has(c.id) && isAddable(c));
  }, [favoritesData, allCollectionsData]);

  // Search: accumulate pages and filter by isAddable
  const searchItems = useMemo(() => {
    if (!searchData?.data) return [];
    return searchData.data.filter(isAddable);
  }, [searchData]);

  // Search error message
  const searchError = searchIsError
    ? t("upload.collectionSelector.searchError", "Failed to search collections")
    : null;

  // Search loading state
  const searchLoading = searchQueryLoading || searchIsFetching;

  // Has-more indicators
  const recentHasMore = recentHasNextPage ?? false;
  const favoritesHasMore = false; // Favorites are fully resolved client-side
  const searchHasMore = searchData?.pagination?.hasNextPage ?? false;

  // Empty state: both Recent and Favorites resolve to zero Addable collections
  const showEmptyState =
    !recentLoading && !favoritesLoading && recentItems.length === 0 && favoritesItems.length === 0;

  // Set of selected collection ids for O(1) lookup
  const selectedIds = useMemo(() => new Set(value.map((c) => c.id)), [value]);

  // Toggle a collection's selection state
  const handleToggle = (collection: Collection) => {
    if (selectedIds.has(collection.id)) {
      onChange(value.filter((c) => c.id !== collection.id));
    } else {
      onChange([...value, { id: collection.id, name: collection.name }]);
    }
  };

  // --- Inline create on no match (Req 6.1–6.5) ---
  const createCollection = useCreateCollection();

  const handleCreate = async () => {
    const name = debouncedSearch;
    if (!name) return;
    setCreateError(null);
    const prevSelection = value; // Req 6.5: snapshot previous selection
    try {
      const res = await createCollection.mutateAsync({ name });
      if (res?.data?.id) {
        onChange([...prevSelection, { id: res.data.id, name: res.data.name }]); // Req 6.2, 6.3
      }
    } catch {
      setCreateError(t("upload.collectionSelector.createFailed", "Failed to create collection")); // Req 6.4
      onChange(prevSelection); // Req 6.5: retain previous selection
    }
  };

  // Show create action when search has results but none are Addable (Req 6.1)
  const showCreateAction =
    debouncedSearch.length > 0 && !searchLoading && !searchIsError && searchItems.length === 0;

  // Reset search page and clear create error when search text changes
  const prevDebouncedRef = useRef(debouncedSearch);
  if (prevDebouncedRef.current !== debouncedSearch) {
    prevDebouncedRef.current = debouncedSearch;
    setSearchPage(1);
    setCreateError(null);
  }

  return (
    <>
      {/* Trigger — read-only field that opens the popover on click */}
      <Box
        ref={triggerRef}
        onClick={handleOpen}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            handleOpen(e as unknown as React.MouseEvent<HTMLElement>);
          }
        }}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1.5,
          py: 1,
          borderRadius: 1,
          border: `1px solid ${alpha(theme.palette.divider, 0.3)}`,
          cursor: disabled ? "default" : "pointer",
          opacity: disabled ? 0.5 : 1,
          transition: "border-color 0.2s, background-color 0.2s",
          bgcolor: disabled ? alpha(theme.palette.action.disabledBackground, 0.05) : "transparent",
          "&:hover": disabled
            ? {}
            : {
                borderColor: theme.palette.text.primary,
                bgcolor: alpha(theme.palette.text.primary, isDark ? 0.04 : 0.02),
              },
        }}
      >
        <Typography variant="body2" sx={{ color: "text.secondary", userSelect: "none" }}>
          {t("upload.collectionSelector.trigger", "Add to collections")}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          {value.length > 0 && (
            <Chip
              label={t("upload.collectionSelector.selectedCount", "{{count}} selected", {
                count: value.length,
              })}
              size="small"
              color="primary"
              variant="outlined"
              sx={{ height: 22, fontSize: "0.75rem" }}
            />
          )}
          <ExpandMoreIcon
            sx={{
              fontSize: 20,
              color: "text.secondary",
              transition: "transform 0.2s",
              transform: open ? "rotate(180deg)" : "none",
            }}
          />
        </Box>
      </Box>

      {/* Popover panel */}
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        slotProps={{
          paper: {
            sx: {
              width: anchorEl?.offsetWidth ?? 360,
              minWidth: 300,
              maxHeight: 420,
              mt: 0.5,
              borderRadius: 2,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            },
          },
        }}
      >
        {/* Search input */}
        <Box
          sx={{
            px: 1.5,
            py: 1,
            borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            display: "flex",
            alignItems: "center",
            gap: 1,
          }}
        >
          <SearchIcon sx={{ fontSize: 20, color: "text.secondary", flexShrink: 0 }} />
          <InputBase
            placeholder={t(
              "upload.collectionSelector.searchPlaceholder",
              "Search collections\u2026"
            )}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            autoFocus
            fullWidth
            sx={{
              fontSize: "0.85rem",
              "& input": { py: 0.4 },
              "& input::placeholder": {
                color: "text.secondary",
                opacity: 0.7,
              },
            }}
            inputProps={{ "aria-label": "Search collections" }}
          />
        </Box>

        {/* Panel body */}
        <Box sx={{ flex: 1, overflowY: "auto", px: 1.5, py: 1 }}>
          {hasSearch ? (
            /* Search section — replaces Recent/Favorites while search text is present */
            <>
              <CollectionSection
                title={t("upload.collectionSelector.searchSection", "Search")}
                items={searchItems}
                selectedIds={selectedIds}
                onToggle={handleToggle}
                hasMore={searchHasMore}
                onMore={() => setSearchPage((prev) => prev + 1)}
                loading={searchLoading}
                error={searchError}
                emptyMessage={t(
                  "upload.collectionSelector.noSearchResults",
                  "No matching collections"
                )}
              />
              {/* Inline create action — shown when no Addable match (Req 6.1) */}
              {showCreateAction && (
                <Box sx={{ mt: 0.5 }}>
                  <ButtonBase
                    onClick={handleCreate}
                    disabled={createCollection.isPending}
                    sx={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      px: 1,
                      py: 0.75,
                      borderRadius: 1,
                      justifyContent: "flex-start",
                      textAlign: "left",
                      "&:hover": {
                        bgcolor: alpha(theme.palette.primary.main, isDark ? 0.12 : 0.06),
                      },
                    }}
                  >
                    <AddIcon sx={{ fontSize: 18, color: "primary.main" }} />
                    <Typography
                      variant="body2"
                      sx={{
                        color: "primary.main",
                        fontSize: "0.85rem",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {t("upload.collectionSelector.createAction", 'Create "{{name}}"', {
                        name: debouncedSearch,
                      })}
                    </Typography>
                  </ButtonBase>
                  {createError && (
                    <Typography
                      variant="caption"
                      sx={{ color: "error.main", px: 1, mt: 0.25, display: "block" }}
                    >
                      {createError}
                    </Typography>
                  )}
                </Box>
              )}
            </>
          ) : showEmptyState ? (
            /* Empty state when no Addable Recent or Favorites */
            <Box sx={{ textAlign: "center", py: 4 }}>
              <FolderOpenIcon
                sx={{
                  fontSize: 40,
                  color: alpha(theme.palette.text.secondary, 0.3),
                  mb: 1,
                }}
              />
              <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.85rem" }}>
                {t(
                  "upload.collectionSelector.emptyState",
                  "No collections available. Create one using search."
                )}
              </Typography>
            </Box>
          ) : (
            /* Recent + Favorites sections when no search text */
            <>
              <CollectionSection
                title={t("upload.collectionSelector.recentSection", "Recent")}
                items={recentItems}
                selectedIds={selectedIds}
                onToggle={handleToggle}
                hasMore={recentHasMore}
                onMore={() => fetchNextRecentPage()}
                loading={recentLoading}
                emptyMessage={t("upload.collectionSelector.emptyRecent", "No recent collections")}
              />
              <CollectionSection
                title={t("upload.collectionSelector.favoritesSection", "Favorites")}
                items={favoritesItems}
                selectedIds={selectedIds}
                onToggle={handleToggle}
                hasMore={favoritesHasMore}
                onMore={() => {}}
                loading={favoritesLoading}
                emptyMessage={t(
                  "upload.collectionSelector.emptyFavorites",
                  "No favorite collections"
                )}
              />
            </>
          )}
        </Box>
      </Popover>
    </>
  );
};

export default CollectionSelector;
