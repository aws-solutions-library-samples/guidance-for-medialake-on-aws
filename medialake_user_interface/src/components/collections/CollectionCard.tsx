import React, { useState, useCallback, useMemo } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Tooltip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  People as SharedIcon,
  Share as ShareIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  MoreHoriz as MoreHorizIcon,
  ChevronRight as ChevronRightIcon,
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { ALL_ICONS } from "./ThumbnailSelector";
import type { Collection } from "../../api/hooks/useCollections";
import type {
  CollectionCardDisplayPrefs,
  CollectionCardSize,
} from "../../hooks/useCollectionViewPreferences";
import { DEFAULT_PREFS } from "../../hooks/useCollectionViewPreferences";

type PermissionCheck = { disabled: boolean; tooltip?: string };

export interface CollectionCardProps {
  collection: Collection;
  /** Click handler for the card body (typically navigate to detail view) */
  onClick: (collection: Collection) => void;
  /** Owner-only action. Hidden when `undefined`. */
  onShareClick?: (collection: Collection) => void;
  /** Owner/editor action. Hidden when `undefined`. */
  onEditClick?: (collection: Collection) => void;
  /** Owner-only action. Hidden when `undefined`. */
  onDeleteClick?: (collection: Collection) => void;
  /** Optional role-based gates applied after per-collection permission logic */
  editPermission?: PermissionCheck;
  deletePermission?: PermissionCheck;
  /**
   * Optional accent color for the thumbnail placeholder background — used when
   * the collection has no thumbnail URL/icon. Typically derived from the
   * collection's collectionType.
   */
  accentColor?: string;
  /** Icon rendered in the placeholder when no thumbnail exists. */
  placeholderIconName?: string;
  /**
   * When a custom-metadata sort is active, the key is passed in so the card can
   * surface the value for that key as a small chip (explains sort position).
   * In `minimal` preset this is the only metadata shown; in other presets the
   * metadata strip covers it implicitly.
   */
  sortedMetadataKey?: string;
  /**
   * Parent breadcrumb name — rendered above the collection name when the card
   * surfaces as part of a flat (include-children) search result so users can see
   * where the child lives.
   */
  parentName?: string;
  /**
   * Display preferences (preset, field toggles, metadata keys, card size).
   * When omitted, defaults to the built-in `rich` profile — the default is
   * safe for legacy callers (e.g. the Sub-Collections grid on the detail page)
   * that haven't been wired up to the preferences hook yet.
   */
  display?: CollectionCardDisplayPrefs;
  /** Whether the collection is currently in the user's favorites. */
  isFavorite?: boolean;
  /** Callback fired when the favorite toggle is activated. When undefined the toggle is not rendered. */
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void;
}

// Tag cap derived from card size — keeps card heights visually stable.
const TAG_CAP_BY_SIZE: Record<CollectionCardSize, number> = {
  small: 2,
  medium: 3,
  large: 5,
};

// Description line clamp — denser cards get fewer lines.
const DESCRIPTION_LINES_BY_SIZE: Record<CollectionCardSize, number> = {
  small: 1,
  medium: 2,
  large: 3,
};

// Thumbnail height in px. Scales visually with card width.
const THUMBNAIL_HEIGHT_BY_SIZE: Record<CollectionCardSize, number> = {
  small: 140,
  medium: 180,
  large: 220,
};

/**
 * Unified collection card used in both the primary Collections list and the
 * Sub-Collections grid on the detail page. Owns the card's look, actions, and
 * permission gating so the two surfaces stay in sync.
 *
 * Display is driven by a `CollectionCardDisplayPrefs` object (presets +
 * per-field toggles + custom metadata keys + card size). Defaults to the
 * built-in `rich` profile so callers that don't wire up preferences still get
 * a sensible, metadata-aware card.
 *
 * Key design decisions:
 * - Thumbnail is edge-to-edge so uploaded images fill the top of the card.
 * - Actions collapse into a single always-visible `⋯` menu — hover-only icon
 *   clusters are invisible on touch and easy to miss on desktop.
 * - Visibility reads as a chip in most presets and as a corner dot on the
 *   thumbnail in `minimal` — the signal is preserved even in image-first mode.
 * - The metadata strip (key:value chips) sits between description and tags so
 *   it reads as supporting info next to the name, not as a separate footer.
 */
