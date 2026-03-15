import type {
  MarkerApi,
  MarkerSyncEnvelope,
  MarkerOperation,
  SyncCoordinatorEvent,
  Clock,
  IdGenerator,
  StoragePort,
} from "./ports";

export class MarkerSyncCoordinator {
  private _envelopes = new Map<string, MarkerSyncEnvelope>();
  private _confirmed = new Map<string, MarkerSyncEnvelope>();
  private _markers = new Map<string, MarkerApi>();
  private _confirmedMarkers = new Map<string, MarkerApi>();
  private _ops = new Map<string, MarkerOperation>();
  private _listeners = new Map<SyncCoordinatorEvent, Set<(payload?: unknown) => void>>();
  private _ready = false;
  private _selectedId: string | null = null;
  private _sessionId: string;
  private _clock: Clock;
  private _idGenerator: IdGenerator;
  private _storage: StoragePort;
  private _assetId: string;

  constructor({
    clock,
    idGenerator,
    storage,
    assetId,
  }: {
    clock: Clock;
    idGenerator: IdGenerator;
    storage: StoragePort;
    assetId: string;
  }) {
    this._clock = clock;
    this._idGenerator = idGenerator;
    this._storage = storage;
    this._assetId = assetId;
    this._sessionId = idGenerator.next();

    const persisted = storage.load(assetId);
    for (const env of persisted) {
      this._envelopes.set(env.id, { ...env });
      this._confirmed.set(env.id, { ...env });
      // Reconstruct pending ops from persisted envelopes for session-remount detection
      if (env.pendingOpId) {
        this._ops.set(env.pendingOpId, {
          opId: env.pendingOpId,
          markerId: env.id,
          revision: env.revision,
          sessionId: env.sessionId,
          type: "update",
        });
      }
    }
  }

  setReady(ready: boolean): void {
    this._ready = ready;
  }

  isReady(): boolean {
    return this._ready;
  }

  on(event: SyncCoordinatorEvent, handler: (payload?: unknown) => void): void {
    let set = this._listeners.get(event);
    if (!set) {
      set = new Set();
      this._listeners.set(event, set);
    }
    set.add(handler);
  }

  off(event: SyncCoordinatorEvent, handler: (payload?: unknown) => void): void {
    this._listeners.get(event)?.delete(handler);
  }

  list(): MarkerApi[] {
    return Array.from(this._markers.values());
  }

