import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { OmakasePlayer, PlayerChromingTheme } from "@byomakase/omakase-player";
import type { OmakaseThemeConfig, AudioThemeConfig } from "@byomakase/omakase-player";
import { MarkerSyncCoordinator } from "./marker-sync/MarkerSyncCoordinator";
import type { DetailMarkerAdapter, MarkerApi } from "./marker-sync/ports";
import { playerTimeStore } from "./playerTimeStore";
import type { PlayerThemeResult } from "./createOmakaseThemeConfig";

export interface UseDetailPlayerOptions {
  containerId: string;
  src: string;
  mediaType: "video" | "audio";
  assetId: string;
  themeResult: PlayerThemeResult;
  onTimeUpdate?: (time: number) => void;
}

export interface UseDetailPlayerResult {
  playerRef: React.MutableRefObject<OmakasePlayer | null>;
  markerTrackRef: React.MutableRefObject<unknown | null>;
  markerAdapter: DetailMarkerAdapter;
  isMarkerReady: boolean;
  duration: number;
  isPlaying: boolean;
  volume: number;
  muted: boolean;
  seek: (time: number) => void;
  play: () => void;
  pause: () => void;
  setVolume: (volume: number) => void;
  mute: () => void;
  unmute: () => void;
  setPlaybackRate: (rate: number) => void;
  toggleFullscreen: () => void;
}

