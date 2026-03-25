/**
 * Role-based auth fixtures for permission testing.
 *
 * Creates Cognito test users with specific group memberships to test
 * different permission levels: superAdministrator, editor, readOnly.
 *
 * The backend's pre-token-generation Lambda trigger reads the group's
 * permission set and injects `custom:permissions` into the JWT.
 *
 * Groups expected in Cognito:
 *   - superAdministrators: full access to everything
 *   - editors: can view + edit assets, collections, pipelines; no settings
 *   - read-only: read-only access to assets, collections, search
 */
import { test as base, expect, Page } from "@playwright/test";
import { execSync } from "child_process";
import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";
const AWS_PROFILE = process.env.AWS_PROFILE || "default";

type RoleName = "superAdmin" | "editor" | "readOnly";

// Map role names to Cognito group names
const ROLE_TO_GROUP: Record<RoleName, string> = {
  superAdmin: "superAdministrators",
  editor: "editors",
  readOnly: "read-only",
};

function awsCli(command: string): string {
  return execSync(`aws ${command} --profile ${AWS_PROFILE} --region ${AWS_REGION}`, {
    encoding: "utf8",
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();
}

/**
 * Resolve the Cognito user pool ID.
 *
 * Priority:
 *   1. COGNITO_USER_POOL_ID env var (explicit override)
 *   2. public/aws-exports.json — validated against the current AWS account
 *   3. Name-based search across the AWS account (fallback)
 */
function findUserPoolId(): string {
  // 1. Explicit env var
  if (process.env.COGNITO_USER_POOL_ID) {
    return process.env.COGNITO_USER_POOL_ID;
  }

  // 2. Read from aws-exports.json and verify the pool exists in this account
  try {
    const exportsPath = path.resolve(process.cwd(), "public/aws-exports.json");
    const raw = fs.readFileSync(exportsPath, "utf8");
    const config = JSON.parse(raw);
    const poolId = config?.Auth?.Cognito?.userPoolId;
    if (poolId) {
      // Verify the pool actually exists in the current AWS account
      try {
        awsCli(`cognito-idp describe-user-pool --user-pool-id ${poolId}`);
        console.log(`[RoleAuth] Using user pool from aws-exports.json: ${poolId}`);
        return poolId;
      } catch {
        console.warn(
          `[RoleAuth] Pool ${poolId} from aws-exports.json not found in current account, falling back to name search`
        );
      }
    }
  } catch (e: any) {
    console.warn(`[RoleAuth] Could not read aws-exports.json: ${e.message}`);
  }

  // 3. Fallback: search by name
  const output = awsCli("cognito-idp list-user-pools --max-results 50");
  const pool = JSON.parse(output).UserPools?.find(
    (p: any) => p.Name?.toLowerCase().includes("medialake")
  );
  if (!pool) throw new Error("No MediaLake user pool found");
  console.log(`[RoleAuth] Using user pool from name search: ${pool.Id}`);
  return pool.Id;
}

function generatePassword(): string {
  const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lower = "abcdefghijklmnopqrstuvwxyz";
  const digits = "0123456789";
  const symbols = "@%+=._-";
  const all = upper + lower + digits + symbols;

  let pw = "";
  pw += upper[Math.floor(Math.random() * upper.length)];
  pw += upper[Math.floor(Math.random() * upper.length)];
  pw += lower[Math.floor(Math.random() * lower.length)];
  pw += lower[Math.floor(Math.random() * lower.length)];
  pw += digits[Math.floor(Math.random() * digits.length)];
  pw += digits[Math.floor(Math.random() * digits.length)];
  pw += symbols[Math.floor(Math.random() * symbols.length)];
  while (pw.length < 24) pw += all[Math.floor(Math.random() * all.length)];
  return pw
    .split("")
    .sort(() => Math.random() - 0.5)
    .join("")
    .replace(/^[^a-zA-Z0-9]/, "A"); // ensure starts with alphanumeric
}

function ensureGroupExists(userPoolId: string, groupName: string): boolean {
  try {
    awsCli(`cognito-idp get-group --user-pool-id ${userPoolId} --group-name ${groupName}`);
    return true;
  } catch {
    console.warn(`[RoleAuth] Group "${groupName}" not found in user pool`);
    return false;
  }
}

function createUserWithRole(
  userPoolId: string,
  email: string,
  password: string,
  groupName: string
): void {
  try {
    awsCli(
      `cognito-idp admin-create-user --user-pool-id ${userPoolId} --username "${email}" ` +
        `--user-attributes Name=email,Value="${email}" Name=email_verified,Value=true ` +
        `--temporary-password "${password}" --message-action SUPPRESS`
    );
  } catch (e: any) {
    if (!e.message.includes("UsernameExistsException")) throw e;
  }

  awsCli(
    `cognito-idp admin-set-user-password --user-pool-id ${userPoolId} ` +
      `--username "${email}" --password "${password}" --permanent`
  );

  if (ensureGroupExists(userPoolId, groupName)) {
    try {
      awsCli(
        `cognito-idp admin-add-user-to-group --user-pool-id ${userPoolId} ` +
          `--username "${email}" --group-name ${groupName}`
      );
    } catch {
      // already in group
    }
  }
}

function deleteUser(userPoolId: string, email: string): void {
  try {
    awsCli(`cognito-idp admin-delete-user --user-pool-id ${userPoolId} --username "${email}"`);
  } catch {
    // user already gone
  }
}

interface TestUserInfo {
  username: string;
  password: string;
  role: RoleName;
  group: string;
}

export type RoleAuthFixtures = {
  superAdminPage: Page;
  editorPage: Page;
  readOnlyPage: Page;
  superAdminUser: TestUserInfo;
  editorUser: TestUserInfo;
  readOnlyUser: TestUserInfo;
};

async function loginAs(page: Page, baseURL: string | undefined, user: TestUserInfo): Promise<void> {
  const loginUrl = baseURL ? `${baseURL}/sign-in` : "http://localhost:5173/sign-in";

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto(loginUrl, { waitUntil: "domcontentloaded" });
      await page
        .getByRole("textbox", { name: "Email" })
        .waitFor({ state: "visible", timeout: 15000 });
      await page.getByRole("textbox", { name: "Email" }).fill(user.username);
      await page.getByRole("textbox", { name: "Password" }).fill(user.password);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await page.waitForFunction(() => !window.location.pathname.includes("sign-in"), {
        timeout: 30000,
      });
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);
      return;
    } catch {
      if (attempt === 2) throw new Error(`Login failed for ${user.role} after 3 attempts`);
      await page.waitForTimeout(3000);
    }
  }
}

