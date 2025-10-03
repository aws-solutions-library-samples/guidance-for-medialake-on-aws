import React from "react";
import { Box, Typography, Stack, CircularProgress } from "@mui/material";
import { useNavigate } from "react-router-dom";
import {
  useGetFavorites,
  useRemoveFavorite,
} from "../../api/hooks/useFavorites";
import AssetCard from "../../components/shared/AssetCard";

export const Favorites: React.FC = () => {
  const navigate = useNavigate();
  const {
    data: unsortedFavorites,
    isLoading,
    error,
    refetch,
  } = useGetFavorites("ASSET");
  const { mutate: removeFavorite } = useRemoveFavorite();

  // Sort favorites by addedAt timestamp in descending order (newest first)
  const favorites = React.useMemo(() => {
    if (!unsortedFavorites) return [];

    return [...unsortedFavorites].sort((a, b) => {
      // If both have addedAt timestamps, compare them
      if (a.addedAt && b.addedAt) {
        return new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime();
      }

      // If only a has addedAt, it should come first (newer)
      if (a.addedAt && !b.addedAt) {
        return -1;
      }

      // If only b has addedAt, it should come first (newer)
      if (!a.addedAt && b.addedAt) {
        return 1;
      }

      // If neither has addedAt, maintain original order
      return 0;
    });
  }, [unsortedFavorites]);

  // Log when the component renders and when data changes
  console.log("Favorites component rendering with sorted data:", favorites);

  // Add effect to log when favorites data changes
  React.useEffect(() => {
    console.log("Favorites data changed:", unsortedFavorites);
    console.log("Sorted favorites:", favorites);
  }, [unsortedFavorites, favorites]);

  // Handle clicking on an asset to navigate to its detail page
  const handleAssetClick = (assetId: string, assetType: string) => {
    const pathPrefix =
      assetType.toLowerCase() === "audio"
        ? "/audio/"
        : `/${assetType.toLowerCase()}s/`;
    navigate(`${pathPrefix}${assetId}`);
  };

  // Handle toggling favorite status
  const handleFavoriteToggle = (
    assetId: string,
    itemType: string,
    event: React.MouseEvent<HTMLElement>,
  ) => {
    event.stopPropagation();
    removeFavorite({ itemId: assetId, itemType });
  };

  // Render loading state
  if (isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "200px",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Render error state
  if (error) {
    return (
      <Box>
        <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
          Favorites
        </Typography>
        <Typography color="error">
          Error loading favorites: {error.message}
        </Typography>
      </Box>
    );
  }

  // Render empty state
  if (!favorites || favorites.length === 0) {
    return (
      <Box>
        <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
          Favorites
        </Typography>
        <Typography color="text.secondary">No favorite assets yet</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
        Favorites
      </Typography>

      <Stack
        direction="row"
        spacing={2}
        sx={{
          overflowX: "auto",
          pb: 2,
          "&::-webkit-scrollbar": {
            height: "8px",
          },
          "&::-webkit-scrollbar-track": {
            backgroundColor: "rgba(0,0,0,0.05)",
            borderRadius: "4px",
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: "rgba(0,0,0,0.2)",
            borderRadius: "4px",
          },
        }}
      >
        {favorites.map((favorite) => (
          <Box
            key={favorite.itemId}
            sx={{
              minWidth: "250px",
              maxWidth: "250px",
            }}
          >
            <AssetCard
              id={favorite.itemId}
              name={favorite.metadata?.name || favorite.itemId}
              thumbnailUrl={favorite.metadata?.thumbnailUrl || ""}
              assetType={favorite.metadata?.assetType || "Unknown"}
              fields={[
                { id: "name", label: "Name", visible: true },
                { id: "type", label: "Type", visible: true },
              ]}
              renderField={(fieldId) => {
                if (fieldId === "name")
                  return favorite.metadata?.name || favorite.itemId;
                if (fieldId === "type")
                  return favorite.metadata?.assetType || "Unknown";
                return "";
              }}
              onAssetClick={() =>
                handleAssetClick(
                  favorite.itemId,
                  favorite.metadata?.assetType || "Unknown",
                )
              }
              onDeleteClick={() => {}} // Not used in this context
              onDownloadClick={() => {}} // Not used in this context
              isFavorite={true}
              onFavoriteToggle={(e) =>
                handleFavoriteToggle(favorite.itemId, favorite.itemType, e)
              }
              cardSize="medium"
              aspectRatio="square"
              thumbnailScale="fill"
              showMetadata={true}
            />
          </Box>
        ))}
      </Stack>
    </Box>
  );
};
