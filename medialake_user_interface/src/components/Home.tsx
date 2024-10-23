import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Box,
    Typography,
    Grid,
    Card,
    CardContent,
    CardActions,
    Button,
    CircularProgress,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';

interface SmartFolder {
    id: number;
    name: string;
    description: string;
}

const fetchSmartFolders = async (): Promise<SmartFolder[]> => {
    // Replace this with your actual API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    return [
        { id: 1, name: 'Recent Searches', description: 'Your recent search queries' },
        { id: 2, name: 'Favorites', description: 'Your favorite search results' },
        { id: 3, name: 'Most Viewed', description: 'Your most frequently viewed results' },
        { id: 4, name: 'Custom Folder 1', description: 'A custom folder you created' },
    ];
};

const Home: React.FC = () => {
    const { data: smartFolders, isLoading } = useQuery<SmartFolder[]>({
        queryKey: ['smartFolders'],
        queryFn: fetchSmartFolders,
    });

    if (isLoading) return <CircularProgress />;

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Smart Folders
            </Typography>
            <Grid container spacing={2}>
                {smartFolders?.map((folder) => (
                    <Grid item xs={12} sm={6} md={3} key={folder.id}>
                        <Card>
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <FolderIcon sx={{ fontSize: 40, mr: 2 }} />
                                    <Typography variant="h6">{folder.name}</Typography>
                                </Box>
                                <Typography variant="body2" color="text.secondary">
                                    {folder.description}
                                </Typography>
                            </CardContent>
                            <CardActions>
                                <Button size="small">Open</Button>
                                <Button size="small">Edit</Button>
                            </CardActions>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};

export default Home;
