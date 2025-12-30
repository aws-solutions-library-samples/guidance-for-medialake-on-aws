import React, { useMemo } from "react";
import { Card, CardContent, CardMedia, Typography, Box, IconButton } from "@mui/material";
import {
  MoreVert,
  FolderOpen,
  Folder,
  Work,
  Campaign,
  Assignment,
  Archive,
  PhotoLibrary,
  Label,
  Movie,
  Collections,
  Dashboard,
  Storage,
  Inventory,
  Category,
  BookmarkBorder,
  LocalOffer,
} from "@mui/icons-material";
import { useGetCollectionTypes } from "@/api/hooks/useCollections";
import type { Collection } from "../../types/collection";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <Folder />,
  FolderOpen: <FolderOpen />,
  Work: <Work />,
  Campaign: <Campaign />,
  Assignment: <Assignment />,
  Archive: <Archive />,
  PhotoLibrary: <PhotoLibrary />,
  Label: <Label />,
  Movie: <Movie />,
  Collections: <Collections />,
  Dashboard: <Dashboard />,
  Storage: <Storage />,
  Inventory: <Inventory />,
  Category: <Category />,
  BookmarkBorder: <BookmarkBorder />,
  LocalOffer: <LocalOffer />,
};

interface CollectionCardProps {
  collection: Collection;
  onOpen?: (id: string) => void;
}

export const CollectionCard: React.FC<CollectionCardProps> = ({ collection }) => {
  // Fetch collection types to get icon and color
  const { data: collectionTypesResponse, isLoading: isLoadingTypes } = useGetCollectionTypes();
  const collectionTypes = collectionTypesResponse?.data || [];

  // Find the collection type for this collection
  const collectionType = useMemo(() => {
    if (!collection.collectionTypeId || isLoadingTypes) return null;
    return collectionTypes.find((type) => type.id === collection.collectionTypeId) || null;
  }, [collection.collectionTypeId, collectionTypes, isLoadingTypes]);

  // Get the icon to display
  const displayIcon = useMemo(() => {
    if (collectionType?.icon && ICON_MAP[collectionType.icon]) {
      return React.cloneElement(ICON_MAP[collectionType.icon], {
        sx: { fontSize: 60, color: collectionType.color || "grey.400" },
      });
    }
    return (
      <FolderOpen
        sx={{
          fontSize: 60,
          color: (theme) => theme.palette.grey[400],
        }}
      />
    );
  }, [collectionType]);

  return (
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRadius: 3,
        border: collectionType?.color ? `2px solid ${collectionType.color}` : "2px solid",
        borderColor: collectionType?.color || "divider",
        overflow: "visible", // Prevent clipping on hover
        transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-4px)",
          boxShadow: (theme) => theme.shadows[4],
        },
      }}
    >
      <CardMedia
        component="div"
        sx={{
          height: 140,
          backgroundColor: (theme) =>
            collection.thumbnailUrl ? "transparent" : theme.palette.grey[200],
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {!collection.thumbnailUrl && displayIcon}
        {collection.thumbnailUrl && (
          <img
            src={collection.thumbnailUrl}
            alt={collection.name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </CardMedia>
      <CardContent sx={{ flexGrow: 1, pb: 2 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <Box>
            <Typography variant="h6" component="h3" noWrap>
              {collection.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {collection.itemCount} items
            </Typography>
          </Box>
          <IconButton size="small">
            <MoreVert />
          </IconButton>
        </Box>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {collection.description}
        </Typography>
      </CardContent>
    </Card>
  );
};
