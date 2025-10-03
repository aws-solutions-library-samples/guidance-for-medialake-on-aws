// AssetAudio.tsx
import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Typography,
  IconButton,
  Slider,
  Stack,
  Paper,
  useTheme,
  alpha,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import SkipPreviousIcon from "@mui/icons-material/SkipPrevious";
import MusicNoteIcon from "@mui/icons-material/MusicNote";

interface AssetAudioProps {
  src: string;
  alt?: string;
  compact?: boolean;
  size?: "small" | "medium" | "large";
  onAudioElementReady?: (audioElement: HTMLAudioElement) => void;
}

/**
 * Now there is only one getSizeStyles(...) function. It returns:
 *  • musicIconSize, playIconSize, buttonPadding, marginBottom (for compact mode)
 *  • waveformHeight, barWidth, barCount (for full mode)
 */
const getSizeStyles = (size: "small" | "medium" | "large") => {
  switch (size) {
    case "small":
      return {
        musicIconSize: 22,
        playIconSize: 18,
        buttonPadding: "4px",
        marginBottom: 0.5,

        waveformHeight: 100,
        barWidth: 2,
        barCount: 60,
      };
    case "large":
      return {
        musicIconSize: 40,
        playIconSize: 30,
        buttonPadding: "10px",
        marginBottom: 1,

        waveformHeight: 180,
        barWidth: 5,
        barCount: 100,
      };
    case "medium":
    default:
      return {
        musicIconSize: 32,
        playIconSize: 24,
        buttonPadding: "6px",
        marginBottom: 0.75,

        waveformHeight: 160,
        barWidth: 4,
        barCount: 80,
      };
  }
};

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
};

