import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  MediaTemporalFormat,
  PlayerEventType,
  type MarkerTrack,
  type OmakasePlayer,
} from "@byomakase/omakase-player";
import { randomHexColor } from "../common/utils";
import { getPlayerCurrentTime, getPlayerDuration } from "./playerTimeStore";
import { readTrackMarkers, type CreateMarkerInput, type DetailMarker } from "./markerTracks";

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
  /** Creates a marker at the playhead (the `I` shortcut). */
  addUserMarker: (input: Omit<CreateMarkerInput, "kind">) => DetailMarker | undefined;
  userTrackRef: React.MutableRefObject<MarkerTrack | null>;
  semanticTrackRef: React.MutableRefObject<MarkerTrack | null>;
  isMarkersReady: boolean;
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
  addUserMarker,
  userTrackRef,
  semanticTrackRef,
  isMarkersReady,
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
    const htmlVideoElement = omakaseRef?.current?.player.htmlMediaElement;
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

  // Pick up the real frame rate once media is loaded.
  //
  // `getFrameRate()` is gone; the rate now lives on the loaded media's
  // `frameRateModel`, and load completion arrives on the joint event stream
  // rather than a dedicated `onVideoLoaded$`.
  useEffect(() => {
    const p = omakaseRef.current?.player;
    if (!p) return;
    const sub = p.onEvent$.subscribe((event) => {
      if (event.type === PlayerEventType.PLAYER_MAIN_MEDIA_LOADED) {
        const rate = event.data.mainMediaState.frameRateModel?.value;
        if (typeof rate === "number" && Number.isFinite(rate) && rate > 0) {
          fpsRef.current = rate;
        }
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
            omakaseRef.current?.player
              .seekFromCurrentTime(-framesPerTick, MediaTemporalFormat.FRAME_COUNT)
              .subscribe({ error: () => undefined });
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

    const videoElement = omakaseRef?.current?.player.htmlMediaElement;
    const actuallyPlaying = videoElement ? !videoElement.paused : isPlaying;

    if (actuallyPlaying) {
      pause();
      const htmlVideoElement = omakaseRef?.current?.player.htmlMediaElement;
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
      omakaseRef.current?.player
        .seekFromCurrentTime(dir, MediaTemporalFormat.FRAME_COUNT)
        .subscribe({ error: () => undefined });
    },
    [stopTransport, omakaseRef]
  );

  // Keep UI rate in sync when forward rate changes
  useEffect(() => {
    const p = omakaseRef.current?.player;
    if (!p) return;
    const sub = p.onEvent$.subscribe((event) => {
      if (event.type === PlayerEventType.PLAYER_PLAYBACK_RATE_UPDATE) {
        if (reverseTimerRef.current === null) {
          setCurrentPlaybackRate(event.data.playbackRate);
        }
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

  // Marker navigation.
  //
  // Stepping is relative to the playhead rather than to a "selected marker"
  // cursor. The old version tracked selection in the coordinator and advanced an
  // index, which drifted from what the user saw whenever they scrubbed: after
  // seeking elsewhere, `N` jumped to the marker after the last *clicked* one
  // rather than the next one ahead. Reading the playhead makes the shortcut mean
  // what it looks like it means, and needs no selection state at all.
  //
  // Both tracks participate, so `N`/`P` walk user markers and clip matches
  // together in time order.
  const collectMarkers = useCallback((): DetailMarker[] => {
    const markers = [
      ...readTrackMarkers(userTrackRef.current ?? undefined),
      ...readTrackMarkers(semanticTrackRef.current ?? undefined),
    ];
    return markers.sort((a, b) => a.startTime - b.startTime);
  }, [userTrackRef, semanticTrackRef]);

  const navigateToNextMarker = useCallback(() => {
    if (!isMarkersReady) return;

    const markers = collectMarkers();
    if (markers.length === 0) return;

    // Small epsilon so repeated presses advance instead of re-selecting the
    // marker we just seeked to.
    const now = getPlayerCurrentTime() + 0.01;
    const next = markers.find((marker) => marker.startTime > now) ?? markers[0];
    seek(next.startTime);
  }, [collectMarkers, isMarkersReady, seek]);

  const navigateToPreviousMarker = useCallback(() => {
    if (!isMarkersReady) return;

    const markers = collectMarkers();
    if (markers.length === 0) return;

    const now = getPlayerCurrentTime() - 0.01;
    const previous =
      [...markers].reverse().find((marker) => marker.startTime < now) ??
      markers[markers.length - 1];
    seek(previous.startTime);
  }, [collectMarkers, isMarkersReady, seek]);

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
          if (isMarkersReady) {
            const t = getPlayerCurrentTime();
            addUserMarker({
              startTime: t,
              endTime: t + 2,
              color: randomHexColor(),
            });
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
    addUserMarker,
    isMarkersReady,
    navigateToNextMarker,
    navigateToPreviousMarker,
  ]);

  // Prevent video element from holding focus after mouse clicks
  useEffect(() => {
    const htmlVideoElement = omakaseRef?.current?.player.htmlMediaElement;
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
        if (isMarkersReady) {
          const t = getPlayerCurrentTime();
          addUserMarker({
            startTime: t,
            endTime: t + 2,
            color: randomHexColor(),
          });
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
