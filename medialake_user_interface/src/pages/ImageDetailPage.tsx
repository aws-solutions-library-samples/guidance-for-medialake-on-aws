import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Paper, Grid, Button, IconButton, Divider, CircularProgress } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DownloadIcon from '@mui/icons-material/Download';

interface ImageData {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
    type?: string;
    resolution?: string;
    fileSize?: string;
}

// Mock API function to simulate fetching image data
const fetchImageData = async (id: string): Promise<ImageData> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // Mock data
    const mockData: Record<string, ImageData> = {
        '1': {
            src: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470',
            id: 1,
            fileName: 'Mountain Lake',
            creationDate: '2023-05-10T09:15:00Z',
            description: 'A serene mountain lake view',
            type: 'image/jpeg',
            resolution: '1920x1080',
            fileSize: '2.5 MB'
        },
        '2': {
            src: 'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05',
            id: 2,
            fileName: 'River Valley',
            creationDate: '2023-05-11T16:45:00Z',
            description: 'A beautiful river flowing through a valley',
            type: 'image/jpeg',
            resolution: '1920x1080',
            fileSize: '3.1 MB'
        },
        '3': {
            src: 'https://images.unsplash.com/photo-1511497584788-876760111969',
            id: 3,
            fileName: 'Misty Forest',
            creationDate: '2023-05-12T11:30:00Z',
            description: 'A mysterious misty forest landscape',
            type: 'image/jpeg',
            resolution: '1920x1080',
            fileSize: '2.8 MB'
        }
    };

    if (!mockData[id]) {
        throw new Error('Image not found');
    }

    return mockData[id];
};

const ImageDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [imageData, setImageData] = useState<ImageData | null>(null);

    useEffect(() => {
        const loadImage = async () => {
            if (!id) {
                setError('No image ID provided');
                setLoading(false);
                return;
            }

            try {
                const data = await fetchImageData(id);
                setImageData(data);
                setError(null);
            } catch (err) {
                setError('Image not found');
                setImageData(null);
            } finally {
                setLoading(false);
            }
        };

        loadImage();
    }, [id]);

    const handleBack = () => {
        navigate('/search');
    };

    if (loading) {
        return (
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: 'calc(100vh - 100px)'
            }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error || !imageData) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="h5" color="error" gutterBottom>
                    {error || 'Error loading image'}
                </Typography>
                <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={handleBack}
                    variant="contained"
                    sx={{ mt: 2 }}
                >
                    Back to Search
                </Button>
            </Box>
        );
    }

    return (
        <Box sx={{ flexGrow: 1, p: 3, maxWidth: '1600px', margin: '0 auto' }}>
            <Button
                startIcon={<ArrowBackIcon />}
                onClick={handleBack}
                variant="contained"
                sx={{ mb: 3 }}
            >
                Back to Search
            </Button>

            <Grid container spacing={3}>
                <Grid item xs={12} md={8}>
                    <Paper
                        elevation={3}
                        sx={{
                            p: 2,
                            position: 'relative',
                            overflow: 'hidden',
                            borderRadius: 2
                        }}
                    >
                        <img
                            src={imageData.src}
                            alt={imageData.fileName}
                            style={{
                                width: '100%',
                                height: 'auto',
                                maxHeight: '70vh',
                                objectFit: 'contain',
                                display: 'block'
                            }}
                        />
                        <IconButton
                            sx={{
                                position: 'absolute',
                                top: 8,
                                right: 8,
                                bgcolor: 'rgba(255, 255, 255, 0.8)',
                                '&:hover': {
                                    bgcolor: 'rgba(255, 255, 255, 0.9)'
                                }
                            }}
                            title="Download original"
                        >
                            <DownloadIcon />
                        </IconButton>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={4}>
                    <Paper
                        elevation={3}
                        sx={{
                            p: 3,
                            borderRadius: 2
                        }}
                    >
                        <Typography variant="h5" gutterBottom>
                            {imageData.fileName}
                        </Typography>
                        <Typography variant="body1" color="text.secondary" paragraph>
                            {imageData.description}
                        </Typography>
                        <Divider sx={{ my: 2 }} />
                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2" color="text.secondary">
                                    Created
                                </Typography>
                                <Typography variant="body1">
                                    {new Date(imageData.creationDate).toLocaleDateString()}
                                </Typography>
                            </Grid>
                            {imageData.type && (
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2" color="text.secondary">
                                        Type
                                    </Typography>
                                    <Typography variant="body1">
                                        {imageData.type}
                                    </Typography>
                                </Grid>
                            )}
                            {imageData.resolution && (
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2" color="text.secondary">
                                        Resolution
                                    </Typography>
                                    <Typography variant="body1">
                                        {imageData.resolution}
                                    </Typography>
                                </Grid>
                            )}
                            {imageData.fileSize && (
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2" color="text.secondary">
                                        File Size
                                    </Typography>
                                    <Typography variant="body1">
                                        {imageData.fileSize}
                                    </Typography>
                                </Grid>
                            )}
                        </Grid>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ImageDetailPage;
