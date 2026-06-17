import React, { useCallback, useMemo, useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Divider,
  FormControlLabel,
  FormGroup,
  Menu,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import {
  KeyboardArrowDown as KeyboardArrowDownIcon,
  Tune as TuneIcon,
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
  PhotoSizeSelectSmall as PhotoSizeSelectSmallIcon,
  ViewModule as ViewModuleIcon,
  PhotoSizeSelectLarge as PhotoSizeSelectLargeIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import type {
  CollectionCardDisplayPrefs,
  CollectionCardPreset,
  CollectionCardSize,
  CollectionCoreFieldId,
} from "../../hooks/useCollectionViewPreferences";

const PRESETS: Array<{
  id: Exclude<CollectionCardPreset, "custom">;
  labelKey: string;
  fallback: string;
  descKey: string;
  descFallback: string;
}> = [
  {
    id: "full",
    labelKey: "collectionsPage.cardView.preset.full",
    fallback: "Full",
    descKey: "collectionsPage.cardView.preset.fullDesc",
    descFallback: "All metadata, tags, description",
  },
  {
    id: "rich",
    labelKey: "collectionsPage.cardView.preset.rich",
    fallback: "Rich",
    descKey: "collectionsPage.cardView.preset.richDesc",
    descFallback: "Top metadata, tags, description",
  },
  {
    id: "compact",
    labelKey: "collectionsPage.cardView.preset.compact",
    fallback: "Compact",
    descKey: "collectionsPage.cardView.preset.compactDesc",
    descFallback: "Tags and description only",
  },
  {
    id: "minimal",
    labelKey: "collectionsPage.cardView.preset.minimal",
    fallback: "Minimal",
    descKey: "collectionsPage.cardView.preset.minimalDesc",
    descFallback: "Image and name only",
  },
];

const CORE_FIELDS: Array<{
  id: CollectionCoreFieldId;
  labelKey: string;
  fallback: string;
}> = [
  {
    id: "description",
    labelKey: "collectionsPage.cardView.fields.description",
    fallback: "Description",
  },
  {
    id: "tags",
    labelKey: "collectionsPage.cardView.fields.tags",
    fallback: "Tags",
  },
  {
    id: "meta",
    labelKey: "collectionsPage.cardView.fields.meta",
    fallback: "Item count & updated date",
  },
  {
    id: "visibility",
    labelKey: "collectionsPage.cardView.fields.visibility",
    fallback: "Visibility badge",
  },
  {
    id: "parentBreadcrumb",
    labelKey: "collectionsPage.cardView.fields.parentBreadcrumb",
    fallback: "Parent breadcrumb (search results)",
  },
];

export interface CollectionCardViewControlsProps {
  prefs: CollectionCardDisplayPrefs;
  onPresetChange: (preset: Exclude<CollectionCardPreset, "custom">) => void;
  onCardSizeChange: (size: CollectionCardSize) => void;
  onCoreFieldToggle: (field: CollectionCoreFieldId) => void;
  onMetadataKeyToggle: (key: string) => void;
  /** Full list of available customMetadata keys for this tenant. */
  availableMetadataKeys: string[];
}

/**
 * Toolbar trigger + popover that controls how cards render on the Collections
 * page. Siblings with `CollectionViewControls`' Sort and Filters popovers —
 * same styling vocabulary, same trigger size.
 *
 * Three sections in the popover:
 *   1. Preset — 4-up segmented pill (Full / Rich / Compact / Minimal).
 *   2. Card size — 3-up segmented pill (S / M / L).
 *   3. Customize fields — expandable checkbox list for core fields + custom
 *      metadata keys. Picks from `availableMetadataKeys` (fed from the existing
 *      `/collections/metadata-keys` endpoint — no new backend work).
 */
export const CollectionCardViewControls: React.FC<CollectionCardViewControlsProps> = ({
  prefs,
  onPresetChange,
  onCardSizeChange,
  onCoreFieldToggle,
  onMetadataKeyToggle,
  availableMetadataKeys,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [customizeOpen, setCustomizeOpen] = useState(false);

  const open = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => setAnchor(e.currentTarget),
    []
  );
  const close = useCallback(() => setAnchor(null), []);

  const presetLabel = useMemo(() => {
    if (prefs.preset === "custom") {
      return t("collectionsPage.cardView.preset.custom", "Custom");
    }
    const entry = PRESETS.find((p) => p.id === prefs.preset);
    return entry ? t(entry.labelKey, entry.fallback) : prefs.preset;
  }, [prefs.preset, t]);

  const selectedCoreCount = CORE_FIELDS.reduce(
    (acc, f) => acc + (getCoreFieldValue(prefs, f.id) ? 1 : 0),
    0
  );
  const customizeSummary = t(
    "collectionsPage.cardView.customizeSummary",
    "{{selected}} of {{total}} fields",
    {
      selected: selectedCoreCount + prefs.visibleMetadataKeys.length,
      total: CORE_FIELDS.length + availableMetadataKeys.length,
    }
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

  const segmentedToggleSx = {
    "& .MuiToggleButton-root": {
      flex: 1,
      borderRadius: "8px",
      py: 0.625,
      fontSize: "0.75rem",
      fontWeight: 500,
      textTransform: "none" as const,
      gap: 0.5,
      "&.Mui-selected": {
        bgcolor: alpha(theme.palette.primary.main, 0.1),
        color: "primary.main",
        borderColor: alpha(theme.palette.primary.main, 0.3),
        "&:hover": {
          bgcolor: alpha(theme.palette.primary.main, 0.15),
        },
      },
    },
    "& .MuiToggleButtonGroup-grouped:not(:first-of-type)": {
      ml: 0.5,
      borderLeft: "1px solid transparent",
    },
  };

  // Preset pill is visually active when the user has explicitly changed away
  // from the default `rich` preset OR picked a non-default size — mirrors how
  // the Sort trigger highlights only when state differs from default.
  const isPrefsNonDefault = prefs.preset !== "rich" || prefs.cardSize !== "medium";

  return (
    <>
      <Button
        size="small"
        startIcon={<TuneIcon />}
        endIcon={<KeyboardArrowDownIcon />}
        onClick={open}
        aria-haspopup="true"
        aria-expanded={Boolean(anchor)}
        sx={triggerSx(Boolean(anchor), isPrefsNonDefault)}
      >
        {isPrefsNonDefault ? (
          <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            {t("collectionsPage.cardView.viewTrigger", "View")}:
            <Box component="span" sx={{ color: "primary.main", fontWeight: 600 }}>
              {presetLabel}
            </Box>
          </Box>
        ) : (
          t("collectionsPage.cardView.viewTrigger", "View")
        )}
      </Button>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={close}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{
          paper: {
            elevation: 3,
            sx: {
              mt: 0.5,
              minWidth: 320,
              borderRadius: 1.5,
              border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            },
          },
        }}
      >
        <Box sx={{ p: 2 }}>
          {/* Preset */}
          <SectionLabel>{t("collectionsPage.cardView.presetLabel", "Preset")}</SectionLabel>
          <ToggleButtonGroup
            value={prefs.preset}
            exclusive
            size="small"
            fullWidth
            aria-label="Card preset"
            onChange={(_, val: CollectionCardPreset | null) => {
              if (val && val !== "custom") onPresetChange(val);
            }}
            sx={{ ...segmentedToggleSx, mb: 0.5 }}
          >
            {PRESETS.map((p) => (
              <ToggleButton key={p.id} value={p.id} aria-label={t(p.labelKey, p.fallback)}>
                <Tooltip title={t(p.descKey, p.descFallback)}>
                  <Box component="span">{t(p.labelKey, p.fallback)}</Box>
                </Tooltip>
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          {prefs.preset === "custom" && (
            <Typography
              variant="caption"
              sx={{
                display: "block",
                fontSize: "0.65rem",
                color: "text.disabled",
                fontStyle: "italic",
                mb: 1,
              }}
            >
              {t("collectionsPage.cardView.customHint", "Custom fields selected below")}
            </Typography>
          )}

          <Divider sx={{ my: 1.5, borderColor: alpha(theme.palette.divider, 0.5) }} />

          {/* Card size */}
          <SectionLabel>{t("collectionsPage.cardView.cardSize", "Card size")}</SectionLabel>
          <ToggleButtonGroup
            value={prefs.cardSize}
            exclusive
            size="small"
            fullWidth
            aria-label="Card size"
            onChange={(_, val: CollectionCardSize | null) => {
              if (val) onCardSizeChange(val);
            }}
            sx={segmentedToggleSx}
          >
            <ToggleButton value="small" aria-label={t("collectionsPage.cardView.small", "Small")}>
              <PhotoSizeSelectSmallIcon sx={{ fontSize: "0.875rem" }} />
              {t("collectionsPage.cardView.small", "Small")}
            </ToggleButton>
            <ToggleButton
              value="medium"
              aria-label={t("collectionsPage.cardView.medium", "Medium")}
            >
              <ViewModuleIcon sx={{ fontSize: "0.875rem" }} />
              {t("collectionsPage.cardView.medium", "Medium")}
            </ToggleButton>
            <ToggleButton value="large" aria-label={t("collectionsPage.cardView.large", "Large")}>
              <PhotoSizeSelectLargeIcon sx={{ fontSize: "0.875rem" }} />
              {t("collectionsPage.cardView.large", "Large")}
            </ToggleButton>
          </ToggleButtonGroup>

          <Divider sx={{ my: 1.5, borderColor: alpha(theme.palette.divider, 0.5) }} />

          {/* Customize fields (collapsed summary -> expanded list) */}
          <Box
            onClick={() => setCustomizeOpen((o) => !o)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setCustomizeOpen((o) => !o);
              }
            }}
            role="button"
            tabIndex={0}
            aria-expanded={customizeOpen}
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              userSelect: "none",
              py: 0.5,
              "&:hover .customize-label": { color: "text.primary" },
            }}
          >
            <Box sx={{ display: "flex", flexDirection: "column" }}>
              <Typography
                variant="overline"
                className="customize-label"
                sx={{
                  fontSize: "0.625rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: "text.secondary",
                  lineHeight: 1.2,
                }}
              >
                {t("collectionsPage.cardView.customizeFields", "Customize fields")}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontSize: "0.7rem",
                  color: "text.disabled",
                }}
              >
                {customizeSummary}
              </Typography>
            </Box>
            {customizeOpen ? (
              <ExpandLessIcon sx={{ fontSize: 18, color: "text.secondary" }} />
            ) : (
              <ExpandMoreIcon sx={{ fontSize: 18, color: "text.secondary" }} />
            )}
          </Box>

          {customizeOpen && (
            <Box sx={{ mt: 1 }}>
              {/* Core fields */}
              <SectionLabel>{t("collectionsPage.cardView.coreFields", "Core fields")}</SectionLabel>
              <FormGroup sx={{ gap: 0 }}>
                {CORE_FIELDS.map((field) => {
                  const checked = getCoreFieldValue(prefs, field.id);
                  return (
                    <FormControlLabel
                      key={field.id}
                      control={
                        <Checkbox
                          checked={checked}
                          onChange={() => onCoreFieldToggle(field.id)}
                          size="small"
                          sx={{
                            py: 0.25,
                            color: "text.secondary",
                            "&.Mui-checked": { color: "primary.main" },
                          }}
                        />
                      }
                      label={
                        <Typography
                          variant="body2"
                          sx={{
                            fontSize: "0.8125rem",
                            fontWeight: checked ? 500 : 400,
                            color: checked ? "text.primary" : "text.secondary",
                          }}
                        >
                          {t(field.labelKey, field.fallback)}
                        </Typography>
                      }
                      sx={{ mx: 0, my: -0.25 }}
                    />
                  );
                })}
              </FormGroup>

              {/* Custom metadata keys */}
              {availableMetadataKeys.length > 0 && (
                <>
                  <Divider
                    sx={{
                      my: 1,
                      borderColor: alpha(theme.palette.divider, 0.5),
                    }}
                  />
                  <SectionLabel>
                    {t("collectionsPage.cardView.customMetadata", "Custom metadata")}
                  </SectionLabel>
                  <FormGroup sx={{ gap: 0, maxHeight: 240, overflowY: "auto" }}>
                    {availableMetadataKeys.map((key) => {
                      const checked = prefs.visibleMetadataKeys.includes(key);
                      return (
                        <FormControlLabel
                          key={key}
                          control={
                            <Checkbox
                              checked={checked}
                              onChange={() => onMetadataKeyToggle(key)}
                              size="small"
                              sx={{
                                py: 0.25,
                                color: "text.secondary",
                                "&.Mui-checked": { color: "primary.main" },
                              }}
                            />
                          }
                          label={
                            <Typography
                              variant="body2"
                              sx={{
                                fontFamily:
                                  'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
                                fontSize: "0.78rem",
                                fontWeight: checked ? 500 : 400,
                                color: checked ? "text.primary" : "text.secondary",
                              }}
                            >
                              {key}
                            </Typography>
                          }
                          sx={{ mx: 0, my: -0.25 }}
                        />
                      );
                    })}
                  </FormGroup>
                </>
              )}
            </Box>
          )}
        </Box>
      </Menu>
    </>
  );
};

function getCoreFieldValue(
  prefs: CollectionCardDisplayPrefs,
  field: CollectionCoreFieldId
): boolean {
  switch (field) {
    case "description":
      return prefs.showDescription;
    case "tags":
      return prefs.showTags;
    case "meta":
      return prefs.showMeta;
    case "visibility":
      return prefs.showVisibility;
    case "parentBreadcrumb":
      return prefs.showParentBreadcrumb;
  }
}

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Typography
    variant="overline"
    sx={{
      display: "block",
      fontSize: "0.625rem",
      fontWeight: 700,
      letterSpacing: "0.08em",
      color: "text.disabled",
      mb: 0.75,
    }}
  >
    {children}
  </Typography>
);

export default CollectionCardViewControls;