export function useDetailPlayer(options: UseDetailPlayerOptions): UseDetailPlayerResult {
  const { containerId, src, mediaType, assetId, themeResult, onTimeUpdate } = options;

  const playerRef = useRef<OmakasePlayer | null>(null);
  const markerTrackRef = useRef<unknown | null>(null);
  const isMountedRef = useRef(false);
  const abortedRef = useRef(false);
  const subscriptionsRef = useRef<{ unsubscribe(): void }[]>([]);
  const coordinatorRef = useRef<MarkerSyncCoordinator | null>(null);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const themeResultRef = useRef(themeResult);

  const [isMarkerReady, setIsMarkerReady] = useState(false);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolumeState] = useState(100);
  const [muted, setMutedState] = useState(false);

  // Keep refs in sync without triggering effect re-runs
  onTimeUpdateRef.current = onTimeUpdate;
  themeResultRef.current = themeResult;

  useEffect(() => {
    if (!containerId || !src) return;

    isMountedRef.current = true;
    abortedRef.current = false;

    // Instantiate MarkerSyncCoordinator
    const coordinator = new MarkerSyncCoordinator({
      clock: { now: () => Date.now() },
      idGenerator: { next: () => crypto.randomUUID() },
      storage: {
        load: (id: string) => {
          try {
            return JSON.parse(localStorage.getItem("markers:" + id) ?? "[]");
          } catch {
            console.warn("Failed to load markers from localStorage");
            return [];
          }
        },
        save: (id: string, envelopes) => {
          try {
            localStorage.setItem("markers:" + id, JSON.stringify(envelopes));
          } catch (err) {
            console.warn("Failed to save markers to localStorage:", err);
          }
        },
      },
      assetId,
    });
    coordinatorRef.current = coordinator;

    // Create player with the appropriate chroming theme
    const tr = themeResultRef.current;
    const playerChroming =
      tr.mediaType === "audio"
        ? { theme: PlayerChromingTheme.Audio as const, themeConfig: tr.themeConfig }
        : { theme: PlayerChromingTheme.Omakase as const, themeConfig: tr.themeConfig };

    const player = new OmakasePlayer({
      playerHTMLElementId: containerId,
      playerChroming,
      // Disable manifest subtitle track fetching — the VTT segmentation code
      // crashes on certain streams where segment duration is non-numeric.
      // The detail page uses its own TranscriptionTab for transcript display.
      hlsConfig: {
        fetchManifestSubtitleTracks: false,
      },
    });
    playerRef.current = player;

    // Load video
    const loadSub = player
      .loadVideo(src, mediaType === "audio" ? { protocol: "audio" as const } : { frameRate: 25 })
      .subscribe({
        next: (video) => {
          if (abortedRef.current) return;
          setDuration(video.duration);
          playerTimeStore.getState().setDuration(video.duration);
          markerTrackRef.current = player.chroming?.progressMarkerTrack ?? null;
          coordinator.setReady(true);
          setIsMarkerReady(true);
        },
        error: (err) => {
          console.error("Error loading video:", err);
        },
      });
    subscriptionsRef.current.push(loadSub);

    // Subscribe to time updates — writes to Zustand store (no React re-render)
    const timeSub = player.video.onVideoTimeChange$.subscribe({
      next: (event) => {
        if (abortedRef.current) return;
        playerTimeStore.getState().setCurrentTime(event.currentTime);
        onTimeUpdateRef.current?.(event.currentTime);
      },
    });
    subscriptionsRef.current.push(timeSub);

    // Subscribe to play/pause state
    const playSub = player.video.onPlay$.subscribe({
      next: () => {
        if (!abortedRef.current) setIsPlaying(true);
      },
    });
    subscriptionsRef.current.push(playSub);

    const pauseSub = player.video.onPause$.subscribe({
      next: () => {
        if (!abortedRef.current) setIsPlaying(false);
      },
    });
    subscriptionsRef.current.push(pauseSub);

    // Subscribe to volume changes
    const volumeSub = player.video.onVolumeChange$.subscribe({
      next: (event) => {
        if (abortedRef.current) return;
        setVolumeState(Math.round(event.volume * 100));
        setMutedState(event.muted);
      },
    });
    subscriptionsRef.current.push(volumeSub);

    // Cleanup
    return () => {
      abortedRef.current = true;
      subscriptionsRef.current.forEach((s) => {
        try {
          s.unsubscribe();
        } catch {
          /* ok */
        }
      });
      subscriptionsRef.current = [];
      coordinator.setReady(false);
      try {
        player.destroy();
      } catch {
        /* ok */
      }
      playerRef.current = null;
      markerTrackRef.current = null;
      setIsMarkerReady(false);
    };
  }, [containerId, src, mediaType, assetId]);

  // Build stable markerAdapter
  const markerAdapter: DetailMarkerAdapter = useMemo(
    () => ({
      list: () => coordinatorRef.current?.list() ?? [],
      add: (marker: Partial<MarkerApi>, source: "track" | "sidebar") =>
        coordinatorRef.current?.add(marker, source),
      update: (id, patch, source, expectedRevision?) =>
        coordinatorRef.current?.update(id, patch, source, expectedRevision),
      remove: (id, source, expectedRevision?) =>
        coordinatorRef.current?.remove(id, source, expectedRevision),
      clear: (source) => coordinatorRef.current?.clear(source),
      select: (id) => coordinatorRef.current?.select(id),
      selected: () => coordinatorRef.current?.selected(),
      preview: (id, patch, source) => coordinatorRef.current?.preview(id, patch, source),
      commit: (id, source) => coordinatorRef.current?.commit(id, source),
      rollback: (opId) => coordinatorRef.current?.rollback(opId),
      isReady: () => coordinatorRef.current?.isReady() ?? false,
      on: (event, handler) => coordinatorRef.current?.on(event, handler),
      off: (event, handler) => coordinatorRef.current?.off(event, handler),
    }),
    []
  );

  // Control callbacks
  const seek = useCallback((time: number) => {
    playerRef.current?.video.seekToTime(time);
  }, []);
  const play = useCallback(() => {
    playerRef.current?.video.play();
  }, []);
  const pause = useCallback(() => {
    playerRef.current?.video.pause();
  }, []);
  const setVolume = useCallback((volume: number) => {
    playerRef.current?.video.setVolume(volume / 100);
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

  return {
    playerRef,
    markerTrackRef,
    markerAdapter,
    isMarkerReady,
    duration,
    isPlaying,
    volume,
    muted,
    seek,
    play,
    pause,
    setVolume,
    mute,
    unmute,
    setPlaybackRate,
    toggleFullscreen,
  };
}
