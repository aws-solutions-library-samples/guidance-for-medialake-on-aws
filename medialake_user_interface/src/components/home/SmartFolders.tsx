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
    useTheme,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import EditIcon from '@mui/icons-material/Edit';

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

export const SmartFolders: React.FC = () => {
    const theme = useTheme();
    const { data: smartFolders, isLoading } = useQuery<SmartFolder[]>({
        queryKey: ['smartFolders'],
        queryFn: fetchSmartFolders,
    });

    if (isLoading) {
        return (
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: 200
            }}>
                <CircularProgress size={40} thickness={4} />
            </Box>
        );
    }

    return (
        <Box>
            <Typography
                variant="h5"
                component="h2"
                gutterBottom
                sx={{
                    fontWeight: 600,
                    color: theme.palette.primary.main,
                    mb: 3,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1
                }}
            >
                <FolderIcon sx={{ fontSize: 28 }} />
                Smart Folders
            </Typography>
            <Grid container spacing={3}>
                {smartFolders?.map((folder) => (
                    <Grid item xs={12} sm={6} md={3} key={folder.id}>
                        <Card
                            sx={{
                                height: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                transition: 'all 0.3s ease-in-out',
                                '&:hover': {
                                    transform: 'translateY(-4px)',
                                    boxShadow: theme.shadows[8],
                                    '& .folder-icon': {
                                        transform: 'scale(1.1)',
                                        color: theme.palette.primary.main,
                                    }
                                },
                                borderRadius: 2,
                                overflow: 'hidden',
                                border: '1px solid',
                                borderColor: theme.palette.divider,
                            }}
                        >
                            <CardContent sx={{ flexGrow: 1, p: 3 }}>
                                <Box
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        mb: 2
                                    }}
                                >
                                    <FolderIcon
                                        className="folder-icon"
                                        sx={{
                                            fontSize: 40,
                                            mr: 2,
                                            color: theme.palette.text.secondary,
                                            transition: 'all 0.3s ease-in-out'
                                        }}
                                    />
                                    <Typography
                                        variant="h6"
                                        sx={{
                                            fontWeight: 500,
                                            color: theme.palette.text.primary
                                        }}
                                    >
                                        {folder.name}
                                    </Typography>
                                </Box>
                                <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{
                                        lineHeight: 1.6,
                                        opacity: 0.8
                                    }}
                                >
                                    {folder.description}
                                </Typography>
                            </CardContent>
                            <CardActions
                                sx={{
                                    p: 2,
                                    pt: 0,
                                    gap: 1
                                }}
                            >
                                <Button
                                    size="small"
                                    variant="contained"
                                    startIcon={<OpenInNewIcon />}
                                    sx={{
                                        borderRadius: 1.5,
                                        textTransform: 'none',
                                        boxShadow: 'none',
                                        '&:hover': {
                                            boxShadow: 'none'
                                        }
                                    }}
                                >
                                    Open
                                </Button>
                                <Button
                                    size="small"
                                    startIcon={<EditIcon />}
                                    sx={{
                                        borderRadius: 1.5,
                                        textTransform: 'none'
                                    }}
                                >
                                    Edit
                                </Button>
                            </CardActions>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};
