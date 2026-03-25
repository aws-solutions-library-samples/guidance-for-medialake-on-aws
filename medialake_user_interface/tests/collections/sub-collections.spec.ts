import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { CollectionViewPage } from "./pages/collection-view.page";

/**
 * Sub-collection tests — creating nested collections,
 * navigating the hierarchy, and breadcrumb navigation.
 * Single test to share the authenticated session.
 */

const PARENT_NAME = `E2E Parent ${Date.now()}`;
const CHILD_NAME = `E2E Child ${Date.now()}`;

test("sub-collection lifecycle", async ({ authenticatedPage }) => {
  test.setTimeout(120000);

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const viewPage = new CollectionViewPage(authenticatedPage);

  // --- Create parent collection ---
  await test.step("create parent collection", async () => {
    await collectionsPage.goto();
    await collectionsPage.createCollection({ name: PARENT_NAME });
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await expect(collectionsPage.cardByName(PARENT_NAME)).toBeVisible();
  });

  // --- Create sub-collection from view page ---
  await test.step("create sub-collection from view page", async () => {
    await collectionsPage.openCollection(PARENT_NAME);
    await expect(viewPage.collectionName).toContainText(PARENT_NAME);

    await viewPage.createSubCollection(CHILD_NAME);

    // Refresh and verify
    await authenticatedPage.reload({ waitUntil: "domcontentloaded" });
    await authenticatedPage.waitForLoadState("networkidle").catch(() => {});
    await expect(viewPage.subCollectionsSection).toBeVisible({ timeout: 10000 });
    await expect(viewPage.subCollectionCard(CHILD_NAME)).toBeVisible();
  });

  // --- Navigate into sub-collection and back via breadcrumbs ---
  await test.step("navigate hierarchy via breadcrumbs", async () => {
    await viewPage.navigateToSubCollection(CHILD_NAME);
    await expect(viewPage.collectionName).toContainText(CHILD_NAME);

    await viewPage.navigateViaBreadcrumb(PARENT_NAME);
    await expect(viewPage.collectionName).toContainText(PARENT_NAME);
  });

  // --- Cleanup: delete parent (cascades to children) ---
  await test.step("delete parent collection", async () => {
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await collectionsPage.deleteCollection(PARENT_NAME);
    await collectionsPage.goto();
    await expect(collectionsPage.cardByName(PARENT_NAME)).toBeHidden({
      timeout: 10000,
    });
  });
});
