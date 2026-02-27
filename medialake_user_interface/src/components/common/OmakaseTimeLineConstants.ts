import {
  ScrubberLaneStyle,
  TimelineLaneStyle,
  TimelineStyle,
  PeriodMarkerStyle,
} from "@byomakase/omakase-player";
import { randomHexColor } from "./utils";
import { colorTokens } from "@/theme/tokens";

/**
 * Timeline constants — wired to design tokens where possible.
 * The Omakase player API requires raw color strings, so we reference
 * colorTokens directly rather than the MUI theme object.
 */

export const TIMELINE_STYLE: Partial<TimelineStyle> = {
  stageMinHeight: 100,
  rightPaneMarginLeft: 10,
  rightPaneMarginRight: 10,
  rightPaneClipPadding: 10,

  backgroundFill: colorTokens.background.default.light,

  headerHeight: 0,
  headerBackgroundFill: colorTokens.background.default.light,
  headerMarginBottom: 0,

  footerHeight: 0,
  footerBackgroundFill: colorTokens.background.default.light,
  footerMarginTop: 0,

  thumbnailHoverWidth: 200,
  thumbnailHoverStroke: colorTokens.secondary.main,
  thumbnailHoverStrokeWidth: 5,
  thumbnailHoverYOffset: 0,

  leftPaneWidth: 0,
  scrollbarHeight: 0,

  playheadVisible: true,
  playheadFill: "#000",
  playheadLineWidth: 2,
  playheadSymbolHeight: 10,
  playheadScrubberHeight: 10,
  playheadTextFill: "rgb(0,0,0, 0)", // opacity 0
  playheadTextYOffset: -15,

  playheadBackgroundFill: colorTokens.background.paper.light,
  playheadBackgroundOpacity: 0,

  playheadPlayProgressFill: colorTokens.info.main,
  playheadPlayProgressOpacity: 0.5,

  playheadBufferedFill: "#a2a2a2",
  playheadBufferedOpacity: 1,

  scrubberHeight: 50,
  scrubberMarginBottom: 2,

  scrubberSnappedFill: "rgb(0,0,0,0)",
  scrubberSouthLineOpacity: 0.2,
  scrubberTextFill: "rgb(0,0,0,0)",
  scrubberTextYOffset: -15,
};

export const TIMELINE_LANE_STYLE: Partial<TimelineLaneStyle> = {
  marginBottom: 0,
  backgroundFill: colorTokens.background.default.light,
};

export const SCRUBBER_LANE_STYLE: Partial<ScrubberLaneStyle> = {
  ...TIMELINE_LANE_STYLE,
  tickFill: colorTokens.text.secondary.light,
  timecodeFill: colorTokens.text.secondary.light,
};

export const TIMELINE_STYLE_DARK: Partial<TimelineStyle> = {
  ...TIMELINE_STYLE,
  stageMinHeight: 30,
  backgroundFill: colorTokens.background.default.dark,

  playheadFill: colorTokens.accent.light,
  playheadBufferedFill: colorTokens.secondary.light,
  playheadBackgroundFill: colorTokens.text.secondary.dark,
  playheadPlayProgressFill: colorTokens.secondary.dark,

  scrubberFill: "#B2BAD6",
  scrubberSnappedFill: colorTokens.success.light,
};

export const TIMELINE_LANE_STYLE_DARK: Partial<TimelineLaneStyle> = {
  ...TIMELINE_LANE_STYLE,
  backgroundFill: colorTokens.background.default.dark,
};

export const SCRUBBER_LANE_STYLE_DARK: Partial<ScrubberLaneStyle> = {
  ...TIMELINE_LANE_STYLE_DARK,
  tickFill: colorTokens.text.primary.dark,
  timecodeFill: colorTokens.text.primary.dark,
};

export const PERIOD_MARKER_STYLE: Partial<PeriodMarkerStyle> = {
  color: randomHexColor(),
  symbolSize: 10,
  symbolType: "circle",
};
