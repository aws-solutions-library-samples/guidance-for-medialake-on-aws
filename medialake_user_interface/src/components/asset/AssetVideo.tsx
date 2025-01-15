import React from 'react';
import { Box, Paper } from '@mui/material';
import { VideoViewer } from '../common/VideoViewer';

interface AssetVideoProps {
    src: string;
    alt?: string;
}

const AssetVideo: React.FC<AssetVideoProps> = ({ src, alt }) => {
    return (
        <Box
            sx={{
                position: 'sticky',
                top: 120, // Below breadcrumb and header
                zIndex: 900,
                mb: 3,
                height: 'calc(80vh - 120px)', // Take 80% of viewport height minus top offset
                minHeight: 400, // Increased minimum height
                maxHeight: 'calc(100vh - 180px)', // Maximum height almost full viewport
            }}
        >
            <Paper
                elevation={1}
                sx={{
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                    bgcolor: 'background.paper',
                    '& img': {
                        maxWidth: '100%',
                        maxHeight: '100%',
                        objectFit: 'contain'
                    }
                }}
            >
                <VideoViewer
                    videoSrc={src}
                    maxHeight="100%"
                />
            </Paper>
        </Box>
    );
};

export default AssetVideo;
