import React from "react";
import {
  Card,
  CardContent,
  CardMedia,
  Typography,
  Box,
  IconButton,
} from "@mui/material";
import { MoreVert, FolderOpen } from "@mui/icons-material";
import type { Collection } from "../../types/collection";

interface CollectionCardProps {
  collection: Collection;
  onOpen?: (id: string) => void;
}

export const CollectionCard: React.FC<CollectionCardProps> = ({
  collection,
  onOpen,
}) => {
  return (
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
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
        {!collection.thumbnailUrl && (
          <FolderOpen
            sx={{
              fontSize: 60,
              color: (theme) => theme.palette.grey[400],
            }}
          />
        )}
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
