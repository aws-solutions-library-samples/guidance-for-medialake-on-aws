import { describe, expect, it } from "vitest";
import { PROFILE_LOCALES, selectedProfileLocale } from "./profileLocales";

describe("selectedProfileLocale", () => {
  it("keeps a language that is one of the options", () => {
    expect(selectedProfileLocale("fr", "fr")).toBe("fr");
    expect(selectedProfileLocale("he")).toBe("he");
  });

  it("maps a detected regional browser language to its option", () => {
    expect(selectedProfileLocale("en-US", "en")).toBe("en");
    expect(selectedProfileLocale("pt-BR")).toBe("pt");
    expect(selectedProfileLocale("zh-Hans-CN")).toBe("zh");
  });

  it("falls back to English for an unsupported language", () => {
    expect(selectedProfileLocale("nl-NL", "en")).toBe("en");
    expect(selectedProfileLocale("sv")).toBe("en");
    expect(selectedProfileLocale(undefined)).toBe("en");
  });

  it("always returns one of the selector options", () => {
    const codes = PROFILE_LOCALES.map((l) => l.code);
    for (const lang of ["en-GB", "de-AT", "xx", "", "ar-SA", "ja-JP", "cimode"]) {
      expect(codes).toContain(selectedProfileLocale(lang));
    }
  });
});