const AssetAudio: React.FC<AssetAudioProps> = ({
  src,
  alt,
  compact = false,
  size = "medium",
  onAudioElementReady,
}) => {
  const theme = useTheme();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(80);
  const [isMuted, setIsMuted] = useState(false);

  // Merge everything into one sizeStyles object
  const sizeStyles = getSizeStyles(size);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    // Register with media controller if provided
    if (onAudioElementReady) {
      onAudioElementReady(audio);
    }

    const updateTime = () => setCurrentTime(audio.currentTime);
    const handleLoadedMetadata = () => setDuration(audio.duration);
    const handleEnded = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", updateTime);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("ended", handleEnded);

    return () => {
      audio.removeEventListener("timeupdate", updateTime);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("ended", handleEnded);
    };
  }, [onAudioElementReady]);

  const togglePlay = () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying((prev) => !prev);
  };

  const handleTimeChange = (_: Event, newValue: number | number[]) => {
    if (!audioRef.current) return;
    const newTime = newValue as number;
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleVolumeChange = (_: Event, newValue: number | number[]) => {
    if (!audioRef.current) return;
    const newVolume = newValue as number;
    setVolume(newVolume);
    audioRef.current.volume = newVolume / 100;

    if (newVolume === 0) {
      setIsMuted(true);
    } else if (isMuted) {
      setIsMuted(false);
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    if (isMuted) {
      audioRef.current.volume = volume / 100;
      setIsMuted(false);
    } else {
      audioRef.current.volume = 0;
      setIsMuted(true);
    }
  };

  // Calculate progress for waveform percentage
  const progressPercentage = duration > 0 ? (currentTime / duration) * 100 : 0;

  // If compact mode is requested, render only the small overlay version
  if (compact) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          width: "100%",
          height: "100%",
          position: "relative",
          backgroundColor: alpha(theme.palette.background.paper, 0.6),
          borderRadius: 1,
          overflow: "hidden",
        }}
      >
        <audio ref={audioRef} src={src} preload="metadata" />

        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            width: "100%",
            height: "100%",
          }}
        >
          <MusicNoteIcon
            sx={{
              fontSize: sizeStyles.musicIconSize,
              color: alpha(theme.palette.primary.main, 0.8),
              mb: sizeStyles.marginBottom,
            }}
          />

          <IconButton
            onClick={togglePlay}
            size="small"
            sx={{
              backgroundColor: alpha(theme.palette.primary.main, 0.1),
              padding: sizeStyles.buttonPadding,
              "&:hover": {
                backgroundColor: alpha(theme.palette.primary.main, 0.2),
              },
              // ↓ Removed the duplicate `padding` here (that caused the TS1117 error)
            }}
          >
            {isPlaying ? (
              <PauseIcon sx={{ fontSize: sizeStyles.playIconSize }} />
            ) : (
              <PlayArrowIcon sx={{ fontSize: sizeStyles.playIconSize }} />
            )}
          </IconButton>

          {duration > 0 && (
            <Box
              sx={{
                position: "absolute",
                bottom: 0,
                left: 0,
                width: "100%",
                height: 3,
              }}
            >
              <Box
                sx={{
                  width: `${progressPercentage}%`,
                  height: "100%",
                  backgroundColor: theme.palette.secondary.main,
                  transition: "width 0.1s linear",
                }}
              />
            </Box>
          )}
        </Box>
      </Box>
    );
  }

  // Otherwise, render the full‐sized audio player with waveform, time slider, controls, etc.
  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        backgroundColor: alpha(theme.palette.background.paper, 0.7),
        borderRadius: 2,
        p: 3,
      }}
    >
      <audio ref={audioRef} src={src} preload="metadata" />

      {/* Waveform Visualization Container */}
      <Box
        sx={{
          width: "100%",
          maxWidth: 800,
          height: `${sizeStyles.waveformHeight}px`,
          mb: 4,
          position: "relative",
          borderRadius: 2,
          p: 2,
          backgroundColor: alpha(theme.palette.background.default, 0.3),
          overflow: "hidden",
        }}
      >
        <Box sx={{ position: "relative", height: "100%", width: "100%" }}>
          {/* Bars */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              height: "100%",
            }}
          >
            {Array.from({ length: sizeStyles.barCount }).map((_, index) => {
              const baseHeight = 20;
              const middleBoost =
                Math.sin((index / sizeStyles.barCount) * Math.PI) * 80;
              const randomVariation = Math.random() * 15;
              const height = baseHeight + middleBoost + randomVariation;

              const isBeforePlayhead =
                (index / sizeStyles.barCount) * 100 <= progressPercentage;

              return (
                <Box
                  key={index}
                  sx={{
                    width: `${sizeStyles.barWidth}px`,
                    height: `${height}px`,
                    backgroundColor: isBeforePlayhead
                      ? alpha(theme.palette.secondary.main, 0.8)
                      : alpha(theme.palette.primary.main, 0.5),
                    borderRadius: "2px",
                    transition: "height 0.1s ease, background-color 0.2s ease",
                  }}
                />
              );
            })}
          </Box>

          {/* Playhead Indicator */}
          <Box
            sx={{
              position: "absolute",
              left: `${progressPercentage}%`,
              top: 0,
              bottom: 0,
              width: "2px",
              backgroundColor: theme.palette.error.main,
              transform: "translateX(-50%)",
              zIndex: 2,
              transition: "left 0.1s ease-out",
            }}
          />

          {/* Center Baseline */}
          <Box
            sx={{
              position: "absolute",
              left: 0,
              right: 0,
              top: "50%",
              height: "1px",
              backgroundColor: alpha(theme.palette.text.secondary, 0.3),
              zIndex: 1,
            }}
          />
        </Box>
      </Box>

      {/* Controls Panel */}
      <Paper
        elevation={0}
        sx={{
          width: "100%",
          maxWidth: 800,
          p: 2,
          borderRadius: 2,
          backgroundColor: alpha(theme.palette.background.paper, 0.9),
          backdropFilter: "blur(10px)",
        }}
      >
        <Stack spacing={2}>
          <Typography variant="h6" align="center" sx={{ fontWeight: 500 }}>
            {alt || "Audio Player"}
          </Typography>

          {/* Time Slider + Timestamps */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              px: 1,
            }}
          >
            <Typography variant="body2">{formatTime(currentTime)}</Typography>
            <Slider
              value={currentTime}
              max={duration || 100}
              onChange={handleTimeChange}
              aria-label="time-slider"
              color="secondary"
              sx={{
                mx: 2,
                "& .MuiSlider-thumb": {
                  width: 12,
                  height: 12,
                },
              }}
            />
            <Typography variant="body2">{formatTime(duration)}</Typography>
          </Box>

          {/* Play / Pause / Skip Controls */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <IconButton
              aria-label="previous"
              sx={{ color: theme.palette.text.secondary }}
            >
              <SkipPreviousIcon fontSize="large" />
            </IconButton>
            <IconButton
              aria-label={isPlaying ? "pause" : "play"}
              onClick={togglePlay}
              sx={{
                mx: 2,
                color: theme.palette.primary.main,
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                "&:hover": {
                  backgroundColor: alpha(theme.palette.primary.main, 0.2),
                },
              }}
            >
              {isPlaying ? (
                <PauseIcon fontSize="large" />
              ) : (
                <PlayArrowIcon fontSize="large" />
              )}
            </IconButton>
            <IconButton
              aria-label="next"
              sx={{ color: theme.palette.text.secondary }}
            >
              <SkipNextIcon fontSize="large" />
            </IconButton>
          </Box>

          {/* Volume / Mute */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              px: 2,
            }}
          >
            <IconButton
              aria-label="toggle-mute"
              onClick={toggleMute}
              sx={{ color: theme.palette.text.secondary }}
            >
              {isMuted ? <VolumeOffIcon /> : <VolumeUpIcon />}
            </IconButton>
            <Slider
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              aria-label="volume-slider"
              color="secondary"
              size="small"
              sx={{
                ml: 2,
                width: 100,
                "& .MuiSlider-thumb": {
                  width: 8,
                  height: 8,
                },
              }}
            />
          </Box>
        </Stack>
      </Paper>

      <Typography
        variant="caption"
        sx={{ mt: 2, color: theme.palette.text.secondary }}
      >
        Format: MP3 • Sample Rate: 44.1 kHz • Bit Rate: 320 kbps • Channels:
        Stereo
      </Typography>
    </Box>
  );
};

export default AssetAudio;
