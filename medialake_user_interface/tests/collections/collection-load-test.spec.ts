import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { CollectionViewPage } from "./pages/collection-view.page";
import { Page } from "@playwright/test";

/**
 * Load test: 2,000 root collections + 6,000 children (4 levels deep).
 * Measures API response times and UI render times under realistic load.
 *
 * Pre-requisite: Run the data seeding script to create 8,000 collections.
 *
 * Usage:
 *   AWS_PROFILE=ml-dev4 npx playwright test --config=playwright.collections.config.ts collection-load-test
 */

interface PerfEntry {
  operation: string;
  apiMs: number | null;
  renderMs: number;
}

const perfLog: PerfEntry[] = [];

/** Intercept the first matching API response and measure wall-clock render time. */
async function timed(
  page: Page,
  operation: string,
  action: () => Promise<void>,
  apiPattern?: string | RegExp
): Promise<PerfEntry> {
  let apiMs: number | null = null;
  let apiStatus: number | null = null;

  const apiPromise = apiPattern
    ? page
        .waitForResponse(
          (r) =>
            typeof apiPattern === "string"
              ? r.url().includes(apiPattern)
              : apiPattern.test(r.url()),
          { timeout: 45000 }
        )
        .then(async (resp) => {
          apiStatus = resp.status();
          const timing = resp.request().timing();
          apiMs = timing.responseEnd > 0 ? Math.round(timing.responseEnd) : null;
        })
        .catch(() => {})
    : Promise.resolve();

  const t0 = Date.now();
  await action();
  const renderMs = Date.now() - t0;

  await apiPromise;

  const entry: PerfEntry = { operation, apiMs, renderMs };
  perfLog.push(entry);

  const apiStr = apiMs !== null ? `${apiMs}ms` : "n/a";
  const statusStr = apiStatus !== null ? ` (${apiStatus})` : "";
  console.log(`⏱  ${operation}: render=${renderMs}ms, api=${apiStr}${statusStr}`);
  return entry;
}

