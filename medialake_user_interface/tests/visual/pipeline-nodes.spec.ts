/**
 * Pipeline node catalog validation for the Upload Session Completion feature.
 * Confirms the two new nodes are present in the DEPLOYED node catalog UI:
 *   - TRIGGER: "Upload Batch Completed"
 *   - UTILITY: "Mark Upload Processing Complete"
 * Then best-effort adds the trigger to the canvas and opens its config to
 * verify parameters (Automation Tag / Portal / Completion Outcome).
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroQA-Dev4-Visual2026' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 SKIP_ROLE_CHECK=true \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   npx playwright test tests/visual/pipeline-nodes.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium --reporter=list
 */
import { test, expect } from "../fixtures/static-auth.fixtures";
import type { Page } from "@playwright/test";

const OUT = "test-results/pipeline-nodes";
const ROOT = process.env.PLAYWRIGHT_BASE_URL ?? "https://d2gn8nwil93iye.cloudfront.net";

async function freeze(page: Page) {
  await page.addStyleTag({
    content: "*,*::before,*::after{transition:none!important;animation:none!important}",
  });
}

// Ensure the right "Available Nodes" sidebar is expanded.
async function ensureSidebar(page: Page) {
  await page.goto(`${ROOT}/pipelines/new`, { waitUntil: "domcontentloaded" });
  await freeze(page);
  await page.waitForTimeout(2500);
  // Wait for the nodes API to populate (CircularProgress -> content)
  for (let i = 0; i < 4; i++) {
    if (
      await page
        .getByText("Available Nodes")
        .isVisible()
        .catch(() => false)
    )
      break;
    // Try clicking the chevron toggle (fixed button on the right edge)
    const chevL = page.locator('button:has([data-testid="ChevronLeftIcon"])');
    if (await chevL.count()) {
      await chevL
        .first()
        .click()
        .catch(() => {});
    }
    await page.waitForTimeout(2000);
  }
  await page.getByText("Available Nodes").waitFor({ state: "visible", timeout: 20000 });
}

// Find the node-search box inside the sidebar (right half of viewport, not the global search).
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
  // fallback: last textbox
  return inputs.last();
}

async function dumpNodeTitles(page: Page, label: string) {
  const titles = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('[draggable="true"]'))
      .map((el) =>
        (el.querySelector("h6, .MuiTypography-subtitle1")?.textContent || el.textContent || "")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 60)
      )
      .filter(Boolean);
  });
  console.log(`\n===NODE TITLES (${label})=== ${JSON.stringify(titles)}`);
}

test("TRIGGER catalog contains 'Upload Batch Completed'", async ({ authenticatedPage: page }) => {
  await ensureSidebar(page);
  await page.waitForTimeout(1500);
  await dumpNodeTitles(page, "default (TRIGGER expanded)");
  // Use node search to be section-independent
  const search = await nodeSearch(page);
  await search.fill("Upload Batch Completed");
  await page.waitForTimeout(1500);
  const card = page.getByText("Upload Batch Completed", { exact: true });
  const visible = await card
    .first()
    .isVisible()
    .catch(() => false);
  console.log(`[nodes] 'Upload Batch Completed' visible after search: ${visible}`);
  await page.screenshot({ path: `${OUT}/01-trigger-upload-batch-completed.png`, fullPage: true });
  expect(visible, "Upload Batch Completed trigger should appear in the catalog").toBe(true);
});

test("UTILITY catalog contains 'Mark Upload Processing Complete'", async ({
  authenticatedPage: page,
}) => {
  await ensureSidebar(page);
  const search = await nodeSearch(page);
  await search.fill("Mark Upload Processing Complete");
  await page.waitForTimeout(1500);
  await dumpNodeTitles(page, "search=Mark Upload");
  const card = page.getByText("Mark Upload Processing Complete", { exact: true });
  const visible = await card
    .first()
    .isVisible()
    .catch(() => false);
  console.log(`[nodes] 'Mark Upload Processing Complete' visible after search: ${visible}`);
  // capture its description text too
  const desc = await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll('[draggable="true"]')).find((e) =>
      /Mark Upload Processing Complete/i.test(e.textContent || "")
    );
    return el ? (el.textContent || "").replace(/\s+/g, " ").trim() : null;
  });
  console.log(`[nodes] Mark Upload card text: ${desc}`);
  await page.screenshot({ path: `${OUT}/02-utility-mark-upload-complete.png`, fullPage: true });
  expect(visible, "Mark Upload Processing Complete utility should appear in the catalog").toBe(
    true
  );
});

test("add trigger to canvas + open config (best effort)", async ({ authenticatedPage: page }) => {
  await ensureSidebar(page);
  const search = await nodeSearch(page);
  await search.fill("Upload Batch Completed");
  await page.waitForTimeout(1500);

  const before = await page.locator(".react-flow__node").count();
  console.log(`[nodes] react-flow nodes before drop: ${before}`);

  // HTML5 drag-drop simulation carrying the application/reactflow dataTransfer.
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
    return { ok: true, data: dt.getData("application/reactflow")?.slice(0, 80) };
  });
  console.log(`[nodes] drop sim: ${JSON.stringify(dropped)}`);
  await page.waitForTimeout(2000);
  const after = await page.locator(".react-flow__node").count();
  console.log(`[nodes] react-flow nodes after drop: ${after}`);
  await page.screenshot({ path: `${OUT}/03-canvas-after-drop.png`, fullPage: true });

  if (after > before) {
    // Try to open config: double-click the node, or click a Configure/gear control.
    const node = page.locator(".react-flow__node").first();
    await node.dblclick().catch(() => {});
    await page.waitForTimeout(1500);
    // dump dialog/form fields
    const fields = await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]') || document.body;
      const labels = Array.from(dialog.querySelectorAll("label, [id*='label'], legend"))
        .map((l) => (l.textContent || "").replace(/\s+/g, " ").trim())
        .filter(Boolean);
      const text = (dialog as HTMLElement).innerText || "";
      return {
        labels: [...new Set(labels)].slice(0, 30),
        hasAutomationTag: /automation tag/i.test(text),
        hasPortal: /portal/i.test(text),
        hasOutcome: /completion outcome|completed only|completed with errors|both/i.test(text),
      };
    });
    console.log(`[nodes] config form: ${JSON.stringify(fields)}`);
    await page.screenshot({ path: `${OUT}/04-trigger-config.png`, fullPage: true });
  } else {
    console.log(
      "[nodes] Drag-drop did not add a node (headless DnD limitation). Catalog presence still verified above."
    );
  }
});
