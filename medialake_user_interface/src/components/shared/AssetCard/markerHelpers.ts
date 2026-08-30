/**
 * Marker helper functions for Omakase player clip markers.
 * Pure functions — no React dependencies.
 */
import {
  ChromingTrackDestination,
  MarkerTrack,
  MediaTemporalFormat,
  TrackSource,
  TrackType,
  type OmakasePlayer,
} from "@byomakase/omakase-player";
import { getMarkerColorByConfidence } from "../../common/utils";
import { DEFAULT_FPS, parseTimecode } from "@/utils/timecode";
import { createMarker } from "@/components/player/markerTracks";

/**
 * Label for the single marker track each card player owns.
 *
 * Used to find the existing track on re-runs instead of registering another —
 * cards re-render on clip and threshold changes, and Omakase has no
 * "replace the bar" call.
 */
const CARD_MARKER_TRACK_LABEL = "clips";

export interface ClipData {
  start_timecode?: string;
  end_timecode?: string;
  start?: number;
  end?: number;
  score?: number;
  embedding_option?: string;
  model_version?: string;
}

/**
 * Convert a source timecode to seconds for marker placement.
 *
 * `fps` is optional because a card only has the clip payload, not the asset's
 * embedded metadata; it falls back to `DEFAULT_FPS`, the same rate the player is
 * loaded with. Callers that do know the asset's real rate should pass it.
 *
 * Returns 0 for unparseable input, matching the previous behaviour — a marker at
 * the head of the timeline is a visible, recoverable error, whereas NaN silently
 * breaks the player's marker track.
 */
export function timecodeToSeconds(tc: string, fps: number = DEFAULT_FPS): number {
  return parseTimecode(tc, fps) ?? 0;
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

  // One marker track per card, reused across re-renders. 1.1.1 has no
  // `chroming.progressMarkerTrack` to write into: markers live on a MarkerTrack
  // registered in the track repository, and a chroming marker bar renders it.
  // `find` keeps this idempotent — the effect re-runs whenever clips or the
  // confidence threshold change, and re-registering would stack duplicate bars.
  const existing = player.track.findFirst(
    (track) => (track as MarkerTrack).label === CARD_MARKER_TRACK_LABEL
  ) as MarkerTrack | undefined;

  const markerTrack =
    existing ??
    (player.track.add(new MarkerTrack({ label: CARD_MARKER_TRACK_LABEL })) as MarkerTrack);

  if (!existing) {
    // Register the bar on the progress bar so clip matches read as segments of
    // the scrubber, which is what the card's Stamp chroming shows.
    player.chroming
      .addMarkerBar(TrackSource.fromTrack(markerTrack), ChromingTrackDestination.PROGRESS_BAR, {
        trackType: TrackType.MARKER_TRACK,
      })
      .subscribe({
        error: () => {
          // A card can be parked before the bar resolves; nothing to recover.
        },
      });
  }

  // Replace the previous set wholesale — the threshold filter changes which
  // clips qualify, and diffing a read-only derived set buys nothing.
  try {
    markerTrack.deleteTimedItems(markerTrack.timedItems.map((item) => item.id));
  } catch {
    /* track may be locked or already gone */
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

    const marker = createMarker({
      kind: "semantic",
      startTime: start,
      endTime: end,
      color: getMarkerColorByConfidence(clip.score, clip.model_version),
      score: clip.score,
      modelVersion: clip.model_version,
    });

    try {
      markerTrack.addTimedItems(marker);
      markerIds.push(marker.id);
      if (isClip || (filteredClips.length === 1 && index === 0)) {
        // Fire-and-forget seek — don't subscribe synchronously as it blocks the main thread
        // when multiple cards load simultaneously. The seek is best-effort.
        try {
          player.player.seekTo(start, MediaTemporalFormat.SECONDS).subscribe({
            error: () => {
              /* media may not be ready */
            },
          });
        } catch {
          /* media may not be ready */
        }
      }
    } catch {
      /* ok */
    }
  });

  return markerIds;
}
