import { chromium } from "@playwright/test";
import { BASE, STATE, SHOTS, dumpUI } from "./lib.mjs";

const SLUG = process.argv[2];
if (!SLUG) { console.error("usage: node flowA_verify.mjs <slug>"); process.exit(1); }
const log = (...a) => console.log("[verifyA]", ...a);

const browser = await chromium.launch({ headless: true });

// ---------- PART 1: authed portals list ----------
try {
  const ctx = await browser.newContext({ storageState: STATE, viewport: { width: 1440, height: 900 }, colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2500);
  // Find the row for our slug/name.
  const rowInfo = await page.evaluate((slug) => {
    const rows = Array.from(document.querySelectorAll("tr,li,[role=row]"));
    const match = rows.find((r) => (r.innerText || "").includes(slug));
    const result = { matched: !!match, rowText: match ? (match.innerText || "").replace(/\s+/g, " ").slice(0, 240) : null };
    // collect any /p/ links on the page
    const pLinks = Array.from(document.querySelectorAll('a[href*="/p/"]')).map((a) => a.getAttribute("href"));
    result.pLinks = Array.from(new Set(pLinks)).slice(0, 20);
    return result;
  }, SLUG);
  log("PORTALS LIST row match:", JSON.stringify(rowInfo));
  await page.screenshot({ path: `${SHOTS}/verifyA-01-list.png`, fullPage: true }).catch(() => {});
  await ctx.close();
} catch (e) { log("PART1 ERROR:", e.message); }

// ---------- PART 2: PUBLIC page (no auth) ----------
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  const url = `${BASE}/p/${SLUG}`;
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3500);
  log("PUBLIC url:", page.url());
  const ui1 = await dumpUI(page);
  log("PUBLIC page1 headings:", JSON.stringify(ui1.h));
  log("PUBLIC page1 buttons:", JSON.stringify(ui1.buttons));
  log("PUBLIC page1 inputs:", JSON.stringify(ui1.inputs));
  // Did we hit an access gate (passcode/email) or land straight in (public)?
  const bodyText = await page.evaluate(() => (document.body.innerText || "").replace(/\s+/g, " ").slice(0, 500));
  log("PUBLIC body text:", JSON.stringify(bodyText));
  await page.screenshot({ path: `${SHOTS}/verifyA-02-public-page1.png`, fullPage: true }).catch(() => {});

  // Look for the boolean field "Needs Review" and any Next/navigation button.
  const hasBoolean = await page.getByText(/Needs Review/i).count();
  log("PUBLIC 'Needs Review' boolean present on page1:", hasBoolean);

  // Try to advance to page 2 (SurveyJS "Next" or similar).
  const nextBtn = page.getByRole("button", { name: /next|continue/i }).first();
  if (await nextBtn.count()) {
    await nextBtn.click().catch(() => {});
    await page.waitForTimeout(2000);
    const ui2 = await dumpUI(page);
    log("PUBLIC after Next — headings:", JSON.stringify(ui2.h));
    log("PUBLIC after Next — buttons:", JSON.stringify(ui2.buttons));
    await page.screenshot({ path: `${SHOTS}/verifyA-03-public-page2.png`, fullPage: true }).catch(() => {});
  } else {
    log("PUBLIC no Next/Continue button found (single-page render or boolean gates nav)");
  }
  log("PUBLIC console errors:", JSON.stringify(consoleErrors.slice(0, 10)));
  await ctx.close();
} catch (e) { log("PART2 ERROR:", e.message); }

await browser.close();
