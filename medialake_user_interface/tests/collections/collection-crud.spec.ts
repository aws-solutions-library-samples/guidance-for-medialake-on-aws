import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { CollectionViewPage } from "./pages/collection-view.page";

/**
 * Collection CRUD — full lifecycle in a single authenticated session.
 *
 * Since the Cognito fixture creates a fresh user per test, we run the
 * entire create → verify → search → view → edit → delete flow in one
 * test to share the same user session and collection state.
 */

const COLLECTION_NAME = `E2E Test Collection ${Date.now()}`;
const UPDATED_NAME = `${COLLECTION_NAME} Updated`;
const DESCRIPTION = "Created by Playwright E2E test";

test("collection CRUD lifecycle", async ({ authenticatedPage }) => {
  test.setTimeout(120000); // 2 min for the full lifecycle

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const viewPage = new CollectionViewPage(authenticatedPage);

  // --- Step 1: Navigate to collections ---
  await test.step("navigate to collections page", async () => {
    await collectionsPage.goto();
    await expect(collectionsPage.heading).toBeVisible();
  });

  // --- Step 2: Create a new private collection ---
  await test.step("create a new private collection", async () => {
    await collectionsPage.createCollection({
      name: COLLECTION_NAME,
      description: DESCRIPTION,
    });

    // Re-navigate to refresh the list
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await expect(collectionsPage.cardByName(COLLECTION_NAME)).toBeVisible();
  });

  // --- Step 3: Search for the collection ---
  await test.step("find collection via search", async () => {
    await collectionsPage.searchFor(COLLECTION_NAME);
    await expect(collectionsPage.cardByName(COLLECTION_NAME)).toBeVisible();
    await collectionsPage.clearSearch();
  });

  // --- Step 4: Navigate into collection view ---
  await test.step("navigate into collection view page", async () => {
    await collectionsPage.openCollection(COLLECTION_NAME);
    await expect(viewPage.collectionName).toContainText(COLLECTION_NAME);
    await expect(viewPage.breadcrumbs).toContainText("Collections");
    await expect(viewPage.emptyState).toBeVisible({ timeout: 15000 });
  });

  // --- Step 5: Go back and edit the collection ---
  await test.step("edit collection name and description", async () => {
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();

    await collectionsPage.editCollection(COLLECTION_NAME, {
      name: UPDATED_NAME,
      description: "Updated description",
    });

    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await expect(collectionsPage.cardByName(UPDATED_NAME)).toBeVisible();
  });

  // --- Step 6: Delete the collection ---
  await test.step("delete the collection", async () => {
    await collectionsPage.deleteCollection(UPDATED_NAME);
    await collectionsPage.goto();
    await authenticatedPage.waitForTimeout(2000);
    await expect(collectionsPage.cardByName(UPDATED_NAME)).toBeHidden();
  });
});
