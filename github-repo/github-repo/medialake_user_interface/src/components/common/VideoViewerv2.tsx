// VideoViewer.tsx
import React, {
  useEffect,
  useRef,
  useCallback,
  useState,
  FC,
  SyntheticEvent,
} from "react";
import { OmakasePlayer } from "@byomakase/omakase-player";
import Slider from "@mui/material/Slider";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import "./VideoViewer.css";

export interface VideoViewerProps {
  videoSrc: string;
  onClickEvent?: () => void;
  onPlay?: () => void;
  onPause?: () => void;
  onSeek?: (time: number) => void;
  onVolumeChange?: (volume: number) => void;
  onMute?: () => void;
  onUnmute?: () => void;
  onPlaybackRateChange?: (rate: number) => void;
  onFullscreenChange?: (isFullscreen: boolean) => void;
  onRemoveSafeZone?: (id: string) => void;
  onClearSafeZones?: () => void;
  onBuffering?: () => void;
  onEnded?: () => void;
  onError?: (error: any) => void;
  onTimeUpdate?: (time: number) => void;
  // Optionally, add additional props such as onLoaded if needed.
}

/**
 * A custom hook that creates and manages the OmakasePlayer instance.
 * (Here we also add local state for currentTime and duration.)
 */
const useOmakasePlayer = (
  videoSrc: string,
  containerRef: React.RefObject<HTMLDivElement>,
  callbacks: Partial<VideoViewerProps>,
) => {
  const playerRef = useRef<OmakasePlayer | null>(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  const initializePlayer = useCallback(() => {
    if (!containerRef.current) return;

    const player = new OmakasePlayer({
      playerHTMLElementId: containerRef.current.id,
      // mediaChrome: 'disabled'
    });
    playerRef.current = player;

    const subscriptions = [
      player.loadVideo(videoSrc, 25).subscribe({
        next: (video) => {
          console.log(
            `Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`,
          );
          setDuration(video.duration);
        },
        error: (error) => {
          console.error("Error loading video:", error);
          callbacks.onError?.(error);
        },
        complete: () => {
          console.log("Video loading completed");
        },
      }),
      player.video.onPlay$.subscribe({
        next: (event) => {
          console.log(`Video play. Timestamp: ${event.currentTime}`);
          callbacks.onPlay?.();
        },
      }),
      player.video.onPause$.subscribe({
        next: (event) => {
          console.log(`Video pause. Timestamp: ${event.currentTime}`);
          callbacks.onPause?.();
        },
      }),
      player.video.onSeeked$.subscribe({
        next: (event) => {
          console.log(`Video seeked. Timestamp: ${event.currentTime}`);
          callbacks.onSeek?.(event.currentTime);
        },
      }),
      player.video.onBuffering$.subscribe({
        next: () => {
          console.log("Video buffering");
          callbacks.onBuffering?.();
        },
      }),
      player.video.onEnded$.subscribe({
        next: () => {
          console.log("Video ended");
          callbacks.onEnded?.();
        },
      }),
      player.video.onFullscreenChange$.subscribe({
        next: (event) => {
          // If you wish, forward fullscreen changes:
          // callbacks.onFullscreenChange?.(event.isFullscreen);
        },
      }),
      player.video.onVolumeChange$.subscribe({
        next: (event) => {
          console.log(`Volume changed: ${event.volume}`);
          callbacks.onVolumeChange?.(event.volume);
        },
      }),
      player.video.onVideoTimeChange$.subscribe({
        next: (event) => {
          setCurrentTime(event.currentTime);
          callbacks.onTimeUpdate?.(event.currentTime);
        },
      }),
      player.video.onVideoError$.subscribe({
        next: (error) => {
          console.error("Video error:", error);
          callbacks.onError?.(error);
        },
      }),
    ];

    return () => {
      subscriptions.forEach((subscription) => subscription.unsubscribe());
      player.destroy();
      playerRef.current = null;
    };
  }, [videoSrc, callbacks, containerRef]);

  useEffect(() => {
    const cleanup = initializePlayer();
    return cleanup;
  }, [initializePlayer]);

  const play = useCallback(() => {
    playerRef.current?.video.play();
  }, []);

  const pause = useCallback(() => {
    playerRef.current?.video.pause();
  }, []);

  const seek = useCallback((time: number) => {
    playerRef.current?.video.seekToTime(time);
  }, []);

  const setVolume = useCallback((volume: number) => {
    playerRef.current?.video.setVolume(volume);
  }, []);

  const mute = useCallback(() => {
    playerRef.current?.video.mute();
  }, []);

  const unmute = useCallback(() => {
    playerRef.current?.video.unmute();
  }, []);

  const setPlaybackRate = useCallback((rate: number) => {
    playerRef.current?.video.setPlaybackRate(rate);
  }, []);

  const toggleFullscreen = useCallback(() => {
    playerRef.current?.video.toggleFullscreen();
  }, []);

  const removeSafeZone = useCallback(
    (id: string) => {
      playerRef.current?.video.removeSafeZone(id).subscribe({
        next: () => {
          console.log("Safe zone removed:", id);
          callbacks.onRemoveSafeZone?.(id);
        },
        error: (error) => {
          console.error("Error removing safe zone:", error);
        },
      });
    },
    [callbacks],
  );

  const clearSafeZones = useCallback(() => {
    playerRef.current?.video.clearSafeZones().subscribe({
      next: () => {
        console.log("All safe zones cleared");
        callbacks.onClearSafeZones?.();
      },
      error: (error) => {
        console.error("Error clearing safe zones:", error);
      },
    });
  }, [callbacks]);

  return {
    play,
    pause,
    seek,
    setVolume,
    mute,
    unmute,
    setPlaybackRate,
    toggleFullscreen,
    removeSafeZone,
    clearSafeZones,
    currentTime,
    duration,
  };
};

/**
 * A custom value label component for the seek slider.
 * It shows a thumbnail image based on the current slider value.
 */
function ThumbLabel(props: any) {
  const { children, open, value } = props;
  const thumbnailUrl = getThumbnailForTime(value);
  return (
    <Tooltip
      open={open}
      title={
        <img
          src={thumbnailUrl}
          alt={`Thumbnail at ${value}`}
          style={{ width: 100, display: "block" }}
        />
      }
      placement="top"
    >
      {children}
    </Tooltip>
  );
}

/**
 * A dummy function to simulate obtaining a thumbnail URL for a given time.
 * Replace this with your real thumbnail extraction from a VTT file.
 */
function getThumbnailForTime(time: number): string {
  return `https://via.placeholder.com/100x56.png?text=${Math.floor(time)}`;
}

/**
 * The VideoViewer component renders the video container (which OmakasePlayer uses)
 * and a custom control bar below it.
 */
export const VideoViewer: FC<VideoViewerProps> = ({
  videoSrc,
  onClickEvent,
  onPlay,
  onPause,
  onSeek,
  onVolumeChange,
  onMute,
  onUnmute,
  onPlaybackRateChange,
  onFullscreenChange,
  onRemoveSafeZone,
  onClearSafeZones,
  onBuffering,
  onEnded,
  onError,
  onTimeUpdate,
}) => {
  const playerContainerRef = useRef<HTMLDivElement>(null);

  // Local state to track whether the video is playing, the volume level, and mute status.
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolumeState] = useState(100);
  const [muted, setMuted] = useState(false);

  // Wrap some callbacks so we can update local state (and then call any parent callbacks)
  const customCallbacks: Partial<VideoViewerProps> = {
    onPlay: () => {
      setIsPlaying(true);
      onPlay?.();
    },
    onPause: () => {
      setIsPlaying(false);
      onPause?.();
    },
    onSeek,
    onVolumeChange: (vol: number) => {
      setVolumeState(vol);
      onVolumeChange?.(vol);
    },
    onBuffering,
    onEnded,
    onError,
    onTimeUpdate: (time: number) => {
      onTimeUpdate?.(time);
    },
  };

  const {
    play,
    pause,
    seek,
    setVolume: setPlayerVolume,
    mute,
    unmute,
    toggleFullscreen,
    removeSafeZone,
    clearSafeZones,
    currentTime,
    duration,
  } = useOmakasePlayer(videoSrc, playerContainerRef, customCallbacks);

  const handlePlayPause = () => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  };

  const handleSeekChange = (event: Event, newValue: number | number[]) => {
    // (Optional: you might want to update a “preview” state here)
  };

  const handleSeekCommitted = (
    event: Event | SyntheticEvent,
    newValue: number | number[],
  ) => {
    if (typeof newValue === "number") {
      seek(newValue);
    }
  };

  const handleVolumeChange = (event: Event, newValue: number | number[]) => {
    if (typeof newValue === "number") {
      setPlayerVolume(newValue);
      setVolumeState(newValue);
    }
  };

  const handleMuteToggle = () => {
    if (muted) {
      unmute();
      setMuted(false);
      onUnmute?.();
    } else {
      mute();
      setMuted(true);
      onMute?.();
    }
  };

  const handleFullscreenToggle = () => {
    toggleFullscreen();
    onFullscreenChange?.(true); // You could enhance this to track fullscreen state.
  };

  // A helper to format seconds into mm:ss
  const formatTime = (time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
  };

  return (
    <div className="video-viewer-wrapper">
      <div
        onClick={onClickEvent}
        ref={playerContainerRef}
        id="omakase-player"
        className="video-viewer-container"
      >
        {/* The OmakasePlayer renders the video into this container */}
      </div>
      <div className="custom-controls">
        {/* Seek Slider with a thumbnail preview */}
        <Slider
          value={currentTime}
          min={0}
          max={duration}
          onChange={handleSeekChange}
          onChangeCommitted={handleSeekCommitted}
          valueLabelDisplay="auto"
          components={{ ValueLabel: ThumbLabel }} // <-- Updated prop usage
          className="seek-slider"
        />
        <div className="control-bar">
          {/* Play / Pause */}
          <IconButton onClick={handlePlayPause}>
            {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
          {/* Timecode display */}
          <div className="timecode">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>
          {/* Volume and mute */}
          <div className="volume-control">
            <IconButton onClick={handleMuteToggle}>
              {muted || volume === 0 ? <VolumeOffIcon /> : <VolumeUpIcon />}
            </IconButton>
            <Slider
              orientation="vertical"
              value={volume}
              min={0}
              max={100}
              onChange={handleVolumeChange}
              className="volume-slider"
            />
          </div>
          {/* Fullscreen */}
          <IconButton onClick={handleFullscreenToggle}>
            <FullscreenIcon />
          </IconButton>
        </div>
      </div>
    </div>
  );
};

export default VideoViewer;
