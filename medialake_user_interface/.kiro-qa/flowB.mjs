import { launch, BASE, SHOTS, dumpUI } from "./lib.mjs";

// FLOW B + C — pipeline editor: add "Upload Batch Completed" trigger, configure
// Automation Tag + Completion Outcome, add "Mark Upload Processing Complete"
// downstream, connect, then Save (= deploy via createPipeline) and capture result.
const TS = Date.now();
const PIPE = `qa-auto-pipe-${TS}`;
const TAG = "qa-auto-tag-1782057039335"; // automation tag created in Flow A

// Wide viewport => full toolbar mode + room on canvas.
const { browser, page, consoleErrors, pageErrors } = await launch({
  viewport: { width: 1728, height: 1080 },
});
const log = (...a) => console.log("[flowB]", ...a);

// Ground-truth API capture.
const nodeApi = [];
const pipeApi = [];
page.on("response", async (res) => {
  const u = res.url();
  const m = res.request().method();
  if (/\/nodes(\b|\/|\?)/.test(u) && m === "GET") {
    let b = ""; try { b = await res.text(); } catch {}
    nodeApi.push({ status: res.status(), body: b });
  }
  if (/\/pipelines(\b|\/|\?)/.test(u) && m !== "GET") {
    let b = ""; try { b = (await res.text()).slice(0, 800); } catch {}
    pipeApi.push({ method: m, status: res.status(), url: u, body: b });
  }
});

const shot = async (n) => {
  await page.screenshot({ path: `${SHOTS}/flowB-${n}.png`, fullPage: false }).catch(() => {});
};

// HTML5 drag a palette Paper onto the React Flow canvas at (dropX,dropY) relative to canvas.
async function dragNodeToCanvas(title, dropX, dropY) {
  const item = page.locator('div.MuiPaper-root[draggable="true"]', { hasText: title }).first();
  await item.scrollIntoViewIfNeeded().catch(() => {});
  await item.waitFor({ state: "visible", timeout: 12000 });
  const canvas = page.locator(".react-flow").first();
  await canvas.waitFor({ state: "visible", timeout: 12000 });
  const cb = await canvas.boundingBox();
  if (!cb) throw new Error("no canvas bbox");
  const x = cb.x + dropX;
  const y = cb.y + dropY;
  const dt = await page.evaluateHandle(() => new DataTransfer());
  await item.dispatchEvent("dragstart", { dataTransfer: dt });
  await canvas.dispatchEvent("dragenter", { dataTransfer: dt, clientX: x, clientY: y });
  await canvas.dispatchEvent("dragover", { dataTransfer: dt, clientX: x, clientY: y });
  await canvas.dispatchEvent("drop", { dataTransfer: dt, clientX: x, clientY: y });
  await item.dispatchEvent("dragend", { dataTransfer: dt }).catch(() => {});
  await page.waitForTimeout(900);
}

async function countNodes() {
  return await page.locator(".react-flow__node").count();
}

// Read whatever dialog (config / api-status) is open: title + body text + buttons.
async function dumpDialog() {
  return await page.evaluate(() => {
    const dlgs = Array.from(document.querySelectorAll('[role="dialog"]'));
    return dlgs.map((d) => ({
      text: (d.innerText || "").replace(/\s+/g, " ").trim().slice(0, 500),
      buttons: Array.from(d.querySelectorAll("button"))
        .map((b) => (b.innerText || b.getAttribute("aria-label") || "").trim())
        .filter(Boolean),
      comboboxes: Array.from(d.querySelectorAll('[role="combobox"], select')).length,
    }));
  });
}

