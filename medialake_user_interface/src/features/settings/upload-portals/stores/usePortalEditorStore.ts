import { create } from "zustand";
import { persist, type PersistStorage, type StorageValue } from "zustand/middleware";

import type {
  CreatePortalRequest,
  CreatePortalTemplateRequest,
  CreatePortalThemeRequest,
  Portal,
  PortalDestination,
  PortalMetadataField,
  PortalPage,
  PortalPageElement,
  PortalTemplate,
  PortalTheme,
} from "@/api/types/api.types";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import { PORTAL_DEFAULT_ALLOWED_FILE_TYPES } from "@/features/portal/constants";
import { portalAppearanceSchema } from "../schemas/appearance.schema";
import { portalPagesSchemaWithFieldKeys } from "../schemas/pages.schema";
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
 *
 * `"pages"` is the "Pages & Workflow" section that hosts page CRUD/reorder and
 * field/destination page assignment. It also serves as the bucket key under
 * which page-level structural errors (e.g. a blocked page removal) are recorded
 * in {@link PortalEditorState.validationErrors}. Task 13.3 wires it into the
 * sidebar `SECTIONS` and `SECTION_ORDER`.
 *
 * `"fields"` is the "Field Configuration" section that owns the metadata field
 * builder (label/type/required/choices). It sits directly under
 * "Pages & Workflow" so admins configure the fields they dragged onto pages
 * right next to where they placed them. `"metadata"` now hosts only the asset
 * upload limits (max file size, max files per session, allowed file types) and
 * is surfaced as "Upload Limits & File Settings".
 */
