/**
 * Page Object for the Share Management Modal.
 */
import { Page } from "@playwright/test";

export class ShareModal {
  constructor(private page: Page) {}

  get dialog() {
    return this.page.getByRole("dialog");
  }

  get userAutocomplete() {
    return this.dialog.getByLabel(/Select user/i);
  }

  get roleSelect() {
    // MUI Select renders as a combobox inside a FormControl with "Role" label
    return this.dialog.getByRole("combobox").nth(1);
  }

  get messageField() {
    return this.dialog.getByLabel(/Message/i);
  }

  get shareButton() {
    return this.dialog.getByRole("button", { name: /^Share$/i });
  }

  get closeButton() {
    return this.dialog.getByRole("button", { name: /Close/i });
  }

  get sharedWithSection() {
    return this.dialog.getByText(/Shared With/i);
  }

  get notSharedYetMessage() {
    return this.dialog.getByText(/hasn't been shared yet/i);
  }

  sharedUserEntry(username: string) {
    return this.dialog.getByText(username);
  }

  async shareWithUser(username: string, role: "VIEWER" | "EDITOR" = "VIEWER") {
    await this.userAutocomplete.fill(username);
    // Wait for autocomplete dropdown and select the user
    await this.page.getByRole("option").filter({ hasText: username }).first().click();

    if (role === "EDITOR") {
      await this.roleSelect.click();
      await this.page.getByRole("option", { name: /Editor/i }).click();
    }

    await this.shareButton.click();
    // Wait for the share to complete
    await this.page.waitForTimeout(1000);
  }

  async removeShare(username: string) {
    const entry = this.dialog.getByRole("listitem").filter({ hasText: username });
    await entry.getByRole("button").click();
    await this.page.waitForTimeout(1000);
  }

  async close() {
    await this.closeButton.click();
  }
}
