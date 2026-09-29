import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The detector runs once, when the module initialises i18next, so each test
// re-imports a fresh copy after seeding localStorage / the browser language.
const loadI18n = async () => {
  vi.resetModules();
  return (await import("./i18n")).default;
};

describe("i18n language detection", () => {
  beforeEach(() => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue("en-US");
    vi.spyOn(window.navigator, "languages", "get").mockReturnValue(["en-US"]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.removeItem("i18nextLng");
  });

  it("restores the language saved in localStorage on startup", async () => {
    localStorage.setItem("i18nextLng", "de");

    const i18n = await loadI18n();

    expect(i18n.language).toBe("de");
    expect(localStorage.getItem("i18nextLng")).toBe("de");
  });

  it("falls back to the browser language when nothing is saved", async () => {
    const i18n = await loadI18n();

    expect(i18n.language).toBe("en-US");
  });
});
