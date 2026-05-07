/**
 * AssetCardActions — the bottom action bar for the full variant.
 * Download, Collection, Detail, Favorite, Delete buttons.
 */
import React from "react";
import { Box, IconButton, Button } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderIcon from "@mui/icons-material/FavoriteBorder";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";

interface AssetCardActionsProps {
  isClipMode: boolean;
  isFavorite: boolean;
  showRemoveButton: boolean;
  canDelete?: boolean;
  onAssetClick: () => void;
  onDeleteClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (event: React.MouseEvent<HTMLElement>) => void;
  onFavoriteToggle?: (event: React.MouseEvent<HTMLElement>) => void;
}

const actionBtnSx = {
  color: "primary.main",
  "&:hover": { bgcolor: "primary.main", color: "primary.contrastText" },
};

const AssetCardActions: React.FC<AssetCardActionsProps> = React.memo(
  ({
    isClipMode,
    isFavorite,
    showRemoveButton,
    canDelete = true,
    onAssetClick,
    onDeleteClick,
    onDownloadClick,
    onAddToCollectionClick,
    onFavoriteToggle,
  }) => {
    const { t } = useTranslation();

    return (
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 0.5,
          px: 1,
          py: 0.75,
          bgcolor: "background.paper",
          borderTop: "1px solid",
          borderColor: (theme) => alpha(theme.palette.divider, 0.08),
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {!isClipMode && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onDownloadClick?.(e);
            }}
            sx={actionBtnSx}
            title={t("common.actions.download")}
          >
            <DownloadIcon fontSize="small" />
          </IconButton>
        )}
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            onAddToCollectionClick?.(e);
          }}
          sx={actionBtnSx}
          title={
            showRemoveButton
              ? t("common.actions.removeFromCollection")
              : t("common.actions.addToCollection")
          }
        >
          {showRemoveButton ? <RemoveIcon fontSize="small" /> : <AddIcon fontSize="small" />}
        </IconButton>
        <Button
          size="small"
          variant="outlined"
          onClick={(e) => {
            e.stopPropagation();
            onAssetClick();
          }}
          sx={{
            flex: 1,
            mx: 0.5,
            minWidth: "40px",
            fontSize: "0.7rem",
            py: 0.4,
            textTransform: "none",
            borderColor: (theme) => alpha(theme.palette.primary.main, 0.3),
          }}
          title={t("common.actions.assetDetail")}
        >
          <Box
            sx={{
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              width: "100%",
              textAlign: "center",
            }}
          >
            {t("common.actions.assetDetail")}
          </Box>
        </Button>
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            onFavoriteToggle?.(e);
          }}
          sx={{
            color: isFavorite ? "error.main" : "primary.main",
            "&:hover": {
              bgcolor: isFavorite ? "error.main" : "primary.main",
              color: "primary.contrastText",
            },
          }}
          title={isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite")}
          data-testid="favorite-button"
        >
          {isFavorite ? <FavoriteIcon fontSize="small" /> : <FavoriteBorderIcon fontSize="small" />}
        </IconButton>
        {!isClipMode && canDelete && (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onDeleteClick?.(e);
            }}
            sx={actionBtnSx}
            title={t("common.actions.delete")}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        )}
      </Box>
    );
  }
);

AssetCardActions.displayName = "AssetCardActions";
export default AssetCardActions;
