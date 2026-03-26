import React from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Button,
  ToggleButtonGroup,
  ToggleButton,
  Menu,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Switch,
  Tooltip,
  Divider,
  Chip,
  IconButton,
  alpha,
  Badge,
} from "@mui/material";

import ViewModuleIcon from "@mui/icons-material/ViewModule";
import ViewListIcon from "@mui/icons-material/ViewList";
import ViewColumnIcon from "@mui/icons-material/ViewColumn";
import SortIcon from "@mui/icons-material/Sort";
import TuneIcon from "@mui/icons-material/Tune";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import CropPortraitIcon from "@mui/icons-material/CropPortrait";
import CropSquareIcon from "@mui/icons-material/CropSquare";
import CropLandscapeIcon from "@mui/icons-material/CropLandscape";
import PhotoSizeSelectSmallIcon from "@mui/icons-material/PhotoSizeSelectSmall";
import PhotoSizeSelectLargeIcon from "@mui/icons-material/PhotoSizeSelectLarge";
import FitScreenIcon from "@mui/icons-material/FitScreen";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ClearIcon from "@mui/icons-material/Clear";
import SortByAlphaIcon from "@mui/icons-material/SortByAlpha";
import {
  type CardSize,
  type AspectRatio,
  type AssetViewControlsProps as BaseAssetViewControlsProps,
} from "../../types/shared/assetComponents";
import { type FieldInfo } from "@/api/hooks/useSearchFields";

// ─── Shared styles ───

interface AssetViewControlsProps extends BaseAssetViewControlsProps {
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  cardSize: CardSize;
  onCardSizeChange: (size: CardSize) => void;
  aspectRatio: AspectRatio;
  onAspectRatioChange: (ratio: AspectRatio) => void;
  thumbnailScale: "fit" | "fill";
  onThumbnailScaleChange: (scale: "fit" | "fill") => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
  hasSelectedAssets?: boolean;
  selectAllState?: "none" | "some" | "all";
  onSelectAllToggle?: () => void;
  // Metadata field selection (from useMetadataFieldPreferences)
  availableFields?: FieldInfo[];
  selectedSearchFields?: string[];
  onSelectedFieldsChange?: (fields: string[]) => void;
}

/** Trigger button styling — adapts to open/active state */
const triggerButtonSx = (isOpen: boolean, isActive: boolean) => ({
  textTransform: "none" as const,
  borderRadius: "8px",
  px: 1.5,
  py: 0.5,
  fontSize: "0.8125rem",
  fontWeight: 500,
  color: isActive ? "primary.main" : "text.secondary",
  bgcolor: isOpen ? (theme: any) => alpha(theme.palette.primary.main, 0.08) : "transparent",
  border: "1px solid",
  borderColor: isActive ? (theme: any) => alpha(theme.palette.primary.main, 0.3) : "transparent",
  transition: "all 0.15s ease",
  "&:hover": {
    bgcolor: (theme: any) => alpha(theme.palette.primary.main, 0.06),
    borderColor: (theme: any) => alpha(theme.palette.primary.main, 0.2),
  },
  "& .MuiButton-startIcon": {
    mr: 0.5,
    "& .MuiSvgIcon-root": { fontSize: "1rem" },
  },
  "& .MuiButton-endIcon": {
    ml: 0.25,
    "& .MuiSvgIcon-root": {
      fontSize: "0.875rem",
      transition: "transform 0.2s ease",
      transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
    },
  },
});

/** Shared ToggleButtonGroup styling for pill-style segmented controls */
const segmentedToggleSx = {
  "& .MuiToggleButton-root": {
    flex: 1,
    borderRadius: "8px",
    py: 0.625,
    fontSize: "0.75rem",
    fontWeight: 500,
    textTransform: "none",
    gap: 0.5,
    "&.Mui-selected": {
      bgcolor: (theme: any) => alpha(theme.palette.primary.main, 0.1),
      color: "primary.main",
      borderColor: (theme: any) => alpha(theme.palette.primary.main, 0.3),
      "&:hover": {
        bgcolor: (theme: any) => alpha(theme.palette.primary.main, 0.15),
      },
    },
  },
  "& .MuiToggleButtonGroup-grouped:not(:first-of-type)": {
    ml: 0.5,
    borderLeft: "1px solid",
    borderColor: "divider",
    borderRadius: "8px",
  },
  "& .MuiToggleButtonGroup-grouped:first-of-type": {
    borderRadius: "8px",
  },
};

