import { useCallback, useRef, useEffect, useMemo, useState } from "react";
import { PeriodMarker } from "@byomakase/omakase-player";
import { PERIOD_MARKER_STYLE } from "./OmakaseTimeLineConstants";
import { randomHexColor } from "./utils";

interface UseVideoKeyboardShortcutsProps {
  // Player control functions
  play: () => void;
  pause: () => void;
  seek: (time: number) => void;
  setPlaybackRate: (rate: number) => void;
  mute: () => void;
  unmute: () => void;
  toggleFullscreen: () => void;

  // Player state
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  muted: boolean;

  // Volume control
  setPlayerVolume: (volume: number) => void;
  setVolumeState: (volume: number) => void;
  setMuted: (muted: boolean) => void;
  setIsVolumeHovered: (hovered: boolean) => void;
  lastNonZeroVolumeRef: React.MutableRefObject<number>;
  volumeHoverTimeoutRef: React.MutableRefObject<NodeJS.Timeout | null>;

  // Marker functionality
  markerLaneRef: React.MutableRefObject<any | null>;
  customCallbacks: {
    onMarkerAdd?: (time: number) => void;
  };

  // Player ref for frame operations
  omakaseRef: React.MutableRefObject<any | null>;

  // Fullscreen callback
  onFullscreenChange?: (isFullscreen: boolean) => void;

  // Mute/unmute callbacks
  onMute?: () => void;
  onUnmute?: () => void;
}

