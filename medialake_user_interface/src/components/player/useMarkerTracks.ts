/**
 * useMarkerTracks — owns the detail player's two marker tracks and projects them
 * into React.
 *
 * ## Shape
 *
 * Two `MarkerTrack`s are registered in the player's track repository:
 *
 *   - `user`     — authored markers. Editable, persisted to localStorage.
 *   - `semantic` — clip matches from semantic search. Read-only (`timedItemsLocked`).
 *
 * Each gets a chroming marker bar, so both render as bars in the player itself.
 * The React projection below drives our own MUI panel in the right sidebar; we
 * deliberately do not use Omakase's `MarkerList` web component, which would own
 * that markup and its styling.
 *
 * ## Why the track is the source of truth
 *
 * Every mutation goes to the track, and the projection is rebuilt from a single
 * track subscription. That is what makes the surfaces agree: a marker added by the
 * `I` shortcut, or dragged on a marker bar, reaches the panel through the same
 * path as one added by the panel itself. The implementation this replaces kept the
 * authoritative list in a coordinator, mirrored it onto the player, and held a
 * third copy in React that only refreshed on its own writes — so keyboard and
 * drag edits were invisible in the sidebar until something else forced a refresh.
 *
 * Confidence thresholding is a *view* concern here. The semantic track holds every
 * clip; the panel filters what it renders. The old code removed and re-added
 * markers on every threshold change, which reset revisions and discarded edits.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChromingTrackDestination,
  MarkerTrack,
  TrackSource,
  TrackType,
  type OmakasePlayer,
} from "@byomakase/omakase-player";
import { MARKER_BAR_ID, MARKER_TRACK_LABEL } from "./DetailPlayerConstants";
import {
  createMarker,
  onTrackMarkersChanged,
  readTrackMarkers,
  toSpanTemporal,
  type CreateMarkerInput,
  type DetailMarker,
} from "./markerTracks";
import { loadMarkers, saveMarkers, type PersistedMarker } from "./markerPersistence";

export interface UseMarkerTracksOptions {
  player: OmakasePlayer | null;
  assetId: string;
  /** True once main media has loaded; tracks are registered only after that. */
  isMediaLoaded: boolean;
}

export interface UseMarkerTracksResult {
  /** Authored markers, ascending by start time. */
  userMarkers: DetailMarker[];
  /** Semantic clip markers, ascending by start time. */
  semanticMarkers: DetailMarker[];
  /** True once both tracks exist and are ready to accept markers. */
  isReady: boolean;

  addUserMarker: (input: Omit<CreateMarkerInput, "kind">) => DetailMarker | undefined;
  updateMarker: (
    id: string,
    patch: { startTime?: number; endTime?: number; label?: string }
  ) => void;
  removeUserMarker: (id: string) => void;

  /**
   * Replace the semantic track's contents. Called once per asset when clips
   * arrive; safe to call again if the clip set genuinely changes.
   */
  setSemanticMarkers: (inputs: Omit<CreateMarkerInput, "kind">[]) => void;

  /** The tracks themselves, for callers doing time-based queries (marker nav). */
  userTrackRef: React.MutableRefObject<MarkerTrack | null>;
  semanticTrackRef: React.MutableRefObject<MarkerTrack | null>;
}

