import React from "react";
import { Box, Typography, Grid } from "@mui/material";
import { CollectionCard } from "./CollectionCard";
import type { Collection } from "../../types/collection";

const sampleSharedCollections: Collection[] = [
  {
    id: "5",
    name: "Marketing Assets 2024",
    description: "Shared marketing assets for the year 2024 campaigns.",
    itemCount: 89,
    createdAt: "2024-01-01T00:00:00Z",
    lastModified: "2024-03-15T14:30:00Z",
  },
  {
    id: "6",
    name: "Client Deliverables",
    description: "Final deliverables for client projects.",
    itemCount: 34,
    createdAt: "2024-02-15T10:00:00Z",
    lastModified: "2024-03-16T09:00:00Z",
  },
];

export const SharedCollections: React.FC = () => {
  return (
    <Box>
      <Typography variant="h5" component="h2" sx={{ mb: 3 }}>
        Shared Collections
      </Typography>
      <Grid container spacing={3}>
        {sampleSharedCollections.map((collection) => (
          <Grid item xs={12} sm={6} md={4} key={collection.id}>
            <CollectionCard collection={collection} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};
