import { launch, BASE, SHOTS } from "./lib.mjs";

const { browser, page, consoleErrors } = await launch();
const log = (...a) => console.log("[probe2]", ...a);

try {
  await page.goto(`${BASE}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(4000);

  const grp = page.locator(`#portal-editor-group-structure-header`);
  if (await grp.count()) { const e = await grp.getAttribute("aria-expanded"); if (e !== "true") await grp.click(); }
  await page.waitForTimeout(300);
  const sec = page.locator(`#portal-editor-section-destinations-header`);
  if (await sec.count()) { const e = await sec.getAttribute("aria-expanded"); if (e !== "true") await sec.click(); }
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "Add Destination" }).click();
  await page.waitForTimeout(4000); // allow connectors query to settle

  // Dump the dialog structure.
  const dialogInfo = await page.evaluate(() => {
    const dlg = document.querySelector('[role="dialog"]');
    if (!dlg) return { found: false };
    const combo = dlg.querySelector('[role="combobox"], .MuiSelect-select');
    const hiddenSelect = dlg.querySelector('input[aria-hidden="true"], select');
    return {
      found: true,
      comboText: combo ? (combo.textContent || "").trim() : null,
      comboAria: combo ? combo.getAttribute("aria-label") : null,
      hiddenValue: hiddenSelect ? hiddenSelect.value : null,
    };
  });
  log("dialog info:", JSON.stringify(dialogInfo));

  // Open the MUI Select by clicking the combobox node directly.
  const combo = page.locator('[role="dialog"] [role="combobox"]').first();
  let optionTexts = [];
  if (await combo.count()) {
    await combo.click();
    await page.waitForTimeout(1200);
    // MUI renders the listbox in a portal at body root.
    optionTexts = await page.locator('li[role="option"]').allInnerTexts();
    await page.screenshot({ path: `${SHOTS}/probe2-connector-menu.png` }).catch(() => {});
    await page.keyboard.press("Escape");
  } else {
    log("combobox not found in dialog");
  }
  log("connector option texts:", JSON.stringify(optionTexts));
} catch (e) {
  log("ERROR:", e.message);
  await page.screenshot({ path: `${SHOTS}/probe2-ERROR.png` }).catch(() => {});
} finally {
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 10)));
  await browser.close();
}
