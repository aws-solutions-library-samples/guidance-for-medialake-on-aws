import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { CollectionViewPage } from "./pages/collection-view.page";
import { Page } from "@playwright/test";

/**
 * OpenSearch Listing E2E Tests
 *
 * Seeds its own data (public collections) so pagination, search, sort,
 * My Collections, sub-collections, and private-visibility tests are
 * deterministic and don't depend on pre-existing environment data.
 *
 * Usage:
 *   AWS_PROFILE=ml-dev4 npx playwright test --config=playwright.collections.config.ts collection-opensearch-listing
 */

const TS = Date.now();
const SEED_PREFIX = `Seed-${TS}`;
const PARENT_NAME = `${SEED_PREFIX}-Parent`;
const CHILD_A = `${SEED_PREFIX}-ChildA`;
const CHILD_B = `${SEED_PREFIX}-ChildB`;
const PRIVATE_NAME = `${SEED_PREFIX}-Private`;
const SEARCH_NAME = `${SEED_PREFIX}-Searchable`;

// We need > pageSize collections to test multi-page. Default pageSize is 100,
// so we use pageSize=20 in the test and seed 25 collections → 2 pages.
const PAGE_SIZE_FOR_TEST = 20;
const SEED_COUNT = 25;

/** Create N collections via the UI, returning their names. */
async function seedCollections(
  page: Page,
  collections: CollectionsPage,
  count: number
): Promise<string[]> {
  const names: string[] = [];
  for (let i = 1; i <= count; i++) {
    const name = `${SEED_PREFIX}-${String(i).padStart(3, "0")}`;
    await collections.createCollection({ name });
    // Small pause between creates to avoid throttling
    await page.waitForTimeout(500);
    names.push(name);
  }
  return names;
}

/** Delete collections by name, swallowing errors for already-deleted ones. */
async function cleanupCollections(page: Page, collections: CollectionsPage, names: string[]) {
  for (const name of names) {
    try {
      // Search to find the card, then delete
      await collections.searchFor(name);
      await page.waitForTimeout(1500);
      const card = collections.cardByName(name);
      if (await card.isVisible({ timeout: 2000 }).catch(() => false)) {
        await collections.deleteCollection(name);
        await page.waitForTimeout(500);
      }
    } catch {
      // Already deleted or not found — fine
    }
  }
  await collections.clearSearch();
}

/** Wait for the page size selector and change it. */
async function changePageSize(page: Page, size: number) {
  // There are 2 comboboxes: sort (first, shows "Name") and page size (second, shows "100")
  const pageSizeCombo = page.locator('[role="combobox"]').nth(1);
  await pageSizeCombo.click({ timeout: 5000 });
  await page.getByRole("option", { name: String(size), exact: true }).click();
  await page.waitForTimeout(2000);
}

