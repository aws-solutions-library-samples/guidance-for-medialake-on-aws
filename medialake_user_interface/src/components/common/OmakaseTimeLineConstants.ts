import { Triangle } from "lucide-react";
import {
  ScrubberLaneStyle,
  TimelineLaneStyle,
  TimelineStyle,
  PeriodMarkerStyle,
} from "@byomakase/omakase-player";
import { randomHexColor } from "./utils";

export const TIMELINE_STYLE: Partial<TimelineStyle> = {
  stageMinHeight: 100,
  rightPaneMarginLeft: 10,
  rightPaneMarginRight: 10,
  rightPaneClipPadding: 10,

  backgroundFill: "#E4E5E5",

  headerHeight: 0,
  headerBackgroundFill: "#EDEFEE",
  headerMarginBottom: 0,

  footerHeight: 0,
  footerBackgroundFill: "#EDEFEE",
  footerMarginTop: 0,

  thumbnailHoverWidth: 200,
  thumbnailHoverStroke: "#ff4991",
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

  playheadBackgroundFill: "#ffffff",
  playheadBackgroundOpacity: 0,

  playheadPlayProgressFill: "#008cbc",
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
  backgroundFill: "#edefee",
};

export const SCRUBBER_LANE_STYLE: Partial<ScrubberLaneStyle> = {
  ...TIMELINE_LANE_STYLE,
  tickFill: "#5f6070",
  timecodeFill: "#5f6070",
};

export const TIMELINE_STYLE_DARK: Partial<TimelineStyle> = {
  ...TIMELINE_STYLE,
  stageMinHeight: 30,
  backgroundFill: "#292d43",

  playheadFill: "#43F4FF",
  playheadBufferedFill: "#989BFF",
  playheadBackgroundFill: "#83899E",
  playheadPlayProgressFill: "#3E44FE",

  scrubberFill: "#B2BAD6",
  scrubberSnappedFill: "#9ED78D",
};

export const TIMELINE_LANE_STYLE_DARK: Partial<TimelineLaneStyle> = {
  ...TIMELINE_LANE_STYLE,
  backgroundFill: "#292D43",
};

export const SCRUBBER_LANE_STYLE_DARK: Partial<ScrubberLaneStyle> = {
  ...TIMELINE_LANE_STYLE_DARK,
  tickFill: "#FFFFFF",
  timecodeFill: "#FFFFFF",
};

export const PERIOD_MARKER_STYLE: Partial<PeriodMarkerStyle> = {
  color: randomHexColor(),
  symbolSize: 10,
  symbolType: "circle",
};