export type EditorSection =
  | "branding"
  | "content"
  | "appearance"
  | "typography"
  | "layout"
  | "access"
  | "destinations"
  | "metadata"
  | "pages"
  | "fields";

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

  /**
   * Seed the editor for a brand-new portal from a Template and/or a Theme by
   * SNAPSHOT (copy-on-create) — there is NO live link back to either source
   * (Requirements 16.5, 17.4, Property 11).
   *
   * Appearance is resolved with later sources overriding earlier ones
   * (Requirement 17.5):
   *
   *   1. `DEFAULT_PORTAL_APPEARANCE`                         (baseline)
   *   2. the template's appearance — resolved as: if the template's
   *      `themeId` matches the supplied `theme.themeId`, that theme's
   *      appearance; OTHERWISE the template's inline `appearance`. A
   *      DANGLING `themeId` (whose theme isn't supplied) is IGNORED and the
   *      template's inline `appearance` is used (Requirement 16.9).
   *   3. the explicitly selected standalone `theme`'s appearance — layered
   *      last so an admin-picked theme wins over the template's look.
   *
   * Structure (`pages`, `metadataFields`, `destinations` incl. `connectorId`
   * + `pageNumber`, access settings, and limits) is seeded ONLY from the
   * `template`; a theme never carries structure. With no template the editor
   * starts from the empty/default single-page structure.
   *
   * Everything copied from the sources is DEEP-CLONED so later edits in the
   * store never mutate the source `template`/`theme` objects and vice-versa
   * (Property 11 — snapshot independence).
   *
   * Like {@link initialize}, this is a fresh editor seed: it sets
   * `isInitialized: true` and `isDirty: false` (the admin hasn't edited yet;
   * the first `update*`/page action flips `isDirty`). `portalData.themeId` is
   * set to the applied theme's id (the standalone theme, else the template's
   * `themeId` when it resolved to a supplied theme) as INFORMATIONAL metadata
   * only — there is no live inheritance.
   */
  initializeFromSources: (sources: { template?: PortalTemplate; theme?: PortalTheme }) => void;

  /**
   * Apply a Theme to the portal currently open in the editor by replacing
   * ONLY `appearance` with a snapshot of the theme's appearance, leaving the
   * portal STRUCTURE (`pages`, `metadataFields`, `destinations`) untouched
   * (Requirement 16.7). The theme's appearance is deep-merged onto
   * `DEFAULT_PORTAL_APPEARANCE` (so a partial theme still yields a complete
   * appearance) and deep-cloned, so the editor stays independent of the theme
   * (Property 11). Records the applied theme's id on `portalData.themeId`
   * (informational only) and marks the store dirty.
   */
  applyTheme: (theme: PortalTheme) => void;

  /**
   * Serialize the current editor `appearance` into a
   * {@link CreatePortalThemeRequest} ("Save as Theme"). A theme is
   * appearance-only — NO structure is included. `name`/`description` are
   * supplied by the caller because the editor store does not hold a theme
   * name. The appearance is deep-cloned so the returned payload is
   * independent of the store (Property 11).
   */
  buildThemePayload: (name: string, description?: string) => CreatePortalThemeRequest;

  /**
   * Serialize the current editor structure into a
   * {@link CreatePortalTemplateRequest} ("Save as Template"). Includes the
   * full structure snapshot (`pages`, `metadataFields`, `destinations` incl.
   * `connectorId` + `pageNumber`, `appearance`, access settings, and limits)
   * plus an optional `themeId`. NEVER includes a passphrase — templates do
   * not carry per-portal secrets (Requirement 17.7). `name`/`description`/
   * `themeId` are supplied by the caller. The structure is deep-cloned so the
   * returned payload is independent of the store (Property 11).
   */
  buildTemplatePayload: (
    name: string,
    description?: string,
    themeId?: string
  ) => CreatePortalTemplateRequest;

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

  // Pages slice actions (task 12.1)
  //
  // Pages live on `portalData.pages` (`PortalPage[]`) for persistence
  // symmetry; metadata fields on `portalData.metadataFields`
  // (`PortalMetadataField[]`, each with optional `pageNumber`); destinations
  // on `portalData.destinations` (`PortalDestination[]`, each with optional
  // `pageNumber`). A `metadata-field` element references a field via
  // `fieldKey === slug(field.label)`. Every action below marks the store
  // dirty, matching the rest of the portal-data mutators.

  /**
   * Append a new empty page after the highest existing `pageNumber`
   * (or page 1 when there are none). No-op when the portal already has the
   * maximum of 50 pages; in that case a `"pages"` validation error is
   * recorded explaining the limit (Requirement 9.2).
   */
  addPage: () => void;
  /**
   * Remove a page by `pageNumber`. BLOCKED (no mutation) when the page still
   * hosts any `metadata-field` element, any destination assigned to it, or
   * the uploader element; the reason is recorded under the `"pages"` error
   * bucket. Otherwise the page is removed, the remaining pages are renumbered
   * 1..N contiguously, and the new `pageNumber` cascades onto the fields and
   * destinations that referenced renumbered pages (Requirements 9.3, 9.4).
   */
  removePage: (pageNumber: number) => void;
  /**
   * Move the page currently at `fromPageNumber` to `toIndex` in the page
   * array, then renumber all pages 1..N contiguously and cascade the new
   * `pageNumber` onto every metadata field and destination that referenced a
   * renumbered page (Requirement 9.3).
   */
  reorderPages: (fromPageNumber: number, toIndex: number) => void;
  /**
   * Shallow-merge `patch` (title / descriptionHtml / visibleIf) into the page
   * identified by `pageNumber`. `pageNumber` and `elements` are never
   * overwritten by this action.
   */
  updatePage: (pageNumber: number, patch: Partial<PortalPage>) => void;
  /**
   * Move an existing metadata field's `metadata-field` element to
   * `pageNumber` at the given `index`, removing it from whichever page
   * previously hosted it, and set the field's `pageNumber` (Requirement 9.5).
   */
  assignFieldToPage: (fieldKey: string, pageNumber: number, index: number) => void;
  /**
   * Create a brand-new metadata field of `fieldType`, push it onto
   * `metadataFields` with its `pageNumber`, and insert its `metadata-field`
   * element at `index` on the target page (dnd palette drop, Requirement 9.5).
   *
   * When `role` is `"collection-picker"`, the field is seeded with that role,
   * a friendly default label ("Add to collection"), and an empty
   * `roleConfig` (multi-select, no allowed collections yet — the admin curates
   * them in Field Configuration).
   */
  addFieldToPage: (
    fieldType: PortalMetadataField["type"],
    pageNumber: number,
    index: number,
    role?: PortalMetadataField["role"]
  ) => void;
  /**
   * Reorder a metadata field's `metadata-field` element to `index` within the
   * page that currently hosts it (same-page reorder). Referenced by the
   * dnd-kit handler in task 13.
   */
  reorderFieldWithinPage: (fieldKey: string, index: number) => void;
  /**
   * Rename the metadata field currently keyed by `oldFieldKey` to `newLabel`,
   * updating BOTH the field's `label` AND every referencing `metadata-field`
   * page element's `fieldKey` atomically so the
   * `slug(field.label) === element.fieldKey` invariant is preserved.
   *
   * Without this atomicity, editing a field's label directly would leave the
   * page element pointing at the stale slug — the renderer would no longer
   * resolve the field and it would silently vanish from the page.
   *
   * Returns `true` when the rename was applied. The rename is REJECTED
   * (returns `false`, no mutation) when:
   *   - no field is keyed by `oldFieldKey`;
   *   - `newLabel` slugifies to an empty string (a field must have a key); or
   *   - the new slug collides with a DIFFERENT existing field (which would
   *     merge two fields under one key).
   * When the new slug equals `oldFieldKey` (e.g. a whitespace/case-only edit),
   * only the display `label` changes and no element keys are touched.
   */
  renameField: (oldFieldKey: string, newLabel: string) => boolean;
  /**
   * Set the `pageNumber` of the destination identified by `destinationId`
   * (Requirement 9.5).
   */
  assignDestinationToPage: (destinationId: string, pageNumber: number) => void;
  /**
   * Place the uploader element on exactly one page: remove any existing
   * `{ kind: "uploader" }` element from every page, then append one to the
   * target page (single-uploader enforcement, Requirement 9.6).
   */
  setUploaderPage: (pageNumber: number) => void;

  /**
   * Place a single built-in element (`uploader`, `destination-selector`,
   * `path-browser`, or `path-builder`) on a page at `index`. These elements are
   * unique per portal, so this strips any existing element of the same `kind`
   * from every page first, then inserts one at the target position. This backs
   * both dragging a built-in from the palette onto a page AND moving an
   * existing built-in element across/within pages.
   */
  addElementToPage: (
    kind: Exclude<PortalPageElement["kind"], "metadata-field">,
    pageNumber: number,
    index: number
  ) => void;

  /**
   * Remove every built-in element of the given `kind` from all pages.
   */
  removeElement: (kind: Exclude<PortalPageElement["kind"], "metadata-field">) => void;

  /**
   * Create a brand-new metadata field from the Field Configuration section and
   * place it on a page so it appears in the Pages tab AND renders on the public
   * portal. Mirrors {@link addFieldToPage} but targets the page hosting the
   * uploader (falling back to the first page) and appends the field's
   * `metadata-field` element to the end of that page. A unique, non-empty
   * default label is synthesized so the field has a valid `fieldKey`
   * (`slug(label)`) for the element reference; the admin renames it afterward
   * via the atomic {@link renameField} path. No-op when the portal has no
   * pages. Marks the store dirty.
   */
  addMetadataField: (
    fieldType?: PortalMetadataField["type"],
    role?: PortalMetadataField["role"]
  ) => void;

  /**
   * Fully delete the metadata field keyed by `fieldKey` (`slug(label)`): remove
   * it from `metadataFields` AND strip its `metadata-field` element from every
   * page. This keeps the field list and page elements in sync so deleting a
   * field never leaves an orphaned, input-type-less element on a page (which
   * previously failed save validation). Backs both the Field Configuration
   * delete button and the per-field delete affordance in the Pages tab. Marks
   * the store dirty.
   */
  removeMetadataField: (fieldKey: string) => void;

  // Validation actions
  clearSectionErrors: (section: EditorSection) => void;

  /**
   * Validate the current store state. Runs
   * {@link portalAppearanceSchema} against `state.appearance` and checks
   * `portalData` invariants (non-empty `name`, slug present and matching
   * the portal slug pattern, at least one destination). Additionally runs
   * {@link portalPagesSchemaWithFieldKeys} against `portalData.pages`
   * (contiguous `pageNumber`s, exactly one uploader element, and every
   * `metadata-field` element referencing a real field key) plus
   * reference-integrity checks that every metadata field's and destination's
   * `pageNumber` references an existing page — recording any failure under the
   * dedicated `"pages"` error bucket (Requirements 9.8, 10.1). Populates
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
   * - Includes `pages`, `appearance`, and preserves the `pageNumber` on each
   *   destination and metadata field so the page assignment round-trips to the
   *   backend (Requirement 9.7).
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
 * Build the default `portalData` for a brand-new portal (create mode).
 *
 * Seeds a single Page 1 whose only element is the uploader, so the editor
 * never starts from a "zero pages" state. This means:
 *   - the admin is not forced to "Add Page" before doing anything;
 *   - the Pages & Workflow drop surface exists immediately, so drag-and-drop
 *     of field types works from the first interaction;
 *   - the preview renders the real (initially empty) page instead of a
 *     synthesized mock; and
 *   - the "exactly one uploader" save validation is satisfied out of the box.
 *
 * `metadataFields` and `destinations` start empty — the preview shows only
 * what the admin actually configures (no phantom mock fields).
 */