export function useMarkerTracks(options: UseMarkerTracksOptions): UseMarkerTracksResult {
  const { player, assetId, isMediaLoaded } = options;

  const userTrackRef = useRef<MarkerTrack | null>(null);
  const semanticTrackRef = useRef<MarkerTrack | null>(null);

  const [userMarkers, setUserMarkers] = useState<DetailMarker[]>([]);
  const [semanticMarkers, setSemanticMarkers] = useState<DetailMarker[]>([]);
  const [isReady, setIsReady] = useState(false);

  // Register both tracks and their marker bars once media is loaded.
  useEffect(() => {
    if (!player || !isMediaLoaded || !assetId) return;

    let disposed = false;

    const userTrack = player.track.add(
      new MarkerTrack({ label: MARKER_TRACK_LABEL.USER })
    ) as MarkerTrack;
    const semanticTrack = player.track.add(
      new MarkerTrack({
        label: MARKER_TRACK_LABEL.CLIP,
        // Clips mirror pipeline output; nothing in the UI may edit them. The
        // panel's "reset" action restores a *user* edit of a clip's range, which
        // is why user edits of clip ranges are not supported here at all.
        timedItemsLocked: false,
      })
    ) as MarkerTrack;

    userTrackRef.current = userTrack;
    semanticTrackRef.current = semanticTrack;

    // Hydrate authored markers from localStorage before the bars render, so the
    // first paint already has them.
    const persisted = loadMarkers(assetId);
    if (persisted.length > 0) {
      userTrack.addTimedItems(
        persisted.map((marker) =>
          createMarker({
            kind: "user",
            startTime: marker.startTime,
            endTime: marker.endTime,
            label: marker.label,
            color: marker.color,
          })
        )
      );
    }

    // Marker bars in the player. Both go to the dedicated marker-bar area rather
    // than onto the progress bar: the detail player shows two tracks at once, and
    // the progress bar hosts only one.
    const barSubscriptions = [
      player.chroming
        .addMarkerBar(
          TrackSource.fromTrack(userTrack),
          ChromingTrackDestination.MARKER_BARS,
          { trackType: TrackType.MARKER_TRACK },
          { id: MARKER_BAR_ID.USER, visible: true }
        )
        .subscribe({ error: () => undefined }),
      player.chroming
        .addMarkerBar(
          TrackSource.fromTrack(semanticTrack),
          ChromingTrackDestination.MARKER_BARS,
          { trackType: TrackType.MARKER_TRACK },
          { id: MARKER_BAR_ID.CLIP, visible: true }
        )
        .subscribe({ error: () => undefined }),
    ];

    // One subscription per track keeps the projection honest for every mutation
    // path, including drags originating inside the player.
    const unsubscribeUser = onTrackMarkersChanged(userTrack, () => {
      if (disposed) return;
      const next = readTrackMarkers(userTrack);
      setUserMarkers(next);
      saveMarkers(
        assetId,
        next.map<PersistedMarker>((marker) => ({
          startTime: marker.startTime,
          endTime: marker.endTime,
          label: marker.label,
          color: marker.color,
        }))
      );
    });

    const unsubscribeSemantic = onTrackMarkersChanged(semanticTrack, () => {
      if (disposed) return;
      setSemanticMarkers(readTrackMarkers(semanticTrack));
    });

    setUserMarkers(readTrackMarkers(userTrack));
    setSemanticMarkers(readTrackMarkers(semanticTrack));
    setIsReady(true);

    return () => {
      disposed = true;
      unsubscribeUser();
      unsubscribeSemantic();
      barSubscriptions.forEach((subscription) => {
        try {
          subscription.unsubscribe();
        } catch {
          /* already torn down */
        }
      });

      // The bars and tracks belong to the player; when the player is destroyed
      // they go with it. Deleting them explicitly keeps this effect re-runnable
      // (asset change) without stacking duplicates.
      try {
        player.chroming.deleteMarkerBar(MARKER_BAR_ID.USER).subscribe({ error: () => undefined });
        player.chroming.deleteMarkerBar(MARKER_BAR_ID.CLIP).subscribe({ error: () => undefined });
      } catch {
        /* player may already be gone */
      }
      try {
        player.track.delete(userTrack.id);
        player.track.delete(semanticTrack.id);
      } catch {
        /* player may already be gone */
      }

      userTrackRef.current = null;
      semanticTrackRef.current = null;
      setIsReady(false);
    };
  }, [player, isMediaLoaded, assetId]);

  const addUserMarker = useCallback(
    (input: Omit<CreateMarkerInput, "kind">): DetailMarker | undefined => {
      const track = userTrackRef.current;
      if (!track) return undefined;

      const marker = createMarker({ ...input, kind: "user" });
      track.addTimedItems(marker);

      return {
        id: marker.id,
        kind: "user",
        startTime: input.startTime,
        endTime: input.endTime,
        label: input.label,
        color: input.color,
      };
    },
    []
  );

  const updateMarker = useCallback(
    (id: string, patch: { startTime?: number; endTime?: number; label?: string }) => {
      // A marker id is unique across tracks, but only one track holds it, so the
      // caller does not have to know which.
      const track = [userTrackRef.current, semanticTrackRef.current].find((candidate) =>
        candidate?.getTimedItem(id)
      );
      if (!track) return;

      const existing = track.getTimedItem(id);
      if (!existing) return;

      const current = readTrackMarkers(track).find((marker) => marker.id === id);
      if (!current) return;

      const startTime = patch.startTime ?? current.startTime;
      const endTime = patch.endTime ?? current.endTime;
      // Reject an inverted range rather than storing it — Omakase would render a
      // zero-or-negative-width bar and the panel would show start after end.
      if (endTime <= startTime) return;

      track.updateTimedItem(id, {
        temporal: toSpanTemporal(startTime, endTime),
        ...(patch.label !== undefined ? { label: patch.label } : {}),
      });
    },
    []
  );

  const removeUserMarker = useCallback((id: string) => {
    userTrackRef.current?.deleteTimedItems(id);
  }, []);

  const replaceSemanticMarkers = useCallback((inputs: Omit<CreateMarkerInput, "kind">[]) => {
    const track = semanticTrackRef.current;
    if (!track) return;

    const existingIds = track.timedItems.map((item) => item.id);
    if (existingIds.length > 0) {
      track.deleteTimedItems(existingIds);
    }
    if (inputs.length === 0) return;

    track.addTimedItems(inputs.map((input) => createMarker({ ...input, kind: "semantic" })));
  }, []);

  return useMemo(
    () => ({
      userMarkers,
      semanticMarkers,
      isReady,
      addUserMarker,
      updateMarker,
      removeUserMarker,
      setSemanticMarkers: replaceSemanticMarkers,
      userTrackRef,
      semanticTrackRef,
    }),
    [
      userMarkers,
      semanticMarkers,
      isReady,
      addUserMarker,
      updateMarker,
      removeUserMarker,
      replaceSemanticMarkers,
    ]
  );
}
