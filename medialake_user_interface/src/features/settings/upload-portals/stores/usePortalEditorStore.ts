import { create } from "zustand";
import { persist, type PersistStorage, type StorageValue } from "zustand/middleware";

import type {
  CreatePortalRequest,
  Portal,
  PortalDestination,
  PortalMetadataField,
} from "@/api/types/api.types";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import { portalAppearanceSchema } from "../schemas/appearance.schema";
import type {
  PortalAppearance,
  PortalAppearanceBranding,
  PortalAppearanceColors,
  PortalAppearanceContent,
  PortalAppearanceLayout,
  PortalAppearanceTypography,
} from "../types/appearance.types";
import { deepMerge } from "../utils/deepMerge";

/**
 * Local typed wrapper around {@link deepMerge}.
 *
 * `deepMerge` is constrained to `T extends Record<string, unknown>`, which
 * does not accept TypeScript interfaces (interfaces are not assignable to
 * index-signature types). The `PortalAppearance` sub-shapes we merge here are
 * declared as interfaces in `appearance.types.ts`, so we cast through
 * `Record<string, unknown>` at the boundary. Runtime behavior is identical —
 * `deepMerge` only relies on `Object.keys` and `isPlainObject` at runtime, not
 * on any index-signature contract.
 */
const mergeInto = <T extends object>(target: T, source: Partial<T>): T =>
  deepMerge(
    target as unknown as Record<string, unknown>,
    source as unknown as Partial<Record<string, unknown>>
  ) as unknown as T;

/**
 * A single validation error with the field it belongs to and a human-readable
 * message explaining what's wrong and how to fix it.
 */
export interface ValidationError {
  /** Identifier for the specific field (e.g. "slug", "name", "destinations"). */
  field: string;
  /** Human-readable error message shown to the user. */
  message: string;
}

/**
 * Accordion sections rendered in the portal editor sidebar.
 *
 * The order here mirrors the sidebar rendering order defined in design.md:
 * Branding → Content → Appearance → Typography → Layout → Access Control
 * → Destinations → Metadata & Limits.
 */
export type EditorSection =
  | "branding"
  | "content"
  | "appearance"
  | "typography"
  | "layout"
  | "access"
  | "destinations"
  | "metadata";

/**
 * Responsive preview frame device modes rendered by the preview panel.
 */
export type PreviewMode = "desktop" | "tablet" | "mobile";

/**
 * Placeholder shape for the portal data slice held by the editor store.
 *
 * Phase 1 intentionally keeps this loose. The full shape (metadata fields,
 * destinations, access control, etc.) is introduced in later phases when the
 * settings sections are migrated into the editor. The index signature lets
 * those phases extend the object without forcing churn here.
 *
 * `initialize` accepts either this loose shape or a real {@link Portal} (edit
 * mode); both are compatible because `Portal` satisfies the `appearance?`
 * optionality this interface allows.
 */
export interface PortalEditorPortalData {
  portalId?: string;
  name?: string;
  slug?: string;
  /**
   * Resolved URL (or S3 key) for the currently saved portal logo. Cleared by
   * {@link PortalEditorState.clearLogo} and replaced by
   * {@link PortalEditorState.updateLogoUrl} after a successful upload.
   */
  logoUrl?: string;
  /**
   * Raw `File` selected in create mode before a `portalId` exists. The save
   * flow (task 5.8) consumes this to perform a deferred logo upload once the
   * portal has been created. Always `null` in edit mode where the upload
   * happens immediately via {@link useUploadPortalLogo}.
   */
  logoFile?: File | null;
  appearance?: PortalAppearance;
  /**
   * Allowed file types for uploads. Empty array means "accept all".
   * Each entry is a MIME pattern (e.g. "image/*") or extension (".pdf").
   */
  allowedFileTypes?: string[];
  [key: string]: unknown;
}

/**
 * Zustand store state + actions for the portal visual editor.
 *
 * Phase 1 scaffolding only. Validation (`validate`), payload serialization
 * (`getPayload`), and `persist` middleware are layered on in later phases
 * (see tasks 5.6 and 5.16).
 */
