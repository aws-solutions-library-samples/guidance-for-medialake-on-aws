import React from 'react';
import { Box, Typography, Grid, Tabs, Tab } from '@mui/material';
import { CollectionCard } from './CollectionCard';
import type { Collection } from '../../types/collection';

const sampleFavorites: Collection[] = [
    {
        id: '7',
        name: 'Best Shots 2024',
        description: 'Curated collection of the best shots from various projects.',
        itemCount: 42,
        createdAt: '2024-01-15T12:00:00Z',
        lastModified: '2024-03-16T15:45:00Z'
    }
];

export const Favorites: React.FC = () => {
    const [tabValue, setTabValue] = React.useState(0);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
    };

    return (
        <Box>
            <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
                Favorites
            </Typography>
            <Tabs
                value={tabValue}
                onChange={handleTabChange}
                sx={{ mb: 3 }}
            >
                <Tab label="Collections" />
                <Tab label="Assets" />
                <Tab label="Workflows" />
            </Tabs>

            {tabValue === 0 && (
                <Grid container spacing={3}>
                    {sampleFavorites.map((collection) => (
                        <Grid item xs={12} sm={6} md={4} key={collection.id}>
                            <CollectionCard collection={collection} />
                        </Grid>
                    ))}
                </Grid>
            )}
            {tabValue === 1 && (
                <Typography color="text.secondary">
                    No favorite assets yet
                </Typography>
            )}
            {tabValue === 2 && (
                <Typography color="text.secondary">
                    No favorite workflows yet
                </Typography>
            )}
        </Box>
    );
}; 