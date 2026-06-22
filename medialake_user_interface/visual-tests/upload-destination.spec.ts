import { test, expect, Page, BrowserContext } from "@playwright/test";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import { loginViaUI, navigateToAssets } from "./helpers/auth";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Test users provisioned in Cognito (us-east-1_lkKoeeo4U) ──────────────
const USER_A = {
  email: "visual-test-userA@example.com",
  password: "VtestA#2026xyz",
  label: "UserA-editors",
  sub: "64a86448-a071-7018-b049-b7002b84c681",
};
const USER_B = {
  email: "visual-test-userB@example.com",
  password: "VtestB#2026xyz",
  label: "UserB-personal-uploaders",
  sub: "14a8b468-5071-705f-ad77-8ce764ce1aac",
};

const SHOTS = path.join(__dirname, "screenshots", "upload-destination");

function ensureDirs() {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
}
async function shot(page: Page, name: string) {
  ensureDirs();
  const p = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log(`  📸 ${name}.png`);
}
async function stabilize(page: Page) {
  try {
    await page.waitForLoadState("domcontentloaded");
    await page.addStyleTag({
      content: `*,*::before,*::after{animation-duration:0s !important;transition-duration:0s !important;}`,
    });
  } catch {
    // navigation in-flight; ignore
  }
}
async function settleAfterLogin(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);
  await stabilize(page);
}
async function newCtx(browser: any): Promise<BrowserContext> {
  return browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/New_York",
    colorScheme: "light",
    reducedMotion: "reduce",
    ignoreHTTPSErrors: true,
  });
}

interface ApiHit {
  url: string;
  status: number;
  body: string;
}
function trackApi(page: Page, hits: ApiHit[]) {
  page.on("response", async (resp) => {
    const url = resp.url();
    if (url.includes("/search/connectors") || url.includes("/connectors/my-assets")) {
      let body = "";
      try {
        body = (await resp.text()).substring(0, 4000);
      } catch {}
      hits.push({ url, status: resp.status(), body });
    }
  });
}
function summarizeApi(label: string, hits: ApiHit[]) {
  console.log(`  --- ${label}: connector API responses ---`);
  for (const h of hits) {
    const ep = h.url.includes("/search/connectors")
      ? "/search/connectors"
      : "/connectors/my-assets";
    let count = "";
    try {
      const j = JSON.parse(h.body);
      if (ep === "/search/connectors") count = ` connectors=${(j?.data?.connectors || []).length}`;
      else count = ` connector=${j?.data?.connector?.id || "none"}`;
    } catch {}
    console.log(`    ${ep} -> HTTP ${h.status}${count}`);
  }
}

async function openTopBarUploadModal(page: Page): Promise<void> {
  // The upload IconButton has no accessible label and (in the prod build) no
  // data-testid. It is the icon button immediately preceding the
  // "notifications" button in the TopBar. Use that relationship, with a few
  // fallbacks.
  const candidates = [
    page.locator('xpath=//button[@aria-label="notifications"]/preceding-sibling::button[1]'),
    page.locator('button:has([data-testid="CloudUploadIcon"])'),
    page.locator('button:has(svg[data-testid="CloudUploadIcon"])'),
  ];
  let clicked = false;
  for (const c of candidates) {
    if (
      await c
        .first()
        .isVisible()
        .catch(() => false)
    ) {
      await c.first().click();
      clicked = true;
      break;
    }
  }
  if (!clicked) {
    throw new Error("Could not locate the TopBar upload button");
  }
  const dialog = page.locator('[role="dialog"]').first();
  await dialog.waitFor({ state: "visible", timeout: 15_000 });
  // give the connector/my-assets queries time to resolve & UI to settle
  await page.waitForTimeout(3500);
  await stabilize(page);
}

interface ModalState {
  dialogText: string;
  hasCombobox: boolean;
  hasUploadDestinationLabel: boolean;
  hasS3ConnectorLabel: boolean;
  hasMyAssetsText: boolean;
  hasPersonalPrivateChip: boolean;
  hasOldUploadingToBanner: boolean;
  hasUppyDashboard: boolean;
  hasNoDestinationsMsg: boolean;
  comboboxOptions: string[];
}

