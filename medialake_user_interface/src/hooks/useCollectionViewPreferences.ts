import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";

/**
 * Display preferences for the Collections list and sub-collections grid.
 *
 * Mirrors the Search page's `useMetadataFieldPreferences` pattern but targets a
 * smaller, fixed surface area: four presets, a handful of core toggles, a
 * user-editable list of `customMetadata` keys, and card size.
 *
 * Persistence: localStorage, debounced writes, zod-validated on read so future
 * field additions don't blow up saved prefs.
 */

const STORAGE_KEY = "medialake.collectionViewPrefs.v1";

export type CollectionCardPreset = "full" | "rich" | "compact" | "minimal" | "custom";

export type CollectionCardSize = "small" | "medium" | "large";

export interface CollectionCardDisplayPrefs {
  preset: CollectionCardPreset;
  cardSize: CollectionCardSize;
  showDescription: boolean;
  showTags: boolean;
  /** Item/sub counts + updated date */
  showMeta: boolean;
  showVisibility: boolean;
  /** Breadcrumb only renders when the caller passes `parentName`; this gates it */
  showParentBreadcrumb: boolean;
  /** Which customMetadata keys to render on cards, in order. Empty = none. */
  visibleMetadataKeys: string[];
  /** Soft cap in `rich`, hard cap otherwise. Keeps cards visually stable. */
  maxMetadataKeys: number;
  /**
   * Set to true once `visibleMetadataKeys` has been auto-seeded from the
   * tenant's metadata-keys endpoint. Survives reloads so we don't re-seed
   * after the user explicitly clears the list. Users who were early-adopters
   * (prefs saved before seeding landed) get re-seeded on their next visit
   * because the flag is absent for them.
   */
  metadataKeysInitialized?: boolean;
}

const prefsSchema = z.object({
  preset: z.enum(["full", "rich", "compact", "minimal", "custom"]),
  cardSize: z.enum(["small", "medium", "large"]),
  showDescription: z.boolean(),
  showTags: z.boolean(),
  showMeta: z.boolean(),
  showVisibility: z.boolean(),
  showParentBreadcrumb: z.boolean(),
  visibleMetadataKeys: z.array(z.string()),
  maxMetadataKeys: z.number().int().min(0).max(20),
  metadataKeysInitialized: z.boolean().optional(),
});

/**
 * Preset profiles. Applying a preset rewrites every toggle + the maxMetadataKeys
 * cap. `visibleMetadataKeys` is preserved across preset changes — users curate
 * the *set* of keys, presets control how *many* of them render.
 */
const PRESET_PROFILES: Record<
  Exclude<CollectionCardPreset, "custom">,
  Omit<CollectionCardDisplayPrefs, "preset" | "cardSize" | "visibleMetadataKeys">
> = {
  full: {
    showDescription: true,
    showTags: true,
    showMeta: true,
    showVisibility: true,
    showParentBreadcrumb: true,
    maxMetadataKeys: 20,
  },
  rich: {
    showDescription: true,
    showTags: true,
    showMeta: true,
    showVisibility: true,
    showParentBreadcrumb: true,
    maxMetadataKeys: 3,
  },
  compact: {
    showDescription: false,
    showTags: true,
    showMeta: true,
    showVisibility: true,
    showParentBreadcrumb: true,
    maxMetadataKeys: 0,
  },
  minimal: {
    showDescription: false,
    showTags: false,
    showMeta: false,
    // Visibility is rendered as a thumbnail corner dot in minimal, not as a chip.
    // Keep `showVisibility` true so the card still communicates the signal.
    showVisibility: true,
    showParentBreadcrumb: false,
    maxMetadataKeys: 0,
  },
};

export const DEFAULT_PREFS: CollectionCardDisplayPrefs = {
  preset: "rich",
  cardSize: "medium",
  ...PRESET_PROFILES.rich,
  visibleMetadataKeys: [],
};

function readFromStorage(): CollectionCardDisplayPrefs | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = prefsSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

function writeToStorage(prefs: CollectionCardDisplayPrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Quota exceeded / private mode — prefs degrade to in-memory only.
  }
}

/**
 * Compare a set of toggles against a preset profile. Used to keep the
 * `preset` field honest as the user flips individual checkboxes: if they hand-
 * edit back to a recognized profile, we re-label the preset accordingly.
 */
function inferPreset(prefs: Omit<CollectionCardDisplayPrefs, "preset">): CollectionCardPreset {
  for (const name of ["full", "rich", "compact", "minimal"] as const) {
    const p = PRESET_PROFILES[name];
    if (
      prefs.showDescription === p.showDescription &&
      prefs.showTags === p.showTags &&
      prefs.showMeta === p.showMeta &&
      prefs.showVisibility === p.showVisibility &&
      prefs.showParentBreadcrumb === p.showParentBreadcrumb &&
      prefs.maxMetadataKeys === p.maxMetadataKeys
    ) {
      return name;
    }
  }
  return "custom";
}

export type CollectionCoreFieldId =
  | "description"
  | "tags"
  | "meta"
  | "visibility"
  | "parentBreadcrumb";

const CORE_FIELD_TO_KEY: Record<CollectionCoreFieldId, keyof CollectionCardDisplayPrefs> = {
  description: "showDescription",
  tags: "showTags",
  meta: "showMeta",
  visibility: "showVisibility",
  parentBreadcrumb: "showParentBreadcrumb",
};

