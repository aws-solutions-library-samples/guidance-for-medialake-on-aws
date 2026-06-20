import React from "react";
import { Box, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material";
import { useTranslation } from "react-i18next";
import type { Collection } from "../../api/hooks/useCollections";

export interface CollectionsFavoritesSectionProps {
  /** The favorited collections to render (joined live objects + metadata fallbacks). */
  favorites: Collection[];
  /**
   * Returns true when a favorite is backed by a live loaded object (and should
   * therefore get the owner-only action menu). Metadata fallback cards return
   * false so no wrongly-permissioned actions are shown.
   */
  isLive: (collectionId: string) => boolean;
  /** Renders a single favorite card; `withActions` gates the mutation menu. */
  renderCard: (collection: Collection, withActions: boolean) => React.ReactNode;
  /** Grid styling shared with the main collections grid. */
  gridSx?: SxProps<Theme>;
}

/**
 * The Favorites section shown at the top of the My Collections tab. Renders a
 * semantic heading followed by either a favorites-specific empty state or a grid
 * of favorited collection cards.
 */
export const CollectionsFavoritesSection: React.FC<CollectionsFavoritesSectionProps> = ({
  favorites,
  isLive,
  renderCard,
  gridSx,
}) => {
  const { t } = useTranslation();

  return (
    <Box component="section" sx={{ mb: 4 }}>
      <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 2 }}>
        {t("collectionsPage.favorites.sectionTitle", "Favorites")}
      </Typography>

      {favorites.length === 0 ? (
        <Box sx={{ py: 4, textAlign: "center" }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
            {t("collectionsPage.favorites.emptyTitle", "No Favorite Collections")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t(
              "collectionsPage.favorites.emptyDescription",
              "Collections you favorite will appear here"
            )}
          </Typography>
        </Box>
      ) : (
        <Box sx={gridSx} data-testid="favorites-grid">
          {favorites.map((collection) => renderCard(collection, isLive(collection.id)))}
        </Box>
      )}
    </Box>
  );
};

export default CollectionsFavoritesSection;
