import { test, expect } from "../fixtures/perf-auth.fixtures";
import { CollectionsPage } from "./pages/collections.page";
import { ShareModal } from "./pages/share-modal.page";

/**
 * Collection sharing & privacy tests.
 *
 * Validates:
 * - Opening the share modal on a collection
 * - The "not shared yet" state
 * - Share modal UI elements (user picker, role selector)
 * - Cleanup: deleting test collections
 *
 * Note: Full two-user sharing validation (User A shares → User B sees it)
 * requires a second browser context with a separate Cognito user.
 * That can be added as a follow-up by creating a second user in the
 * test and opening a new browser context.
 */

const SHARED_COLLECTION = `E2E Shared ${Date.now()}`;
const PRIVATE_COLLECTION = `E2E Private ${Date.now()}`;

test("collection sharing and privacy", async ({ authenticatedPage }) => {
  test.setTimeout(120000);

  const collectionsPage = new CollectionsPage(authenticatedPage);
  const shareModal = new ShareModal(authenticatedPage);

  // --- Create two collections ---
  await test.step("create private and shared collections", async () => {
    await collectionsPage.goto();

    await collectionsPage.createCollection({ name: PRIVATE_COLLECTION });
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await expect(collectionsPage.cardByName(PRIVATE_COLLECTION)).toBeVisible();

    await collectionsPage.createCollection({ name: SHARED_COLLECTION });
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();
    await expect(collectionsPage.cardByName(SHARED_COLLECTION)).toBeVisible();
  });

  // --- Open share modal and verify initial state ---
  await test.step("open share modal and verify not-shared state", async () => {
    await collectionsPage.shareCollection(SHARED_COLLECTION);

    await expect(shareModal.dialog).toBeVisible();
    await expect(shareModal.notSharedYetMessage).toBeVisible();
    await expect(shareModal.userAutocomplete).toBeVisible();
    // Role selector is a combobox showing "Viewer" by default
    await expect(shareModal.dialog.getByText("Viewer")).toBeVisible();
    await expect(shareModal.shareButton).toBeVisible();

    await shareModal.close();
  });

  // --- Verify private collection shows Private chip ---
  await test.step("verify private collection has Private badge", async () => {
    const privateCard = collectionsPage.cardByName(PRIVATE_COLLECTION);
    // Target the MUI Chip label specifically, not the collection name
    await expect(privateCard.locator(".MuiChip-label", { hasText: "Private" })).toBeVisible();
  });

  // --- Cleanup ---
  await test.step("cleanup test collections", async () => {
    await collectionsPage.deleteCollection(SHARED_COLLECTION);
    await collectionsPage.goto();
    await collectionsPage.waitForCollections();

    await collectionsPage.deleteCollection(PRIVATE_COLLECTION);
    await collectionsPage.goto();
    await authenticatedPage.waitForTimeout(2000);
  });
});
