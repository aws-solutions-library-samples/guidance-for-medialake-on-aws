import { launch, BASE, SHOTS } from "./lib.mjs";

// FLOW A — create + publish a multi-page portal, look for a conditional boolean field.
const TS = Date.now();
const SLUG = `qa-auto-${TS}`;
const NAME = `qa-auto Portal ${TS}`;
const TAG = `qa-auto-tag-${TS}`;

const { browser, page, consoleErrors, pageErrors } = await launch();
const log = (...a) => console.log("[flowA]", ...a);

// Capture portal API traffic so we have ground-truth on save/publish.
const api = [];
page.on("response", async (res) => {
  const u = res.url();
  if (/\/portals(\b|\/|\?)/.test(u) && res.request().method() !== "GET") {
    let body = "";
    try { body = (await res.text()).slice(0, 400); } catch {}
    api.push({ method: res.request().method(), status: res.status(), url: u, body });
  }
});

const shot = async (n) => { await page.screenshot({ path: `${SHOTS}/flowA-${n}.png`, fullPage: true }).catch(() => {}); };

// Expand a sidebar group accordion then a section accordion within it.
async function openSection(groupKey, sectionKey) {
  const grp = page.locator(`#portal-editor-group-${groupKey}-header`);
  if (await grp.count()) {
    const expanded = await grp.getAttribute("aria-expanded");
    if (expanded !== "true") { await grp.click(); await page.waitForTimeout(300); }
  }
  const sec = page.locator(`#portal-editor-section-${sectionKey}-header`);
  await sec.scrollIntoViewIfNeeded().catch(() => {});
  const secExpanded = await sec.getAttribute("aria-expanded");
  if (secExpanded !== "true") { await sec.click(); await page.waitForTimeout(500); }
  await page.locator(`#portal-editor-section-${sectionKey}-content`).waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
}

// Dump the visible text + control labels of a section body (for conditional-logic discovery).
async function dumpSection(sectionKey) {
  return await page.evaluate((key) => {
    const root = document.getElementById(`portal-editor-section-${key}-content`);
    if (!root) return { found: false };
    const labels = Array.from(root.querySelectorAll("label,[aria-label],button,legend")).map((el) =>
      (el.getAttribute("aria-label") || el.textContent || "").trim().replace(/\s+/g, " ")
    ).filter(Boolean);
    return { found: true, text: (root.innerText || "").replace(/\s+/g, " ").slice(0, 600), labels: Array.from(new Set(labels)).slice(0, 40) };
  }, sectionKey);
}

async function readToast() {
  try {
    const alert = page.getByRole("alert").last();
    await alert.waitFor({ state: "visible", timeout: 8000 });
    const t = (await alert.innerText()).replace(/\s+/g, " ").trim();
    return t;
  } catch { return "(no toast captured)"; }
}

