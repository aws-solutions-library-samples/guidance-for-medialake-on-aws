/**
 * Property-based tests for the CollectionSection item cap and More affordance.
 *
 * Feature: upload-to-collections
 * Property 9: Section item cap and More affordance
 *
 * Validates: Requirements 2.3, 2.4, 3.3, 3.4
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import fc from "fast-check";

import CollectionSection, { SECTION_ITEM_LIMIT } from "./CollectionSection";
import type { Collection } from "@/api/hooks/useCollections";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue: string) => defaultValue || _key,
  }),
}));

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/** Generate a single fake Collection with a unique id. */
const collectionArb = (index: number): fc.Arbitrary<Collection> =>
  fc
    .record({
      name: fc.string({ minLength: 1, maxLength: 30 }),
    })
    .map(({ name }) => ({
      id: `col-${index}`,
      name: `${name}-${index}`,
      type: "private" as const,
      ownerId: "user-1",
      itemCount: 0,
      childCount: 0,
      childCollectionCount: 0,
      isPublic: false,
      status: "ACTIVE",
      userRole: "owner",
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    }));

/**
 * Generate a list of 0..30 collections with unique ids.
 * We cap at 30 to keep rendering fast while exercising multiple pagination pages.
 */
const collectionListArb: fc.Arbitrary<Collection[]> = fc
  .integer({ min: 0, max: 30 })
  .chain((count) =>
    count === 0
      ? fc.constant([])
      : fc.tuple(...Array.from({ length: count }, (_, i) => collectionArb(i))).map((arr) => arr)
  );

// ---------------------------------------------------------------------------
// Property 9: Section item cap and More affordance
// ---------------------------------------------------------------------------

describe("Feature: upload-to-collections, Property 9: Section item cap and More affordance", () => {
  /**
   * For any candidate list, the section initially shows exactly
   * min(SECTION_ITEM_LIMIT, items.length) item elements, confirming the cap.
   *
   * Validates: Requirements 2.3, 3.3
   */
  it("initially shows exactly min(SECTION_ITEM_LIMIT, items.length) items", () => {
    fc.assert(
      fc.property(collectionListArb, (items) => {
        const { container, unmount } = render(
          <CollectionSection
            title="Test Section"
            items={items}
            selectedIds={new Set()}
            onToggle={() => {}}
          />
        );

        const expectedVisible = Math.min(SECTION_ITEM_LIMIT, items.length);

        // Each item is rendered as a role="option" element
        const options = container.querySelectorAll('[role="option"]');
        expect(options.length).toBe(expectedVisible);

        unmount();
      }),
      { numRuns: 150 }
    );
  });

  /**
   * The More affordance is shown iff the item list has more items than are
   * currently displayed (i.e., items.length > SECTION_ITEM_LIMIT when pagesShown=1
   * and hasMore is false).
   *
   * Validates: Requirements 2.4, 3.4
   */
  it("shows More affordance iff items.length > SECTION_ITEM_LIMIT (client-side only)", () => {
    fc.assert(
      fc.property(collectionListArb, (items) => {
        const { container, unmount } = render(
          <CollectionSection
            title="Test Section"
            items={items}
            selectedIds={new Set()}
            onToggle={() => {}}
            hasMore={false}
          />
        );

        const moreButton = container.querySelector("button");
        const shouldShowMore = items.length > SECTION_ITEM_LIMIT;

        if (shouldShowMore) {
          expect(moreButton).not.toBeNull();
          expect(moreButton?.textContent).toMatch(/more/i);
        } else {
          // No "More" button should exist (null or not matching "more")
          const moreButtons = Array.from(container.querySelectorAll("button")).filter((btn) =>
            /more/i.test(btn.textContent || "")
          );
          expect(moreButtons.length).toBe(0);
        }

        unmount();
      }),
      { numRuns: 150 }
    );
  });

  /**
   * When hasMore is true and all local items are shown, the More affordance
   * is still rendered (server-side paging scenario).
   *
   * Validates: Requirements 3.4
   */
  it("shows More affordance when hasMore=true even if all local items are shown", () => {
    fc.assert(
      fc.property(
        // Generate lists that fit within one page (0..SECTION_ITEM_LIMIT items)
        fc
          .integer({ min: 1, max: SECTION_ITEM_LIMIT })
          .chain((count) =>
            fc.tuple(...Array.from({ length: count }, (_, i) => collectionArb(i))).map((arr) => arr)
          ),
        (items) => {
          const { container, unmount } = render(
            <CollectionSection
              title="Test Section"
              items={items}
              selectedIds={new Set()}
              onToggle={() => {}}
              hasMore={true}
            />
          );

          // All local items fit in one page, but hasMore=true → More should show
          const moreButtons = Array.from(container.querySelectorAll("button")).filter((btn) =>
            /more/i.test(btn.textContent || "")
          );
          expect(moreButtons.length).toBe(1);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });
});
