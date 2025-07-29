import React from "react";
import { Grid, Typography, Box, Button } from "@mui/material";
import { CollectionCard } from "@/features/home/CollectionCard";
import { Add } from "@mui/icons-material";
import type { Collection } from "../../types/collection";

const sampleCollections: Collection[] = [
  {
    id: "1",
    name: "Summer Campaign 2024",
    description:
      "Marketing assets for the upcoming summer campaign including photos and videos from the beach photoshoot.",
    itemCount: 124,
    createdAt: "2024-01-15T10:00:00Z",
    lastModified: "2024-03-10T15:30:00Z",
  },
  {
    id: "2",
    name: "Product Launches",
    description:
      "All media assets related to new product launches, including promotional materials and product photos.",
    itemCount: 89,
    createdAt: "2024-02-01T09:00:00Z",
    lastModified: "2024-03-15T11:20:00Z",
  },
  {
    id: "3",
    name: "Brand Guidelines",
    description:
      "Official brand assets including logos, color palettes, and typography examples.",
    itemCount: 45,
    createdAt: "2024-01-01T08:00:00Z",
    lastModified: "2024-03-01T14:15:00Z",
  },
  {
    id: "4",
    name: "Social Media Content",
    description:
      "Curated collection of images and videos optimized for various social media platforms.",
    thumbnailUrl: "/sample-images/social-media.jpg",
    itemCount: 256,
    createdAt: "2024-02-15T13:00:00Z",
    lastModified: "2024-03-16T09:45:00Z",
  },
];

export const Collections: React.FC = () => {
  const handleOpenCollection = (id: string) => {
    console.log(`Opening collection ${id}`);
  };

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          mb: 3,
          alignItems: "center",
        }}
      >
        <Typography variant="h5" component="h2">
          My Collections
        </Typography>
        <Button variant="contained" startIcon={<Add />} size="small">
          New Collection
        </Button>
      </Box>
      <Grid container spacing={3}>
        {sampleCollections.map((collection) => (
          <Grid item xs={12} sm={6} md={4} key={collection.id}>
            <CollectionCard
              collection={collection}
              onOpen={handleOpenCollection}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};