/** Shared popover paper styling */
const popoverPaperSx = (minWidth: number) => ({
  mt: 0.75,
  borderRadius: "12px",
  minWidth,
  boxShadow: (theme: any) =>
    theme.palette.mode === "dark" ? "0 8px 32px rgba(0,0,0,0.5)" : "0 8px 32px rgba(0,0,0,0.1)",
  border: "1px solid",
  borderColor: "divider",
});

// ─── Sub-components ───

/** Panel header with optional right-side action */
const PanelHeader: React.FC<{ title: string; action?: React.ReactNode }> = ({ title, action }) => (
  <Box
    sx={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      mb: 1.5,
    }}
  >
    <Typography
      variant="overline"
      sx={{
        fontSize: "0.6875rem",
        fontWeight: 700,
        letterSpacing: "0.08em",
        color: "text.secondary",
      }}
    >
      {title}
    </Typography>
    {action}
  </Box>
);

/** Section label inside panels */
const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Typography
    variant="caption"
    sx={{
      display: "block",
      fontSize: "0.6875rem",
      fontWeight: 600,
      color: "text.secondary",
      mb: 0.75,
      mt: 0.5,
      letterSpacing: "0.02em",
    }}
  >
    {children}
  </Typography>
);

/** Clickable text action (e.g. "Select all", "Show all") */
const TextAction: React.FC<{ label: string; onClick: () => void }> = ({ label, onClick }) => (
  <Typography
    component="button"
    variant="caption"
    onClick={onClick}
    sx={{
      fontSize: "0.6875rem",
      color: "primary.main",
      cursor: "pointer",
      fontWeight: 600,
      background: "none",
      border: "none",
      padding: 0,
      "&:hover": { textDecoration: "underline" },
      "&:focus-visible": {
        outline: "2px solid",
        outlineColor: "primary.main",
        outlineOffset: 2,
        borderRadius: "2px",
      },
    }}
  >
    {label}
  </Typography>
);

// ─── Main component ───

