/**
 * Local persistence for user-authored markers.
 *
 * Markers have no server-side home — there is no markers API and no markers
 * table — so authored markers live in `localStorage`, keyed by asset. This module
 * is the whole of that story.
 *
 * It replaces the persistence half of `MarkerSyncCoordinator`. The other half of
 * that class — revisions, envelopes, session ids, pending-op tracking, optimistic
 * commit/rollback — modelled concurrent writers against a shared store. With
 * `localStorage` there is exactly one writer per tab and no server to conflict
 * with, and none of `commit()`, `rollback()`, `acknowledgeCommit()` or
 * `failCommit()` had a production caller. So only the load/save survives.
 *
 * Semantic markers are deliberately NOT persisted: they are derived from clip
 * embeddings that already live in OpenSearch, and a stored copy would go stale
 * as soon as the embedding pipeline re-runs or the model version changes.
 */

/** One persisted user marker. Times are seconds. */
export interface PersistedMarker {
  startTime: number;
  endTime: number;
  label?: string;
  color?: string;
  createdAt?: number;
}

const storageKey = (assetId: string) => `markers:${assetId}`;

/** True when the value is a usable marker record. */
function isPersistedMarker(value: unknown): value is PersistedMarker {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<PersistedMarker>;
  return (
    typeof candidate.startTime === "number" &&
    Number.isFinite(candidate.startTime) &&
    typeof candidate.endTime === "number" &&
    Number.isFinite(candidate.endTime) &&
    candidate.endTime > candidate.startTime
  );
}

/**
 * Read the persisted user markers for an asset.
 *
 * Returns an empty array for anything unreadable rather than throwing: a corrupt
 * or hand-edited entry should cost the user their markers, not the whole detail
 * page. Records are validated individually so one bad entry does not discard the
 * rest.
 *
 * The stored shape changed with this module — the previous format was an array of
 * revision envelopes, which carried no times and is therefore filtered out here
 * as unusable. Older markers are dropped rather than migrated: they were
 * per-browser scratch data, and an envelope has no `startTime` to recover.
 */
export function loadMarkers(assetId: string): PersistedMarker[] {
  if (!assetId) return [];

  try {
    const raw = localStorage.getItem(storageKey(assetId));
    if (!raw) return [];

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isPersistedMarker);
  } catch {
    return [];
  }
}

/**
 * Write the user markers for an asset, replacing whatever was there.
 *
 * Writes synchronously. The implementation this replaces debounced by 100 ms and
 * never flushed on unmount, so the last edit before navigating away could be
 * lost; marker edits are infrequent and small enough that the debounce bought
 * nothing worth that.
 */
export function saveMarkers(assetId: string, markers: PersistedMarker[]): void {
  if (!assetId) return;

  try {
    if (markers.length === 0) {
      localStorage.removeItem(storageKey(assetId));
      return;
    }
    localStorage.setItem(storageKey(assetId), JSON.stringify(markers));
  } catch {
    // Quota exceeded or storage disabled — markers stay in memory for this
    // session. Failing the write must not break playback.
  }
}
