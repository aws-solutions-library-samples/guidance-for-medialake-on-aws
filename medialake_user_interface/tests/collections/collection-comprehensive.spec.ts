import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { CollectionViewPage } from "./pages/collection-view.page";
import { Page } from "@playwright/test";

/**
 * Comprehensive collection tests — CRUD, multi-level sub-collections,
 * pagination, sorting, filtering, and performance timing.
 *
 * Logs API response times and UI render times for each operation.
 *
 * Usage:
 *   AWS_PROFILE=ml-dev4 npx playwright test --config=playwright.collections.config.ts collection-comprehensive
 */

// --- Performance timing helpers ---

interface PerfEntry {
  operation: string;
  apiMs: number | null;
  renderMs: number;
}

const perfLog: PerfEntry[] = [];

/**
 * Measure an operation's API response time (via network interception)
 * and total render time (wall clock from action start to UI assertion).
 */
async function timedOperation(
  page: Page,
  operation: string,
  action: () => Promise<void>,
  urlPattern?: string | RegExp
): Promise<PerfEntry> {
  let apiMs: number | null = null;

  // Intercept API calls matching the pattern
  const apiPromise = urlPattern
    ? page
        .waitForResponse(
          (resp) => {
            const url = resp.url();
            if (typeof urlPattern === "string") return url.includes(urlPattern);
            return urlPattern.test(url);
          },
          { timeout: 30000 }
        )
        .then((resp) => {
          const timing = resp.request().timing();
          apiMs = timing.responseEnd > 0 ? Math.round(timing.responseEnd) : null;
          return resp;
        })
        .catch(() => null)
    : Promise.resolve(null);

  const wallStart = Date.now();
  await action();
  const renderMs = Date.now() - wallStart;

  await apiPromise;

  const entry: PerfEntry = { operation, apiMs, renderMs };
  perfLog.push(entry);

  const apiStr = apiMs !== null ? `${apiMs}ms` : "n/a";
  console.log(`⏱  ${operation}: render=${renderMs}ms, api=${apiStr}`);

  return entry;
}

// --- Test data ---
const TS = Date.now();
const ROOT_A = `Perf Root Alpha ${TS}`;
const ROOT_B = `Perf Root Beta ${TS}`;
const ROOT_C = `Perf Root Charlie ${TS}`;
const SUB_A1 = `Sub Alpha-1 ${TS}`;
const SUB_A2 = `Sub Alpha-2 ${TS}`;
const SUBSUB_A1_1 = `Deep Alpha-1-1 ${TS}`;
const UPDATED_ROOT_A = `Perf Root Alpha Updated ${TS}`;