async function inspectModal(page: Page): Promise<ModalState> {
  const dialog = page.locator('[role="dialog"]').first();
  const dialogText = (await dialog.innerText().catch(() => "")) || "";
  const combobox = dialog.locator('[role="combobox"]');
  const hasCombobox = (await combobox.count()) > 0;

  let comboboxOptions: string[] = [];
  if (hasCombobox) {
    await combobox
      .first()
      .click()
      .catch(() => {});
    await page.waitForTimeout(800);
    const opts = page.locator('[role="option"]');
    const n = await opts.count();
    for (let i = 0; i < n; i++) {
      comboboxOptions.push(
        (
          (await opts
            .nth(i)
            .innerText()
            .catch(() => "")) || ""
        ).trim()
      );
    }
    // close the listbox
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(400);
  }

  return {
    dialogText,
    hasCombobox,
    hasUploadDestinationLabel: /Upload Destination/i.test(dialogText),
    hasS3ConnectorLabel: /S3 Connector/i.test(dialogText),
    hasMyAssetsText: /My Assets/i.test(dialogText),
    hasPersonalPrivateChip: /Personal\s*·\s*Private/i.test(dialogText),
    hasOldUploadingToBanner:
      /Uploading to:/i.test(dialogText) || /personal\/[0-9a-f]/i.test(dialogText),
    hasUppyDashboard: (await dialog.locator(".uppy-Dashboard").count()) > 0,
    hasNoDestinationsMsg: /don'?t have access to any upload destinations/i.test(dialogText),
    comboboxOptions,
  };
}

function logState(label: string, s: ModalState) {
  console.log(`  --- ${label}: modal state ---`);
  console.log(`    label "Upload Destination": ${s.hasUploadDestinationLabel}`);
  console.log(`    old "S3 Connector" label:   ${s.hasS3ConnectorLabel}`);
  console.log(`    dropdown (combobox):        ${s.hasCombobox}`);
  console.log(`    combobox options:           ${JSON.stringify(s.comboboxOptions)}`);
  console.log(`    My Assets present:          ${s.hasMyAssetsText}`);
  console.log(`    Personal·Private chip:      ${s.hasPersonalPrivateChip}`);
  console.log(`    OLD "Uploading to:" banner: ${s.hasOldUploadingToBanner}`);
  console.log(`    Uppy dashboard present:     ${s.hasUppyDashboard}`);
  console.log(`    "no destinations" message:  ${s.hasNoDestinationsMsg}`);
}

async function closeModal(page: Page) {
  const close = page.locator('[role="dialog"] button:has-text("Close")').first();
  if (await close.isVisible().catch(() => false)) await close.click().catch(() => {});
  else await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(500);
}