interface PortalEditorState {
  // Domain slices
  portalData: PortalEditorPortalData | null;
  appearance: PortalAppearance;

  // History for undo/redo (NOT persisted)
  history: PortalAppearance[];
  historyIndex: number;

  // Lifecycle flags
  isDirty: boolean;
  isSaving: boolean;
  isInitialized: boolean;

  /**
   * `true` when the store was rehydrated from a persisted draft in
   * `localStorage` on mount — i.e. the last session ended without a
   * successful save. Consumers (e.g. `PortalEditorPage`) render a
   * non-blocking "Restored unsaved changes from your last session." banner
   * while this flag is set (Requirement 14.7).
   *
   * This flag is NEVER persisted itself (it's excluded from `partialize`);
   * it's a per-mount derived signal flipped on by the `persist`
   * middleware's `onRehydrateStorage` callback when a non-empty draft is
   * found, and flipped off by {@link PortalEditorState.acknowledgeRestoredDraft},
   * {@link PortalEditorState.initialize}, {@link PortalEditorState.reset},
   * or {@link PortalEditorState.markClean}.
   */
  hasRestoredDraft: boolean;

  // UI slices
  activeSection: EditorSection;
  previewMode: PreviewMode;

  // Validation
  validationErrors: Partial<Record<EditorSection, ValidationError[]>>;

  // Lifecycle actions
  initialize: (portal?: PortalEditorPortalData | Portal) => void;
  reset: () => void;
  markClean: () => void;
  setSaving: (isSaving: boolean) => void;

  /**
   * Dismiss the "Restored unsaved changes" banner by clearing the
   * {@link PortalEditorState.hasRestoredDraft} flag. Does NOT touch the
   * persisted draft in storage — the draft continues to auto-persist on
   * further edits and is only cleared by `markClean()` (successful save)
   * or `reset()`.
   */
  acknowledgeRestoredDraft: () => void;

  // UI actions
  setActiveSection: (section: EditorSection) => void;
  setPreviewMode: (mode: PreviewMode) => void;

  // Appearance actions
  updateAppearance: (partial: Partial<PortalAppearance>) => void;
  updateColor: (key: keyof PortalAppearanceColors, value: string) => void;
  updateTypography: (patch: Partial<PortalAppearanceTypography>) => void;
  updateLayout: (patch: Partial<PortalAppearanceLayout>) => void;
  updateBranding: (patch: Partial<PortalAppearanceBranding>) => void;
  updateContent: (patch: Partial<PortalAppearanceContent>) => void;
  resetAppearanceToDefaults: () => void;

  // Undo/Redo actions
  undo: () => void;
  redo: () => void;

  // Portal data actions (task 3.7 / 3.8 / 5.2-5.5)
  /**
   * Merge a partial patch into `portalData`. Used by the Access Control,
   * Destinations, and Metadata sections to update multi-field slices in a
   * single action. Marks the store dirty.
   */
  updatePortalData: (patch: Partial<PortalEditorPortalData>) => void;
  /**
   * Update the portal slug stored on {@link PortalEditorState.portalData}.
   * Marks the store dirty. Slugification is the caller's responsibility —
   * this action stores the value verbatim.
   */
  updateSlug: (slug: string) => void;
  /**
   * Set the resolved logo URL (or S3 key) on `portalData`. Called in edit
   * mode after a successful {@link useUploadPortalLogo} response. Pass
   * `undefined` to clear without touching `logoFile`. Marks the store dirty.
   */
  updateLogoUrl: (url: string | undefined) => void;
  /**
   * Stash a raw `File` for deferred upload in create mode, or clear the
   * stashed file with `null`. Marks the store dirty so the save flow knows
   * a logo upload is pending.
   */
  setLogoFile: (file: File | null) => void;
  /**
   * Clear both `portalData.logoUrl` and `portalData.logoFile` at once. Used
   * by the "Remove logo" button in {@link BrandingSection}. Marks the store
   * dirty.
   */
  clearLogo: () => void;