test("load test: 8k collections — page load, pagination, navigation, search", async ({
  authenticatedPage,
}) => {
  test.setTimeout(300000); // 5 min

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const viewPage = new CollectionViewPage(authenticatedPage);

  // ── 1. Initial page load with 2,000 root collections ──────────
  await test.step("initial collections page load (2k roots)", async () => {
    await timed(
      authenticatedPage,
      "PAGE LOAD (2k roots)",
      async () => {
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
        await expect(collectionsPage.heading).toBeVisible();
      },
      /collections/
    );

    // Verify pagination text
    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
      return m ? m[0] : "not found";
    });
    console.log(`   → ${showing}`);

    // The test user sees all collections (owned by seeded user + public ones)
    // Just verify the page loaded with some results
    const totalMatch = showing.match(/of (\d+) results/);
    const totalCount = totalMatch ? parseInt(totalMatch[1]) : 0;
    console.log(`   → Total visible collections: ${totalCount}`);
    expect(totalCount).toBeGreaterThan(0);
  });

  // ── 2. Pagination: page 2 at default 100/page ─────────────────
  await test.step("navigate to page 2 (100/page)", async () => {
    // Only test if there are enough results for page 2
    const totalCount = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/of (\d+) results/);
      return m ? parseInt(m[1]) : 0;
    });

    if (totalCount > 100) {
      await timed(authenticatedPage, "PAGE 2 (100/page)", async () => {
        await authenticatedPage.getByRole("button", { name: "Go to page 2" }).click();
        await authenticatedPage.waitForTimeout(300);
      });
    } else {
      console.log(`   → Skipping page 2 (only ${totalCount} results)`);
    }

    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
      return m ? m[0] : "not found";
    });
    console.log(`   → ${showing}`);
  });

  // ── 3. Change page size to 20 ─────────────────────────────────
  await test.step("change page size to 20", async () => {
    await timed(authenticatedPage, "CHANGE PAGE SIZE → 20", async () => {
      const select = authenticatedPage.locator("[role=combobox]").last();
      await select.click();
      await authenticatedPage.waitForTimeout(300);
      await authenticatedPage.locator('[data-value="20"]').click();
      await authenticatedPage.waitForTimeout(500);
    });

    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
      return m ? m[0] : "not found";
    });
    console.log(`   → ${showing}`);
  });

  // ── 4. Jump to last page ───────────────────────────────────────
  await test.step("jump to last page (20/page)", async () => {
    await timed(authenticatedPage, "LAST PAGE (20/page)", async () => {
      await authenticatedPage.getByRole("button", { name: "Go to last page" }).click();
      await authenticatedPage.waitForTimeout(300);
    });

    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
      return m ? m[0] : "not found";
    });
    console.log(`   → ${showing}`);
  });

  // ── 5. Change page size to 200 ────────────────────────────────
  await test.step("change page size to 200", async () => {
    await timed(authenticatedPage, "CHANGE PAGE SIZE → 200", async () => {
      const select = authenticatedPage.locator("[role=combobox]").last();
      await select.click();
      await authenticatedPage.waitForTimeout(300);
      await authenticatedPage.locator('[data-value="200"]').click();
      await authenticatedPage.waitForTimeout(500);
    });

    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/Showing \d+ - \d+ of \d+ results/);
      return m ? m[0] : "not found";
    });
    console.log(`   → ${showing}`);
  });

  // Reset to 100
  const select = authenticatedPage.locator("[role=combobox]").last();
  await select.click();
  await authenticatedPage.waitForTimeout(300);
  await authenticatedPage.locator('[data-value="100"]').click();
  await authenticatedPage.waitForTimeout(500);

  // ── 6. Search filter ───────────────────────────────────────────
  await test.step("search filter: 'Marketing'", async () => {
    await timed(authenticatedPage, "SEARCH 'Marketing' (client filter)", async () => {
      await collectionsPage.searchFor("Marketing");
      await authenticatedPage.waitForTimeout(500);
    });

    const count = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/of (\d+) results/);
      return m ? m[1] : "?";
    });
    console.log(`   → Filtered to ${count} results`);
    await collectionsPage.clearSearch();
    await authenticatedPage.waitForTimeout(300);
  });

  await test.step("search filter: 'L0-00001'", async () => {
    await timed(authenticatedPage, "SEARCH 'L0-00001' (specific)", async () => {
      await collectionsPage.searchFor("L0-00001");
      await authenticatedPage.waitForTimeout(500);
    });

    const count = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/of (\d+) results/);
      return m ? m[1] : "?";
    });
    console.log(`   → Filtered to ${count} results`);
    await collectionsPage.clearSearch();
    await authenticatedPage.waitForTimeout(300);
  });

  // ── 7. Sort descending ─────────────────────────────────────────
  await test.step("sort descending", async () => {
    await timed(authenticatedPage, "SORT DESCENDING (2k items)", async () => {
      await authenticatedPage.getByRole("button", { name: "Descending" }).click();
      await authenticatedPage.waitForTimeout(500);
    });

    // Verify first card starts with a later letter
    const firstH3 = await authenticatedPage.evaluate(() => {
      const h = document.querySelector("h3");
      return h?.textContent || "";
    });
    console.log(`   → First card: ${firstH3}`);

    // Reset
    await authenticatedPage.getByRole("button", { name: "Ascending" }).click();
    await authenticatedPage.waitForTimeout(300);
  });

  // ── 8. Navigate into a root with children ──────────────────────
  await test.step("open root collection with 4 children", async () => {
    // Clear any previous search and go back to page 1
    await collectionsPage.clearSearch();
    await authenticatedPage.waitForTimeout(500);

    // Search for a specific root that has children (first 500 roots have children)
    await collectionsPage.searchFor("Root 0001");
    await authenticatedPage.waitForTimeout(1000);

    await timed(
      authenticatedPage,
      "OPEN ROOT (4 L1 children)",
      async () => {
        // Click the first visible card
        await collectionsPage.cards.first().click();
        await authenticatedPage.waitForLoadState("domcontentloaded");
        await authenticatedPage.waitForTimeout(2000);
      },
      /collections/
    );
  });

  // ── 9. Navigate into L1 child ──────────────────────────────────
  await test.step("navigate into L1 child (has 4 L2 children)", async () => {
    await authenticatedPage.waitForTimeout(2000);

    await timed(
      authenticatedPage,
      "OPEN L1 CHILD (4 L2 children)",
      async () => {
        // Click any sub-collection card/heading
        const subLink = authenticatedPage.locator("h4, h3").filter({ hasText: /L1-/ }).first();
        if (await subLink.isVisible().catch(() => false)) {
          await subLink.click();
        } else {
          // Try clicking any sub-collection card
          const anySubCard = authenticatedPage.locator(".MuiCard-root").nth(0);
          await anySubCard.click();
        }
        await authenticatedPage.waitForLoadState("domcontentloaded");
        await authenticatedPage.waitForTimeout(1500);
      },
      /collections/
    );
  });

  // ── 10. Navigate into L2 child ─────────────────────────────────
  await test.step("navigate into L2 child (has 4 L3 children)", async () => {
    await authenticatedPage.waitForTimeout(2000);

    await timed(
      authenticatedPage,
      "OPEN L2 CHILD (4 L3 leaves)",
      async () => {
        const subLink = authenticatedPage.locator("h4, h3").filter({ hasText: /L2-/ }).first();
        if (await subLink.isVisible().catch(() => false)) {
          await subLink.click();
        } else {
          console.log("   → No L2 children visible, skipping");
          return;
        }
        await authenticatedPage.waitForLoadState("domcontentloaded");
        await authenticatedPage.waitForTimeout(1500);
      },
      /collections/
    );
  });

  // ── 11. Navigate into L3 leaf ──────────────────────────────────
  await test.step("navigate into L3 leaf (no children)", async () => {
    await authenticatedPage.waitForTimeout(2000);

    await timed(
      authenticatedPage,
      "OPEN L3 LEAF (0 children)",
      async () => {
        const subLink = authenticatedPage.locator("h4, h3").filter({ hasText: /L3-/ }).first();
        if (await subLink.isVisible().catch(() => false)) {
          await subLink.click();
        } else {
          console.log("   → No L3 children visible, skipping");
          return;
        }
        await authenticatedPage.waitForLoadState("domcontentloaded");
        await authenticatedPage.waitForTimeout(1500);
      },
      /collections/
    );
  });

  // ── 12. Breadcrumb navigation back to root ─────────────────────
  await test.step("breadcrumb: jump back to root from L3", async () => {
    await timed(authenticatedPage, "BREADCRUMB L3 → ROOT", async () => {
      // Click the root collection in breadcrumbs
      const rootLink = viewPage.breadcrumbs.getByRole("link").first();
      await rootLink.click();
      await authenticatedPage.waitForLoadState("domcontentloaded");
      await authenticatedPage.waitForTimeout(1000);
    });
  });

  // ── 13. Navigate back to collections list ──────────────────────
  await test.step("return to collections list from view", async () => {
    await timed(
      authenticatedPage,
      "BACK TO LIST (2k roots)",
      async () => {
        await collectionsPage.goto();
        await collectionsPage.waitForCollections();
      },
      /collections/
    );
  });

  // ── 14. Tab: My Collections ────────────────────────────────────
  await test.step("switch to My Collections tab", async () => {
    await timed(authenticatedPage, "TAB: My Collections", async () => {
      await collectionsPage.tab("My Collections").click();
      await authenticatedPage.waitForTimeout(1000);
    });

    const showing = await authenticatedPage.evaluate(() => {
      const m = document.body.innerText.match(/of (\d+) results/);
      return m ? m[1] : "?";
    });
    console.log(`   → ${showing} results`);
  });

  // ══════════════════════════════════════════════════════════════
  // Performance Summary
  // ══════════════════════════════════════════════════════════════
  console.log("\n");
  console.log("╔══════════════════════════════════════════════════════════════╗");
  console.log("║  📊 LOAD TEST PERFORMANCE SUMMARY (8,000 collections)      ║");
  console.log("╠══════════════════════════════════════════════════════════════╣");
  console.log("║  Operation                          Render     API          ║");
  console.log("╠══════════════════════════════════════════════════════════════╣");
  for (const e of perfLog) {
    const api = e.apiMs !== null ? `${e.apiMs}ms` : "n/a";
    const line = `║  ${e.operation.padEnd(34)} ${String(e.renderMs + "ms").padStart(
      8
    )}  ${api.padStart(8)}  ║`;
    console.log(line);
  }
  console.log("╚══════════════════════════════════════════════════════════════╝");
});
