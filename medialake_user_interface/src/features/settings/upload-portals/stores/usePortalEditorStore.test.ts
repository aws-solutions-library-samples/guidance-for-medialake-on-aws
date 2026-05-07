import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import type { PortalAppearance } from "../types/appearance.types";
import { usePortalEditorStore, type PortalEditorPortalData } from "./usePortalEditorStore";

/**
 * Unit tests for `usePortalEditorStore`.
 *
 * Validates: Requirements 2.6, 10.11
 *
 * Covers:
 *   - `initialize()` with and without a portal argument (deep-merge into
 *     `DEFAULT_PORTAL_APPEARANCE`, lifecycle flags).
 *   - Each `update*` setter (appearance, color, typography, layout, branding,
 *     content) patches the correct sub-slice and sets `isDirty = true`.
 *   - `markClean` clears the dirty flag (and is a no-op when already clean).
 *   - `resetAppearanceToDefaults` restores defaults and marks dirty.
 *   - `clearSectionErrors` removes a single section's validation errors.
 *   - Simple UI round-trips: `setSaving`, `setActiveSection`, `setPreviewMode`.
 */
describe("usePortalEditorStore", () => {
  beforeEach(() => {
    // Reset to a clean, uninitialized state before every test so assertions
    // about lifecycle flags (isDirty / isInitialized) start from a known base.
    // `reset()` also clears the persisted draft in `localStorage` so tests
    // don't accidentally rehydrate state from a previous test (task 5.17).
    usePortalEditorStore.getState().reset();
  });

  describe("initialize", () => {
    it("initialize() with no arg seeds defaults and clears dirty flag", () => {
      usePortalEditorStore.getState().initialize();

      const state = usePortalEditorStore.getState();

      expect(state.isInitialized).toBe(true);
      expect(state.isDirty).toBe(false);
      expect(state.portalData).toBeNull();
      expect(state.appearance).toEqual(DEFAULT_PORTAL_APPEARANCE);
    });

    it("initialize(portal) deep-merges partial appearance into defaults", () => {
      const portal: PortalEditorPortalData = {
        appearance: {
          colors: { primary: "#123456" },
          // Intentionally omit other colors and sibling slices so we can
          // assert that the defaults are preserved for every unspecified
          // field. The cast matches what real portal data looks like on the
          // wire — a partial `appearance` is common for older records.
        } as unknown as PortalAppearance,
      };

      usePortalEditorStore.getState().initialize(portal);

      const { appearance } = usePortalEditorStore.getState();

      // Overridden field takes the new value.
      expect(appearance.colors.primary).toBe("#123456");

      // All unspecified color fields still match the defaults.
      expect(appearance.colors.background).toBe(DEFAULT_PORTAL_APPEARANCE.colors.background);
      expect(appearance.colors.cardBackground).toBe(
        DEFAULT_PORTAL_APPEARANCE.colors.cardBackground
      );
      expect(appearance.colors.textPrimary).toBe(DEFAULT_PORTAL_APPEARANCE.colors.textPrimary);

      // Sibling slices remain at defaults.
      expect(appearance.typography).toEqual(DEFAULT_PORTAL_APPEARANCE.typography);
      expect(appearance.layout).toEqual(DEFAULT_PORTAL_APPEARANCE.layout);
      expect(appearance.branding).toEqual(DEFAULT_PORTAL_APPEARANCE.branding);
      expect(appearance.content).toEqual(DEFAULT_PORTAL_APPEARANCE.content);
    });

    it("initialize(portal) ignores unknown portalData keys like contentFormat", () => {
      // `contentFormat` is no longer a store field. Passing it via the
      // loose `PortalEditorPortalData` index signature must not throw and
      // must not end up as a state slice.
      usePortalEditorStore.getState().initialize({ contentFormat: "markdown" } as never);

      const state = usePortalEditorStore.getState() as unknown as Record<string, unknown>;
      expect(state.contentFormat).toBeUndefined();
    });
  });

  describe("update* setters mark the store dirty", () => {
    beforeEach(() => {
      usePortalEditorStore.getState().initialize();
    });

    it("updateColor patches a single color and sets isDirty", () => {
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");

      const state = usePortalEditorStore.getState();
      expect(state.appearance.colors.primary).toBe("#abcdef");
      // Sibling color must be untouched.
      expect(state.appearance.colors.background).toBe(DEFAULT_PORTAL_APPEARANCE.colors.background);
      expect(state.isDirty).toBe(true);
    });

    it("updateTypography patches typography and leaves siblings intact", () => {
      usePortalEditorStore.getState().updateTypography({ baseFontSize: 20 });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.typography.baseFontSize).toBe(20);
      expect(state.appearance.typography.headingFontFamily).toBe(
        DEFAULT_PORTAL_APPEARANCE.typography.headingFontFamily
      );
      expect(state.appearance.typography.bodyFontFamily).toBe(
        DEFAULT_PORTAL_APPEARANCE.typography.bodyFontFamily
      );
      expect(state.isDirty).toBe(true);
    });

    it("updateLayout patches layout and sets isDirty", () => {
      usePortalEditorStore.getState().updateLayout({ cardMaxWidth: 900 });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.layout.cardMaxWidth).toBe(900);
      expect(state.appearance.layout.cardBorderRadius).toBe(
        DEFAULT_PORTAL_APPEARANCE.layout.cardBorderRadius
      );
      expect(state.isDirty).toBe(true);
    });

    it("updateBranding patches branding and sets isDirty", () => {
      usePortalEditorStore.getState().updateBranding({ logoSize: 96 });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.branding.logoSize).toBe(96);
      expect(state.appearance.branding.showPoweredBy).toBe(
        DEFAULT_PORTAL_APPEARANCE.branding.showPoweredBy
      );
      expect(state.isDirty).toBe(true);
    });

    it("updateContent patches content and sets isDirty", () => {
      usePortalEditorStore.getState().updateContent({ titleHtml: "<h1>Hi</h1>" });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.content.titleHtml).toBe("<h1>Hi</h1>");
      expect(state.appearance.content.submitButtonText).toBe(
        DEFAULT_PORTAL_APPEARANCE.content.submitButtonText
      );
      expect(state.isDirty).toBe(true);
    });

    it("updateAppearance merges a top-level slice and sets isDirty", () => {
      usePortalEditorStore.getState().updateAppearance({ mode: "dark" });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.mode).toBe("dark");
      expect(state.isDirty).toBe(true);
    });
  });

  describe("markClean", () => {
    it("clears isDirty", () => {
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");
      expect(usePortalEditorStore.getState().isDirty).toBe(true);

      usePortalEditorStore.getState().markClean();

      expect(usePortalEditorStore.getState().isDirty).toBe(false);
    });

    it("is a no-op when the store is already clean", () => {
      usePortalEditorStore.getState().initialize();
      expect(usePortalEditorStore.getState().isDirty).toBe(false);

      const before = usePortalEditorStore.getState();
      usePortalEditorStore.getState().markClean();
      const after = usePortalEditorStore.getState();

      expect(after.isDirty).toBe(false);
      // Nothing else should have changed — assert a handful of invariants
      // rather than full reference-equality (zustand always produces a fresh
      // state object on `set`, so referential equality is not guaranteed).
      expect(after.appearance).toEqual(before.appearance);
      expect(after.isInitialized).toBe(before.isInitialized);
      expect(after.validationErrors).toEqual(before.validationErrors);
    });

    it("supports the initialize → update → markClean three-state transition", () => {
      usePortalEditorStore.getState().initialize();
      expect(usePortalEditorStore.getState().isDirty).toBe(false);

      usePortalEditorStore.getState().updateColor("primary", "#abcdef");
      expect(usePortalEditorStore.getState().isDirty).toBe(true);

      usePortalEditorStore.getState().markClean();
      expect(usePortalEditorStore.getState().isDirty).toBe(false);
    });
  });

  describe("resetAppearanceToDefaults", () => {
    it("restores defaults after edits and marks isDirty", () => {
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");
      usePortalEditorStore.getState().updateLayout({ cardMaxWidth: 900 });
      usePortalEditorStore.getState().markClean();

      usePortalEditorStore.getState().resetAppearanceToDefaults();

      const state = usePortalEditorStore.getState();
      expect(state.appearance).toEqual(DEFAULT_PORTAL_APPEARANCE);
      expect(state.isDirty).toBe(true);
    });
  });

  describe("clearSectionErrors", () => {
    it("removes a single section's errors from validationErrors", () => {
      usePortalEditorStore.getState().initialize();

      // Seed errors directly via setState because the store doesn't expose a
      // public `setValidationErrors` action in Phase 1 yet.
      usePortalEditorStore.setState({
        validationErrors: {
          layout: [{ field: "test", message: "err" }],
          appearance: [{ field: "test", message: "err" }],
        },
      });

      usePortalEditorStore.getState().clearSectionErrors("layout");

      const { validationErrors } = usePortalEditorStore.getState();
      expect(validationErrors).not.toHaveProperty("layout");
      expect(validationErrors.appearance).toEqual([{ field: "test", message: "err" }]);
    });

    it("is a no-op when the section has no errors", () => {
      usePortalEditorStore.getState().initialize();

      const before = usePortalEditorStore.getState().validationErrors;
      usePortalEditorStore.getState().clearSectionErrors("layout");
      const after = usePortalEditorStore.getState().validationErrors;

      expect(after).toEqual(before);
    });
  });

  describe("UI round-trips", () => {
    it("setSaving toggles isSaving in both directions", () => {
      usePortalEditorStore.getState().setSaving(true);
      expect(usePortalEditorStore.getState().isSaving).toBe(true);

      usePortalEditorStore.getState().setSaving(false);
      expect(usePortalEditorStore.getState().isSaving).toBe(false);
    });

    it("setActiveSection and setPreviewMode round-trip", () => {
      usePortalEditorStore.getState().setActiveSection("typography");
      expect(usePortalEditorStore.getState().activeSection).toBe("typography");

      usePortalEditorStore.getState().setPreviewMode("mobile");
      expect(usePortalEditorStore.getState().previewMode).toBe("mobile");
    });
  });
});

