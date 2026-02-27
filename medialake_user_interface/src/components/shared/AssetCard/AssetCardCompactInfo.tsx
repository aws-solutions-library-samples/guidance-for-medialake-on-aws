/**
 * AssetCardCompactInfo — the info section for the compact (dashboard) variant.
 * Name, inline editor, field summary, favorite toggle, and overflow menu.
 */
import React, { useState, useRef } from "react";
import {
  Box,
  Typography,
  IconButton,
  CircularProgress,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderIcon from "@mui/icons-material/FavoriteBorder";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import { InlineTextEditor } from "../../common/InlineTextEditor";
import InlineEditActions from "../../common/InlineEditActions";
import type { AssetField } from "@/types/shared/assetComponents";

interface AssetCardCompactInfoProps {
  id: string;
  name: string;
  fields: AssetField[];
  renderField: (fieldId: string) => string | React.ReactNode;
  isEditing?: boolean;
  editedName?: string;
  isRenaming: boolean;
  isClipMode: boolean;
  isFavorite: boolean;
  showRemoveButton: boolean;
  onAssetClick: () => void;
  onEditClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (save: boolean, value?: string) => void;
  onDeleteClick: (event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void;
}

const AssetCardCompactInfo: React.FC<AssetCardCompactInfoProps> = React.memo(
  ({
    id,
    name,
    fields,
    renderField,
    isEditing,
    editedName,
    isRenaming,
    isClipMode,
    isFavorite,
    showRemoveButton,
    onAssetClick,
    onEditClick,
    onEditNameChange,
    onEditNameComplete,
    onDeleteClick,
    onDownloadClick,
    onAddToCollectionClick,
    onFavoriteToggle,
  }) => {
    const { t } = useTranslation();
    const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
    const menuOpen = Boolean(menuAnchor);
    const preventCommitRef = useRef(false);
    const commitRef = useRef<(() => void) | null>(null);

    return (
      <Box sx={{ px: 1.5, pt: 1, pb: 1, cursor: "pointer" }} onClick={onAssetClick}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
          {isEditing && onEditClick ? (
            <Box
              sx={{ width: "100%", display: "flex", flexDirection: "column", gap: 0.5 }}
              onClick={(e) => e.stopPropagation()}
            >
              <InlineTextEditor
                initialValue={editedName || ""}
                editingCellId={id}
                preventCommitRef={preventCommitRef}
                commitRef={commitRef}
                onChangeCommit={(value) =>
                  onEditNameChange?.({ target: { value } } as React.ChangeEvent<HTMLInputElement>)
                }
                onComplete={(save, value) => onEditNameComplete?.(save, value)}
                isEditing
                disabled={isRenaming}
                autoFocus
                size="small"
                fullWidth
                sx={{ "& .MuiInputBase-root": { fontSize: "0.82rem" } }}
                InputProps={{ endAdornment: isRenaming && <CircularProgress size={14} /> }}
              />
              <InlineEditActions
                preventCommitRef={preventCommitRef}
                commitRef={commitRef}
                onCancel={() => onEditNameComplete?.(false, undefined)}
                isDisabled={isRenaming}
                sx={{ fontSize: "0.7rem", py: 0.25, px: 1, minWidth: 0 }}
                containerSx={{ gap: 0.5 }}
              />
            </Box>
          ) : (
            <>
              <Typography
                variant="subtitle2"
                component="h4"
                title={name}
                sx={{
                  fontWeight: 600,
                  fontSize: "0.82rem",
                  lineHeight: 1.4,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                }}
              >
                {name}
              </Typography>
              {onEditClick && (
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEditClick(e);
                  }}
                  disabled={isRenaming}
                  sx={{ p: 0.25 }}
                >
                  {isRenaming ? <CircularProgress size={12} /> : <EditIcon sx={{ fontSize: 14 }} />}
                </IconButton>
              )}
            </>
          )}
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              fontSize: "0.7rem",
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {fields
              .filter((f) => f.id !== "name")
              .map((f) => String(renderField(f.id)))
              .filter(Boolean)
              .join(" · ")}
          </Typography>
          <Box
            sx={{ display: "flex", alignItems: "center", gap: 0.25, ml: 0.5, flexShrink: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onFavoriteToggle?.(e);
              }}
              sx={{
                p: 0.25,
                color: isFavorite ? "error.main" : "text.secondary",
                transition: "color 0.15s ease",
                "&:hover": {
                  color: isFavorite ? "error.dark" : "error.main",
                  bgcolor: (theme) => alpha(theme.palette.error.main, 0.08),
                },
              }}
              title={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
              data-testid="favorite-button"
            >
              {isFavorite ? (
                <FavoriteIcon sx={{ fontSize: 16 }} />
              ) : (
                <FavoriteBorderIcon sx={{ fontSize: 16 }} />
              )}
            </IconButton>
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setMenuAnchor(e.currentTarget);
              }}
              sx={{
                p: 0.25,
                color: "text.secondary",
                "&:hover": {
                  color: "primary.main",
                  bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08),
                },
              }}
              aria-label={t("common.actions.more", "More actions")}
              aria-haspopup="true"
            >
              <MoreHorizIcon sx={{ fontSize: 18 }} />
            </IconButton>
            <Menu
              anchorEl={menuAnchor}
              open={menuOpen}
              onClose={(e: React.SyntheticEvent) => {
                e.stopPropagation?.();
                setMenuAnchor(null);
              }}
              onClick={(e) => e.stopPropagation()}
              anchorOrigin={{ vertical: "top", horizontal: "right" }}
              transformOrigin={{ vertical: "bottom", horizontal: "right" }}
              slotProps={{
                paper: {
                  elevation: 3,
                  sx: {
                    minWidth: 180,
                    borderRadius: 2,
                    mt: -0.5,
                    border: "1px solid",
                    borderColor: "divider",
                    "& .MuiMenuItem-root": { fontSize: "0.82rem", py: 0.75, gap: 1 },
                  },
                },
              }}
            >
              {!isClipMode && (
                <MenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuAnchor(null);
                    onDownloadClick(e);
                  }}
                >
                  <ListItemIcon>
                    <DownloadIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText>{t("common.actions.download")}</ListItemText>
                </MenuItem>
              )}
              <MenuItem
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuAnchor(null);
                  onAddToCollectionClick?.(e);
                }}
              >
                <ListItemIcon>
                  {showRemoveButton ? (
                    <RemoveIcon fontSize="small" />
                  ) : (
                    <AddIcon fontSize="small" />
                  )}
                </ListItemIcon>
                <ListItemText>
                  {showRemoveButton
                    ? t("common.actions.removeFromCollection")
                    : t("common.actions.addToCollection")}
                </ListItemText>
              </MenuItem>
              {!isClipMode && (
                <MenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuAnchor(null);
                    onDeleteClick(e);
                  }}
                  sx={{
                    color: "error.main",
                    "&:hover": { bgcolor: (theme) => alpha(theme.palette.error.main, 0.08) },
                  }}
                >
                  <ListItemIcon>
                    <DeleteIcon fontSize="small" sx={{ color: "error.main" }} />
                  </ListItemIcon>
                  <ListItemText>{t("common.actions.delete")}</ListItemText>
                </MenuItem>
              )}
            </Menu>
          </Box>
        </Box>
      </Box>
    );
  }
);

AssetCardCompactInfo.displayName = "AssetCardCompactInfo";
export default AssetCardCompactInfo;
