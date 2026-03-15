export type MarkerApi = {
  id: string;
  timeObservation: { start: number; end: number };
  label?: string;
  color?: string;
  score?: number;
  type?: "user" | "semantic";
};

export type MarkerSyncEnvelope = {
  id: string;
  revision: number;
  updatedAt: number;
  source: "track" | "sidebar";
  sessionId: string;
  pendingOpId?: string;
};

export type MarkerOperation = {
  opId: string;
  markerId: string;
  revision: number;
  sessionId: string;
  type: "add" | "update" | "remove";
};

export type SyncCoordinatorEvent =
  | "MARKER_ADDED"
  | "MARKER_REMOVED"
  | "MARKER_UPDATED"
  | "MARKER_CLEARED"
  | "MARKER_COMMIT_REQUESTED"
  | "MARKER_COMMIT_CONFIRMED"
  | "MARKER_COMMIT_FAILED_ROLLBACK_APPLIED"
  | "MARKER_PREVIEW_UPDATED"
  | "MARKER_SYSTEM_NOT_READY"
  | "STALE_ACK_IGNORED"
  | "SESSION_MISMATCH_IGNORED";

export interface DetailMarkerAdapter {
  list(): MarkerApi[];
  add(marker: Partial<MarkerApi>, source: "track" | "sidebar"): MarkerApi | undefined;
  update(
    id: string,
    patch: Partial<MarkerApi>,
    source: "track" | "sidebar",
    expectedRevision?: number
  ): void;
  remove(id: string, source: "track" | "sidebar", expectedRevision?: number): void;
  clear(source: "track" | "sidebar"): void;
  select(id: string): void;
  selected(): MarkerApi | undefined;
  preview(id: string, patch: Partial<MarkerApi>, source: "track" | "sidebar"): void;
  commit(id: string, source: "track" | "sidebar"): void;
  rollback(opId: string): void;
  isReady(): boolean;
  on(event: SyncCoordinatorEvent, handler: (payload?: unknown) => void): void;
  off(event: SyncCoordinatorEvent, handler: (payload?: unknown) => void): void;
}

export interface Clock {
  now(): number;
}

export interface IdGenerator {
  next(): string;
}

export interface StoragePort {
  load(assetId: string): MarkerSyncEnvelope[];
  save(assetId: string, envelopes: MarkerSyncEnvelope[]): void;
}