  // Validation actions
  clearSectionErrors: (section: EditorSection) => void;

  /**
   * Validate the current store state. Runs
   * {@link portalAppearanceSchema} against `state.appearance` and checks
   * `portalData` invariants (non-empty `name`, slug present and matching
   * the portal slug pattern, at least one destination). Populates
   * `state.validationErrors` keyed by {@link EditorSection} and returns
   * `true` when every check passes, `false` otherwise.
   *
   * The return value is the boolean gate the Save/Publish handlers in
   * `PortalEditorPage` check before calling the mutation — failure is a
   * pure state-level signal that no network request should fire.
   */
  validate: () => boolean;

  /**
   * Build the server-bound payload for a Create/Update request.
   *
   * - Combines `portalData` and `appearance` into a
   *   {@link CreatePortalRequest}-shaped object.
   * - Strips the client-only `logoFile` (uploaded separately by the save
   *   handler).
   * - Emits no `contentFormat` field — that concept was removed when the
   *   visual editor became the only content-authoring surface.
   * - Fills sensible defaults for fields the backend treats as required
   *   (`accessMode`, `destinations`, `metadataFields`).
   * - Includes `logoUrl` only when truthy.
   * - The returned object is JSON-serializable; the save flow relies on
   *   this to persist drafts and to hand payloads to `apiClient.post/put`.
   */
  getPayload: () => CreatePortalRequest;
}

/**
 * Sections whose errors are cleared by `resetAppearanceToDefaults`. Kept as a
 * module-level constant so the set is easy to audit and stays in sync with the
 * appearance-related `update*` actions above.
 */
const APPEARANCE_SECTIONS: readonly EditorSection[] = [
  "appearance",
  "typography",
  "layout",
  "branding",
  "content",
] as const;

/**
 * Route a Zod `issue.path` under `portalAppearanceSchema` to the editor
 * section that owns that field. The design doc pins this mapping:
 *
 *   - `appearance.typography.*`  → `"typography"`
 *   - `appearance.layout.*`      → `"layout"`
 *   - `appearance.branding.*`    → `"branding"`
 *   - `appearance.content.*`     → `"content"`
 *   - `appearance.colors.*`      → `"appearance"` (the Appearance
 *                                  sidebar accordion owns the color
 *                                  pickers)
 *   - anything else (including `appearance.mode` and the top-level
 *     object itself) → `"appearance"` as a safe default.
 *
 * The argument is Zod's `issue.path`, which starts at the root of
 * whatever object was parsed — in our case, `state.appearance`. So
 * `path[0]` is the first *sub-slice* key (`"typography"`, `"layout"`,
 * etc.), not the literal string `"appearance"`.
 */
const mapAppearancePathToSection = (path: ReadonlyArray<PropertyKey>): EditorSection => {
  const head = path[0];
  if (head === "typography") return "typography";
  if (head === "layout") return "layout";
  if (head === "branding") return "branding";
  if (head === "content") return "content";
  return "appearance";
};

const createInitialState = () => ({
  portalData: null as PortalEditorPortalData | null,
  appearance: structuredClone(DEFAULT_PORTAL_APPEARANCE),
  history: [] as PortalAppearance[],
  historyIndex: -1,
  isDirty: false,
  isSaving: false,
  isInitialized: false,
  hasRestoredDraft: false,
  activeSection: "branding" as EditorSection,
  previewMode: "desktop" as PreviewMode,
  validationErrors: {} as Partial<Record<EditorSection, ValidationError[]>>,
});

/**
 * `localStorage` key under which the editor draft is persisted.
 *
 * The key is intentionally STATIC (not scoped to a specific `portalId`).
 * Zustand's `persist` middleware takes `name` at store-creation time; a
 * dynamic-per-portal key would require `persist.setOptions({ name })`
 * plumbing at every editor mount and would still share a single store
 * instance in memory. A static key sidesteps that complexity and still
 * satisfies Requirement 14.1 (draft exists for crash recovery).
 *
 * To keep drafts from one portal leaking into the editor of another, the
 * consumer (`PortalEditorPage`) compares the rehydrated
 * `state.portalData?.portalId` against the portal it is about to load and
 * either keeps the draft (same portal) or calls `initialize(portal)` to
 * overwrite it (different portal). The draft is also cleared on successful
 * save via {@link PortalEditorState.markClean}.
 */
