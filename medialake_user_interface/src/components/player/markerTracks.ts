/**
 * Marker tracks — the single source of truth for detail-page markers.
 *
 * ## Why this replaces `marker-sync/`
 *
 * Under 0.25.x the player had no owner for marker state, so the app grew one:
 * `MarkerSyncCoordinator` held the authoritative list, persisted it, and
 * `useMarkerTrackSync` mirrored it onto the player's chroming marker track with
 * two id maps and an echo-suppression flag. The sidebar kept a third copy as
 * React state. Three copies of the same list meant three ways to disagree, and
 * they did: a marker added by keyboard shortcut or moved by dragging never
 * reached the sidebar, because the sidebar only re-projected on its own writes.
 *
 * 1.1.1 supplies the owner. A `MarkerTrack` holds markers, exposes CRUD
 * (`addTimedItems` / `updateTimedItem` / `deleteTimedItems`) and query helpers,
 * and emits events on change. Every surface — the chroming marker bars, a
 * timeline lane, and our own React panel — binds to the same track and follows
 * it. So the coordinator, the adapter port, the id maps and the echo guard all
 * go away, and the sidebar bug goes away with them: the panel is derived from
 * track events rather than written to independently.
 *
 * ## Two tracks, not one
 *
 * User markers and semantic clip matches are separate tracks because they differ
 * in every respect that matters to Omakase: clips are read-only and coloured by
 * confidence, user markers are editable and individually coloured. Separate
 * tracks give each its own marker bar, its own colour rule, and its own locked
 * flag, without per-marker branching.
 *
 * ## Times are strings
 *
 * `TimedItemTemporal` carries times as strings of seconds (`{type: SPAN, start:
 * '56', end: '63'}`), not numbers. Conversion is centralised in
 * `toSpanTemporal` / `readSpan` so no caller has to remember it.
 */
import {
  DefaultMarker,
  MarkerTrack,
  TimedItemTemporalType,
  TimedItemsTrackEventType,
  type Marker,
  type MarkerState,
  type TimedItemTemporal,
} from "@byomakase/omakase-player";

/** Which logical track a marker belongs to. */
export type MarkerKind = "user" | "semantic";

/**
 * A marker as the MediaLake UI thinks about it: seconds, plus the display and
 * provenance fields we attach.
 *
 * This is a read model projected from `MarkerState`. It is not stored anywhere —
 * the track is the store.
 */
export interface DetailMarker {
  /** Omakase's marker uuid. Stable for the lifetime of the track. */
  id: string;
  kind: MarkerKind;
  startTime: number;
  endTime: number;
  label?: string;
  color?: string;
  /** Semantic markers only: the clip's match score. */
  score?: number;
  /** Semantic markers only: embedding model version, for confidence banding. */
  modelVersion?: string;
}

/**
 * The payload we attach to each marker via `TimedItemArgs.data`.
 *
 * Omakase carries this through untouched and hands it back on every event, which
 * is what lets a marker stay self-describing without a side table keyed by id —
 * the mechanism the old coordinator's envelope map existed to provide.
 */
interface MarkerData {
  kind: MarkerKind;
  color?: string;
  score?: number;
  modelVersion?: string;
}

/** Build a SPAN temporal from seconds. Omakase expects strings. */
export function toSpanTemporal(startTime: number, endTime: number): TimedItemTemporal {
  return {
    type: TimedItemTemporalType.SPAN,
    start: String(startTime),
    end: String(endTime),
  };
}

/**
 * Read a temporal back into seconds.
 *
 * Returns null for the temporal shapes a span marker should never have
 * (`MOMENT`, `SPAN_START`, `SPAN_END`) or for values that don't parse, so callers
 * drop the marker rather than render `NaN`.
 */
export function readSpan(temporal: TimedItemTemporal): { start: number; end: number } | null {
  if (temporal.type !== TimedItemTemporalType.SPAN) return null;

  // `Number("")` is 0, not NaN, so a blank temporal would otherwise read as a
  // zero-length marker at the head of the timeline instead of being rejected.
  if (!temporal.start?.trim() || !temporal.end?.trim()) return null;

  const start = Number(temporal.start);
  const end = Number(temporal.end);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;

  return { start, end };
}