function createRoleUser(role: RoleName, workerIndex: number): { email: string; password: string } {
  const id = crypto.randomBytes(4).toString("hex");
  return {
    email: `mne-medialake+e2e-${role}-${workerIndex}-${id}@amazon.com`,
    password: generatePassword(),
  };
}

export const test = base.extend<RoleAuthFixtures>({
  superAdminUser: [
    async ({}, use, testInfo) => {
      const userPoolId = findUserPoolId();
      const { email, password } = createRoleUser("superAdmin", testInfo.workerIndex);
      const group = ROLE_TO_GROUP.superAdmin;
      createUserWithRole(userPoolId, email, password, group);
      const user: TestUserInfo = { username: email, password, role: "superAdmin", group };
      await use(user);
      deleteUser(userPoolId, email);
    },
    { scope: "test" },
  ],

  editorUser: [
    async ({}, use, testInfo) => {
      const userPoolId = findUserPoolId();
      const { email, password } = createRoleUser("editor", testInfo.workerIndex);
      const group = ROLE_TO_GROUP.editor;
      createUserWithRole(userPoolId, email, password, group);
      const user: TestUserInfo = { username: email, password, role: "editor", group };
      await use(user);
      deleteUser(userPoolId, email);
    },
    { scope: "test" },
  ],

  readOnlyUser: [
    async ({}, use, testInfo) => {
      const userPoolId = findUserPoolId();
      const { email, password } = createRoleUser("readOnly", testInfo.workerIndex);
      const group = ROLE_TO_GROUP.readOnly;
      createUserWithRole(userPoolId, email, password, group);
      const user: TestUserInfo = { username: email, password, role: "readOnly", group };
      await use(user);
      deleteUser(userPoolId, email);
    },
    { scope: "test" },
  ],

  superAdminPage: async ({ browser, superAdminUser, baseURL }, use) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginAs(page, baseURL, superAdminUser);
    await use(page);
    await ctx.close();
  },

  editorPage: async ({ browser, editorUser, baseURL }, use) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginAs(page, baseURL, editorUser);
    await use(page);
    await ctx.close();
  },

  readOnlyPage: async ({ browser, readOnlyUser, baseURL }, use) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginAs(page, baseURL, readOnlyUser);
    await use(page);
    await ctx.close();
  },
});

export { expect };
