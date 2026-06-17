import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Box,
  Popover,
  Typography,
  IconButton,
  Button,
  Checkbox,
  FormControlLabel,
  Select,
  MenuItem,
  TextField,
  Divider,
  Chip,
  Collapse,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Close as CloseIcon,
  Public as PublicIcon,
  Label as LabelIcon,
  Category as CategoryIcon,
  DateRange as DateRangeIcon,
  Add as AddIcon,
  DeleteOutline as DeleteOutlineIcon,
  Tune as TuneIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

export type CollectionVisibility = "public" | "shared" | "private";
export type UpdatedWithin = "24h" | "7d" | "30d" | null;

export interface MetadataKVFilter {
  id: string;
  key: string;
  value: string;
}

export interface CollectionFilterState {
  visibility: CollectionVisibility[];
  collectionTypeIds: string[];
  tags: string[];
  metadataFilters: MetadataKVFilter[];
  updatedWithin: UpdatedWithin;
}

export const EMPTY_FILTER_STATE: CollectionFilterState = {
  visibility: [],
  collectionTypeIds: [],
  tags: [],
  metadataFilters: [],
  updatedWithin: null,
};

export interface CollectionFilterDrawerProps {
  /**
   * The DOM element to anchor the popover to. When null/undefined the popover is
   * closed. When set, the popover opens anchored to that element.
   */
  anchorEl?: HTMLElement | null;
  onClose: () => void;
  /** Currently-applied filters — popover loads them into its draft on open */
  applied: CollectionFilterState;
  /** Called with the new filter state when the user hits Apply */
  onApply: (state: CollectionFilterState) => void;
  /** Available collection types (for the "Collection type" section) */
  availableCollectionTypes: Array<{ id: string; name: string }>;
  /** Available tag values (for the "Tags" section) */
  availableTags: string[];
  /** Available custom-metadata keys (for the "Custom metadata" section key dropdown) */
  availableMetadataKeys: string[];
}

/**
 * Count the number of active filters for the "N active" label in the header.
 * Metadata K/V rows only count when both key and value are non-empty.
 */
export const countActiveFilters = (state: CollectionFilterState): number => {
  let n = 0;
  n += state.visibility.length;
  n += state.collectionTypeIds.length;
  n += state.tags.length;
  n += state.metadataFilters.filter((f) => f.key.trim() && f.value.trim()).length;
  if (state.updatedWithin) n += 1;
  return n;
};

type SectionId = "visibility" | "collectionType" | "tags" | "customMetadata" | "updated";

/**
 * Compact filter popover anchored to the Filters toolbar button. Matches the
 * Sort popover's size and interaction pattern so the toolbar reads as two
 * equivalent trigger buttons rather than one button + a full-page drawer.
 *
 * Sections collapse individually (click the header) so users can drill into
 * the one they care about without scrolling through all five. The popover is
 * a draft surface — clicks only mutate local state; the parent's filter state
 * is updated when the user presses Apply. Reset and Close discard the draft.
 */
