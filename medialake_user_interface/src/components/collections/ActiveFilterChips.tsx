import React from "react";
import { Box, Chip, Typography, alpha, useTheme } from "@mui/material";
import { useTranslation } from "react-i18next";
import type { CollectionFilterState } from "./CollectionFilterDrawer";

export interface ActiveFilterChipsProps {
  search: string;
  sortLabel?: string;
  sortDirection: "asc" | "desc";
  /** True when the current sort is the default — we suppress the chip in that case */
  sortIsDefault: boolean;
  filters: CollectionFilterState;
  collectionTypeNameById: Record<string, string>;
  onClearSearch: () => void;
  onClearSort: () => void;
  onRemoveVisibility: (v: CollectionFilterState["visibility"][number]) => void;
  onRemoveType: (id: string) => void;
  onRemoveTag: (tag: string) => void;
  onRemoveMetadata: (id: string) => void;
  onClearUpdatedWithin: () => void;
  onClearAll: () => void;
}

/**
 * Horizontal row of removable chips that surface every currently-applied filter,
 * sort, and search. Lives under the toolbar so the user can see — and dismiss —
 * exactly what's narrowing their results without reopening the drawer.
 *
 * The row hides entirely when no filters are active so it doesn't add vertical
 * noise to an otherwise clean list.
 */
export const ActiveFilterChips: React.FC<ActiveFilterChipsProps> = ({
  search,
  sortLabel,
  sortDirection,
  sortIsDefault,
  filters,
  collectionTypeNameById,
  onClearSearch,
  onClearSort,
  onRemoveVisibility,
  onRemoveType,
  onRemoveTag,
  onRemoveMetadata,
  onClearUpdatedWithin,
  onClearAll,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const chips: React.ReactNode[] = [];

  if (search) {
    chips.push(
      <Chip
        key="search"
        label={`${t("common.search", "Search")}: "${search}"`}
        size="small"
        onDelete={onClearSearch}
        sx={chipSx(theme)}
      />
    );
  }

  if (!sortIsDefault && sortLabel) {
    chips.push(
      <Chip
        key="sort"
        label={`${t("common.viewControls.sort", "Sort")}: ${sortLabel} ${
          sortDirection === "desc" ? "↓" : "↑"
        }`}
        size="small"
        onDelete={onClearSort}
        sx={chipSx(theme)}
      />
    );
  }

  for (const v of filters.visibility) {
    const label =
      v === "public"
        ? t("collectionsPage.labels.public", "Public")
        : v === "shared"
          ? t("collectionsPage.filters.sharedWithMe", "Shared with me")
          : t("collectionsPage.labels.private", "Private");
    chips.push(
      <Chip
        key={`vis-${v}`}
        label={label}
        size="small"
        onDelete={() => onRemoveVisibility(v)}
        sx={chipSx(theme)}
      />
    );
  }

  for (const id of filters.collectionTypeIds) {
    const name = collectionTypeNameById[id] || id;
    chips.push(
      <Chip
        key={`type-${id}`}
        label={name}
        size="small"
        onDelete={() => onRemoveType(id)}
        sx={chipSx(theme)}
      />
    );
  }

  for (const tag of filters.tags) {
    chips.push(
      <Chip
        key={`tag-${tag}`}
        label={`#${tag}`}
        size="small"
        onDelete={() => onRemoveTag(tag)}
        sx={chipSx(theme)}
      />
    );
  }

  for (const f of filters.metadataFilters) {
    if (!f.key.trim() || !f.value.trim()) continue;
    chips.push(
      <Chip
        key={`md-${f.id}`}
        label={`${f.key} = ${f.value}`}
        size="small"
        onDelete={() => onRemoveMetadata(f.id)}
        sx={chipSx(theme)}
      />
    );
  }

  if (filters.updatedWithin) {
    const label =
      filters.updatedWithin === "24h"
        ? t("collectionsPage.filters.last24h", "Last 24 hours")
        : filters.updatedWithin === "7d"
          ? t("collectionsPage.filters.last7d", "Last 7 days")
          : t("collectionsPage.filters.last30d", "Last 30 days");
    chips.push(
      <Chip
        key="updated"
        label={label}
        size="small"
        onDelete={onClearUpdatedWithin}
        sx={chipSx(theme)}
      />
    );
  }

  if (chips.length === 0) return null;

  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 0.75,
        mb: 0.75,
      }}
    >
      <Typography
        variant="overline"
        sx={{
          fontSize: "0.625rem",
          fontWeight: 700,
          letterSpacing: "0.08em",
          color: "text.disabled",
          mr: 0.5,
        }}
      >
        {t("collectionsPage.filters.activeLabel", "Active")}
      </Typography>
      {chips}
      {chips.length > 1 && (
        <Chip
          label={t("collectionsPage.filters.clearAll", "Clear all")}
          size="small"
          onClick={onClearAll}
          variant="outlined"
          sx={{
            height: 22,
            fontSize: "0.6875rem",
            color: "text.secondary",
            borderColor: alpha(theme.palette.divider, 0.3),
            cursor: "pointer",
            "&:hover": {
              borderColor: "error.main",
              color: "error.main",
            },
          }}
        />
      )}
    </Box>
  );
};

const chipSx = (theme: any) => ({
  height: 22,
  fontSize: "0.6875rem",
  fontWeight: 500,
  bgcolor: alpha(theme.palette.primary.main, 0.08),
  color: "primary.main",
  "& .MuiChip-deleteIcon": {
    fontSize: 14,
    color: alpha(theme.palette.primary.main, 0.6),
    "&:hover": { color: theme.palette.primary.main },
  },
});

export default ActiveFilterChips;
