/**
 * Marker helper functions for Omakase player clip markers.
 * Pure functions — no React dependencies.
 */
import { OmakasePlayer, PeriodMarker } from "@byomakase/omakase-player";
import { getMarkerColorByConfidence } from "../../common/utils";

export interface ClipData {
  start_timecode?: string;
  end_timecode?: string;
  start?: number;
  end?: number;
  score?: number;
  embedding_option?: string;
  model_version?: string;
}

export function timecodeToSeconds(tc: string): number {
  const [hh, mm, ss, ff] = tc.split(":").map(Number);
  const fps = 25;
  return hh * 3600 + mm * 60 + ss + (isNaN(ff) ? 0 : ff / fps);
}

export function getFilteredClips(
  id: string,
  clips: ClipData[] | undefined,
  isSemantic: boolean,
  confidenceThreshold: number
): ClipData[] {
  if (!Array.isArray(clips) || clips.length === 0) return [];
  const isClip = id.includes("#CLIP#") || id.includes("_clip_");

  if (isClip) {
    return clips.filter(
      (clip) =>
        (clip.start_timecode && clip.end_timecode) ||
        (typeof clip.start === "number" && typeof clip.end === "number")
    );
  }

  const shouldFilter = isSemantic && confidenceThreshold > 0;
  return shouldFilter ? clips.filter((clip) => (clip.score ?? 1) >= confidenceThreshold) : clips;
}

export function addMarkersToPlayer(
  player: OmakasePlayer,
  id: string,
  clips: ClipData[],
  isSemantic: boolean,
  confidenceThreshold: number
): string[] {
  const markerIds: string[] = [];
  const isClip = id.includes("#CLIP#") || id.includes("_clip_");
  const filteredClips = getFilteredClips(id, clips, isSemantic, confidenceThreshold);

  try {
    player.progressMarkerTrack.removeAllMarkers();
  } catch {
    /* ok */
  }

  filteredClips.forEach((clip, index) => {
    const start =
      typeof clip.start === "number"
        ? clip.start
        : clip.start_timecode
          ? timecodeToSeconds(clip.start_timecode)
          : undefined;
    const end =
      typeof clip.end === "number"
        ? clip.end
        : clip.end_timecode
          ? timecodeToSeconds(clip.end_timecode)
          : undefined;

    if (start === undefined || end === undefined) return;
    if ((start === 0 && end - start < 1) || (start < 2 && end - start < 1)) return;
    if (end - start < 1) return;

    const marker = new PeriodMarker({
      timeObservation: { start, end },
      style: { color: getMarkerColorByConfidence(clip.score, clip.model_version) },
    });

    try {
      player.progressMarkerTrack.addMarker(marker);
      markerIds.push(marker.id || `${start}-${end}`);
      if (isClip || (filteredClips.length === 1 && index === 0)) {
        // Fire-and-forget seek — don't subscribe synchronously as it blocks the main thread
        // when multiple cards load simultaneously. The seek is best-effort.
        try {
          player.video.seekToTime(start);
        } catch {
          /* video may not be ready */
        }
      }
    } catch {
      /* ok */
    }
  });

  return markerIds;
}
