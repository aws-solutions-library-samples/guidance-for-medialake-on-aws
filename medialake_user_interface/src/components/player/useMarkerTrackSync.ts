/**
 * useMarkerTrackSync — creates a chroming marker track via
 * player.chroming.createMarkerTrack() and syncs it bidirectionally
 * with the MarkerSyncCoordinator.
 *
 * The chroming marker track is a thin bar rendered inside the player
 * chrome (above the progress bar). It supports editable PeriodMarkers
 * with mouse drag on start/end handles, and fires onMarkerUpdate$
 * when markers are moved.
 *
 * Event handlers are registered immediately so that markers added
 * before the track is ready are queued and flushed once the track
 * becomes available.
 */
import { useEffect, useRef } from "react";
import { OmakasePlayer, PeriodMarker } from "@byomakase/omakase-player";
import type { MarkerTrackApi, MarkerUpdateEvent } from "@byomakase/omakase-player";
import type { DetailMarkerAdapter, MarkerApi } from "./marker-sync/ports";

export interface UseMarkerTrackSyncOptions {
  playerRef: React.MutableRefObject<OmakasePlayer | null>;
  markerAdapter: DetailMarkerAdapter;
  isReady: boolean;
}

export function useMarkerTrackSync({
  playerRef,
  markerAdapter,
  isReady,
}: UseMarkerTrackSyncOptions): void {
  const coordToTrackId = useRef<Map<string, string>>(new Map());
  const trackToCoordId = useRef<Map<string, string>>(new Map());
  const suppressTrackUpdate = useRef(false);
  const markerTrackApiRef = useRef<MarkerTrackApi | null>(null);
  // Queue of pending operations that arrived before the track was ready
  const pendingOps = useRef<
    Array<{ type: "add" | "remove" | "update" | "clear"; payload?: unknown }>
  >([]);

  useEffect(() => {
    if (!isReady) return;

    const player = playerRef.current;
    if (!player?.chroming) return;

    const c2t = coordToTrackId.current;
    const t2c = trackToCoordId.current;
    c2t.clear();
    t2c.clear();
    pendingOps.current = [];

    const subscriptions: { unsubscribe(): void }[] = [];

    // --- track operations (only work when track is ready) ---
    const addToTrack = (m: MarkerApi) => {
      const track = markerTrackApiRef.current;
      if (!track) {
        pendingOps.current.push({ type: "add", payload: m });
        return;
      }
      if (c2t.has(m.id)) return;
      try {
        const pm = new PeriodMarker({
          timeObservation: { start: m.timeObservation.start, end: m.timeObservation.end },
          editable: true,
          style: { color: m.color ?? "#F5A524" },
        });
        const added = track.addMarker(pm);
        c2t.set(m.id, added.id);
        t2c.set(added.id, m.id);
      } catch {
        /* track may not be ready */
      }
    };

    const removeFromTrack = (coordId: string) => {
      const track = markerTrackApiRef.current;
      if (!track) {
        pendingOps.current.push({ type: "remove", payload: { id: coordId } });
        return;
      }
      const trackId = c2t.get(coordId);
      if (!trackId) return;
      try {
        track.removeMarker(trackId);
      } catch {
        /* ok */
      }
      c2t.delete(coordId);
      t2c.delete(trackId);
    };

    const updateOnTrack = (m: MarkerApi) => {
      if (suppressTrackUpdate.current) return;
      const track = markerTrackApiRef.current;
      if (!track) {
        pendingOps.current.push({ type: "update", payload: m });
        return;
      }
      const trackId = c2t.get(m.id);
      if (!trackId) return;
      try {
        track.updateMarker(trackId, {
          timeObservation: { start: m.timeObservation.start, end: m.timeObservation.end },
          style: { color: m.color ?? "#F5A524" },
        });
      } catch {
        // Fallback: remove + re-add
        removeFromTrack(m.id);
        addToTrack(m);
      }
    };

    const clearTrack = () => {
      const track = markerTrackApiRef.current;
      if (!track) {
        pendingOps.current.push({ type: "clear" });
        return;
      }
      try {
        track.removeAllMarkers();
      } catch {
        /* ok */
      }
      c2t.clear();
      t2c.clear();
    };

    // --- coordinator event handlers (registered immediately) ---
    const onAdded = (payload?: unknown) => {
      const m = payload as MarkerApi;
      if (m?.id) addToTrack(m);
    };
    const onRemoved = (payload?: unknown) => {
      const p = payload as { id: string };
      if (p?.id) removeFromTrack(p.id);
    };
    const onUpdated = (payload?: unknown) => {
      const m = payload as MarkerApi;
      if (m?.id) updateOnTrack(m);
    };
    const onCleared = () => clearTrack();

    markerAdapter.on("MARKER_ADDED", onAdded);
    markerAdapter.on("MARKER_REMOVED", onRemoved);
    markerAdapter.on("MARKER_UPDATED", onUpdated);
    markerAdapter.on("MARKER_CLEARED", onCleared);

    // --- create the chroming marker track (async) ---
    const createSub = player.chroming.createMarkerTrack({}).subscribe({
      next: (trackApi) => {
        markerTrackApiRef.current = trackApi;

        // Flush all existing coordinator markers
        for (const m of markerAdapter.list()) {
          addToTrack(m);
        }

        // Flush any queued operations that arrived before the track was ready
        for (const op of pendingOps.current) {
          switch (op.type) {
            case "add": {
              const m = op.payload as MarkerApi;
              if (m?.id) addToTrack(m);
              break;
            }
            case "remove": {
              const p = op.payload as { id: string };
              if (p?.id) removeFromTrack(p.id);
              break;
            }
            case "update": {
              const m = op.payload as MarkerApi;
              if (m?.id) updateOnTrack(m);
              break;
            }
            case "clear":
              clearTrack();
              break;
          }
        }
        pendingOps.current = [];

        // Subscribe to track drag events
        const dragSub = trackApi.onMarkerUpdate$.subscribe({
          next: (event: MarkerUpdateEvent) => {
            const trackMarkerId = event.marker.id;
            const coordId = t2c.get(trackMarkerId);
            if (!coordId) return;

            const obs = event.marker.timeObservation;
            const start = "start" in obs ? obs.start : undefined;
            const end = "end" in obs ? obs.end : undefined;
            if (start == null || end == null) return;

            suppressTrackUpdate.current = true;
            try {
              markerAdapter.update(coordId, { timeObservation: { start, end } }, "track");
            } finally {
              suppressTrackUpdate.current = false;
            }
          },
        });
        subscriptions.push(dragSub);
      },
    });
    subscriptions.push(createSub);

    return () => {
      markerAdapter.off("MARKER_ADDED", onAdded);
      markerAdapter.off("MARKER_REMOVED", onRemoved);
      markerAdapter.off("MARKER_UPDATED", onUpdated);
      markerAdapter.off("MARKER_CLEARED", onCleared);
      subscriptions.forEach((s) => {
        try {
          s.unsubscribe();
        } catch {
          /* ok */
        }
      });
      if (markerTrackApiRef.current) {
        try {
          markerTrackApiRef.current.destroy();
        } catch {
          /* ok */
        }
        markerTrackApiRef.current = null;
      }
      c2t.clear();
      t2c.clear();
      pendingOps.current = [];
    };
  }, [playerRef, markerAdapter, isReady]);
}