/** Project an Omakase `MarkerState` into the UI read model. */
export function toDetailMarker(state: MarkerState): DetailMarker | null {
  const span = readSpan(state.temporal);
  if (!span) return null;

  const data = (state.data ?? {}) as Partial<MarkerData>;

  return {
    id: state.id,
    kind: data.kind === "semantic" ? "semantic" : "user",
    startTime: span.start,
    endTime: span.end,
    label: state.label,
    color: data.color,
    score: data.score,
    modelVersion: data.modelVersion,
  };
}

/** Construction input for a new marker. */
export interface CreateMarkerInput {
  kind: MarkerKind;
  startTime: number;
  endTime: number;
  label?: string;
  color?: string;
  score?: number;
  modelVersion?: string;
}

/**
 * Build a marker instance.
 *
 * The colour rides in `data` rather than being written as an Omakase marker
 * style: per-track colour is set once on the marker bar / lane, and per-marker
 * overrides go through `setMarkerViewStyle`, so `data.color` stays the single
 * value our React panel and the Omakase surfaces both read.
 */
export function createMarker(input: CreateMarkerInput): DefaultMarker {
  const data: MarkerData = {
    kind: input.kind,
    color: input.color,
    score: input.score,
    modelVersion: input.modelVersion,
  };

  return new DefaultMarker({
    temporal: toSpanTemporal(input.startTime, input.endTime),
    label: input.label,
    data,
  });
}

/**
 * Read every marker off a track, ordered by start time.
 *
 * `timedItemsSorted` is Omakase's own ascending-by-start ordering, so the panel
 * does not need to sort — and cannot disagree with the marker bar about order.
 */
export function readTrackMarkers(track: MarkerTrack | undefined): DetailMarker[] {
  if (!track) return [];

  const markers: DetailMarker[] = [];
  for (const item of track.timedItemsSorted) {
    const projected = toDetailMarker(item.state as MarkerState);
    if (projected) markers.push(projected);
  }
  return markers;
}

/**
 * Subscribe to any change in a track's marker collection.
 *
 * Fires on add, delete and update. Returns an unsubscribe function.
 *
 * This is the subscription the old sidebar was missing. Because every mutation
 * path — panel, keyboard shortcut, a drag on the marker bar — lands on the track,
 * one subscription here keeps the panel correct for all of them.
 */
export function onTrackMarkersChanged(track: MarkerTrack, handler: () => void): () => void {
  const subscription = track.onEvent$.subscribe({
    next: (event) => {
      if (
        event.type === TimedItemsTrackEventType.TIMED_ITEMS_TRACK_ITEMS_ADDED ||
        event.type === TimedItemsTrackEventType.TIMED_ITEMS_TRACK_ITEMS_DELETED ||
        event.type === TimedItemsTrackEventType.TIMED_ITEMS_TRACK_ITEMS_UPDATED
      ) {
        handler();
      }
    },
  });

  return () => {
    try {
      subscription.unsubscribe();
    } catch {
      // Already torn down with the player.
    }
  };
}

/**
 * Find the marker whose span covers `time`, preferring the nearest start.
 *
 * Delegates to the track's own spatial queries rather than scanning a copy of
 * the list, which is what makes marker navigation O(log n)-ish on the track's
 * sorted collection instead of a linear scan through React state.
 */
export function findMarkerAtTime(
  track: MarkerTrack | undefined,
  time: number
): DetailMarker | null {
  if (!track) return null;

  const item = track.findFirstTimedItemAtTime(time) as Marker | undefined;
  if (!item) return null;

  return toDetailMarker(item.state as MarkerState);
}

/**
 * The marker nearest `time` by start, used by next/previous navigation.
 */
export function findNearestMarker(
  track: MarkerTrack | undefined,
  time: number
): DetailMarker | null {
  if (!track) return null;

  const item = track.findNearestTimedItem(time) as Marker | undefined;
  if (!item) return null;

  return toDetailMarker(item.state as MarkerState);
}
