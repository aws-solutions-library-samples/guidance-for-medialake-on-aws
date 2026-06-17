import { describe, expect, it } from "vitest";
import fc from "fast-check";

import { portalAppearanceSchema } from "../schemas/appearance.schema";
import type { PortalAppearance } from "../types/appearance.types";
import type { EditorSection, PreviewMode } from "./usePortalEditorStore";
import { usePortalEditorStore } from "./usePortalEditorStore";

/**
 * Validates: Requirements 21.9, 21.13
 *
 * Property 9: Dirty-flag monotonicity.
 *
 *   After `initialize(...)`, any subsequent `update*()` action SHALL set
 *   `isDirty = true`, and `markClean()` SHALL be the only action that can
 *   set `isDirty = false`.
 *
 * In addition to the core two-way implication, we assert that the
 * "dirty-preserving" UI controls (`setSaving`, `setActiveSection`,
 * `setPreviewMode`, `clearSectionErrors`) never flip `isDirty` in either
 * direction — i.e. they leave the dirty flag exactly as they found it. This
 * rules out a class of regressions where, say, `setPreviewMode` accidentally
 * marks the store dirty or clean as a side effect.
 */
describe("Feature: portal-visual-editor, Property 9: Dirty-flag monotonicity", () => {
  // ---- Action tags & generators -------------------------------------------

  // Dirty-setting actions: every call SHALL leave `isDirty === true`.
  type DirtyAction =
    | { tag: "updateColor"; key: "primary" | "accent" | "border"; value: string }
    | { tag: "updateTypography"; baseFontSize: number }
    | { tag: "updateLayout"; cardMaxWidth: number }
    | { tag: "updateBranding"; logoSize: number }
    | { tag: "updateContent"; submitButtonText: string }
    | { tag: "updateAppearance"; mode: "light" | "dark" }
    | { tag: "resetAppearanceToDefaults" };

  // Cleaning action: SHALL leave `isDirty === false`.
  type CleanAction = { tag: "markClean" };

  // Neutral actions: SHALL NOT flip `isDirty` in either direction.
  type NeutralAction =
    | { tag: "setSaving"; value: boolean }
    | { tag: "setActiveSection"; section: EditorSection }
    | { tag: "setPreviewMode"; mode: PreviewMode }
    | { tag: "clearSectionErrors"; section: EditorSection };

  type Action = DirtyAction | CleanAction | NeutralAction;

  const sectionArb: fc.Arbitrary<EditorSection> = fc.constantFrom<EditorSection>(
    "branding",
    "content",
    "appearance",
    "typography",
    "layout",
    "access",
    "destinations",
    "metadata",
    "pages",
    "fields"
  );

  const previewArb: fc.Arbitrary<PreviewMode> = fc.constantFrom<PreviewMode>(
    "desktop",
    "tablet",
    "mobile"
  );

  // Hex-like strings are fine here — the store doesn't validate color syntax,
  // and Property 9 is independent of the color value.
  const hexColorArb = fc
    .integer({ min: 0, max: 0xffffff })
    .map((n) => `#${n.toString(16).padStart(6, "0")}`);

  const dirtyActionArb: fc.Arbitrary<DirtyAction> = fc.oneof(
    fc.record({
      tag: fc.constant("updateColor" as const),
      key: fc.constantFrom("primary" as const, "accent" as const, "border" as const),
      value: hexColorArb,
    }),
    fc.record({
      tag: fc.constant("updateTypography" as const),
      baseFontSize: fc.integer({ min: 12, max: 24 }),
    }),
    fc.record({
      tag: fc.constant("updateLayout" as const),
      cardMaxWidth: fc.integer({ min: 400, max: 1200 }),
    }),
    fc.record({
      tag: fc.constant("updateBranding" as const),
      logoSize: fc.integer({ min: 24, max: 120 }),
    }),
    fc.record({
      tag: fc.constant("updateContent" as const),
      submitButtonText: fc.string({ minLength: 1, maxLength: 50 }),
    }),
    fc.record({
      tag: fc.constant("updateAppearance" as const),
      mode: fc.constantFrom("light" as const, "dark" as const),
    }),
    fc.record({
      tag: fc.constant("resetAppearanceToDefaults" as const),
    })
  );

  const cleanActionArb: fc.Arbitrary<CleanAction> = fc.record({
    tag: fc.constant("markClean" as const),
  });

  const neutralActionArb: fc.Arbitrary<NeutralAction> = fc.oneof(
    fc.record({
      tag: fc.constant("setSaving" as const),
      value: fc.boolean(),
    }),
    fc.record({
      tag: fc.constant("setActiveSection" as const),
      section: sectionArb,
    }),
    fc.record({
      tag: fc.constant("setPreviewMode" as const),
      mode: previewArb,
    }),
    fc.record({
      tag: fc.constant("clearSectionErrors" as const),
      section: sectionArb,
    })
  );

  const actionArb: fc.Arbitrary<Action> = fc.oneof(
    dirtyActionArb,
    cleanActionArb,
    neutralActionArb
  );

  const applyAction = (action: Action): void => {
    const store = usePortalEditorStore.getState();
    switch (action.tag) {
      case "updateColor":
        store.updateColor(action.key, action.value);
        return;
      case "updateTypography":
        store.updateTypography({ baseFontSize: action.baseFontSize });
        return;
      case "updateLayout":
        store.updateLayout({ cardMaxWidth: action.cardMaxWidth });
        return;
      case "updateBranding":
        store.updateBranding({ logoSize: action.logoSize });
        return;
      case "updateContent":
        store.updateContent({ submitButtonText: action.submitButtonText });
        return;
      case "updateAppearance":
        store.updateAppearance({ mode: action.mode });
        return;
      case "resetAppearanceToDefaults":
        store.resetAppearanceToDefaults();
        return;
      case "markClean":
        store.markClean();
        return;
      case "setSaving":
        store.setSaving(action.value);
        return;
      case "setActiveSection":
        store.setActiveSection(action.section);
        return;
      case "setPreviewMode":
        store.setPreviewMode(action.mode);
        return;
      case "clearSectionErrors":
        store.clearSectionErrors(action.section);
        return;
    }
  };

  // ---- The property --------------------------------------------------------

  it("after initialize(), every action leaves isDirty in the expected state", () => {
    fc.assert(
      fc.property(fc.array(actionArb, { minLength: 0, maxLength: 30 }), (actions) => {
        // Each property run starts from a freshly initialized store.
        usePortalEditorStore.getState().reset();
        usePortalEditorStore.getState().initialize();

        // Baseline after initialize: the store must be clean.
        expect(usePortalEditorStore.getState().isDirty).toBe(false);

        for (const action of actions) {
          const dirtyBefore = usePortalEditorStore.getState().isDirty;

          applyAction(action);

          const dirtyAfter = usePortalEditorStore.getState().isDirty;

          switch (action.tag) {
            case "updateColor":
            case "updateTypography":
            case "updateLayout":
            case "updateBranding":
            case "updateContent":
            case "updateAppearance":
            case "resetAppearanceToDefaults":
              // Monotonicity (forward direction): any update* action sets
              // isDirty to true, regardless of the prior value.
              expect(dirtyAfter).toBe(true);
              break;
            case "markClean":
              // Monotonicity (reverse direction): markClean is the ONLY
              // action allowed to flip the flag from true to false.
              expect(dirtyAfter).toBe(false);
              break;
            case "setSaving":
            case "setActiveSection":
            case "setPreviewMode":
            case "clearSectionErrors":
              // Neutral actions preserve the dirty flag exactly — they must
              // never set it to true, and they must never clear it.
              expect(dirtyAfter).toBe(dirtyBefore);
              break;
          }
        }
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Validates: Requirements 21.8, 21.13
 *
 * Property 8: Validation payload round-trip.
 *
 *   Given a store that has been initialized with a valid `portalData` +
 *   `appearance`, feeding `store.getPayload().appearance` back through
 *   `portalAppearanceSchema.parse(...)` must produce a structurally equal
 *   value. In other words, the payload serialization path is lossless —
 *   parse ∘ getPayload ≡ getPayload on the appearance slice.
 *
 * Why this matters: `getPayload()` is the single choke-point between
 * in-memory editor state and the wire payload we POST/PUT to the backend.
 * If it silently mutated the appearance (reordered keys, stripped a
 * field, rounded a number), a save that passed client-side validation
 * would still be rejected or corrupted server-side. We reuse the valid
 * appearance arbitrary from `createPortalTheme.pbt.test.ts` (which is
 * already schema-consistent) so every generated example is a legitimate
 * piece of editor state.
 */
describe("Feature: portal-visual-editor, Property 8: Validation payload round-trip", () => {
  // Valid arbitraries mirroring the schema bounds. Kept local rather than
  // importing from the theme PBT file so this test stays self-contained
  // and the two suites can evolve independently.
  const colorArb = fc.constantFrom(
    "#ff0000",
    "#00ff00",
    "#0000ff",
    "#2B6CB0",
    "#1a202c",
    "#f0f4f8",
    "#ffffff",
    "#e2e8f0"
  );

  const familyArb = fc.constantFrom("Inter", "Roboto", "System Default");

  const appearanceArb: fc.Arbitrary<PortalAppearance> = fc.record({
    mode: fc.constantFrom("light", "dark") as fc.Arbitrary<"light" | "dark">,
    colors: fc.record({
      primary: colorArb,
      background: colorArb,
      cardBackground: colorArb,
      textPrimary: colorArb,
      textSecondary: colorArb,
      border: colorArb,
      accent: colorArb,
    }),
    typography: fc.record({
      headingFontFamily: familyArb,
      bodyFontFamily: familyArb,
      baseFontSize: fc.integer({ min: 12, max: 24 }),
      headingFontWeight: fc.constantFrom(400, 500, 600, 700, 800, 900),
    }),
    layout: fc.record({
      cardMaxWidth: fc.integer({ min: 400, max: 1200 }),
      cardBorderRadius: fc.integer({ min: 0, max: 32 }),
      cardShadow: fc.constantFrom("none", "sm", "md", "lg") as fc.Arbitrary<
        "none" | "sm" | "md" | "lg"
      >,
      cardPadding: fc.integer({ min: 16, max: 64 }),
      cardBorder: fc.boolean(),
      pageVerticalPadding: fc.integer({ min: 0, max: 120 }),
    }),
    branding: fc.record({
      showLogo: fc.boolean(),
      logoSize: fc.integer({ min: 24, max: 120 }),
      logoAlignment: fc.constantFrom("left", "center") as fc.Arbitrary<"left" | "center">,
      showPoweredBy: fc.boolean(),
      bannerHeight: fc.integer({ min: 0, max: 400 }),
    }),
    content: fc.record({
      titleHtml: fc.string({ maxLength: 100 }),
      descriptionHtml: fc.string({ maxLength: 100 }),
      submitButtonText: fc.string({ minLength: 1, maxLength: 50 }),
      footerHtml: fc.string({ maxLength: 100 }),
      successMessage: fc.string({ maxLength: 100 }),
      dropZoneText: fc.string({ maxLength: 100 }),
      buttonStyle: fc.constantFrom("contained", "outlined", "text") as fc.Arbitrary<
        "contained" | "outlined" | "text"
      >,
      buttonRounding: fc.constantFrom("square", "rounded", "pill") as fc.Arbitrary<
        "square" | "rounded" | "pill"
      >,
    }),
  });

  it("getPayload().appearance round-trips through portalAppearanceSchema.parse", () => {
    fc.assert(
      fc.property(appearanceArb, (appearance) => {
        // Start from a freshly reset store, then seed it with enough
        // portalData to satisfy getPayload's defaults without triggering
        // validate(). getPayload does not invoke validate; it only needs a
        // valid appearance to satisfy the schema round-trip.
        usePortalEditorStore.getState().reset();
        usePortalEditorStore.getState().initialize({
          name: "Portal",
          slug: "portal",
          appearance,
        });

        const payload = usePortalEditorStore.getState().getPayload();

        // The schema must accept the payload's appearance unchanged — any
        // lossy transform (key drop, number coercion, default injection)
        // would be visible either as a parse failure or a diff here.
        const parsed = portalAppearanceSchema.parse(payload.appearance);

        expect(parsed).toEqual(payload.appearance);
      }),
      { numRuns: 100 }
    );
  });
});
