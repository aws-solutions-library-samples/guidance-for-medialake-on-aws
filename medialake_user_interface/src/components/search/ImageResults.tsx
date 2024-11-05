import React from 'react';
import { Box, Grid, Typography, Pagination, Card, CardContent, CardMedia, IconButton } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useNavigate } from 'react-router-dom';

interface ImageItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface ImageResultsProps {
    images: ImageItem[];
}

const ImageResults: React.FC<ImageResultsProps> = ({ images }) => {
    const navigate = useNavigate();

    const handleImageClick = (imageId: number) => {
        navigate(`/images/${imageId}`);
    };

    return (
        <Box sx={{ mb: 6 }}>
            <Typography
                variant="h5"
                component="h2"
                sx={{
                    fontWeight: 600,
                    mb: 3,
                    color: 'primary.main',
                    borderBottom: '2px solid',
                    borderColor: 'primary.main',
                    pb: 1,
                    display: 'inline-block'
                }}
            >
                Images
            </Typography>

            <Grid container spacing={3}>
                {images.map((image) => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={image.id}>
                        <Card
                            sx={{
                                height: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                                '&:hover': {
                                    transform: 'translateY(-4px)',
                                    boxShadow: 4
                                }
                            }}
                        >
                            <Box
                                onClick={() => handleImageClick(image.id)}
                                sx={{
                                    cursor: 'pointer',
                                    position: 'relative',
                                    '&:hover .image-overlay': {
                                        opacity: 1
                                    }
                                }}
                            >
                                <CardMedia
                                    component="img"
                                    height="180"
                                    image={image.src}
                                    alt={image.fileName}
                                    sx={{ objectFit: 'cover' }}
                                />
                                <Box
                                    className="image-overlay"
                                    sx={{
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        right: 0,
                                        bottom: 0,
                                        bgcolor: 'rgba(0, 0, 0, 0.5)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        opacity: 0,
                                        transition: 'opacity 0.2s ease-in-out'
                                    }}
                                >
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            color: 'white',
                                            textAlign: 'center',
                                            p: 2
                                        }}
                                    >
                                        Click to view details
                                    </Typography>
                                </Box>
                            </Box>
                            <CardContent sx={{ flexGrow: 1, p: 2 }}>
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'flex-start',
                                    mb: 1
                                }}>
                                    <Typography
                                        variant="subtitle1"
                                        sx={{
                                            fontWeight: 500,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            display: '-webkit-box',
                                            WebkitLineClamp: 2,
                                            WebkitBoxOrient: 'vertical'
                                        }}
                                    >
                                        {image.fileName}
                                    </Typography>
                                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                                        <IconButton size="small">
                                            <EditIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton size="small">
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton size="small">
                                            <MoreVertIcon fontSize="small" />
                                        </IconButton>
                                    </Box>
                                </Box>
                                <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{ mb: 1 }}
                                >
                                    {new Date(image.creationDate).toLocaleDateString()}
                                </Typography>
                                <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        display: '-webkit-box',
                                        WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical'
                                    }}
                                >
                                    {image.description}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {images.length > 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <Pagination
                        count={Math.ceil(images.length / 12)}
                        color="primary"
                        size="large"
                    />
                </Box>
            )}
        </Box>
    );
};

export default ImageResults;