// ════════════════════════════════════════════════════════════════════════
test.describe("Upload destination picker — My Assets changes", () => {
  test.setTimeout(180_000);

  test("Scenario A: user WITH connector access (editors)", async ({ browser }) => {
    const ctx = await newCtx(browser);
    const page = await ctx.newPage();
    const hits: ApiHit[] = [];
    const consoleErrors: string[] = [];
    trackApi(page, hits);
    page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

    await loginViaUI(page, USER_A.email, USER_A.password);
    await settleAfterLogin(page);

    // --- TopBar global upload modal ---
    await openTopBarUploadModal(page);
    await shot(page, "A1-topbar-upload-modal");
    const sA = await inspectModal(page);
    logState("Scenario A / TopBar", sA);
    summarizeApi("Scenario A", hits);

    const connHitA = hits.find((h) => h.url.includes("/search/connectors"));
    expect
      .soft(connHitA?.status, "GET /search/connectors should return HTTP 200 for editors")
      .toBe(200);
    // The /search/connectors response must NOT leak my-assets / internal connectors.
    let connListA: any[] = [];
    try {
      connListA = JSON.parse(connHitA?.body || "{}")?.data?.connectors || [];
    } catch {}
    const leakedApiA = connListA.filter(
      (c) =>
        /my-assets/i.test(c?.id || "") ||
        c?.type === "my-assets" ||
        /My Assets System|personal-assets/i.test(`${c?.name || ""} ${c?.storageIdentifier || ""}`)
    );
    console.log(
      `    /search/connectors returned ids: ${JSON.stringify(connListA.map((c) => c?.id))}`
    );
    expect
      .soft(
        leakedApiA.length,
        "no my-assets/internal connector should be returned by /search/connectors"
      )
      .toBe(0);
    // The dropdown must not surface the internal "My Assets System Connector".
    const leakedOptionA = sA.comboboxOptions.filter((o) =>
      /My Assets System Connector|personal-assets/i.test(o)
    );
    expect
      .soft(
        leakedOptionA.length,
        "internal 'My Assets System Connector' must not appear in the dropdown"
      )
      .toBe(0);
    expect.soft(sA.hasUploadDestinationLabel, "label should read 'Upload Destination'").toBe(true);
    expect.soft(sA.hasS3ConnectorLabel, "old 'S3 Connector' label should be GONE").toBe(false);
    expect.soft(sA.hasCombobox, "dropdown should be present when 2+ destinations").toBe(true);
    expect.soft(sA.hasMyAssetsText, "My Assets should be an option").toBe(true);
    expect
      .soft(sA.hasOldUploadingToBanner, "old 'Uploading to: personal/...' banner removed")
      .toBe(false);
    await closeModal(page);

    // --- Assets page My Assets scoped upload ---
    await navigateToAssets(page);
    await stabilize(page);
    const myAssets = page.locator('text="My Assets"').first();
    if (await myAssets.isVisible().catch(() => false)) {
      await myAssets.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1500);
    }
    await stabilize(page);
    await shot(page, "A2-assets-myassets-view");
    const uploadButton = page.locator('button:has-text("Upload")').first();
    expect
      .soft(await uploadButton.isVisible().catch(() => false), "Assets Upload button visible")
      .toBe(true);
    if (await uploadButton.isVisible().catch(() => false)) {
      await uploadButton.click();
      const dlg = page.locator('[role="dialog"]').first();
      await dlg.waitFor({ state: "visible", timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(3000);
      await stabilize(page);
      await shot(page, "A3-assets-upload-modal-scoped");
      const sAa = await inspectModal(page);
      logState("Scenario A / Assets scoped", sAa);
      expect.soft(sAa.hasCombobox, "scoped (locked) modal must NOT show a dropdown").toBe(false);
      expect.soft(sAa.hasMyAssetsText, "scoped modal shows My Assets").toBe(true);
      expect.soft(sAa.hasUppyDashboard, "scoped modal shows Uppy dashboard").toBe(true);
      await closeModal(page);
    }

    console.log(`  console errors: ${consoleErrors.length}`);
    consoleErrors.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 160)}`));
    await ctx.close();
  });

  test("Scenario B: user WITHOUT connector access (personal-uploaders)", async ({ browser }) => {
    const ctx = await newCtx(browser);
    const page = await ctx.newPage();
    const hits: ApiHit[] = [];
    const consoleErrors: string[] = [];
    trackApi(page, hits);
    page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

    await loginViaUI(page, USER_B.email, USER_B.password);
    await settleAfterLogin(page);

    // --- TopBar global upload modal ---
    await openTopBarUploadModal(page);
    await shot(page, "B1-topbar-upload-modal");
    const sB = await inspectModal(page);
    logState("Scenario B / TopBar", sB);
    summarizeApi("Scenario B", hits);

    // Expected (post-fix) behavior for a user WITHOUT search:view:
    //  * GET /search/connectors must be HTTP 403 in the captured network hits.
    //  * The modal shows the read-only "My Assets" card (Personal · Private),
    //    NOT a dropdown/combobox, since My Assets is the only destination.
    const connHitB = hits.find((h) => h.url.includes("/search/connectors"));
    expect
      .soft(
        connHitB?.status,
        "GET /search/connectors should return HTTP 403 for personal-uploaders"
      )
      .toBe(403);
    expect
      .soft(sB.hasCombobox, "no dropdown/combobox when My Assets is the only destination")
      .toBe(false);
    expect.soft(sB.hasMyAssetsText, "read-only My Assets card must be present").toBe(true);
    expect.soft(sB.hasPersonalPrivateChip, "My Assets card shows 'Personal · Private'").toBe(true);
    expect.soft(sB.hasNoDestinationsMsg, "should NOT show 'no destinations' message").toBe(false);
    expect
      .soft(sB.hasUppyDashboard, "user can still proceed to upload (Uppy dashboard)")
      .toBe(true);
    expect
      .soft(sB.hasOldUploadingToBanner, "old 'Uploading to: personal/...' banner removed")
      .toBe(false);
    // Leakage check: no other (real) connector should be visible
    expect
      .soft(/\bs2\b/.test(sB.dialogText), "no other connector (s2) should be leaked")
      .toBe(false);
    expect.soft(sB.hasS3ConnectorLabel, "no real S3 connector leaked into the modal").toBe(false);
    await closeModal(page);

    // --- Assets page My Assets scoped upload ---
    await navigateToAssets(page);
    await stabilize(page);
    const myAssets = page.locator('text="My Assets"').first();
    if (await myAssets.isVisible().catch(() => false)) {
      await myAssets.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1500);
    }
    await stabilize(page);
    await shot(page, "B2-assets-myassets-view");
    const uploadButton = page.locator('button:has-text("Upload")').first();
    expect
      .soft(await uploadButton.isVisible().catch(() => false), "Assets Upload button visible")
      .toBe(true);
    if (await uploadButton.isVisible().catch(() => false)) {
      await uploadButton.click();
      const dlg = page.locator('[role="dialog"]').first();
      await dlg.waitFor({ state: "visible", timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(3000);
      await stabilize(page);
      await shot(page, "B3-assets-upload-modal-scoped");
      const sBa = await inspectModal(page);
      logState("Scenario B / Assets scoped", sBa);
      expect.soft(sBa.hasCombobox, "scoped (locked) modal must NOT show a dropdown").toBe(false);
      expect.soft(sBa.hasMyAssetsText, "scoped modal shows My Assets").toBe(true);
      expect.soft(sBa.hasUppyDashboard, "scoped modal shows Uppy dashboard").toBe(true);
      await closeModal(page);
    }

    console.log(`  console errors: ${consoleErrors.length}`);
    consoleErrors.slice(0, 5).forEach((e) => console.log(`    - ${e.substring(0, 160)}`));
    await ctx.close();
  });
});
