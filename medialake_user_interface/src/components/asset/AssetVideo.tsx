import React from 'react';
import { Box, Paper } from '@mui/material';
import { VideoViewer } from '../common/VideoViewer';

interface AssetVideoProps {
    src: string;
    alt?: string;
}

const AssetVideo: React.FC<AssetVideoProps> = ({ src, alt }) => {
    return (

        <Paper
            elevation={1}
        // sx={{
        //     height: '100%',
        //     display: 'flex',
        //     justifyContent: 'center',
        //     alignItems: 'center',
        //     overflow: 'hidden',
        //     bgcolor: 'background.paper',
        //     '& img': {
        //         maxWidth: '100%',
        //         maxHeight: '100%',
        //         objectFit: 'contain'
        //     }
        // }}
        >
            <VideoViewer
                videoSrc={src}
            />
        </Paper>

    );
};

export default AssetVideo;
