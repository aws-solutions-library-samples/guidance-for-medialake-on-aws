/**
 * Property-based tests for the isAddable predicate.
 *
 * Feature: upload-to-collections
 * Property 1: Addable scoping is exactly owner/editor/admin
 *
 * Validates: Requirements 4.1, 4.2, 4.3, 4.4
 */

import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { isAddable, Collection } from "@/api/hooks/useCollections";

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

/**
 * All possible userRole values: the three Addable roles (owner, admin, editor),
 * the non-Addable viewer role, and undefined (no role).
 */
const addableRoles = ["owner", "admin", "editor"] as const;
const nonAddableRoles = ["viewer", undefined] as const;

const allRoles = [...addableRoles, ...nonAddableRoles];

const roleArb = fc.constantFrom<string | undefined>(...allRoles);

/**
 * Collection status values: ACTIVE (allows Addable) and non-ACTIVE statuses
 * that should always result in isAddable returning false.
 */
const activeStatus = "ACTIVE";
const nonActiveStatuses = ["DELETED", "ARCHIVED", "INACTIVE", "PENDING", ""] as const;

const statusArb = fc.constantFrom<string>(activeStatus, ...nonActiveStatuses);

/**
 * Minimal Collection object generator — only the fields relevant to isAddable
 * (status and userRole) are varied; other required fields use fixed placeholder values.
 */
const collectionArb = (
  status: fc.Arbitrary<string>,
  role: fc.Arbitrary<string | undefined>
): fc.Arbitrary<Collection> =>
  fc
    .record({
      status,
      userRole: role,
    })
    .map(({ status: s, userRole: r }) => ({
      id: "coll-test",
      name: "Test Collection",
      type: "private" as const,
      ownerId: "user-1",
      itemCount: 0,
      childCount: 0,
      childCollectionCount: 0,
      isPublic: false,
      status: s,
      userRole: r,
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    }));

// ---------------------------------------------------------------------------
// Property 1: Addable scoping is exactly owner/editor/admin
// ---------------------------------------------------------------------------

describe("Feature: upload-to-collections, Property 1: Addable scoping is exactly owner/editor/admin", () => {
  /**
   * isAddable returns true if and only if the collection is ACTIVE and its
   * userRole is owner, admin, or editor. For any other combination of status
   * and role, isAddable must return false.
   */
  it("isAddable is true iff status is ACTIVE and role is owner/admin/editor", () => {
    fc.assert(
      fc.property(collectionArb(statusArb, roleArb), (collection) => {
        const result = isAddable(collection);

        const expectedAddable =
          collection.status === "ACTIVE" &&
          (collection.userRole === "owner" ||
            collection.userRole === "admin" ||
            collection.userRole === "editor");

        expect(result).toBe(expectedAddable);
      }),
      { numRuns: 200 }
    );
  });

  /**
   * All three Addable roles on an ACTIVE collection must return true.
   * (Req 4.2: owner, Req 4.3: editor/admin)
   */
  it("ACTIVE collections with owner/admin/editor roles are always Addable", () => {
    fc.assert(
      fc.property(
        collectionArb(fc.constant(activeStatus), fc.constantFrom<string>(...addableRoles)),
        (collection) => {
          expect(isAddable(collection)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Viewer-only or no-role collections must never be Addable regardless of status.
   * (Req 4.4: exclude viewer)
   */
  it("collections with viewer or no role are never Addable", () => {
    fc.assert(
      fc.property(
        collectionArb(statusArb, fc.constantFrom<string | undefined>(...nonAddableRoles)),
        (collection) => {
          expect(isAddable(collection)).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Non-ACTIVE collections must never be Addable regardless of role.
   */
  it("non-ACTIVE collections are never Addable regardless of role", () => {
    fc.assert(
      fc.property(
        collectionArb(fc.constantFrom<string>(...nonActiveStatuses), roleArb),
        (collection) => {
          expect(isAddable(collection)).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  });
});