const PERSIST_STORAGE_KEY = "portal-editor-draft";

/**
 * Trailing-edge debounce window before an in-memory write is flushed to
 * `localStorage`. Requirement 14.3 pins this at 5 seconds so rapid-fire
 * edits (slider drags, typing) do not thrash storage.
 */
const PERSIST_DEBOUNCE_MS = 5_000;

/**
 * The subset of {@link PortalEditorState} we hand to `persist`. Excludes
 * UI/lifecycle flags, validation errors, and the transient `logoFile`
 * (a `File` is not JSON-serializable and must never land in storage
 * anyway — Requirements 14.4, 14.5).
 */
type PersistedEditorSlice = {
  portalData: PortalEditorPortalData | null;
  appearance: PortalAppearance;
};

/**
 * `PersistStorage<T>` adapter around `window.localStorage` that debounces
 * writes at {@link PERSIST_DEBOUNCE_MS} and fails soft when storage is
 * unavailable (Requirement 14.8).
 *
 * - `getItem` flushes any pending write before reading so in-tab
 *   round-trips are consistent.
 * - `setItem` coalesces consecutive writes by keeping only the most
 *   recent value and scheduling a single trailing flush.
 * - `removeItem` cancels any pending write and deletes the key
 *   immediately (used by `persist.clearStorage()` from `markClean` /
 *   `reset`).
 *
 * All three methods swallow exceptions — `localStorage` may throw on
 * quota exceeded, privacy-mode profiles, or SSR environments, and the
 * editor must continue functioning in those cases.
 */
const createDebouncedLocalStorage = <T>(): PersistStorage<T> => {
  let pendingTimer: ReturnType<typeof setTimeout> | null = null;
  let pendingWrite: { name: string; value: StorageValue<T> } | null = null;

  const flushNow = () => {
    const write = pendingWrite;
    pendingWrite = null;
    pendingTimer = null;
    if (!write) return;
    try {
      if (typeof window === "undefined") return;
      window.localStorage.setItem(write.name, JSON.stringify(write.value));
    } catch {
      // `localStorage` may be unavailable (privacy mode, quota exceeded,
      // SSR). Fail soft — dropping the write is preferable to throwing
      // out of a user-initiated store update.
    }
  };

  const cancelPending = () => {
    if (pendingTimer !== null) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    pendingWrite = null;
  };

  return {
    getItem: (name) => {
      // Flush any pending write synchronously so a read after a write in
      // the same tick observes the just-written value.
      if (pendingWrite && pendingWrite.name === name) {
        const value = pendingWrite.value;
        cancelPending();
        try {
          if (typeof window !== "undefined") {
            window.localStorage.setItem(name, JSON.stringify(value));
          }
        } catch {
          // fall through to the read below — even if we couldn't
          // write-back, the in-memory `value` is still correct.
        }
        return value;
      }
      try {
        if (typeof window === "undefined") return null;
        const raw = window.localStorage.getItem(name);
        if (raw === null) return null;
        return JSON.parse(raw) as StorageValue<T>;
      } catch {
        // Corrupt JSON or storage error — treat as "no draft" so
        // `persist` falls back to the initial state (Requirement 14.8).
        return null;
      }
    },
    setItem: (name, value) => {
      pendingWrite = { name, value };
      if (pendingTimer !== null) {
        clearTimeout(pendingTimer);
      }
      pendingTimer = setTimeout(flushNow, PERSIST_DEBOUNCE_MS);
    },
    removeItem: (name) => {
      // Drop any pending write for this key before we clear storage so a
      // late flush doesn't resurrect a just-cleared draft.
      if (pendingWrite && pendingWrite.name === name) {
        cancelPending();
      }
      try {
        if (typeof window === "undefined") return;
        window.localStorage.removeItem(name);
      } catch {
        // ignore
      }
    },
  };
};

