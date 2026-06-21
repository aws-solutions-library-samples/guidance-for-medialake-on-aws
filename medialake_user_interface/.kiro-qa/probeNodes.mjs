import { launch, BASE, SHOTS, dumpUI } from "./lib.mjs";

const { browser, page, consoleErrors } = await launch();
const log = (...a) => console.log("[nodes]", ...a);

const nodeApi = [];
page.on("response", async (res) => {
  const u = res.url();
  if (/\/nodes(\b|\/|\?)/.test(u) && res.request().method() === "GET") {
    let body = "";
    try { body = await res.text(); } catch {}
    nodeApi.push({ status: res.status(), url: u, body });
  }
});

try {
  await page.goto(`${BASE}/settings/pipelines/new`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 25000 }).catch(() => {});
  await page.waitForTimeout(4000);
  log("URL:", page.url());

  // Parse node catalog from captured API.
  for (const r of nodeApi) {
    log(`NODES API ${r.status} ${r.url}`);
    try {
      const j = JSON.parse(r.body);
      // Try common shapes
      const arr = j?.data?.nodes || j?.nodes || j?.data || (Array.isArray(j) ? j : []);
      const list = Array.isArray(arr) ? arr : [];
      const ids = list.map((n) => n.nodeId || n.id || n?.node?.id).filter(Boolean);
      const titles = list.map((n) => n.title || n?.info?.title || n?.node?.title || n?.name).filter(Boolean);
      log("node count:", list.length);
      log("node ids:", JSON.stringify(ids));
      log("node titles:", JSON.stringify(titles));
      log("HAS upload_batch_completed:", r.body.includes("upload_batch_completed") || r.body.includes("Upload Batch Completed"));
      log("HAS mark_upload_complete:", r.body.includes("mark_upload_complete") || r.body.includes("Mark Upload Processing Complete"));
    } catch (e) {
      log("parse error; raw snippet:", r.body.slice(0, 300));
      log("HAS upload_batch_completed:", r.body.includes("upload_batch_completed") || r.body.includes("Upload Batch Completed"));
      log("HAS mark_upload_complete:", r.body.includes("mark_upload_complete") || r.body.includes("Mark Upload Processing Complete"));
    }
  }
  if (nodeApi.length === 0) log("NO /nodes API call captured");

  // Dump the visible 'Available Nodes' sidebar text.
  const sidebarText = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll("aside, [class*='sidebar'], [class*='Sidebar'], [class*='panel'], [class*='Panel']"));
    return all.map((el) => (el.innerText || "").replace(/\s+/g, " ").trim()).filter((t) => t.length > 10 && t.length < 2000).slice(0, 5);
  });
  log("sidebar text candidates:", JSON.stringify(sidebarText));

  // Search the whole DOM for the two node labels.
  const labelHits = await page.evaluate(() => {
    const txt = document.body.innerText || "";
    return {
      uploadBatch: txt.includes("Upload Batch Completed"),
      markComplete: txt.includes("Mark Upload Processing Complete") || txt.includes("Mark Upload Complete"),
    };
  });
  log("DOM label hits:", JSON.stringify(labelHits));
  await page.screenshot({ path: `${SHOTS}/nodes-pipeline-editor.png`, fullPage: true }).catch(() => {});
} catch (e) {
  log("ERROR:", e.message);
  await page.screenshot({ path: `${SHOTS}/nodes-ERROR.png` }).catch(() => {});
} finally {
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 10)));
  await browser.close();
}
