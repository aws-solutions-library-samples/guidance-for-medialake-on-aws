// VideoViewer.tsx
import React, {
  useEffect,
  useRef,
  useCallback,
  useState,
  SyntheticEvent,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from "react";
import {
  MarkerLane,
  OmakasePlayer,
  PeriodMarker,
} from "@byomakase/omakase-player";
import {
  SCRUBBER_LANE_STYLE_DARK,
  TIMELINE_STYLE_DARK,
  PERIOD_MARKER_STYLE,
} from "./OmakaseTimeLineConstants";
import {
  Tooltip,
  IconButton,
  Stack,
  Slider,
  Box,
  Popover,
  Typography,
  Paper,
  Chip,
  Grid,
  Divider,
  Button,
} from "@mui/material";

import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import KeyboardAltIcon from "@mui/icons-material/KeyboardAlt";
import PauseIcon from "@mui/icons-material/Pause";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import "./VideoViewer.css";
import "../../styles/player-overrides.css";

import { createTimecodePlaceholder } from "@/utils/placeholderSvg";
import { useVideoKeyboardShortcuts } from "./useVideoKeyboardShortcuts";

import { filter } from "rxjs";
import { randomHexColor } from "./utils";

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
  showThumbnails?: boolean;
  onMarkerAdd?: (time: number) => void;
  playerRef?: React.RefObject<OmakasePlayer>;
}

export type Marker = {
  start: number;
  color: string;
  end: number;
};

export interface VideoViewerRef {
  hello: () => PeriodMarker;
  getMarkerLane: () => MarkerLane | null;
  getCurrentTime: () => number;
  formatToTimecode: (time: number) => string;
  seek: (time: number) => void;
}

/**
 * Custom hook that creates and manages the OmakasePlayer instance.
 * We pass in a markerLaneRef to save the created marker lane so that we can add markers later.
 */
