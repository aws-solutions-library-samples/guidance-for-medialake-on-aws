import { beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";

import type { PortalDestination, PortalMetadataField, PortalPage } from "@/api/types/api.types";

import { usePortalEditorStore, type PortalEditorPortalData } from "./usePortalEditorStore";

/**
 * Pages-slice tests for `usePortalEditorStore` (task 12.3).
 *
 * Validates: Requirements 9.2, 9.3, 9.6, 9.8, 10.1
 *
 * Covers the correctness properties the pages slice must uphold:
 *   - Property 5 (contiguity): after any sequence of add/remove/reorder, the
 *     `pageNumber`s map to 1..N with no gaps or duplicates, and field /
 *     destination `pageNumber`s cascade with the renumber.
 *   - Property 6 (reference integrity): `assignFieldToPage` /
 *     `assignDestinationToPage` keep each field's / destination's `pageNumber`
 *     referencing an existing page; `validate()` flags a dangling reference.
 *   - Property 7 (single uploader): `setUploaderPage` keeps exactly one
 *     uploader element across all pages; `validate()` flags 0 or 2 uploaders.
 *   - `removePage` blocking (Req 9.4): removing a page that hosts a field,
 *     an assigned destination, or the uploader is a no-op and records a
 *     `"pages"` error.
 *   - `getPayload` shape (Req 9.7): the payload includes `pages`, `appearance`,
 *     and `pageNumber` on each destination and metadata field.
 *   - `validate` blocking (Req 9.8, 10.1): structural violations return `false`
 *     and populate the `"pages"` error bucket; a valid structure returns `true`.
 */

// ---- Local helpers ---------------------------------------------------------

/**
 * Mirror of the private `slug` helper in the store: lowercase, non-alphanumeric
 * runs → `_`, trim leading/trailing `_`. A `metadata-field` element references
 * its field via `fieldKey === slug(field.label)`.
 */
const slug = (label: string): string =>
  label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

const emptyPage = (pageNumber: number): PortalPage => ({
  pageNumber,
  title: `Page ${pageNumber}`,
  elements: [],
});

const makeField = (label: string, pageNumber: number): PortalMetadataField => ({
  label,
  type: "text",
  required: false,
  order: pageNumber,
  pageNumber,
});

const makeDestination = (destinationId: string, pageNumber: number): PortalDestination => ({
  destinationId,
  friendlyName: `Destination ${destinationId}`,
  connectorId: "connector-1",
  rootPath: "/",
  allowBrowsing: true,
  allowFolderCreation: false,
  order: 1,
  pageNumber,
});

/**
 * A fully valid multi-page portal: two contiguous pages, exactly one uploader,
 * one metadata field whose element references a real field key, and one
 * destination — all `pageNumber`s reference existing pages. `validate()` must
 * return `true` for this structure and `getPayload()` must round-trip it.
 */
const validPortal = (): PortalEditorPortalData => ({
  name: "Portal",
  slug: "portal",
  pages: [
    {
      pageNumber: 1,
      title: "Details",
      elements: [{ kind: "metadata-field", fieldKey: slug("Full Name") }],
    },
    {
      pageNumber: 2,
      title: "Upload",
      elements: [{ kind: "uploader" }],
    },
  ],
  metadataFields: [makeField("Full Name", 1)],
  destinations: [makeDestination("d1", 1)],
});

/** Seed the store with a deep clone of `portal` so property runs never alias. */
const seed = (portal: PortalEditorPortalData): void => {
  usePortalEditorStore.getState().reset();
  usePortalEditorStore.getState().initialize(structuredClone(portal));
};

const currentPages = (): PortalPage[] =>
  (usePortalEditorStore.getState().portalData?.pages as PortalPage[] | undefined) ?? [];

const currentFields = (): PortalMetadataField[] =>
  (usePortalEditorStore.getState().portalData?.metadataFields as
    | PortalMetadataField[]
    | undefined) ?? [];

const currentDestinations = (): PortalDestination[] =>
  (usePortalEditorStore.getState().portalData?.destinations as PortalDestination[] | undefined) ??
  [];

const pageNumbers = (pages: PortalPage[]): number[] =>
  pages.map((p) => p.pageNumber).sort((a, b) => a - b);

const expectedContiguous = (length: number): number[] => Array.from({ length }, (_, i) => i + 1);

const uploaderCount = (pages: PortalPage[]): number =>
  pages.flatMap((p) => p.elements).filter((el) => el.kind === "uploader").length;

beforeEach(() => {
  // Clear any persisted draft and in-memory state so leftover pages from a
  // prior test never bleed into the next one.
  usePortalEditorStore.getState().reset();
});

// ---------------------------------------------------------------------------
// Property 5 — page-number contiguity after add / remove / reorder
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — Property 5: contiguity", () => {
  // Validates: Requirements 9.2, 9.3, 10.1

  it("keeps page numbers contiguous (1..N) after any sequence of add/remove/reorder", () => {
    type Op =
      | { tag: "add" }
      | { tag: "remove"; pageNumber: number }
      | { tag: "reorder"; from: number; to: number };

    const opArb: fc.Arbitrary<Op> = fc.oneof(
      fc.record({ tag: fc.constant("add" as const) }),
      fc.record({
        tag: fc.constant("remove" as const),
        pageNumber: fc.integer({ min: 1, max: 10 }),
      }),
      fc.record({
        tag: fc.constant("reorder" as const),
        from: fc.integer({ min: 1, max: 10 }),
        to: fc.integer({ min: 0, max: 9 }),
      })
    );

    fc.assert(
      fc.property(fc.array(opArb, { maxLength: 40 }), (ops) => {
        // Start from two empty pages. Empty pages host no field / destination /
        // uploader, so every removePage target is removable and contiguity is
        // driven purely by the renumber logic.
        seed({ name: "P", slug: "p", pages: [emptyPage(1), emptyPage(2)] });

        const store = usePortalEditorStore.getState();
        for (const op of ops) {
          if (op.tag === "add") {
            store.addPage();
          } else if (op.tag === "remove") {
            store.removePage(op.pageNumber);
          } else {
            store.reorderPages(op.from, op.to);
          }

          const pages = currentPages();
          expect(pageNumbers(pages)).toEqual(expectedContiguous(pages.length));
        }
      }),
      { numRuns: 100 }
    );
  });

  it("addPage appends 1..N contiguous numbers and stops at the 50-page cap", () => {
    seed({ name: "P", slug: "p", pages: [emptyPage(1)] });
    const store = usePortalEditorStore.getState();

    // Grow to the cap.
    for (let i = 0; i < 60; i += 1) {
      store.addPage();
    }

    const pages = currentPages();
    expect(pages.length).toBe(50);
    expect(pageNumbers(pages)).toEqual(expectedContiguous(50));
    // The over-cap add recorded a "pages" error explaining the limit.
    expect(usePortalEditorStore.getState().validationErrors.pages?.length).toBeGreaterThan(0);
  });

  it("removePage renumbers remaining pages and cascades pageNumber onto fields/destinations", () => {
    seed({
      name: "P",
      slug: "p",
      pages: [
        emptyPage(1),
        {
          pageNumber: 2,
          title: "Two",
          elements: [{ kind: "metadata-field", fieldKey: "full_name" }],
        },
        { pageNumber: 3, title: "Three", elements: [{ kind: "uploader" }] },
      ],
      metadataFields: [makeField("Full Name", 2)],
      destinations: [makeDestination("d1", 3)],
    });

    // Page 1 is empty → removable. Old pages 2 and 3 slide down to 1 and 2.
    usePortalEditorStore.getState().removePage(1);

    expect(pageNumbers(currentPages())).toEqual([1, 2]);
    expect(currentFields()[0].pageNumber).toBe(1);
    expect(currentDestinations()[0].pageNumber).toBe(2);
  });

  it("reorderPages renumbers 1..N in the new order and cascades onto fields/destinations", () => {
    seed({
      name: "P",
      slug: "p",
      pages: [
        emptyPage(1),
        {
          pageNumber: 2,
          title: "Two",
          elements: [{ kind: "metadata-field", fieldKey: "full_name" }],
        },
        { pageNumber: 3, title: "Three", elements: [{ kind: "uploader" }] },
      ],
      metadataFields: [makeField("Full Name", 2)],
      destinations: [makeDestination("d1", 3)],
    });

    // Move page 1 to the end: order becomes [old2, old3, old1] → renumber 1,2,3.
    usePortalEditorStore.getState().reorderPages(1, 2);

    const pages = currentPages();
    expect(pageNumbers(pages)).toEqual([1, 2, 3]);
    // old page 2 (the field's page) is now page 1; old page 3 (dest) now page 2.
    expect(currentFields()[0].pageNumber).toBe(1);
    expect(currentDestinations()[0].pageNumber).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Property 6 — reference integrity
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — Property 6: reference integrity", () => {
  // Validates: Requirements 9.8

  it("assignFieldToPage / assignDestinationToPage keep pageNumber referencing an existing page", () => {
    type Op =
      | { tag: "assignField"; pageNumber: number }
      | { tag: "assignDest"; pageNumber: number };

    fc.assert(
      fc.property(
        // Build K contiguous pages, then drive random assignments to page
        // numbers within [1..K] (always existing pages).
        fc.integer({ min: 1, max: 6 }).chain((pageCount) =>
          fc.record({
            pageCount: fc.constant(pageCount),
            ops: fc.array(
              fc.oneof(
                fc.record({
                  tag: fc.constant("assignField" as const),
                  pageNumber: fc.integer({ min: 1, max: pageCount }),
                }),
                fc.record({
                  tag: fc.constant("assignDest" as const),
                  pageNumber: fc.integer({ min: 1, max: pageCount }),
                })
              ),
              { maxLength: 25 }
            ),
          })
        ),
        ({ pageCount, ops }: { pageCount: number; ops: Op[] }) => {
          const pages = Array.from({ length: pageCount }, (_, i) => emptyPage(i + 1));
          seed({
            name: "P",
            slug: "p",
            pages,
            metadataFields: [makeField("Full Name", 1)],
            destinations: [makeDestination("d1", 1)],
          });

          const store = usePortalEditorStore.getState();
          for (const op of ops) {
            if (op.tag === "assignField") {
              store.assignFieldToPage(slug("Full Name"), op.pageNumber, 0);
            } else {
              store.assignDestinationToPage("d1", op.pageNumber);
            }

            const existing = new Set(currentPages().map((p) => p.pageNumber));
            for (const field of currentFields()) {
              if (field.pageNumber !== undefined) {
                expect(existing.has(field.pageNumber)).toBe(true);
              }
            }
            for (const dest of currentDestinations()) {
              if (dest.pageNumber !== undefined) {
                expect(existing.has(dest.pageNumber)).toBe(true);
              }
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("validate() flags a destination whose pageNumber references a non-existent page", () => {
    const portal = validPortal();
    // Point the destination at a page that does not exist (only 1 and 2 exist).
    (portal.destinations as PortalDestination[])[0].pageNumber = 99;
    seed(portal);

    const ok = usePortalEditorStore.getState().validate();

    expect(ok).toBe(false);
    const pagesErrors = usePortalEditorStore.getState().validationErrors.pages ?? [];
    expect(pagesErrors.length).toBeGreaterThan(0);
    expect(pagesErrors.some((e) => e.field === "destinations")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Property 7 — exactly one uploader
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — Property 7: single uploader", () => {
  // Validates: Requirements 9.6

  it("setUploaderPage keeps exactly one uploader on the most recently targeted page", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }).chain((pageCount) =>
          fc.record({
            pageCount: fc.constant(pageCount),
            // Include some out-of-range targets (no-ops) to exercise the guard.
            targets: fc.array(fc.integer({ min: 1, max: pageCount + 2 }), { maxLength: 20 }),
          })
        ),
        ({ pageCount, targets }: { pageCount: number; targets: number[] }) => {
          const pages = Array.from({ length: pageCount }, (_, i) => emptyPage(i + 1));
          seed({ name: "P", slug: "p", pages });

          const store = usePortalEditorStore.getState();
          let lastValid: number | undefined;
          for (const target of targets) {
            store.setUploaderPage(target);
            if (target <= pageCount) {
              lastValid = target;
            }

            const current = currentPages();
            if (lastValid === undefined) {
              // No valid placement yet → no uploader anywhere.
              expect(uploaderCount(current)).toBe(0);
            } else {
              // Exactly one uploader, hosted only by the last valid target.
              expect(uploaderCount(current)).toBe(1);
              const hostsUploader = (n: number) =>
                current
                  .find((p) => p.pageNumber === n)!
                  .elements.some((el) => el.kind === "uploader");
              expect(hostsUploader(lastValid)).toBe(true);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("validate() flags zero uploaders", () => {
    const portal = validPortal();
    // Strip the uploader element from page 2.
    (portal.pages as PortalPage[])[1].elements = [];
    seed(portal);

    expect(usePortalEditorStore.getState().validate()).toBe(false);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });

  it("validate() flags two uploaders", () => {
    const portal = validPortal();
    // Add a second uploader element on page 1.
    (portal.pages as PortalPage[])[0].elements.push({ kind: "uploader" });
    seed(portal);

    expect(usePortalEditorStore.getState().validate()).toBe(false);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });
});

// ---------------------------------------------------------------------------
// removePage blocking (Req 9.4)
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — removePage blocking", () => {
  // Validates: Requirements 9.3 (block + no mutation), 10.1

  it("blocks removing a page that hosts a metadata-field element and records a pages error", () => {
    seed({
      name: "P",
      slug: "p",
      pages: [
        {
          pageNumber: 1,
          title: "One",
          elements: [{ kind: "metadata-field", fieldKey: "full_name" }],
        },
        { pageNumber: 2, title: "Two", elements: [{ kind: "uploader" }] },
      ],
      metadataFields: [makeField("Full Name", 1)],
    });

    usePortalEditorStore.getState().removePage(1);

    // No mutation: both pages remain.
    expect(pageNumbers(currentPages())).toEqual([1, 2]);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });

  it("blocks removing a page that hosts an assigned destination", () => {
    seed({
      name: "P",
      slug: "p",
      pages: [{ pageNumber: 1, title: "One", elements: [{ kind: "uploader" }] }, emptyPage(2)],
      destinations: [makeDestination("d1", 2)],
    });

    usePortalEditorStore.getState().removePage(2);

    expect(pageNumbers(currentPages())).toEqual([1, 2]);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });

  it("blocks removing a page that hosts the uploader", () => {
    seed({
      name: "P",
      slug: "p",
      pages: [{ pageNumber: 1, title: "One", elements: [{ kind: "uploader" }] }, emptyPage(2)],
    });

    usePortalEditorStore.getState().removePage(1);

    expect(pageNumbers(currentPages())).toEqual([1, 2]);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });
});

// ---------------------------------------------------------------------------
// getPayload shape (Req 9.7)
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — getPayload shape", () => {
  // Validates: Requirements 9.7

  it("includes pages, appearance, and pageNumber on each destination and metadata field", () => {
    const portal = validPortal();
    seed(portal);

    const payload = usePortalEditorStore.getState().getPayload();

    // Pages round-trip verbatim.
    expect(payload.pages).toEqual(portal.pages);
    // Appearance is present (the default seeded by initialize).
    expect(payload.appearance).toBeDefined();
    // Each destination carries its pageNumber.
    expect(payload.destinations.length).toBeGreaterThan(0);
    for (const dest of payload.destinations) {
      expect(dest.pageNumber).toBeDefined();
    }
    // Each metadata field carries its pageNumber.
    expect(payload.metadataFields?.length).toBeGreaterThan(0);
    for (const field of payload.metadataFields ?? []) {
      expect(field.pageNumber).toBeDefined();
    }
  });
});

// ---------------------------------------------------------------------------
// validate blocking (Req 9.8, 10.1)
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — validate blocking", () => {
  // Validates: Requirements 9.8, 10.1

  it("returns true for a valid structure and leaves the pages bucket empty", () => {
    seed(validPortal());

    expect(usePortalEditorStore.getState().validate()).toBe(true);
    expect(usePortalEditorStore.getState().validationErrors.pages).toBeUndefined();
  });

  it("returns false and populates the pages bucket on a contiguity gap", () => {
    const portal = validPortal();
    // Introduce a gap: pages 1 and 3 (missing 2).
    (portal.pages as PortalPage[])[1].pageNumber = 3;
    seed(portal);

    expect(usePortalEditorStore.getState().validate()).toBe(false);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });

  it("returns false and populates the pages bucket on a dangling field reference", () => {
    const portal = validPortal();
    // Point the field at a page that does not exist.
    (portal.metadataFields as PortalMetadataField[])[0].pageNumber = 99;
    seed(portal);

    expect(usePortalEditorStore.getState().validate()).toBe(false);
    const pagesErrors = usePortalEditorStore.getState().validationErrors.pages ?? [];
    expect(pagesErrors.some((e) => e.field === "metadataFields")).toBe(true);
  });

  it("returns false and populates the pages bucket on a wrong uploader count", () => {
    const portal = validPortal();
    // Remove the only uploader.
    (portal.pages as PortalPage[])[1].elements = [];
    seed(portal);

    expect(usePortalEditorStore.getState().validate()).toBe(false);
    expect((usePortalEditorStore.getState().validationErrors.pages ?? []).length).toBeGreaterThan(
      0
    );
  });
});

// ---------------------------------------------------------------------------
// renameField — atomic label + fieldKey rename
// ---------------------------------------------------------------------------

describe("usePortalEditorStore pages slice — renameField", () => {
  // Validates: the slug(label) === element.fieldKey invariant is preserved
  // across a label rename so the field never silently detaches from its page.

  it("renames the label AND rewrites the referencing element fieldKey atomically", () => {
    seed(validPortal());

    const oldKey = slug("Full Name");
    const ok = usePortalEditorStore.getState().renameField(oldKey, "Customer Name");

    expect(ok).toBe(true);
    const newKey = slug("Customer Name");

    // Field label updated.
    const field = currentFields()[0];
    expect(field.label).toBe("Customer Name");

    // The page element now references the NEW key (link preserved).
    const page1 = currentPages().find((p) => p.pageNumber === 1)!;
    const mdElement = page1.elements.find((el) => el.kind === "metadata-field");
    expect(mdElement && mdElement.kind === "metadata-field" && mdElement.fieldKey).toBe(newKey);

    // No element still points at the stale key.
    const danglingExists = currentPages()
      .flatMap((p) => p.elements)
      .some((el) => el.kind === "metadata-field" && el.fieldKey === oldKey);
    expect(danglingExists).toBe(false);
  });

  it("keeps the element resolvable: slug(newLabel) matches the element fieldKey", () => {
    seed(validPortal());
    usePortalEditorStore.getState().renameField(slug("Full Name"), "Project Code 123!");

    const field = currentFields()[0];
    const page1 = currentPages().find((p) => p.pageNumber === 1)!;
    const mdElement = page1.elements.find((el) => el.kind === "metadata-field");
    // The renderer matches via slug(field.label) === element.fieldKey.
    expect(mdElement && mdElement.kind === "metadata-field" && mdElement.fieldKey).toBe(
      slug(field.label)
    );
  });

  it("a whitespace/case-only edit changes the label but leaves the key (and element) untouched", () => {
    seed(validPortal());
    const oldKey = slug("Full Name");

    const ok = usePortalEditorStore.getState().renameField(oldKey, "  full name  ");

    expect(ok).toBe(true);
    // slug("  full name  ") === slug("Full Name") === "full_name", so the key
    // is unchanged but the display label reflects the new text.
    expect(slug("  full name  ")).toBe(oldKey);
    const field = currentFields()[0];
    expect(field.label).toBe("  full name  ");
    const page1 = currentPages().find((p) => p.pageNumber === 1)!;
    const mdElement = page1.elements.find((el) => el.kind === "metadata-field");
    expect(mdElement && mdElement.kind === "metadata-field" && mdElement.fieldKey).toBe(oldKey);
  });

  it("rejects an empty label (returns false, no mutation)", () => {
    seed(validPortal());
    const before = structuredClone(usePortalEditorStore.getState().portalData);

    const ok = usePortalEditorStore.getState().renameField(slug("Full Name"), "   ");

    expect(ok).toBe(false);
    expect(usePortalEditorStore.getState().portalData).toEqual(before);
  });

  it("rejects a rename that collides with a different existing field", () => {
    const portal = validPortal();
    // Add a second field on page 1.
    (portal.metadataFields as PortalMetadataField[]).push(makeField("Region", 1));
    (portal.pages as PortalPage[])[0].elements.push({
      kind: "metadata-field",
      fieldKey: slug("Region"),
    });
    seed(portal);

    // Renaming "Full Name" to "Region" would merge two fields under one key.
    const ok = usePortalEditorStore.getState().renameField(slug("Full Name"), "Region");

    expect(ok).toBe(false);
    // Both keys still present and distinct.
    const labels = currentFields()
      .map((f) => f.label)
      .sort();
    expect(labels).toEqual(["Full Name", "Region"]);
  });

  it("returns false when no field is keyed by oldFieldKey", () => {
    seed(validPortal());
    const ok = usePortalEditorStore.getState().renameField("does_not_exist", "Whatever");
    expect(ok).toBe(false);
  });

  it("marks the store dirty on a successful rename", () => {
    seed(validPortal());
    // initialize() leaves the store clean.
    expect(usePortalEditorStore.getState().isDirty).toBe(false);

    usePortalEditorStore.getState().renameField(slug("Full Name"), "Customer Name");
    expect(usePortalEditorStore.getState().isDirty).toBe(true);
  });
});
