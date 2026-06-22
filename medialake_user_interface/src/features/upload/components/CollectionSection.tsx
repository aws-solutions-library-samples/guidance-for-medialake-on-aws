import React, { useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import { FolderOpen as FolderOpenIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";

import type { Collection } from "@/api/hooks/useCollections";

/** Maximum number of items shown per "page" within a section. */
export const SECTION_ITEM_LIMIT = 5;

export interface CollectionSectionProps {
  /** Section heading (e.g. "Recent", "Favorites", "Search") */
  title: string;
  /** Full list of collection items available for this section */
  items: Collection[];
  /** Set of currently selected collection ids */
  selectedIds: Set<string>;
  /** Callback when a collection is toggled */
  onToggle: (collection: Collection) => void;
  /**
   * Whether there are more items available beyond `items.length`.
   * For server-paged sections (Search), this indicates another server page exists.
   * For client-paged sections (Recent/Favorites), this is typically false since
   * all items are already in `items`.
   */
  hasMore?: boolean;
  /** Called when the user activates the More affordance */
  onMore?: () => void;
  /** Whether the section is currently loading data */
  loading?: boolean;
  /** Error message to display instead of items */
  error?: string | null;
  /** Empty-state message when items is empty and not loading */
  emptyMessage?: string;
}

/**
 * CollectionSection — presentational component that renders a capped list of
 * collections within a section of the CollectionSelector popover.
 *
 * Display logic:
 *   - Shows at most SECTION_ITEM_LIMIT * pagesShown items (capped at items.length).
 *   - Renders a "More" text button iff there are more items available than
 *     currently shown (either locally paginated or server-paginated via `hasMore`).
 *   - Recent/Favorites paginate client-side (advance local `pagesShown`);
 *     Search appends server-side pages (parent calls `onMore` to fetch next page).
 *
 * Validates: Requirements 2.3, 2.4, 2.5, 3.3, 3.4, 3.5
 */
const CollectionSection: React.FC<CollectionSectionProps> = ({
  title,
  items,
  selectedIds,
  onToggle,
  hasMore = false,
  onMore,
  loading = false,
  error = null,
  emptyMessage,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  // Client-side pagination: how many "pages" of items to show
  const [pagesShown, setPagesShown] = useState(1);

  // Number of items currently visible
  const visibleCount = Math.min(SECTION_ITEM_LIMIT * pagesShown, items.length);
  const visibleItems = items.slice(0, visibleCount);

  // More affordance is shown when:
  // 1. There are more local items beyond visibleCount, OR
  // 2. The parent signals server-side hasMore (all local items shown but more exist on server)
  const moreLocalItems = items.length > visibleCount;
  const showMore = moreLocalItems || (visibleCount >= items.length && hasMore);

  const handleMore = () => {
    if (moreLocalItems) {
      // Client-side pagination: show next page of already-loaded items
      setPagesShown((prev) => prev + 1);
    } else if (hasMore && onMore) {
      // Server-side pagination: fetch the next page
      onMore();
    }
  };

  return (
    <Box sx={{ mb: 1.5 }}>
      {/* Section title */}
      <Typography
        variant="caption"
        sx={{
          color: "text.secondary",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          display: "block",
          mb: 0.5,
          px: 0.5,
        }}
      >
        {title}
      </Typography>

      {/* Error state */}
      {error && (
        <Box sx={{ px: 0.5, py: 1 }}>
          <Typography variant="body2" sx={{ color: "error.main", fontSize: "0.8rem" }}>
            {error}
          </Typography>
        </Box>
      )}

      {/* Loading state */}
      {!error && loading && items.length === 0 && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
          <CircularProgress size={20} />
        </Box>
      )}

      {/* Empty state */}
      {!error && !loading && items.length === 0 && (
        <Box sx={{ textAlign: "center", py: 2 }}>
          <FolderOpenIcon
            sx={{
              fontSize: 32,
              color: alpha(theme.palette.text.secondary, 0.3),
              mb: 0.5,
            }}
          />
          <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.8rem" }}>
            {emptyMessage || t("upload.collectionSelector.emptySection", "No collections")}
          </Typography>
        </Box>
      )}

      {/* Items list */}
      {!error && visibleItems.length > 0 && (
        <Box>
          {visibleItems.map((collection) => {
            const isSelected = selectedIds.has(collection.id);
            return (
              <Box
                key={collection.id}
                onClick={() => onToggle(collection)}
                role="option"
                aria-selected={isSelected}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                  px: 0.5,
                  py: 0.4,
                  borderRadius: 1,
                  cursor: "pointer",
                  transition: "background-color 0.15s",
                  "&:hover": {
                    bgcolor: alpha(theme.palette.text.primary, 0.04),
                  },
                }}
              >
                <Checkbox
                  checked={isSelected}
                  size="small"
                  tabIndex={-1}
                  sx={{ p: 0.25 }}
                  inputProps={{ "aria-label": `Select ${collection.name}` }}
                />
                <Typography
                  variant="body2"
                  sx={{
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontSize: "0.85rem",
                  }}
                >
                  {collection.name}
                </Typography>
                {collection.userRole && (
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontSize: "0.7rem",
                      flexShrink: 0,
                    }}
                  >
                    {collection.userRole}
                  </Typography>
                )}
              </Box>
            );
          })}
        </Box>
      )}

      {/* More affordance */}
      {showMore && (
        <Button
          size="small"
          onClick={handleMore}
          disabled={loading}
          sx={{
            mt: 0.5,
            px: 0.5,
            py: 0.25,
            minWidth: "auto",
            fontSize: "0.75rem",
            textTransform: "none",
            color: "text.secondary",
            "&:hover": { color: "primary.main" },
          }}
        >
          {loading
            ? t("upload.collectionSelector.loading", "Loading\u2026")
            : t("upload.collectionSelector.more", "More")}
        </Button>
      )}
    </Box>
  );
};

export default CollectionSection;