// ============================================================
// TEST 1: Full CRUD lifecycle with timing
// ============================================================
test("collection CRUD with performance timing", async ({ authenticatedPage }) => {
  test.setTimeout(180000);

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const viewPage = new CollectionViewPage(authenticatedPage);

  // --- CREATE: Root collection A ---
  await test.step("create root collection A", async () => {
    await collectionsPage.goto();
    await expect(collectionsPage.heading).toBeVisible();

    await timedOperation(
      authenticatedPage,
      "CREATE root collection A",
      async () => {
        await collectionsPage.createCollection({
          name: ROOT_A,
          description: "Performance test root collection A",
        });
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.cardByName(ROOT_A)).toBeVisible();
      },
      /collections/
    );
  });

  // --- CREATE: Root collection B ---
  await test.step("create root collection B", async () => {
    await timedOperation(
      authenticatedPage,
      "CREATE root collection B",
      async () => {
        await collectionsPage.createCollection({
          name: ROOT_B,
          description: "Performance test root collection B",
        });
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.cardByName(ROOT_B)).toBeVisible();
      },
      /collections/
    );
  });

  // --- CREATE: Root collection C ---
  await test.step("create root collection C", async () => {
    await timedOperation(
      authenticatedPage,
      "CREATE root collection C",
      async () => {
        await collectionsPage.createCollection({
          name: ROOT_C,
          description: "Performance test root collection C",
        });
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.cardByName(ROOT_C)).toBeVisible();
      },
      /collections/
    );
  });

  // --- UPDATE: Rename root A ---
  await test.step("update root collection A name", async () => {
    await timedOperation(
      authenticatedPage,
      "UPDATE root collection A",
      async () => {
        await collectionsPage.editCollection(ROOT_A, {
          name: UPDATED_ROOT_A,
          description: "Updated description for perf test",
        });
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.cardByName(UPDATED_ROOT_A)).toBeVisible();
      },
      /collections/
    );
  });

  // --- SEARCH: Find by partial name ---
  await test.step("search collections by name", async () => {
    await timedOperation(authenticatedPage, "SEARCH by name 'Alpha'", async () => {
      await collectionsPage.searchFor("Alpha");
      await authenticatedPage.waitForTimeout(500);
      await expect(collectionsPage.cardByName(UPDATED_ROOT_A)).toBeVisible();
    });

    // Verify other collections are filtered out
    const betaVisible = await collectionsPage
      .cardByName(ROOT_B)
      .isVisible()
      .catch(() => false);
    expect(betaVisible).toBe(false);

    await collectionsPage.clearSearch();
    await authenticatedPage.waitForTimeout(500);
  });

  // --- SEARCH: Find by description ---
  await test.step("search collections by description", async () => {
    await timedOperation(authenticatedPage, "SEARCH by description 'Beta'", async () => {
      await collectionsPage.searchFor("Beta");
      await authenticatedPage.waitForTimeout(500);
      await expect(collectionsPage.cardByName(ROOT_B)).toBeVisible();
    });
    await collectionsPage.clearSearch();
    await authenticatedPage.waitForTimeout(500);
  });

  // --- SORT: Descending ---
  await test.step("sort collections descending", async () => {
    await timedOperation(authenticatedPage, "SORT descending", async () => {
      await authenticatedPage.getByRole("button", { name: "Descending" }).click();
      await authenticatedPage.waitForTimeout(500);
    });

    // Verify order: first card should be later alphabetically
    const headings = await authenticatedPage.evaluate(() => {
      const h3s = document.querySelectorAll("h3");
      return Array.from(h3s)
        .map((h) => h.textContent || "")
        .filter((t) => t.includes("Perf Root"));
    });
    // In descending order, Charlie > Beta > Alpha
    const charlieIdx = headings.findIndex((h) => h.includes("Charlie"));
    const alphaIdx = headings.findIndex((h) => h.includes("Alpha"));
    expect(charlieIdx).toBeLessThan(alphaIdx);

    // Reset to ascending
    await authenticatedPage.getByRole("button", { name: "Ascending" }).click();
    await authenticatedPage.waitForTimeout(500);
  });

  // --- DELETE: Root C ---
  await test.step("delete root collection C", async () => {
    await timedOperation(
      authenticatedPage,
      "DELETE root collection C",
      async () => {
        await collectionsPage.deleteCollection(ROOT_C);
        await collectionsPage.goto();
        await authenticatedPage.waitForTimeout(2000);
        await expect(collectionsPage.cardByName(ROOT_C)).toBeHidden();
      },
      /collections/
    );
  });

  // --- Cleanup remaining ---
  await test.step("cleanup: delete remaining collections", async () => {
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();

    for (const name of [UPDATED_ROOT_A, ROOT_B]) {
      const visible = await collectionsPage
        .cardByName(name)
        .isVisible()
        .catch(() => false);
      if (visible) {
        await collectionsPage.deleteCollection(name);
        await collectionsPage.goto();
        await authenticatedPage.waitForTimeout(1000);
      }
    }
  });

  // --- Print performance summary ---
  console.log("\n📊 Performance Summary (CRUD):");
  console.log("─".repeat(60));
  for (const entry of perfLog) {
    const apiStr = entry.apiMs !== null ? `${entry.apiMs}ms` : "n/a";
    console.log(
      `  ${entry.operation.padEnd(35)} render: ${String(entry.renderMs).padStart(
        6
      )}ms  api: ${apiStr}`
    );
  }
  console.log("─".repeat(60));
});