  clear(source: "track" | "sidebar"): void {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }
    this._envelopes.clear();
    this._confirmed.clear();
    this._markers.clear();
    this._confirmedMarkers.clear();
    this._ops.clear();
    this._selectedId = null;
    this._persist();
    this._emit("MARKER_CLEARED");
  }

  select(id: string): void {
    this._selectedId = id;
  }

  selected(): MarkerApi | undefined {
    if (!this._selectedId) return undefined;
    return this._markers.get(this._selectedId);
  }

  rollback(opId: string): void {
    const op = this._ops.get(opId);
    if (!op) return;
    const confirmed = this._confirmed.get(op.markerId);
    if (confirmed) {
      this._envelopes.set(op.markerId, { ...confirmed });
    }
    // Restore confirmed marker snapshot
    const confirmedMarker = this._confirmedMarkers.get(op.markerId);
    if (confirmedMarker) {
      this._markers.set(op.markerId, { ...confirmedMarker });
    }
    this._ops.delete(opId);
    this._persist();
  }

  add(marker: Partial<MarkerApi>, source: "track" | "sidebar"): MarkerApi | undefined {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }

    const id =
      marker.type === "semantic" &&
      marker.timeObservation?.start != null &&
      marker.timeObservation?.end != null
        ? `clip-${marker.timeObservation.start}-${marker.timeObservation.end}-${this._assetId}`
        : this._idGenerator.next();

    const envelope: MarkerSyncEnvelope = {
      id,
      revision: 1,
      updatedAt: this._clock.now(),
      source,
      sessionId: this._sessionId,
    };

    const created: MarkerApi = {
      ...marker,
      id,
      timeObservation: marker.timeObservation ?? { start: 0, end: 0 },
    } as MarkerApi;

    this._envelopes.set(id, envelope);
    this._confirmed.set(id, { ...envelope });
    this._markers.set(id, created);
    this._confirmedMarkers.set(id, { ...created });
    this._persist();
    this._emit("MARKER_ADDED", created);

    return created;
  }

  update(
    id: string,
    patch: Partial<MarkerApi>,
    source: "track" | "sidebar",
    expectedRevision?: number
  ): void {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }

    const envelope = this._envelopes.get(id);
    if (!envelope) return;

    if (expectedRevision !== undefined && envelope.revision > expectedRevision) return;

    // Snapshot confirmed marker before mutation
    const currentMarker = this._markers.get(id);
    if (currentMarker && !this._confirmedMarkers.has(id)) {
      this._confirmedMarkers.set(id, { ...currentMarker });
    }

    // Apply patch optimistically
    if (currentMarker) {
      const updated = { ...currentMarker, ...patch, id };
      this._markers.set(id, updated);
      this._emit("MARKER_UPDATED", updated);
    }

    envelope.revision++;
    envelope.updatedAt = this._clock.now();
    envelope.source = source;

    const opId = this._idGenerator.next();
    envelope.pendingOpId = opId;

    const op: MarkerOperation = {
      opId,
      markerId: id,
      revision: envelope.revision,
      sessionId: this._sessionId,
      type: "update",
    };
    this._ops.set(opId, op);

    this._emit("MARKER_COMMIT_REQUESTED", { ...op, patch, source });
    this._persist();
  }

  preview(id: string, patch: Partial<MarkerApi>, source: "track" | "sidebar"): void {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }
    this._emit("MARKER_PREVIEW_UPDATED", { id, patch, source });
  }

  commit(id: string, source: "track" | "sidebar"): void {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }

    const envelope = this._envelopes.get(id);
    if (!envelope) return;

    envelope.revision++;
    envelope.updatedAt = this._clock.now();
    envelope.source = source;

    const opId = this._idGenerator.next();
    envelope.pendingOpId = opId;

    const op: MarkerOperation = {
      opId,
      markerId: id,
      revision: envelope.revision,
      sessionId: this._sessionId,
      type: "update",
    };
    this._ops.set(opId, op);

    this._emit("MARKER_COMMIT_REQUESTED", { ...op, source });
    this._persist();
  }

  remove(id: string, source: "track" | "sidebar", expectedRevision?: number): void {
    if (!this._ready) {
      this._emit("MARKER_SYSTEM_NOT_READY");
      return;
    }

    const envelope = this._envelopes.get(id);
    if (!envelope) return;

    if (expectedRevision !== undefined && envelope.revision > expectedRevision) return;

    this._envelopes.delete(id);
    this._confirmed.delete(id);
    this._markers.delete(id);
    this._confirmedMarkers.delete(id);
    this._persist();
    this._emit("MARKER_REMOVED", { id });
  }

  acknowledgeCommit(opId: string): void {
    const op = this._ops.get(opId);
    if (!op) return;

    if (op.sessionId !== this._sessionId) {
      this._emit("SESSION_MISMATCH_IGNORED", { opId });
      return;
    }

    const envelope = this._envelopes.get(op.markerId);
    if (!envelope) return;

    if (op.revision < envelope.revision) {
      this._emit("STALE_ACK_IGNORED", {
        opId,
        opRevision: op.revision,
        currentRevision: envelope.revision,
      });
      return;
    }

    this._confirmed.set(op.markerId, { ...envelope });
    const currentMarker = this._markers.get(op.markerId);
    if (currentMarker) {
      this._confirmedMarkers.set(op.markerId, { ...currentMarker });
    }
    delete envelope.pendingOpId;
    this._ops.delete(opId);
    this._emit("MARKER_COMMIT_CONFIRMED", { opId, markerId: op.markerId });
    this._persist();
  }

  failCommit(opId: string): void {
    const op = this._ops.get(opId);
    if (!op) return;

    const envelope = this._envelopes.get(op.markerId);
    if (!envelope) return;

    if (op.revision !== envelope.revision) return;

    const confirmed = this._confirmed.get(op.markerId);
    if (confirmed) {
      this._envelopes.set(op.markerId, { ...confirmed });
    }

    // Restore confirmed marker snapshot
    const confirmedMarker = this._confirmedMarkers.get(op.markerId);
    if (confirmedMarker) {
      this._markers.set(op.markerId, { ...confirmedMarker });
    }

    this._ops.delete(opId);
    this._emit("MARKER_COMMIT_FAILED_ROLLBACK_APPLIED", { opId, markerId: op.markerId });
    this._persist();
  }

  private _persistTimer: ReturnType<typeof setTimeout> | null = null;

  private _persist(): void {
    // Debounce localStorage writes to avoid blocking the main thread
    // during rapid operations (e.g., confidence slider dragging).
    if (this._persistTimer !== null) return;
    this._persistTimer = setTimeout(() => {
      this._persistTimer = null;
      this._storage.save(this._assetId, Array.from(this._envelopes.values()));
    }, 100);
  }

  /** Flush any pending persist immediately (call before teardown). */
  flushPersist(): void {
    if (this._persistTimer !== null) {
      clearTimeout(this._persistTimer);
      this._persistTimer = null;
      this._storage.save(this._assetId, Array.from(this._envelopes.values()));
    }
  }

  private _emit(event: SyncCoordinatorEvent, payload?: unknown): void {
    const handlers = this._listeners.get(event);
    if (handlers) {
      for (const handler of handlers) {
        handler(payload);
      }
    }
  }
}
