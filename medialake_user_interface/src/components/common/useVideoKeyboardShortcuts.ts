import React, { useCallback, useRef, useEffect, useMemo, useState } from "react";
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
  volumeHoverTimeoutRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;

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
  play: originalPlay,
  pause: originalPause,
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
    () => [-16, -8, -4, -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2, 4, 8, 16] as const,
    []
  );
  const [, setShuttleIdx] = useState(SHUTTLE_STOPS.indexOf(1 as (typeof SHUTTLE_STOPS)[number]));

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
  // Wrap play and pause with logging
  const play = useCallback(() => {
    console.log(
      `PLAY() called from keyboard shortcuts - Stack:`,
      new Error().stack?.split("\n").slice(1, 4).join("\n")
    );
    originalPlay();
  }, [originalPlay]);

  const pause = useCallback(() => {
    console.log(
      `PAUSE() called from keyboard shortcuts - Stack:`,
      new Error().stack?.split("\n").slice(1, 4).join("\n")
    );
    originalPause();
  }, [originalPause]);

  const isPlayingRef = useRef(isPlaying);

  // Prevent video element from receiving focus to avoid native browser controls
  useEffect(() => {
    const omakasePlayer = omakaseRef?.current;
    const htmlVideoElement = omakasePlayer?.video?.htmlVideoElement;

    if (htmlVideoElement) {
      console.log(`INITIALIZING video element to prevent focus conflicts`);
      // Disable tabindex to prevent focus
      htmlVideoElement.setAttribute("tabindex", "-1");
      // Remove any existing focus
      htmlVideoElement.blur();
      console.log(`VIDEO ELEMENT configured to prevent native keyboard controls`);
    }
  }, [omakaseRef]);
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
      } catch {
        // Ignore frame rate detection errors
      }
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
            omakaseRef.current?.video.seekFromCurrentFrame(-framesPerTick).subscribe();
          },
          Math.max(8, intervalMs)
        );
      }
    },
    [play, pause, setPlaybackRate, omakaseRef, clearReverseTimer]
  );

  // helpers to bump the shuttle speed up/down the ladder
  const bumpShuttle = useCallback(
    (dir: 1 | -1) => {
      setShuttleIdx((prev) => {
        const next = Math.min(SHUTTLE_STOPS.length - 1, Math.max(0, prev + dir));
        applyShuttleSpeed(SHUTTLE_STOPS[next]);
        return next;
      });
    },
    [applyShuttleSpeed, SHUTTLE_STOPS]
  );

  // Add a ref to track the last toggle time to prevent rapid toggles
  const lastToggleTimeRef = useRef<number>(0);
  const toggleCallCountRef = useRef<number>(0);

  // Create a single transport toggle for K/Space and the play button
  const toggleTransport = useCallback(() => {
    const now = Date.now();
    const timeSinceLastToggle = now - lastToggleTimeRef.current;
    const callCount = ++toggleCallCountRef.current;

    console.log(
      `TOGGLE TRANSPORT CALLED #${callCount} - Time since last: ${timeSinceLastToggle}ms`
    );
    console.log(`Call stack:`, new Error().stack?.split("\n").slice(1, 4).join("\n"));

    // Prevent rapid toggles within 150ms
    if (timeSinceLastToggle < 150) {
      console.log(`Ignoring rapid toggle #${callCount}, time since last: ${timeSinceLastToggle}ms`);
      return;
    }

    lastToggleTimeRef.current = now;

    // Check if we're in shuttle mode first
    if (isShuttlingReverseRef.current) {
      console.log(`Stopping shuttle mode (call #${callCount})`);
      applyShuttleSpeed(0);
      return;
    }

    // Check the actual video element state to avoid React state synchronization issues
    const videoElement = omakaseRef?.current?.video?.htmlVideoElement;
    const actuallyPlaying = videoElement ? !videoElement.paused : isPlaying;

    console.log(` TOGGLE STATE CHECK #${callCount}:`);
    console.log(`  - isPlaying prop: ${isPlaying}`);
    console.log(`  - isPlayingRef: ${isPlayingRef.current}`);
    console.log(`  - video.paused: ${videoElement?.paused}`);
    console.log(`  - actuallyPlaying: ${actuallyPlaying}`);
    console.log(`  - timeSinceLastToggle: ${timeSinceLastToggle}ms`);

    if (actuallyPlaying) {
      console.log(`PAUSING video (call #${callCount})`);
      pause();

      // Prevent focus-related issues by removing focus from video element
      const preventFocusIssues = () => {
        console.log(`PREVENTING focus-related keyboard conflicts`);
        const omakasePlayer = omakaseRef?.current;
        const htmlVideoElement = omakasePlayer?.video?.htmlVideoElement;

        if (htmlVideoElement) {
          // Remove focus from video element to prevent native browser controls
          htmlVideoElement.blur();
          // Disable tabindex to prevent future focus
          htmlVideoElement.setAttribute("tabindex", "-1");
          console.log(`REMOVED focus from video element`);
        }
      };
      preventFocusIssues();
    } else {
      console.log(`PLAYING video (call #${callCount})`);
      play();
    }
  }, [play, pause, applyShuttleSpeed, isPlaying]);

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
    [SHUTTLE_STOPS, applyShuttleSpeed, clearReverseTimer, setPlaybackRate]
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
    [stopTransport, omakaseRef]
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

  // Marker navigation functions
  const navigateToNextMarker = useCallback(() => {
    if (!markerLaneRef.current) {
      console.warn("Marker lane is not available yet. Video may still be loading.");
      return;
    }

    try {
      const markers = markerLaneRef.current.getMarkers();
      if (!markers || markers.length === 0) {
        console.log("No markers available to navigate to.");
        return;
      }

      // Sort markers by their start time (chronological order)
      const sortedMarkers = [...markers].sort((a, b) => {
        const aStart = a.timeObservation?.start || 0;
        const bStart = b.timeObservation?.start || 0;
        return aStart - bStart;
      });

      const currentMarkerInFocus = markerLaneRef.current.getMarkerInFocus();
      let nextMarkerIndex = 0;

      if (currentMarkerInFocus) {
        // Find current marker index in sorted array and move to next
        const currentIndex = sortedMarkers.findIndex(
          (marker) => marker.id === currentMarkerInFocus.id
        );
        nextMarkerIndex = (currentIndex + 1) % sortedMarkers.length;
      }

      const nextMarker = sortedMarkers[nextMarkerIndex];
      if (nextMarker) {
        markerLaneRef.current.focusMarker(nextMarker.id);
        // Seek to the start of the marker
        const timeObservation = nextMarker.timeObservation;
        if (timeObservation && timeObservation.start !== undefined) {
          seek(timeObservation.start);
        }
        console.log("Navigated to next marker:", nextMarker.id, "at time:", timeObservation?.start);
      }
    } catch (error) {
      console.error("Error navigating to next marker:", error);
    }
  }, [markerLaneRef, seek]);

  const navigateToPreviousMarker = useCallback(() => {
    if (!markerLaneRef.current) {
      console.warn("Marker lane is not available yet. Video may still be loading.");
      return;
    }

    try {
      const markers = markerLaneRef.current.getMarkers();
      if (!markers || markers.length === 0) {
        console.log("No markers available to navigate to.");
        return;
      }

      // Sort markers by their start time (chronological order)
      const sortedMarkers = [...markers].sort((a, b) => {
        const aStart = a.timeObservation?.start || 0;
        const bStart = b.timeObservation?.start || 0;
        return aStart - bStart;
      });

      const currentMarkerInFocus = markerLaneRef.current.getMarkerInFocus();
      let prevMarkerIndex = sortedMarkers.length - 1;

      if (currentMarkerInFocus) {
        // Find current marker index in sorted array and move to previous
        const currentIndex = sortedMarkers.findIndex(
          (marker) => marker.id === currentMarkerInFocus.id
        );
        prevMarkerIndex = currentIndex > 0 ? currentIndex - 1 : sortedMarkers.length - 1;
      }

      const prevMarker = sortedMarkers[prevMarkerIndex];
      if (prevMarker) {
        markerLaneRef.current.focusMarker(prevMarker.id);
        // Seek to the start of the marker
        const timeObservation = prevMarker.timeObservation;
        if (timeObservation && timeObservation.start !== undefined) {
          seek(timeObservation.start);
        }
        console.log(
          "Navigated to previous marker:",
          prevMarker.id,
          "at time:",
          timeObservation?.start
        );
      }
    } catch (error) {
      console.error("Error navigating to previous marker:", error);
    }
  }, [markerLaneRef, seek]);

  // Keyboard event handler with capture-phase blocking
  useEffect(() => {
    const handledKeys = new Set([" ", "k", "K"]); // Space + K keys that we handle

    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore when typing in fields
      const tag = (event.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      // If we handle this key, stop anyone else from seeing it
      if (handledKeys.has(event.key)) {
        (event as any).stopImmediatePropagation?.();
        event.stopPropagation();
        event.preventDefault();
      }

      // Double-tap detection
      const now = performance.now();
      const isDoubleTap =
        event.key === lastKeyRef.current && now - lastKeyTimeRef.current < DOUBLE_TAP_MS;
      lastKeyRef.current = event.key;
      lastKeyTimeRef.current = now;

      switch (event.key) {
        case " ": // Space or K toggles transport / double-tap resets to 1x
        case "k":
        case "K":
          if (isDoubleTap) {
            resetSpeed(true); // play at 1× forward
          } else {
            // Call immediately - no delay needed since we blocked other handlers
            toggleTransport();
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
            console.warn("Marker lane is not available yet. Video may still be loading.");
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
        case "n": // next marker
        case "N":
          event.preventDefault();
          navigateToNextMarker();
          break;
        case "p": // previous marker
        case "P":
          event.preventDefault();
          navigateToPreviousMarker();
          break;
      }
    };

    // Block native/key-up fallbacks some players use
    const blockNative = (e: KeyboardEvent) => {
      if (handledKeys.has(e.key)) {
        (e as any).stopImmediatePropagation?.();
        e.stopPropagation();
        e.preventDefault();
      }
    };

    // Capture-phase listener at the top of the tree to intercept before any other handlers
    window.addEventListener("keydown", handleKeyDown, { capture: true });
    window.addEventListener("keyup", blockNative, { capture: true });
    window.addEventListener("keypress", blockNative, { capture: true });

    return () => {
      window.removeEventListener("keydown", handleKeyDown, {
        capture: true,
      } as any);
      window.removeEventListener("keyup", blockNative, {
        capture: true,
      } as any);
      window.removeEventListener("keypress", blockNative, {
        capture: true,
      } as any);
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
    navigateToNextMarker,
    navigateToPreviousMarker,
  ]);

  // Prevent video element from holding focus after mouse clicks (belt & suspenders)
  useEffect(() => {
    const omakasePlayer = omakaseRef?.current;
    const htmlVideoElement = omakasePlayer?.video?.htmlVideoElement;

    if (!htmlVideoElement) return;

    const blurAfterPointer = () => {
      setTimeout(() => {
        htmlVideoElement.blur();
        console.log("🎯 BLURRED video element after pointer interaction");
      }, 0);
    };

    // Prevent video from being focusable and blur after any pointer interaction
    htmlVideoElement.setAttribute("tabindex", "-1");
    htmlVideoElement.addEventListener("pointerdown", blurAfterPointer);
    htmlVideoElement.addEventListener("click", blurAfterPointer);

    console.log("✅ VIDEO ELEMENT configured to prevent focus after mouse interactions");

    return () => {
      htmlVideoElement.removeEventListener("pointerdown", blurAfterPointer);
      htmlVideoElement.removeEventListener("click", blurAfterPointer);
    };
  }, [omakaseRef]);

  // Keyboard shortcuts for help display with actions
  const SHORTCUTS = [
    {
      keys: ["Space", "K"],
      description: "Play/Pause",
      category: "Playback",
      action: toggleTransport,
    },
    {
      keys: ["J"],
      description: "Shuttle slower/reverse",
      category: "Playback",
      action: () => bumpShuttle(-1),
    },
    {
      keys: ["L"],
      description: "Shuttle faster/forward",
      category: "Playback",
      action: () => bumpShuttle(1),
    },
    {
      keys: ["←"],
      description: "Step 5s backward",
      category: "Navigation",
      action: () => seek(Math.max(currentTime - 5, 0)),
    },
    {
      keys: ["→"],
      description: "Step 5s forward",
      category: "Navigation",
      action: () => seek(Math.min(currentTime + 5, duration)),
    },
    {
      keys: [","],
      description: "Frame backward",
      category: "Navigation",
      action: () => stepFrame(-1),
    },
    {
      keys: ["."],
      description: "Frame forward",
      category: "Navigation",
      action: () => stepFrame(1),
    },
    {
      keys: ["N"],
      description: "Next marker",
      category: "Markers",
      action: navigateToNextMarker,
    },
    {
      keys: ["P"],
      description: "Previous marker",
      category: "Markers",
      action: navigateToPreviousMarker,
    },
    {
      keys: ["I"],
      description: "Add marker",
      category: "Markers",
      action: () => {
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
        }
      },
    },
    {
      keys: ["↑"],
      description: "Volume up",
      category: "Audio",
      action: () => {
        const newVol = Math.min(volume + 10, 100);
        setPlayerVolume(newVol);
        setVolumeState(newVol);
        if (newVol > 0) {
          lastNonZeroVolumeRef.current = newVol;
          if (muted) {
            unmute();
            setMuted(false);
          }
        }
      },
    },
    {
      keys: ["↓"],
      description: "Volume down",
      category: "Audio",
      action: () => {
        const newVol = Math.max(volume - 10, 0);
        setPlayerVolume(newVol);
        setVolumeState(newVol);
        setMuted(newVol === 0);
      },
    },
    {
      keys: ["M"],
      description: "Mute/Unmute",
      category: "Audio",
      action: handleMuteToggle,
    },
    {
      keys: ["F"],
      description: "Toggle fullscreen",
      category: "Display",
      action: handleFullscreenToggle,
    },
  ];

  return {
    SHORTCUTS,
    toggleTransport,
    currentPlaybackRate,
    isShuttlingReverse,
  };
};