/**
 * Maximum number of history entries for undo/redo. Older entries are
 * dropped when the stack exceeds this limit.
 */
const MAX_HISTORY_SIZE = 50;

export const usePortalEditorStore = create<PortalEditorState>()(
  persist<PortalEditorState, [], [], PersistedEditorSlice>(
    (set, get) => {
      /**
       * Push a new appearance snapshot onto the history stack. Called by
       * every `update*` action AFTER applying the change. Truncates any
       * redo entries beyond the current index and caps at MAX_HISTORY_SIZE.
       *
       * Model: `history[historyIndex]` is always the current appearance.
       * On first call, seeds history with the snapshot. Subsequent calls
       * truncate redo entries and append.
       */
      const pushToHistory = (newAppearance: PortalAppearance) => {
        const state = get();
        if (state.history.length === 0) {
          // First change: seed with the original + new state
          // We don't have the original anymore, so just start tracking from now
          set({
            history: [structuredClone(newAppearance)],
            historyIndex: 0,
          });
          return;
        }
        // Truncate any redo entries beyond the current position
        const truncated = state.history.slice(0, state.historyIndex + 1);
        const next = [...truncated, structuredClone(newAppearance)];
        // Cap at MAX_HISTORY_SIZE by dropping the oldest entries
        if (next.length > MAX_HISTORY_SIZE) {
          const excess = next.length - MAX_HISTORY_SIZE;
          set({
            history: next.slice(excess),
            historyIndex: MAX_HISTORY_SIZE - 1,
          });
        } else {
          set({
            history: next,
            historyIndex: next.length - 1,
          });
        }
      };

      /**
       * Seed the history with the initial appearance so undo can return to it.
       * Called once when the first edit happens (lazy initialization).
       */
      const ensureHistorySeeded = () => {
        const state = get();
        if (state.history.length === 0) {
          // Seed with the current (pre-change) appearance
          set({
            history: [structuredClone(state.appearance)],
            historyIndex: 0,
          });
        }
      };

      return {
        ...createInitialState(),

        initialize: (portal) =>
          set({
            portalData: (portal ?? null) as PortalEditorPortalData | null,
            appearance: portal?.appearance
              ? mergeInto(structuredClone(DEFAULT_PORTAL_APPEARANCE), portal.appearance)
              : structuredClone(DEFAULT_PORTAL_APPEARANCE),
            isDirty: false,
            isInitialized: true,
            hasRestoredDraft: false,
            validationErrors: {},
            history: [],
            historyIndex: -1,
          }),

        reset: () => {
          set(createInitialState());
          // Clear the persisted draft so tests and "start over" flows don't
          // accidentally re-hydrate stale state on the next store read.
          // `clearStorage` is added to the store by the `persist` middleware;
          // wrap in try/catch because the method can throw if storage is
          // unavailable (Requirement 14.8).
          try {
            usePortalEditorStore.persist.clearStorage();
          } catch {
            // ignore — clearing storage is best-effort.
          }
        },

        markClean: () => {
          set({ isDirty: false, hasRestoredDraft: false });
          // Requirement 14.6: once a save succeeds, the persisted draft is no
          // longer needed. Clearing it here (rather than in the save handler)
          // keeps the concern co-located with the "we're clean now" semantics
          // and means any code path that transitions the store to clean also
          // clears the draft.
          try {
            usePortalEditorStore.persist.clearStorage();
          } catch {
            // ignore
          }
        },

        setSaving: (isSaving) => set({ isSaving }),

        acknowledgeRestoredDraft: () => set({ hasRestoredDraft: false }),

        // Undo/Redo — snapshot-based model.
        // `history` stores appearance snapshots. `historyIndex` points to the
        // last pushed snapshot. pushHistory() saves the current appearance
        // before a change. undo() restores the snapshot at historyIndex and
        // decrements. redo() increments and restores.
        undo: () => {
          const state = get();
          if (state.historyIndex <= 0) return;
          const newIndex = state.historyIndex - 1;
          set({
            appearance: structuredClone(state.history[newIndex]),
            historyIndex: newIndex,
            isDirty: true,
          });
        },

        redo: () => {
          const state = get();
          if (state.historyIndex >= state.history.length - 1) return;
          const newIndex = state.historyIndex + 1;
          set({
            appearance: structuredClone(state.history[newIndex]),
            historyIndex: newIndex,
            isDirty: true,
          });
        },

        setActiveSection: (section) => set({ activeSection: section }),

        setPreviewMode: (mode) => set({ previewMode: mode }),

        updateAppearance: (partial) => {
          ensureHistorySeeded();
          const newAppearance = mergeInto(get().appearance, partial);
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
        },

        updateColor: (key, value) => {
          ensureHistorySeeded();
          const state = get();
          const newAppearance = {
            ...state.appearance,
            colors: { ...state.appearance.colors, [key]: value },
          };
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
          get().clearSectionErrors("appearance");
        },

        updateTypography: (patch) => {
          ensureHistorySeeded();
          const state = get();
          const newAppearance = {
            ...state.appearance,
            typography: mergeInto(state.appearance.typography, patch),
          };
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
          get().clearSectionErrors("typography");
        },

        updateLayout: (patch) => {
          ensureHistorySeeded();
          const state = get();
          const newAppearance = {
            ...state.appearance,
            layout: mergeInto(state.appearance.layout, patch),
          };
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
          get().clearSectionErrors("layout");
        },

        updateBranding: (patch) => {
          ensureHistorySeeded();
          const state = get();
          const newAppearance = {
            ...state.appearance,
            branding: mergeInto(state.appearance.branding, patch),
          };
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
          get().clearSectionErrors("branding");
        },

        updateContent: (patch) => {
          ensureHistorySeeded();
          const state = get();
          const newAppearance = {
            ...state.appearance,
            content: mergeInto(state.appearance.content, patch),
          };
          set({ appearance: newAppearance, isDirty: true });
          pushToHistory(newAppearance);
          get().clearSectionErrors("content");
        },

        resetAppearanceToDefaults: () => {
          ensureHistorySeeded();
          const state = get();
          const nextErrors: Partial<Record<EditorSection, ValidationError[]>> = {
            ...state.validationErrors,
          };
          for (const section of APPEARANCE_SECTIONS) {
            delete nextErrors[section];
          }
          const newAppearance = structuredClone(DEFAULT_PORTAL_APPEARANCE);
          set({
            appearance: newAppearance,
            isDirty: true,
            validationErrors: nextErrors,
          });
          pushToHistory(newAppearance);
        },

        updateSlug: (slug) =>
          set((state) => ({
            // `portalData` is `null` until `initialize` has run. Creating an
            // empty object here keeps `updateSlug` usable in create mode before
            // the first real portal payload lands in the store.
            portalData: { ...(state.portalData ?? {}), slug },
            isDirty: true,
          })),

        updatePortalData: (patch) =>
          set((state) => ({
            portalData: { ...(state.portalData ?? {}), ...patch },
            isDirty: true,
          })),

        updateLogoUrl: (url) =>
          set((state) => ({
            portalData: { ...(state.portalData ?? {}), logoUrl: url },
            isDirty: true,
          })),

        setLogoFile: (file) =>
          set((state) => ({
            portalData: { ...(state.portalData ?? {}), logoFile: file },
            isDirty: true,
          })),

        clearLogo: () =>
          set((state) => ({
            // Clear both slots in one write so the save flow and the UI always
            // observe a consistent "no logo" state. We intentionally set the
            // fields to `undefined`/`null` rather than delete them so TypeScript
            // sees the keys as explicitly cleared.
            portalData: {
              ...(state.portalData ?? {}),
              logoUrl: undefined,
              logoFile: null,
            },
            isDirty: true,
          })),

        clearSectionErrors: (section) =>
          set((state) => {
            if (!(section in state.validationErrors)) {
              return {};
            }
            const { [section]: _omit, ...rest } = state.validationErrors;
            return { validationErrors: rest };
          }),

        validate: () => {
          const state = get();
          const errors: Partial<Record<EditorSection, ValidationError[]>> = {};
          const pushError = (section: EditorSection, field: string, message: string) => {
            const bucket = errors[section] ?? [];
            bucket.push({ field, message });
            errors[section] = bucket;
          };

          // ---- 1. Appearance schema --------------------------------------------
          const appearanceResult = portalAppearanceSchema.safeParse(state.appearance);
          if (!appearanceResult.success) {
            for (const issue of appearanceResult.error.issues) {
              const section = mapAppearancePathToSection(issue.path);
              const field = issue.path.length > 0 ? String(issue.path[issue.path.length - 1]) : "unknown";
              pushError(section, field, issue.message);
            }
          }

          // ---- 2. portalData invariants ---------------------------------------
          const portal = state.portalData ?? {};
          const name = typeof portal.name === "string" ? portal.name.trim() : "";
          if (name.length === 0) {
            pushError("content", "name", "Portal name is required. Enter a name for your portal.");
          }

          const slug = typeof portal.slug === "string" ? portal.slug : "";
          if (slug.length === 0) {
            pushError("content", "slug", "Portal slug is required. Enter a URL-friendly identifier (e.g. \"my-portal\").");
          } else if (!/^[a-z0-9-]+$/.test(slug)) {
            pushError("content", "slug", "Slug must contain only lowercase letters, numbers, and hyphens (e.g. \"my-portal-2024\").");
          }

          const destinations = Array.isArray(portal.destinations)
            ? (portal.destinations as PortalDestination[])
            : [];
          if (destinations.length === 0) {
            pushError("destinations", "destinations", "At least one destination is required. Add a collection or folder where uploaded files will be stored.");
          }

          set({ validationErrors: errors });
          return Object.keys(errors).length === 0;
        },

        getPayload: () => {
          const state = get();
          const portal = state.portalData ?? {};

          // Every field we deliberately include is read through a local
          // variable so the final object literal is easy to scan. Anything not
          // copied here is intentionally dropped from the payload — in
          // particular `logoFile` (client-only) and `contentFormat` (removed).
          const name = typeof portal.name === "string" ? portal.name : "";
          const slug = typeof portal.slug === "string" ? portal.slug : "";
          const description =
            typeof portal.description === "string" ? portal.description : undefined;
          const accessMode =
            (portal.accessMode as CreatePortalRequest["accessMode"] | undefined) ?? "public";
          const destinations = Array.isArray(portal.destinations)
            ? (portal.destinations as PortalDestination[])
            : [];
          const metadataFields = Array.isArray(portal.metadataFields)
            ? (portal.metadataFields as PortalMetadataField[])
            : [];
          const allowedGroups = Array.isArray(portal.allowedGroups)
            ? (portal.allowedGroups as string[])
            : undefined;
          const ipAllowlist = Array.isArray(portal.ipAllowlist)
            ? (portal.ipAllowlist as string[])
            : undefined;
          const passphrase = typeof portal.passphrase === "string" ? portal.passphrase : undefined;
          const tokenBypassesPassphrase =
            typeof portal.tokenBypassesPassphrase === "boolean"
              ? portal.tokenBypassesPassphrase
              : undefined;
          const structuredPathMode =
            typeof portal.structuredPathMode === "boolean" ? portal.structuredPathMode : undefined;
          const captchaEnabled =
            typeof portal.captchaEnabled === "boolean" ? portal.captchaEnabled : undefined;
          const isActive = typeof portal.isActive === "boolean" ? portal.isActive : undefined;
          const expiresAt = typeof portal.expiresAt === "string" ? portal.expiresAt : undefined;
          const maxFileSizeBytes =
            typeof portal.maxFileSizeBytes === "number" ? portal.maxFileSizeBytes : undefined;
          const maxFilesPerSession =
            typeof portal.maxFilesPerSession === "number" ? portal.maxFilesPerSession : undefined;
          const logoUrl =
            typeof portal.logoUrl === "string" && portal.logoUrl ? portal.logoUrl : undefined;
          const allowedFileTypes = Array.isArray(portal.allowedFileTypes)
            ? (portal.allowedFileTypes as string[])
            : undefined;

          const payload: CreatePortalRequest = {
            name,
            slug,
            accessMode,
            destinations,
            metadataFields,
            appearance: state.appearance,
          };

          if (description !== undefined) payload.description = description;
          if (allowedGroups !== undefined) payload.allowedGroups = allowedGroups;
          if (passphrase !== undefined) payload.passphrase = passphrase;
          if (tokenBypassesPassphrase !== undefined) {
            payload.tokenBypassesPassphrase = tokenBypassesPassphrase;
          }
          if (ipAllowlist !== undefined) payload.ipAllowlist = ipAllowlist;
          if (structuredPathMode !== undefined) {
            payload.structuredPathMode = structuredPathMode;
          }
          if (captchaEnabled !== undefined) payload.captchaEnabled = captchaEnabled;
          if (isActive !== undefined) payload.isActive = isActive;
          if (expiresAt !== undefined) payload.expiresAt = expiresAt;
          if (maxFileSizeBytes !== undefined) {
            payload.maxFileSizeBytes = maxFileSizeBytes;
          }
          if (maxFilesPerSession !== undefined) {
            payload.maxFilesPerSession = maxFilesPerSession;
          }
          if (logoUrl !== undefined) payload.logoUrl = logoUrl;
          if (allowedFileTypes !== undefined && allowedFileTypes.length > 0) {
            payload.allowedFileTypes = allowedFileTypes;
          }

          return payload;
        },
      };
    },
    {
      name: PERSIST_STORAGE_KEY,
      // Custom debounced storage adapter: trailing-edge `setItem` debounce
      // at 5 s (Requirement 14.3), synchronous `getItem`, fail-soft on
      // `localStorage` unavailability (Requirement 14.8). The storage
      // handles its own JSON serialization, so we don't layer
      // `createJSONStorage` on top — that helper only adds JSON over a
      // `string`-based backend and we're already going direct.
      storage: createDebouncedLocalStorage<PersistedEditorSlice>(),
      // Requirements 14.4 & 14.5: persist only `portalData` and
      // `appearance`. Explicitly exclude `logoFile` (a non-serializable
      // `File`), `isSaving`, `validationErrors`, `activeSection`,
      // `previewMode`, `isDirty`, `isInitialized`, and `hasRestoredDraft`.
      partialize: (state) => ({
        portalData:
          state.portalData === null
            ? null
            : {
                ...state.portalData,
                // `File` objects aren't JSON-serializable. Drop them on
                // the way to storage; the user can re-pick the file
                // after hydration if needed.
                logoFile: null,
              },
        appearance: state.appearance,
      }),
      // Flip `hasRestoredDraft` on when a non-empty draft rehydrated so
      // `PortalEditorPage` can render the "Restored unsaved changes"
      // banner (Requirement 14.7). `persist` invokes this callback after
      // hydration resolves with `state` populated on success, or with
      // `error` set when parsing / storage failed. We ignore errors per
      // Requirement 14.8 and fall back to a fresh store.
      onRehydrateStorage: () => (state, error) => {
        if (error) {
          // Corrupt JSON or storage error — `persist` already left the
          // store at its initial state. Nothing to do.
          return;
        }
        if (state && state.portalData) {
          // A draft with `portalData` is an unsaved session. Mirror its
          // unsaved-ness onto `isDirty` so the toolbar and unsaved-
          // changes guard reflect it immediately, and expose the banner
          // flag for the page to render.
          usePortalEditorStore.setState({
            hasRestoredDraft: true,
            isDirty: true,
          });
        }
      },
    }
  )
);
