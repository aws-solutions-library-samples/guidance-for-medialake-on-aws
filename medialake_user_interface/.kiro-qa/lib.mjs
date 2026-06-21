import { chromium } from "@playwright/test";

export const BASE = "https://d2gn8nwil93iye.cloudfront.net";
export const STATE = "/tmp/kiro-qa/state.json";
export const SHOTS = "/tmp/kiro-qa/shots";

export async function launch({ viewport } = {}) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    storageState: STATE,
    viewport: viewport || { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/New_York",
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  return { browser, context, page, consoleErrors, pageErrors };
}

// Dump an interactable summary of the page: headings, buttons, links, tabs, inputs.
export async function dumpUI(page) {
  return await page.evaluate(() => {
    const txt = (el) => (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80);
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    const collect = (sel) =>
      Array.from(document.querySelectorAll(sel))
        .filter(visible)
        .map((el) => {
          const label =
            el.getAttribute("aria-label") ||
            el.getAttribute("placeholder") ||
            el.getAttribute("name") ||
            txt(el);
          return label;
        })
        .filter(Boolean);
    return {
      url: location.href,
      h: collect("h1,h2,h3,h4,h5,h6,[role=heading]").slice(0, 30),
      buttons: Array.from(new Set(collect("button,[role=button]"))).slice(0, 60),
      tabs: Array.from(new Set(collect('[role=tab]'))).slice(0, 20),
      links: Array.from(new Set(collect("nav a, aside a, a"))).slice(0, 40),
      inputs: Array.from(document.querySelectorAll("input,textarea,select"))
        .filter(visible)
        .map((el) => ({
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute("type"),
          name: el.getAttribute("name"),
          ph: el.getAttribute("placeholder"),
          label: el.getAttribute("aria-label"),
        }))
        .slice(0, 40),
    };
  });
}
