import type { Theme } from "@mui/material/styles";
import type React from "react";
import type { OmakaseThemeConfig, AudioThemeConfig } from "@byomakase/omakase-player";
import {
  OmakaseControlBarVisibility,
  OmakaseThemeControl,
  OmakaseThemeFloatingControl,
  OmakaseThemeActionIcon,
  OmakaseProgressBarPosition,
  ControlBarVisibility,
  AudioThemeControl,
  AudioThemeFloatingControl,
  AudioPlayerSize,
  AudioVisualization,
  TimeFormat,
} from "@byomakase/omakase-player";

export type PlayerThemeResult =
  | { mediaType: "video"; themeConfig: OmakaseThemeConfig; cssVars: React.CSSProperties }
  | { mediaType: "audio"; themeConfig: AudioThemeConfig; cssVars: React.CSSProperties };

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
      controlBarVisibility: ControlBarVisibility.Enabled,
      controlBar: [
        AudioThemeControl.Play,
        AudioThemeControl.Scrubber,
        AudioThemeControl.Volume,
        AudioThemeControl.Time,
        AudioThemeControl.PlaybackRate,
        AudioThemeControl.Trackselector,
      ],
      floatingControls: [AudioThemeFloatingControl.HelpMenu],
      playbackRates: [0.25, 0.5, 1, 1.5, 2, 4],
      playerSize: AudioPlayerSize.Full,
      visualization: AudioVisualization.Enabled,
      visualizationConfig: {
        strokeColor: theme.palette.primary.main,
        fillColors: [theme.palette.primary.light, theme.palette.primary.dark],
      },
      timeFormat: TimeFormat.Timecode,
    };
    return { mediaType: "audio", themeConfig, cssVars };
  }

  const themeConfig: OmakaseThemeConfig = {
    controlBarVisibility: OmakaseControlBarVisibility.Enabled,
    controlBar: [
      OmakaseThemeControl.Play,
      OmakaseThemeControl.FrameBackward,
      OmakaseThemeControl.FrameForward,
      OmakaseThemeControl.Volume,
      OmakaseThemeControl.Time,
      OmakaseThemeControl.PlaybackRate,
      OmakaseThemeControl.Trackselector,
      OmakaseThemeControl.Fullscreen,
    ],
    floatingControls: [
      OmakaseThemeFloatingControl.ProgressBar,
      OmakaseThemeFloatingControl.PlaybackControls,
    ],
    alwaysOnFloatingControls: [OmakaseThemeFloatingControl.ProgressBar],
    actionIcons: [
      OmakaseThemeActionIcon.HelpMenu,
      OmakaseThemeActionIcon.AudioToggle,
      OmakaseThemeActionIcon.Fullscreen,
    ],
    progressBarPosition: OmakaseProgressBarPosition.OverVideo,
    playbackRates: [0.25, 0.5, 1, 1.5, 2, 4],
    timeFormat: TimeFormat.Timecode,
  };
  return { mediaType: "video", themeConfig, cssVars };
}