export interface UseCollectionViewPreferencesOptions {
  /**
   * Complete list of available custom-metadata keys for the tenant. When
   * provided and the user has no saved selection, the hook seeds
   * `visibleMetadataKeys` with the first 3 alphabetical entries so the metadata
   * strip is populated out-of-the-box. Pruning also runs: keys that no longer
   * exist are quietly dropped so cards never reference stale keys.
   */
  availableMetadataKeys?: string[];
  /** Upper bound for the auto-seed. Defaults to 3. */
  initialMetadataKeyCount?: number;
}

export interface UseCollectionViewPreferencesResult {
  prefs: CollectionCardDisplayPrefs;
  setPreset: (preset: Exclude<CollectionCardPreset, "custom">) => void;
  setCardSize: (size: CollectionCardSize) => void;
  toggleCoreField: (field: CollectionCoreFieldId) => void;
  setVisibleMetadataKeys: (keys: string[]) => void;
  toggleMetadataKey: (key: string) => void;
  /** Reset to the built-in defaults (preset=rich, size=medium, empty metadata keys) */
  reset: () => void;
}

export function useCollectionViewPreferences(
  options: UseCollectionViewPreferencesOptions = {}
): UseCollectionViewPreferencesResult {
  const { availableMetadataKeys, initialMetadataKeyCount = 3 } = options;

  const [prefs, setPrefs] = useState<CollectionCardDisplayPrefs>(
    () => readFromStorage() ?? DEFAULT_PREFS
  );

  // Track whether we've already seeded from availableMetadataKeys in-session.
  // The persistent flag is `prefs.metadataKeysInitialized` — kept in sync with
  // this ref. Seeding happens when:
  //   (a) the user has never been seeded before (`metadataKeysInitialized`
  //       is falsy), AND
  //   (b) `visibleMetadataKeys` is currently empty.
  // This heals users who saved prefs during the early rollout before seeding
  // was implemented correctly — their saved blob has no flag, so seeding runs
  // once on their next visit.
  const seededRef = useRef<boolean>(false);

  useEffect(() => {
    if (!availableMetadataKeys || availableMetadataKeys.length === 0) return;
    const availableSet = new Set(availableMetadataKeys);
    setPrefs((prev) => {
      // Prune keys that no longer exist in the tenant.
      const prunedVisible = prev.visibleMetadataKeys.filter((k) => availableSet.has(k));

      // One-time seed: fires when the user has never been seeded (persistent
      // flag absent or false) AND their visible list is currently empty.
      const needsSeed =
        !seededRef.current && !prev.metadataKeysInitialized && prunedVisible.length === 0;

      if (needsSeed) {
        seededRef.current = true;
        const seeded = [...availableMetadataKeys]
          .sort((a, b) => a.localeCompare(b))
          .slice(0, initialMetadataKeyCount);
        return {
          ...prev,
          visibleMetadataKeys: seeded,
          metadataKeysInitialized: true,
        };
      }

      // Flip the init flag on so we don't repeatedly re-check seeding
      // conditions on subsequent renders — prevents a re-seed if the user
      // deletes every key later and reloads.
      const needsInitFlag = !prev.metadataKeysInitialized;

      if (prunedVisible.length === prev.visibleMetadataKeys.length && !needsInitFlag) {
        return prev;
      }
      return {
        ...prev,
        visibleMetadataKeys: prunedVisible,
        metadataKeysInitialized: true,
      };
    });
  }, [availableMetadataKeys, initialMetadataKeyCount]);

  // Debounce localStorage writes so rapid toggles don't thrash disk.
  const writeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (writeTimer.current) clearTimeout(writeTimer.current);
    writeTimer.current = setTimeout(() => writeToStorage(prefs), 150);
    return () => {
      if (writeTimer.current) clearTimeout(writeTimer.current);
    };
  }, [prefs]);

  const setPreset = useCallback((preset: Exclude<CollectionCardPreset, "custom">) => {
    setPrefs((prev) => ({
      ...prev,
      preset,
      ...PRESET_PROFILES[preset],
    }));
  }, []);

  const setCardSize = useCallback((cardSize: CollectionCardSize) => {
    setPrefs((prev) => ({ ...prev, cardSize }));
  }, []);

  const toggleCoreField = useCallback((field: CollectionCoreFieldId) => {
    setPrefs((prev) => {
      const key = CORE_FIELD_TO_KEY[field];
      const next = { ...prev, [key]: !prev[key] } as CollectionCardDisplayPrefs;
      next.preset = inferPreset(next);
      return next;
    });
  }, []);

  const setVisibleMetadataKeys = useCallback((keys: string[]) => {
    setPrefs((prev) => ({
      ...prev,
      visibleMetadataKeys: keys,
    }));
  }, []);

  const toggleMetadataKey = useCallback((key: string) => {
    setPrefs((prev) => {
      const has = prev.visibleMetadataKeys.includes(key);
      const next = has
        ? prev.visibleMetadataKeys.filter((k) => k !== key)
        : [...prev.visibleMetadataKeys, key];
      return { ...prev, visibleMetadataKeys: next };
    });
  }, []);

  const reset = useCallback(() => {
    setPrefs(DEFAULT_PREFS);
  }, []);

  // Stable reference for the metadata keys array so consumers can memoize cheaply.
  const stableKeys = useMemo(
    () => prefs.visibleMetadataKeys,
    // The join creates a stable string key so the memo only updates when array content changes
    [prefs.visibleMetadataKeys.join("\0")]
  );

  const finalPrefs = useMemo<CollectionCardDisplayPrefs>(
    () => ({ ...prefs, visibleMetadataKeys: stableKeys }),
    [prefs, stableKeys]
  );

  return {
    prefs: finalPrefs,
    setPreset,
    setCardSize,
    toggleCoreField,
    setVisibleMetadataKeys,
    toggleMetadataKey,
    reset,
  };
}
