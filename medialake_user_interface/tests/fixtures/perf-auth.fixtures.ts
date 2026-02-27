/**
 * Performance-specific auth fixture.
 *
 * Extends the Cognito fixture directly (not the full auth fixture)
 * to handle the login flow with more resilient URL matching and
 * longer timeouts appropriate for perf testing against CloudFront.
 */
import { test as cognitoBase } from "./cognito.fixtures";
import { Page } from "@playwright/test";

export type PerfAuthFixtures = {
  authenticatedPage: Page;
};

export const test = cognitoBase.extend<PerfAuthFixtures>({
  authenticatedPage: [
    async ({ page, cognitoTestUser, baseURL }, use) => {
      const loginUrl = baseURL ? `${baseURL}/sign-in` : "/sign-in";
      await page.goto(loginUrl, { waitUntil: "domcontentloaded" });

      // Wait for login form
      await page
        .getByRole("textbox", { name: "Email" })
        .waitFor({ state: "visible", timeout: 15000 });

      await page.getByRole("textbox", { name: "Email" }).fill(cognitoTestUser.username);
      await page.getByRole("textbox", { name: "Password" }).fill(cognitoTestUser.password);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();

      // Wait for redirect away from sign-in page after successful login
      await page.waitForFunction(() => !window.location.pathname.includes("sign-in"), {
        timeout: 45000,
      });

      await page.waitForLoadState("domcontentloaded");

      // Wait for the app shell to render (not just the HTML)
      await page.waitForTimeout(2000);

      await use(page);
    },
    { scope: "test" },
  ],
});

export { expect } from "@playwright/test";
