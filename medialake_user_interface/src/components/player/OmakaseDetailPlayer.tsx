import React, { useEffect, useId, useMemo } from "react";
import { useTheme } from "@mui/material/styles";
import { Alert, Box } from "@mui/material";
import { createOmakaseThemeConfig } from "./createOmakaseThemeConfig";
import { useDetailPlayer, type UseDetailPlayerResult } from "./useDetailPlayer";
import { usePlayerKeyboardShortcutsCore } from "./usePlayerKeyboardShortcutsCore";
import { useMarkerTrackSync } from "./useMarkerTrackSync";
import { DETAIL_PLAYER_CONTAINER_ID_PREFIX } from "./DetailPlayerConstants";

// Omakase player styles are imported globally in main.tsx

export interface OmakaseDetailPlayerProps {
  src: string;
  mediaType: "video" | "audio";
  assetId: string;
  onTimeUpdate?: (time: number) => void;
  onPlayerReady?: (result: UseDetailPlayerResult) => void;
}

export function OmakaseDetailPlayer({
  src,
  mediaType,
  assetId,
  onTimeUpdate,
  onPlayerReady,
}: OmakaseDetailPlayerProps) {
  const theme = useTheme();

  // Memoize theme config — only recompute when palette mode or media type changes
  const themeResult = useMemo(
    () => createOmakaseThemeConfig(theme, mediaType),
    [theme.palette.mode, mediaType]
  );
  const { cssVars } = themeResult;

  const reactId = useId();
  const containerId = `${DETAIL_PLAYER_CONTAINER_ID_PREFIX}-${reactId.replace(/:/g, "")}`;

  const result = useDetailPlayer({
    containerId,
    src,
    mediaType,
    assetId,
    themeResult,
    onTimeUpdate,
  });

  usePlayerKeyboardShortcutsCore({
    play: result.play,
    pause: result.pause,
    seek: result.seek,
    setPlaybackRate: result.setPlaybackRate,
    toggleFullscreen: result.toggleFullscreen,
    isPlaying: result.isPlaying,
    volume: result.volume,
    muted: result.muted,
    setPlayerVolume: result.setVolume,
    mute: result.mute,
    unmute: result.unmute,
    markerAdapter: result.markerAdapter,
    omakaseRef: result.playerRef,
  });

  // Sync coordinator markers → chroming marker track (thin bar above progress bar)
  useMarkerTrackSync({
    playerRef: result.playerRef,
    markerAdapter: result.markerAdapter,
    isReady: result.isMarkerReady,
  });

  useEffect(() => {
    if (result.isMarkerReady) {
      onPlayerReady?.(result);
    }
  }, [result.isMarkerReady, onPlayerReady]);

  return (
    <Box sx={{ width: "100%", height: "100%", position: "relative" }}>
      <div id={containerId} style={{ width: "100%", height: "100%", ...cssVars }} />
      {!result.isMarkerReady && (
        <Alert
          severity="info"
          sx={{
            position: "absolute",
            top: 8,
            left: 8,
            zIndex: 1,
            opacity: 0.9,
          }}
        >
          Marker system loading…
        </Alert>
      )}
    </Box>
  );
}

export default OmakaseDetailPlayer;