try {
  await page.goto(`${BASE}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2500);
  log("URL after open:", page.url());
  await shot("01-editor-open");

  // ---- STEP 1: name + slug (Content section, Appearance group) ----
  await openSection("appearance", "content");
  await page.locator('input[aria-label="Portal name"]').fill(NAME);
  await page.locator('input[aria-label="Portal slug"]').fill(SLUG);
  await page.waitForTimeout(500);
  const slugVal = await page.locator('input[aria-label="Portal slug"]').inputValue();
  const nameVal = await page.locator('input[aria-label="Portal name"]').inputValue();
  log("name set:", JSON.stringify(nameVal), "slug set:", JSON.stringify(slugVal));
  await shot("02-content-name-slug");

  // ---- STEP 2: Pages & Workflow — inspect default pages, add a 2nd page ----
  await openSection("structure", "pages");
  await page.waitForTimeout(400);
  const pagesBefore = await page.locator('[aria-label^="Reorder page "]').count();
  log("pages before Add Page:", pagesBefore);
  await page.getByRole("button", { name: "Add Page" }).click();
  await page.waitForTimeout(700);
  const pagesAfter = await page.locator('[aria-label^="Reorder page "]').count();
  log("pages after Add Page:", pagesAfter);
  // Ensure an uploader is placed on page 1 (needed for publish validation).
  const setUploader1 = page.locator('[aria-label="Set uploader on page 1"]');
  if (await setUploader1.count()) { await setUploader1.click(); await page.waitForTimeout(400); log("clicked Set uploader on page 1"); }
  const pagesDump = await dumpSection("pages");
  log("PAGES section labels:", JSON.stringify(pagesDump.labels));
  await shot("03-pages");

  // ---- STEP 3: Field Configuration — add a Yes/No boolean field ----
  await openSection("structure", "fields");
  await page.waitForTimeout(400);
  const fieldsBefore = await page.getByRole("button", { name: "Add Field" }).count();
  log("Add Field button present:", fieldsBefore);
  await page.getByRole("button", { name: "Add Field" }).click();
  await page.waitForTimeout(700);
  // Set the new field's label.
  const labelInput = page.getByLabel("Field label").first();
  if (await labelInput.count()) { await labelInput.fill("Needs Review"); await page.waitForTimeout(300); }
  // Set type -> Yes / No (boolean).
  const typeSelect = page.locator('[aria-label^="Field type for"]').first();
  if (await typeSelect.count()) {
    await typeSelect.click();
    await page.waitForTimeout(300);
    const opt = page.getByRole("option", { name: "Yes / No" });
    if (await opt.count()) { await opt.click(); log("selected Yes / No type"); }
    else { log("Yes / No option NOT found"); await page.keyboard.press("Escape"); }
    await page.waitForTimeout(400);
  } else {
    log("field type select NOT found");
  }
  const fieldsDump = await dumpSection("fields");
  log("FIELDS section text:", JSON.stringify(fieldsDump.text));
  log("FIELDS section labels:", JSON.stringify(fieldsDump.labels));
  // Conditional-logic discovery: search the whole sidebar for any conditional control.
  const condHits = await page.evaluate(() => {
    const re = /(visible\s*if|conditional|show\s*(this\s*)?(field|when|if)|depends?\s*on|enable\s*if|logic)/i;
    const out = [];
    document.querySelectorAll("button,label,legend,span,p,h1,h2,h3,h4,h5,h6,[aria-label]").forEach((el) => {
      const t = (el.getAttribute("aria-label") || el.textContent || "").trim();
      if (t && re.test(t) && t.length < 80) out.push(t);
    });
    return Array.from(new Set(out)).slice(0, 30);
  });
  log("CONDITIONAL-LOGIC control hits across sidebar:", JSON.stringify(condHits));
  await shot("04-fields-boolean");

  // ---- STEP 4: Automation Tag (Upload Limits & File Settings = metadata section) ----
  await openSection("structure", "metadata");
  await page.waitForTimeout(400);
  const tagInput = page.getByLabel("Automation Tag");
  if (await tagInput.count()) { await tagInput.fill(TAG); log("automation tag set:", TAG); }
  else { log("Automation Tag input NOT found"); }
  await shot("05-automation-tag");

  // ---- STEP 5: Destination ----
  await openSection("structure", "destinations");
  await page.waitForTimeout(400);
  const addDest = page.getByRole("button", { name: "Add Destination" });
  if (await addDest.count()) {
    await addDest.click();
    await page.waitForTimeout(800);
    await page.waitForTimeout(3500); // let the /connectors query settle
    // Friendly name
    const fn = page.getByLabel("Friendly Name");
    if (await fn.count()) await fn.fill(`qa-auto-dest-${TS}`);
    // Connector select — click the MUI combobox inside the dialog (NOT the hidden input).
    const connSelect = page.locator('[role="dialog"] [role="combobox"]').first();
    let connectorOptions = [];
    if (await connSelect.count()) {
      await connSelect.click();
      await page.waitForTimeout(1000);
      connectorOptions = await page.locator('li[role="option"]').allInnerTexts();
      log("connector options:", JSON.stringify(connectorOptions));
      if (connectorOptions.length > 0) {
        await page.locator('li[role="option"]').first().click();
        log("selected first connector:", connectorOptions[0]);
      } else {
        await page.keyboard.press("Escape");
      }
      await page.waitForTimeout(500);
    }
    await shot("06-destination-form");
    // Save the destination (dialog submit button).
    const saveDest = page.locator('[role="dialog"]').getByRole("button", { name: /Add Destination|Update Destination/ }).last();
    if (await saveDest.count() && connectorOptions.length > 0) {
      await saveDest.click();
      await page.waitForTimeout(1000);
      const destCount = await page.locator('[aria-label^="Edit "]').count();
      log("destination saved; destination cards:", destCount);
    } else {
      log("NO connectors available — cannot save a destination in this environment");
      // close dialog
      const cancel = page.getByRole("button", { name: "Cancel" }).last();
      if (await cancel.count()) await cancel.click();
    }
  } else {
    log("Add Destination button NOT found");
  }
  await shot("07-destinations");

  // ---- STEP 6: Save ----
  const saveBtn = page.getByRole("button", { name: "Save", exact: true });
  const saveDisabled = await saveBtn.isDisabled().catch(() => true);
  log("Save button disabled?", saveDisabled);
  if (!saveDisabled) {
    await saveBtn.click();
    const toast = await readToast();
    log("SAVE toast:", JSON.stringify(toast));
    await page.waitForTimeout(1500);
  }
  await shot("08-after-save");
  log("URL after save:", page.url());

  // ---- STEP 7: Publish ----
  const pubBtn = page.getByRole("button", { name: "Publish", exact: true });
  if (await pubBtn.count()) {
    const pubDisabled = await pubBtn.isDisabled().catch(() => true);
    log("Publish disabled?", pubDisabled);
    if (!pubDisabled) {
      await pubBtn.click();
      const toast = await readToast();
      log("PUBLISH toast:", JSON.stringify(toast));
      await page.waitForTimeout(2000);
    }
  }
  await shot("09-after-publish");
  log("URL after publish:", page.url());

  log("API calls (portals):", JSON.stringify(api, null, 0));
  log("SLUG used:", SLUG);
} catch (e) {
  log("ERROR:", e.message);
  await shot("ERROR");
} finally {
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 12)));
  log("page errors:", JSON.stringify(pageErrors.slice(0, 6)));
  await browser.close();
}