// ============================================================
// TEST 2: Multi-level sub-collection hierarchy
// ============================================================
test("multi-level sub-collection hierarchy", async ({ authenticatedPage }) => {
  test.setTimeout(180000);

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const viewPage = new CollectionViewPage(authenticatedPage);
  const localPerf: PerfEntry[] = [];

  const PARENT = `Hierarchy Parent ${TS}`;
  const CHILD_1 = `Hierarchy Child 1 ${TS}`;
  const CHILD_2 = `Hierarchy Child 2 ${TS}`;
  const GRANDCHILD = `Hierarchy Grandchild ${TS}`;

  // --- Create parent ---
  await test.step("create parent collection", async () => {
    await collectionsPage.goto();
    const entry = await timedOperation(
      authenticatedPage,
      "CREATE parent",
      async () => {
        await collectionsPage.createCollection({ name: PARENT });
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.cardByName(PARENT)).toBeVisible();
      },
      /collections/
    );
    localPerf.push(entry);
  });

  // --- Navigate into parent and create child 1 ---
  await test.step("create first sub-collection", async () => {
    await collectionsPage.openCollection(PARENT);
    await expect(viewPage.collectionName).toContainText(PARENT);

    const entry = await timedOperation(
      authenticatedPage,
      "CREATE sub-collection 1",
      async () => {
        await viewPage.createSubCollection(CHILD_1);
        await authenticatedPage.reload({ waitUntil: "domcontentloaded" });
        await authenticatedPage.waitForLoadState("networkidle").catch(() => {});
        await expect(viewPage.subCollectionCard(CHILD_1)).toBeVisible({ timeout: 15000 });
      },
      /collections/
    );
    localPerf.push(entry);
  });

  // --- Create child 2 ---
  await test.step("create second sub-collection", async () => {
    const entry = await timedOperation(
      authenticatedPage,
      "CREATE sub-collection 2",
      async () => {
        await viewPage.createSubCollection(CHILD_2);
        await authenticatedPage.reload({ waitUntil: "domcontentloaded" });
        await authenticatedPage.waitForLoadState("networkidle").catch(() => {});
        await expect(viewPage.subCollectionCard(CHILD_2)).toBeVisible({ timeout: 15000 });
      },
      /collections/
    );
    localPerf.push(entry);
  });

  // --- Navigate into child 1 and create grandchild ---
  await test.step("create grandchild (3rd level)", async () => {
    await viewPage.navigateToSubCollection(CHILD_1);
    await expect(viewPage.collectionName).toContainText(CHILD_1);

    const entry = await timedOperation(
      authenticatedPage,
      "CREATE grandchild (level 3)",
      async () => {
        await viewPage.createSubCollection(GRANDCHILD);
        await authenticatedPage.reload({ waitUntil: "domcontentloaded" });
        await authenticatedPage.waitForLoadState("networkidle").catch(() => {});
        await expect(viewPage.subCollectionCard(GRANDCHILD)).toBeVisible({
          timeout: 15000,
        });
      },
      /collections/
    );
    localPerf.push(entry);
  });

  // --- Navigate into grandchild and verify breadcrumbs ---
  await test.step("verify 3-level breadcrumb navigation", async () => {
    const entry = await timedOperation(authenticatedPage, "NAVIGATE into grandchild", async () => {
      await viewPage.navigateToSubCollection(GRANDCHILD);
      await expect(viewPage.collectionName).toContainText(GRANDCHILD);
      // Breadcrumbs should show: Collections > Parent > Child 1 > Grandchild
      await expect(viewPage.breadcrumbs).toContainText("Collections");
    });
    localPerf.push(entry);

    // Navigate back up via breadcrumbs
    const backEntry = await timedOperation(
      authenticatedPage,
      "BREADCRUMB navigate to parent",
      async () => {
        await viewPage.navigateViaBreadcrumb(PARENT);
        await expect(viewPage.collectionName).toContainText(PARENT);
      }
    );
    localPerf.push(backEntry);
  });

  // --- Verify sub-collection count on parent ---
  await test.step("verify parent shows 2 sub-collections", async () => {
    await expect(viewPage.subCollectionsSection).toBeVisible({ timeout: 10000 });
    // Use heading role to avoid matching both tree view label and card heading
    await expect(authenticatedPage.getByRole("heading", { name: CHILD_1 })).toBeVisible();
    await expect(authenticatedPage.getByRole("heading", { name: CHILD_2 })).toBeVisible();
  });

  // --- Cleanup: delete parent (cascades) ---
  await test.step("cleanup: delete parent collection", async () => {
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    const entry = await timedOperation(
      authenticatedPage,
      "DELETE parent (cascade)",
      async () => {
        await collectionsPage.deleteCollection(PARENT);
        await collectionsPage.goto();
        await authenticatedPage.waitForTimeout(2000);
        await expect(collectionsPage.cardByName(PARENT)).toBeHidden({ timeout: 10000 });
      },
      /collections/
    );
    localPerf.push(entry);
  });

  // --- Print performance summary ---
  console.log("\n📊 Performance Summary (Hierarchy):");
  console.log("─".repeat(60));
  for (const entry of localPerf) {
    const apiStr = entry.apiMs !== null ? `${entry.apiMs}ms` : "n/a";
    console.log(
      `  ${entry.operation.padEnd(35)} render: ${String(entry.renderMs).padStart(
        6
      )}ms  api: ${apiStr}`
    );
  }
  console.log("─".repeat(60));
});