const AssetViewControls: React.FC<AssetViewControlsProps> = ({
  viewMode,
  onViewModeChange,
  sorting,
  sortOptions,
  onSortChange,
  fields,
  onFieldToggle,
  groupByType,
  onGroupByTypeChange,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange,
  selectAllState = "none",
  onSelectAllToggle,
  availableFields,
  selectedSearchFields,
  onSelectedFieldsChange,
}) => {
  const { t } = useTranslation();
  const [sortAnchor, setSortAnchor] = React.useState<null | HTMLElement>(null);
  const [fieldsAnchor, setFieldsAnchor] = React.useState<null | HTMLElement>(null);
  const [appearanceAnchor, setAppearanceAnchor] = React.useState<null | HTMLElement>(null);

  const handleSortClose = () => setSortAnchor(null);
  const handleFieldsClose = () => setFieldsAnchor(null);
  const handleAppearanceClose = () => setAppearanceAnchor(null);

  // Sort options — show all available sort options
  const filteredSortOptions = sortOptions;

  // ─── Derived active-state indicators ───

  const activeSortLabel = React.useMemo(() => {
    if (sorting.length === 0) return null;
    return filteredSortOptions.find((o) => o.id === sorting[0]?.id)?.label ?? null;
  }, [sorting, filteredSortOptions]);

  const hiddenFieldCount = React.useMemo(() => {
    if (availableFields && availableFields.length > 0 && selectedSearchFields) {
      return availableFields.filter((f) => !selectedSearchFields.includes(f.name)).length;
    }
    return fields.filter((f) => !f.visible).length;
  }, [fields, availableFields, selectedSearchFields]);

  const appearanceIsModified = React.useMemo(() => {
    if (groupByType) return true;
    if (viewMode === "card") {
      return (
        cardSize !== "medium" ||
        aspectRatio !== "square" ||
        thumbnailScale !== "fit" ||
        !showMetadata
      );
    }
    return false;
  }, [viewMode, cardSize, aspectRatio, thumbnailScale, showMetadata, groupByType]);

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        mb: 3,
      }}
    >
      {/* ─── Left: View toggle + Select all ─── */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={onViewModeChange}
          size="small"
          sx={{
            ...segmentedToggleSx,
            "& .MuiToggleButton-root": {
              ...segmentedToggleSx["& .MuiToggleButton-root"],
              px: 1,
              py: 0.5,
            },
          }}
        >
          <Tooltip title={t("common.views.cardView")}>
            <ToggleButton value="card" aria-label={t("common.views.cardView")}>
              <ViewModuleIcon sx={{ fontSize: "1.1rem" }} />
            </ToggleButton>
          </Tooltip>
          <Tooltip title={t("common.views.tableView")}>
            <ToggleButton value="table" aria-label={t("common.views.tableView")}>
              <ViewListIcon sx={{ fontSize: "1.1rem" }} />
            </ToggleButton>
          </Tooltip>
        </ToggleButtonGroup>

        <Divider
          orientation="vertical"
          flexItem
          sx={{ mx: 0.5, height: 24, alignSelf: "center" }}
        />

        <FormControlLabel
          control={
            <Checkbox
              checked={selectAllState === "all"}
              indeterminate={selectAllState === "some"}
              onChange={onSelectAllToggle}
              size="small"
              sx={{
                color: "text.secondary",
                "&.Mui-checked": { color: "primary.main" },
                "&.MuiCheckbox-indeterminate": { color: "primary.main" },
                "& .MuiSvgIcon-root": { fontSize: "1.1rem" },
              }}
            />
          }
          label={
            <Typography
              variant="body2"
              sx={{
                fontSize: "0.8125rem",
                color: "text.secondary",
                userSelect: "none",
              }}
            >
              {selectAllState === "all"
                ? t("common.viewControls.deselect")
                : t("common.viewControls.selectAll")}
            </Typography>
          }
          sx={{ margin: 0, ml: -0.25 }}
        />
      </Box>

      {/* ─── Right: Sort, Fields, Appearance ─── */}
      <Box sx={{ display: "flex", gap: 0.75, alignItems: "center" }}>
        {/* Sort — shows active sort inline */}
        <Button
          size="small"
          startIcon={<SortIcon />}
          endIcon={<KeyboardArrowDownIcon />}
          onClick={(e) => setSortAnchor(e.currentTarget)}
          aria-haspopup="true"
          aria-expanded={Boolean(sortAnchor)}
          sx={triggerButtonSx(Boolean(sortAnchor), Boolean(activeSortLabel))}
        >
          {activeSortLabel ? (
            <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              {t("common.viewControls.sort")}:
              <Box component="span" sx={{ color: "primary.main", fontWeight: 600 }}>
                {activeSortLabel}
              </Box>
              {sorting[0]?.desc ? (
                <ArrowDownwardIcon sx={{ fontSize: "0.75rem" }} />
              ) : (
                <ArrowUpwardIcon sx={{ fontSize: "0.75rem" }} />
              )}
            </Box>
          ) : (
            t("common.viewControls.sort")
          )}
        </Button>

        {/* Fields — badge shows hidden count */}
        <Badge
          badgeContent={hiddenFieldCount > 0 ? hiddenFieldCount : 0}
          color="primary"
          variant="standard"
          sx={{
            "& .MuiBadge-badge": {
              fontSize: "0.625rem",
              height: 16,
              minWidth: 16,
              top: 4,
              right: 4,
            },
          }}
        >
          <Button
            size="small"
            startIcon={<ViewColumnIcon />}
            endIcon={<KeyboardArrowDownIcon />}
            onClick={(e) => setFieldsAnchor(e.currentTarget)}
            aria-haspopup="true"
            aria-expanded={Boolean(fieldsAnchor)}
            sx={triggerButtonSx(Boolean(fieldsAnchor), hiddenFieldCount > 0)}
          >
            {t("common.viewControls.fields")}
          </Button>
        </Badge>

        {/* Appearance — dot when non-default */}
        <Badge
          variant="dot"
          invisible={!appearanceIsModified}
          color="primary"
          sx={{
            "& .MuiBadge-badge": {
              top: 6,
              right: 6,
              width: 7,
              height: 7,
              minWidth: 7,
            },
          }}
        >
          <Button
            size="small"
            startIcon={<TuneIcon />}
            endIcon={<KeyboardArrowDownIcon />}
            onClick={(e) => setAppearanceAnchor(e.currentTarget)}
            aria-haspopup="true"
            aria-expanded={Boolean(appearanceAnchor)}
            sx={triggerButtonSx(Boolean(appearanceAnchor), appearanceIsModified)}
          >
            {t("common.viewControls.appearance")}
          </Button>
        </Badge>
      </Box>

      {/* ═══ Sort Panel ═══ */}
      <Menu
        open={Boolean(sortAnchor)}
        anchorEl={sortAnchor}
        onClose={handleSortClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: { ...popoverPaperSx(280), maxHeight: 480 } } }}
      >
        <Box sx={{ p: 2 }}>
          <PanelHeader
            title={t("common.viewControls.sortBy")}
            action={
              sorting.length > 0 ? (
                <Tooltip title={t("common.viewControls.clearSort")}>
                  <IconButton
                    size="small"
                    aria-label={t("common.viewControls.clearSort")}
                    onClick={() => {
                      onSortChange("");
                      handleSortClose();
                    }}
                    sx={{
                      p: 0.25,
                      color: "text.secondary",
                      "&:hover": { color: "error.main" },
                    }}
                  >
                    <ClearIcon sx={{ fontSize: "0.875rem" }} />
                  </IconButton>
                </Tooltip>
              ) : undefined
            }
          />

          {filteredSortOptions.length === 0 ? (
            /* Empty state */
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                py: 2,
                gap: 0.75,
              }}
            >
              <SortByAlphaIcon sx={{ fontSize: "1.5rem", color: "text.disabled" }} />
              <Typography variant="caption" sx={{ color: "text.secondary", textAlign: "center" }}>
                {t("common.viewControls.noSortableFields")}
                <br />
                {t("common.viewControls.enableMoreFields")}
              </Typography>
            </Box>
          ) : (
            (() => {
              // Split sort options into standard (from columns) and custom (from metadata fields)
              const standardIds = new Set(
                (availableFields ?? []).filter((f) => f.isDefault).map((f) => f.name)
              );
              const standardOpts = filteredSortOptions.filter(
                (o) => !availableFields || standardIds.has(o.id) || !o.id.includes(".")
              );
              const customOpts = filteredSortOptions.filter(
                (o) => availableFields && !standardIds.has(o.id) && o.id.includes(".")
              );

              const renderSortItem = (option: { id: string; label: string }) => {
                const isActive = sorting[0]?.id === option.id;
                const isDesc = sorting[0]?.desc;
                return (
                  <Box
                    key={option.id}
                    role="option"
                    aria-selected={isActive}
                    tabIndex={0}
                    onClick={() => {
                      onSortChange(option.id);
                      handleSortClose();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSortChange(option.id);
                        handleSortClose();
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
                      bgcolor: isActive
                        ? (theme) => alpha(theme.palette.primary.main, 0.08)
                        : "transparent",
                      transition: "all 0.12s ease",
                      "&:hover, &:focus-visible": {
                        bgcolor: (theme) =>
                          isActive
                            ? alpha(theme.palette.primary.main, 0.12)
                            : alpha(theme.palette.primary.main, 0.04),
                        outline: "none",
                      },
                      "&:focus-visible": {
                        boxShadow: (theme) => `inset 0 0 0 2px ${theme.palette.primary.main}`,
                      },
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
                      {isActive && (
                        <CheckCircleIcon
                          sx={{ fontSize: "0.875rem", color: "primary.main", flexShrink: 0 }}
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
                      <Chip
                        size="small"
                        label={
                          isDesc ? t("common.viewControls.desc") : t("common.viewControls.asc")
                        }
                        icon={
                          isDesc ? (
                            <ArrowDownwardIcon sx={{ fontSize: "0.7rem" }} />
                          ) : (
                            <ArrowUpwardIcon sx={{ fontSize: "0.7rem" }} />
                          )
                        }
                        sx={{
                          height: 22,
                          fontSize: "0.6875rem",
                          fontWeight: 600,
                          flexShrink: 0,
                          ml: 1,
                          bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                          color: "primary.main",
                          "& .MuiChip-icon": { color: "primary.main", ml: 0.5 },
                        }}
                      />
                    )}
                  </Box>
                );
              };

              return (
                <Box
                  role="listbox"
                  aria-label="Sort options"
                  sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}
                >
                  {standardOpts.map(renderSortItem)}
                  {customOpts.length > 0 && (
                    <>
                      <Divider
                        sx={{
                          my: 1,
                          borderColor: (theme) => alpha(theme.palette.divider, 0.5),
                        }}
                      />
                      <Typography
                        variant="overline"
                        sx={{
                          fontSize: "0.625rem",
                          fontWeight: 700,
                          letterSpacing: "0.08em",
                          color: "text.disabled",
                          px: 1.25,
                          mb: 0.25,
                        }}
                      >
                        Custom fields
                      </Typography>
                      {customOpts.map(renderSortItem)}
                    </>
                  )}
                </Box>
              );
            })()
          )}
        </Box>
      </Menu>

      {/* ═══ Fields Panel ═══ */}
      <Menu
        open={Boolean(fieldsAnchor)}
        anchorEl={fieldsAnchor}
        onClose={handleFieldsClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: { ...popoverPaperSx(280), maxHeight: 480 } } }}
      >
        <Box sx={{ p: 2 }}>
          {/* When availableFields + selectedSearchFields are provided, show the full metadata field list */}
          {availableFields &&
          availableFields.length > 0 &&
          selectedSearchFields &&
          onSelectedFieldsChange ? (
            <>
              <PanelHeader
                title={t("common.viewControls.displayFields")}
                action={
                  <TextAction
                    label={
                      availableFields.every((f) => selectedSearchFields.includes(f.name))
                        ? t("common.viewControls.hideAll")
                        : t("common.viewControls.showAll")
                    }
                    onClick={() => {
                      const allSelected = availableFields.every((f) =>
                        selectedSearchFields.includes(f.name)
                      );
                      onSelectedFieldsChange(allSelected ? [] : availableFields.map((f) => f.name));
                    }}
                  />
                }
              />
              <FormGroup sx={{ gap: 0 }}>
                {(() => {
                  const defaultFields = availableFields.filter((f) => f.isDefault);
                  const customFields = availableFields.filter((f) => !f.isDefault);

                  const renderFieldItem = (field: FieldInfo) => {
                    const isChecked = selectedSearchFields.includes(field.name);
                    return (
                      <FormControlLabel
                        key={field.name}
                        control={
                          <Checkbox
                            checked={isChecked}
                            onChange={() => {
                              const updated = isChecked
                                ? selectedSearchFields.filter((f) => f !== field.name)
                                : [...selectedSearchFields, field.name];
                              onSelectedFieldsChange(updated);
                            }}
                            size="small"
                            sx={{
                              py: 0.25,
                              color: "text.secondary",
                              "&.Mui-checked": { color: "primary.main" },
                            }}
                          />
                        }
                        label={
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <Typography
                              variant="body2"
                              sx={{
                                fontSize: "0.8125rem",
                                fontWeight: isChecked ? 500 : 400,
                                color: isChecked ? "text.primary" : "text.secondary",
                              }}
                            >
                              {field.displayName || field.name}
                            </Typography>
                            {field.isDefault && (
                              <Typography
                                variant="caption"
                                sx={{ fontSize: "0.625rem", color: "text.disabled" }}
                              >
                                default
                              </Typography>
                            )}
                          </Box>
                        }
                        sx={{ mx: 0, my: -0.25 }}
                      />
                    );
                  };

                  return (
                    <>
                      {defaultFields.map(renderFieldItem)}
                      {customFields.length > 0 && (
                        <>
                          <Divider
                            sx={{
                              my: 1,
                              borderColor: (theme) => alpha(theme.palette.divider, 0.5),
                            }}
                          />
                          <Typography
                            variant="overline"
                            sx={{
                              fontSize: "0.625rem",
                              fontWeight: 700,
                              letterSpacing: "0.08em",
                              color: "text.disabled",
                              px: 0.5,
                              mb: 0.25,
                            }}
                          >
                            Custom fields
                          </Typography>
                          {customFields.map(renderFieldItem)}
                        </>
                      )}
                    </>
                  );
                })()}
              </FormGroup>
            </>
          ) : (
            /* Fallback: show the legacy cardFields / columns list */
            fields.length > 0 && (
              <>
                <PanelHeader
                  title={
                    viewMode === "card"
                      ? t("common.viewControls.displayFields")
                      : t("common.viewControls.tableColumns")
                  }
                  action={
                    <TextAction
                      label={
                        fields.every((f) => f.visible)
                          ? t("common.viewControls.hideAll")
                          : t("common.viewControls.showAll")
                      }
                      onClick={() => {
                        const allVisible = fields.every((f) => f.visible);
                        fields.forEach((f) => {
                          if (allVisible === f.visible) onFieldToggle(f.id);
                        });
                      }}
                    />
                  }
                />
                <FormGroup sx={{ gap: 0 }}>
                  {fields.map((field) => (
                    <FormControlLabel
                      key={field.id}
                      control={
                        <Checkbox
                          checked={field.visible}
                          onChange={() => onFieldToggle(field.id)}
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
                            fontWeight: field.visible ? 500 : 400,
                            color: field.visible ? "text.primary" : "text.secondary",
                          }}
                        >
                          {field.label}
                        </Typography>
                      }
                      sx={{ mx: 0, my: -0.25 }}
                    />
                  ))}
                </FormGroup>
              </>
            )
          )}
        </Box>
      </Menu>

      {/* ═══ Appearance Panel ═══ */}
      <Menu
        open={Boolean(appearanceAnchor)}
        anchorEl={appearanceAnchor}
        onClose={handleAppearanceClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: popoverPaperSx(300) } }}
      >
        <Box sx={{ p: 2 }}>
          <PanelHeader title={t("common.viewControls.appearance")} />

          {viewMode === "card" && (
            <>
              {/* Card Size */}
              <Box sx={{ mb: 2 }}>
                <SectionLabel>{t("common.viewControls.cardSize")}</SectionLabel>
                <ToggleButtonGroup
                  value={cardSize}
                  exclusive
                  onChange={(_, val) => val && onCardSizeChange(val)}
                  size="small"
                  fullWidth
                  aria-label="Card size"
                  sx={segmentedToggleSx}
                >
                  <ToggleButton value="small" aria-label={t("common.viewControls.small")}>
                    <PhotoSizeSelectSmallIcon sx={{ fontSize: "0.875rem" }} />
                    {t("common.viewControls.small")}
                  </ToggleButton>
                  <ToggleButton value="medium" aria-label={t("common.viewControls.medium")}>
                    <ViewModuleIcon sx={{ fontSize: "0.875rem" }} />
                    {t("common.viewControls.medium")}
                  </ToggleButton>
                  <ToggleButton value="large" aria-label={t("common.viewControls.large")}>
                    <PhotoSizeSelectLargeIcon sx={{ fontSize: "0.875rem" }} />
                    {t("common.viewControls.large")}
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              {/* Aspect Ratio */}
              <Box sx={{ mb: 2 }}>
                <SectionLabel>{t("common.viewControls.aspectRatio")}</SectionLabel>
                <ToggleButtonGroup
                  value={aspectRatio}
                  exclusive
                  onChange={(_, val) => val && onAspectRatioChange(val)}
                  size="small"
                  fullWidth
                  aria-label="Aspect ratio"
                  sx={segmentedToggleSx}
                >
                  <ToggleButton value="vertical" aria-label={t("common.viewControls.portrait")}>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 0.25,
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                        <CropPortraitIcon sx={{ fontSize: "0.875rem" }} />
                        {t("common.viewControls.portrait")}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{ fontSize: "0.6rem", opacity: 0.7, lineHeight: 1 }}
                      >
                        3:4
                      </Typography>
                    </Box>
                  </ToggleButton>
                  <ToggleButton value="square" aria-label={t("common.viewControls.square")}>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 0.25,
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                        <CropSquareIcon sx={{ fontSize: "0.875rem" }} />
                        {t("common.viewControls.square")}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{ fontSize: "0.6rem", opacity: 0.7, lineHeight: 1 }}
                      >
                        1:1
                      </Typography>
                    </Box>
                  </ToggleButton>
                  <ToggleButton value="horizontal" aria-label={t("common.viewControls.landscape")}>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 0.25,
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                        <CropLandscapeIcon sx={{ fontSize: "0.875rem" }} />
                        {t("common.viewControls.landscape")}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{ fontSize: "0.6rem", opacity: 0.7, lineHeight: 1 }}
                      >
                        4:3
                      </Typography>
                    </Box>
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              {/* Thumbnail Scale */}
              <Box sx={{ mb: 2 }}>
                <SectionLabel>{t("common.viewControls.thumbnailScale")}</SectionLabel>
                <ToggleButtonGroup
                  value={thumbnailScale}
                  exclusive
                  onChange={(_, val) => val && onThumbnailScaleChange(val)}
                  size="small"
                  fullWidth
                  aria-label="Thumbnail scale"
                  sx={segmentedToggleSx}
                >
                  <ToggleButton value="fit" aria-label={t("common.viewControls.fit")}>
                    <FitScreenIcon sx={{ fontSize: "0.875rem" }} />
                    {t("common.viewControls.fit")}
                  </ToggleButton>
                  <ToggleButton value="fill" aria-label={t("common.viewControls.fill")}>
                    <FullscreenIcon sx={{ fontSize: "0.875rem" }} />
                    {t("common.viewControls.fill")}
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>

              <Divider
                sx={{
                  my: 1.5,
                  borderColor: (theme) => alpha(theme.palette.divider, 0.5),
                }}
              />
            </>
          )}

          {/* Toggle switches — always visible, with a section label in table mode */}
          {viewMode === "table" && <SectionLabel>{t("common.viewControls.options")}</SectionLabel>}

          <Box sx={{ display: "flex", flexDirection: "row", gap: 1, flexWrap: "wrap" }}>
            <FormControlLabel
              control={
                <Switch
                  checked={groupByType}
                  onChange={(e) => onGroupByTypeChange(e.target.checked)}
                  size="small"
                  sx={{
                    "& .MuiSwitch-switchBase.Mui-checked": {
                      color: "primary.main",
                    },
                    "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
                      bgcolor: "primary.main",
                    },
                  }}
                />
              }
              label={
                <Typography variant="body2" sx={{ fontSize: "0.8125rem" }}>
                  {t("common.viewControls.groupByType")}
                </Typography>
              }
              sx={{ mx: 0, flex: "0 0 auto" }}
            />
            {viewMode === "card" && (
              <FormControlLabel
                control={
                  <Switch
                    checked={showMetadata}
                    onChange={(e) => onShowMetadataChange(e.target.checked)}
                    size="small"
                    sx={{
                      "& .MuiSwitch-switchBase.Mui-checked": {
                        color: "primary.main",
                      },
                      "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
                        bgcolor: "primary.main",
                      },
                    }}
                  />
                }
                label={
                  <Typography variant="body2" sx={{ fontSize: "0.8125rem" }}>
                    {t("common.viewControls.metadata")}
                  </Typography>
                }
                sx={{ mx: 0, flex: "0 0 auto" }}
              />
            )}
          </Box>
        </Box>
      </Menu>
    </Box>
  );
};

export default AssetViewControls;
