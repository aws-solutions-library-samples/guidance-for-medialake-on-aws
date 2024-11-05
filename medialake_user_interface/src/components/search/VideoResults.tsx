import React from 'react';
import { Box, Grid, Typography, Pagination, Card, CardContent, CardMedia, IconButton, Menu, MenuItem } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useNavigate } from 'react-router-dom';

interface VideoItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface VideoResultsProps {
    videos: VideoItem[];
}

const VideoResults: React.FC<VideoResultsProps> = ({ videos }) => {
    const navigate = useNavigate();

    const handleVideoClick = (videoId: number) => {
        navigate(`/video/${videoId}`);
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
                Videos
            </Typography>

            <Grid container spacing={3}>
                {videos.map((video) => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={video.id}>
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
                            <Box onClick={() => handleVideoClick(video.id)} sx={{ cursor: 'pointer' }}>
                                <CardMedia
                                    component="video"
                                    height="180"
                                    src={video.src}
                                    title={video.fileName}
                                    controls
                                    sx={{
                                        objectFit: 'cover',
                                        bgcolor: 'black'
                                    }}
                                />
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
                                        {video.fileName}
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
                                    {new Date(video.creationDate).toLocaleDateString()}
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
                                    {video.description}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {videos.length > 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <Pagination
                        count={Math.ceil(videos.length / 12)}
                        color="primary"
                        size="large"
                    />
                </Box>
            )}
        </Box>
    );
};

export default VideoResults;
