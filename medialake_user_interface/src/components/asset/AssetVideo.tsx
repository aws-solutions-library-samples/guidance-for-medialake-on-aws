import React from 'react';
import { Box } from '@mui/material';
import { VideoViewer, VideoViewerRef } from '../common/VideoViewer';

import { forwardRef, useImperativeHandle, useRef } from 'react';
import { OmakasePlayer } from '@byomakase/omakase-player';

interface AssetVideoProps {
    src: string;
    alt?: string;
}


export const AssetVideo = forwardRef<VideoViewerRef, AssetVideoProps>(({ src, alt }, ref) => {
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
                ref= {ref}
                videoSrc={src}
            />
        </Box>
    );
});

AssetVideo.displayName = 'AssetVideo';
export default AssetVideo;
