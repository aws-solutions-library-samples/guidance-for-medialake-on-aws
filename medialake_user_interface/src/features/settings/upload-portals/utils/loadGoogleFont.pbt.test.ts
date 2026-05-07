import { beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";

import { GOOGLE_FONT_LINK_ID_PREFIX, loadGoogleFont } from "./loadGoogleFont";

/**
 * Validates: Requirements 21.7, 21.13
 *
 * Property 7: `loadGoogleFont` idempotence.
 *
 *   ∀ font: string, ∀ n >= 1. After calling `loadGoogleFont(font)` n times,
 *   the number of `<link>` tags for that family in `document.head`
 *   is ≤ 1.
 *
 * The pragmatic strengthening we assert: for an arbitrary sequence of
 * `loadGoogleFont(family)` calls across a curated family set, the final
 * DOM state contains AT MOST ONE `<link>` element per distinct family,
 * regardless of how many times each family was invoked. The bound is
 * "≤ 1" rather than "= 1" because system-font stacks (e.g.
 * `"System Default"`, `"-apple-system..."`) are expected no-ops and
 * produce zero links — that is still idempotent.
 */

const SAMPLE_FAMILIES: readonly string[] = [
  // Curated set — a mix of single-word and multi-word Google Fonts plus
  // system-stack sentinels so the property test also exercises the
  // no-op branches.
  "Inter",
  "Roboto",
  "Open Sans",
  "Plus Jakarta Sans",
  "JetBrains Mono",
  "Playfair Display",
  "System Default",
  "-apple-system, BlinkMacSystemFont",
  "",
];

/** Count how many `<link>` elements currently live under the Google Fonts id prefix. */
const countFontLinks = (): number =>
  document.head.querySelectorAll(`link[id^="${GOOGLE_FONT_LINK_ID_PREFIX}"]`).length;

/** Clean up any link elements this test produced. */
const clearFontLinks = (): void => {
  const existing = document.head.querySelectorAll(`link[id^="${GOOGLE_FONT_LINK_ID_PREFIX}"]`);
  existing.forEach((el) => el.parentNode?.removeChild(el));
};

describe("Feature: portal-visual-editor, Property 7: loadGoogleFont idempotence", () => {
  beforeEach(() => {
    clearFontLinks();
  });

  it("keeps at most one <link> per family across arbitrary call sequences", () => {
    // Each call in the sequence picks a family from the curated set.
    // `fc.array` with `maxLength: 50` gives us call sequences long enough
    // to stress rapid repeated invocations and mixed families.
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...SAMPLE_FAMILIES), {
          minLength: 1,
          maxLength: 50,
        }),
        (calls) => {
          // Reset the DOM state at the start of every run so the property
          // is an isolated claim — mixing runs would turn the assertion
          // into "eventually consistent across all time" which is weaker.
          clearFontLinks();

          for (const family of calls) {
            loadGoogleFont(family);
          }

          // Group the distinct families invoked and check each produced
          // at most one link. The count includes system-stack sentinels
          // which should produce zero links.
          const distinctFamilies = new Set(calls);
          for (const family of distinctFamilies) {
            const links = document.head.querySelectorAll(
              `link[id^="${GOOGLE_FONT_LINK_ID_PREFIX}"]`
            );
            // Narrow to links whose id slug matches this family. We
            // reuse the same slug logic the implementation uses:
            // lowercase and collapse non-alphanumerics.
            const slug = family
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-+|-+$/g, "");
            const matching = Array.from(links).filter(
              (link) => link.id === `${GOOGLE_FONT_LINK_ID_PREFIX}${slug}`
            );
            expect(matching.length).toBeLessThanOrEqual(1);
          }

          // Stronger ambient bound: the total number of font links is
          // always ≤ the number of *distinct* families ever invoked.
          // System-stack families reduce this further because they
          // produce zero links.
          expect(countFontLinks()).toBeLessThanOrEqual(distinctFamilies.size);
        }
      ),
      { numRuns: 100 }
    );
  });
});
