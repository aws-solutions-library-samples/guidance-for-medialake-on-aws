/**
 * useDetailPlayer — owns the asset detail page's Omakase player instance.
 *
 * ## What changed with 1.1.1
 *
 * The player surface was reorganised, so this is a rewrite rather than a port:
 *
 *   - Config keys are flat and prefixed: `playerHtmlElementId`, `chromingTheme`,
 *     `chromingThemeConfig`. The 0.25.x nested `playerChroming: {theme,
 *     themeConfig}` is gone. It is worth stating plainly that passing the old
 *     shape is *silently* ignored rather than rejected, so a mechanical port that
 *     kept it would have produced a player with default chroming and no error.
 *   - `player.video.*` became `player.player.*`; `loadVideo` became
 *     `loadMainMedia`; volume and mute moved to `player.player.audio`.
 *   - The per-concern observables (`onVideoTimeChange$`, `onPlay$`, `onPause$`,
 *     `onVolumeChange$`) collapsed into one `player.onEvent$` carrying a
 *     discriminated `PlayerEventType`. One subscription now replaces five.
 *   - Markers are no longer a chroming side-effect: they live on `MarkerTrack`s in
 *     the track repository. Track ownership lives in `useMarkerTracks`, which this
 *     hook composes and re-exposes.
 *
 * Frame rate is now taken from the asset's embedded metadata instead of being
 * hardcoded to 25. `MainMediaLoadOptions.frameRate` accepts `number | string`
 * including an ffprobe rational (`"30000/1001"`), which is the form our metadata
 * carries — so frame stepping and SMPTE display finally agree with the media.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChromingTheme,
  MainMediaType,
  MediaTemporalFormat,
  OmakasePlayer,
  PlayerAudioType,
  PlayerEventType,
  type MainMediaLoadOptions,
} from "@byomakase/omakase-player";
import { playerTimeStore } from "./playerTimeStore";
import type { PlayerThemeResult } from "./createOmakaseThemeConfig";
import { useMarkerTracks, type UseMarkerTracksResult } from "./useMarkerTracks";

export interface UseDetailPlayerOptions {
  containerId: string;
  src: string;
  mediaType: "video" | "audio";
  assetId: string;
  themeResult: PlayerThemeResult;
  /**
   * The media's frame rate. A number, or an ffprobe rational string such as
   * `"30000/1001"`. Omitted when unknown — Omakase then derives what it can from
   * the stream rather than being told a wrong value.
   */
  frameRate?: number | string;
  onTimeUpdate?: (time: number) => void;
}

export interface UseDetailPlayerResult extends UseMarkerTracksResult {
  playerRef: React.MutableRefObject<OmakasePlayer | null>;
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
  const { containerId, src, mediaType, assetId, themeResult, frameRate, onTimeUpdate } = options;

  const playerRef = useRef<OmakasePlayer | null>(null);
  const abortedRef = useRef(false);
  const subscriptionsRef = useRef<{ unsubscribe(): void }[]>([]);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  const themeResultRef = useRef(themeResult);
  const frameRateRef = useRef(frameRate);

