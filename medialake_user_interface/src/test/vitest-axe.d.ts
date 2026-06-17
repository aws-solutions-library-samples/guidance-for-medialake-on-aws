/**
 * Type augmentation registering the `vitest-axe` matchers on Vitest's
 * `expect`.
 *
 * `vitest-axe@0.1.0` ships its matcher augmentation against the legacy global
 * `Vi.Assertion` namespace (see `vitest-axe/extend-expect`), which Vitest 4 no
 * longer consults for matcher typing — it resolves custom matcher types from
 * the `vitest` module's `Assertion` interface instead (the same mechanism
 * `@testing-library/jest-dom/vitest` uses). Without this, `expect(...).
 * toHaveNoViolations()` is a runtime-valid call (the matcher is registered via
 * `expect.extend(axeMatchers)` in the axe test files) but a `tsc` type error.
 *
 * This declaration mirrors the jest-dom vitest augmentation: it re-exposes the
 * `AxeMatchers` interface (which declares `toHaveNoViolations`) on both the
 * synchronous `Assertion` and the asymmetric-matcher interfaces.
 */
import "vitest";
import type { AxeMatchers } from "vitest-axe/matchers";

declare module "vitest" {
  interface Assertion<T = any> extends AxeMatchers {}
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
