import React from 'react';
import { Box, Grid, Typography, Pagination, Card, CardContent, CardMedia, IconButton } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import MusicNoteIcon from '@mui/icons-material/MusicNote';

interface AudioItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface AudioResultsProps {
    audios: AudioItem[];
}

const AudioResults: React.FC<AudioResultsProps> = ({ audios }) => {
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
                Audio
            </Typography>

            <Grid container spacing={3}>
                {audios.map((audio) => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={audio.id}>
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
                            <Box sx={{
                                height: 120,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                bgcolor: 'primary.light',
                                position: 'relative'
                            }}>
                                <MusicNoteIcon sx={{ fontSize: 48, color: 'white' }} />
                                <CardMedia
                                    component="audio"
                                    src={audio.src}
                                    title={audio.fileName}
                                    controls
                                    sx={{
                                        position: 'absolute',
                                        bottom: 0,
                                        width: '100%',
                                        bgcolor: 'rgba(0, 0, 0, 0.5)',
                                        '& audio': {
                                            width: '100%'
                                        }
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
                                        {audio.fileName}
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
                                    {new Date(audio.creationDate).toLocaleDateString()}
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
                                    {audio.description}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {audios.length > 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <Pagination
                        count={Math.ceil(audios.length / 12)}
                        color="primary"
                        size="large"
                    />
                </Box>
            )}
        </Box>
    );
};

export default AudioResults;
