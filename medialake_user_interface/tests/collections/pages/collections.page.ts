/**
 * Page Object for the Collections list page (/collections).
 * Encapsulates locators and actions — assertions stay in spec files.
 */
import { Page } from "@playwright/test";

export class CollectionsPage {
  constructor(private page: Page) {}

  // --- Navigation ---
  async goto() {
    // Use direct navigation — Amplify stores auth tokens in localStorage
    // which persists across page.goto() calls within the same browser context.
    // Wait briefly to ensure Amplify has finished persisting tokens after login.
    await this.page.waitForTimeout(500);
    await this.page.goto("/collections", { waitUntil: "domcontentloaded" });
    await this.page.waitForLoadState("networkidle").catch(() => {});
    // If we got redirected to login, wait a moment and retry once
    // (Amplify may need a tick to restore tokens from localStorage on cold navigation)
    if (this.page.url().includes("sign-in")) {
      await this.page.waitForTimeout(3000);
      await this.page.goto("/collections", { waitUntil: "domcontentloaded" });
      await this.page.waitForLoadState("networkidle").catch(() => {});
      if (this.page.url().includes("sign-in")) {
        throw new Error("Auth tokens lost during navigation — session expired");
      }
    }
  }

  // --- Locators ---
  get heading() {
    return this.page.getByRole("heading", { name: "Collections", exact: true });
  }

  get createButton() {
    // Target the header button specifically (not the empty state one)
    return this.page.getByRole("button", { name: /Create Collection/i }).first();
  }

  get refreshButton() {
    return this.page.locator('[aria-label*="refresh" i], [title*="refresh" i]').first();
  }

  get searchInput() {
    return this.page.getByPlaceholder(/Search collections/i);
  }

  // Filter tabs
  tab(name: string) {
    return this.page.getByRole("button", { name: new RegExp(name, "i") });
  }

  // Collection cards — target the root Card element only
  get cards() {
    return this.page.locator(".MuiCard-root");
  }

  cardByName(name: string) {
    return this.page.locator(".MuiCard-root").filter({ hasText: name }).first();
  }

  // Sort controls
  get sortBySelect() {
    return this.page.locator('[class*="MuiSelect"]').first();
  }

  // Empty state
  get emptyState() {
    return this.page.getByText(/No collections found/i);
  }

  // --- Actions ---
  async createCollection(opts: { name: string; description?: string; isPublic?: boolean }) {
    await this.createButton.click();
    // Wait for dialog to open
    await this.page.getByRole("dialog").waitFor({ state: "visible" });

    await this.page.getByRole("textbox", { name: /Collection Name/i }).fill(opts.name);
    if (opts.description) {
      await this.page.getByRole("textbox", { name: /Description/i }).fill(opts.description);
    }
    if (opts.isPublic) {
      await this.page.getByRole("checkbox").click();
    }
    // Click the Create Collection button inside the dialog
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: /Create Collection/i })
      .click();
    // Wait for modal to close
    await this.page
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});
  }

  async editCollection(
    collectionName: string,
    updates: { name?: string; description?: string; isPublic?: boolean }
  ) {
    const card = this.cardByName(collectionName);
    await card.hover();
    await card.getByRole("button", { name: /Edit/i }).click();
    await this.page.getByRole("dialog").waitFor({ state: "visible" });

    if (updates.name !== undefined) {
      const nameField = this.page.getByRole("textbox", { name: /Collection Name|^Name/i });
      await nameField.clear();
      await nameField.fill(updates.name);
    }
    if (updates.description !== undefined) {
      const descField = this.page.getByRole("textbox", { name: /Description/i });
      await descField.clear();
      await descField.fill(updates.description);
    }
    if (updates.isPublic !== undefined) {
      const checkbox = this.page.getByRole("checkbox");
      const isChecked = await checkbox.isChecked();
      if (isChecked !== updates.isPublic) {
        await checkbox.click();
      }
    }
    await this.page.getByRole("dialog").getByRole("button", { name: /Save/i }).click();
    await this.page
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});
  }

  async deleteCollection(collectionName: string) {
    const card = this.cardByName(collectionName);
    await card.hover();
    await card.getByRole("button", { name: /Delete/i }).click();
    // Confirm in dialog
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: /^Delete$/i })
      .click();
    await this.page
      .getByRole("dialog")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});
  }

  async shareCollection(collectionName: string) {
    const card = this.cardByName(collectionName);
    await card.hover();
    await card.getByRole("button", { name: /Share/i }).click();
  }

  async openCollection(collectionName: string) {
    await this.cardByName(collectionName).click();
    await this.page.waitForLoadState("domcontentloaded");
  }

  async searchFor(query: string) {
    await this.searchInput.fill(query);
  }

  async clearSearch() {
    await this.searchInput.clear();
  }

  async waitForCollections() {
    await this.cards
      .first()
      .waitFor({ state: "visible", timeout: 15000 })
      .catch(() => {});
  }
}