export const CollectionFilterDrawer: React.FC<CollectionFilterDrawerProps> = ({
  anchorEl,
  onClose,
  applied,
  onApply,
  availableCollectionTypes,
  availableTags,
  availableMetadataKeys,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const open = Boolean(anchorEl);

  // Local draft state — seeded from `applied` whenever the popover opens so a
  // cancel-then-reopen sequence always restarts from what's currently applied.
  const [draft, setDraft] = useState<CollectionFilterState>(applied);

  // Collapse state — `visibility` stays open by default (most common use case);
  // other sections expand as the user needs them.
  const [expanded, setExpanded] = useState<Record<SectionId, boolean>>({
    visibility: true,
    collectionType: false,
    tags: false,
    customMetadata: false,
    updated: false,
  });

  useEffect(() => {
    if (open) {
      setDraft(applied);
    }
  }, [open, applied]);

  const toggleInList = <T,>(list: T[], value: T): T[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const toggleSection = useCallback(
    (id: SectionId) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] })),
    []
  );

  const handleVisibilityToggle = useCallback(
    (v: CollectionVisibility) =>
      setDraft((d) => ({ ...d, visibility: toggleInList(d.visibility, v) })),
    []
  );

  const handleTypeToggle = useCallback(
    (id: string) =>
      setDraft((d) => ({
        ...d,
        collectionTypeIds: toggleInList(d.collectionTypeIds, id),
      })),
    []
  );

  const handleTagToggle = useCallback(
    (tag: string) => setDraft((d) => ({ ...d, tags: toggleInList(d.tags, tag) })),
    []
  );

  const handleUpdatedWithin = useCallback(
    (value: UpdatedWithin) =>
      setDraft((d) => ({
        ...d,
        updatedWithin: d.updatedWithin === value ? null : value,
      })),
    []
  );

  const handleMetadataRowUpdate = useCallback(
    (id: string, patch: Partial<MetadataKVFilter>) =>
      setDraft((d) => ({
        ...d,
        metadataFilters: d.metadataFilters.map((f) => (f.id === id ? { ...f, ...patch } : f)),
      })),
    []
  );

  const handleMetadataRowRemove = useCallback(
    (id: string) =>
      setDraft((d) => ({
        ...d,
        metadataFilters: d.metadataFilters.filter((f) => f.id !== id),
      })),
    []
  );

  const handleMetadataRowAdd = useCallback(
    () =>
      setDraft((d) => ({
        ...d,
        metadataFilters: [
          ...d.metadataFilters,
          {
            id: `mk-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            key: "",
            value: "",
          },
        ],
      })),
    []
  );

  const handleReset = useCallback(() => setDraft(EMPTY_FILTER_STATE), []);
  const handleApply = useCallback(() => {
    const pruned: CollectionFilterState = {
      ...draft,
      metadataFilters: draft.metadataFilters.filter((f) => f.key.trim() && f.value.trim()),
    };
    onApply(pruned);
    onClose();
  }, [draft, onApply, onClose]);

  const draftActiveCount = useMemo(() => countActiveFilters(draft), [draft]);

  // ---- helpers ----

  const renderSectionHeader = (
    id: SectionId,
    label: string,
    icon: React.ReactNode,
    count: number
  ) => {
    const isOpen = expanded[id];
    return (
      <Box
        onClick={() => toggleSection(id)}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          py: 0.75,
          px: 0.5,
          borderRadius: 1,
          userSelect: "none",
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.04) },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.75,
            fontSize: "0.6875rem",
            fontWeight: 700,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: isOpen ? "primary.main" : "text.secondary",
          }}
        >
          {icon}
          {label}
          {count > 0 && (
            <Chip
              size="small"
              label={count}
              sx={{
                height: 16,
                minWidth: 16,
                ml: 0.25,
                fontSize: "0.6rem",
                fontWeight: 700,
                bgcolor: alpha(theme.palette.primary.main, 0.12),
                color: "primary.main",
                "& .MuiChip-label": { px: 0.5 },
              }}
            />
          )}
        </Box>
        {isOpen ? (
          <ExpandLessIcon sx={{ fontSize: 16, color: "text.disabled" }} />
        ) : (
          <ExpandMoreIcon sx={{ fontSize: 16, color: "text.disabled" }} />
        )}
      </Box>
    );
  };

  const renderCheckboxRow = (label: string, checked: boolean, onChange: () => void) => (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        px: 0.5,
        py: 0.1,
        borderRadius: 1,
        cursor: "pointer",
        "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.06) },
      }}
      onClick={onChange}
    >
      <FormControlLabel
        control={
          <Checkbox
            size="small"
            checked={checked}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => e.stopPropagation()}
            sx={{ py: 0.25 }}
          />
        }
        label={
          <Typography variant="body2" sx={{ fontSize: "0.8125rem" }}>
            {label}
          </Typography>
        }
        sx={{ m: 0 }}
      />
    </Box>
  );

  // Scrollable inner area so long lists don't blow out the popover
  const scrollAreaSx = {
    maxHeight: 220,
    overflowY: "auto" as const,
    pr: 0.5,
  };

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      transformOrigin={{ vertical: "top", horizontal: "right" }}
      slotProps={{
        paper: {
          elevation: 4,
          sx: {
            mt: 0.5,
            width: 340,
            maxHeight: "min(640px, calc(100vh - 120px))",
            display: "flex",
            flexDirection: "column",
            borderRadius: 1.5,
            border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            overflow: "hidden",
          },
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1.5,
          py: 1,
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          bgcolor: alpha(theme.palette.text.primary, 0.015),
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.75,
          }}
        >
          <Typography
            sx={{
              fontSize: "0.8125rem",
              fontWeight: 700,
              letterSpacing: "-0.01em",
            }}
          >
            {t("collectionsPage.filters.drawerTitle", "Filter collections")}
          </Typography>
          {draftActiveCount > 0 && (
            <Chip
              size="small"
              label={t("collectionsPage.filters.activeCount", "{{count}} active", {
                count: draftActiveCount,
              })}
              sx={{
                height: 18,
                fontSize: "0.65rem",
                fontWeight: 600,
                bgcolor: alpha(theme.palette.primary.main, 0.1),
                color: "primary.main",
                "& .MuiChip-label": { px: 0.75 },
              }}
            />
          )}
        </Box>
        <IconButton
          size="small"
          onClick={onClose}
          aria-label={t("common.close", "Close")}
          sx={{ p: 0.25 }}
        >
          <CloseIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Box>

      {/* Body */}
      <Box sx={{ flex: 1, overflowY: "auto", px: 1.5, py: 1 }}>
        {/* Visibility */}
        {renderSectionHeader(
          "visibility",
          t("collectionsPage.filters.visibility", "Visibility"),
          <PublicIcon sx={{ fontSize: 13 }} />,
          draft.visibility.length
        )}
        <Collapse in={expanded.visibility} unmountOnExit>
          <Box sx={{ pl: 0.5, pb: 0.5 }}>
            {renderCheckboxRow(
              t("collectionsPage.labels.public", "Public"),
              draft.visibility.includes("public"),
              () => handleVisibilityToggle("public")
            )}
            {renderCheckboxRow(
              t("collectionsPage.filters.sharedWithMe", "Shared with me"),
              draft.visibility.includes("shared"),
              () => handleVisibilityToggle("shared")
            )}
            {renderCheckboxRow(
              t("collectionsPage.labels.private", "Private"),
              draft.visibility.includes("private"),
              () => handleVisibilityToggle("private")
            )}
          </Box>
        </Collapse>

        {/* Collection type */}
        {availableCollectionTypes.length > 0 && (
          <>
            <Divider sx={{ my: 0.5, borderColor: alpha(theme.palette.divider, 0.5) }} />
            {renderSectionHeader(
              "collectionType",
              t("collectionsPage.filters.collectionType", "Collection type"),
              <CategoryIcon sx={{ fontSize: 13 }} />,
              draft.collectionTypeIds.length
            )}
            <Collapse in={expanded.collectionType} unmountOnExit>
              <Box sx={{ pl: 0.5, pb: 0.5, ...scrollAreaSx }}>
                {availableCollectionTypes.map((type) =>
                  renderCheckboxRow(type.name, draft.collectionTypeIds.includes(type.id), () =>
                    handleTypeToggle(type.id)
                  )
                )}
              </Box>
            </Collapse>
          </>
        )}

        {/* Tags */}
        {availableTags.length > 0 && (
          <>
            <Divider sx={{ my: 0.5, borderColor: alpha(theme.palette.divider, 0.5) }} />
            {renderSectionHeader(
              "tags",
              t("collectionsPage.filters.tags", "Tags"),
              <LabelIcon sx={{ fontSize: 13 }} />,
              draft.tags.length
            )}
            <Collapse in={expanded.tags} unmountOnExit>
              <Box sx={{ pl: 0.5, pb: 0.5, ...scrollAreaSx }}>
                {availableTags
                  .slice(0, 50)
                  .map((tag) =>
                    renderCheckboxRow(tag, draft.tags.includes(tag), () => handleTagToggle(tag))
                  )}
              </Box>
            </Collapse>
          </>
        )}

        {/* Custom metadata */}
        <Divider sx={{ my: 0.5, borderColor: alpha(theme.palette.divider, 0.5) }} />
        {renderSectionHeader(
          "customMetadata",
          t("collectionsPage.filters.customMetadata", "Custom metadata"),
          <TuneIcon sx={{ fontSize: 13 }} />,
          draft.metadataFilters.filter((f) => f.key.trim() && f.value.trim()).length
        )}
        <Collapse in={expanded.customMetadata} unmountOnExit>
          <Box sx={{ pl: 0.5, pb: 0.5, pt: 0.5 }}>
            {draft.metadataFilters.map((filter) => (
              <Box
                key={filter.id}
                sx={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1.3fr 24px",
                  gap: 0.6,
                  mb: 0.6,
                  alignItems: "center",
                }}
              >
                <Select
                  size="small"
                  value={filter.key}
                  displayEmpty
                  onChange={(e) =>
                    handleMetadataRowUpdate(filter.id, {
                      key: e.target.value as string,
                    })
                  }
                  sx={{ fontSize: "0.75rem", "& .MuiSelect-select": { py: 0.5 } }}
                >
                  <MenuItem value="" disabled>
                    <em>{t("collectionsPage.filters.selectKey", "Select key\u2026")}</em>
                  </MenuItem>
                  {availableMetadataKeys.map((key) => (
                    <MenuItem key={key} value={key}>
                      {key}
                    </MenuItem>
                  ))}
                </Select>
                <TextField
                  size="small"
                  value={filter.value}
                  onChange={(e) => handleMetadataRowUpdate(filter.id, { value: e.target.value })}
                  placeholder={t("collectionsPage.filters.valuePlaceholder", "value")}
                  inputProps={{
                    style: { fontSize: "0.75rem", padding: "6px 8px" },
                  }}
                />
                <IconButton
                  size="small"
                  onClick={() => handleMetadataRowRemove(filter.id)}
                  aria-label={t("common.remove", "Remove")}
                  sx={{ p: 0.25, color: "text.disabled" }}
                >
                  <DeleteOutlineIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Box>
            ))}
            <Button
              size="small"
              startIcon={<AddIcon sx={{ fontSize: 14 }} />}
              onClick={handleMetadataRowAdd}
              variant="outlined"
              sx={{
                mt: 0.25,
                textTransform: "none",
                fontSize: "0.7rem",
                borderStyle: "dashed",
                color: "text.secondary",
                borderColor: alpha(theme.palette.divider, 0.3),
                py: 0.25,
                "&:hover": {
                  borderStyle: "dashed",
                  borderColor: "primary.main",
                  color: "primary.main",
                },
              }}
            >
              {t("collectionsPage.filters.addMetadata", "Add metadata filter")}
            </Button>
          </Box>
        </Collapse>

        {/* Updated */}
        <Divider sx={{ my: 0.5, borderColor: alpha(theme.palette.divider, 0.5) }} />
        {renderSectionHeader(
          "updated",
          t("collectionsPage.filters.updated", "Updated"),
          <DateRangeIcon sx={{ fontSize: 13 }} />,
          draft.updatedWithin ? 1 : 0
        )}
        <Collapse in={expanded.updated} unmountOnExit>
          <Box sx={{ pl: 0.5, pb: 0.5 }}>
            {(
              [
                ["24h", t("collectionsPage.filters.last24h", "Last 24 hours")],
                ["7d", t("collectionsPage.filters.last7d", "Last 7 days")],
                ["30d", t("collectionsPage.filters.last30d", "Last 30 days")],
              ] as const
            ).map(([value, label]) =>
              renderCheckboxRow(label, draft.updatedWithin === value, () =>
                handleUpdatedWithin(value as UpdatedWithin)
              )
            )}
          </Box>
        </Collapse>
      </Box>

      {/* Footer */}
      <Box
        sx={{
          display: "flex",
          gap: 1,
          justifyContent: "flex-end",
          px: 1.5,
          py: 1,
          borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          bgcolor: alpha(theme.palette.text.primary, 0.015),
        }}
      >
        <Button
          size="small"
          onClick={handleReset}
          sx={{
            textTransform: "none",
            color: "text.secondary",
            fontSize: "0.75rem",
          }}
        >
          {t("collectionsPage.filters.reset", "Reset all")}
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={handleApply}
          sx={{ textTransform: "none", fontSize: "0.75rem" }}
        >
          {t("collectionsPage.filters.apply", "Apply")}
        </Button>
      </Box>
    </Popover>
  );
};

export default CollectionFilterDrawer;
