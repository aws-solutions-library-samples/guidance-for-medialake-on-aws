import { launch, BASE, SHOTS, dumpUI } from "./lib.mjs";

const { browser, page, consoleErrors } = await launch();
const log = (...a) => console.log("[explore]", ...a);

async function visit(path, name, settleMs = 3000) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(settleMs);
  const ui = await dumpUI(page);
  log(`=== ${name} (${path}) ===`);
  log("URL:", ui.url);
  log("headings:", JSON.stringify(ui.h));
  log("tabs:", JSON.stringify(ui.tabs));
  log("buttons:", JSON.stringify(ui.buttons));
  log("inputs:", JSON.stringify(ui.inputs));
  await page.screenshot({ path: `${SHOTS}/explore-${name}.png`, fullPage: true });
}

try {
  await visit("/settings/upload-portals", "portals-list");
  await visit("/settings/upload-portals/new", "portal-new-editor", 4000);
} catch (e) {
  log("ERROR:", e.message);
  await page.screenshot({ path: `${SHOTS}/explore-ERROR.png` }).catch(() => {});
} finally {
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 8)));
  await browser.close();
}
