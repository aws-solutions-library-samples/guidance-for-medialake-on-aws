import { chromium } from "@playwright/test";
import { BASE, SHOTS } from "./lib.mjs";

// STEP 6 — Responsive layout check of the public upload portal page at
// desktop / tablet / mobile breakpoints. Detects horizontal overflow
// (the classic responsive bug), off-canvas / clipped elements, and confirms
// the heading, form fields and primary CTA remain visible + reachable.
// Uses anonymous contexts (no auth storageState) to mirror a real visitor.

const SLUG = process.argv[2] || "qa-auto-1782076662";
const log = (...a) => console.log("[resp]", ...a);

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "tablet", width: 1024, height: 768, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
];

// Runs in the page: measures overflow + collects elements that spill past the
// right edge of the viewport (the things that produce a horizontal scrollbar).
function measure() {
  const de = document.documentElement;
  const iw = window.innerWidth;
  const ih = window.innerHeight;
  const docW = Math.max(de.scrollWidth, document.body ? document.body.scrollWidth : 0);
  const tol = 2; // sub-pixel tolerance
  const all = Array.from(document.querySelectorAll("body *"));
  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const offenders = [];
  for (const el of all) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    // Only flag elements that actually extend beyond the viewport's right edge
    // (or start left of it) AND are not themselves a scroll container clipping content.
    const s = getComputedStyle(el);
    const clips = s.overflowX === "hidden" || s.overflowX === "auto" || s.overflowX === "scroll";
    if (clips) continue;
    if (r.right > iw + tol || r.left < -tol) {
      offenders.push({
        sel:
          el.tagName.toLowerCase() +
          (el.id ? "#" + el.id : "") +
          (typeof el.className === "string" && el.className
            ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".")
            : ""),
        right: Math.round(r.right),
        left: Math.round(r.left),
        w: Math.round(r.width),
        text: (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 50),
      });
    }
  }
  // Keep the widest / furthest-spilling offenders, de-duped by selector.
  const seen = new Set();
  const top = offenders
    .sort((a, b) => b.right - a.right)
    .filter((o) => (seen.has(o.sel) ? false : (seen.add(o.sel), true)))
    .slice(0, 12);

  // Primary CTA reachability: find an enabled button matching common labels.
  const btns = Array.from(document.querySelectorAll("button,[role=button]")).filter(visible);
  const ctaRe = /next|continue|upload|submit|browse|select file|choose|start/i;
  const cta = btns.find((b) => ctaRe.test((b.innerText || b.getAttribute("aria-label") || "")));
  let ctaInfo = null;
  if (cta) {
    const r = cta.getBoundingClientRect();
    ctaInfo = {
      text: (cta.innerText || cta.getAttribute("aria-label") || "").trim().slice(0, 40),
      inViewportX: r.left >= -tol && r.right <= iw + tol,
      fullyVisibleY: r.top >= -tol && r.bottom <= ih + tol,
      clipped: r.right > iw + tol || r.left < -tol,
    };
  }
  return {
    iw,
    ih,
    docW: Math.round(docW),
    horizontalOverflow: docW > iw + tol,
    overflowPx: Math.round(docW - iw),
    offenders: top,
    visibleButtons: btns.length,
    cta: ctaInfo,
  };
}

async function clickNext(page) {
  // Try to advance the multi-page portal to the uploader page.
  const labels = ["Next", "Continue", "Upload", "Proceed"];
  for (const name of labels) {
    const btn = page.getByRole("button", { name: new RegExp(`^${name}`, "i") });
    if ((await btn.count()) && !(await btn.first().isDisabled().catch(() => true))) {
      await btn.first().click().catch(() => {});
      await page.waitForTimeout(1500);
      return name;
    }
  }
  return null;
}

const browser = await chromium.launch({ headless: true });
const summary = [];

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    isMobile: vp.isMobile,
    hasTouch: vp.isMobile,
    deviceScaleFactor: 1,
    locale: "en-US",
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  // Capture failed responses (4xx/5xx) with URL + type to identify the 404.
  const failed = [];
  page.on("response", (res) => {
    const s = res.status();
    if (s >= 400) failed.push({ status: s, type: res.request().resourceType(), url: res.url() });
  });

  try {
    await page.goto(`${BASE}/p/${SLUG}`, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
    // Wait for the SPA to actually hydrate page-1 content before measuring,
    // otherwise overflow/CTA metrics are taken against a blank shell.
    await page
      .waitForFunction(
        () => document.querySelectorAll("button,[role=button],input,textarea,select,h1,h2").length > 0,
        { timeout: 15000 }
      )
      .catch(() => {});
    await page.waitForTimeout(1500);

    const m1 = await page.evaluate(measure);
    log(`\n=== ${vp.name} (${vp.width}x${vp.height}) PAGE 1 ===`);
    log("metrics:", JSON.stringify({ ...m1, offenders: m1.offenders.length }));
    if (m1.horizontalOverflow) log("  OVERFLOW offenders:", JSON.stringify(m1.offenders));
    log("  CTA:", JSON.stringify(m1.cta));
    await page.screenshot({ path: `${SHOTS}/step6-${vp.name}-p1.png`, fullPage: true }).catch(() => {});

    const advanced = await clickNext(page);
    let m2 = null;
    if (advanced) {
      await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(1500);
      m2 = await page.evaluate(measure);
      log(`=== ${vp.name} PAGE 2 (via "${advanced}") ===`);
      log("metrics:", JSON.stringify({ ...m2, offenders: m2.offenders.length }));
      if (m2.horizontalOverflow) log("  OVERFLOW offenders:", JSON.stringify(m2.offenders));
      log("  CTA:", JSON.stringify(m2.cta));
      await page.screenshot({ path: `${SHOTS}/step6-${vp.name}-p2.png`, fullPage: true }).catch(() => {});
    } else {
      log(`=== ${vp.name} PAGE 2 : no advance button found ===`);
    }

    summary.push({
      vp: vp.name,
      dims: `${vp.width}x${vp.height}`,
      p1Overflow: m1.horizontalOverflow ? `${m1.overflowPx}px` : "none",
      p1CtaClipped: m1.cta ? m1.cta.clipped : "no-cta",
      p2Overflow: m2 ? (m2.horizontalOverflow ? `${m2.overflowPx}px` : "none") : "n/a",
      p2CtaClipped: m2 && m2.cta ? m2.cta.clipped : "n/a",
      consoleErrors: consoleErrors.length,
      pageErrors: pageErrors.length,
    });
    if (consoleErrors.length) log("  console errors:", JSON.stringify(consoleErrors.slice(0, 6)));
    if (pageErrors.length) log("  page errors:", JSON.stringify(pageErrors.slice(0, 4)));
    if (failed.length) log("  FAILED responses:", JSON.stringify(failed.slice(0, 10)));
  } catch (e) {
    log(`${vp.name} FATAL:`, e.message);
    summary.push({ vp: vp.name, dims: `${vp.width}x${vp.height}`, error: e.message });
  } finally {
    await ctx.close();
  }
}

log("\n===== STEP 6 SUMMARY =====");
for (const s of summary) log(JSON.stringify(s));
await browser.close();
