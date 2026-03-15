import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { OmakasePlayer } from "@byomakase/omakase-player";
import type { DetailMarkerAdapter, MarkerApi } from "./marker-sync/ports";
import { randomHexColor } from "../common/utils";
import { getPlayerCurrentTime, getPlayerDuration } from "./playerTimeStore";

export interface UsePlayerKeyboardShortcutsCoreProps {
  play: () => void;
  pause: () => void;
  seek: (time: number) => void;
  setPlaybackRate: (rate: number) => void;
  toggleFullscreen: () => void;
  isPlaying: boolean;
  volume: number;
  muted: boolean;
  setPlayerVolume: (volume: number) => void;
  mute: () => void;
  unmute: () => void;
  markerAdapter: DetailMarkerAdapter;
  omakaseRef: React.MutableRefObject<OmakasePlayer | null>;
}

export const usePlayerKeyboardShortcutsCore = ({
  play: originalPlay,
  pause: originalPause,
  seek,
  setPlaybackRate,
  toggleFullscreen,
  isPlaying,
  volume,
  muted,
  setPlayerVolume,
  mute,
  unmute,
  markerAdapter,
  omakaseRef,
}: UsePlayerKeyboardShortcutsCoreProps) => {
  // Store high-frequency values in refs so the keydown effect doesn't
  // re-register on every change.
  const volumeRef = useRef(volume);
  volumeRef.current = volume;
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const SHUTTLE_STOPS = useMemo(
    () => [-16, -8, -4, -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2, 4, 8, 16] as const,
    []
  );
  const [, setShuttleIdx] = useState(SHUTTLE_STOPS.indexOf(1 as (typeof SHUTTLE_STOPS)[number]));
  const [currentPlaybackRate, setCurrentPlaybackRate] = useState(1);
  const reverseTimerRef = useRef<number | null>(null);
  const fpsRef = useRef<number>(25);
  const [isShuttlingReverse, setIsShuttlingReverse] = useState(false);
  const lastNonZeroShuttleRef = useRef<number>(1);
  const lastNonZeroVolumeRef = useRef<number>(100);

  const play = useCallback(() => {
    originalPlay();
  }, [originalPlay]);

  const pause = useCallback(() => {
    originalPause();
  }, [originalPause]);

  const isPlayingRef = useRef(isPlaying);
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  const isShuttlingReverseRef = useRef(isShuttlingReverse);
  useEffect(() => {
    isShuttlingReverseRef.current = isShuttlingReverse;
  }, [isShuttlingReverse]);

  const lastKeyRef = useRef<string>("");
  const lastKeyTimeRef = useRef<number>(0);
  const DOUBLE_TAP_MS = 250;

  const lastToggleTimeRef = useRef<number>(0);
  const toggleCallCountRef = useRef<number>(0);

  // Prevent video element from receiving focus
  useEffect(() => {
    const htmlVideoElement = omakaseRef?.current?.video?.getHTMLVideoElement();
    if (htmlVideoElement) {
      htmlVideoElement.setAttribute("tabindex", "-1");
      htmlVideoElement.blur();
    }
  }, [omakaseRef]);

  const clearReverseTimer = useCallback(() => {
    if (reverseTimerRef.current !== null) {
      window.clearInterval(reverseTimerRef.current);
      reverseTimerRef.current = null;
    }
  }, []);

  // Pick up actual frame rate once video is loaded
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
        setPlaybackRate(target);
        play();
      } else {
        setIsShuttlingReverse(true);
        pause();
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

  const toggleTransport = useCallback(() => {
    const now = Date.now();
    const timeSinceLastToggle = now - lastToggleTimeRef.current;
    ++toggleCallCountRef.current;

    if (timeSinceLastToggle < 150) {
      return;
    }

    lastToggleTimeRef.current = now;

    if (isShuttlingReverseRef.current) {
      applyShuttleSpeed(0);
      return;
    }

    const videoElement = omakaseRef?.current?.video?.getHTMLVideoElement();
    const actuallyPlaying = videoElement ? !videoElement.paused : isPlaying;

    if (actuallyPlaying) {
      pause();
      const htmlVideoElement = omakaseRef?.current?.video?.getHTMLVideoElement();
      if (htmlVideoElement) {
        htmlVideoElement.blur();
        htmlVideoElement.setAttribute("tabindex", "-1");
      }
    } else {
      play();
    }
  }, [play, pause, applyShuttleSpeed, isPlaying]);

  const resetSpeed = useCallback(
    (playAfter = true) => {
      const idx1 = SHUTTLE_STOPS.indexOf(1 as any);
      setShuttleIdx(idx1);
      lastNonZeroShuttleRef.current = 1;
      if (playAfter) {
        applyShuttleSpeed(1);
      } else {
        clearReverseTimer();
        setCurrentPlaybackRate(1);
        setPlaybackRate(1);
        setIsShuttlingReverse(false);
      }
    },
    [SHUTTLE_STOPS, applyShuttleSpeed, clearReverseTimer, setPlaybackRate]
  );

  const stopTransport = useCallback(() => {
    applyShuttleSpeed(0);
  }, [applyShuttleSpeed]);

  const stepFrame = useCallback(
    (dir: -1 | 1) => {
      stopTransport();
      omakaseRef.current?.video.seekFromCurrentFrame(dir).subscribe();
    },
    [stopTransport, omakaseRef]
  );

  // Keep UI rate in sync when forward rate changes
  useEffect(() => {
    const v = omakaseRef.current?.video;
    if (!v?.onPlaybackRateChange$) return;
    const sub = v.onPlaybackRateChange$.subscribe(({ playbackRate }) => {
      if (reverseTimerRef.current === null) {
        setCurrentPlaybackRate(playbackRate);
      }
    });
    return () => sub?.unsubscribe();
  }, [omakaseRef]);

  // Clear timer on unmount
  useEffect(() => () => clearReverseTimer(), [clearReverseTimer]);

  const adjustVolume = useCallback(
    (delta: number) => {
      const newVol = Math.min(Math.max(volumeRef.current + delta, 0), 100);
      setPlayerVolume(newVol);
      if (newVol > 0) {
        lastNonZeroVolumeRef.current = newVol;
        unmute();
      } else {
        mute();
      }
    },
    [setPlayerVolume, unmute, mute]
  );

  const handleMuteToggle = useCallback(() => {
    if (mutedRef.current) {
      unmute();
      if (volumeRef.current === 0) {
        setPlayerVolume(lastNonZeroVolumeRef.current || 100);
      }
    } else {
      if (volumeRef.current > 0) lastNonZeroVolumeRef.current = volumeRef.current;
      mute();
    }
  }, [unmute, setPlayerVolume, mute]);

  const handleFullscreenToggle = useCallback(() => {
    toggleFullscreen();
  }, [toggleFullscreen]);

  // Marker navigation
  const navigateToNextMarker = useCallback(() => {
    if (!markerAdapter.isReady()) return;

    const markers = markerAdapter.list();
    if (markers.length === 0) return;

    const sortedMarkers = [...markers].sort(
      (a, b) => (a.timeObservation?.start || 0) - (b.timeObservation?.start || 0)
    );

    const currentMarker = markerAdapter.selected();
    let nextIndex = 0;

    if (currentMarker) {
      const currentIndex = sortedMarkers.findIndex((m) => m.id === currentMarker.id);
      nextIndex = (currentIndex + 1) % sortedMarkers.length;
    }

    const nextMarker = sortedMarkers[nextIndex];
    if (nextMarker) {
      markerAdapter.select(nextMarker.id);
      if (nextMarker.timeObservation?.start !== undefined) {
        seek(nextMarker.timeObservation.start);
      }
    }
  }, [markerAdapter, seek]);

  const navigateToPreviousMarker = useCallback(() => {
    if (!markerAdapter.isReady()) return;

    const markers = markerAdapter.list();
    if (markers.length === 0) return;

    const sortedMarkers = [...markers].sort(
      (a, b) => (a.timeObservation?.start || 0) - (b.timeObservation?.start || 0)
    );

    const currentMarker = markerAdapter.selected();
    let prevIndex = sortedMarkers.length - 1;

    if (currentMarker) {
      const currentIndex = sortedMarkers.findIndex((m) => m.id === currentMarker.id);
      prevIndex = currentIndex > 0 ? currentIndex - 1 : sortedMarkers.length - 1;
    }

    const prevMarker = sortedMarkers[prevIndex];
    if (prevMarker) {
      markerAdapter.select(prevMarker.id);
      if (prevMarker.timeObservation?.start !== undefined) {
        seek(prevMarker.timeObservation.start);
      }
    }
  }, [markerAdapter, seek]);

  // Keyboard event handler with capture-phase blocking
  useEffect(() => {
    const handledKeys = new Set([" ", "k", "K"]);

    const handleKeyDown = (event: KeyboardEvent) => {
      const activeElement = document.activeElement as HTMLElement;
      const target = event.target as HTMLElement;

      if (activeElement) {
        const activeTag = activeElement.tagName;
        if (activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT") return;
        if (activeElement.isContentEditable) return;
        if (activeElement.getAttribute("role") === "listbox") return;
        let element: HTMLElement | null = activeElement;
        while (element) {
          if (
            element.tagName === "INPUT" ||
            element.tagName === "TEXTAREA" ||
            element.tagName === "SELECT"
          )
            return;
          if (
            element.classList.contains("MuiInputBase-input") ||
            element.classList.contains("MuiSelect-select")
          )
            return;
          if (element.getAttribute("role") === "listbox") return;
          element = element.parentElement;
        }
      }

      if (target) {
        const targetTag = target.tagName;
        if (targetTag === "INPUT" || targetTag === "TEXTAREA" || targetTag === "SELECT") return;
        if (target.isContentEditable) return;
        if (target.getAttribute("role") === "listbox") return;
      }

      if (handledKeys.has(event.key)) {
        (event as any).stopImmediatePropagation?.();
        event.stopPropagation();
        event.preventDefault();
      }

      const now = performance.now();
      const isDoubleTap =
        event.key === lastKeyRef.current && now - lastKeyTimeRef.current < DOUBLE_TAP_MS;
      lastKeyRef.current = event.key;
      lastKeyTimeRef.current = now;

      switch (event.key) {
        case " ":
        case "k":
        case "K":
          if (isDoubleTap) {
            resetSpeed(true);
          } else {
            toggleTransport();
          }
          break;
        case "j":
        case "J":
          event.preventDefault();
          bumpShuttle(-1);
          break;
        case "l":
        case "L":
          event.preventDefault();
          bumpShuttle(1);
          break;
        case "ArrowLeft":
          event.preventDefault();
          seek(Math.max(getPlayerCurrentTime() - 5, 0));
          break;
        case "ArrowRight":
          event.preventDefault();
          seek(Math.min(getPlayerCurrentTime() + 5, getPlayerDuration()));
          break;
        case "ArrowUp":
          event.preventDefault();
          adjustVolume(10);
          break;
        case "ArrowDown":
          event.preventDefault();
          adjustVolume(-10);
          break;
        case "m":
        case "M":
          event.preventDefault();
          handleMuteToggle();
          break;
        case "f":
        case "F":
          event.preventDefault();
          handleFullscreenToggle();
          break;
        case "i":
        case "I":
          event.preventDefault();
          if (markerAdapter.isReady()) {
            const t = getPlayerCurrentTime();
            markerAdapter.add(
              {
                timeObservation: { start: t, end: t + 2 },
                color: randomHexColor(),
                type: "user",
              },
              "sidebar"
            );
          }
          break;
        case ",":
          event.preventDefault();
          stepFrame(-1);
          break;
        case ".":
          event.preventDefault();
          stepFrame(1);
          break;
        case "n":
        case "N":
          event.preventDefault();
          navigateToNextMarker();
          break;
        case "p":
        case "P":
          event.preventDefault();
          navigateToPreviousMarker();
          break;
      }
    };

    const blockNative = (e: KeyboardEvent) => {
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        const activeTag = activeElement.tagName;
        if (
          activeTag === "INPUT" ||
          activeTag === "TEXTAREA" ||
          activeTag === "SELECT" ||
          activeElement.isContentEditable
        )
          return;
        if (activeElement.getAttribute("role") === "listbox") return;
        let element: HTMLElement | null = activeElement;
        while (element) {
          if (
            element.tagName === "INPUT" ||
            element.tagName === "TEXTAREA" ||
            element.tagName === "SELECT"
          )
            return;
          if (
            element.classList.contains("MuiInputBase-input") ||
            element.classList.contains("MuiSelect-select")
          )
            return;
          if (element.getAttribute("role") === "listbox") return;
          element = element.parentElement;
        }
      }

      if (handledKeys.has(e.key)) {
        (e as any).stopImmediatePropagation?.();
        e.stopPropagation();
        e.preventDefault();
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    window.addEventListener("keyup", blockNative, { capture: true });
    window.addEventListener("keypress", blockNative, { capture: true });

    return () => {
      window.removeEventListener("keydown", handleKeyDown, { capture: true } as any);
      window.removeEventListener("keyup", blockNative, { capture: true } as any);
      window.removeEventListener("keypress", blockNative, { capture: true } as any);
    };
  }, [
    toggleTransport,
    resetSpeed,
    stepFrame,
    bumpShuttle,
    seek,
    adjustVolume,
    handleMuteToggle,
    handleFullscreenToggle,
    markerAdapter,
    navigateToNextMarker,
    navigateToPreviousMarker,
  ]);

  // Prevent video element from holding focus after mouse clicks
  useEffect(() => {
    const htmlVideoElement = omakaseRef?.current?.video?.getHTMLVideoElement();
    if (!htmlVideoElement) return;

    const blurAfterPointer = () => {
      setTimeout(() => {
        htmlVideoElement.blur();
      }, 0);
    };

    htmlVideoElement.setAttribute("tabindex", "-1");
    htmlVideoElement.addEventListener("pointerdown", blurAfterPointer);
    htmlVideoElement.addEventListener("click", blurAfterPointer);

    return () => {
      htmlVideoElement.removeEventListener("pointerdown", blurAfterPointer);
      htmlVideoElement.removeEventListener("click", blurAfterPointer);
    };
  }, [omakaseRef]);

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
      action: () => seek(Math.max(getPlayerCurrentTime() - 5, 0)),
    },
    {
      keys: ["→"],
      description: "Step 5s forward",
      category: "Navigation",
      action: () => seek(Math.min(getPlayerCurrentTime() + 5, getPlayerDuration())),
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
        if (markerAdapter.isReady()) {
          const t = getPlayerCurrentTime();
          markerAdapter.add(
            {
              timeObservation: { start: t, end: t + 2 },
              color: randomHexColor(),
              type: "user",
            },
            "sidebar"
          );
        }
      },
    },
    {
      keys: ["↑"],
      description: "Volume up",
      category: "Audio",
      action: () => adjustVolume(10),
    },
    {
      keys: ["↓"],
      description: "Volume down",
      category: "Audio",
      action: () => adjustVolume(-10),
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