// ============================================================
// TEST 3: Pagination with different page sizes
// ============================================================
test("pagination across page sizes", async ({ authenticatedPage }) => {
  test.setTimeout(180000);

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const localPerf: PerfEntry[] = [];

  // Create 25 collections for pagination testing
  const BATCH_PREFIX = `PagTest ${TS}`;
  const BATCH_COUNT = 25;

  await test.step("create 25 collections for pagination", async () => {
    await collectionsPage.goto();
    for (let i = 1; i <= BATCH_COUNT; i++) {
      await collectionsPage.createCollection({
        name: `${BATCH_PREFIX} ${String(i).padStart(3, "0")}`,
      });
      // Brief pause to avoid rate limiting
      if (i % 5 === 0) {
        await authenticatedPage.waitForTimeout(500);
      }
    }
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
  });

  // --- Test page size 20: should paginate ---
  await test.step("page size 20: verify pagination", async () => {
    // Change page size to 20
    const select = authenticatedPage.locator("[role=combobox]").last();
    await select.click();
    await authenticatedPage.waitForTimeout(300);
    await authenticatedPage.locator('[data-value="20"]').click();
    await authenticatedPage.waitForTimeout(500);

    const entry = await timedOperation(authenticatedPage, "RENDER page 1 at 20/page", async () => {
      const showing = await authenticatedPage.evaluate(() => {
        const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
        return m ? m[0] : "not found";
      });
      expect(showing).toContain("Showing 1 - 20");
    });
    localPerf.push(entry);

    // Navigate to page 2
    const p2Entry = await timedOperation(authenticatedPage, "NAVIGATE to page 2", async () => {
      await authenticatedPage.getByRole("button", { name: "Go to page 2" }).click();
      await authenticatedPage.waitForTimeout(300);
      const showing = await authenticatedPage.evaluate(() => {
        const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
        return m ? m[0] : "not found";
      });
      expect(showing).toContain("Showing 21 -");
    });
    localPerf.push(p2Entry);
  });

  // --- Test page size 50: all on one page ---
  await test.step("page size 50: all on one page", async () => {
    const select = authenticatedPage.locator("[role=combobox]").last();
    await select.click();
    await authenticatedPage.waitForTimeout(300);
    await authenticatedPage.locator('[data-value="50"]').click();
    await authenticatedPage.waitForTimeout(500);

    const entry = await timedOperation(authenticatedPage, "RENDER all at 50/page", async () => {
      const showing = await authenticatedPage.evaluate(() => {
        const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
        return m ? m[0] : "not found";
      });
      // All collections should fit on one page
      expect(showing).toMatch(/Showing 1 - \d+ of \d+ results/);
    });
    localPerf.push(entry);
  });

  // --- Search with pagination ---
  await test.step("search narrows pagination", async () => {
    const entry = await timedOperation(
      authenticatedPage,
      "SEARCH + pagination update",
      async () => {
        await collectionsPage.searchFor(BATCH_PREFIX);
        await authenticatedPage.waitForTimeout(500);
        const showing = await authenticatedPage.evaluate(() => {
          const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
          return m ? m[0] : "not found";
        });
        expect(showing).toContain(`of ${BATCH_COUNT} results`);
      }
    );
    localPerf.push(entry);
    await collectionsPage.clearSearch();
  });

  // --- Cleanup ---
  await test.step("cleanup: delete batch collections", async () => {
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();

    // Change to 200/page to see all
    const select = authenticatedPage.locator("[role=combobox]").last();
    await select.click();
    await authenticatedPage.waitForTimeout(300);
    await authenticatedPage.locator('[data-value="200"]').click();
    await authenticatedPage.waitForTimeout(500);

    // Search for our batch
    await collectionsPage.searchFor(BATCH_PREFIX);
    await authenticatedPage.waitForTimeout(1000);

    for (let i = BATCH_COUNT; i >= 1; i--) {
      const name = `${BATCH_PREFIX} ${String(i).padStart(3, "0")}`;
      const visible = await collectionsPage
        .cardByName(name)
        .isVisible()
        .catch(() => false);
      if (visible) {
        await collectionsPage.deleteCollection(name);
        await authenticatedPage.waitForTimeout(300);
      }
    }
  });

  // --- Print performance summary ---
  console.log("\n📊 Performance Summary (Pagination):");
  console.log("─".repeat(60));
  for (const entry of localPerf) {
    const apiStr = entry.apiMs !== null ? `${entry.apiMs}ms` : "n/a";
    console.log(
      `  ${entry.operation.padEnd(35)} render: ${String(entry.renderMs).padStart(
        6
      )}ms  api: ${apiStr}`
    );
  }
  console.log("─".repeat(60));
});