try {
  await page.goto(`${BASE}/settings/pipelines/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 25000 }).catch(() => {});
  await page.waitForTimeout(4000);
  log("URL:", page.url());

  // Report deployed automation_tag options (ground truth from /nodes).
  for (const r of nodeApi) {
    try {
      const j = JSON.parse(r.body);
      const arr = j?.data?.nodes || j?.nodes || j?.data || (Array.isArray(j) ? j : []);
      const list = Array.isArray(arr) ? arr : [];
      const ubc = list.find(
        (n) => (n.nodeId || n.id) === "upload_batch_completed" || (n.info?.title || n.title) === "Upload Batch Completed"
      );
      if (ubc) {
        const methods = ubc.methods;
        const m = Array.isArray(methods) ? methods[0] : methods?.trigger || Object.values(methods || {})[0];
        const params = m?.config?.parameters || m?.parameters || [];
        log("DEPLOYED upload_batch_completed params:", JSON.stringify(params).slice(0, 900));
      } else {
        log("upload_batch_completed not found in /nodes parse");
      }
    } catch (e) {
      log("nodes parse err:", e.message);
    }
  }

  // DOM scan: palette + canvas presence.
  const scan = await page.evaluate(() => {
    const papers = Array.from(document.querySelectorAll('div.MuiPaper-root[draggable="true"]')).map(
      (p) => (p.innerText || "").replace(/\s+/g, " ").trim().slice(0, 60)
    );
    const accordions = Array.from(document.querySelectorAll(".MuiAccordionSummary-root")).map((a) =>
      (a.innerText || "").trim()
    );
    return {
      canvas: !!document.querySelector(".react-flow"),
      pane: !!document.querySelector(".react-flow__pane"),
      paletteCount: papers.length,
      paletteItems: papers.slice(0, 12),
      accordions: accordions.slice(0, 10),
    };
  });
  log("SCAN:", JSON.stringify(scan));
  await shot("01-editor-open");

  // ---- Add TRIGGER: Upload Batch Completed (Triggers section expanded by default) ----
  // Use the search box to filter + auto-expand its section.
  const search = page.getByPlaceholder("Search nodes...");
  if (await search.count()) {
    await search.fill("Upload Batch");
    await page.waitForTimeout(800);
  }
  log("nodes before trigger drop:", await countNodes());
  await dragNodeToCanvas("Upload Batch Completed", 360, 280);
  log("nodes after trigger drop:", await countNodes());
  await shot("02-after-trigger-drop");

  // Trigger has params => Configure Node dialog should auto-open.
  await page.waitForTimeout(1500);
  let dlg = await dumpDialog();
  log("DIALOG after trigger drop:", JSON.stringify(dlg));

  // Fill the config form. Log every field + options; best-effort selection.
  const dialog = page.locator('[role="dialog"]').last();
  if (await dialog.count()) {
    // Enumerate comboboxes (MUI selects) inside the dialog.
    const combos = dialog.locator('[role="combobox"]');
    const nCombo = await combos.count();
    log("config comboboxes:", nCombo);
    for (let i = 0; i < nCombo; i++) {
      const c = combos.nth(i);
      const labelText = await c.evaluate((el) => {
        // Find associated label text by walking up to the form control.
        const fc = el.closest(".MuiFormControl-root");
        const lab = fc?.querySelector("label");
        return (lab?.innerText || "").trim();
      }).catch(() => "");
      await c.click().catch(() => {});
      await page.waitForTimeout(500);
      const opts = await page.locator('li[role="option"]').allInnerTexts().catch(() => []);
      log(`combobox[${i}] label=${JSON.stringify(labelText)} options=${JSON.stringify(opts)}`);
      // Choose: for Completion Outcome pick "Both"; for Automation Tag pick the qa tag if present, else first.
      let picked = null;
      if (/outcome|completion/i.test(labelText)) {
        const both = page.locator('li[role="option"]', { hasText: "Both" });
        if (await both.count()) { await both.first().click(); picked = "Both"; }
      } else if (/automation|tag/i.test(labelText)) {
        const tagOpt = page.locator('li[role="option"]', { hasText: TAG });
        if (await tagOpt.count()) { await tagOpt.first().click(); picked = TAG; }
      }
      if (!picked) {
        const first = page.locator('li[role="option"]').first();
        if (await first.count()) { picked = (await first.innerText()).trim(); await first.click(); }
        else { await page.keyboard.press("Escape"); picked = "(no options)"; }
      }
      log(`combobox[${i}] picked=${JSON.stringify(picked)}`);
      await page.waitForTimeout(400);
    }
    await shot("03-config-dialog-filled");
    // Submit the dialog (Form button[type=submit] = "Save"). DynamicForm submits even if invalid.
    const submit = dialog.locator('button[type="submit"]');
    if (await submit.count()) {
      await submit.first().click();
      log("clicked config dialog submit");
    } else {
      const saveBtn = dialog.getByRole("button", { name: "Save" });
      if (await saveBtn.count()) { await saveBtn.first().click(); log("clicked config Save by name"); }
      else log("NO submit button in config dialog");
    }
    await page.waitForTimeout(1500);
  } else {
    log("NO config dialog opened after trigger drop");
  }
  dlg = await dumpDialog();
  log("DIALOG after config submit:", JSON.stringify(dlg));
  await shot("04-after-config-submit");

  // ---- Add UTILITY: Mark Upload Processing Complete (Flow C barrier node) ----
  if (await search.count()) {
    await search.fill("");
    await page.waitForTimeout(300);
    await search.fill("Mark Upload");
    await page.waitForTimeout(900);
  }
  log("nodes before barrier drop:", await countNodes());
  await dragNodeToCanvas("Mark Upload Processing Complete", 760, 280);
  log("nodes after barrier drop:", await countNodes());
  await page.waitForTimeout(1200);
  // Barrier has no params -> no dialog expected. If one opened, submit/close it.
  let bdlg = await dumpDialog();
  log("DIALOG after barrier drop:", JSON.stringify(bdlg));
  if (bdlg.length) {
    const d2 = page.locator('[role="dialog"]').last();
    const s2 = d2.locator('button[type="submit"]');
    if (await s2.count()) { await s2.first().click(); log("submitted barrier dialog"); await page.waitForTimeout(1000); }
  }
  await shot("05-after-barrier-drop");

  // On-screen description of the barrier node (Flow C requirement).
  const barrierDesc = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll(".react-flow__node"));
    const b = nodes.find((n) => (n.innerText || "").includes("Mark Upload Processing Complete"));
    return b ? (b.innerText || "").replace(/\s+/g, " ").trim().slice(0, 300) : "(not found)";
  });
  log("BARRIER node on-screen text:", JSON.stringify(barrierDesc));

  // ---- Connect trigger -> barrier (connectOnClick=true) ----
  try {
    const srcHandles = page.locator(".react-flow__handle.source");
    const tgtHandles = page.locator(".react-flow__handle.target");
    const nSrc = await srcHandles.count();
    const nTgt = await tgtHandles.count();
    log("handles: source=", nSrc, "target=", nTgt);
    const edgesBefore = await page.locator(".react-flow__edge").count();
    if (nSrc > 0 && nTgt > 0) {
      await srcHandles.first().click({ force: true });
      await page.waitForTimeout(400);
      await tgtHandles.first().click({ force: true });
      await page.waitForTimeout(800);
    }
    const edgesAfter = await page.locator(".react-flow__edge").count();
    log("edges before/after connect click:", edgesBefore, edgesAfter);
  } catch (e) {
    log("connect attempt error:", e.message);
  }
  await shot("06-after-connect");

  // ---- Name + Save (deploy) ----
  const nameInput = page.getByPlaceholder("Enter pipeline name");
  await nameInput.waitFor({ state: "visible", timeout: 8000 });
  await nameInput.fill(PIPE);
  log("pipeline name set:", PIPE);
  await page.waitForTimeout(400);
  await shot("07-named");

  const saveBtn = page.getByRole("button", { name: "Save", exact: true });
  const saveDisabled = await saveBtn.first().isDisabled().catch(() => true);
  log("toolbar Save disabled?", saveDisabled, "count:", await saveBtn.count());
  if (!saveDisabled) {
    await saveBtn.first().click();
    log("clicked toolbar Save (deploy)");
    // Wait for ApiStatusModal (createPipeline). Poll dialog text up to ~30s.
    let result = "(none)";
    for (let i = 0; i < 30; i++) {
      await page.waitForTimeout(1000);
      const ds = await dumpDialog();
      const hit = ds.find((d) => /Pipeline Creation|Creating Pipeline|Pipeline Created|Failed|started|monitor/i.test(d.text));
      if (hit) { result = hit.text; if (!/Please wait/i.test(hit.text)) { log("DEPLOY modal:", JSON.stringify(hit.text)); break; } }
      if (i % 5 === 0) log(`...waiting for deploy result (${i}s) dialogs=${JSON.stringify(ds.map((d) => d.text.slice(0, 60)))}`);
    }
    log("DEPLOY RESULT TEXT:", JSON.stringify(result));
  }
  await shot("08-after-save");
  log("URL after save:", page.url());

  // Final ground truth.
  log("PIPELINE API calls:", JSON.stringify(pipeApi));
  log("final node count:", await countNodes());
  log("PIPE name:", PIPE);
} catch (e) {
  log("FATAL ERROR:", e.message, e.stack?.split("\n").slice(0, 3).join(" | "));
  await shot("ERROR");
} finally {
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 12)));
  log("page errors:", JSON.stringify(pageErrors.slice(0, 6)));
  await browser.close();
}
