import { Page } from "@playwright/test";

/**
 * Log in via the Amplify Authenticator UI (Cognito hosted form embedded in the app).
 * Saves storage state to the given path for reuse.
 */
export async function loginViaUI(
  page: Page,
  email: string,
  password: string,
  storageStatePath?: string
): Promise<void> {
  // Navigate to sign-in page
  await page.goto("/sign-in", { waitUntil: "networkidle" });

  // Wait for the Amplify authenticator form to appear
  const emailField = page.locator('input[name="username"], input[type="email"]').first();
  await emailField.waitFor({ state: "visible", timeout: 30_000 });

  // Fill credentials
  await emailField.fill(email);

  const passwordField = page.locator('input[name="password"], input[type="password"]').first();
  await passwordField.waitFor({ state: "visible", timeout: 10_000 });
  await passwordField.fill(password);

  // Submit
  const submitButton = page
    .locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Sign In")')
    .first();
  await submitButton.click();

  // Wait for redirect to the main app (away from /sign-in)
  await page.waitForURL((url) => !url.pathname.includes("sign-in"), {
    timeout: 30_000,
  });

  // Wait for the app shell to be ready
  await page.waitForLoadState("networkidle");

  // Save storage state if path provided
  if (storageStatePath) {
    await page.context().storageState({ path: storageStatePath });
  }
}

/**
 * Navigate to the Assets page and wait for it to load.
 */
export async function navigateToAssets(page: Page): Promise<void> {
  await page.goto("/assets", { waitUntil: "networkidle" });
  await page.locator('text="Assets"').first().waitFor({ state: "visible", timeout: 15_000 });
}

/**
 * Navigate to the Search page.
 */
export async function navigateToSearch(page: Page): Promise<void> {
  await page.goto("/search", { waitUntil: "networkidle" });
  await page.waitForLoadState("networkidle");
}
