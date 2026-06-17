import { describe, expect, it } from "vitest";
import fc from "fast-check";

import type {
  PortalConfig,
  PortalDestination,
  PortalMetadataField,
  PortalPage,
  PortalPageElement,
} from "@/features/portal/types/portal.types";

import { buildSurveyJson, slug } from "./portalSurveyModel";
import { PORTAL_QUESTION_TYPES } from "./registerPortalQuestions";

/**
 * Property-based (`fast-check`) coverage for the shared SurveyJS schema builder
 * (task 18.1). The example-based determinism/ordering tests live in
 * `portalSurveyModel.test.ts`; this file proves the same invariants hold across
 * ARBITRARY valid `PortalConfig`s.
 *
 * Validates: Requirements 6.3, 6.6
 *
 * Property 8 (schema lockstep / purity): `buildSurveyJson(config)` is a pure,
 * deterministic function of `config` alone — two invocations on the same config
 * produce deep-equal output, the input config is never mutated, and ordering is
 * deterministic (pages sorted ascending by `pageNumber`, element order preserved).
 *
 * Preview-vs-public parity: both the admin preview renderer and the public
 * renderer derive their schema from this ONE builder. "Parity" therefore means
 * the single shared schema is deep-equal to itself across calls and is
 * render-mode-agnostic — the preview-vs-public distinction (display vs edit
 * mode, mock vs live uploader) is applied AT RENDER TIME on the Survey model,
 * never baked into the schema. The schema simply carries the uploader question
 * TYPE (`portal-uppy-uploader`); both paths consume that identical type.
 */

// ---------------------------------------------------------------------------
// Arbitraries — generate structurally-valid PortalConfig values
// ---------------------------------------------------------------------------

/**
 * A label whose {@link slug} is non-empty. Drawn from a small alphabet (letters,
 * digits, spaces) so slugification exercises the collapse/trim logic while
 * staying cheap to generate and shrink.
 */
const labelArb: fc.Arbitrary<string> = fc
  .array(fc.constantFrom("a", "b", "c", "d", "e", "f", "g", "h", "1", "2", " "), {
    minLength: 1,
    maxLength: 10,
  })
  .map((chars) => chars.join(""))
  .filter((label) => slug(label).length > 0);

/** Choice list for `select` metadata fields. */
const optionsArb: fc.Arbitrary<string[]> = fc.array(fc.constantFrom("NA", "EU", "APAC", "X", "Y"), {
  minLength: 1,
  maxLength: 4,
});

/**
 * Build a metadata-field set whose `slug(label)` keys are unique (so every
 * `metadata-field` element resolves to exactly one field) and each field is
 * assigned to a real page (`pageNumber` in `[1..pageCount]`).
 */
const fieldsArb = (pageCount: number): fc.Arbitrary<PortalMetadataField[]> =>
  fc
    .uniqueArray(
      fc.record({
        label: labelArb,
        type: fc.constantFrom<PortalMetadataField["type"]>("text", "number", "select"),
        required: fc.boolean(),
        options: optionsArb,
        pageNumber: fc.integer({ min: 1, max: pageCount }),
      }),
      { selector: (f) => slug(f.label), minLength: 0, maxLength: 6 }
    )
    .map((fields) =>
      fields.map(
        (f, index): PortalMetadataField => ({
          label: f.label,
          type: f.type,
          required: f.required,
          order: index,
          // `options` is only meaningful for `select`; mirror real configs by
          // omitting it otherwise.
          ...(f.type === "select" ? { options: f.options } : {}),
          pageNumber: f.pageNumber,
        })
      )
    );

/**
 * Build a destination set with unique `destinationId`s, each referencing a real
 * page. Destinations are not consumed by {@link buildSurveyJson} (the schema
 * emits a generic `destination-selector` question), so this mainly guards that
 * extra config never leaks into / mutates the schema.
 */
const destinationsArb = (pageCount: number): fc.Arbitrary<PortalDestination[]> =>
  fc
    .array(
      fc.record({
        allowBrowsing: fc.boolean(),
        allowFolderCreation: fc.boolean(),
        pageNumber: fc.integer({ min: 1, max: pageCount }),
      }),
      { maxLength: 3 }
    )
    .map((arr) =>
      arr.map(
        (d, index): PortalDestination => ({
          destinationId: `dest-${index}`,
          friendlyName: `Destination ${index}`,
          allowBrowsing: d.allowBrowsing,
          allowFolderCreation: d.allowFolderCreation,
          order: index,
          pageNumber: d.pageNumber,
        })
      )
    );

/** Per-page flags toggling the optional built-in (non-uploader) elements. */
const pageExtrasArb = (pageCount: number) =>
  fc.array(
    fc.record({
      hasDestinationSelector: fc.boolean(),
      hasPathBrowser: fc.boolean(),
      hasPathBuilder: fc.boolean(),
    }),
    { minLength: pageCount, maxLength: pageCount }
  );

/**
 * Generate an arbitrary structurally-valid {@link PortalConfig}:
 *   - `pageCount` contiguous pages numbered 1..N (1 ≤ N ≤ 5),
 *   - `metadata-field` elements referencing real (slug-unique) field keys,
 *   - optional `destination-selector` / `path-browser` / `path-builder` elements,
 *   - EXACTLY ONE `uploader` element across all pages,
 *   - destinations whose `pageNumber`s reference real pages.
 *
 * The final `pages` array is a full random permutation of the natural 1..N
 * order so the builder's ascending-by-`pageNumber` sort is exercised on inputs
 * that arrive out of order.
 */
