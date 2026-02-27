# Playwright Test Design & Best Practices Guide

This document defines team-wide best practices for designing, writing, and maintaining Playwright end‑to‑end tests. It is intended to be checked into your repository and shared across projects.

---

## 1. Goals and Principles

- Validate critical user journeys end to end (auth, navigation, core flows), not every minor visual detail.
- Keep tests **reliable**, readable, and fast to run and debug.
- Prefer many small, focused tests over a few long "mega" tests.
- Treat tests as production code: reviewed, refactored, and owned by the team.

---

## 2. What to Cover with Playwright

- Focus on happy paths and key variants for: sign-in/sign-up, search, create/update/delete flows, checkout/payment, file upload, and settings.
- Use unit and integration tests for pure business logic; use Playwright to verify integration of UI, backend, and third‑party services.
- Include at least one E2E test for every new feature that a real user would care about.

---

## 3. Test Structure and Organization

### 3.1 Folder structure

Organize tests by domain or feature to mirror the application's structure.

Example:

```text
tests/
  auth/
    login.spec.ts
    signup.spec.ts
  dashboard/
    dashboard-view.spec.ts
  product/
    product-search.spec.ts
    product-details.spec.ts
  checkout/
    cart.spec.ts
    payment.spec.ts
```

### 3.2 File and test layout

- One feature or user flow per spec file where possible.
- Use `test.describe` blocks to group related scenarios and states.
- Use descriptive titles that read like documentation of behavior, e.g.
  - `should allow user to reset password via email link`
  - `should show validation errors for invalid credit card`

---

## 4. Using Fixtures

- Use Playwright test fixtures for common setup/teardown (authentication, seeded data, environment toggles).
- Prefer fixtures over ad‑hoc `beforeEach` blocks when logic is reused across files.
- Keep fixtures focused: each fixture should do one clear job (e.g., `loggedInPage`, `adminUser`, `testData`).

Guidelines:

- Avoid deeply nested or "magic" fixtures that hide important test steps.
- Document fixtures in a central `fixtures` module and reference from spec files.

---

## 5. Page Object Model (POM)

- Use Page Object Model to encapsulate locators and actions for each page or component.
- Keep assertions in spec files; keep interactions and selectors in page objects.
- Create reusable methods that represent user actions (e.g., `loginAs`, `addItemToCart`, `fillShippingAddress`).

Example pattern:

- `pages/login-page.ts`
- `pages/dashboard-page.ts`
- `pages/components/navbar.ts`

Benefits:

- Reduces duplication when the UI changes.
- Improves readability and makes refactoring safer.

---

## 6. Locators and Selectors

- Prefer **role‑ and label‑based locators**: `getByRole`, `getByLabel`, `getByText` for accessibility and stability.
- Add dedicated `data-testid` attributes for elements that are hard to select semantically.
- Avoid brittle selectors tied to styling or layout such as `.classNames`, `nth-child`, or deeply nested CSS.

Selector guidelines:

- One canonical selector per element, defined in a page object.
- Avoid using text that changes frequently (marketing copy, timestamps, random identifiers).

---

## 7. Waiting and Flakiness

- Rely on Playwright's auto‑waiting: interact through locators and assertions instead of manual timeouts.
- Avoid `page.waitForTimeout(...)` except for rare, well‑documented cases (e.g., animation timing issues).
- Use explicit expectations like `await expect(element).toBeVisible()` to synchronize tests with the UI.

Anti‑flakiness practices:

- Ensure each test starts from a clean state and uses its own browser context (default behavior).
- Mock or stub third‑party services where possible when they are slow or unstable.
- Investigate and fix flaky tests promptly instead of hiding them with excessive retries.

---

## 8. Test Independence and Data Management

- Every test must be able to run in isolation and in any order.
- Avoid coupling tests by reusing data or depending on results of previous tests.
- Use test data factories or API helpers to create and clean up data per test or per suite.

Data guidelines:

- Prefer creating test data via APIs or direct DB utilities instead of long UI setup flows, unless you are explicitly testing those flows.
- Use unique identifiers (timestamps, GUIDs) in test data to avoid collisions in parallel runs.

---

## 9. Configuration, Parallelization, and CI

- Run tests in parallel by default to keep feedback fast.
- Configure multiple `projects` in `playwright.config` for different browsers and key viewports where it provides real value.
- In CI, run a fast **smoke** suite on each pull request and a broader **regression** suite on main or on a nightly schedule.

Retries and CI:

- Use `retries` only in CI and keep them low (1–2) to catch intermittent issues without masking real problems.
- Collect and store artifacts (traces, screenshots, videos) for failed tests in CI.

---

## 10. Authentication and Sessions

- Use authenticated fixtures or storage state (`storageState`) to avoid logging in via UI in every test.
- Maintain separate auth states for different roles (e.g., `user`, `admin`) as fixtures or stored files.
- Include at least one test that exercises the full login flow end‑to‑end to detect auth regressions.

---

## 11. Readability and Maintainability

- Keep tests short and focused; each should validate one behavior or closely related behaviors.
- Use `test.step` (where available) to break complex flows into clearly labeled phases.
- Name tests and helper methods to express intent, not implementation details.

Code style:

- Follow the project's existing code style and linting rules for test files.
- Avoid over‑engineering: simple helpers and page objects are better than deep abstraction hierarchies.

---

## 12. Review, Refactoring, and Ownership

- Treat failing tests as high‑priority work: red builds block merges until fixed or reverted.
- Regularly refactor test code to remove duplication and simplify flows.
- Delete or rewrite tests that no longer provide value or are consistently flaky after investigation.

Team practices:

- Require code review for new or changed tests, just like production code.
- Keep this document versioned; update it when patterns, tools, or frameworks evolve.

---

## 13. Appendix: Quick Checklist

Before merging, each new Playwright test should meet the following:

- Covers a meaningful user behavior or business rule.
- Uses stable, semantic locators or `data-testid`.
- Has no hard `waitForTimeout` calls without justification.
- Is independent, idempotent, and safe to run in parallel.
- Uses fixtures and page objects where appropriate.
- Is easy to read and understand by another engineer.
