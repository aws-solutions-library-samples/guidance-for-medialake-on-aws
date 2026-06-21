import { launch, BASE, SHOTS } from "./lib.mjs";

const { browser, page, consoleErrors } = await launch();
const log = (...a) => console.log("[probe]", ...a);

const conn = [];
page.on("response", async (res) => {
  const u = res.url();
  if (/\/connectors(\b|\/|\?)/.test(u)) {
    let body = "";
    try { body = (await res.text()).slice(0, 600); } catch {}
    conn.push({ method: res.request().method(), status: res.status(), url: u, body });
  }
});

try {
  await page.goto(`${BASE}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(4000);

  // Open Structure > Destinations and the Add Destination dialog, wait for connectors to load.
  const grp = page.locator(`#portal-editor-group-structure-header`);
  if (await grp.count()) { const e = await grp.getAttribute("aria-expanded"); if (e !== "true") await grp.click(); }
  await page.waitForTimeout(300);
  const sec = page.locator(`#portal-editor-section-destinations-header`);
  if (await sec.count()) { const e = await sec.getAttribute("aria-expanded"); if (e !== "true") await sec.click(); }
  await page.waitForTimeout(500);
  const addDest = page.getByRole("button", { name: "Add Destination" });
  if (await addDest.count()) { await addDest.click(); await page.waitForTimeout(4000); }
  const connSelect = page.getByLabel("Connector").first();
  let opts = [];
  if (await connSelect.count()) {
    await connSelect.click();
    await page.waitForTimeout(1500);
    opts = await page.getByRole("option").allInnerTexts();
    await page.keyboard.press("Escape");
  }
  log("connector dropdown options (after 4s wait):", JSON.stringify(opts));
  await page.screenshot({ path: `${SHOTS}/probe-connectors.png`, fullPage: true }).catch(() => {});

  // Also probe the connectors API directly via the app's authenticated fetch.
  const apiProbe = await page.evaluate(async () => {
    // Try to discover the API base from any axios/fetch config on window, else guess common patterns.
    const tryUrls = [];
    // The app stores API base in a runtime config; attempt window.__APP_CONFIG__ or env.
    const cfg = (window).__APP_CONFIG__ || (window).appConfig || {};
    return { cfgKeys: Object.keys(cfg), note: "see network capture for real /connectors response" };
  });
  log("app config keys:", JSON.stringify(apiProbe));
} catch (e) {
  log("ERROR:", e.message);
} finally {
  log("CONNECTORS API responses:", JSON.stringify(conn, null, 0));
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 12)));
  await browser.close();
}