const useOmakasePlayer = (
  videoSrc: string,
  containerRef: React.RefObject<HTMLDivElement>,
  callbacks: Partial<VideoViewerProps>,
  markerLaneRef: React.MutableRefObject<any | null>,
) => {
  const playerRef = useRef<OmakasePlayer | null>(null);
  const [playerVolume, setPlayerVolume] = useState(1);

  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const callbacksRef = useRef(callbacks);
  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);

  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  const initializePlayer = useCallback(() => {
    if (!containerRef.current) return;

    // Reset marker lane state when initializing a new player
    markerLaneRef.current = null;

    const player = new OmakasePlayer({
      playerHTMLElementId: containerRef.current.id,
    });
    playerRef.current = player;
    player
      .createTimeline({
        timelineHTMLElementId: "omakase-timeline",
        style: { ...TIMELINE_STYLE_DARK },
        zoomWheelEnabled: false,
      })
      .subscribe((timelineApi) => {
        console.log("Timeline created");
        const scrubberLane = timelineApi.getScrubberLane();
        scrubberLane.style = { ...SCRUBBER_LANE_STYLE_DARK };

        // Create marker lanes after timeline is ready
        createTimelineLanes();
      });

    const subscriptions = [
      player.loadVideo(videoSrc).subscribe({
        next: (video) => {
          console.log(`Video loaded. Duration: ${video.duration}`);
          setDuration(video.duration);
        },
        error: (error) => {
          console.error("Error loading video:", error);
          callbacksRef.current.onError?.(error);
        },
        complete: () => {
          console.log("Video loading completed");
        },
      }),
      player.video.onPlay$.subscribe({
        next: (event) => {
          console.log(`Video play. Timestamp: ${event.currentTime}`);
          callbacksRef.current.onPlay?.();
        },
      }),
      player.video.onPause$.subscribe({
        next: (event) => {
          console.log(
            `Video pause. Timestamp: ${playerRef.current.video.formatToTimecode(event.currentTime)}`,
          );
          callbacksRef.current.onPause?.();
        },
      }),
      player.video.onSeeked$.subscribe({
        next: (event) => {
          console.log(`Video seeked. Timestamp: ${event.currentTime}`);
          callbacksRef.current.onSeek?.(event.currentTime);
        },
      }),
      player.video.onBuffering$.subscribe({
        next: () => {
          console.log("Video buffering");
          callbacksRef.current.onBuffering?.();
        },
      }),
      player.video.onEnded$.subscribe({
        next: () => {
          console.log("Video ended");
          callbacksRef.current.onEnded?.();
        },
      }),
      player.video.onFullscreenChange$.subscribe({
        next: (event) => {
          // Forward fullscreen changes if needed.
        },
      }),
      player.video.onVolumeChange$.subscribe({
        next: (event) => {
          const newVolume = Math.round(event.volume * 100);
          console.log(`Volume changed: ${newVolume}`);
          setPlayerVolume(event.volume);
          callbacksRef.current.onVolumeChange?.(newVolume);
        },
      }),
      player.video.onVideoTimeChange$.subscribe({
        next: (event) => {
          setCurrentTime(event.currentTime);
          callbacksRef.current.onTimeUpdate?.(event.currentTime);
        },
      }),
      player.video.onVideoError$.subscribe({
        next: (error) => {
          console.error("Video error:", error);
          callbacksRef.current.onError?.(error);
        },
      }),
    ];

    const createTimelineLanes = () => {
      markerLane1();
    };

    const markerLane1 = (retryCount = 0) => {
      const maxRetries = 3;
      const retryDelay = 1000; // 1 second

      try {
        if (!player.timeline) {
          console.warn("Timeline not available for marker lane creation");
          if (retryCount < maxRetries) {
            console.log(
              `Retrying marker lane creation in ${retryDelay}ms (attempt ${retryCount + 1}/${maxRetries})`,
            );
            retryTimeoutRef.current = setTimeout(() => {
              markerLane1(retryCount + 1);
            }, retryDelay);
            return;
          } else {
            console.error("Failed to create marker lane after maximum retries");
            return;
          }
        }

        const markerLane = new MarkerLane({
          style: { ...TIMELINE_STYLE_DARK, height: 25 },
        });
        const lane = player.timeline.addTimelineLane(markerLane);
        markerLaneRef.current = lane;

        console.log("Marker lane created successfully");
      } catch (error) {
        console.error("Error creating marker lane:", error);
        markerLaneRef.current = null;

        if (retryCount < maxRetries) {
          console.log(
            `Retrying marker lane creation in ${retryDelay}ms (attempt ${retryCount + 1}/${maxRetries})`,
          );
          retryTimeoutRef.current = setTimeout(() => {
            markerLane1(retryCount + 1);
          }, retryDelay);
        } else {
          console.error("Failed to create marker lane after maximum retries");
        }
      }
    };

    return () => {
      subscriptions.forEach((subscription) => subscription.unsubscribe());
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      playerRef.current = null;
      // Cleanup handled by individual subscriptions and refs
    };
  }, [videoSrc, containerRef, markerLaneRef]);

  useEffect(
    () => {
      const cleanup = initializePlayer();
      return cleanup;
    },
    [
      /*initializePlayer*/
    ],
  ); //Not using UseEffect dependency array due to player inicializing everytime someone changes tabs

  // Responsive timeline: Listen for window resize events and trigger a timeline resize.
  // useEffect(() => {
  //   const handleResize = () => {
  //     if (
  //       playerRef.current?.timeline &&
  //       typeof playerRef.current.timeline.resize === 'function'
  //     ) {
  //       playerRef.current.timeline.resize();
  //       console.log('Timeline resized');
  //     }
  //   };
  //   window.addEventListener('resize', handleResize);
  //   return () => window.removeEventListener('resize', handleResize);
  // }, []);
  useEffect(() => {
    // Select the timeline container element.
    const timelineContainer = document.getElementById("omakase-timeline");
    if (!timelineContainer) return;

    const resizeObserver = new ResizeObserver((entries) => {
      // When the timeline container's size changes, settle the layout.
      if (playerRef.current?.timeline) {
        playerRef.current.timeline.zoomTo(100);
        playerRef.current.timeline.settleLayout();
        // Check if zoom is not 100% and adjust it
        if (playerRef.current.timeline.getZoomPercent() !== 100) {
          playerRef.current.timeline.zoomTo(100);
        }
        console.log("Timeline layout settled via ResizeObserver");
      }
    });
    resizeObserver.observe(timelineContainer);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

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
    const newVolume = volume / 100;
    playerRef.current?.video.setVolume(newVolume);
    setPlayerVolume(newVolume);
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

  const removeSafeZone = useCallback((id: string) => {
    playerRef.current?.video.removeSafeZone(id).subscribe({
      next: () => {
        console.log("Safe zone removed:", id);
        callbacksRef.current.onRemoveSafeZone?.(id);
      },
      error: (error) => {
        console.error("Error removing safe zone:", error);
      },
    });
  }, []);

  const clearSafeZones = useCallback(() => {
    playerRef.current?.video.clearSafeZones().subscribe({
      next: () => {
        console.log("All safe zones cleared");
        callbacksRef.current.onClearSafeZones?.();
      },
      error: (error) => {
        console.error("Error clearing safe zones:", error);
      },
    });
  }, []);

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
    setCurrentTime,
    playerRef,
  };
};

