import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAsset, Asset } from '../api/hooks/useAssets';
import { Box, Typography, Grid, Paper, CircularProgress, useTheme, Chip, Button, Divider, Card, CardMedia, CardContent, IconButton, Tooltip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import InfoIcon from '@mui/icons-material/Info';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { ImageViewer } from '../components/common/ImageViewer'

interface Pipeline {
    id: string;
    name: string;
    description: string;
    icon: string;
    estimatedTime: string;
}

const ImageDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();


    const [derivedRepresentations] = useState(() => {
        if (!assetData?.data) return [];

        const representations = [
            // Include the original (master) representation
            {
                id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
                src: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: 'Original',
                description: 'Original high resolution version',
                createdAt: assetData.data.asset.DigitalSourceAsset.CreateDate,
                format: assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format,
                size: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size
            },
            // Dynamically add all DerivedRepresentations
            ...assetData.data.asset.DerivedRepresentations.map(rep => ({
                id: rep.ID,
                src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: rep.Purpose.charAt(0).toUpperCase() + rep.Purpose.slice(1), // Capitalize the purpose
                description: `${rep.Purpose} version`,
                createdAt: new Date().toISOString(), // Note: Actual creation date not provided in the data
                format: rep.Format,
                size: rep.StorageInfo.PrimaryLocation.FileInfo.Size,
                resolution: rep.ImageSpec?.Resolution
                    ? `${rep.ImageSpec.Resolution.Width}x${rep.ImageSpec.Resolution.Height}`
                    : undefined
            }))
        ];

        return representations;
    });


    const [availablePipelines] = useState([
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
        }
    ]);

    const handlePipelineExecution = (pipelineId: string) => {
        console.log(`Executing pipeline: ${pipelineId}`);
        // Implementation for pipeline execution
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error || !assetData) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="h5" color="error">
                    {error ? 'Error loading asset details' : 'Asset not found'}
                </Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }

    const getProxyUrl = () => {
        if (assetData?.data?.asset?.DerivedRepresentations) {
            const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
            if (proxyRep) {
                return proxyRep.URL;
            }
        }
        return assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Path;
    };

    const proxyUrl = getProxyUrl();

    console.log(proxyUrl)

    return (
        <Box sx={{ flexGrow: 1, p: 3, maxWidth: '1600px', margin: '0 auto' }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 3 }}>
                Back to Search Results
            </Button>

            <Grid container spacing={3}>
                {/* Main Image Display */}
                <Grid item xs={12} md={8}>
                    <Paper elevation={3} sx={{ p: 2, position: 'relative' }}>
                        {/* <img
                            src={proxyUrl}
                            alt={assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Path}
                            style={{
                                width: '100%',
                                height: 'auto',
                                maxHeight: '70vh',
                                objectFit: 'contain'
                            }}
                        /> */}
                        <ImageViewer
                            imageSrc={proxyUrl}
                            maxHeight={600}
                        />
                        {/* <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
                            <Tooltip title="Download Original">
                                <IconButton color="primary">
                                    <DownloadIcon />
                                </IconButton>
                            </Tooltip>
                        </Box> */}
                    </Paper>
                </Grid>

                {/* Quick Info and Actions */}
                <Grid item xs={12} md={4}>
                    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                        <Typography variant="h6" gutterBottom>{assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Path}</Typography>
                        {/* <Typography variant="body2" color="text.secondary" paragraph>
                            {asset.Metadata.Description}
                        </Typography> */}
                        <Divider sx={{ my: 2 }} />
                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Resolution</Typography>
                                {/* <Typography variant="body2">{asset.Metadata.resolution}</Typography> */}
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">File Size</Typography>
                                {/* <Typography variant="body2">{asset.Metadata.fileSize}</Typography> */}
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Color Space</Typography>
                                {/* <Typography variant="body2">{asset.Metadata.colorSpace}</Typography> */}
                            </Grid>
                            <Grid item xs={6}>
                                <Typography variant="subtitle2">Created</Typography>
                                <Typography variant="body2">
                                    {new Date(assetData.data.asset.DigitalSourceAsset.CreateDate).toLocaleDateString()}
                                </Typography>
                            </Grid>
                        </Grid>
                    </Paper>

                    {/* Content Analysis */}
                    {/* {asset.Metadata.contentAnalysis && (
                        <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>Content Analysis</Typography>
                            <Typography variant="body2" paragraph>
                                {asset.Metadata.contentAnalysis.summary}
                            </Typography>
                            <Box sx={{ mb: 1 }}>
                                <Typography variant="subtitle2" gutterBottom>Detected Objects:</Typography>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                    {asset.Metadata.contentAnalysis.detectedObjects.map((obj, index) => (
                                        <Chip key={index} label={obj} size="small" />
                                    ))}
                                </Box>
                            </Box>
                            {asset.Metadata.contentAnalysis.people.length > 0 && (
                                <Box sx={{ mb: 1 }}>
                                    <Typography variant="subtitle2" gutterBottom>People:</Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {asset.Metadata.contentAnalysis.people.map((person, index) => (
                                            <Chip key={index} label={person} size="small" />
                                        ))}
                                    </Box>
                                </Box>
                            )}
                        </Paper>
                    )} */}
                </Grid>

                {/* Related Versions */}
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                        <Typography variant="h6" gutterBottom>Related Versions</Typography>
                        <Grid container spacing={2}>
                            {derivedRepresentations.map((version) => (
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
                        {assetData.data.asset.Metadata.CustomMetadata.IPTC && (
                            <Grid container spacing={2}>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Creator</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.IPTC?.creator}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Copyright</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.IPTC?.copyright}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Caption</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.IPTC?.caption}</Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="subtitle2">Keywords</Typography>
                                    {/* <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                                        {assetData.data.asset.Metadata.CustomMetadata.IPTC?.keywords.map((keyword, index) => (
                                            <Chip key={index} label={keyword} size="small" />
                                        ))}
                                    </Box> */}
                                </Grid>
                            </Grid>
                        )}
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>EXIF Data</Typography>
                        {assetData.data.asset.Metadata.CustomMetadata.EXIF && (
                            <Grid container spacing={2}>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Camera Make</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.make}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Model</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.model}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Exposure Time</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.exposureTime}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">F-Number</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.fNumber}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">ISO</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.iso}</Typography>
                                </Grid>
                                <Grid item xs={6}>
                                    <Typography variant="subtitle2">Focal Length</Typography>
                                    <Typography variant="body2">{assetData.data.asset.Metadata.CustomMetadata.EXIF.focalLength}</Typography>
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
