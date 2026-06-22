import { chromium } from "@playwright/test";
import { BASE, SHOTS, dumpUI } from "./lib.mjs";

// STEP 6 final artifact — capture what a real visitor sees above-the-fold on
// page 1 of the public portal at desktop/tablet/mobile, AFTER the primary
// control (Next) is actually visible. Records the element inventory + overflow.

const SLUG = process.argv[2] || "qa-auto-1782076662";
const log = (...a) => console.log("[fin]", ...a);

const overflow = () => {
  const de = document.documentElement;
  const docW = Math.max(de.scrollWidth, document.body?.scrollWidth || 0);
  return { iw: window.innerWidth, docW: Math.round(docW), overflowPx: Math.round(docW - window.innerWidth) };
};

const browser = await chromium.launch({ headless: true });

for (const vp of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 1024, height: 768 },
  { name: "mobile", width: 390, height: 844 },
]) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/p/${SLUG}`, { waitUntil: "domcontentloaded" });

  // Wait for the actual primary control to be visible (Playwright actionability).
  const next = page.getByRole("button", { name: /next|continue/i }).first();
  const seen = await next
    .waitFor({ state: "visible", timeout: 20000 })
    .then(() => true)
    .catch(() => false);
  await page.waitForTimeout(800);

  const ui = await dumpUI(page);
  const of = await page.evaluate(overflow);
  log(`\n=== ${vp.name} (${vp.width}x${vp.height}) ===`);
  log("Next visible:", seen, "| overflow:", JSON.stringify(of));
  log("headings:", JSON.stringify(ui.h));
  log("buttons:", JSON.stringify(ui.buttons));
  log("inputs:", JSON.stringify(ui.inputs.map((i) => i.label || i.ph || i.name || i.type)));

  // Viewport-only (above-the-fold) screenshot — the right responsive artifact.
  await page.screenshot({ path: `${SHOTS}/step6-${vp.name}-p1-final.png`, fullPage: false }).catch(() => {});
  await ctx.close();
}
await browser.close();