function ThumbLabel(props: any) {
  const { children, open, value, showThumbnails = true } = props;
  const lastValueRef = useRef(value);
  const [thumbnailUrl, setThumbnailUrl] = useState(() =>
    getThumbnailForTime(value),
  );
  const timeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    lastValueRef.current = value;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      if (lastValueRef.current === value) {
        setThumbnailUrl(getThumbnailForTime(value));
      }
    }, 50);
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [value]);

  return (
    <Tooltip
      open={open && showThumbnails}
      title={
        showThumbnails ? (
          <img
            src={thumbnailUrl}
            alt={`Thumbnail at ${value}`}
            style={{ width: 100, display: "block" }}
          />
        ) : (
          value.toFixed(1)
        )
      }
      placement="top"
    >
      {children}
    </Tooltip>
  );
}

function getThumbnailForTime(time: number): string {
  const hours = Math.floor(time / 3600);
  const minutes = Math.floor((time % 3600) / 60);
  const seconds = Math.floor(time % 60);
  const frames = Math.floor((time % 1) * 25);
  const timeString = `${hours.toString().padStart(2, "0")}:${minutes
    .toString()
    .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}:${frames
    .toString()
    .padStart(2, "0")}`;
  return createTimecodePlaceholder(timeString);
}

export const VideoViewer = forwardRef<VideoViewerRef, VideoViewerProps>(
  (
    {
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
      showThumbnails = false,
      onMarkerAdd,
      playerRef,
    },
    ref,
  ) => {
    const playerContainerRef = useRef<HTMLDivElement>(null);
    const markerLaneRef = useRef<MarkerLane | null>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [volume, setVolumeState] = useState(100);
    const [muted, setMuted] = useState(false);
    const [isSmtpeFormat, setIsSmtpeFormat] = useState(true);
    const [isVolumeHovered, setIsVolumeHovered] = useState(false);

    const [shortcutsAnchor, setShortcutsAnchor] = useState<null | HTMLElement>(
      null,
    );
    const openShortcuts = Boolean(shortcutsAnchor);
    const handleOpenShortcuts = (event: React.MouseEvent<HTMLElement>) => {
      setShortcutsAnchor(event.currentTarget);
    };
    const handleCloseShortcuts = () => {
      setShortcutsAnchor(null);
    };

    const volumeHoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const lastNonZeroVolumeRef = useRef(100);

    // state near other useStates in VideoViewer
    const [uiTime, setUiTime] = useState(0);

    const customCallbacks = useMemo<Partial<VideoViewerProps>>(
      () => ({
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
        onMarkerAdd: (time: number) => {
          onMarkerAdd?.(time);
        },
      }),
      [
        onPlay,
        onPause,
        onSeek,
        onVolumeChange,
        onBuffering,
        onEnded,
        onError,
        onTimeUpdate,
        onMarkerAdd,
      ],
    );

    const {
      play,
      pause,
      seek,
      setVolume: setPlayerVolume,
      mute,
      unmute,
      setPlaybackRate,
      toggleFullscreen,
      removeSafeZone,
      clearSafeZones,
      currentTime,
      duration,
      setCurrentTime,
      playerRef: omakaseRef, // get the internal ref from the hook
    } = useOmakasePlayer(
      videoSrc,
      playerContainerRef,
      customCallbacks,
      markerLaneRef,
    );

    // reset UI time when the source changes (optional but nice)
    useEffect(() => {
      setUiTime(0);
    }, [videoSrc]);

    // smoothing RAF — use the INTERNAL ref from the hook
    useEffect(() => {
      const videoEl = omakaseRef.current?.video.getHTMLVideoElement();
      if (!videoEl) return;

      let rafId: number;
      let lastMediaTime = videoEl.currentTime;
      let coastStart = 0;
      const COAST_MS = 250; // small smoothing window
      const EPS = 1 / 120; // ~8.3ms, treat smaller deltas as "stalled"

      const bufferedEndNear = (t: number) => {
        const r = videoEl.buffered;
        for (let i = 0; i < r.length; i++) {
          if (r.start(i) - 0.5 <= t && t <= r.end(i) + 0.5) return r.end(i);
        }
        return t;
      };

      const tick = (now: number) => {
        const playing = !videoEl.paused && !videoEl.ended;
        const mediaTime = videoEl.currentTime;
        let target = mediaTime;

        const mediaDelta = mediaTime - lastMediaTime;

        // if playing and time didn't advance meaningfully, coast a bit
        if (playing && mediaDelta < EPS) {
          if (coastStart === 0) coastStart = now;
          const elapsed = Math.min(now - coastStart, COAST_MS);
          target =
            lastMediaTime + (elapsed / 1000) * (videoEl.playbackRate || 1);

          // don't "paint" into unbuffered territory
          const be = bufferedEndNear(lastMediaTime);
          target = Math.min(target, be - 0.033); // ~2 frames at 60fps
        } else {
          coastStart = 0;
        }

        // clamp to duration
        const dur = Number.isFinite(videoEl.duration)
          ? videoEl.duration
          : target;
        target = Math.max(0, Math.min(target, dur));

        setUiTime(target);
        lastMediaTime = mediaTime;
        rafId = requestAnimationFrame(tick);
      };

      rafId = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(rafId);
    }, [omakaseRef, videoSrc]);

    // Use keyboard shortcuts hook
    const {
      SHORTCUTS,
      toggleTransport,
      currentPlaybackRate,
      isShuttlingReverse,
    } = useVideoKeyboardShortcuts({
      play,
      pause,
      seek,
      setPlaybackRate,
      mute,
      unmute,
      toggleFullscreen,
      isPlaying,
      currentTime,
      duration,
      volume,
      muted,
      setPlayerVolume,
      setVolumeState: setVolumeState,
      setMuted,
      setIsVolumeHovered,
      lastNonZeroVolumeRef,
      volumeHoverTimeoutRef,
      markerLaneRef,
      customCallbacks,
      omakaseRef,
      onFullscreenChange,
      onMute,
      onUnmute,
    });

    // Expose the "hello" method via the ref.
    useImperativeHandle(
      ref,
      () => ({
        hello: () => {
          if (!markerLaneRef.current) {
            console.warn(
              "Marker lane is not available yet. Video may still be loading.",
            );
            return null;
          }

          try {
            const periodMarker = new PeriodMarker({
              timeObservation: { start: currentTime, end: currentTime + 5 },
              editable: true,
              style: {
                ...PERIOD_MARKER_STYLE,
                color: randomHexColor(),
              },
            });
            markerLaneRef.current.addMarker(periodMarker);
            customCallbacks.onMarkerAdd?.(currentTime);

            console.log("playeref", playerRef);
            return periodMarker;
          } catch (error) {
            console.error("Error adding marker:", error);
            return null;
          }
        },
        getMarkerLane: () => {
          if (markerLaneRef.current) {
            return markerLaneRef.current;
          }
          console.warn(
            "Marker lane is not available yet. Video may still be loading.",
          );
          return null;
        },
        getCurrentTime: () => currentTime,
        formatToTimecode: (time: number) => {
          const hours = Math.floor(time / 3600);
          const minutes = Math.floor((time % 3600) / 60);
          const seconds = Math.floor(time % 60);
          const frames = Math.floor((time % 1) * 24);
          return `${hours.toString().padStart(2, "0")}:${minutes
            .toString()
            .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}:${frames
            .toString()
            .padStart(2, "0")}`;
        },
        seek: (time: number) => seek(time),
      }),
      [currentTime, customCallbacks, omakaseRef],
    );

    const handlePlayPause = () => {
      if (isPlaying) {
        pause();
      } else {
        play();
      }
    };

    // when dragging, move *ui* time only; commit seeks real media time
    const handleSeekChange = (_: Event, newValue: number | number[]) => {
      if (typeof newValue === "number") {
        setUiTime(newValue);
      }
    };
    const handleSeekCommitted = (
      _: Event | SyntheticEvent,
      newValue: number | number[],
    ) => {
      if (typeof newValue === "number") seek(newValue);
    };
    const handleVolumeChange = (event: Event, newValue: number | number[]) => {
      if (typeof newValue === "number") {
        setPlayerVolume(newValue);
        setVolumeState(newValue);
        if (newValue > 0) {
          lastNonZeroVolumeRef.current = newValue; // remember
          if (muted) {
            unmute();
            setMuted(false);
          } // auto-unmute when raising volume
        } else {
          setMuted(true); // volume 0 => show muted icon
        }
      }
    };

    const handleMuteToggle = () => {
      if (muted) {
        // unmute: restore last non-zero volume if current is 0
        unmute();
        if (volume === 0) {
          const restore = lastNonZeroVolumeRef.current || 100;
          setPlayerVolume(restore);
          setVolumeState(restore);
        }
        setMuted(false);
        onUnmute?.();
      } else {
        // mute: keep current volume for later restore
        if (volume > 0) lastNonZeroVolumeRef.current = volume;
        mute();
        setMuted(true);
        onMute?.();
      }
    };

    const handleFullscreenToggle = () => {
      toggleFullscreen();
      onFullscreenChange?.(true);
    };

    const formatTime = (time: number): string => {
      const hours = Math.floor(time / 3600);
      const minutes = Math.floor((time % 3600) / 60);
      const seconds = Math.floor(time % 60);
      if (isSmtpeFormat) {
        const frames = Math.floor((time % 1) * 25);
        return `${hours.toString().padStart(2, "0")}:${minutes
          .toString()
          .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}:${frames
          .toString()
          .padStart(2, "0")}`;
      } else {
        return `${hours.toString().padStart(2, "0")}:${minutes
          .toString()
          .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
      }
    };

    const handleTimeFormatToggle = () => {
      setIsSmtpeFormat(!isSmtpeFormat);
    };

    // Make the play/pause icon reflect reverse "movement" too
    const transportMoving = isPlaying || isShuttlingReverse;

    return (
      <Stack
        spacing={0}
        sx={{
          width: "100%",
          height: "10%",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <Popover
          open={openShortcuts}
          anchorEl={shortcutsAnchor}
          onClose={handleCloseShortcuts}
          anchorOrigin={{
            vertical: "top",
            horizontal: "center",
          }}
          transformOrigin={{
            vertical: "bottom",
            horizontal: "center",
          }}
          PaperProps={{
            sx: {
              borderRadius: 2,
              boxShadow: "0 8px 32px rgba(0, 0, 0, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              backdropFilter: "blur(10px)",
              maxWidth: 500,
            },
          }}
        >
          <Box sx={{ p: 3 }}>
            <Typography
              variant="h5"
              gutterBottom
              sx={{
                fontWeight: 600,
                mb: 2,
                background: "linear-gradient(45deg, #2196F3, #21CBF3)",
                backgroundClip: "text",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Keyboard Shortcuts
            </Typography>

            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                mb: 3,
                display: "block",
                fontStyle: "italic",
              }}
            >
              Click any shortcut below to execute the action
            </Typography>

            {Object.entries(
              SHORTCUTS.reduce(
                (acc, shortcut) => {
                  if (!acc[shortcut.category]) {
                    acc[shortcut.category] = [];
                  }
                  acc[shortcut.category].push(shortcut);
                  return acc;
                },
                {} as Record<string, typeof SHORTCUTS>,
              ),
            ).map(([category, shortcuts], categoryIndex) => (
              <Box
                key={category}
                sx={{
                  mb:
                    categoryIndex <
                    Object.keys(
                      SHORTCUTS.reduce(
                        (acc, shortcut) => {
                          if (!acc[shortcut.category]) {
                            acc[shortcut.category] = [];
                          }
                          acc[shortcut.category].push(shortcut);
                          return acc;
                        },
                        {} as Record<string, typeof SHORTCUTS>,
                      ),
                    ).length -
                      1
                      ? 2
                      : 0,
                }}
              >
                <Typography
                  variant="subtitle2"
                  sx={{
                    fontWeight: 600,
                    color: "text.secondary",
                    mb: 1,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {category}
                </Typography>

                <Grid container spacing={1}>
                  {shortcuts.map((shortcut, index) => (
                    <Grid item xs={12} key={`${category}-${index}`}>
                      <Button
                        fullWidth
                        variant="text"
                        onClick={() => {
                          try {
                            shortcut.action();
                          } catch (error) {
                            console.error(
                              "Error executing shortcut action:",
                              error,
                            );
                          }
                        }}
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          py: 1,
                          px: 1.5,
                          borderRadius: 1,
                          textTransform: "none",
                          color: "inherit",
                          cursor: "pointer",
                          "&:hover": {
                            backgroundColor: "action.hover",
                            transform: "translateY(-1px)",
                            boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
                          },
                          transition: "all 0.2s ease-in-out",
                        }}
                      >
                        <Typography
                          variant="body2"
                          sx={{
                            flex: 1,
                            color: "text.primary",
                            fontWeight: 500,
                            textAlign: "left",
                          }}
                        >
                          {shortcut.description}
                        </Typography>

                        <Box sx={{ display: "flex", gap: 0.5 }}>
                          {shortcut.keys.map((key, keyIndex) => (
                            <React.Fragment key={keyIndex}>
                              <Chip
                                label={key}
                                size="small"
                                sx={{
                                  height: 24,
                                  fontSize: "0.75rem",
                                  fontWeight: 600,
                                  backgroundColor: "grey.100",
                                  color: "grey.800",
                                  border: "1px solid",
                                  borderColor: "grey.300",
                                  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.1)",
                                  "& .MuiChip-label": {
                                    px: 1,
                                  },
                                  pointerEvents: "none",
                                }}
                              />
                              {keyIndex < shortcut.keys.length - 1 && (
                                <Typography
                                  variant="caption"
                                  sx={{
                                    alignSelf: "center",
                                    color: "text.secondary",
                                    mx: 0.5,
                                    pointerEvents: "none",
                                  }}
                                >
                                  /
                                </Typography>
                              )}
                            </React.Fragment>
                          ))}
                        </Box>
                      </Button>
                    </Grid>
                  ))}
                </Grid>

                {categoryIndex <
                  Object.keys(
                    SHORTCUTS.reduce(
                      (acc, shortcut) => {
                        if (!acc[shortcut.category]) {
                          acc[shortcut.category] = [];
                        }
                        acc[shortcut.category].push(shortcut);
                        return acc;
                      },
                      {} as Record<string, typeof SHORTCUTS>,
                    ),
                  ).length -
                    1 && <Divider sx={{ mt: 1.5 }} />}
              </Box>
            ))}
          </Box>
        </Popover>

        <Box
          onClick={onClickEvent}
          ref={playerContainerRef}
          id="omakase-player"
          sx={{
            width: "100%",
            height: "calc(100% - 250px)",
            position: "relative",
            bgcolor: "black",
            "& > *": {
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
            },
          }}
        />
        <Paper
          elevation={0}
          sx={{
            bgcolor: "rgba(0, 0, 0, 0.85)",
            height: "85px",
            borderRadius: 0,
            width: "100%",
          }}
        >
          <Box sx={{ px: 2, pt: 1 }}>
            <Slider
              value={uiTime}
              min={0}
              max={duration}
              step={0.1}
              onChange={handleSeekChange}
              onChangeCommitted={handleSeekCommitted}
              valueLabelDisplay="auto"
              components={{
                ValueLabel: (props) => ThumbLabel({ ...props, showThumbnails }),
              }}
              size="small"
              sx={{
                "& .MuiSlider-thumb": {
                  width: 12,
                  height: 12,
                  transition: "none",
                },
                "& .MuiSlider-rail": { opacity: 0.3 },
                "& .MuiSlider-track": { border: "none", transition: "none" },
              }}
            />
          </Box>
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ px: 2, pb: 1 }}
          >
            <IconButton
              onClick={handlePlayPause}
              size="small"
              sx={{
                color: "white",
                "&:hover": { bgcolor: "rgba(255, 255, 255, 0.1)" },
              }}
            >
              {transportMoving ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            <Typography
              variant="caption"
              onClick={handleTimeFormatToggle}
              sx={{
                color: "white",
                minWidth: 100,
                userSelect: "none",
                cursor: "pointer",
                "&:hover": { opacity: 0.8 },
              }}
            >
              {formatTime(currentTime)} / {formatTime(duration)}
            </Typography>
            <Box sx={{ flexGrow: 1 }} />
            <Box
              sx={{
                position: "relative",
                "&:hover .volume-slider": { opacity: 1, visibility: "visible" },
              }}
              onMouseEnter={() => setIsVolumeHovered(true)}
              onMouseLeave={() => setIsVolumeHovered(false)}
            >
              <IconButton
                onClick={handleMuteToggle}
                size="small"
                sx={{
                  color: "white",
                  "&:hover": { bgcolor: "rgba(255, 255, 255, 0.1)" },
                }}
              >
                {muted || volume === 0 ? <VolumeOffIcon /> : <VolumeUpIcon />}
              </IconButton>
              <Paper
                className="volume-slider"
                elevation={4}
                sx={{
                  position: "absolute",
                  bottom: "calc(100% + 8px)",
                  left: "50%",
                  transform: "translate(calc(-50% - 8px), 0)", // keep the Paper where you liked it
                  visibility: isVolumeHovered ? "visible" : "hidden",
                  opacity: isVolumeHovered ? 1 : 0,
                  transition: "opacity 0.2s, visibility 0.2s",
                  p: 1,
                  bgcolor: "rgba(0, 0, 0, 0.9)",

                  // center the slider inside
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  lineHeight: 0, // avoid baseline gap from inline blocks
                }}
              >
                <Tooltip
                  open={isVolumeHovered}
                  title={`${volume}%`}
                  placement="top"
                  arrow
                >
                  <Slider
                    orientation="vertical"
                    value={volume}
                    min={0}
                    max={100}
                    onChange={handleVolumeChange}
                    onChangeCommitted={(_, newValue) => {
                      if (typeof newValue === "number")
                        setPlayerVolume(newValue);
                    }}
                    sx={{
                      height: 100,
                      m: 0, // remove margins
                      p: 0, // remove padding
                      mt: -4, // optional tiny nudge up (~4px). Tweak to taste or remove.
                      "& .MuiSlider-rail": { opacity: 0.3 },
                      "& .MuiSlider-track": { border: "none" },
                    }}
                  />
                </Tooltip>
              </Paper>
            </Box>
            <IconButton
              onClick={handleFullscreenToggle}
              size="small"
              sx={{
                color: "white",
                "&:hover": { bgcolor: "rgba(255, 255, 255, 0.1)" },
              }}
            >
              <FullscreenIcon />
            </IconButton>
            <IconButton
              onClick={handleOpenShortcuts}
              size="small"
              sx={{
                color: "white",
                "&:hover": { bgcolor: "rgba(255, 255, 255, 0.1)" },
              }}
            >
              <KeyboardAltIcon />
            </IconButton>
          </Stack>
        </Paper>
        {/* Responsive timeline container */}
        <Box id="omakase-timeline" sx={{ width: "100%", height: "auto" }} />
      </Stack>
    );
  },
);

VideoViewer.displayName = "VideoViewer";
export default VideoViewer;
