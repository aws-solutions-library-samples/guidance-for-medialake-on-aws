import React, { useEffect, useRef, useState } from 'react';
import { OmakasePlayer } from '@byomakase/omakase-player';
import "./VideoViewer.css"

interface VideoViewerProps {
    videoSrc: string;
}

export const VideoViewer: React.FC<VideoViewerProps> = ({ videoSrc }) => {
    const [player, setPlayer] = useState<OmakasePlayer | null>(null);
    const playerContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!player && playerContainerRef.current) {
            const newPlayer = new OmakasePlayer({
                playerHTMLElementId: playerContainerRef.current.id,
                mediaChrome: 'enabled',
            });
            setPlayer(newPlayer);
        }

        return () => {
            if (player) {
                player.destroy();
                setPlayer(null);
            }
        };
    }, []);

    useEffect(() => {
        if (!player) return;

        const subscriptions = [
            player.loadVideo(videoSrc, 25).subscribe({
                next: (video) => {
                    console.log(`Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`);
                },
                error: (error) => {
                    console.error('Error loading video:', error);
                },
                complete: () => {
                    console.log('Video loading completed');
                }
            }),
            player.video.onPlay$.subscribe({
                next: (event) => {
                    console.log(`Video play. Timestamp: ${event.currentTime}`);
                }
            }),
            player.video.onPause$.subscribe({
                next: (event) => {
                    console.log(`Video pause. Timestamp: ${event.currentTime}`);
                }
            }),
            player.video.onSeeked$.subscribe({
                next: (event) => {
                    console.log(`Video seeked. Timestamp: ${event.currentTime}`);
                }
            })
            // adds safe zone calculated from provided aspect ratio expression

        ];

        // player.video.addSafeZone({
        //     aspectRatio: "16/9"
        // })
        return () => {
            subscriptions.forEach(subscription => subscription.unsubscribe());
        };
    }, [player, videoSrc]);

    return (

        <div
            ref={playerContainerRef}
            id="omakase-player"
            className="video-viewer-container"
        />
    );
};

export default VideoViewer;


// import React from 'react';


// interface VideoViewerProps {
//     videoSrc: string;
//     maxHeight?: string | number;
// }

// export const VideoViewer: React.FC<VideoViewerProps> = ({ videoSrc }) => {

//     return (

//         <video
//             src={videoSrc}
//             style={{ width: '100%', height: '100%', objectFit: 'contain' }}
//             controls
//             onError={(e) => console.error("Video error:", e)}
//         />


//     );
// };

// export default VideoViewer;
