/**
 * Portal Pages Runtime Validation Schema
 *
 * Runtime validation surface for the multi-page portal `pages` structure.
 * The persisted `pages` array is the source of truth for portal structure;
 * the SurveyJS schema is derived from it at render time. Every `pages` value
 * that crosses a trust boundary (editor save path, API request) should pass
 * through these schemas before being treated as a trusted, typed
 * `PortalPage[]`.
 *
 * The schemas mirror the TypeScript interfaces `PortalPage` /
 * `PortalPageElement` in `../../../portal/types/portal.types.ts`; the two
 * must stay in lockstep. The `_schemaMatchesInterface` assertions at the
 * bottom of this file are the compile-time guards that enforce that lockstep.
 *
 * ## Structural invariants
 *
 * Three whole-array invariants mirror the server-side `_validate_portal_structure`
 * check (see design.md):
 *
 *   1. `pageNumber` values form the contiguous sequence 1..N (no gaps, no
 *      duplicates).
 *   2. Exactly one `uploader` element exists across all pages.
 *   3. Every `metadata-field` element references a real field key.
 *
 * Invariants 1 and 2 are self-contained within the `pages` array and are
 * enforced by {@link portalPagesSchema}'s `superRefine`. Invariant 3 needs the
 * set of valid field keys, which lives *outside* the `pages` array (on the
 * portal's `metadataFields`). It is therefore enforced by the factory
 * {@link portalPagesSchemaWithFieldKeys}, which closes over the valid key set,
 * or by the standalone {@link validateMetadataFieldRefs} helper. The editor
 * store (and anywhere else with access to the field keys) should prefer
 * `portalPagesSchemaWithFieldKeys(validFieldKeys)` so all three invariants are
 * checked in a single `safeParse`.
 */

import { z } from "zod";

import type { PortalPage, PortalPageElement } from "../../../portal/types/portal.types";

/** Max length for a page title (mirrors design / SurveyJS page title). */
export const PAGE_TITLE_MAX = 120;
/** Max length for a page's sanitized HTML description. */
export const PAGE_DESCRIPTION_HTML_MAX = 10000;
/** Max length for a page's SurveyJS `visibleIf` expression. */
export const PAGE_VISIBLE_IF_MAX = 1000;

/**
 * One ordered element placement on a page. Discriminated on `kind`:
 * a `metadata-field` element references a metadata field by `fieldKey`; the
 * other kinds map to the built-in destination selector, path questions, and
 * uploader question types. Mirrors `PortalPageElement`.
 */
export const portalPageElementSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("metadata-field"), fieldKey: z.string().min(1) }),
  z.object({ kind: z.literal("destination-selector") }),
  z.object({ kind: z.literal("path-browser") }),
  z.object({ kind: z.literal("path-builder") }),
  z.object({ kind: z.literal("uploader") }),
]);

/** A single page in a multi-page portal flow. Mirrors `PortalPage`. */
export const portalPageSchema = z.object({
  pageNumber: z.number().int().positive(),
  title: z.string().min(1).max(PAGE_TITLE_MAX),
  descriptionHtml: z.string().max(PAGE_DESCRIPTION_HTML_MAX).optional(),
  visibleIf: z.string().max(PAGE_VISIBLE_IF_MAX).optional(),
  elements: z.array(portalPageElementSchema),
});

/**
 * Enforces the contiguous-`pageNumber` invariant on a list of pages. Reports
 * a single descriptive issue (identifying the offending values) when the
 * `pageNumber` values do not form the sequence 1..N.
 *
 * Exported so callers can reuse the exact contiguity check independently of
 * the full array schema.
 */
export function refineContiguousPageNumbers(
  pages: ReadonlyArray<{ pageNumber: number }>,
  ctx: z.RefinementCtx
): void {
  const sorted = pages.map((p) => p.pageNumber).sort((a, b) => a - b);
  const isContiguous = sorted.every((n, i) => n === i + 1);
  if (!isContiguous) {
    ctx.addIssue({
      code: "custom",
      message: `Page numbers must form the contiguous sequence 1..${
        pages.length
      } with no gaps or duplicates (got ${sorted.join(",")})`,
      path: ["pageNumber"],
    });
  }
}

/**
 * Enforces the single-uploader invariant: exactly one `uploader` element must
 * exist across all pages. Reports a descriptive issue when zero or two or more
 * uploader elements are present.
 *
 * Exported so callers can reuse the exact uploader check independently.
 */
export function refineSingleUploader(
  pages: ReadonlyArray<{ elements: ReadonlyArray<{ kind: string }> }>,
  ctx: z.RefinementCtx
): void {
  const uploaderCount = pages
    .flatMap((p) => p.elements)
    .filter((e) => e.kind === "uploader").length;
  if (uploaderCount !== 1) {
    ctx.addIssue({
      code: "custom",
      message: `Exactly one page must host the uploader element (found ${uploaderCount})`,
      path: ["elements"],
    });
  }
}

