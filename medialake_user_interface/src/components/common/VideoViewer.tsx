// VideoViewer.tsx
import React, {
    useEffect,
    useRef,
    useCallback,
    useState,
    FC,
    SyntheticEvent,
    useMemo,
} from 'react';
import { OmakasePlayer } from '@byomakase/omakase-player';
import { Tooltip, IconButton, Stack, Slider, Box, Typography, Paper } from '@mui/material'

import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import VolumeOffIcon from '@mui/icons-material/VolumeOff';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
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
    showThumbnails?: boolean;
}

/**
 * A custom hook that creates and manages the OmakasePlayer instance.
 * (Here we also add local state for currentTime and duration.)
 */
const useOmakasePlayer = (
    videoSrc: string,
    containerRef: React.RefObject<HTMLDivElement>,
    callbacks: Partial<VideoViewerProps>
) => {
    const playerRef = useRef<OmakasePlayer | null>(null);

    // We'll store the incoming callbacks in a ref so that changes to these
    // callbacks do NOT trigger re-initialization of the player:
    const callbacksRef = useRef(callbacks);
    useEffect(() => {
        callbacksRef.current = callbacks;
    }, [callbacks]);

    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);

    const initializePlayer = useCallback(() => {
        if (!containerRef.current) return;

        // Create the OmakasePlayer only once per videoSrc/containerRef change:
        const player = new OmakasePlayer({
            playerHTMLElementId: containerRef.current.id,
            // mediaChrome: 'disabled'
        });
        playerRef.current = player;

        const subscriptions = [
            player.loadVideo(videoSrc, 25).subscribe({
                next: (video) => {
                    console.log(
                        `Video loaded. Duration: ${video.duration}, totalFrames: ${video.totalFrames}`
                    );
                    setDuration(video.duration);
                },
                error: (error) => {
                    console.error('Error loading video:', error);
                    callbacksRef.current.onError?.(error);
                },
                complete: () => {
                    console.log('Video loading completed');
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
                    console.log(`Video pause. Timestamp: ${event.currentTime}`);
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
                    console.log('Video buffering');
                    callbacksRef.current.onBuffering?.();
                },
            }),
            player.video.onEnded$.subscribe({
                next: () => {
                    console.log('Video ended');
                    callbacksRef.current.onEnded?.();
                },
            }),
            player.video.onFullscreenChange$.subscribe({
                next: (event) => {
                    // If you wish, forward fullscreen changes:
                    // callbacksRef.current.onFullscreenChange?.(event.isFullscreen);
                },
            }),
            player.video.onVolumeChange$.subscribe({
                next: (event) => {
                    console.log(`Volume changed: ${event.volume}`);
                    callbacksRef.current.onVolumeChange?.(event.volume);
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
                    console.error('Video error:', error);
                    callbacksRef.current.onError?.(error);
                },
            }),
        ];

        return () => {
            // Clean up subscriptions and the player on unmount or when videoSrc changes
            subscriptions.forEach((subscription) => subscription.unsubscribe());
            // If you need to fully remove the player from the DOM, do:
            // player.destroy();
            playerRef.current = null;
        };
    }, [videoSrc, containerRef]);
    // Note: We do NOT include `callbacks` in dependency array, to avoid re-init.

    useEffect(() => {
        const cleanup = initializePlayer();
        return cleanup;
    }, [initializePlayer]);

    // Player control methods:
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
                    console.log('Safe zone removed:', id);
                    callbacksRef.current.onRemoveSafeZone?.(id);
                },
                error: (error) => {
                    console.error('Error removing safe zone:', error);
                },
            });
        },
        []
    );

    const clearSafeZones = useCallback(() => {
        playerRef.current?.video.clearSafeZones().subscribe({
            next: () => {
                console.log('All safe zones cleared');
                callbacksRef.current.onClearSafeZones?.();
            },
            error: (error) => {
                console.error('Error clearing safe zones:', error);
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
    };
};

/**
 * A custom value label component for the seek slider.
 * It shows a thumbnail image based on the current slider value.
 */
function ThumbLabel(props: any) {
    const { children, open, value, showThumbnails = true } = props;
    const lastValueRef = useRef(value);
    const [thumbnailUrl, setThumbnailUrl] = useState(() => getThumbnailForTime(value));
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
        }, 50); // 50ms debounce for smoother updates

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
                        style={{ width: 100, display: 'block' }}
                    />
                ) : value.toFixed(1)
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
    const hours = Math.floor(time / 3600);
    const minutes = Math.floor((time % 3600) / 60);
    const seconds = Math.floor(time % 60);
    const frames = Math.floor((time % 1) * 25); // Using 25 fps as per loadVideo config

    const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
    return `https://placehold.co/100x56/black/white?text=${timeString}`;
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
    showThumbnails = false,
}) => {
    const playerContainerRef = useRef<HTMLDivElement>(null);

    // Local state to track whether the video is playing, the volume level, and mute status.
    const [isPlaying, setIsPlaying] = useState(false);
    const [volume, setVolumeState] = useState(100);
    const [muted, setMuted] = useState(false);
    const [isSmtpeFormat, setIsSmtpeFormat] = useState(true);
    const [isVolumeHovered, setIsVolumeHovered] = useState(false);

    // Define callbacks that update local state, then call the parent props:
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
        ]
    );

    // Hook that manages the OmakasePlayer lifecycle
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
        setCurrentTime,
    } = useOmakasePlayer(videoSrc, playerContainerRef, customCallbacks);

    // Handlers for UI controls:
    const handlePlayPause = () => {
        if (isPlaying) {
            pause();
        } else {
            play();
        }
    };

    const handleSeekChange = (_: Event, newValue: number | number[]) => {
        if (typeof newValue === 'number') {
            setCurrentTime(newValue);
        }
    };

    const handleSeekCommitted = (
        _: Event | SyntheticEvent,
        newValue: number | number[]
    ) => {
        if (typeof newValue === 'number') {
            seek(newValue);
        }
    };

    const handleVolumeChange = (event: Event, newValue: number | number[]) => {
        if (typeof newValue === 'number') {
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
        // If you'd like to track actual fullscreen state, you'd do it in onFullscreenChange:
        onFullscreenChange?.(true);
    };

    // A helper to format seconds into either SMPTE timecode (HH:MM:SS:FF) or HH:MM:SS
    const formatTime = (time: number): string => {
        const hours = Math.floor(time / 3600);
        const minutes = Math.floor((time % 3600) / 60);
        const seconds = Math.floor(time % 60);

        if (isSmtpeFormat) {
            const frames = Math.floor((time % 1) * 25); // Using 25 fps as per loadVideo config
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
        } else {
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    };

    const handleTimeFormatToggle = () => {
        setIsSmtpeFormat(!isSmtpeFormat);
    };

    return (
        <Stack spacing={0} sx={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
            <Box
                onClick={onClickEvent}
                ref={playerContainerRef}
                id="omakase-player"
                sx={{
                    width: '100%',
                    height: 'calc(100% - 80px)',
                    position: 'relative',
                    bgcolor: 'black',
                    '& > *': { position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' },
                }}
            />

            <Paper
                elevation={0}
                sx={{
                    bgcolor: 'rgba(0, 0, 0, 0.85)',
                    height: '85px',
                    borderRadius: 0,
                    width: '100%'
                }}
            >
                <Box sx={{ px: 2, pt: 1 }}>
                    <Slider
                        value={currentTime}
                        min={0}
                        max={duration}
                        step={0.1}
                        onChange={handleSeekChange}
                        onChangeCommitted={handleSeekCommitted}
                        valueLabelDisplay="auto"
                        components={{
                            ValueLabel: (props) => ThumbLabel({ ...props, showThumbnails })
                        }}
                        size="small"
                        sx={{
                            '& .MuiSlider-thumb': {
                                width: 12,
                                height: 12,
                                transition: 'none'
                            },
                            '& .MuiSlider-rail': {
                                opacity: 0.3
                            },
                            '& .MuiSlider-track': {
                                border: 'none',
                                transition: 'none'
                            }
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
                            color: 'white',
                            '&:hover': {
                                bgcolor: 'rgba(255, 255, 255, 0.1)'
                            }
                        }}
                    >
                        {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
                    </IconButton>

                    <Typography
                        variant="caption"
                        onClick={handleTimeFormatToggle}
                        sx={{
                            color: 'white',
                            minWidth: 100,
                            userSelect: 'none',
                            cursor: 'pointer',
                            '&:hover': {
                                opacity: 0.8
                            }
                        }}
                    >
                        {formatTime(currentTime)} / {formatTime(duration)}
                    </Typography>

                    <Box sx={{ flexGrow: 1 }} />

                    <Box
                        sx={{
                            position: 'relative',
                            '&:hover .volume-slider': {
                                opacity: 1,
                                visibility: 'visible'
                            }
                        }}
                        onMouseEnter={() => setIsVolumeHovered(true)}
                        onMouseLeave={() => setIsVolumeHovered(false)}
                    >
                        <IconButton
                            onClick={handleMuteToggle}
                            size="small"
                            sx={{
                                color: 'white',
                                '&:hover': {
                                    bgcolor: 'rgba(255, 255, 255, 0.1)'
                                }
                            }}
                        >
                            {muted || volume === 0 ? <VolumeOffIcon /> : <VolumeUpIcon />}
                        </IconButton>
                        <Paper
                            className="volume-slider"
                            elevation={4}
                            sx={{
                                position: 'absolute',
                                bottom: '100%',
                                left: '50%',
                                transform: 'translateX(-50%)',
                                visibility: 'hidden',
                                opacity: 0,
                                transition: 'opacity 0.2s, visibility 0.2s',
                                p: 1,
                                bgcolor: 'rgba(0, 0, 0, 0.9)',
                                mb: 1
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
                                    sx={{
                                        height: 100,
                                        '& .MuiSlider-rail': {
                                            opacity: 0.3
                                        },
                                        '& .MuiSlider-track': {
                                            border: 'none'
                                        }
                                    }}
                                />
                            </Tooltip>
                        </Paper>
                    </Box>

                    <IconButton
                        onClick={handleFullscreenToggle}
                        size="small"
                        sx={{
                            color: 'white',
                            '&:hover': {
                                bgcolor: 'rgba(255, 255, 255, 0.1)'
                            }
                        }}
                    >
                        <FullscreenIcon />
                    </IconButton>
                </Stack>
            </Paper>
        </Stack>
    );
};

export default VideoViewer;
