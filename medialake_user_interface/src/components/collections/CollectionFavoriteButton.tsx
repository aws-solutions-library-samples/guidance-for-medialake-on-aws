import React from "react";
import { IconButton } from "@mui/material";
import {
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

export interface CollectionFavoriteButtonProps {
  /** Whether the collection is currently in the user's favorites. */
  isFavorite: boolean;
  /** Fired when the toggle is activated. */
  onToggle: (event: React.MouseEvent<HTMLElement>) => void;
  size?: "small" | "medium";
}

/**
 * Plain heart toggle used in the collection detail page header (not an overlay).
 * Mirrors the asset favorite UX: filled red heart when favorited, outline
 * otherwise, with an accessible label that names the action and reflects state.
 */
export const CollectionFavoriteButton: React.FC<CollectionFavoriteButtonProps> = ({
  isFavorite,
  onToggle,
  size = "medium",
}) => {
  const { t } = useTranslation();
  const label = isFavorite ? t("favorites.removeFavorite") : t("favorites.addFavorite");

  return (
    <IconButton
      size={size}
      onClick={(e) => {
        e.stopPropagation();
        onToggle(e);
      }}
      aria-label={label}
      title={label}
      data-testid="collection-favorite-button"
      sx={{ color: isFavorite ? "error.main" : "primary.main" }}
    >
      {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
    </IconButton>
  );
};

export default CollectionFavoriteButton;
