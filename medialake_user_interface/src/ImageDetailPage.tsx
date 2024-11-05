import React, { useState, useEffect } from 'react';
import { Box, Typography, Grid, Paper, CircularProgress, useTheme, Chip, Button, Divider, Card, CardMedia, CardContent, IconButton, Tooltip } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import InfoIcon from '@mui/icons-material/Info';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

interface Image {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
    mediaType: 'video' | 'image' | 'audio';
    type?: string;
    resolution?: string;
    colorSpace?: string;
    fileSize?: string;
    iptc?: {
        creator: string;
        copyright: string;
        caption: string;
        keywords: string[];
    };
    exif?: {
        make: string;
        model: string;
        exposureTime: string;
        fNumber: string;
        iso: string;
        focalLength: string;
        dateTaken: string;
    };
    xmp?: {
        title: string;
        creator: string;
        subject: string[];
        description: string;
        rating: number;
        license: string;
    };
    contentAnalysis?: {
        summary: string;
        detectedObjects: string[];
        people: string[];
        landmarks: string[];
        tags: string[];
        aiGenerated: boolean;
    };
}

interface Pipeline {
    id: string;
    name: string;
    description: string;
    icon: string;
    estimatedTime: string;
}

const ImageDetailPage: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const theme = useTheme();
    const [loading, setLoading] = useState(true);
    const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
    const image = location.state?.image as Image;

    const [relatedVersions] = useState([
        {
            id: '1',
            src: image?.src,
            type: 'Thumbnail',
            description: 'Compressed thumbnail version',
            createdAt: new Date().toISOString()
        },
        {
            id: '2',
            src: image?.src,
            type: 'High Resolution',
            description: 'Original high resolution version',
            createdAt: new Date().toISOString()
        },
        {
            id: '3',
            src: image?.src,
            type: 'Web Optimized',
            description: 'Optimized for web display',
            createdAt: new Date().toISOString()
        }
    ]);

    const availablePipelines: Pipeline[] = [
        {
            id: 'p1',
            name: 'Image Enhancement',
            description: 'Enhance image quality and colors',
            icon: '🎨',
            estimatedTime: '2-3 minutes'
        },
        {
            id: 'p2',
            name: 'Object Detection',
            description: 'Detect and label objects in the image',
            icon: '🔍',
            estimatedTime: '1-2 minutes'
        },
        {
            id: 'p3',
            name: 'Face Recognition',
            description: 'Identify and tag faces in the image',
            icon: '👤',
            estimatedTime: '1-2 minutes'
        },
        {
            id: 'p4',
            name: 'Background Removal',
            description: 'Remove background and create transparent version',
            icon: '✂️',
            estimatedTime: '2-4 minutes'
        }
    ];

    useEffect(() => {
        if (image) {
            setLoading(false);
        }
    }, [image]);

    const handlePipelineExecution = (pipelineId: string) => {
        console.log(`Executing pipeline: ${pipelineId}`);
        // Implementation for pipeline execution
    };

    const handleBack = () => {
        navigate(-1);
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!image) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="h5">Image not found</Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={handleBack} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }

    return (
        <Box sx={{ flexGrow: 1, p: 3, maxWidth: '1600px', margin: '0 auto' }}>
            <Button startIcon={<ArrowBackIcon />} onClick={handleBack} sx={{ mb: 3 }}>
                Back to Search Results
            </Button>

            <Grid container spacing={3}>
                {/* Main Image Display */}
                <Grid item xs={12} md={8}>
                    <Paper elevation={3} sx={{ p: 2, position: 'relative' }}>
                        <img
                            src={image.src}
                            alt={image.fileName}
                            style={{
                                width: '100%',
                                height: 'auto',
                                maxHeight: '70vh',
                                objectFit: 'contain'
                            }}
                        />
                        <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
                            <Tooltip title="Download Original">
                                <IconButton color="primary">
                                    <DownloadIcon />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    </Paper>
                </Grid>

                {/* Quick Info and Actions */}
                <Grid item xs={12} md={4}>
                    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                        <Typography variant="h6" gutterBottom>{image.fileName}</Typography>
                        <Typography variant="body2" color="text.secondary" paragraph>
                            {image.description}
                        </Typography>
                        <Divider sx={{ my: 2 }} />
                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Resolution</Typography>
                                <Typography variant="body2">{image.resolution}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">File Size</Typography>
                                <Typography variant="body2">{image.fileSize}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Color Space</Typography>
                                <Typography variant="body2">{image.colorSpace}</Typography>
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Created</Typography>
                                <Typography variant="body2">
                                    {new Date(image.creationDate).toLocaleDateString()}
                                </Typography>
                            </Grid>
                        </Grid>
                    </Paper>

                    {/* Content Analysis */}
                    {image.contentAnalysis && (
                        <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>Content Analysis</Typography>
                            <Typography variant="body2" paragraph>
                                {image.contentAnalysis.summary}
                            </Typography>
                            <Box sx={{ mb: 1 }}>
                                <Typography variant="subtitle2" gutterBottom>Detected Objects:</Typography>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                    {image.contentAnalysis.detectedObjects.map((obj, index) => (
                                        <Chip key={index} label={obj} size="small" />
                                    ))}
                                </Box>
                            </Box>
                            {image.contentAnalysis.people.length > 0 && (
                                <Box sx={{ mb: 1 }}>
                                    <Typography variant="subtitle2" gutterBottom>People:</Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {image.contentAnalysis.people.map((person, index) => (
                                            <Chip key={index} label={person} size="small" />
                                        ))}
                                    </Box>
                                </Box>
                            )}
                        </Paper>
                    )}
                </Grid>

                {/* Related Versions */}
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                        <Typography variant="h6" gutterBottom>Related Versions</Typography>
                        <Grid container spacing={2}>
                            {relatedVersions.map((version) => (
                                <Grid item xs={12} sm={6} md={4} key={version.id}>
                                    <Card>
                                        <CardMedia
                                            component="img"
                                            height="140"
                                            image={version.src}
                                            alt={version.type}
                                        />
                                        <CardContent>
                                            <Typography variant="h6">{version.type}</Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                {version.description}
                                            </Typography>
                                            <Typography variant="caption" display="block">
                                                Created: {new Date(version.createdAt).toLocaleDateString()}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </Grid>

                {/* Metadata Sections */}
                <Grid item xs={12} md={6}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>IPTC Metadata</Typography>
                        {image.iptc && (
                            <Grid container spacing={2}>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Creator</Typography>
                                    <Typography variant="body2">{image.iptc.creator}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Copyright</Typography>
                                    <Typography variant="body2">{image.iptc.copyright}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Caption</Typography>
                                    <Typography variant="body2">{image.iptc.caption}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Keywords</Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                                        {image.iptc.keywords.map((keyword, index) => (
                                            <Chip key={index} label={keyword} size="small" />
                                        ))}
                                    </Box>
                                </Grid>
                            </Grid>
                        )}
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>EXIF Data</Typography>
                        {image.exif && (
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Camera Make</Typography>
                                    <Typography variant="body2">{image.exif.make}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Model</Typography>
                                    <Typography variant="body2">{image.exif.model}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Exposure Time</Typography>
                                    <Typography variant="body2">{image.exif.exposureTime}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">F-Number</Typography>
                                    <Typography variant="body2">{image.exif.fNumber}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">ISO</Typography>
                                    <Typography variant="body2">{image.exif.iso}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Focal Length</Typography>
                                    <Typography variant="body2">{image.exif.focalLength}</Typography>
                                </Grid>
                            </Grid>
                        )}
                    </Paper>
                </Grid>

                {/* Available Pipelines */}
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>Available Pipelines</Typography>
                        <Grid container spacing={2}>
                            {availablePipelines.map((pipeline) => (
                                <Grid item xs={12} sm={6} md={3} key={pipeline.id}>
                                    <Card>
                                        <CardContent>
                                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                                <Typography variant="h3" sx={{ mr: 1 }}>{pipeline.icon}</Typography>
                                                <Typography variant="h6">{pipeline.name}</Typography>
                                            </Box>
                                            <Typography variant="body2" color="text.secondary" paragraph>
                                                {pipeline.description}
                                            </Typography>
                                            <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                                                Estimated time: {pipeline.estimatedTime}
                                            </Typography>
                                            <Button
                                                variant="contained"
                                                startIcon={<PlayArrowIcon />}
                                                onClick={() => handlePipelineExecution(pipeline.id)}
                                                fullWidth
                                            >
                                                Execute
                                            </Button>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ImageDetailPage;
