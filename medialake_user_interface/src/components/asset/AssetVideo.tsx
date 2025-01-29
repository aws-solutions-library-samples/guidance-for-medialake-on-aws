import React from 'react';
import { Box } from '@mui/material';
import { VideoViewer } from '../common/VideoViewer';

interface AssetVideoProps {
    src: string;
    alt?: string;
}

const AssetVideo: React.FC<AssetVideoProps> = ({ src, alt }) => {
    return (
        <Box
            width="100%"
            height="100%"
            display="flex"
            justifyContent="center"
            alignItems="center"
            sx={{
                '& > div': {
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                },
            }}
        >
            <VideoViewer
                videoSrc={src}
            />
        </Box>
    );
};

export default AssetVideo;
