import React, { useEffect, useRef, useState } from "react";
import { OmakasePlayer } from "@byomakase/omakase-player";
import "./VideoThumbnailViewer.css";

interface VideoThumbnailViewerProps {
  videoSrc: string;
  onClickEvent?: () => void;
}

export const VideoThumbnailViewer: React.FC<VideoThumbnailViewerProps> = ({
  videoSrc,
  onClickEvent,
}) => {
  const [player, setPlayer] = useState<OmakasePlayer | null>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!player && playerContainerRef.current) {
      const newPlayer = new OmakasePlayer({
        playerHTMLElementId: playerContainerRef.current.id,
        mediaChrome: "enabled",
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
          console.log(
            `Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`,
          );
        },
        error: (error) => {
          console.error("Error loading video:", error);
        },
        complete: () => {
          console.log("Video loading completed");
        },
      }),
      player.video.onPlay$.subscribe({
        next: (event) => {
          console.log(`Video play. Timestamp: ${event.currentTime}`);
        },
      }),
      player.video.onPause$.subscribe({
        next: (event) => {
          console.log(`Video pause. Timestamp: ${event.currentTime}`);
        },
      }),
      player.video.onSeeked$.subscribe({
        next: (event) => {
          console.log(`Video seeked. Timestamp: ${event.currentTime}`);
        },
      }),
      // adds safe zone calculated from provided aspect ratio expression
    ];

    // player.video.addSafeZone({
    //     aspectRatio: "16/9"
    // })
    return () => {
      subscriptions.forEach((subscription) => subscription.unsubscribe());
    };
  }, [player, videoSrc]);

  return (
    <div
      onClick={onClickEvent}
      ref={playerContainerRef}
      id="omakase-player"
      className="video-viewer-container"
    />
  );
};

//  omakase-player-wrapper

export default VideoThumbnailViewer;
