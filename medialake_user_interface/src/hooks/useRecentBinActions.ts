import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

/**
 * Most-recently-used store for the actions a user runs from the selection bin
 * (the right sidebar's "N items" panel).
 *
 * Two kinds of target are tracked:
 *   - `collection` — a collection the user added the selection to
 *   - `workflow`   — a manual-trigger pipeline the user ran against the selection
 *
 * The bin uses this for two things: the Quick Access row (top few entries across
 * both kinds) and the "recent" sections of the Workflow/Collection dropdowns.
 *
 * Names are cached alongside the id so a chip can render without refetching the
 * collection or pipeline list. A cached name can go stale (rename/delete); the
 * bin calls `forget` when acting on an entry fails, so a dead chip disappears
 * after the first failed click rather than lingering forever.
 *
 * Persistence: localStorage, zod-validated on read so a corrupted or
 * older-shaped blob degrades to "no recents" instead of throwing during render.
 */

const STORAGE_KEY = "medialake.binRecentActions.v1";

/** Hard cap on stored entries per kind. Keeps the blob small and reads cheap. */
const MAX_PER_KIND = 8;

export type RecentBinActionKind = "collection" | "workflow";

const entrySchema = z.object({
  kind: z.enum(["collection", "workflow"]),
  id: z.string().min(1),
  name: z.string().min(1),
  /** Epoch ms of the most recent use. Drives MRU ordering. */
  usedAt: z.number().finite().nonnegative(),
});

const storeSchema = z.array(entrySchema);

export type RecentBinAction = z.infer<typeof entrySchema>;

function readFromStorage(): RecentBinAction[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = storeSchema.safeParse(JSON.parse(raw));
    // Normalize on read as well as on write: a blob written by an older build
    // (or hand-edited) can be out of order or over the per-kind cap, and every
    // consumer relies on MRU-first ordering.
    return parsed.success ? normalize(parsed.data) : [];
  } catch {
    // Corrupted JSON, or storage unavailable (private mode / disabled).
    return [];
  }
}

function writeToStorage(entries: RecentBinAction[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Quota exceeded / private mode — recents degrade to in-memory only.
  }
}

/**
 * Module-level cache + subscriber set.
 *
 * Several bin instances can be mounted at once (each page renders its own
 * TabbedSidebar), and Quick Access must update the moment an action runs
 * anywhere. Sharing one in-memory copy keeps every consumer consistent without
 * a round trip through localStorage on each render.
 */
let cache: RecentBinAction[] | null = null;
const subscribers = new Set<(entries: RecentBinAction[]) => void>();

function getSnapshot(): RecentBinAction[] {
  if (cache === null) {
    cache = readFromStorage();
  }
  return cache;
}

function publish(next: RecentBinAction[]) {
  cache = next;
  writeToStorage(next);
  for (const notify of subscribers) {
    notify(next);
  }
}

/**
 * Sort MRU-first and keep at most MAX_PER_KIND entries of each kind.
 *
 * The sort is by `usedAt` descending and relies on `Array.prototype.sort` being
 * stable: several uses can land in the same millisecond, and in that case the
 * caller's ordering decides the winner. `recordUse` therefore puts the entry it
 * just recorded at the head so a same-millisecond tie can't evict it.
 */
function normalize(entries: RecentBinAction[]): RecentBinAction[] {
  const byKind = new Map<RecentBinActionKind, RecentBinAction[]>();
  for (const entry of [...entries].sort((a, b) => b.usedAt - a.usedAt)) {
    const bucket = byKind.get(entry.kind) ?? [];
    if (bucket.length < MAX_PER_KIND) {
      bucket.push(entry);
      byKind.set(entry.kind, bucket);
    }
  }
  return [...byKind.values()].flat().sort((a, b) => b.usedAt - a.usedAt);
}

/** Test-only: drop the in-memory cache so each test starts from storage. */
export function __resetRecentBinActionsCache() {
  cache = null;
}

export interface UseRecentBinActionsResult {
  /** Every remembered entry, most recently used first, both kinds interleaved. */
  recents: RecentBinAction[];
  /** Record a use, moving the entry to the front and refreshing its cached name. */
  recordUse: (kind: RecentBinActionKind, id: string, name: string) => void;
  /** Drop an entry — used when acting on it fails because it no longer exists. */
  forget: (kind: RecentBinActionKind, id: string) => void;
}

export function useRecentBinActions(): UseRecentBinActionsResult {
  const [recents, setRecents] = useState<RecentBinAction[]>(getSnapshot);

  useEffect(() => {
    const notify = (entries: RecentBinAction[]) => setRecents(entries);
    subscribers.add(notify);
    // Re-sync on mount: another instance may have published while unmounted.
    setRecents(getSnapshot());
    return () => {
      subscribers.delete(notify);
    };
  }, []);

  const recordUse = useCallback((kind: RecentBinActionKind, id: string, name: string) => {
    const trimmedId = id?.trim();
    const trimmedName = name?.trim();
    // Both are required by the schema; a blank name would render an empty chip.
    if (!trimmedId || !trimmedName) return;

    const current = getSnapshot();
    const without = current.filter((e) => !(e.kind === kind && e.id === trimmedId));
    // New entry first so a same-millisecond tie resolves in its favour.
    publish(
      normalize([{ kind, id: trimmedId, name: trimmedName, usedAt: Date.now() }, ...without])
    );
  }, []);

  const forget = useCallback((kind: RecentBinActionKind, id: string) => {
    const current = getSnapshot();
    const next = current.filter((e) => !(e.kind === kind && e.id === id));
    if (next.length !== current.length) {
      publish(next);
    }
  }, []);

  return { recents, recordUse, forget };
}