const createDefaultPortalData = (): PortalEditorPortalData => ({
  pages: [
    {
      pageNumber: 1,
      title: "Page 1",
      // Uploader-only by default. The uploader auto-resolves the sole
      // destination at runtime (see UppyUploaderQuestion), so no visible
      // destination-selector is needed for the common single-destination
      // portal — keeping the public page to just the upload widget.
      elements: [{ kind: "uploader" }],
    },
  ],
  metadataFields: [],
  destinations: [],
  // Portals collect a form submission by default: the public flow shows a
  // Submit step whose click marks the session submitted. The admin can turn
  // this off to make the portal upload-only (no Submit button).
  formSubmissionEnabled: true,
  // Seed the default media allow-list so the editor's "Allowed file types"
  // field shows the supported audio/video/image types out of the box. The
  // admin can edit it, or CLEAR it entirely to allow any file type — an empty
  // list round-trips to the backend and the uploader/validator treat it as
  // "allow all" (see UppyUploaderQuestion + portal_public _resolve_allowed_types).
  allowedFileTypes: [...PORTAL_DEFAULT_ALLOWED_FILE_TYPES],
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

/**
 * Maximum number of pages a single portal may contain (Requirements 1.1 / 9.2).
 * {@link PortalEditorState.addPage} is a no-op once this many pages exist and
 * records a `"pages"` validation error explaining the limit.
 */
const MAX_PAGES = 50;

/**
 * Slugify an admin-authored field label into the stable `fieldKey` used to
 * relate a `metadata-field` page element back to its
 * {@link PortalMetadataField}.
 *
 * Mirrors the `slug` helper in `shared/portalSurveyModel.ts` (lowercase,
 * non-alphanumeric runs → `_`, trim leading/trailing `_`). It is duplicated
 * here as a tiny pure function rather than imported so the editor store does
 * not pull `survey-core` — and its module-init question registration — into its
 * module graph.
 */
const slug = (label: string): string =>
  label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

/**
 * Read the `pages` array off the (loose) portal-data slice, defaulting to an
 * empty array when absent or malformed.
 */
const readPages = (portal: PortalEditorPortalData): PortalPage[] =>
  Array.isArray(portal.pages) ? (portal.pages as PortalPage[]) : [];

/**
 * Read the `metadataFields` array off the (loose) portal-data slice, defaulting
 * to an empty array when absent or malformed.
 */
const readFields = (portal: PortalEditorPortalData): PortalMetadataField[] =>
  Array.isArray(portal.metadataFields) ? (portal.metadataFields as PortalMetadataField[]) : [];

/**
 * Read the `destinations` array off the (loose) portal-data slice, defaulting
 * to an empty array when absent or malformed.
 */
const readDestinations = (portal: PortalEditorPortalData): PortalDestination[] =>
  Array.isArray(portal.destinations) ? (portal.destinations as PortalDestination[]) : [];

/**
 * Apply an old→new `pageNumber` remap to the `pageNumber` field of a list of
 * items (metadata fields or destinations). Items whose current `pageNumber` is
 * absent from the map are returned unchanged. Used by `removePage` and
 * `reorderPages` to cascade the renumbered pages onto the fields/destinations
 * that referenced them (Requirement 9.3).
 */
const cascadePageNumbers = <T extends { pageNumber?: number }>(
  items: T[],
  remap: ReadonlyMap<number, number>
): T[] =>
  items.map((item) =>
    item.pageNumber !== undefined && remap.has(item.pageNumber)
      ? { ...item, pageNumber: remap.get(item.pageNumber) as number }
      : item
  );

/**
 * Renumber a page array to a contiguous 1..N sequence in array order and
 * return both the renumbered pages and the old→new `pageNumber` remap used to
 * cascade the change onto fields/destinations.
 */
const renumberPages = (
  pages: PortalPage[]
): { pages: PortalPage[]; remap: Map<number, number> } => {
  const remap = new Map<number, number>();
  const renumbered = pages.map((page, index) => {
    const nextNumber = index + 1;
    remap.set(page.pageNumber, nextNumber);
    return { ...page, pageNumber: nextNumber };
  });
  return { pages: renumbered, remap };
};

/**
 * Resolve the appearance a Template contributes when seeding the editor
 * (Requirements 17.5, 16.9).
 *
 * - If the template references a Theme by `themeId` AND that exact theme is
 *   supplied (matching `themeId`), use the supplied theme's `appearance`.
 * - OTHERWISE fall back to the template's inline `appearance`. This is the
 *   dangling-`themeId` case: a `themeId` whose theme isn't supplied is
 *   IGNORED and we use the inline snapshot rather than raising (Req 16.9).
 *
 * Returns `undefined` when neither source yields an appearance (the caller
 * then keeps the default baseline).
 */
const resolveTemplateAppearance = (
  template: PortalTemplate,
  referencedTheme?: PortalTheme
): PortalAppearance | undefined => {
  if (
    template.themeId !== undefined &&
    referencedTheme !== undefined &&
    referencedTheme.themeId === template.themeId &&
    referencedTheme.appearance !== undefined
  ) {
    return referencedTheme.appearance;
  }
  return template.appearance;
};

/**
 * Structural keys copied from a Template into `portalData` when seeding a new
 * portal (Requirement 17.4). Appearance is resolved separately; `pages`,
 * `metadataFields`, and `destinations` are deep-cloned by the caller. Listed
 * as a constant so the snapshot surface is easy to audit and stays in sync
 * with {@link CreatePortalTemplateRequest}.
 */
const TEMPLATE_SCALAR_STRUCTURE_KEYS = [
  "accessMode",
  "allowedGroups",
  "ipAllowlist",
  "tokenBypassesPassphrase",
  "structuredPathMode",
  "captchaEnabled",
  "formSubmissionEnabled",
  "maxFileSizeBytes",
  "maxFilesPerSession",
] as const satisfies readonly (keyof PortalTemplate)[];

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
            portalData: (portal ?? createDefaultPortalData()) as PortalEditorPortalData,
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

        initializeFromSources: ({ template, theme } = {}) => {
          // ---- 1. Resolve appearance (later layers override earlier) -------
          // Layer order (Req 17.5): DEFAULT -> template (its referenced theme
          // OR inline appearance) -> explicitly selected theme.
          let appearance = structuredClone(DEFAULT_PORTAL_APPEARANCE);

          if (template) {
            const templateAppearance = resolveTemplateAppearance(template, theme);
            if (templateAppearance) {
              // structuredClone the source slice before merging so we never
              // read-through to (or alias) the template/theme objects.
              appearance = mergeInto(appearance, structuredClone(templateAppearance));
            }
          }

          // A standalone selected theme wins over the template's look. We only
          // layer it again here when it is NOT the template's referenced theme
          // (that case was already applied above); re-layering an identical
          // object is harmless, but layering it explicitly keeps the
          // "selected theme wins" semantics obvious for the theme-only path.
          if (theme?.appearance) {
            appearance = mergeInto(appearance, structuredClone(theme.appearance));
          }

          // ---- 2. Seed structure from the template (deep-cloned) -----------
          const portalData: PortalEditorPortalData = {};

          if (template) {
            // Arrays are deep-cloned wholesale so editing the store never
            // mutates the source template (Property 11). `destinations` keep
            // their `connectorId` + `pageNumber` verbatim; `metadataFields`
            // keep their `pageNumber`.
            portalData.pages = structuredClone(template.pages ?? []);
            portalData.metadataFields = structuredClone(template.metadataFields ?? []);
            portalData.destinations = structuredClone(template.destinations ?? []);

            for (const key of TEMPLATE_SCALAR_STRUCTURE_KEYS) {
              const value = template[key];
              if (value !== undefined) {
                // Deep-clone array-valued settings (allowedGroups, ipAllowlist)
                // so they too are independent of the source template.
                (portalData as Record<string, unknown>)[key] = structuredClone(value);
              }
            }
          }

          // ---- 3. Informational themeId (NOT a live link) ------------------
          // Record the applied theme's id (informational only — there is no
          // live inheritance). `theme?.themeId` covers both paths: a
          // standalone selected theme, and a template's referenced theme when
          // that theme was actually supplied. A DANGLING template `themeId`
          // (no theme supplied) leaves `theme` undefined, so nothing is
          // recorded — we fell back to the template's inline appearance and
          // there is no resolved theme to point at (Req 16.9).
          const appliedThemeId = theme?.themeId;

          if (appliedThemeId !== undefined) {
            portalData.themeId = appliedThemeId;
          }

          set({
            portalData,
            appearance,
            // Creating-from is a fresh editor seed: mark initialized and clean
            // (mirrors `initialize`). The first admin edit flips `isDirty`.
            isDirty: false,
            isInitialized: true,
            hasRestoredDraft: false,
            validationErrors: {},
            history: [],
            historyIndex: -1,
          });
        },

        applyTheme: (theme) => {
          const state = get();
          // Replace ONLY appearance; structure (`portalData`) is untouched
          // (Req 16.7). Deep-merge the theme's appearance onto the DEFAULT so
          // a partial theme still yields a complete appearance, and clone the
          // source slice so the editor stays independent of the theme.
          const appearance = theme.appearance
            ? mergeInto(
                structuredClone(DEFAULT_PORTAL_APPEARANCE),
                structuredClone(theme.appearance)
              )
            : structuredClone(DEFAULT_PORTAL_APPEARANCE);

          set({
            appearance,
            // Record the applied theme on the existing portalData
            // (informational only) without disturbing any structural field.
            portalData:
              theme.themeId !== undefined
                ? { ...(state.portalData ?? {}), themeId: theme.themeId }
                : state.portalData,
            isDirty: true,
          });
        },

        buildThemePayload: (name, description) => {
          const state = get();
          // Appearance-only — NO structure. Deep-clone so the payload is
          // independent of the live store appearance (Property 11).
          const payload: CreatePortalThemeRequest = {
            name,
            appearance: structuredClone(state.appearance),
          };
          if (description !== undefined) payload.description = description;
          return payload;
        },

        buildTemplatePayload: (name, description, themeId) => {
          const state = get();
          const portal = state.portalData ?? {};

          // Full structure snapshot. Every array/slice is deep-cloned so the
          // returned payload never aliases the live store (Property 11).
          // NOTE: passphrase is NEVER read or included (Req 17.7).
          const pages = Array.isArray(portal.pages)
            ? structuredClone(portal.pages as PortalPage[])
            : [];
          const metadataFields = Array.isArray(portal.metadataFields)
            ? structuredClone(portal.metadataFields as PortalMetadataField[])
            : [];
          const destinations = Array.isArray(portal.destinations)
            ? structuredClone(portal.destinations as PortalDestination[])
            : [];

          const payload: CreatePortalTemplateRequest = {
            name,
            pages,
            metadataFields,
            destinations,
            appearance: structuredClone(state.appearance),
          };

          if (description !== undefined) payload.description = description;
          if (themeId !== undefined) payload.themeId = themeId;

          const accessMode = portal.accessMode as
            | CreatePortalTemplateRequest["accessMode"]
            | undefined;
          if (accessMode !== undefined) payload.accessMode = accessMode;

          if (Array.isArray(portal.allowedGroups)) {
            payload.allowedGroups = structuredClone(portal.allowedGroups as string[]);
          }
          if (Array.isArray(portal.ipAllowlist)) {
            payload.ipAllowlist = structuredClone(portal.ipAllowlist as string[]);
          }
          if (typeof portal.tokenBypassesPassphrase === "boolean") {
            payload.tokenBypassesPassphrase = portal.tokenBypassesPassphrase;
          }
          if (typeof portal.structuredPathMode === "boolean") {
            payload.structuredPathMode = portal.structuredPathMode;
          }
          if (typeof portal.captchaEnabled === "boolean") {
            payload.captchaEnabled = portal.captchaEnabled;
          }
          if (typeof portal.formSubmissionEnabled === "boolean") {
            payload.formSubmissionEnabled = portal.formSubmissionEnabled;
          }
          if (typeof portal.maxFileSizeBytes === "number") {
            payload.maxFileSizeBytes = portal.maxFileSizeBytes;
          }
          if (typeof portal.maxFilesPerSession === "number") {
            payload.maxFilesPerSession = portal.maxFilesPerSession;
          }

          return payload;
        },

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

        // ---- Pages slice actions (task 12.1) --------------------------------

        addPage: () =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (pages.length >= MAX_PAGES) {
              // At the limit: no mutation, record a "pages" error explaining
              // the cap (Requirement 9.2). Replace the bucket so the message
              // does not accumulate across repeated clicks.
              return {
                validationErrors: {
                  ...state.validationErrors,
                  pages: [
                    {
                      field: "pages",
                      message: `A portal can have at most ${MAX_PAGES} pages. Remove a page before adding another.`,
                    },
                  ],
                },
              };
            }
            const maxNumber = pages.reduce((max, p) => Math.max(max, p.pageNumber), 0);
            const nextNumber = maxNumber + 1;
            const newPage: PortalPage = {
              pageNumber: nextNumber,
              title: `Page ${nextNumber}`,
              elements: [],
            };
            return {
              portalData: { ...portal, pages: [...pages, newPage] },
              isDirty: true,
            };
          }),

        removePage: (pageNumber) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            const target = pages.find((p) => p.pageNumber === pageNumber);
            if (!target) {
              // Nothing to remove — leave the slice unchanged.
              return {};
            }

            const destinations = readDestinations(portal);
            const hostsMetadataField = target.elements.some((el) => el.kind === "metadata-field");
            const hostsUploader = target.elements.some((el) => el.kind === "uploader");
            const hostsDestination = destinations.some((d) => d.pageNumber === pageNumber);

            if (hostsMetadataField || hostsUploader || hostsDestination) {
              // BLOCK removal: record the reason under the "pages" bucket and
              // leave the slice unchanged (Requirement 9.4).
              const reasons: string[] = [];
              if (hostsMetadataField) reasons.push("metadata fields");
              if (hostsDestination) reasons.push("an assigned destination");
              if (hostsUploader) reasons.push("the uploader");
              return {
                validationErrors: {
                  ...state.validationErrors,
                  pages: [
                    {
                      field: `page-${pageNumber}`,
                      message: `Page ${pageNumber} can't be removed while it still hosts ${reasons.join(
                        ", "
                      )}. Move or remove ${reasons.length > 1 ? "them" : "it"} first.`,
                    },
                  ],
                },
              };
            }

            // Safe to remove: drop the page, renumber 1..N contiguously, and
            // cascade the new pageNumber onto fields/destinations that
            // referenced renumbered pages (Requirement 9.3).
            const remaining = pages.filter((p) => p.pageNumber !== pageNumber);
            const { pages: renumbered, remap } = renumberPages(remaining);
            return {
              portalData: {
                ...portal,
                pages: renumbered,
                metadataFields: cascadePageNumbers(readFields(portal), remap),
                destinations: cascadePageNumbers(destinations, remap),
              },
              isDirty: true,
            };
          }),

        reorderPages: (fromPageNumber, toIndex) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            const fromIndex = pages.findIndex((p) => p.pageNumber === fromPageNumber);
            if (fromIndex === -1) return {};

            const clampedTo = Math.max(0, Math.min(toIndex, pages.length - 1));
            if (fromIndex === clampedTo) return {};

            const reordered = [...pages];
            const [moved] = reordered.splice(fromIndex, 1);
            reordered.splice(clampedTo, 0, moved);

            // Renumber 1..N in the new order and cascade onto fields/dests
            // (Requirement 9.3).
            const { pages: renumbered, remap } = renumberPages(reordered);
            return {
              portalData: {
                ...portal,
                pages: renumbered,
                metadataFields: cascadePageNumbers(readFields(portal), remap),
                destinations: cascadePageNumbers(readDestinations(portal), remap),
              },
              isDirty: true,
            };
          }),

        updatePage: (pageNumber, patch) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            let changed = false;
            const nextPages = pages.map((page) => {
              if (page.pageNumber !== pageNumber) return page;
              changed = true;
              // Shallow-merge title/descriptionHtml/visibleIf. `pageNumber`
              // and `elements` are owned by the page actions and never
              // overwritten through this patch path.
              const {
                pageNumber: _ignoredPageNumber,
                elements: _ignoredElements,
                ...safePatch
              } = patch;
              return { ...page, ...safePatch };
            });
            if (!changed) return {};
            return { portalData: { ...portal, pages: nextPages }, isDirty: true };
          }),

        assignFieldToPage: (fieldKey, pageNumber, index) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (!pages.some((p) => p.pageNumber === pageNumber)) return {};

            // Pull the field's element off whichever page currently hosts it.
            let element: PortalPageElement | undefined;
            const stripped = pages.map((page) => {
              const idx = page.elements.findIndex(
                (el) => el.kind === "metadata-field" && el.fieldKey === fieldKey
              );
              if (idx === -1) return page;
              element = page.elements[idx];
              return { ...page, elements: page.elements.filter((_, i) => i !== idx) };
            });
            const elementToInsert: PortalPageElement = element ?? {
              kind: "metadata-field",
              fieldKey,
            };

            // Insert it on the target page at the requested index.
            const nextPages = stripped.map((page) => {
              if (page.pageNumber !== pageNumber) return page;
              const elements = [...page.elements];
              const clampedIndex = Math.max(0, Math.min(index, elements.length));
              elements.splice(clampedIndex, 0, elementToInsert);
              return { ...page, elements };
            });

            // Keep the field's pageNumber in sync (Requirement 9.5).
            const metadataFields = readFields(portal).map((f) =>
              slug(f.label) === fieldKey ? { ...f, pageNumber } : f
            );

            return {
              portalData: { ...portal, pages: nextPages, metadataFields },
              isDirty: true,
            };
          }),

        addFieldToPage: (fieldType, pageNumber, index, role) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (!pages.some((p) => p.pageNumber === pageNumber)) return {};

            const fields = readFields(portal);

            // Derive a unique label so its slugified fieldKey doesn't collide
            // with an existing field (the element references the field by
            // `slug(label)`).
            const usedKeys = new Set(fields.map((f) => slug(f.label)));
            const isCollectionPicker = role === "collection-picker";
            const baseLabel = isCollectionPicker ? "Add to collection" : "New Field";
            let label = baseLabel;
            let suffix = 1;
            while (usedKeys.has(slug(label))) {
              suffix += 1;
              label = `${baseLabel} ${suffix}`;
            }

            const order = fields.reduce((max, f) => Math.max(max, f.order ?? 0), 0) + 1;
            const newField: PortalMetadataField = {
              label,
              type: fieldType,
              required: false,
              order,
              pageNumber,
              ...(isCollectionPicker
                ? {
                    role: "collection-picker" as const,
                    roleConfig: {
                      allowedCollections: [],
                      fixedCollectionIds: [],
                      multiple: true,
                    },
                  }
                : {}),
            };
            const newElement: PortalPageElement = {
              kind: "metadata-field",
              fieldKey: slug(label),
            };

            const nextPages = pages.map((page) => {
              if (page.pageNumber !== pageNumber) return page;
              const elements = [...page.elements];
              const clampedIndex = Math.max(0, Math.min(index, elements.length));
              elements.splice(clampedIndex, 0, newElement);
              return { ...page, elements };
            });

            return {
              portalData: {
                ...portal,
                pages: nextPages,
                metadataFields: [...fields, newField],
              },
              isDirty: true,
            };
          }),

        reorderFieldWithinPage: (fieldKey, index) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            let changed = false;
            const nextPages = pages.map((page) => {
              const idx = page.elements.findIndex(
                (el) => el.kind === "metadata-field" && el.fieldKey === fieldKey
              );
              if (idx === -1) return page;
              changed = true;
              const elements = [...page.elements];
              const [moved] = elements.splice(idx, 1);
              const clampedIndex = Math.max(0, Math.min(index, elements.length));
              elements.splice(clampedIndex, 0, moved);
              return { ...page, elements };
            });
            if (!changed) return {};
            return { portalData: { ...portal, pages: nextPages }, isDirty: true };
          }),

        renameField: (oldFieldKey, newLabel) => {
          const portal: PortalEditorPortalData = get().portalData ?? {};
          const fields = readFields(portal);
          const target = fields.find((f) => slug(f.label) === oldFieldKey);
          // No field keyed by oldFieldKey → nothing to rename.
          if (!target) return false;

          const newKey = slug(newLabel);
          // A field must keep a non-empty key.
          if (newKey === "") return false;

          // A key-changing rename must not collide with a DIFFERENT field
          // (that would merge two fields under one key).
          if (
            newKey !== oldFieldKey &&
            fields.some((f) => f !== target && slug(f.label) === newKey)
          ) {
            return false;
          }

          // Update the field's label. When the slug changes, also rewrite the
          // matching element's fieldKey on every page so the link survives.
          const metadataFields = fields.map((f) => (f === target ? { ...f, label: newLabel } : f));

          let pages = readPages(portal);
          if (newKey !== oldFieldKey) {
            pages = pages.map((page) => {
              let pageChanged = false;
              const elements = page.elements.map((el) => {
                if (el.kind === "metadata-field" && el.fieldKey === oldFieldKey) {
                  pageChanged = true;
                  return { ...el, fieldKey: newKey };
                }
                return el;
              });
              return pageChanged ? { ...page, elements } : page;
            });
          }

          set({
            portalData: { ...portal, pages, metadataFields },
            isDirty: true,
          });
          return true;
        },

        assignDestinationToPage: (destinationId, pageNumber) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const destinations = readDestinations(portal);
            let changed = false;
            const next = destinations.map((d) => {
              if (d.destinationId !== destinationId) return d;
              changed = true;
              return { ...d, pageNumber };
            });
            if (!changed) return {};
            return { portalData: { ...portal, destinations: next }, isDirty: true };
          }),

        setUploaderPage: (pageNumber) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (!pages.some((p) => p.pageNumber === pageNumber)) return {};

            // Single-uploader enforcement (Requirement 9.6): strip the uploader
            // element from every page, then append exactly one onto the target.
            const nextPages = pages.map((page) => {
              const withoutUploader = page.elements.filter((el) => el.kind !== "uploader");
              if (page.pageNumber === pageNumber) {
                return {
                  ...page,
                  elements: [...withoutUploader, { kind: "uploader" } as PortalPageElement],
                };
              }
              // Only allocate a new array when this page actually hosted one.
              if (withoutUploader.length === page.elements.length) return page;
              return { ...page, elements: withoutUploader };
            });

            return { portalData: { ...portal, pages: nextPages }, isDirty: true };
          }),

        addElementToPage: (kind, pageNumber, index) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (!pages.some((p) => p.pageNumber === pageNumber)) return {};

            // Built-in elements are unique per portal: strip any existing
            // element of this kind from every page, then insert exactly one at
            // the target position (mirrors setUploaderPage's enforcement).
            const newElement = { kind } as PortalPageElement;
            const nextPages = pages.map((page) => {
              const without = page.elements.filter((el) => el.kind !== kind);
              if (page.pageNumber === pageNumber) {
                const elements = [...without];
                const clampedIndex = Math.max(0, Math.min(index, elements.length));
                elements.splice(clampedIndex, 0, newElement);
                return { ...page, elements };
              }
              if (without.length === page.elements.length) return page;
              return { ...page, elements: without };
            });

            return { portalData: { ...portal, pages: nextPages }, isDirty: true };
          }),

        removeElement: (kind) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            let changed = false;
            const nextPages = pages.map((page) => {
              const without = page.elements.filter((el) => el.kind !== kind);
              if (without.length === page.elements.length) return page;
              changed = true;
              return { ...page, elements: without };
            });
            if (!changed) return {};
            return { portalData: { ...portal, pages: nextPages }, isDirty: true };
          }),

        addMetadataField: (fieldType = "text", role) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const pages = readPages(portal);
            if (pages.length === 0) return {};

            const fields = readFields(portal);

            // Target the page hosting the uploader so the new field renders
            // alongside the upload widget; fall back to the first page.
            const targetPage =
              pages.find((p) => p.elements.some((el) => el.kind === "uploader")) ?? pages[0];

            // Derive a unique, non-empty label so its slugified fieldKey does
            // not collide with an existing field (the page element references
            // the field by `slug(label)`, and an empty label has no key).
            const usedKeys = new Set(fields.map((f) => slug(f.label)));
            const isCollectionPicker = role === "collection-picker";
            const baseLabel = isCollectionPicker ? "Add to collection" : "New Field";
            let label = baseLabel;
            let suffix = 1;
            while (usedKeys.has(slug(label))) {
              suffix += 1;
              label = `${baseLabel} ${suffix}`;
            }

            const order = fields.reduce((max, f) => Math.max(max, f.order ?? 0), 0) + 1;
            const newField: PortalMetadataField = {
              label,
              type: fieldType,
              required: false,
              order,
              pageNumber: targetPage.pageNumber,
              ...(isCollectionPicker
                ? {
                    role: "collection-picker" as const,
                    roleConfig: {
                      allowedCollections: [],
                      fixedCollectionIds: [],
                      multiple: true,
                    },
                  }
                : {}),
            };
            const newElement: PortalPageElement = {
              kind: "metadata-field",
              fieldKey: slug(label),
            };

            const nextPages = pages.map((page) =>
              page.pageNumber === targetPage.pageNumber
                ? { ...page, elements: [...page.elements, newElement] }
                : page
            );

            return {
              portalData: {
                ...portal,
                pages: nextPages,
                metadataFields: [...fields, newField],
              },
              isDirty: true,
            };
          }),

        removeMetadataField: (fieldKey) =>
          set((state) => {
            const portal: PortalEditorPortalData = state.portalData ?? {};
            const fields = readFields(portal);
            const nextFields = fields.filter((f) => slug(f.label) !== fieldKey);

            const pages = readPages(portal);
            let pagesChanged = false;
            const nextPages = pages.map((page) => {
              const without = page.elements.filter(
                (el) => !(el.kind === "metadata-field" && el.fieldKey === fieldKey)
              );
              if (without.length === page.elements.length) return page;
              pagesChanged = true;
              return { ...page, elements: without };
            });

            // No matching field and no matching element → nothing to do.
            if (nextFields.length === fields.length && !pagesChanged) return {};

            return {
              portalData: {
                ...portal,
                pages: nextPages,
                metadataFields: nextFields,
              },
              isDirty: true,
            };
          }),

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
              const field =
                issue.path.length > 0 ? String(issue.path[issue.path.length - 1]) : "unknown";
              pushError(section, field, issue.message);
            }
          }

          // ---- 2. portalData invariants ---------------------------------------
          const portal = state.portalData ?? {};
          const name = typeof portal.name === "string" ? portal.name.trim() : "";
          if (name.length === 0) {
            pushError("content", "name", "Portal name is required. Enter a name for your portal.");
          }

          const slugValue = typeof portal.slug === "string" ? portal.slug : "";
          if (slugValue.length === 0) {
            pushError(
              "content",
              "slug",
              'Portal slug is required. Enter a URL-friendly identifier (e.g. "my-portal").'
            );
          } else if (!/^[a-z0-9-]+$/.test(slugValue)) {
            pushError(
              "content",
              "slug",
              'Slug must contain only lowercase letters, numbers, and hyphens (e.g. "my-portal-2024").'
            );
          }

          const destinations = Array.isArray(portal.destinations)
            ? (portal.destinations as PortalDestination[])
            : [];
          if (destinations.length === 0) {
            pushError(
              "destinations",
              "destinations",
              "At least one destination is required. Add a collection or folder where uploaded files will be stored."
            );
          }

          // ---- 3. Page structure ----------------------------------------------
          // Mirrors the server-side `_validate_portal_structure` invariants and
          // the Zod `portalPagesSchema` so client and server agree before any
          // request is sent (Requirements 9.8, 10.1). Errors land in the
          // dedicated `"pages"` bucket so the UI (task 13.3) can open the
          // "Pages & Workflow" section and surface them inline (Req 10.5).
          const pages = Array.isArray(portal.pages) ? (portal.pages as PortalPage[]) : [];
          const metadataFields = Array.isArray(portal.metadataFields)
            ? (portal.metadataFields as PortalMetadataField[])
            : [];

          // The set of field keys a `metadata-field` element may reference is
          // derived from each metadata field's slugified label (the same
          // relation the pages slice actions use).
          const validFieldKeys = new Set(
            metadataFields
              .map((field) => (typeof field.label === "string" ? slug(field.label) : ""))
              .filter((key) => key.length > 0)
          );

          // Run the field-key-aware schema: contiguity (1..N), exactly one
          // uploader, and every `metadata-field` element referencing a real
          // field key, all in a single pass.
          const pagesResult = portalPagesSchemaWithFieldKeys(validFieldKeys).safeParse(pages);
          if (!pagesResult.success) {
            for (const issue of pagesResult.error.issues) {
              const field =
                issue.path.length > 0 ? String(issue.path[issue.path.length - 1]) : "pages";
              pushError("pages", field, issue.message);
            }
          }

          // Reference integrity the Zod schema cannot cover: destinations live
          // outside the `pages` array, so verify each destination's
          // `pageNumber` references an existing page (Requirement 9.8 / 10.3).
          // Metadata-field `pageNumber` integrity is likewise checked here in
          // addition to the element-level `fieldKey` check above.
          const validPageNumbers = new Set(pages.map((page) => page.pageNumber));
          if (pages.length > 0) {
            for (const field of metadataFields) {
              if (field.pageNumber !== undefined && !validPageNumbers.has(field.pageNumber)) {
                pushError(
                  "pages",
                  "metadataFields",
                  `Metadata field "${
                    typeof field.label === "string" ? field.label : ""
                  }" references page ${
                    field.pageNumber
                  }, which does not exist. Assign it to an existing page.`
                );
              }
            }
            for (const destination of destinations) {
              if (
                destination.pageNumber !== undefined &&
                !validPageNumbers.has(destination.pageNumber)
              ) {
                pushError(
                  "pages",
                  "destinations",
                  `Destination "${
                    typeof destination.friendlyName === "string"
                      ? destination.friendlyName
                      : destination.destinationId
                  }" references page ${
                    destination.pageNumber
                  }, which does not exist. Assign it to an existing page.`
                );
              }
            }
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
          // Requirement 9.7: the payload must carry each destination's and each
          // metadata field's `pageNumber` (assigned by the pages slice actions
          // in task 12.1). Spread every item so the page assignment — and every
          // other field — is preserved verbatim and never stripped, while still
          // handing the request a fresh copy rather than the live store array.
          const destinations = (
            Array.isArray(portal.destinations) ? (portal.destinations as PortalDestination[]) : []
          ).map((destination) => ({ ...destination }));
          const metadataFields = (
            Array.isArray(portal.metadataFields)
              ? (portal.metadataFields as PortalMetadataField[])
              : []
          ).map((field) => ({ ...field }));
          const pages = Array.isArray(portal.pages) ? (portal.pages as PortalPage[]) : [];
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
          const formSubmissionEnabled =
            typeof portal.formSubmissionEnabled === "boolean"
              ? portal.formSubmissionEnabled
              : undefined;
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
          const automationTag =
            typeof portal.automationTag === "string" ? portal.automationTag : undefined;

          const payload: CreatePortalRequest = {
            name,
            slug,
            accessMode,
            destinations,
            metadataFields,
            pages,
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
          if (formSubmissionEnabled !== undefined) {
            payload.formSubmissionEnabled = formSubmissionEnabled;
          }
          if (isActive !== undefined) payload.isActive = isActive;
          if (expiresAt !== undefined) payload.expiresAt = expiresAt;
          if (maxFileSizeBytes !== undefined) {
            payload.maxFileSizeBytes = maxFileSizeBytes;
          }
          if (maxFilesPerSession !== undefined) {
            payload.maxFilesPerSession = maxFilesPerSession;
          }
          if (logoUrl !== undefined) payload.logoUrl = logoUrl;
          // Persist whenever the editor holds an array — INCLUDING an empty one.
          // An empty array is the explicit "allow any file type" state and must
          // round-trip; only a truly-absent value is omitted so the backend
          // falls back to its default media allow-list.
          if (allowedFileTypes !== undefined) {
            payload.allowedFileTypes = allowedFileTypes;
          }
          if (automationTag !== undefined) payload.automationTag = automationTag;

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