  // `player` is state, not just a ref: useMarkerTracks must re-run when the
  // instance changes, and a ref mutation would not trigger that.
  const [player, setPlayer] = useState<OmakasePlayer | null>(null);
  const [isMediaLoaded, setIsMediaLoaded] = useState(false);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolumeState] = useState(100);
  const [muted, setMutedState] = useState(false);

  // Kept in refs so changing a callback or the theme does not tear down the player.
  onTimeUpdateRef.current = onTimeUpdate;
  themeResultRef.current = themeResult;
  frameRateRef.current = frameRate;

  useEffect(() => {
    if (!containerId || !src) return;

    abortedRef.current = false;

    const theme = themeResultRef.current;
    // `chromingTheme` and `chromingThemeConfig` are correlated: PlayerChromingConfig
    // is a union keyed on the theme, so the pair has to be constructed inside one
    // branch. Passing `ChromingTheme.DEFAULT | AUDIO` alongside a union of configs
    // does not type-check, which is the compiler catching a real hazard — an AUDIO
    // config under the DEFAULT theme would be accepted structurally and then
    // misconfigure the control bar.
    const instance =
      theme.mediaType === "audio"
        ? new OmakasePlayer({
            playerHtmlElementId: containerId,
            chromingTheme: ChromingTheme.AUDIO,
            chromingThemeConfig: theme.themeConfig,
          })
        : new OmakasePlayer({
            playerHtmlElementId: containerId,
            chromingTheme: ChromingTheme.DEFAULT,
            chromingThemeConfig: theme.themeConfig,
          });

    playerRef.current = instance;
    setPlayer(instance);

    const loadOptions: MainMediaLoadOptions =
      mediaType === "audio"
        ? { mainMediaType: MainMediaType.AUDIO_FILE }
        : frameRateRef.current !== undefined
          ? { frameRate: frameRateRef.current }
          : {};

    const loadSubscription = instance.loadMainMedia(src, loadOptions).subscribe({
      next: (mainMedia) => {
        if (abortedRef.current) return;
        const mediaDuration = mainMedia.state.duration ?? 0;
        setDuration(mediaDuration);
        playerTimeStore.getState().setDuration(mediaDuration);
        setIsMediaLoaded(true);
      },
      error: (error) => {
        console.error("Error loading main media:", error);
      },
    });
    subscriptionsRef.current.push(loadSubscription);

    // One subscription for every player event. Time updates go to the Zustand
    // store rather than React state — they fire per frame, and re-rendering the
    // detail page at that rate is what the store exists to avoid.
    const eventSubscription = instance.player.onEvent$.subscribe({
      next: (event) => {
        if (abortedRef.current) return;

        switch (event.type) {
          case PlayerEventType.PLAYER_PLAYBACK_PROGRESS: {
            const currentTime = instance.player.getCurrentTime(MediaTemporalFormat.SECONDS);
            playerTimeStore.getState().setCurrentTime(currentTime);
            onTimeUpdateRef.current?.(currentTime);
            break;
          }
          case PlayerEventType.PLAYER_SEEKED: {
            const currentTime = instance.player.getCurrentTime(MediaTemporalFormat.SECONDS);
            playerTimeStore.getState().setCurrentTime(currentTime);
            onTimeUpdateRef.current?.(currentTime);
            break;
          }
          case PlayerEventType.PLAYER_PLAY:
            setIsPlaying(true);
            break;
          case PlayerEventType.PLAYER_PAUSE:
          case PlayerEventType.PLAYER_ENDED:
            setIsPlaying(false);
            break;
          case PlayerEventType.PLAYER_AUDIO_CHANGE: {
            // Read volume/muted from the event payload, not from
            // `player.audio.volume` / `.muted`. Those getters go through
            // `getOutputHandlerOrFail()`, which *throws* `Error("Audio not set
            // up")` until the OUTPUT audio handler exists — and this event fires
            // before it does, so touching the getters here surfaced an uncaught
            // error on every asset detail load.
            const output = event.data.playerAudio.handlers[PlayerAudioType.OUTPUT];
            if (output) {
              setVolumeState(Math.round(output.volume * 100));
              setMutedState(output.muted);
            }
            break;
          }
          default:
            break;
        }
      },
    });
    subscriptionsRef.current.push(eventSubscription);

    return () => {
      abortedRef.current = true;
      subscriptionsRef.current.forEach((subscription) => {
        try {
          subscription.unsubscribe();
        } catch {
          /* ok */
        }
      });
      subscriptionsRef.current = [];

      try {
        instance.destroy();
      } catch {
        /* ok */
      }

      playerRef.current = null;
      setPlayer(null);
      setIsMediaLoaded(false);
    };
  }, [containerId, src, mediaType, assetId]);

  const markerTracks = useMarkerTracks({ player, assetId, isMediaLoaded });

  // Every control subscribes. Omakase returns cold Observables, so an unsubscribed
  // call never executes — the previous `seek()` did exactly that and silently did
  // nothing when invoked from the sidebar or a keyboard shortcut.
  const seek = useCallback((time: number) => {
    playerRef.current?.player.seekTo(time, MediaTemporalFormat.SECONDS).subscribe({
      error: () => undefined,
    });
  }, []);
  const play = useCallback(() => {
    playerRef.current?.player.play().subscribe({ error: () => undefined });
  }, []);
  const pause = useCallback(() => {
    playerRef.current?.player.pause().subscribe({ error: () => undefined });
  }, []);
  // Audio calls go through `getOutputHandlerOrFail()`, which throws
  // synchronously until the OUTPUT handler is established. Guard rather than let
  // a volume keypress take down the page.
  const withAudio = useCallback((action: (audio: OmakasePlayer["player"]["audio"]) => void) => {
    const audio = playerRef.current?.player.audio;
    if (!audio) return;
    try {
      action(audio);
    } catch {
      // Audio not set up yet.
    }
  }, []);

  const setVolume = useCallback(
    (next: number) => {
      withAudio((audio) => audio.setVolume(next / 100).subscribe({ error: () => undefined }));
    },
    [withAudio]
  );
  const mute = useCallback(() => {
    withAudio((audio) => audio.mute().subscribe({ error: () => undefined }));
  }, [withAudio]);
  const unmute = useCallback(() => {
    withAudio((audio) => audio.unmute().subscribe({ error: () => undefined }));
  }, [withAudio]);
  const setPlaybackRate = useCallback((rate: number) => {
    playerRef.current?.player.setPlaybackRate(rate).subscribe({ error: () => undefined });
  }, []);
  const toggleFullscreen = useCallback(() => {
    playerRef.current?.player.toggleFullScreen().subscribe({ error: () => undefined });
  }, []);

  return useMemo(
    () => ({
      ...markerTracks,
      playerRef,
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
    }),
    [
      markerTracks,
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
    ]
  );
}
