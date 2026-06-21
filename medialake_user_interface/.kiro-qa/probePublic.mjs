import { chromium } from "@playwright/test";
import { BASE, SHOTS } from "./lib.mjs";

const SLUG = process.argv[2];
const log = (...a) => console.log("[pub]", ...a);
const browser = await chromium.launch({ headless: true });

for (let attempt = 1; attempt <= 4; attempt++) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const reqs = [];
  page.on("response", async (res) => {
    const u = res.url();
    if (/portal/i.test(u) && /\/v1\//.test(u)) {
      let body = "";
      try { body = (await res.text()).slice(0, 300); } catch {}
      reqs.push({ status: res.status(), method: res.request().method(), url: u, body });
    }
  });
  await page.goto(`${BASE}/p/${SLUG}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3000);
  const bodyLen = await page.evaluate(() => (document.body.innerText || "").trim().length);
  log(`attempt ${attempt}: body length=${bodyLen}; portal API calls=`, JSON.stringify(reqs));
  if (attempt === 4) await page.screenshot({ path: `${SHOTS}/probe-public-final.png`, fullPage: true }).catch(() => {});
  await ctx.close();
  if (attempt < 4) await new Promise((r) => setTimeout(r, 4000));
}
await browser.close();
