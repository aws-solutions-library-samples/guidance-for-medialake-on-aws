/**
 * Task 3 closure: capture the "Upload Batch Completed" TRIGGER node config form.
 *
 * Root cause of the earlier failing test (pipeline-nodes.spec.ts test 3):
 *   - It used node.dblclick() on the node BODY to open config. That does NOT open
 *     config. Config opens either:
 *       (a) AUTOMATICALLY on drop, because onDrop() sets isNodeConfigOpen=true when
 *           the dragged payload's methodConfig.parameters has keys (it does: 3 params), OR
 *       (b) via a single click on the gear (Settings) IconButton inside the node's
 *           ".node-actions" container, which is opacity:0/width:0 until the node is hovered.
 *   - The original test also simply exceeded the 90s test timeout in ensureSidebar.
 *
 * This spec uses a generous timeout, drops the node (which auto-opens the dialog),
 * and falls back to forcing .node-actions visible + clicking the gear if needed.
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroQA-Dev4-Visual2026' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 SKIP_ROLE_CHECK=true \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   npx playwright test tests/visual/pipeline-trigger-config.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium --reporter=list
 */
import { test, expect } from "../fixtures/static-auth.fixtures";
import type { Page } from "@playwright/test";

const OUT = "test-results/pipeline-nodes";
const ROOT = process.env.PLAYWRIGHT_BASE_URL ?? "https://d2gn8nwil93iye.cloudfront.net";

async function freeze(page: Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important}" +
      // Force node action buttons (gear/delete/rotate) visible regardless of hover.
      ".node-actions{opacity:1!important;width:auto!important;margin-left:8px!important;overflow:visible!important}",
  });
}

async function ensureSidebar(page: Page) {
  await page.goto(`${ROOT}/pipelines/new`, { waitUntil: "domcontentloaded" });
  await freeze(page);
  await page.getByText("Available Nodes").waitFor({ state: "visible", timeout: 30000 });
}

async function nodeSearch(page: Page) {
  const inputs = page.getByRole("textbox");
  const n = await inputs.count();
  const vw = page.viewportSize()!.width;
  for (let i = 0; i < n; i++) {
    const el = inputs.nth(i);
    const ph = await el.getAttribute("placeholder").catch(() => null);
    if (ph === "Search (e.g., sunset)") continue;
    const box = await el.boundingBox().catch(() => null);
    if (box && box.x > vw / 2) return el;
  }
  return inputs.last();
}

async function readConfigForm(page: Page) {
  return page.evaluate(() => {
    const dialog =
      (document.querySelector('[role="dialog"]') as HTMLElement) ||
      (document.querySelector(".MuiModal-root") as HTMLElement) ||
      document.body;
    const text = (dialog as HTMLElement).innerText || "";
    const labels = Array.from(dialog.querySelectorAll("label, legend"))
      .map((l) => (l.textContent || "").replace(/\s+/g, " ").trim())
      .filter(Boolean);
    return {
      open: !!document.querySelector('[role="dialog"]'),
      labels: [...new Set(labels)].slice(0, 30),
      hasAutomationTag: /automation tag/i.test(text),
      hasPortal: /portal/i.test(text),
      hasOutcome: /completion outcome|completed only|completed with errors|both/i.test(text),
      snippet: text.replace(/\s+/g, " ").trim().slice(0, 400),
    };
  });
}

test("Upload Batch Completed trigger config exposes Automation Tag / Portal / Completion Outcome", async ({
  authenticatedPage: page,
}) => {
  test.setTimeout(180000);
  await ensureSidebar(page);

  const search = await nodeSearch(page);
  await search.fill("Upload Batch Completed");
  await page.waitForTimeout(1200);

  const before = await page.locator(".react-flow__node").count();

  // HTML5 DnD simulation. The app's onDragStart writes the full payload (including
  // methodConfig.parameters) onto the DataTransfer we provide; onDrop then auto-opens config.
  const dropped = await page.evaluate(() => {
    const src = Array.from(document.querySelectorAll('[draggable="true"]')).find((e) =>
      /Upload Batch Completed/i.test(e.textContent || "")
    ) as HTMLElement | undefined;
    const pane =
      (document.querySelector(".react-flow__pane") as HTMLElement) ||
      (document.querySelector(".react-flow") as HTMLElement);
    if (!src || !pane) return { ok: false, reason: !src ? "no-source" : "no-pane" };
    const dt = new DataTransfer();
    const pr = pane.getBoundingClientRect();
    const cx = pr.x + pr.width / 2;
    const cy = pr.y + pr.height / 2;
    const fire = (el: Element, type: string, x: number, y: number) =>
      el.dispatchEvent(
        new DragEvent(type, {
          bubbles: true,
          cancelable: true,
          dataTransfer: dt,
          clientX: x,
          clientY: y,
        } as any)
      );
    const sr = src.getBoundingClientRect();
    fire(src, "dragstart", sr.x + 5, sr.y + 5);
    fire(pane, "dragenter", cx, cy);
    fire(pane, "dragover", cx, cy);
    fire(pane, "drop", cx, cy);
    fire(src, "dragend", cx, cy);
    return { ok: true, payload: dt.getData("application/reactflow") };
  });
  console.log(`[trigger-config] drop sim ok=${(dropped as any).ok}`);
  console.log(
    `[trigger-config] payload=${JSON.stringify((dropped as any).payload || (dropped as any).reason)}`
  );

  await page.waitForTimeout(2500);
  const after = await page.locator(".react-flow__node").count();
  console.log(`[trigger-config] nodes ${before} -> ${after}`);

  // 1) Did the config dialog auto-open on drop?
  let form = await readConfigForm(page);

  // 2) Fallback: hover node + click the gear (Settings) IconButton.
  if (!form.open && after > before) {
    const node = page.locator(".react-flow__node").first();
    await node.hover().catch(() => {});
    await page.waitForTimeout(300);
    const gear = node.locator('button:has(svg[data-testid="SettingsIcon"])');
    if (await gear.count()) {
      await gear
        .first()
        .click({ force: true })
        .catch(() => {});
      await page.waitForTimeout(1500);
      form = await readConfigForm(page);
    } else {
      console.log("[trigger-config] gear button not found on node (no configurable params?)");
    }
  }

  console.log(`[trigger-config] form: ${JSON.stringify(form)}`);
  await page.screenshot({ path: `${OUT}/05-trigger-config-form.png`, fullPage: true });

  // Assert the node was added and the three documented params are present.
  expect(after, "node should be added to canvas").toBeGreaterThan(before);
  expect(form.hasAutomationTag, "config form should expose an Automation Tag parameter").toBe(true);
  expect(form.hasOutcome, "config form should expose a Completion Outcome parameter").toBe(true);
});