/**
 * Persistence behavior (tasks 5.16 & 5.17).
 *
 * Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8
 *
 * Covers:
 *   - Static `localStorage` key `"portal-editor-draft"` (Requirement 14.1/14.2).
 *   - 5-second trailing-edge debounce on writes (Requirement 14.3).
 *   - `partialize` persists `portalData` + `appearance` only, strips
 *     `logoFile`, and never writes `isSaving` / `validationErrors` /
 *     `activeSection` / `previewMode` / `isDirty` / `isInitialized` /
 *     `hasRestoredDraft` (Requirements 14.4, 14.5).
 *   - `markClean` clears the persisted draft (Requirement 14.6).
 *   - `reset` clears the persisted draft (test-isolation guarantee).
 *   - `onRehydrateStorage` flips `hasRestoredDraft` on when a non-empty
 *     draft was found (Requirement 14.7).
 *   - `acknowledgeRestoredDraft` dismisses the banner flag without
 *     clearing storage.
 *   - Corrupt JSON in storage falls back to a fresh store without
 *     throwing (Requirement 14.8).
 */
const PERSIST_KEY = "portal-editor-draft";

describe("usePortalEditorStore — persist middleware", () => {
  beforeEach(() => {
    vi.useRealTimers();
    usePortalEditorStore.getState().reset();
    localStorage.removeItem(PERSIST_KEY);
  });

  describe("debounced write behavior", () => {
    it("writes to localStorage under the static key after the 5s debounce", () => {
      vi.useFakeTimers();
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");

      // Immediately after the edit the write is still pending.
      expect(localStorage.getItem(PERSIST_KEY)).toBeNull();

      // Advance past the 5-second window; the trailing flush should now
      // land in storage.
      vi.advanceTimersByTime(5_000);

      const raw = localStorage.getItem(PERSIST_KEY);
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw as string);
      // The persisted envelope is `{ state, version }` per Zustand persist.
      expect(parsed.state.appearance.colors.primary).toBe("#abcdef");
    });

    it("coalesces rapid edits into a single write at the end of the window", () => {
      vi.useFakeTimers();
      usePortalEditorStore.getState().initialize();

      // Three rapid edits within the debounce window.
      usePortalEditorStore.getState().updateColor("primary", "#aaaaaa");
      vi.advanceTimersByTime(1_000);
      usePortalEditorStore.getState().updateColor("primary", "#bbbbbb");
      vi.advanceTimersByTime(1_000);
      usePortalEditorStore.getState().updateColor("primary", "#cccccc");

      // Not yet — only 2s have elapsed since the last edit.
      expect(localStorage.getItem(PERSIST_KEY)).toBeNull();

      // Advance the final 5s since the last edit to trigger the flush.
      vi.advanceTimersByTime(5_000);
      const parsed = JSON.parse(localStorage.getItem(PERSIST_KEY) as string);
      expect(parsed.state.appearance.colors.primary).toBe("#cccccc");
    });

    it("does not persist isSaving, validationErrors, activeSection, previewMode, or isDirty", () => {
      vi.useFakeTimers();
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().setSaving(true);
      usePortalEditorStore.getState().setActiveSection("typography");
      usePortalEditorStore.getState().setPreviewMode("mobile");
      usePortalEditorStore.setState({
        validationErrors: { layout: [{ field: "test", message: "err" }] },
      });
      usePortalEditorStore.getState().updateColor("primary", "#111111");

      vi.advanceTimersByTime(5_000);

      const parsed = JSON.parse(localStorage.getItem(PERSIST_KEY) as string);
      const persistedState = parsed.state as Record<string, unknown>;
      expect(persistedState).not.toHaveProperty("isSaving");
      expect(persistedState).not.toHaveProperty("validationErrors");
      expect(persistedState).not.toHaveProperty("activeSection");
      expect(persistedState).not.toHaveProperty("previewMode");
      expect(persistedState).not.toHaveProperty("isDirty");
      expect(persistedState).not.toHaveProperty("isInitialized");
      expect(persistedState).not.toHaveProperty("hasRestoredDraft");
      // Sanity: the slices that SHOULD be persisted are present.
      expect(persistedState).toHaveProperty("portalData");
      expect(persistedState).toHaveProperty("appearance");
    });

    it("strips non-serializable logoFile from the persisted portalData", () => {
      vi.useFakeTimers();
      // A real File works in jsdom and is the concrete case we need to
      // neutralize before a JSON write.
      const file = new File(["x"], "logo.png", { type: "image/png" });
      usePortalEditorStore.getState().initialize({
        name: "Portal",
        slug: "portal",
        logoFile: file,
      });

      vi.advanceTimersByTime(5_000);

      const parsed = JSON.parse(localStorage.getItem(PERSIST_KEY) as string);
      expect(parsed.state.portalData.logoFile).toBeNull();
      expect(parsed.state.portalData.name).toBe("Portal");
    });
  });

  describe("draft clearing", () => {
    it("markClean clears the persisted draft", () => {
      vi.useFakeTimers();
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");
      vi.advanceTimersByTime(5_000);
      expect(localStorage.getItem(PERSIST_KEY)).not.toBeNull();

      usePortalEditorStore.getState().markClean();

      expect(localStorage.getItem(PERSIST_KEY)).toBeNull();
    });

    it("markClean clears the hasRestoredDraft flag", () => {
      usePortalEditorStore.setState({ hasRestoredDraft: true });
      usePortalEditorStore.getState().markClean();
      expect(usePortalEditorStore.getState().hasRestoredDraft).toBe(false);
    });

    it("reset clears the persisted draft", () => {
      vi.useFakeTimers();
      usePortalEditorStore.getState().initialize();
      usePortalEditorStore.getState().updateColor("primary", "#abcdef");
      vi.advanceTimersByTime(5_000);
      expect(localStorage.getItem(PERSIST_KEY)).not.toBeNull();

      usePortalEditorStore.getState().reset();

      expect(localStorage.getItem(PERSIST_KEY)).toBeNull();
    });
  });

  describe("rehydration", () => {
    it("onRehydrateStorage flips hasRestoredDraft when a non-empty draft exists", async () => {
      // Seed localStorage with a pre-existing draft, then trigger a
      // manual rehydrate. `persist.rehydrate()` re-runs hydration against
      // the current store instance, which is exactly the flow we want to
      // assert (new page load finds an existing draft).
      localStorage.setItem(
        PERSIST_KEY,
        JSON.stringify({
          state: {
            portalData: { portalId: "p1", name: "Draft portal" },
            appearance: DEFAULT_PORTAL_APPEARANCE,
          },
          version: 0,
        })
      );

      await usePortalEditorStore.persist.rehydrate();

      const state = usePortalEditorStore.getState();
      expect(state.hasRestoredDraft).toBe(true);
      expect(state.isDirty).toBe(true);
      expect(state.portalData?.portalId).toBe("p1");
    });

    it("does NOT flip hasRestoredDraft when no draft exists", async () => {
      // Empty storage path — `getItem` returns `null`, rehydration is a
      // no-op beyond applying the initial state.
      await usePortalEditorStore.persist.rehydrate();

      expect(usePortalEditorStore.getState().hasRestoredDraft).toBe(false);
    });

    it("falls back to fresh state when the persisted value is malformed", async () => {
      localStorage.setItem(PERSIST_KEY, "{not json");

      // This must not throw, per Requirement 14.8.
      await usePortalEditorStore.persist.rehydrate();

      expect(usePortalEditorStore.getState().hasRestoredDraft).toBe(false);
    });

    it("acknowledgeRestoredDraft clears the banner without wiping storage", () => {
      usePortalEditorStore.setState({ hasRestoredDraft: true });
      localStorage.setItem(PERSIST_KEY, JSON.stringify({ state: {}, version: 0 }));

      usePortalEditorStore.getState().acknowledgeRestoredDraft();

      expect(usePortalEditorStore.getState().hasRestoredDraft).toBe(false);
      // The draft itself is intentionally still in storage — the user
      // just dismissed the banner.
      expect(localStorage.getItem(PERSIST_KEY)).not.toBeNull();
    });

    it("initialize clears hasRestoredDraft", () => {
      usePortalEditorStore.setState({ hasRestoredDraft: true });
      usePortalEditorStore.getState().initialize();
      expect(usePortalEditorStore.getState().hasRestoredDraft).toBe(false);
    });
  });
});
