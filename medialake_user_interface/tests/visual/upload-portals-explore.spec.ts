/**
 * EXPLORATION spec — dumps the live DOM handles of the portal editor and the
 * pipeline/canvas node catalog so the lifecycle spec can be authored against
 * real selectors. Read the console output; screenshots saved for reference.
 *
 * Run:
 *   MEDIALAKE_TEST_EMAIL='kiro-qa@medialake.test' \
 *   MEDIALAKE_TEST_PASSWORD='KiroQA-Dev4-Visual2026' \
 *   AWS_PROFILE=ml-dev4 AWS_REGION=us-east-1 SKIP_ROLE_CHECK=true \
 *   PLAYWRIGHT_BASE_URL=https://d2gn8nwil93iye.cloudfront.net \
 *   npx playwright test tests/visual/upload-portals-explore.spec.ts \
 *     --config=playwright.visual.config.ts --project=chromium
 */
import { test, expect } from "../fixtures/static-auth.fixtures";
import type { Page } from "@playwright/test";

const OUT = "test-results/upload-portals-explore";
const ROOT = process.env.PLAYWRIGHT_BASE_URL ?? "https://d2gn8nwil93iye.cloudfront.net";

async function freeze(page: Page) {
  await page.addStyleTag({
    content:
      "*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important}",
  });
}

async function dump(page: Page, label: string) {
  const data = await page.evaluate(() => {
    const sel =
      'button,input,textarea,select,[role="button"],[role="combobox"],[role="checkbox"],[role="switch"],[role="radio"],[role="tab"],[role="menuitem"],a[href],[contenteditable="true"]';
    const els = Array.from(document.querySelectorAll(sel));
    return els
      .map((el) => {
        const r = el.getBoundingClientRect();
        return {
          tag: el.tagName.toLowerCase(),
          type: (el as HTMLInputElement).type || el.getAttribute("type") || undefined,
          role: el.getAttribute("role") || undefined,
          id: el.id || undefined,
          tid: el.getAttribute("data-testid") || undefined,
          name: el.getAttribute("name") || undefined,
          ph: el.getAttribute("placeholder") || undefined,
          aria: el.getAttribute("aria-label") || undefined,
          txt: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 45) || undefined,
          vis: r.width > 0 && r.height > 0,
        };
      })
      .filter((e) => e.vis);
  });
  console.log(`\n===DUMP=== ${label} (${data.length} visible interactive)`);
  for (const d of data) console.log("  " + JSON.stringify(d));
}

async function dumpHeadings(page: Page, label: string) {
  const data = await page.evaluate(() => {
    const els = Array.from(
      document.querySelectorAll(
        "h1,h2,h3,h4,h5,h6,label,legend,[class*='MuiAccordionSummary'],[class*='section-title']"
      )
    );
    return els
      .map((el) => (el.textContent || "").replace(/\s+/g, " ").trim())
      .filter((t) => t.length > 0 && t.length < 60);
  });
  console.log(`\n===HEAD=== ${label}`);
  console.log("  " + JSON.stringify([...new Set(data)].slice(0, 60)));
}

test("EXPLORE portal list", async ({ authenticatedPage: page }) => {
  await page.goto(`${ROOT}/settings/upload-portals`, { waitUntil: "domcontentloaded" });
  await freeze(page);
  await page.waitForTimeout(3500);
  // Dump table rows with their text
  const rows = await page.evaluate(() => {
    const trs = Array.from(document.querySelectorAll("tbody tr, [role='row']"));
    return trs.map((tr) => (tr.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160));
  });
  console.log(`\n===PORTAL-LIST ROWS=== (${rows.length})`);
  rows.forEach((r) => console.log("  " + r));
  await dump(page, "portal-list");
  await page.screenshot({ path: `${OUT}/list.png`, fullPage: true });
});

test("EXPLORE portal editor /new", async ({ authenticatedPage: page }) => {
  await page.goto(`${ROOT}/settings/upload-portals/new`, { waitUntil: "domcontentloaded" });
  await freeze(page);
  await page.waitForTimeout(3500);
  await dumpHeadings(page, "editor-new headings");
  await dump(page, "editor-new default");

  // Expand Structure group
  const structure = page.locator("#portal-editor-group-structure-header");
  if (await structure.count()) {
    await structure.first().click();
    await page.waitForTimeout(700);
  }
  // Expand each structure section and dump
  for (const sec of ["pages", "metadata", "destinations", "fields", "access"]) {
    const h = page.locator(`#portal-editor-section-${sec}-header`);
    if (await h.count()) {
      await h.first().click();
      await page.waitForTimeout(900);
      await dump(page, `editor section=${sec}`);
      await page.screenshot({ path: `${OUT}/editor-${sec}.png`, fullPage: true });
    } else {
      console.log(`\n===DUMP=== editor section=${sec} NOT FOUND`);
    }
  }
});

test("EXPLORE pipelines + canvas node catalog", async ({ authenticatedPage: page }) => {
  // Pipelines list
  await page.goto(`${ROOT}/pipelines`, { waitUntil: "domcontentloaded" });
  await freeze(page);
  await page.waitForTimeout(3500);
  console.log(`\n===URL after /pipelines=== ${page.url()}`);
  await dumpHeadings(page, "pipelines headings");
  await dump(page, "pipelines page");
  await page.screenshot({ path: `${OUT}/pipelines.png`, fullPage: true });

  // Try canvas (new pipeline builder)
  for (const route of ["/canvas", "/pipelines/new"]) {
    await page.goto(`${ROOT}${route}`, { waitUntil: "domcontentloaded" });
    await freeze(page);
    await page.waitForTimeout(4000);
    console.log(`\n===URL after ${route}=== ${page.url()}`);
    await dumpHeadings(page, `${route} headings`);
    await dump(page, `${route} page`);
    await page.screenshot({
      path: `${OUT}/canvas-${route.replace(/\W/g, "_")}.png`,
      fullPage: true,
    });

    // Search the whole DOM for the two target node titles
    const found = await page.evaluate(() => {
      const text = document.body.innerText || "";
      return {
        uploadBatchCompleted: /Upload Batch Completed/i.test(text),
        markUploadComplete: /Mark Upload Processing Complete/i.test(text),
        triggerWord: /trigger/i.test(text),
        nodeWord: /node|catalog|palette/i.test(text),
      };
    });
    console.log(`\n===NODE-SEARCH ${route}=== ${JSON.stringify(found)}`);
  }
});