/**
 * Enforces the metadata-field-reference invariant: every `metadata-field`
 * element must reference a field key present in `validFieldKeys`. Reports one
 * issue per dangling reference, identifying the offending key.
 *
 * Exported (and usable standalone) because the set of valid field keys lives
 * outside the `pages` array, so callers that have the keys can run this check
 * directly, while callers without them can validate the rest of the structure
 * via {@link portalPagesSchema} and run this check separately.
 */
export function refineMetadataFieldRefs(
  pages: ReadonlyArray<{ elements: ReadonlyArray<PortalPageElement> }>,
  validFieldKeys: ReadonlySet<string>,
  ctx: z.RefinementCtx
): void {
  pages.forEach((page, pageIndex) => {
    page.elements.forEach((element, elementIndex) => {
      if (element.kind === "metadata-field" && !validFieldKeys.has(element.fieldKey)) {
        ctx.addIssue({
          code: "custom",
          message: `metadata-field element references unknown field key "${element.fieldKey}"`,
          path: [pageIndex, "elements", elementIndex, "fieldKey"],
        });
      }
    });
  });
}

/**
 * Whole-array schema enforcing the two self-contained structural invariants:
 *
 *   - `pageNumber` values are contiguous from 1.
 *   - Exactly one `uploader` element exists across all pages.
 *
 * The metadata-field-reference invariant requires the valid field key set and
 * is enforced by {@link portalPagesSchemaWithFieldKeys}. Use this schema when
 * the field keys are not available in the calling context.
 */
export const portalPagesSchema = z.array(portalPageSchema).superRefine((pages, ctx) => {
  refineContiguousPageNumbers(pages, ctx);
  refineSingleUploader(pages, ctx);
});

/**
 * Build a `pages` array schema that enforces ALL THREE structural invariants:
 * contiguous page numbers, exactly one uploader, and every `metadata-field`
 * element referencing a real field key from `validFieldKeys`.
 *
 * The field keys live outside the `pages` array (on the portal's
 * `metadataFields`), so they are supplied here and closed over. The editor
 * store should call this with its current set of field keys so a single
 * `safeParse` validates the full structure.
 *
 * @param validFieldKeys Iterable of field keys that `metadata-field` elements
 *   may reference. Accepts any iterable (array, Set, etc.).
 */
export function portalPagesSchemaWithFieldKeys(validFieldKeys: Iterable<string>) {
  const keySet = new Set(validFieldKeys);
  return z.array(portalPageSchema).superRefine((pages, ctx) => {
    refineContiguousPageNumbers(pages, ctx);
    refineSingleUploader(pages, ctx);
    refineMetadataFieldRefs(pages, keySet, ctx);
  });
}

/**
 * Standalone validator for the metadata-field-reference invariant. Returns the
 * list of dangling field-key references (empty when every `metadata-field`
 * element references a real key). Useful for callers that want a plain boolean
 * / list check without constructing a Zod schema.
 */
export function validateMetadataFieldRefs(
  pages: ReadonlyArray<{ elements: ReadonlyArray<PortalPageElement> }>,
  validFieldKeys: Iterable<string>
): string[] {
  const keySet = new Set(validFieldKeys);
  const dangling: string[] = [];
  for (const page of pages) {
    for (const element of page.elements) {
      if (element.kind === "metadata-field" && !keySet.has(element.fieldKey)) {
        dangling.push(element.fieldKey);
      }
    }
  }
  return dangling;
}

/** Type inferred from the element schema. */
export type PortalPageElementFromSchema = z.infer<typeof portalPageElementSchema>;
/** Type inferred from the single-page schema. */
export type PortalPageFromSchema = z.infer<typeof portalPageSchema>;
/** Type inferred from the pages-array schema. */
export type PortalPagesFromSchema = z.infer<typeof portalPagesSchema>;

/**
 * Compile-time lockstep assertions between the hand-written `PortalPage` /
 * `PortalPageElement` interfaces and the schema-inferred types. Asserting both
 * directions catches drift either way (interface grows a field the schema
 * misses, or vice versa). These are erased at runtime and cost nothing in the
 * shipped bundle.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _elementMatchesInterface: PortalPageElement = {} as PortalPageElementFromSchema;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _elementInterfaceMatchesSchema: PortalPageElementFromSchema = {} as PortalPageElement;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _pageMatchesInterface: PortalPage = {} as PortalPageFromSchema;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _pageInterfaceMatchesSchema: PortalPageFromSchema = {} as PortalPage;
