import { chromium } from "@playwright/test";

const BASE = "https://d2gn8nwil93iye.cloudfront.net";
const EMAIL = "kiro-qa@medialake.test";
const PASSWORD = "KiroQa#Test2026";
const SHOTS = "/tmp/kiro-qa/shots";
const STATE = "/tmp/kiro-qa/state.json";

const log = (...a) => console.log("[auth]", ...a);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
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

try {
  await page.goto(`${BASE}/sign-in`, { waitUntil: "domcontentloaded" });
  await page.getByRole("textbox", { name: "Email" }).waitFor({ state: "visible", timeout: 20000 });
  log("sign-in form visible");
  await page.screenshot({ path: `${SHOTS}/auth-01-signin.png` });

  await page.getByRole("textbox", { name: "Email" }).fill(EMAIL);
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  log("clicked Sign in, waiting for redirect...");

  await page.waitForFunction(() => !window.location.pathname.includes("sign-in"), {
    timeout: 35000,
  });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2500);

  const url = page.url();
  log("post-login URL:", url);
  await page.screenshot({ path: `${SHOTS}/auth-02-dashboard.png`, fullPage: false });

  // Confirm authenticated shell by listing visible nav landmarks
  const navTexts = await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll('nav a, [role="navigation"] a, aside a'))
      .map((a) => a.textContent?.trim())
      .filter(Boolean);
    return Array.from(new Set(items)).slice(0, 40);
  });
  log("nav items:", JSON.stringify(navTexts));

  // Page title / any visible error
  const bodyHasSignInError = await page.getByText(/Incorrect username or password/i).count();
  log("incorrect-credentials error present:", bodyHasSignInError);

  await context.storageState({ path: STATE });
  log("saved storageState ->", STATE);

  log("console errors:", consoleErrors.length, JSON.stringify(consoleErrors.slice(0, 10)));

  if (url.includes("sign-in")) {
    log("RESULT: FAIL — still on sign-in");
    process.exitCode = 2;
  } else {
    log("RESULT: PASS — authenticated, reached", url);
  }
} catch (e) {
  log("ERROR:", e.message);
  await page.screenshot({ path: `${SHOTS}/auth-ERROR.png` }).catch(() => {});
  log("console errors:", JSON.stringify(consoleErrors.slice(0, 10)));
  process.exitCode = 3;
} finally {
  await browser.close();
}
