import React, { useState } from 'react';
import { Box, Typography, Button, Grid } from '@mui/material';
import { useParams } from 'react-router-dom';

// Add interface for video object
interface Video {
    src: string;
    id: number;
    container: string;
    codec: string;
    resolution: string;
    bitrate: string;
    duration: string;
}

const VideoDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const [isAssetChatOpen, setIsAssetChatOpen] = useState<boolean>(false);

    // Update the videos array with type annotation
    const videos: Video[] = [
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', id: 1, container: 'MP4', codec: 'H.264', resolution: '1080p', bitrate: '5000 kbps', duration: '00:09:56' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', id: 2, container: 'MP4', codec: 'H.264', resolution: '720p', bitrate: '2500 kbps', duration: '00:10:53' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4', id: 3, container: 'MP4', codec: 'H.264', resolution: '1080p', bitrate: '5000 kbps', duration: '00:14:48' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4', id: 4, container: 'MP4', codec: 'H.264', resolution: '720p', bitrate: '2500 kbps', duration: '00:12:14' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4', id: 5, container: 'MP4', codec: 'H.264', resolution: '1080p', bitrate: '5000 kbps', duration: '00:15:01' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4', id: 6, container: 'MP4', codec: 'H.264', resolution: '720p', bitrate: '2500 kbps', duration: '00:15:22' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4', id: 7, container: 'MP4', codec: 'H.264', resolution: '1080p', bitrate: '5000 kbps', duration: '00:05:04' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4', id: 8, container: 'MP4', codec: 'H.264', resolution: '720p', bitrate: '2500 kbps', duration: '00:15:32' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4', id: 9, container: 'MP4', codec: 'H.264', resolution: '1080p', bitrate: '5000 kbps', duration: '00:15:06' },
        { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4', id: 10, container: 'MP4', codec: 'H.264', resolution: '720p', bitrate: '2500 kbps', duration: '00:08:43' },
    ];

    const video = videos.find((v) => v.id === parseInt(id ?? '', 10));

    const handleAssetChatToggle = () => {
        setIsAssetChatOpen(!isAssetChatOpen);
    };

    if (!video) {
        return <Typography>Video not found</Typography>;
    }

    return (
        <Box sx={{ flexGrow: 1, p: 3 }}>
            <Grid container spacing={2}>
                <Grid item xs={12} md={8}>
                    <Box sx={{ position: 'relative', paddingTop: '56.25%' }}>
                        <video
                            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
                            src={video.src}
                            controls
                        />
                    </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Typography variant="h6" gutterBottom>
                        Actions
                    </Typography>
                    <Button variant="contained" color="primary" fullWidth sx={{ mb: 2 }}>
                        Send to MAM
                    </Button>
                    <Button variant="contained" color="primary" fullWidth sx={{ mb: 2 }}>
                        Create Clip
                    </Button>
                    <Button variant="contained" color="primary" fullWidth sx={{ mb: 2 }}>
                        Download
                    </Button>
                    <Button
                        variant="contained"
                        color="primary"
                        fullWidth
                        onClick={handleAssetChatToggle}
                    >
                        {isAssetChatOpen ? 'Close Asset Chat' : 'Open Asset Chat'}
                    </Button>
                </Grid>
            </Grid>
            <Box sx={{ mt: 4 }}>
                <Typography variant="h6" gutterBottom>
                    Technical Details
                </Typography>
                <Typography>Container: {video.container}</Typography>
                <Typography>Codec: {video.codec}</Typography>
                <Typography>Resolution: {video.resolution}</Typography>
                <Typography>Bitrate: {video.bitrate}</Typography>
                <Typography>Duration: {video.duration}</Typography>
            </Box>
            {isAssetChatOpen && (
                <Box
                    sx={{
                        position: 'fixed',
                        right: 20,
                        bottom: 20,
                        width: 300,
                        height: 400,
                        zIndex: 9999,
                    }}
                >
                </Box>
            )}
        </Box>
    );
};

export default VideoDetailPage;
