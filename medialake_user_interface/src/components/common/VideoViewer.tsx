// import React, { useEffect, useRef, useState } from 'react';
// import { Box, IconButton, Tooltip } from '@mui/material';
// import GetAppIcon from '@mui/icons-material/GetApp';
// import HomeIcon from '@mui/icons-material/Home';
// import LockIcon from '@mui/icons-material/Lock';
// import LockOpenIcon from '@mui/icons-material/LockOpen';
// import Rotate90DegreesCwIcon from '@mui/icons-material/Rotate90DegreesCw';
// import { OmakasePlayer } from '@byomakase/omakase-player';
// // import 'https://cdn.jsdelivr.net/npm/@byomakase/omakase-player@0.9.2-SNAPSHOT.1724678052/dist/style.min.css'; // Import CSS

// interface VideoViewerProps {
//     videoSrc: string;
//     maxHeight?: string | number;
// }

// export const VideoViewer: React.FC<VideoViewerProps> = ({ videoSrc, maxHeight = '70vh' }) => {
//     const divRef = useRef<HTMLDivElement>(null);
//     let omakasePlayer: OmakasePlayer | null = null;
//     // console.log(videoSrc)
//     useEffect(() => {
//         if (divRef.current) {
//             omakasePlayer = new OmakasePlayer({
//                 playerHTMLElementId: divRef.current.id,
//                 mediaChrome: 'enabled', // Change to 'disabled' or 'fullscreen-only' as needed
//             });

//             omakasePlayer.loadVideo(videoSrc, 25).subscribe({
//                 next: (video) => {
//                     console.log(`Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`);
//                 },
//             });

//             return () => {
//                 if (omakasePlayer) {
//                     omakasePlayer.destroy();
//                     omakasePlayer = null;
//                 }
//             };
//         }
//     }, [videoSrc]);



//     return (
//         <Box
//             ref={divRef}
//             id="omakase-player"
//             sx={{
//                 height: maxHeight,
//                 maxHeight,
//                 width: '100%',
//                 display: 'grid',
//                 gridTemplateColumns: '1fr',
//                 gridTemplateRows: '1fr',
//                 position: 'relative',
//                 overflow: 'hidden',
//             }}
//         >

//         </Box>
//     );
// };

// export default VideoViewer;

import React, { useRef, useState } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import GetAppIcon from '@mui/icons-material/GetApp';
import HomeIcon from '@mui/icons-material/Home';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';

interface VideoViewerProps {
    videoSrc: string;
    maxHeight?: string | number;
}

export const VideoViewer: React.FC<VideoViewerProps> = ({ videoSrc, maxHeight = '70vh' }) => {

    console.log("videoSrc", videoSrc)
    return (
        <Box
            sx={{
                height: maxHeight,
                maxHeight,
                width: '100%',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <video
                src={videoSrc}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                controls
                onError={(e) => console.error("Video error:", e)}
            />

        </Box>
    );
};

export default VideoViewer;
