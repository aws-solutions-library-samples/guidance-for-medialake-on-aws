import React, { useMemo, useState, useCallback } from "react";
import {
  Box,
  Button,
  IconButton,
  InputBase,
  Menu,
  Typography,
  Tooltip,
  Divider,
  Chip,
  Badge,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Search as SearchIcon,
  Clear as ClearIcon,
  Sort as SortIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  CheckCircle as CheckCircleIcon,
  FilterList as FilterListIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

export type SortDirection = "asc" | "desc";

export interface CollectionSortOption {
  id: string;
  label: string;
  /** Default direction when the option is selected (strings → asc, dates → desc) */
  defaultDirection?: SortDirection;
}

export interface CollectionViewControlsProps {
  searchValue: string;
  onSearchChange: (value: string) => void;

  /** Current sort field (e.g. "name", "createdAt", "customMetadata.priority") */
  sortField: string;
  sortDirection: SortDirection;
  onSortChange: (field: string, direction: SortDirection) => void;

  /** Standard sort options — shown at the top of the popover */
  standardSortOptions: CollectionSortOption[];
  /**
   * Custom metadata keys to offer as sort options. Each key becomes a
   * `customMetadata.<key>` sort value. Rendered under a separator with a
   * "Custom metadata" section label.
   */
  customMetadataKeys: string[];

  /** Opens the filter popover, anchored to the clicked trigger element. */
  onOpenFilters?: (e: React.MouseEvent<HTMLElement>) => void;
  /** Count of currently-applied filters — displayed as a badge on the trigger. */
  activeFilterCount?: number;
  /**
   * Additional trigger(s) to render at the end of the toolbar (right side),
   * after the Filters button. Used by the Collections page to mount the
   * `CollectionCardViewControls` trigger without introducing a second toolbar
   * row.
   */
  endSlot?: React.ReactNode;
}

/**
 * Toolbar strip for the Collections list page. Matches the Search page's
 * `AssetViewControls` pattern (Sort popover, Filters trigger, icon buttons)
 * so the two primary list surfaces feel like the same product.
 *
 * Sort popover splits options into two sections:
 *   - Standard fields (name, createdAt, updatedAt)
 *   - Custom metadata (one row per key surfaced by the /collections/metadata-keys endpoint)
 *
 * The direction chip on the active row is clickable — flipping direction stays
 * in the popover, picking a different row resets direction to the option's
 * `defaultDirection` (asc for strings, desc for dates).
 */
export const CollectionViewControls: React.FC<CollectionViewControlsProps> = ({
  searchValue,
  onSearchChange,
  sortField,
  sortDirection,
  onSortChange,
  standardSortOptions,
  customMetadataKeys,
  onOpenFilters,
  activeFilterCount = 0,
  endSlot,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [sortAnchor, setSortAnchor] = useState<HTMLElement | null>(null);

  const customSortOptions = useMemo<CollectionSortOption[]>(
    () =>
      customMetadataKeys.map((key) => ({
        id: `customMetadata.${key}`,
        label: key,
        defaultDirection: "asc",
      })),
    [customMetadataKeys]
  );

  const allOptions = useMemo(
    () => [...standardSortOptions, ...customSortOptions],
    [standardSortOptions, customSortOptions]
  );

  const activeOption = useMemo(
    () => allOptions.find((o) => o.id === sortField),
    [allOptions, sortField]
  );

  // Default sort is the first standard option (name asc in our config). We treat
  // that as "no explicit sort" for the button label — it stays simple until the
  // user changes it.
  const isDefaultSort =
    standardSortOptions.length > 0 &&
    sortField === standardSortOptions[0].id &&
    sortDirection === (standardSortOptions[0].defaultDirection ?? "asc");

  const openSort = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => setSortAnchor(e.currentTarget),
    []
  );
  const closeSort = useCallback(() => setSortAnchor(null), []);

  const pickOption = useCallback(
    (option: CollectionSortOption) => {
      const dir = option.defaultDirection ?? "asc";
      onSortChange(option.id, dir);
      closeSort();
    },
    [onSortChange, closeSort]
  );

  const flipDirection = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onSortChange(sortField, sortDirection === "asc" ? "desc" : "asc");
    },
    [onSortChange, sortField, sortDirection]
  );

  const triggerSx = useCallback(
    (isOpen: boolean, isActive: boolean) => ({
      textTransform: "none" as const,
      borderRadius: "8px",
      px: 1.5,
      py: 0.5,
      fontSize: "0.8125rem",
      fontWeight: 500,
      color: isActive ? "primary.main" : "text.secondary",
      bgcolor: isOpen ? alpha(theme.palette.primary.main, 0.08) : "transparent",
      border: "1px solid",
      borderColor: isActive ? alpha(theme.palette.primary.main, 0.3) : "transparent",
      "&:hover": {
        bgcolor: alpha(theme.palette.primary.main, 0.08),
        color: "text.primary",
      },
    }),
    [theme]
  );

  const renderOption = (option: CollectionSortOption) => {
    const isActive = sortField === option.id;
    return (
      <Box
        key={option.id}
        role="option"
        aria-selected={isActive}
        tabIndex={0}
        onClick={() => pickOption(option)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pickOption(option);
          }
        }}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          py: 0.875,
          px: 1.25,
          borderRadius: "8px",
          cursor: "pointer",
          bgcolor: isActive ? alpha(theme.palette.primary.main, 0.08) : "transparent",
          transition: "all 0.12s ease",
          "&:hover, &:focus-visible": {
            bgcolor: isActive
              ? alpha(theme.palette.primary.main, 0.12)
              : alpha(theme.palette.primary.main, 0.04),
            outline: "none",
          },
          "&:focus-visible": {
            boxShadow: `inset 0 0 0 2px ${theme.palette.primary.main}`,
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
          {isActive && (
            <CheckCircleIcon
              sx={{
                fontSize: "0.875rem",
                color: "primary.main",
                flexShrink: 0,
              }}
            />
          )}
          <Typography
            variant="body2"
            noWrap
            sx={{
              fontSize: "0.8125rem",
              fontWeight: isActive ? 600 : 400,
              color: isActive ? "primary.main" : "text.primary",
            }}
          >
            {option.label}
          </Typography>
        </Box>
        {isActive && (
          <Tooltip title={t("common.viewControls.flipDirection", "Flip direction")}>
            <Chip
              size="small"
              label={
                sortDirection === "desc"
                  ? t("common.viewControls.desc", "Desc")
                  : t("common.viewControls.asc", "Asc")
              }
              icon={
                sortDirection === "desc" ? (
                  <ArrowDownwardIcon sx={{ fontSize: "0.7rem" }} />
                ) : (
                  <ArrowUpwardIcon sx={{ fontSize: "0.7rem" }} />
                )
              }
              onClick={flipDirection}
              sx={{
                height: 22,
                fontSize: "0.6875rem",
                fontWeight: 600,
                flexShrink: 0,
                ml: 1,
                cursor: "pointer",
                bgcolor: alpha(theme.palette.primary.main, 0.1),
                color: "primary.main",
                "& .MuiChip-icon": { color: "primary.main", ml: 0.5 },
                "&:hover": {
                  bgcolor: alpha(theme.palette.primary.main, 0.18),
                },
              }}
            />
          </Tooltip>
        )}
      </Box>
    );
  };

  const activeSortLabel = activeOption?.label;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        mb: 0.75,
      }}
    >
      {/* Search input — owns its own border, so it's the only visual container
          on the toolbar. Everything else is a transparent trigger button. */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          flex: "0 0 340px",
          maxWidth: 340,
          px: 1.25,
          py: 0.65,
          bgcolor: "background.paper",
          border: `1px solid ${alpha(theme.palette.divider, 0.14)}`,
          borderRadius: 1.5,
          transition: "border-color 120ms, box-shadow 120ms",
          "&:focus-within": {
            borderColor: theme.palette.primary.main,
            boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, 0.12)}`,
          },
        }}
      >
        <SearchIcon sx={{ fontSize: 16, color: "text.disabled" }} />
        <InputBase
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t("collectionsPage.searchPlaceholder", "Search collections...")}
          sx={{ flex: 1, fontSize: "0.8125rem" }}
        />
        {searchValue && (
          <IconButton
            size="small"
            onClick={() => onSearchChange("")}
            aria-label={t("common.clear", "Clear")}
            sx={{ p: 0.25, color: "text.disabled" }}
          >
            <ClearIcon sx={{ fontSize: 14 }} />
          </IconButton>
        )}
      </Box>

      <Box sx={{ flex: 1 }} />

      {/* Sort trigger */}
      <Button
        size="small"
        startIcon={<SortIcon />}
        endIcon={<KeyboardArrowDownIcon />}
        onClick={openSort}
        aria-haspopup="true"
        aria-expanded={Boolean(sortAnchor)}
        sx={triggerSx(Boolean(sortAnchor), !isDefaultSort)}
      >
        {!isDefaultSort && activeSortLabel ? (
          <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            {t("common.viewControls.sort", "Sort")}:
            <Box component="span" sx={{ color: "primary.main", fontWeight: 600 }}>
              {activeSortLabel}
            </Box>
            {sortDirection === "desc" ? (
              <ArrowDownwardIcon sx={{ fontSize: "0.75rem" }} />
            ) : (
              <ArrowUpwardIcon sx={{ fontSize: "0.75rem" }} />
            )}
          </Box>
        ) : (
          t("common.viewControls.sort", "Sort")
        )}
      </Button>

      {/* Filters trigger */}
      {onOpenFilters && (
        <Badge
          badgeContent={activeFilterCount || undefined}
          color="primary"
          overlap="rectangular"
          sx={{
            "& .MuiBadge-badge": {
              fontSize: "0.625rem",
              height: 16,
              minWidth: 16,
              right: 4,
              top: 4,
            },
          }}
        >
          <Button
            size="small"
            startIcon={<FilterListIcon />}
            onClick={(e) => onOpenFilters(e)}
            sx={triggerSx(false, activeFilterCount > 0)}
          >
            {t("collectionsPage.filters.title", "Filters")}
          </Button>
        </Badge>
      )}

      {/* End slot (view/display trigger) */}
      {endSlot}

      {/* Sort popover */}
      <Menu
        anchorEl={sortAnchor}
        open={Boolean(sortAnchor)}
        onClose={closeSort}
        slotProps={{
          paper: {
            elevation: 3,
            sx: {
              mt: 0.5,
              minWidth: 260,
              borderRadius: 1.5,
              border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            },
          },
        }}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <Box sx={{ p: 1.25 }}>
          <Typography
            variant="overline"
            sx={{
              display: "block",
              fontSize: "0.625rem",
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: "text.disabled",
              px: 1.25,
              mb: 0.5,
            }}
          >
            {t("collectionsPage.sort.standardFields", "Standard fields")}
          </Typography>
          <Box
            role="listbox"
            aria-label="Sort options"
            sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}
          >
            {standardSortOptions.map(renderOption)}
          </Box>
          {customSortOptions.length > 0 && (
            <>
              <Divider
                sx={{
                  my: 1,
                  borderColor: alpha(theme.palette.divider, 0.5),
                }}
              />
              <Typography
                variant="overline"
                sx={{
                  display: "block",
                  fontSize: "0.625rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: "text.disabled",
                  px: 1.25,
                  mb: 0.5,
                }}
              >
                {t("collectionsPage.sort.customMetadata", "Custom metadata")}
              </Typography>
              <Box
                role="listbox"
                aria-label="Custom metadata sort options"
                sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}
              >
                {customSortOptions.map(renderOption)}
              </Box>
            </>
          )}
        </Box>
      </Menu>
    </Box>
  );
};

export default CollectionViewControls;
