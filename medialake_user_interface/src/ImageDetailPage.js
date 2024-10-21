import React, { useState, useEffect } from 'react';
import { Box, Typography, Grid, Paper, CircularProgress } from '@mui/material';
import { useParams } from 'react-router-dom';

const ImageDetailPage = () => {
    const { id } = useParams();
    const [image, setImage] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchImage = async () => {
            try {
                // Simulate fetching image data based on the id
                const response = await fetch(`https://picsum.photos/id/${id}/info`);
                const data = await response.json();

                // Map the response data to the expected format
                const mappedImage = {
                    id: data.id,
                    src: data.download_url,
                    type: 'JPEG',
                    resolution: `${data.width}x${data.height}`,
                    colorSpace: 'sRGB',
                    fileSize: `${Math.round(data.size / 1024)} KB`,
                    iptc: {
                        creator: data.author,
                        copyright: `© ${new Date().getFullYear()} ${data.author}`,
                        caption: 'A beautiful image from Lorem Picsum',
                        keywords: ['picsum', 'random', 'image'],
                    },
                    exif: {
                        make: 'Unknown',
                        model: 'Unknown',
                        exposureTime: 'Unknown',
                        fNumber: 'Unknown',
                        iso: 'Unknown',
                        focalLength: 'Unknown',
                        dateTaken: data.date || 'Unknown',
                    },
                };

                setImage(mappedImage);
                setLoading(false);
            } catch (error) {
                console.error('Error fetching image:', error);
                setLoading(false);
            }
        };

        fetchImage();
    }, [id]);

    if (loading) {
        return <CircularProgress />;
    }

    if (!image) {
        return <Typography>Image not found</Typography>;
    }

    return (
        <Box sx={{ flexGrow: 1, p: 3 }}>
            <Grid container spacing={3}>
                <Grid item xs={12}>
                    <img src={image.src} alt="Detailed view" style={{ width: '100%', height: 'auto' }} />
                </Grid>
                <Grid item xs={12} md={6}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>Technical Details</Typography>
                        <Typography>Type: {image.type}</Typography>
                        <Typography>Resolution: {image.resolution}</Typography>
                        <Typography>Color Space: {image.colorSpace}</Typography>
                        <Typography>File Size: {image.fileSize}</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>IPTC Metadata</Typography>
                        <Typography>Creator: {image.iptc.creator}</Typography>
                        <Typography>Copyright: {image.iptc.copyright}</Typography>
                        <Typography>Caption: {image.iptc.caption}</Typography>
                        <Typography>Keywords: {image.iptc.keywords.join(', ')}</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>EXIF Data</Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>Make: {image.exif.make}</Typography>
                            </Grid>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>Model: {image.exif.model}</Typography>
                            </Grid>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>Exposure Time: {image.exif.exposureTime}</Typography>
                            </Grid>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>F-Number: {image.exif.fNumber}</Typography>
                            </Grid>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>ISO: {image.exif.iso}</Typography>
                            </Grid>
                            <Grid item xs={6} sm={4} md={3}>
                                <Typography>Focal Length: {image.exif.focalLength}</Typography>
                            </Grid>
                            <Grid item xs={12} sm={8} md={6}>
                                <Typography>Date Taken: {image.exif.dateTaken}</Typography>
                            </Grid>
                        </Grid>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ImageDetailPage;