export const CollectionCard: React.FC<CollectionCardProps> = ({
  collection,
  onClick,
  onShareClick,
  onEditClick,
  onDeleteClick,
  editPermission,
  deletePermission,
  accentColor,
  placeholderIconName,
  sortedMetadataKey,
  parentName,
  display = DEFAULT_PREFS,
  isFavorite,
  onFavoriteToggle,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  // Per-collection permission gating — mirrors `format_collection_item` on the
  // backend: `userRole` is the single source of truth. Legacy fallback covers
  // cached data fetched before the backend added the field.
  const userRole = collection.userRole?.toLowerCase();
  const isOwner =
    userRole === "owner" || (!userRole && !collection.sharedWithMe && !collection.myRole);
  const isEditor = userRole === "editor" || userRole === "admin";
  const canEdit = (isOwner || isEditor) && !!onEditClick;
  const canDelete = isOwner && !!onDeleteClick;
  const canShare = isOwner && !!onShareClick;
  const hasActions = canShare || canEdit || canDelete;

  const handleMenuOpen = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback((e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setMenuAnchor(null);
  }, []);

  const handleAction = useCallback(
    (action: (c: Collection) => void, e: React.MouseEvent) => {
      e.stopPropagation();
      setMenuAnchor(null);
      action(collection);
    },
    [collection]
  );

  const isMinimal = display.preset === "minimal";
  const cardSize = display.cardSize;

  // Tags — capped by card size. Always respects the user's showTags toggle.
  const tags = collection.tags ?? [];
  const tagCap = TAG_CAP_BY_SIZE[cardSize];
  const visibleTags = tags.slice(0, tagCap);
  const hiddenTagCount = Math.max(0, tags.length - tagCap);

  // Metadata strip — pick keys to render. Two sources:
  //   1. Preferred: the keys the user checked under "Customize fields"
  //      (`display.visibleMetadataKeys`). This is the normal path.
  //   2. Fallback: when the user hasn't curated any keys yet (empty list) but
  //      the preset allows metadata (`maxMetadataKeys > 0`), fall back to the
  //      keys present on *this specific collection*. This means Rich / Full
  //      always show something useful out of the box — no "configure a list
  //      first" discovery problem.
  // Either way, only keys with non-empty values are rendered, and the preset's
  // `maxMetadataKeys` caps the count.
  const metadataEntries = useMemo<Array<[string, string]>>(() => {
    if (display.maxMetadataKeys <= 0) return [];
    const custom = collection.customMetadata ?? {};

    const sourceKeys =
      display.visibleMetadataKeys.length > 0
        ? display.visibleMetadataKeys
        : Object.keys(custom).sort((a, b) => a.localeCompare(b));

    const entries: Array<[string, string]> = [];
    for (const key of sourceKeys) {
      const value = custom[key];
      if (value !== undefined && value !== null && value !== "") {
        entries.push([key, String(value)]);
      }
      if (entries.length >= display.maxMetadataKeys) break;
    }
    return entries;
  }, [display.maxMetadataKeys, display.visibleMetadataKeys, collection.customMetadata]);

  // Total keys with values (for the `+N more` overflow label). Uses the same
  // source (curated list or per-collection fallback) as `metadataEntries`.
  const totalAvailableMetadataKeys = useMemo(() => {
    const custom = collection.customMetadata ?? {};
    const sourceKeys =
      display.visibleMetadataKeys.length > 0 ? display.visibleMetadataKeys : Object.keys(custom);
    let count = 0;
    for (const key of sourceKeys) {
      const value = custom[key];
      if (value !== undefined && value !== null && value !== "") count += 1;
    }
    return count;
  }, [display.visibleMetadataKeys, collection.customMetadata]);
  const hiddenMetadataCount = Math.max(0, totalAvailableMetadataKeys - metadataEntries.length);

  const sortedMetadataValue = sortedMetadataKey && collection.customMetadata?.[sortedMetadataKey];

  // Resolve thumbnail: (1) uploaded/asset/frame image URL, (2) icon from the
  // ThumbnailSelector catalog, (3) fallback placeholder icon.
  const thumbnailNode = (() => {
    if (
      collection.thumbnailUrl &&
      collection.thumbnailType &&
      collection.thumbnailType !== "icon"
    ) {
      return (
        <Box
          component="img"
          src={collection.thumbnailUrl}
          alt={collection.name}
          sx={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
      );
    }
    if (collection.thumbnailType === "icon" && collection.thumbnailValue) {
      const IconCmp = ALL_ICONS[collection.thumbnailValue];
      if (IconCmp) {
        return (
          <IconCmp
            sx={{
              fontSize: cardSize === "small" ? 44 : cardSize === "large" ? 64 : 56,
              color: alpha(accentColor || theme.palette.primary.main, 0.55),
            }}
          />
        );
      }
    }
    const PlaceholderIcon = placeholderIconName
      ? (ALL_ICONS[placeholderIconName] ?? FolderIcon)
      : FolderIcon;
    return (
      <PlaceholderIcon
        sx={{
          fontSize: cardSize === "small" ? 44 : cardSize === "large" ? 64 : 56,
          color: alpha(accentColor || theme.palette.primary.main, 0.3),
        }}
      />
    );
  })();

  const visibilityMeta = (() => {
    if (collection.sharedWithMe) {
      return {
        icon: <SharedIcon />,
        label: t("collectionsPage.labels.shared", "Shared"),
      };
    }
    if (collection.isPublic) {
      return {
        icon: <PublicIcon />,
        label: t("collectionsPage.labels.public", "Public"),
      };
    }
    return {
      icon: <PrivateIcon />,
      label: t("collectionsPage.labels.private", "Private"),
    };
  })();

  // Subtle accent per visibility so the inline badge reads without shouting.
  // Public = success tint, Shared = warning/amber tint, Private = muted text color.
  const visibilityColor = collection.sharedWithMe
    ? theme.palette.warning.main
    : collection.isPublic
      ? theme.palette.success.main
      : theme.palette.text.secondary;

  // `minimal` preset: render the visibility signal as a corner dot on the
  // thumbnail instead of a chip in the info row (which doesn't exist in
  // minimal). Keeps the critical cue without re-adding the info section.
  const showCornerVisibilityDot = isMinimal && display.showVisibility;

  // Parent breadcrumb is only rendered when the caller passes a parent AND the
  // user hasn't opted out of it via the core-field toggle.
  const renderParent = !!parentName && display.showParentBreadcrumb && !isMinimal;

  // Description only renders when the user wants it AND the collection has one.
  const renderDescription = !!collection.description && display.showDescription && !isMinimal;

  // Show the sortedMetadataKey chip only when a custom-metadata sort is active
  // AND the metadata strip wouldn't already surface that value. This keeps the
  // "why is this here" hint in `minimal` (where the strip is empty) without
  // double-rendering the same value in `rich`/`full`.
  const renderSortedMetadataChip =
    !!sortedMetadataKey &&
    !!sortedMetadataValue &&
    (isMinimal || !metadataEntries.some(([k]) => k === sortedMetadataKey));

  return (
    <Card
      onClick={() => onClick(collection)}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        cursor: "pointer",
        borderRadius: 2,
        bgcolor: "background.paper",
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        overflow: "hidden",
        transition: "transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: `0 6px 16px ${alpha(theme.palette.common.black, 0.08)}, 0 2px 4px ${alpha(
            theme.palette.common.black,
            0.06
          )}`,
          borderColor: alpha(theme.palette.divider, 0.22),
        },
      }}
    >
      {/* Thumbnail — edge-to-edge, rounded corners inherit from the Card */}
      <Box
        sx={{
          position: "relative",
          height: THUMBNAIL_HEIGHT_BY_SIZE[cardSize],
          bgcolor: alpha(accentColor || theme.palette.primary.main, 0.06),
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {thumbnailNode}

        {showCornerVisibilityDot && (
          <Tooltip title={visibilityMeta.label}>
            <Box
              role="img"
              aria-label={visibilityMeta.label}
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                width: 10,
                height: 10,
                borderRadius: "50%",
                bgcolor: visibilityColor,
                boxShadow: `0 0 0 2px ${theme.palette.background.paper}`,
              }}
            />
          </Tooltip>
        )}

        {onFavoriteToggle && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onFavoriteToggle(e);
            }}
            aria-label={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
            title={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
            data-testid="collection-favorite-button"
            sx={{
              position: "absolute",
              top: 6,
              left: 6,
              color: isFavorite ? "error.main" : "primary.main",
              bgcolor: alpha(theme.palette.background.paper, 0.85),
              "&:hover": {
                bgcolor: alpha(theme.palette.background.paper, 0.95),
              },
            }}
          >
            {isFavorite ? (
              <FavoriteIcon fontSize="small" />
            ) : (
              <FavoriteBorderIcon fontSize="small" />
            )}
          </IconButton>
        )}
      </Box>

      {/* Info section — fully hidden in minimal preset except for a tight name row */}
      <CardContent
        sx={{
          px: 1.75,
          pt: 1.25,
          pb: 1.25,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          "&:last-child": { pb: 1.25 },
        }}
      >
        {renderParent && (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.3,
              mb: 0.4,
              overflow: "hidden",
            }}
          >
            <FolderOpenIcon
              sx={{
                fontSize: 12,
                color: "text.secondary",
                opacity: 0.6,
                flexShrink: 0,
              }}
            />
            <Typography
              variant="caption"
              sx={{
                fontSize: "0.65rem",
                color: "text.secondary",
                opacity: 0.75,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {parentName}
            </Typography>
            <ChevronRightIcon
              sx={{
                fontSize: 11,
                color: "text.secondary",
                opacity: 0.4,
                flexShrink: 0,
              }}
            />
          </Box>
        )}

        {/* Name row + overflow menu */}
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 0.5 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="subtitle2"
              component="h3"
              sx={{
                fontWeight: 600,
                fontSize: cardSize === "small" ? "0.82rem" : "0.9rem",
                lineHeight: 1.35,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {collection.name}
            </Typography>
            {renderDescription && (
              <Typography
                variant="caption"
                sx={{
                  display: "-webkit-box",
                  WebkitLineClamp: DESCRIPTION_LINES_BY_SIZE[cardSize],
                  WebkitBoxOrient: "vertical",
                  fontSize: "0.72rem",
                  color: "text.secondary",
                  lineHeight: 1.4,
                  overflow: "hidden",
                  mt: 0.25,
                }}
              >
                {collection.description}
              </Typography>
            )}
          </Box>
          {hasActions && (
            <Tooltip title={t("common.actions.more", "Actions")}>
              <IconButton
                size="small"
                onClick={handleMenuOpen}
                aria-label={t("common.actions.more", "Actions")}
                sx={{
                  mt: -0.25,
                  mr: -0.5,
                  color: "text.secondary",
                  "&:hover": {
                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                    color: "text.primary",
                  },
                }}
              >
                <MoreHorizIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Metadata strip — key:value chips. Dense, scannable, capped.
            Key = uppercase label in text.disabled. Value = monospace in primary
            color. Echoes the detail-page metadata tile grid so the two surfaces
            feel like the same data with different densities. */}
        {metadataEntries.length > 0 && (
          <Box
            sx={{
              display: "flex",
              flexWrap: "wrap",
              gap: 0.5,
              mt: 0.75,
            }}
            aria-label={t("collectionsPage.cardView.metadataStrip", "Custom metadata")}
          >
            {metadataEntries.map(([key, value]) => (
              <Tooltip key={key} title={`${key}: ${value}`} enterDelay={400}>
                <Box
                  component="span"
                  aria-label={`${key}: ${value}`}
                  sx={{
                    display: "inline-flex",
                    alignItems: "baseline",
                    gap: 0.5,
                    maxWidth: "100%",
                    height: 20,
                    px: 0.75,
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                    bgcolor: alpha(theme.palette.text.primary, 0.02),
                    overflow: "hidden",
                  }}
                >
                  <Typography
                    component="span"
                    sx={{
                      fontSize: "0.58rem",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      fontWeight: 700,
                      color: "text.disabled",
                      flexShrink: 0,
                    }}
                  >
                    {key}
                  </Typography>
                  <Typography
                    component="span"
                    sx={{
                      fontFamily:
                        'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
                      fontSize: "0.68rem",
                      fontWeight: 500,
                      color: "text.primary",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      minWidth: 0,
                    }}
                  >
                    {value}
                  </Typography>
                </Box>
              </Tooltip>
            ))}
            {hiddenMetadataCount > 0 && (
              <Box
                component="span"
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  height: 20,
                  px: 0.75,
                  borderRadius: 1,
                  border: `1px dashed ${alpha(theme.palette.divider, 0.3)}`,
                  fontSize: "0.625rem",
                  color: "text.disabled",
                  fontWeight: 600,
                }}
              >
                +{hiddenMetadataCount}
              </Box>
            )}
          </Box>
        )}

        {/* Sorted-metadata explainer chip — only shown when a customMetadata sort
            is active AND the metadata strip isn't already surfacing that key.
            Keeps `minimal` honest (user can still see why this card is here). */}
        {renderSortedMetadataChip && (
          <Box sx={{ mt: 0.75 }}>
            <Chip
              size="small"
              label={`${sortedMetadataKey} · ${sortedMetadataValue}`}
              sx={{
                height: 20,
                fontSize: "0.65rem",
                fontWeight: 600,
                fontFamily: 'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
                bgcolor: alpha(theme.palette.primary.main, 0.08),
                color: "primary.main",
                "& .MuiChip-label": { px: 0.75 },
              }}
            />
          </Box>
        )}

        {/* Tag row — cap scales with card size, overflow folds to +N */}
        {display.showTags && !isMinimal && tags.length > 0 && (
          <Box
            sx={{
              display: "flex",
              flexWrap: "nowrap",
              gap: 0.5,
              mt: 0.75,
              overflow: "hidden",
            }}
          >
            {visibleTags.map((tag) => (
              <Chip
                key={tag}
                label={tag}
                size="small"
                sx={{
                  height: 18,
                  fontSize: "0.625rem",
                  fontFamily:
                    'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
                  bgcolor: alpha(theme.palette.primary.main, 0.08),
                  color: theme.palette.primary.main,
                  border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
                  "& .MuiChip-label": { px: 0.6 },
                }}
              />
            ))}
            {hiddenTagCount > 0 && (
              <Chip
                label={`+${hiddenTagCount}`}
                size="small"
                sx={{
                  height: 18,
                  fontSize: "0.625rem",
                  fontFamily:
                    'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
                  bgcolor: "transparent",
                  color: alpha(theme.palette.primary.main, 0.7),
                  border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
                  "& .MuiChip-label": { px: 0.6 },
                }}
              />
            )}
          </Box>
        )}

        {/* Spacer pushes the meta row to the bottom when card heights vary */}
        <Box sx={{ flex: 1 }} />

        {/* Meta row — count + date on the left, visibility chip on the right.
            Hidden entirely when both `showMeta` and `showVisibility` are off,
            or in minimal preset (visibility is covered by the thumbnail dot). */}
        {(display.showMeta || (display.showVisibility && !isMinimal)) && (
          <Box
            sx={{
              mt: 1,
              pt: 0.75,
              borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            {display.showMeta ? (
              <Typography
                variant="caption"
                sx={{
                  fontSize: "0.72rem",
                  color: "text.secondary",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  minWidth: 0,
                }}
              >
                {collection.childCollectionCount > 0
                  ? `${collection.childCollectionCount} sub · ${collection.itemCount} ${
                      collection.itemCount === 1 ? "asset" : "assets"
                    }`
                  : `${collection.itemCount} ${collection.itemCount === 1 ? "asset" : "assets"}`}
                {collection.updatedAt && (
                  <Box component="span" sx={{ color: "text.disabled", mx: 0.5 }} aria-hidden="true">
                    ·
                  </Box>
                )}
                {collection.updatedAt
                  ? new Date(collection.updatedAt).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })
                  : ""}
              </Typography>
            ) : (
              <Box sx={{ flex: 1 }} />
            )}
            {display.showVisibility && !isMinimal && (
              <Chip
                label={visibilityMeta.label}
                size="small"
                icon={visibilityMeta.icon}
                variant="outlined"
                sx={{
                  flexShrink: 0,
                  height: 22,
                  fontSize: "0.68rem",
                  fontWeight: 500,
                  color: visibilityColor,
                  borderColor: alpha(visibilityColor, 0.35),
                  bgcolor: alpha(visibilityColor, 0.06),
                  "& .MuiChip-icon": {
                    color: visibilityColor,
                    fontSize: 13,
                    ml: 0.5,
                  },
                  "& .MuiChip-label": { px: 0.75 },
                }}
              />
            )}
          </Box>
        )}
      </CardContent>

      {/* Action menu — single dropdown replaces hover icon cluster */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={() => handleMenuClose()}
        onClick={(e) => e.stopPropagation()}
        slotProps={{
          paper: {
            elevation: 2,
            sx: {
              minWidth: 160,
              mt: 0.5,
              borderRadius: 1.5,
              border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            },
          },
        }}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        {canShare && (
          <MenuItem onClick={(e) => handleAction(onShareClick!, e)} dense>
            <ListItemIcon>
              <ShareIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>{t("common.share", "Share")}</ListItemText>
          </MenuItem>
        )}
        {canEdit && (
          <MenuItem
            onClick={(e) => handleAction(onEditClick!, e)}
            disabled={!!editPermission?.disabled}
            dense
          >
            <ListItemIcon>
              <EditIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>
              {editPermission?.disabled && editPermission.tooltip
                ? editPermission.tooltip
                : t("common.edit", "Edit")}
            </ListItemText>
          </MenuItem>
        )}
        {canDelete && (canShare || canEdit) && <Divider sx={{ my: 0.5 }} />}
        {canDelete && (
          <MenuItem
            onClick={(e) => handleAction(onDeleteClick!, e)}
            disabled={!!deletePermission?.disabled}
            dense
            sx={{ color: "error.main" }}
          >
            <ListItemIcon>
              <DeleteIcon fontSize="small" sx={{ color: "error.main" }} />
            </ListItemIcon>
            <ListItemText>
              {deletePermission?.disabled && deletePermission.tooltip
                ? deletePermission.tooltip
                : t("common.delete", "Delete")}
            </ListItemText>
          </MenuItem>
        )}
      </Menu>
    </Card>
  );
};

export default CollectionCard;
