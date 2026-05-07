/**
 * Static auth fixture for smoke tests.
 *
 * Uses a pre-existing test account instead of creating/destroying
 * Cognito users per test. Faster for comprehensive UI smoke tests
 * that don't need isolated user state.
 *
 * Set MEDIALAKE_TEST_EMAIL and MEDIALAKE_TEST_PASSWORD env vars,
 * or they default to the dev account credentials.
 */
import { test as base, expect, Page } from "@playwright/test";

const TEST_EMAIL = process.env.MEDIALAKE_TEST_EMAIL || "mne-medialake@amazon.com";
const TEST_PASSWORD = process.env.MEDIALAKE_TEST_PASSWORD || "ChangeMe123!";

// Ensure the static test user is in the superAdministrators group.
// This runs once when the fixture module is loaded.
function ensureTestUserIsSuperAdmin(): void {
  if (process.env.SKIP_ROLE_CHECK === "true") return;

  try {
    const { execSync } = require("child_process");
    const fs = require("fs");
    const path = require("path");
    const region = process.env.AWS_REGION || "us-east-1";
    const profile = process.env.AWS_PROFILE || "default";

    // Resolve pool ID: env var → aws-exports.json → name search
    let poolId: string | undefined = process.env.COGNITO_USER_POOL_ID;

    if (!poolId) {
      try {
        const exportsPath = path.resolve(process.cwd(), "public/aws-exports.json");
        const config = JSON.parse(fs.readFileSync(exportsPath, "utf8"));
        const candidateId = config?.Auth?.Cognito?.userPoolId;
        if (candidateId) {
          // Verify pool exists in current account before using it
          try {
            execSync(
              `aws cognito-idp describe-user-pool --user-pool-id ${candidateId} --profile ${profile} --region ${region}`,
              { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] }
            );
            poolId = candidateId;
          } catch {
            // Pool from aws-exports.json not in this account — fall through
          }
        }
      } catch {
        // fall through to name search
      }
    }

    if (!poolId) {
      const poolsJson = execSync(
        `aws cognito-idp list-user-pools --max-results 50 --profile ${profile} --region ${region}`,
        { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] }
      );
      const pool = JSON.parse(poolsJson).UserPools?.find(
        (p: any) => p.Name?.toLowerCase().includes("medialake")
      );
      if (!pool) return;
      poolId = pool.Id;
    }

    // Add user to superAdministrators group (idempotent)
    execSync(
      `aws cognito-idp admin-add-user-to-group --user-pool-id ${poolId} ` +
        `--username "${TEST_EMAIL}" --group-name superAdministrators ` +
        `--profile ${profile} --region ${region}`,
      { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] }
    );
    console.log(`[StaticAuth] Ensured ${TEST_EMAIL} is in superAdministrators group`);
  } catch (e: any) {
    // Non-fatal — the user might already be in the group, or AWS CLI isn't configured
    if (!e.message?.includes("already")) {
      console.warn(`[StaticAuth] Could not verify superAdmin group membership: ${e.message}`);
    }
  }
}

ensureTestUserIsSuperAdmin();

export type StaticAuthFixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<StaticAuthFixtures>({
  authenticatedPage: async ({ page, baseURL }, use) => {
    const loginUrl = baseURL ? `${baseURL}/sign-in` : "http://localhost:5173/sign-in";

    // Retry login up to 2 times in case of Cognito rate limiting
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await page.goto(loginUrl, { waitUntil: "domcontentloaded" });

        await page
          .getByRole("textbox", { name: "Email" })
          .waitFor({ state: "visible", timeout: 15000 });

        await page.getByRole("textbox", { name: "Email" }).fill(TEST_EMAIL);
        await page.getByRole("textbox", { name: "Password" }).fill(TEST_PASSWORD);
        await page.getByRole("button", { name: "Sign in", exact: true }).click();

        // Wait for redirect away from sign-in
        await page.waitForFunction(() => !window.location.pathname.includes("sign-in"), {
          timeout: 30000,
        });
        await page.waitForLoadState("domcontentloaded");
        await page.waitForTimeout(2000);
        break; // Success
      } catch (e) {
        if (attempt === 2) throw e;
        // Wait before retrying (Cognito rate limit backoff)
        await page.waitForTimeout(3000);
      }
    }

    await use(page);
  },
});

export { expect };
