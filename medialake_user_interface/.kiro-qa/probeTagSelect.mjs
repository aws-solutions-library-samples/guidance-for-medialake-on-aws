import { launch, BASE, SHOTS } from "./lib.mjs";

// Focused probe: open the Upload Batch Completed trigger config, wait generously
// for the Automation Tag select to populate, and capture any failing network
// requests (4xx/5xx) to determine WHY the dropdown is empty.
const { browser, page, consoleErrors } = await launch({ viewport: { width: 1728, height: 1080 } });
const log = (...a) => console.log("[probeTag]", ...a);

const failed = [];
page.on("response", (res) => {
  const s = res.status();
  if (s >= 400) failed.push({ status: s, method: res.request().method(), url: res.url().replace(BASE, "") });
});

async function dragNodeToCanvas(title, dropX, dropY) {
  const item = page.locator('div.MuiPaper-root[draggable="true"]', { hasText: title }).first();
  await item.scrollIntoViewIfNeeded().catch(() => {});
  await item.waitFor({ state: "visible", timeout: 12000 });
  const canvas = page.locator(".react-flow").first();
  await canvas.waitFor({ state: "visible", timeout: 12000 });
  const cb = await canvas.boundingBox();
  const x = cb.x + dropX, y = cb.y + dropY;
  const dt = await page.evaluateHandle(() => new DataTransfer());
  await item.dispatchEvent("dragstart", { dataTransfer: dt });
  await canvas.dispatchEvent("dragenter", { dataTransfer: dt, clientX: x, clientY: y });
  await canvas.dispatchEvent("dragover", { dataTransfer: dt, clientX: x, clientY: y });
  await canvas.dispatchEvent("drop", { dataTransfer: dt, clientX: x, clientY: y });
  await page.waitForTimeout(1000);
}

try {
  await page.goto(`${BASE}/settings/pipelines/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 25000 }).catch(() => {});
  await page.waitForTimeout(4000);

  const search = page.getByPlaceholder("Search nodes...");
  if (await search.count()) { await search.fill("Upload Batch"); await page.waitForTimeout(800); }
  await dragNodeToCanvas("Upload Batch Completed", 360, 280);
  await page.waitForTimeout(2000);

  const dialog = page.locator('[role="dialog"]').last();
  const combos = dialog.locator('[role="combobox"]');
  const n = await combos.count();
  log("comboboxes:", n);

  // Open the Automation Tag combobox (first one) and wait up to ~8s for options.
  await combos.first().click().catch(() => {});
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(1000);
    const opts = await page.locator('li[role="option"]').allInnerTexts().catch(() => []);
    if (opts.length) { log(`Automation Tag options after ${i + 1}s:`, JSON.stringify(opts)); break; }
    if (i === 7) log("Automation Tag options after 8s: STILL EMPTY");
  }
  await page.screenshot({ path: `${SHOTS}/step4-tag-select-open.png`, fullPage: false }).catch(() => {});

  // Inspect the rendered select markup for the Automation Tag field.
  const markup = await page.evaluate(() => {
    const dlg = document.querySelectorAll('[role="dialog"]');
    const d = dlg[dlg.length - 1];
    if (!d) return "(no dialog)";
    const fcs = Array.from(d.querySelectorAll(".MuiFormControl-root")).map((fc) => {
      const lab = fc.querySelector("label")?.innerText?.trim();
      const menuItems = fc.querySelectorAll('li[role="option"], option').length;
      return { label: lab, menuItems };
    });
    const openMenuItems = Array.from(document.querySelectorAll('li[role="option"]')).map((li) => li.innerText.trim());
    return { fcs, openMenuItems };
  });
  log("FIELD markup:", JSON.stringify(markup));
  log("FAILED requests (>=400):", JSON.stringify(failed));
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 12)));
} catch (e) {
  log("ERROR:", e.message);
} finally {
  await browser.close();
}