const arbConfig: fc.Arbitrary<PortalConfig> = fc.integer({ min: 1, max: 5 }).chain((pageCount) =>
  fc
    .record({
      fields: fieldsArb(pageCount),
      destinations: destinationsArb(pageCount),
      uploaderPage: fc.integer({ min: 1, max: pageCount }),
      extras: pageExtrasArb(pageCount),
    })
    .chain(({ fields, destinations, uploaderPage, extras }) => {
      // Pages in natural ascending order; shuffled below.
      const pagesInOrder: PortalPage[] = Array.from({ length: pageCount }, (_, idx) => {
        const pageNumber = idx + 1;
        const elements: PortalPageElement[] = [];

        // Metadata-field elements for fields assigned to this page, in field
        // order. Each references a real, slug-unique field key.
        for (const field of fields) {
          if (field.pageNumber === pageNumber) {
            elements.push({ kind: "metadata-field", fieldKey: slug(field.label) });
          }
        }

        const extra = extras[idx];
        if (extra.hasDestinationSelector) {
          elements.push({ kind: "destination-selector" });
        }
        if (extra.hasPathBrowser) elements.push({ kind: "path-browser" });
        if (extra.hasPathBuilder) elements.push({ kind: "path-builder" });

        // Exactly one uploader across all pages.
        if (pageNumber === uploaderPage) elements.push({ kind: "uploader" });

        return { pageNumber, title: `Page ${pageNumber}`, elements };
      });

      return fc
        .shuffledSubarray(pagesInOrder, {
          minLength: pagesInOrder.length,
          maxLength: pagesInOrder.length,
        })
        .map(
          (shuffledPages): PortalConfig => ({
            slug: "demo",
            name: "Demo Portal",
            accessMode: "public",
            tokenBypassesPassphrase: false,
            isActive: true,
            structuredPathMode: false,
            captchaEnabled: false,
            metadataFields: fields,
            destinations,
            pages: shuffledPages,
          })
        );
    })
);

// ---------------------------------------------------------------------------
// Property 8 — determinism / purity
// ---------------------------------------------------------------------------

describe("buildSurveyJson — Property 8: determinism & purity (Req 6.3)", () => {
  it("produces deep-equal output for the same config across invocations", () => {
    fc.assert(
      fc.property(arbConfig, (cfg) => {
        expect(buildSurveyJson(cfg)).toEqual(buildSurveyJson(cfg));
      }),
      { numRuns: 100 }
    );
  });

  it("never mutates the input config", () => {
    fc.assert(
      fc.property(arbConfig, (cfg) => {
        const before = structuredClone(cfg);
        buildSurveyJson(cfg);
        expect(cfg).toEqual(before);
      }),
      { numRuns: 100 }
    );
  });

  it("orders output pages ascending by source pageNumber regardless of input order", () => {
    fc.assert(
      fc.property(arbConfig, (cfg) => {
        const result = buildSurveyJson(cfg);

        // Expected names = source pageNumbers sorted ascending → page-{n}.
        const expectedNames = cfg.pages
          .map((p) => p.pageNumber)
          .sort((a, b) => a - b)
          .map((n) => `page-${n}`);
        expect(result.pages.map((p) => p.name)).toEqual(expectedNames);

        // The extracted numeric page numbers are non-decreasing.
        const numbers = result.pages.map((p) => Number(p.name.replace("page-", "")));
        const sorted = [...numbers].sort((a, b) => a - b);
        expect(numbers).toEqual(sorted);
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Preview-vs-public parity — one shared, render-mode-agnostic schema
// ---------------------------------------------------------------------------

describe("buildSurveyJson — preview/public parity (Req 6.6)", () => {
  it("yields one deep-equal schema both render paths consume, carrying the uploader type", () => {
    fc.assert(
      fc.property(arbConfig, (cfg) => {
        // Both renderers derive their schema from this single builder. Building
        // it for "preview" and for "public" must yield the identical schema —
        // the two paths differ only in render mode (display vs edit) and
        // uploader (mock vs live), applied at render time, never in the schema.
        const previewSchema = buildSurveyJson(cfg);
        const publicSchema = buildSurveyJson(cfg);
        expect(previewSchema).toEqual(publicSchema);

        // Render-mode-agnostic: the schema carries the uploader question TYPE
        // (`portal-uppy-uploader`) — the mock-vs-live distinction is the
        // renderer, not the schema. There is exactly one uploader question.
        const uploaderQuestions = previewSchema.pages
          .flatMap((p) => p.elements)
          .filter((q) => q.type === PORTAL_QUESTION_TYPES.uploader);
        expect(uploaderQuestions).toHaveLength(1);

        // The schema never encodes a render mode/uploader flavor — questions
        // expose only their declarative shape (type/name and optional config).
        for (const question of previewSchema.pages.flatMap((p) => p.elements)) {
          expect(question).not.toHaveProperty("mode");
          expect(question).not.toHaveProperty("uploader");
        }
      }),
      { numRuns: 100 }
    );
  });
});
