import React, { useState } from 'react';
import { Box, Typography, Card, CardContent, CardMedia, Button, Grid, Pagination, Menu, MenuItem, IconButton, TextField, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import { Link, Route, Routes } from 'react-router-dom';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import VideoDetailPage from '../VideoDetailPage';
import ImageDetailPage from '../ImageDetailPage';

interface MediaItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface MediaCardProps extends MediaItem {
    type: 'video' | 'image' | 'audio';
    onImageSelect?: (image: MediaItem) => void;
}

const MediaCard: React.FC<MediaCardProps> = ({ type, src, id, fileName, creationDate, description, onImageSelect }) => {
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [isRenaming, setIsRenaming] = useState(false);
    const [newFileName, setNewFileName] = useState(fileName);
    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleDelete = () => {
        console.log('Deleting:', fileName);
        // Implement delete logic here
    };

    const handleRename = () => {
        setIsRenaming(true);
        handleClose();
    };

    const handleRenameSubmit = () => {
        console.log('Renaming to:', newFileName);
        // Implement rename logic here
        setIsRenaming(false);
    };

    const getActions = () => {
        const actions = [
            { label: 'Rename', action: handleRename },
        ];

        switch (type) {
            case 'video':
                actions.push(
                    { label: 'Send to MAM', action: () => console.log('Sending to MAM') },
                    { label: 'Create Clip', action: () => console.log('Creating Clip') }
                );
                break;
            case 'image':
                actions.push(
                    { label: 'Edit', action: () => console.log('Editing') },
                    { label: 'Share', action: () => console.log('Sharing') }
                );
                break;
            case 'audio':
                actions.push(
                    { label: 'Transcribe', action: () => console.log('Transcribing') },
                    { label: 'Add to Playlist', action: () => console.log('Adding to Playlist') }
                );
                break;
        }

        actions.push({ label: 'Download', action: () => console.log('Downloading') });
        return actions;
    };

    return (
        <Card sx={{ width: '100%', m: 1 }}>
            <Link to={`/${type}/${id}`}>
                {type === 'video' && (
                    <CardMedia
                        component="video"
                        height="140"
                        src={src}
                        title={fileName}  // Changed from alt to title
                        controls
                        sx={{ objectFit: 'cover' }}
                    />
                )}
                {type === 'image' && (
                    <CardMedia
                        component="img"
                        height="140"
                        image={src}
                        alt={fileName}
                        onClick={() => onImageSelect && onImageSelect({ src, id, fileName, creationDate, description })}
                        sx={{ objectFit: 'cover' }}
                    />
                )}
                {type === 'audio' && (
                    <CardMedia
                        component="audio"
                        src={src}
                        title={fileName}  // Changed from alt to title
                        controls
                        sx={{
                            height: 50,  // Moved height to sx
                            '& audio': {
                                width: '100%'
                            }
                        }}
                    />
                )}
            </Link>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="subtitle1" sx={{ flexGrow: 1, mr: 1 }}>
                        {fileName}
                    </Typography>
                    <IconButton size="small" onClick={handleRename}>
                        <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={handleDelete}>
                        <DeleteIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                        id="action-button"
                        aria-controls={open ? 'action-menu' : undefined}
                        aria-haspopup="true"
                        aria-expanded={open ? 'true' : undefined}
                        onClick={handleClick}
                    >
                        <MoreVertIcon />
                    </IconButton>
                </Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                    Created: {new Date(creationDate).toLocaleString()}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    {description}
                </Typography>
                <Menu
                    id="action-menu"
                    anchorEl={anchorEl}
                    open={open}
                    onClose={handleClose}
                    MenuListProps={{
                        'aria-labelledby': 'action-button',
                    }}
                >
                    {getActions().map((action, index) => (
                        <MenuItem key={index} onClick={action.action}>
                            {action.label}
                        </MenuItem>
                    ))}
                </Menu>
            </CardContent>
            <Dialog open={isRenaming} onClose={() => setIsRenaming(false)}>
                <DialogTitle>Rename File</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        label="New File Name"
                        type="text"
                        fullWidth
                        variant="standard"
                        value={newFileName}
                        onChange={(e) => setNewFileName(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setIsRenaming(false)}>Cancel</Button>
                    <Button onClick={handleRenameSubmit}>Rename</Button>
                </DialogActions>
            </Dialog>
        </Card>
    );
};

interface SearchResultsProps {
    onImageSelect: (image: MediaItem) => void;
}

const SearchResults: React.FC<SearchResultsProps> = ({ onImageSelect }) => {
    const [videoView, setVideoView] = useState('card');
    const [imageView, setImageView] = useState('card');
    const [audioView, setAudioView] = useState('card');

    const toggleView = (section: 'video' | 'image' | 'audio') => {
        if (section === 'video') {
            setVideoView(videoView === 'card' ? 'grid' : 'card');
        } else if (section === 'image') {
            setImageView(imageView === 'card' ? 'grid' : 'card');
        } else if (section === 'audio') {
            setAudioView(audioView === 'card' ? 'grid' : 'card');
        }
    };

    const videos: MediaItem[] = [
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', id: 1, fileName: 'Big Buck Bunny', creationDate: '2023-05-01T12:00:00Z', description: 'A short animated film about a big rabbit' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', id: 2, fileName: 'Elephants Dream', creationDate: '2023-05-02T14:30:00Z', description: 'The first Blender Open Movie from 2006' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4', id: 3, fileName: 'Sintel', creationDate: '2023-05-03T10:15:00Z', description: 'Third Blender Open Movie from 2010' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4', id: 4, fileName: 'Tears of Steel', creationDate: '2023-05-04T16:20:00Z', description: 'Tears of Steel short film' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4', id: 5, fileName: 'For Bigger Blazes', creationDate: '2023-05-05T09:30:00Z', description: 'HBO GO now works with Chromecast' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4', id: 6, fileName: 'For Bigger Escapes', creationDate: '2023-05-06T11:45:00Z', description: 'Introducing Chromecast. The easiest way to enjoy online video and music on your TV' },
    ];

    const images: MediaItem[] = [
        { src: 'https://picsum.photos/id/1018/345/194', id: 1, fileName: 'Mountain Lake', creationDate: '2023-05-10T09:15:00Z', description: 'A serene mountain lake view' },
        { src: 'https://picsum.photos/id/1015/345/194', id: 2, fileName: 'River Valley', creationDate: '2023-05-11T16:45:00Z', description: 'A beautiful river flowing through a valley' },
        { src: 'https://picsum.photos/id/1016/345/194', id: 3, fileName: 'Misty Forest', creationDate: '2023-05-12T11:30:00Z', description: 'A mysterious misty forest landscape' },
        { src: 'https://picsum.photos/id/1020/345/194', id: 4, fileName: 'Bear Creek', creationDate: '2023-05-13T14:20:00Z', description: 'A peaceful creek in bear country' },
        { src: 'https://picsum.photos/id/1021/345/194', id: 5, fileName: 'Rocky Mountains', creationDate: '2023-05-14T10:10:00Z', description: 'Majestic view of the Rocky Mountains' },
        { src: 'https://picsum.photos/id/1022/345/194', id: 6, fileName: 'Northern Lights', creationDate: '2023-05-15T22:05:00Z', description: 'Spectacular display of Northern Lights' },
        { src: 'https://picsum.photos/id/1023/345/194', id: 7, fileName: 'Autumn Forest', creationDate: '2023-05-16T15:40:00Z', description: 'Colorful autumn forest scene' },
        { src: 'https://picsum.photos/id/1024/345/194', id: 8, fileName: 'Dragonfly', creationDate: '2023-05-17T13:25:00Z', description: 'Close-up of a dragonfly on a leaf' },
        { src: 'https://picsum.photos/id/1025/345/194', id: 9, fileName: 'Pug Dog', creationDate: '2023-05-18T12:50:00Z', description: 'Adorable pug dog looking at the camera' },
        { src: 'https://picsum.photos/id/1026/345/194', id: 10, fileName: 'Car Show', creationDate: '2023-05-19T11:15:00Z', description: 'Vintage cars at a car show' },
        { src: 'https://picsum.photos/id/1027/345/194', id: 11, fileName: 'Jellyfish', creationDate: '2023-05-20T09:30:00Z', description: 'Colorful jellyfish in deep blue water' },
        { src: 'https://picsum.photos/id/1028/345/194', id: 12, fileName: 'Lighthouse', creationDate: '2023-05-21T17:00:00Z', description: 'A lighthouse on a rocky coast' },
        { src: 'https://picsum.photos/id/1029/345/194', id: 13, fileName: 'Winter Forest', creationDate: '2023-05-22T08:45:00Z', description: 'Snow-covered trees in a winter forest' },
        { src: 'https://picsum.photos/id/1030/345/194', id: 14, fileName: 'Desert Landscape', creationDate: '2023-05-23T14:55:00Z', description: 'Vast desert landscape with sand dunes' },
        { src: 'https://picsum.photos/id/1031/345/194', id: 15, fileName: 'Tropical Beach', creationDate: '2023-05-24T10:20:00Z', description: 'Idyllic tropical beach with palm trees' },
    ];

    const audios: MediaItem[] = [
        { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_700KB.mp3', id: 1, fileName: 'Sample Audio 1', creationDate: '2023-05-25T11:20:00Z', description: 'A sample audio file for testing' },
        { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_1MG.mp3', id: 2, fileName: 'Sample Audio 2', creationDate: '2023-05-26T13:10:00Z', description: 'Another sample audio file for testing' },
        { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_2MG.mp3', id: 3, fileName: 'Sample Audio 3', creationDate: '2023-05-27T15:40:00Z', description: 'A third sample audio file for testing' },
    ];

    return (
        <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Routes>
                <Route path="/" element={
                    <>
                        <Typography variant="h4" component="h2" sx={{ fontWeight: 'bold', mb: 3 }}>
                            Video
                        </Typography>
                        <Grid container spacing={2}>
                            {videos.map((video) => (
                                <Grid item xs={12} sm={6} md={3} key={`video-${video.id}`}>
                                    <MediaCard type="video" {...video} />
                                </Grid>
                            ))}
                        </Grid>
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3, mb: 5 }}>
                            <Pagination count={Math.ceil(videos.length / 8)} color="primary" />
                        </Box>

                        <Typography variant="h4" component="h2" sx={{ fontWeight: 'bold', mb: 3 }}>
                            Images
                        </Typography>
                        <Grid container spacing={2}>
                            {images.map((image) => (
                                <Grid item xs={12} sm={6} md={3} key={`image-${image.id}`}>
                                    <MediaCard type="image" {...image} onImageSelect={onImageSelect} />
                                </Grid>
                            ))}
                        </Grid>
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3, mb: 5 }}>
                            <Pagination count={Math.ceil(images.length / 8)} color="primary" />
                        </Box>

                        <Typography variant="h4" component="h2" sx={{ fontWeight: 'bold', mb: 3 }}>
                            Audio
                        </Typography>
                        <Grid container spacing={2}>
                            {audios.map((audio) => (
                                <Grid item xs={12} sm={6} md={3} key={`audio-${audio.id}`}>
                                    <MediaCard type="audio" {...audio} />
                                </Grid>
                            ))}
                        </Grid>
                    </>
                } />
                <Route path="/video/:id" element={<VideoDetailPage />} />
                <Route path="/image/:id" element={<ImageDetailPage image={undefined} />} />
                {/* <Route path="/audio/:id" element={<AudioDetail />} /> */}
            </Routes>
        </Box>
    );
}

export default SearchResults;
