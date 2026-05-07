import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { deepMerge } from "./deepMerge";

/**
 * Validates: Requirements 21.4, 21.13
 *
 * Property 4: `deepMerge` defaults neutrality.
 *
 *   deepMerge(defaults, {}) is deep-equal to defaults.
 *
 * We additionally assert two closely-related invariants that together form the
 * "neutrality" behavior of the merge:
 *   - deepMerge(t, {}) is deep-equal to t for any plain-object tree t.
 *   - deepMerge does not mutate t — t is deep-equal before and after.
 *
 * These are the strongest neutrality-adjacent properties we can check without
 * depending on the not-yet-implemented PortalAppearance schema.
 */
describe("Feature: portal-visual-editor, Property 4: deepMerge defaults neutrality", () => {
  // Arbitrary plain-object tree with bounded depth so fast-check terminates
  // quickly. Leaves are primitives or arrays of primitives; branches are plain
  // objects keyed by short strings — exactly the shape `deepMerge` operates on.
  const leafArb: fc.Arbitrary<unknown> = fc.oneof(
    fc.integer(),
    fc.double({ noNaN: true }),
    fc.string(),
    fc.boolean(),
    fc.constant(null),
    fc.array(fc.oneof(fc.integer(), fc.string(), fc.boolean()), {
      maxLength: 5,
    })
  );

  const plainObjectTree: fc.Arbitrary<Record<string, unknown>> = fc.letrec((tie) => ({
    value: fc.oneof(
      { depthSize: "small", withCrossShrink: true },
      leafArb,
      tie("node") as fc.Arbitrary<unknown>
    ),
    node: fc.dictionary(
      fc.string({ minLength: 1, maxLength: 6 }),
      tie("value") as fc.Arbitrary<unknown>,
      { maxKeys: 5 }
    ),
  })).node as fc.Arbitrary<Record<string, unknown>>;

  it("deepMerge(t, {}) is deep-equal to t and does not mutate t", () => {
    fc.assert(
      fc.property(plainObjectTree, (t) => {
        const before = structuredClone(t);

        const merged = deepMerge(t, {});

        // Neutrality: merging with an empty source returns the same shape.
        expect(merged).toEqual(t);
        // Non-mutation: target is untouched.
        expect(t).toEqual(before);
      }),
      { numRuns: 100 }
    );
  });

  it("deepMerge(t, s) never mutates t for any plain-object trees t, s", () => {
    fc.assert(
      fc.property(plainObjectTree, plainObjectTree, (t, s) => {
        const tBefore = structuredClone(t);
        const sBefore = structuredClone(s);

        deepMerge(t, s as Partial<typeof t>);

        expect(t).toEqual(tBefore);
        expect(s).toEqual(sBefore);
      }),
      { numRuns: 100 }
    );
  });
});