export const useVideoKeyboardShortcuts = ({
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
  setVolumeState,
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
}: UseVideoKeyboardShortcutsProps) => {
  // --- Jog/Shuttle helpers ---
  const SHUTTLE_STOPS = useMemo(
    () =>
      [-16, -8, -4, -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2, 4, 8, 16] as const,
    [],
  );
  const [shuttleIdx, setShuttleIdx] = useState(
    SHUTTLE_STOPS.indexOf(1 as (typeof SHUTTLE_STOPS)[number]),
  );

  // virtual rate to show UI state
  const [currentPlaybackRate, setCurrentPlaybackRate] = useState(1);

  // interval used to simulate reverse playback
  const reverseTimerRef = useRef<number | null>(null);

  // keep an FPS value for reverse stepping; default to 25 if unknown
  const fpsRef = useRef<number>(25);

  // Is the player currently moving because we're simulating reverse?
  const [isShuttlingReverse, setIsShuttlingReverse] = useState(false);

  // Last non-zero shuttle speed (signed). Used to resume on K/Space.
  const lastNonZeroShuttleRef = useRef<number>(1);

  // Keep refs for toggle logic used inside the keydown listener.
  const isPlayingRef = useRef(isPlaying);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  const isShuttlingReverseRef = useRef(isShuttlingReverse);
  useEffect(() => {
    isShuttlingReverseRef.current = isShuttlingReverse;
  }, [isShuttlingReverse]);

  // Double-tap detection for K/Space to reset to 1x forward
  const lastKeyRef = useRef<string>("");
  const lastKeyTimeRef = useRef<number>(0);
  const DOUBLE_TAP_MS = 250;

  // ensure we don't leave a timer running
  const clearReverseTimer = useCallback(() => {
    if (reverseTimerRef.current !== null) {
      window.clearInterval(reverseTimerRef.current);
      reverseTimerRef.current = null;
    }
  }, []);

  // pick up the actual frame rate once the video is loaded
  useEffect(() => {
    const v = omakaseRef.current?.video;
    if (!v?.onVideoLoaded$) return;
    const sub = v.onVideoLoaded$.subscribe(() => {
      try {
        const fr = v.getFrameRate();
        if (Number.isFinite(fr) && fr > 0) fpsRef.current = fr;
      } catch {}
    });
    return () => sub?.unsubscribe();
  }, [omakaseRef]);

  // core: apply shuttle speed (pos=forward, 0=stop, neg=reverse simulated)
  const applyShuttleSpeed = useCallback(
    (target: number) => {
      clearReverseTimer();
      setCurrentPlaybackRate(target);

      if (target !== 0) {
        lastNonZeroShuttleRef.current = target;
      }

      if (target === 0) {
        setIsShuttlingReverse(false);
        pause();
        setPlaybackRate(1);
        return;
      }

      if (target > 0) {
        setIsShuttlingReverse(false);
        setPlaybackRate(target); // 0.1–16 supported
        play();
      } else {
        setIsShuttlingReverse(true);
        pause(); // required for negative stepping
        setPlaybackRate(1);

        const fps = fpsRef.current || 25;
        const abs = Math.abs(target);
        const framesPerTick = abs >= 1 ? Math.round(abs) : 1;
        const intervalMs = abs >= 1 ? 1000 / fps : 1000 / (fps * abs);

        reverseTimerRef.current = window.setInterval(
          () => {
            omakaseRef.current?.video
              .seekFromCurrentFrame(-framesPerTick)
              .subscribe();
          },
          Math.max(8, intervalMs),
        );
      }
    },
    [play, pause, setPlaybackRate, omakaseRef, clearReverseTimer],
  );

  // helpers to bump the shuttle speed up/down the ladder
  const bumpShuttle = useCallback(
    (dir: 1 | -1) => {
      setShuttleIdx((prev) => {
        const next = Math.min(
          SHUTTLE_STOPS.length - 1,
          Math.max(0, prev + dir),
        );
        applyShuttleSpeed(SHUTTLE_STOPS[next]);
        return next;
      });
    },
    [applyShuttleSpeed, SHUTTLE_STOPS],
  );

  // Create a single transport toggle for K/Space and the play button
  const toggleTransport = useCallback(() => {
    const moving = isPlayingRef.current || isShuttlingReverseRef.current;
    if (moving) {
      // Stop, but keep lastNonZeroShuttleRef so a second press resumes at that speed/direction
      applyShuttleSpeed(0);
    } else {
      // Resume at last non-zero (could be reverse or forward)
      const resume = lastNonZeroShuttleRef.current || 1;
      applyShuttleSpeed(resume);
    }
  }, [applyShuttleSpeed]);

  // Reset to 1x forward speed
  const resetSpeed = useCallback(
    (playAfter = true) => {
      const idx1 = SHUTTLE_STOPS.indexOf(1 as any);
      setShuttleIdx(idx1);
      lastNonZeroShuttleRef.current = 1;
      if (playAfter) {
        applyShuttleSpeed(1); // plays forward at 1×
      } else {
        clearReverseTimer();
        setCurrentPlaybackRate(1);
        setPlaybackRate(1);
        setIsShuttlingReverse(false);
        // leave paused
      }
    },
    [SHUTTLE_STOPS, applyShuttleSpeed, clearReverseTimer, setPlaybackRate],
  );

  // Stop transport (keeps lastNonZeroShuttleRef) then step one frame
  const stopTransport = useCallback(() => {
    // Using your existing function guarantees pause + clears reverse timer
    // and preserves lastNonZeroShuttleRef for resume-on-K
    applyShuttleSpeed(0);
  }, [applyShuttleSpeed]);

  const stepFrame = useCallback(
    (dir: -1 | 1) => {
      // 1) stop if we're moving (forward or reverse)
      stopTransport();
      // 2) step exactly one frame (Omakase requires paused state for frame-seek)
      omakaseRef.current?.video.seekFromCurrentFrame(dir).subscribe();
    },
    [stopTransport, omakaseRef],
  );

  // keep UI rate in sync when forward rate changes
  useEffect(() => {
    const v = omakaseRef.current?.video;
    if (!v?.onPlaybackRateChange$) return;
    const sub = v.onPlaybackRateChange$.subscribe(({ playbackRate }) => {
      // Only update if we're not currently simulating reverse
      if (reverseTimerRef.current === null) {
        setCurrentPlaybackRate(playbackRate);
      }
    });
    return () => sub?.unsubscribe();
  }, [omakaseRef]);

  // safety: clear timer on unmount
  useEffect(() => () => clearReverseTimer(), [clearReverseTimer]);

  const handleMuteToggle = useCallback(() => {
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
  }, [
    muted,
    unmute,
    volume,
    lastNonZeroVolumeRef,
    setPlayerVolume,
    setVolumeState,
    setMuted,
    onUnmute,
    mute,
    onMute,
  ]);

  const handleFullscreenToggle = useCallback(() => {
    toggleFullscreen();
    onFullscreenChange?.(true);
  }, [toggleFullscreen, onFullscreenChange]);

  // Keyboard event handler
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.target as HTMLElement).tagName === "INPUT" ||
        (event.target as HTMLElement).tagName === "TEXTAREA"
      ) {
        return;
      }

      // Double-tap detection
      const now = performance.now();
      const isDoubleTap =
        event.key === lastKeyRef.current &&
        now - lastKeyTimeRef.current < DOUBLE_TAP_MS;
      lastKeyRef.current = event.key;
      lastKeyTimeRef.current = now;

      switch (event.key) {
        case " ": // Space or K toggles transport / double-tap resets to 1x
        case "k":
        case "K":
          event.preventDefault();
          if (isDoubleTap) {
            resetSpeed(true); // play at 1× forward
          } else {
            toggleTransport(); // existing play/pause respecting speed
          }
          break;
        case "j": // decrease speed; crosses 0 into reverse
        case "J":
          event.preventDefault();
          bumpShuttle(-1);
          break;
        case "l": // increase speed; crosses 0 into forward
        case "L":
          event.preventDefault();
          bumpShuttle(1);
          break;
        case "ArrowLeft": // step back 5 s
          event.preventDefault();
          seek(Math.max(currentTime - 5, 0));
          break;
        case "ArrowRight": // step forward 5 s
          event.preventDefault();
          seek(Math.min(currentTime + 5, duration));
          break;
        case "ArrowUp": // volume up 10 %
          event.preventDefault();
          {
            const newVol = Math.min(volume + 10, 100);
            setPlayerVolume(newVol);
            setVolumeState(newVol);
            if (newVol > 0) {
              lastNonZeroVolumeRef.current = newVol;
              if (muted) {
                unmute();
                setMuted(false);
              }
            } else {
              setMuted(true);
            }
            // show slider and hide after 1.5 s
            setIsVolumeHovered(true);
            if (volumeHoverTimeoutRef.current) {
              clearTimeout(volumeHoverTimeoutRef.current);
            }
            volumeHoverTimeoutRef.current = setTimeout(() => {
              setIsVolumeHovered(false);
            }, 1500);
          }
          break;
        case "ArrowDown": // volume down 10 %
          event.preventDefault();
          {
            const newVol = Math.max(volume - 10, 0);
            setPlayerVolume(newVol);
            setVolumeState(newVol);
            setMuted(newVol === 0);
            setIsVolumeHovered(true);
            if (volumeHoverTimeoutRef.current) {
              clearTimeout(volumeHoverTimeoutRef.current);
            }
            volumeHoverTimeoutRef.current = setTimeout(() => {
              setIsVolumeHovered(false);
            }, 1500);
          }
          break;
        case "m": // toggle mute/unmute
        case "M":
          event.preventDefault();
          handleMuteToggle();
          break;
        case "f": // fullscreen
        case "F":
          event.preventDefault();
          handleFullscreenToggle();
          break;
        case "i": // add marker
        case "I":
          event.preventDefault();
          if (markerLaneRef.current) {
            try {
              const periodMarker = new PeriodMarker({
                timeObservation: { start: currentTime, end: currentTime + 2 },
                editable: true,
                style: {
                  ...PERIOD_MARKER_STYLE,
                  color: randomHexColor(),
                },
              });
              markerLaneRef.current.addMarker(periodMarker);
              customCallbacks.onMarkerAdd?.(currentTime);
              console.log("Marker added at time:", currentTime);
            } catch (error) {
              console.error("Error adding marker:", error);
            }
          } else {
            console.warn(
              "Marker lane is not available yet. Video may still be loading.",
            );
          }
          break;
        case ",": // frame backward
          event.preventDefault();
          stepFrame(-1);
          break;
        case ".": // frame forward
          event.preventDefault();
          stepFrame(1);
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (volumeHoverTimeoutRef.current) {
        clearTimeout(volumeHoverTimeoutRef.current);
      }
    };
  }, [
    currentTime,
    duration,
    volume,
    muted,
    toggleTransport,
    resetSpeed,
    stepFrame,
    bumpShuttle,
    seek,
    setPlayerVolume,
    setVolumeState,
    setMuted,
    setIsVolumeHovered,
    lastNonZeroVolumeRef,
    volumeHoverTimeoutRef,
    unmute,
    handleMuteToggle,
    handleFullscreenToggle,
    markerLaneRef,
    customCallbacks,
  ]);

  // Keyboard shortcuts for help display
  const SHORTCUTS: string[] = [
    "Space / K – Play/Pause",
    "J – Shuttle slower/reverse",
    "L – Shuttle faster/forward",
    "← / → – Step 5 s backward/forward",
    ", / . – Frame backward/forward",
    "↑ / ↓ – Volume up/down",
    "F – Toggle fullscreen",
    "M – Mute/Unmute",
    "I – Add marker",
  ];

  return {
    SHORTCUTS,
    toggleTransport,
    currentPlaybackRate,
    isShuttlingReverse,
  };
};
