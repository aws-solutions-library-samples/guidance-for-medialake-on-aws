import React, { useEffect, useRef, useState } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import GetAppIcon from '@mui/icons-material/GetApp';
import HomeIcon from '@mui/icons-material/Home';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import Rotate90DegreesCwIcon from '@mui/icons-material/Rotate90DegreesCw';
import { OmakasePlayer } from '@byomakase/omakase-player';
// import 'https://cdn.jsdelivr.net/npm/@byomakase/omakase-player@0.9.2-SNAPSHOT.1724678052/dist/style.min.css'; // Import CSS

interface VideoViewerProps {
    videoSrc: string;
    maxHeight?: string | number;
    filename?: string;
}

export const VideoViewer: React.FC<VideoViewerProps> = ({ videoSrc, maxHeight = '70vh', filename = 'video_download' }) => {
    const divRef = useRef<HTMLDivElement>(null);
    const [isCanvasLocked, setIsCanvasLocked] = useState(true);
    const [rotate, setRotate] = useState(0);
    let omakasePlayer: OmakasePlayer | null = null;

    useEffect(() => {
        if (divRef.current) {
            omakasePlayer = new OmakasePlayer({
                playerHTMLElementId: divRef.current.id,
                mediaChrome: 'enabled', // Change to 'disabled' or 'fullscreen-only' as needed
            });

            omakasePlayer.loadVideo(videoSrc, 25).subscribe({
                next: (video) => {
                    console.log(`Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`);
                },
            });

            return () => {
                if (omakasePlayer) {
                    omakasePlayer.destroy();
                    omakasePlayer = null;
                }
            };
        }
    }, [videoSrc]);

    const handleCanvasDownload = () => {
        // Implement download logic if needed
    };

    const resetVideo = () => {
        if (omakasePlayer) {
            omakasePlayer.video.seekToTime(0).subscribe({
                next: () => {
                    console.log("Video reset to start");
                },
            });
            setRotate(0);
        }
    };

    const toggleCanvasLock = () => {
        setIsCanvasLocked(!isCanvasLocked);
    };

    const toolButtons = [
        {
            tip: 'Download Canvas',
            icon: <GetAppIcon />,
            onClick: handleCanvasDownload,
        },
        {
            tip: 'Reset',
            icon: <HomeIcon />,
            onClick: resetVideo,
        },
        {
            tip: isCanvasLocked ? 'Unlock canvas' : 'Lock canvas',
            icon: isCanvasLocked ? <LockIcon /> : <LockOpenIcon />,
            onClick: toggleCanvasLock,
        },
        {
            tip: 'Rotate',
            icon: <Rotate90DegreesCwIcon />,
            onClick: () => {
                setRotate((prevRotate) => (prevRotate + 90) % 360);
                if (omakasePlayer) {
                    omakasePlayer.video.addSafeZone({ topRightBottomLeftPercent: [rotate, rotate, rotate, rotate] });
                }
            },
        },
    ];

    return (
        <Box
            ref={divRef}
            id="omakase-player"
            sx={{
                height: maxHeight,
                maxHeight,
                width: '100%',
                display: 'grid',
                gridTemplateColumns: '1fr',
                gridTemplateRows: '1fr',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            <Box
                sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    flexDirection: 'row',
                    gap: '8px',
                    zIndex: 1,
                }}
            >
                {toolButtons.map((item, i) => (
                    <Tooltip key={`video-tool-${i}`} title={item.tip}>
                        <IconButton
                            color="primary"
                            onClick={item.onClick}
                        >
                            {item.icon}
                        </IconButton>
                    </Tooltip>
                ))}
            </Box>
        </Box>
    );
};

export default VideoViewer;