/** Extract the "Showing X - Y of Z results" numbers. */
async function getPaginationInfo(page: Page) {
  const text = await page
    .locator("text=/Showing \\d+/")
    .first()
    .textContent({ timeout: 10000 })
    .catch(() => null);
  if (!text) return null;
  const m = text.match(/Showing (\d+) - (\d+) of (\d+)/);
  if (!m) return null;
  return { from: +m[1], to: +m[2], total: +m[3] };
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

test.describe("OpenSearch Listing — Seeded Pagination", () => {
  // This describe block seeds 25 collections, runs pagination tests, then cleans up.
  let seededNames: string[] = [];

  test.beforeAll(async () => {
    // Note: beforeAll doesn't have access to fixtures, so seeding happens in the first test.
  });

  test("seed data, validate multi-page pagination, then cleanup", async ({ authenticatedPage }) => {
    test.setTimeout(300000); // 5 min — seeding + sync + tests + cleanup
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);

    // ── SEED ──
    await collections.goto();
    await collections.waitForCollections();
    console.log(`Seeding ${SEED_COUNT} collections with prefix "${SEED_PREFIX}"...`);
    seededNames = await seedCollections(page, collections, SEED_COUNT);
    console.log(`Seeded ${seededNames.length} collections. Waiting for OpenSearch sync...`);

    // Wait for DynamoDB Stream → Sync Lambda → OpenSearch
    await page.waitForTimeout(15000);

    // ── TEST 1: Search finds all seeded collections ──
    await page.reload();
    await page.waitForTimeout(5000);
    await collections.searchFor(SEED_PREFIX);
    await page.waitForTimeout(3000);

    let info = await getPaginationInfo(page);
    console.log(`After search "${SEED_PREFIX}": ${JSON.stringify(info)}`);
    expect(info).not.toBeNull();
    // At least most of the seeded collections should be synced by now
    expect(info!.total).toBeGreaterThanOrEqual(20);

    // ── TEST 2: Change page size to 20, verify multiple pages ──
    await changePageSize(page, PAGE_SIZE_FOR_TEST);
    info = await getPaginationInfo(page);
    console.log(`After pageSize=${PAGE_SIZE_FOR_TEST}: ${JSON.stringify(info)}`);
    expect(info).not.toBeNull();
    expect(info!.from).toBe(1);
    expect(info!.to).toBeLessThanOrEqual(PAGE_SIZE_FOR_TEST);
    // With 25+ results at pageSize 20, there must be at least 2 pages
    expect(info!.total).toBeGreaterThan(PAGE_SIZE_FOR_TEST);

    // ── TEST 3: Navigate to page 2 ──
    const page2Btn = page.getByRole("button", { name: "Go to page 2", exact: true });
    await expect(page2Btn).toBeVisible({ timeout: 5000 });

    const [page2Resp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("page=2")),
      page2Btn.click(),
    ]);
    expect(page2Resp.status()).toBe(200);
    await page.waitForTimeout(2000);

    const info2 = await getPaginationInfo(page);
    console.log(`Page 2: ${JSON.stringify(info2)}`);
    expect(info2).not.toBeNull();
    expect(info2!.from).toBe(PAGE_SIZE_FOR_TEST + 1); // 21
    expect(info2!.total).toBe(info!.total); // same total across pages

    // ── TEST 4: Page 2 has different collections than page 1 ──
    // Go back to page 1 and capture first heading
    await page.getByRole("button", { name: "Go to page 1", exact: true }).click();
    await page.waitForTimeout(2000);
    const firstOnPage1 = await page.locator("h3").first().textContent();

    await page.getByRole("button", { name: "Go to page 2", exact: true }).click();
    await page.waitForTimeout(2000);
    const firstOnPage2 = await page.locator("h3").first().textContent();
    expect(firstOnPage2).not.toBe(firstOnPage1);

    // ── TEST 5: Network uses new API format ──
    const [apiResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/collections?") && r.url().includes("page=")),
      page.reload(),
    ]);
    const url = apiResp.url();
    expect(url).toContain("page=");
    expect(url).toContain("pageSize=");
    expect(url).not.toContain("limit=");

    const body = await apiResp.json();
    expect(body.pagination).toHaveProperty("page");
    expect(body.pagination).toHaveProperty("pageSize");
    expect(body.pagination).toHaveProperty("totalResults");
    expect(body.pagination).toHaveProperty("totalPages");
    expect(body.pagination).toHaveProperty("hasNextPage");
    expect(body.pagination).toHaveProperty("hasPrevPage");
    // Old format must NOT be present
    expect(body.pagination).not.toHaveProperty("has_next_page");
    expect(body.pagination).not.toHaveProperty("next_cursor");
    expect(body.pagination).not.toHaveProperty("limit");

    // ── CLEANUP ──
    console.log("Cleaning up seeded collections...");
    await collections.clearSearch();
    await page.waitForTimeout(1000);
    await cleanupCollections(page, collections, seededNames);
    console.log("Cleanup complete.");
  });
});

test.describe("OpenSearch Listing — Sort", () => {
  test("sort changes are sent to server", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);
    await collections.goto();
    await collections.waitForCollections();

    // Change sort to Created via the MUI Select
    await collections.sortBySelect.click();
    await page.getByRole("option", { name: "Created" }).click();
    await page.waitForTimeout(1000);

    const [sortResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("sortDirection=desc")),
      page.getByRole("button", { name: "Descending" }).click(),
    ]);

    expect(sortResp.url()).toContain("sort=createdAt");
    expect(sortResp.url()).toContain("sortDirection=desc");
    expect(sortResp.status()).toBe(200);
  });
});

test.describe("OpenSearch Listing — Search", () => {
  test("search filters results via OpenSearch and finds created collection", async ({
    authenticatedPage,
  }) => {
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);
    await collections.goto();
    await collections.waitForCollections();

    // Create a uniquely named collection for search
    await collections.createCollection({ name: SEARCH_NAME });
    await page.waitForTimeout(12000); // wait for OpenSearch sync

    // Search for it
    const [searchResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("filter%5Bsearch%5D") || r.url().includes("filter[search]")
      ),
      collections.searchFor(SEARCH_NAME),
    ]);
    await page.waitForTimeout(2000);

    expect(searchResp.status()).toBe(200);
    await expect(page.getByRole("heading", { name: SEARCH_NAME })).toBeVisible({
      timeout: 5000,
    });

    // Clean up
    await collections.deleteCollection(SEARCH_NAME);
  });
});

