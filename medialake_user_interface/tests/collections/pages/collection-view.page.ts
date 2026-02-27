/**
 * Page Object for the Collection View page (/collections/:id/view).
 */
import { Page } from "@playwright/test";

export class CollectionViewPage {
  constructor(private page: Page) {}

  // --- Locators ---
  get breadcrumbs() {
    return this.page.getByRole("navigation", { name: "breadcrumb" });
  }

  get collectionName() {
    return this.breadcrumbs.locator("p").last();
  }

  get createSubCollectionButton() {
    return this.page.getByRole("button", { name: /Create Sub-Collection/i });
  }

  get editButton() {
    return this.page.getByRole("button", { name: /^Edit$/i });
  }

  get deleteButton() {
    return this.page.getByRole("button", { name: /^Delete$/i });
  }

  get subCollectionsSection() {
    return this.page.getByText(/Sub-Collections/i);
  }

  get emptyState() {
    return this.page.getByText(/No assets found/i);
  }

  get assetsLoadingIndicator() {
    return this.page.getByText(/Loading assets/i);
  }

  subCollectionCard(name: string) {
    return this.page.getByText(name);
  }

  // --- Actions ---
  async goto(collectionId: string) {
    await this.page.goto(`/collections/${collectionId}/view`, {
      waitUntil: "domcontentloaded",
    });
    await this.page.waitForLoadState("networkidle").catch(() => {});
  }

  async createSubCollection(name: string) {
    await this.createSubCollectionButton.click();
    await this.page.getByRole("dialog").waitFor({ state: "visible" });
    await this.page.getByRole("textbox", { name: /Collection Name/i }).fill(name);
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: /Create Collection/i })
      .click();
    await this.page
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});
  }

  async navigateToSubCollection(name: string) {
    await this.subCollectionCard(name).click();
    await this.page.waitForLoadState("domcontentloaded");
  }

  async navigateViaBreadcrumb(name: string) {
    await this.breadcrumbs.getByRole("link", { name }).click();
    await this.page.waitForLoadState("domcontentloaded");
  }

  async deleteCurrentCollection() {
    await this.deleteButton.click();
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: /^Delete$/i })
      .click();
  }
}
