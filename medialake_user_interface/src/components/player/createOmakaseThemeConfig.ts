import type { Theme } from "@mui/material/styles";
import type React from "react";
import type { AudioThemeConfig, DefaultThemeConfig } from "@byomakase/omakase-player";
import {
  AudioPlayerSize,
  AudioThemeControl,
  AudioThemeFloatingControl,
  AudioVisualization,
  ChromingTimeFormat,
  ControlBarVisibility,
  DefaultThemeActionIcon,
  DefaultThemeControl,
  DefaultThemeFloatingControl,
} from "@byomakase/omakase-player";

/**
 * Builds the Omakase chroming theme config for the asset detail player.
 *
 * Video uses the DEFAULT theme. It is the theme Omakase ships marker bars for
 * (`<omakase-marker-bars>` lives in its template), which the OMAKASE theme this
 * replaces does not have — the marker bars are the whole reason for the switch.
 * DEFAULT is also the player's own default (`DEFAULT_PLAYER_CHROMING.theme`), so
 * we are configuring the supported path rather than an alternate one.
 *
 * Audio keeps the AUDIO theme, which is purpose-built for audio-only playback.
 *
 * Note on 1.1.1 enum names: every member is SCREAMING_SNAKE_CASE
 * (`ControlBarVisibility.ENABLED`, not `.Enabled`). The project README shows
 * PascalCase throughout — that casing does not exist in the shipped package, and
 * `TimeFormat` is now `ChromingTimeFormat`.
 */
export type PlayerThemeResult =
  | { mediaType: "video"; themeConfig: DefaultThemeConfig; cssVars: React.CSSProperties }
  | { mediaType: "audio"; themeConfig: AudioThemeConfig; cssVars: React.CSSProperties };

/** Playback rates offered in both themes' rate menus. */
const PLAYBACK_RATES = [0.25, 0.5, 1, 1.5, 2, 4];

export function createOmakaseThemeConfig(
  theme: Theme,
  mediaType: "video" | "audio"
): PlayerThemeResult {
  const cssVars = {
    "--omakase-color-primary": theme.palette.primary.main,
    "--omakase-color-accent": theme.palette.secondary.main,
    "--omakase-color-background": theme.palette.background.default,
    "--omakase-color-text": "#ffffff",
    "--media-primary-color": theme.palette.primary.main,
    "--media-control-background": theme.palette.background.paper,
    "--media-text-color": "#ffffff",
    "--media-range-track-progress-color": theme.palette.primary.main,
    "--media-accent-color": theme.palette.secondary.main,
  } as React.CSSProperties;

  if (mediaType === "audio") {
    const themeConfig: AudioThemeConfig = {
      controlBarVisibility: ControlBarVisibility.ENABLED,
      controlBar: [
        AudioThemeControl.PLAY,
        AudioThemeControl.SCRUBBER,
        AudioThemeControl.VOLUME,
        AudioThemeControl.TIME,
        AudioThemeControl.PLAYBACK_RATE,
        AudioThemeControl.TRACK_SELECTOR,
      ],
      floatingControls: [AudioThemeFloatingControl.HELP_MENU],
      // Required in 1.1.1 — AudioThemeConfig is no longer partial.
      alwaysOnFloatingControls: [],
      playbackRates: PLAYBACK_RATES,
      playerSize: AudioPlayerSize.FULL,
      visualization: AudioVisualization.ENABLED,
      visualizationConfig: {
        strokeColor: theme.palette.primary.main,
        fillColors: [theme.palette.primary.light, theme.palette.primary.dark],
      },
      timeFormat: ChromingTimeFormat.TIMECODE,
      // Double-click-to-seek on the time display stays off: the detail page has
      // its own editable timecodes in the markers panel, and enabling both gives
      // two competing edit affordances for the same value.
      timeInteractive: false,
    };
    return { mediaType: "audio", themeConfig, cssVars };
  }

  const themeConfig: DefaultThemeConfig = {
    controlBarVisibility: ControlBarVisibility.ENABLED,
    controlBar: [
      DefaultThemeControl.PLAY,
      DefaultThemeControl.FRAME_BACKWARD,
      DefaultThemeControl.FRAME_FORWARD,
      DefaultThemeControl.SCRUBBER,
      DefaultThemeControl.TIME_TOGGLE,
      DefaultThemeControl.VOLUME,
      DefaultThemeControl.PLAYBACK_RATE,
      DefaultThemeControl.TEXT_TOGGLE,
      DefaultThemeControl.TRACK_SELECTOR,
      DefaultThemeControl.FULLSCREEN,
    ],
    floatingControls: [
      DefaultThemeFloatingControl.ACTION_ICONS,
      DefaultThemeFloatingControl.PLAYBACK_CONTROLS,
    ],
    alwaysOnFloatingControls: [],
    actionIcons: [DefaultThemeActionIcon.HELP_MENU],
    playbackRates: PLAYBACK_RATES,
    trackSelectorAutoClose: true,
    timeFormat: ChromingTimeFormat.TIMECODE,
    timeInteractive: false,
    // The VU meter needs an audio peak processor and is off by default here;
    // the detail page has no meter surface to render it into.
    isFloatingVuMeterVisible: false,
    vuMeterConfig: {},
  };
  return { mediaType: "video", themeConfig, cssVars };
}