test.describe("OpenSearch Listing — My Collections Tab", () => {
  test("My Collections sends ownerId filter and returns results for owner", async ({
    authenticatedPage,
  }) => {
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);
    await collections.goto();
    await collections.waitForCollections();

    // Create a collection so the test user owns at least one
    const myName = `${SEED_PREFIX}-Mine`;
    await collections.createCollection({ name: myName });
    await page.waitForTimeout(12000);

    // Click My Collections tab
    const [myCollResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("filter%5BownerId%5D")),
      collections.tab("My Collections").click(),
    ]);

    expect(myCollResp.status()).toBe(200);
    expect(myCollResp.url()).toContain("filter%5BownerId%5D");

    await page.waitForTimeout(3000);
    const info = await getPaginationInfo(page);
    // The test user just created a collection, so My Collections must have ≥ 1
    expect(info).not.toBeNull();
    expect(info!.total).toBeGreaterThanOrEqual(1);

    // Clean up
    await collections.tab("All").click();
    await page.waitForTimeout(2000);
    await collections.searchFor(myName);
    await page.waitForTimeout(2000);
    if (
      await collections
        .cardByName(myName)
        .isVisible({ timeout: 3000 })
        .catch(() => false)
    ) {
      await collections.deleteCollection(myName);
    }
  });
});

test.describe("OpenSearch Listing — Private Collections", () => {
  test("private collection is visible to its owner after sync", async ({ authenticatedPage }) => {
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);
    await collections.goto();
    await collections.waitForCollections();

    // Create a private collection (isPublic defaults to false)
    await collections.createCollection({ name: PRIVATE_NAME });
    await page.waitForTimeout(12000); // wait for OpenSearch sync

    // Sort by Created desc to find it at the top
    await collections.sortBySelect.click();
    await page.getByRole("option", { name: "Created" }).click();
    await page.getByRole("button", { name: "Descending" }).click();
    await page.waitForTimeout(3000);

    // The private collection should be visible (owner can see it via ownerId match)
    await expect(page.getByRole("heading", { name: PRIVATE_NAME })).toBeVisible({
      timeout: 10000,
    });

    // Clean up
    await collections.deleteCollection(PRIVATE_NAME);
  });
});

test.describe("OpenSearch Listing — Sub-Collections", () => {
  test("sub-collections appear in parent detail view after creation", async ({
    authenticatedPage,
  }) => {
    test.setTimeout(120000);
    const page = authenticatedPage;
    const collections = new CollectionsPage(page);
    const viewPage = new CollectionViewPage(page);

    // Create parent
    await collections.goto();
    await collections.waitForCollections();
    await collections.createCollection({ name: PARENT_NAME });
    await page.waitForTimeout(10000);

    // Open parent
    await page.reload();
    await page.waitForTimeout(3000);
    await collections.searchFor(PARENT_NAME);
    await page.waitForTimeout(3000);
    await collections.openCollection(PARENT_NAME);
    await page.waitForTimeout(3000);

    // Create two sub-collections
    await viewPage.createSubCollection(CHILD_A);
    await page.waitForTimeout(2000);
    await viewPage.createSubCollection(CHILD_B);
    await page.waitForTimeout(12000); // wait for sync

    // Reload and verify
    await page.reload();
    await page.waitForTimeout(5000);

    await expect(viewPage.subCollectionsSection).toBeVisible({ timeout: 10000 });
    await expect(viewPage.subCollectionCard(CHILD_A)).toBeVisible({ timeout: 5000 });
    await expect(viewPage.subCollectionCard(CHILD_B)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Collection Hierarchy")).toBeVisible();

    // Navigate into a sub-collection
    await viewPage.navigateToSubCollection(CHILD_A);
    await page.waitForTimeout(3000);
    expect(page.url()).toContain("/view");

    // Clean up
    await collections.goto();
    await page.waitForTimeout(3000);
    await collections.searchFor(PARENT_NAME);
    await page.waitForTimeout(3000);
    await collections.deleteCollection(PARENT_NAME);
  });
});
