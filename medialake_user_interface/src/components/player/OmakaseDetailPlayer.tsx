import React, { useEffect, useId, useMemo } from "react";
import { useTheme } from "@mui/material/styles";
import { Box } from "@mui/material";
import { createOmakaseThemeConfig } from "./createOmakaseThemeConfig";
import { useDetailPlayer, type UseDetailPlayerResult } from "./useDetailPlayer";
import { usePlayerKeyboardShortcutsCore } from "./usePlayerKeyboardShortcutsCore";
import { DETAIL_PLAYER_CONTAINER_ID_PREFIX } from "./DetailPlayerConstants";

// Omakase player styles are imported globally in main.tsx

export interface OmakaseDetailPlayerProps {
  src: string;
  mediaType: "video" | "audio";
  assetId: string;
  /**
   * Media frame rate — a number, or an ffprobe rational such as `"30000/1001"`.
   * Passed straight to Omakase so frame stepping and SMPTE display match the
   * media rather than assuming 25fps.
   */
  frameRate?: number | string;
  onTimeUpdate?: (time: number) => void;
  onPlayerReady?: (result: UseDetailPlayerResult) => void;
}

export function OmakaseDetailPlayer({
  src,
  mediaType,
  assetId,
  frameRate,
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
    frameRate,
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
    addUserMarker: result.addUserMarker,
    userTrackRef: result.userTrackRef,
    semanticTrackRef: result.semanticTrackRef,
    isMarkersReady: result.isReady,
    omakaseRef: result.playerRef,
  });

  // Markers no longer need a sync step. They live on MarkerTracks owned by
  // useMarkerTracks, and the chroming marker bars render those tracks directly —
  // so there is nothing to mirror between a coordinator and the player.

  // Republish on every change to `result`, not just the first time `isReady`
  // flips. Marker state lives in this subtree, so the parent (which renders the
  // marker panel in the sidebar) only sees new markers if we hand it the new
  // value. Keying this effect on `result.isReady` alone published exactly once —
  // with the initial empty marker arrays — and the panel then showed 0 markers
  // forever even though the tracks and their marker bars were correct.
  //
  // `useDetailPlayer` returns a memo, so `result` is referentially stable except
  // when markers or playback state actually change. That makes this safe: a
  // re-render caused by the parent does not re-fire the effect.
  useEffect(() => {
    if (result.isReady) {
      onPlayerReady?.(result);
    }
  }, [result, onPlayerReady]);

  return (
    <Box sx={{ width: "100%", height: "100%", position: "relative" }}>
      <div id={containerId} style={{ width: "100%", height: "100%", ...cssVars }} />
    </Box>
  );
}

export default OmakaseDetailPlayer;
