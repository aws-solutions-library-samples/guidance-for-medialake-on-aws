import { beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";

import type {
  PortalDestination,
  PortalMetadataField,
  PortalPage,
  PortalPageElement,
  PortalTemplate,
} from "@/api/types/api.types";

import type { PortalAppearance } from "../types/appearance.types";
import { usePortalEditorStore } from "./usePortalEditorStore";

/**
 * Property-based test for Property 11 (Snapshot independence).
 *
 * Validates: Requirements 16.3, 17.5, 17.6 (and the design's Property 11,
 * Requirements 17.4, 17.5).
 *
 * Property 11 — Snapshot independence:
 *   For any template `T` and any portal `P` created from `T` via
 *   `initializeFromSources({ template: T })`, the seed is a copy-on-create
 *   SNAPSHOT with NO live link back to `T`. Formally, over arbitrary templates:
 *
 *     (A) editing `T` AFTER the seed leaves the store's seeded portal unchanged
 *         (`∀ T,P=createFrom(T): edit(T) ⇒ P unchanged`); and
 *     (B) editing the store AFTER the seed leaves the source `T` unchanged.
 *
 * Task 17.2 already covers this with hand-written EXAMPLE tests
 * (`usePortalEditorStore.initializeFromSources.test.ts`). This file adds the
 * universal fast-check property over arbitrary valid-ish templates: a generated
 * template has contiguous pages 1..N, exactly one uploader (on the last page),
 * metadata fields / destinations whose `pageNumber` references a real page, and
 * a nested `appearance` object — so the deep-clone seed boundary is exercised
 * across the whole structure (arrays, nested objects, and scalar settings).
 */

// ---------------------------------------------------------------------------
// Arbitraries — generate an arbitrary VALID-ish template.
// ---------------------------------------------------------------------------

const hexColorArb: fc.Arbitrary<string> = fc
  .integer({ min: 0, max: 0xffffff })
  .map((n) => `#${n.toString(16).padStart(6, "0")}`);

const fieldTypeArb = fc.constantFrom<PortalMetadataField["type"]>("text", "number", "select");

const accessModeArb = fc.constantFrom<NonNullable<PortalTemplate["accessMode"]>>(
  "public",
  "token-protected",
  "cognito-groups"
);

/**
 * A nested partial appearance. It need not be a complete `PortalAppearance`
 * (the store deep-merges it onto `DEFAULT_PORTAL_APPEARANCE`), but the nesting
 * — `colors` plus an optional `branding` sub-object — is what makes the
 * deep-clone boundary meaningful (a shallow copy would alias these objects).
 */
const appearanceArb: fc.Arbitrary<PortalAppearance> = fc
  .record({
    colors: fc.record({
      primary: hexColorArb,
      accent: hexColorArb,
      background: hexColorArb,
    }),
    branding: fc.record({
      logoSize: fc.integer({ min: 24, max: 120 }),
      showPoweredBy: fc.boolean(),
    }),
  })
  .map((a) => a as unknown as PortalAppearance);

/**
 * Generate a structurally coherent template:
 *  - `pageCount` pages numbered 1..N (contiguous);
 *  - metadata fields each assigned to a real page, surfaced as `metadata-field`
 *    elements on that page;
 *  - the single uploader element lives on the LAST page;
 *  - destinations each reference a real page.
 */
const templateArb: fc.Arbitrary<PortalTemplate> = fc
  .record({
    pageCount: fc.integer({ min: 1, max: 5 }),
    fieldCount: fc.integer({ min: 0, max: 4 }),
    destCount: fc.integer({ min: 1, max: 3 }),
    appearance: appearanceArb,
    accessMode: accessModeArb,
    allowedGroups: fc.array(fc.string({ minLength: 1, maxLength: 8 }), { maxLength: 3 }),
    ipAllowlist: fc.array(fc.string({ minLength: 1, maxLength: 12 }), { maxLength: 3 }),
    tokenBypassesPassphrase: fc.boolean(),
    structuredPathMode: fc.boolean(),
    captchaEnabled: fc.boolean(),
    maxFileSizeBytes: fc.integer({ min: 1, max: 1_000_000 }),
    maxFilesPerSession: fc.integer({ min: 1, max: 50 }),
  })
  .chain((cfg) => {
    const pageNumbers = Array.from({ length: cfg.pageCount }, (_, i) => i + 1);

    // Assign each metadata field to a random real page.
    return fc
      .record({
        fieldPages: fc.array(fc.constantFrom(...pageNumbers), {
          minLength: cfg.fieldCount,
          maxLength: cfg.fieldCount,
        }),
        destPages: fc.array(fc.constantFrom(...pageNumbers), {
          minLength: cfg.destCount,
          maxLength: cfg.destCount,
        }),
      })
      .map(({ fieldPages, destPages }) => {
        const metadataFields: PortalMetadataField[] = fieldPages.map((pageNumber, i) => ({
          label: `Field ${i}`,
          type: "text",
          required: i % 2 === 0,
          order: i + 1,
          pageNumber,
        }));

        const lastPage = cfg.pageCount;
        const pages: PortalPage[] = pageNumbers.map((pageNumber) => {
          const elements: PortalPageElement[] = metadataFields
            .filter((f) => f.pageNumber === pageNumber)
            .map((f) => ({ kind: "metadata-field", fieldKey: `field_${f.order}` }));
          if (pageNumber === lastPage) {
            elements.push({ kind: "uploader" });
          }
          return { pageNumber, title: `Page ${pageNumber}`, elements };
        });

        const destinations: PortalDestination[] = destPages.map((pageNumber, i) => ({
          destinationId: `dest-${i}`,
          friendlyName: `Destination ${i}`,
          connectorId: `connector-${i}`,
          rootPath: `/incoming/${i}`,
          allowBrowsing: i % 2 === 0,
          allowFolderCreation: i % 3 === 0,
          order: i + 1,
          pageNumber,
        }));

        const template: PortalTemplate = {
          templateId: "tpl-prop",
          name: "Property template",
          pages,
          metadataFields,
          destinations,
          appearance: cfg.appearance,
          accessMode: cfg.accessMode,
          allowedGroups: cfg.allowedGroups,
          ipAllowlist: cfg.ipAllowlist,
          tokenBypassesPassphrase: cfg.tokenBypassesPassphrase,
          structuredPathMode: cfg.structuredPathMode,
          captchaEnabled: cfg.captchaEnabled,
          maxFileSizeBytes: cfg.maxFileSizeBytes,
          maxFilesPerSession: cfg.maxFilesPerSession,
        };
        return template;
      });
  });

// ---------------------------------------------------------------------------
// Mutators — deeply mutate a template / the store in place.
// ---------------------------------------------------------------------------

/**
 * Mutate every reachable part of a template object IN PLACE: scalars, arrays
 * (push + element edits), nested page elements, destinations, and the nested
 * appearance. If the store aliased ANY of these at seed time, the seeded
 * portal would change — which is exactly what Property 11 forbids.
 */
const mutateTemplateDeeply = (template: PortalTemplate): void => {
  template.name = "MUTATED NAME";
  template.accessMode = "public";
  template.tokenBypassesPassphrase = !template.tokenBypassesPassphrase;
  template.maxFileSizeBytes = (template.maxFileSizeBytes ?? 0) + 999;

  template.allowedGroups?.push("MUTATED_GROUP");
  template.ipAllowlist?.push("255.255.255.255");

  template.pages?.forEach((page) => {
    page.title = "MUTATED PAGE";
    page.pageNumber = page.pageNumber + 1000;
    page.elements.push({ kind: "destination-selector" });
    page.elements.forEach((el) => {
      if (el.kind === "metadata-field") el.fieldKey = "MUTATED_KEY";
    });
  });
  template.pages?.push({ pageNumber: 999, title: "ADDED", elements: [] });

  template.metadataFields?.forEach((f) => {
    f.label = "MUTATED LABEL";
    f.pageNumber = (f.pageNumber ?? 0) + 1000;
  });
  template.metadataFields?.push({
    label: "ADDED FIELD",
    type: "select",
    required: true,
    order: 999,
    pageNumber: 999,
  });

  template.destinations?.forEach((d) => {
    d.connectorId = "MUTATED_CONNECTOR";
    d.pageNumber = (d.pageNumber ?? 0) + 1000;
  });

  const appearance = template.appearance as unknown as {
    colors: { primary: string };
    branding: { logoSize: number };
  };
  appearance.colors.primary = "#000000";
  appearance.branding.logoSize = -1;
};

// ---------------------------------------------------------------------------
// Properties
// ---------------------------------------------------------------------------

describe("Feature: multi-page-upload-portals, Property 11: snapshot independence", () => {
  beforeEach(() => {
    usePortalEditorStore.getState().reset();
  });

  it("editing the source template AFTER initializeFromSources leaves the seeded portal unchanged", () => {
    fc.assert(
      fc.property(templateArb, (template) => {
        usePortalEditorStore.getState().reset();
        usePortalEditorStore.getState().initializeFromSources({ template });

        // Capture the seeded structure + appearance immediately after seeding.
        const seededPortalData = structuredClone(usePortalEditorStore.getState().portalData);
        const seededAppearance = structuredClone(usePortalEditorStore.getState().appearance);

        // Now deeply mutate the SOURCE template.
        mutateTemplateDeeply(template);

        // The store's seeded portal must be byte-for-byte what it was at seed
        // time — no aliasing read-through to the mutated template.
        expect(usePortalEditorStore.getState().portalData).toEqual(seededPortalData);
        expect(usePortalEditorStore.getState().appearance).toEqual(seededAppearance);
      }),
      { numRuns: 100 }
    );
  });

  it("editing the store AFTER initializeFromSources leaves the source template unchanged", () => {
    fc.assert(
      fc.property(templateArb, (template) => {
        // Snapshot the template BEFORE seeding so we can prove no store action
        // ever wrote back into it.
        const templateSnapshot = structuredClone(template);

        usePortalEditorStore.getState().reset();
        usePortalEditorStore.getState().initializeFromSources({ template });

        const store = usePortalEditorStore.getState();

        // Mutate appearance via a store action.
        store.updateColor("primary", "#abcdef");

        // Replace the destinations slice with an extended copy (the access /
        // destinations sections do exactly this via updatePortalData).
        const currentDestinations = (store.portalData?.destinations ?? []) as PortalDestination[];
        store.updatePortalData({
          destinations: [
            ...currentDestinations,
            {
              destinationId: "dest-added",
              friendlyName: "Added",
              connectorId: "added",
              rootPath: "/added",
              allowBrowsing: false,
              allowFolderCreation: false,
              order: currentDestinations.length + 1,
              pageNumber: 1,
            },
          ],
        });

        // Append a page and edit an existing one via the page actions.
        usePortalEditorStore.getState().addPage();
        usePortalEditorStore.getState().updatePage(1, { title: "Edited in store" });

        // The source template is untouched by every store mutation above.
        expect(template).toEqual(templateSnapshot);
      }),
      { numRuns: 100 }
    );
  });
});
