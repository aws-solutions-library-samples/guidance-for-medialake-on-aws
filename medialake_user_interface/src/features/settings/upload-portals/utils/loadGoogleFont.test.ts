import { beforeEach, describe, expect, it } from "vitest";
import {
  GOOGLE_FONT_LINK_ID_PREFIX,
  buildGoogleFontHref,
  isSystemFontStack,
  loadGoogleFont,
} from "./loadGoogleFont";

function clearFontLinks(): void {
  const existing = document.head.querySelectorAll(`link[id^="${GOOGLE_FONT_LINK_ID_PREFIX}"]`);
  existing.forEach((el) => el.parentNode?.removeChild(el));
}

function getFontLinks(): HTMLLinkElement[] {
  return Array.from(
    document.head.querySelectorAll<HTMLLinkElement>(`link[id^="${GOOGLE_FONT_LINK_ID_PREFIX}"]`)
  );
}

describe("isSystemFontStack", () => {
  it("treats 'System Default' as a system stack", () => {
    expect(isSystemFontStack("System Default")).toBe(true);
  });

  it("treats empty string as a system stack", () => {
    expect(isSystemFontStack("")).toBe(true);
  });

  it("treats -apple-system prefixed families as a system stack", () => {
    expect(isSystemFontStack("-apple-system")).toBe(true);
    expect(isSystemFontStack("-apple-system, BlinkMacSystemFont")).toBe(true);
  });

  it("treats null/undefined inputs as a system stack", () => {
    expect(isSystemFontStack(null)).toBe(true);
    expect(isSystemFontStack(undefined)).toBe(true);
  });

  it("returns false for curated Google Font families", () => {
    expect(isSystemFontStack("Inter")).toBe(false);
    expect(isSystemFontStack("Plus Jakarta Sans")).toBe(false);
    expect(isSystemFontStack("JetBrains Mono")).toBe(false);
  });
});

describe("buildGoogleFontHref", () => {
  it("builds the correct URL for a single-word family", () => {
    expect(buildGoogleFontHref("Inter")).toBe(
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
    );
  });

  it("encodes spaces as '+' for multi-word families", () => {
    expect(buildGoogleFontHref("Plus Jakarta Sans")).toBe(
      "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap"
    );
  });

  it("correctly encodes JetBrains Mono", () => {
    expect(buildGoogleFontHref("JetBrains Mono")).toBe(
      "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800;900&display=swap"
    );
  });

  it("always requests the 400-900 weight range with display=swap", () => {
    const href = buildGoogleFontHref("Roboto");
    expect(href).toContain(":wght@400;500;600;700;800;900");
    expect(href).toContain("&display=swap");
  });
});

describe("loadGoogleFont", () => {
  beforeEach(() => {
    clearFontLinks();
  });

  it("is a no-op for 'System Default'", () => {
    loadGoogleFont("System Default");
    expect(getFontLinks()).toHaveLength(0);
  });

  it("is a no-op for an empty string", () => {
    loadGoogleFont("");
    expect(getFontLinks()).toHaveLength(0);
  });

  it("is a no-op for an -apple-system stack", () => {
    loadGoogleFont("-apple-system, BlinkMacSystemFont");
    expect(getFontLinks()).toHaveLength(0);
  });

  it("appends exactly one <link> for a single-word family", () => {
    loadGoogleFont("Inter");

    const links = getFontLinks();
    expect(links).toHaveLength(1);

    const [link] = links;
    expect(link.id).toBe("google-font-inter");
    expect(link.rel).toBe("stylesheet");
    expect(link.href).toBe(
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
    );
  });

  it("slugifies multi-word families and uses '+' encoding in the href", () => {
    loadGoogleFont("Plus Jakarta Sans");

    const links = getFontLinks();
    expect(links).toHaveLength(1);

    const [link] = links;
    expect(link.id).toBe("google-font-plus-jakarta-sans");
    expect(link.href).toContain("family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900");
  });

  it("is idempotent — 5 calls for the same family yield a single link", () => {
    for (let i = 0; i < 5; i += 1) {
      loadGoogleFont("Inter");
    }

    const links = getFontLinks();
    expect(links).toHaveLength(1);
    expect(links[0].id).toBe("google-font-inter");
  });

  it("tracks different families with distinct link elements", () => {
    loadGoogleFont("Inter");
    loadGoogleFont("Roboto");

    const links = getFontLinks();
    expect(links).toHaveLength(2);

    const ids = links.map((l) => l.id).sort();
    expect(ids).toEqual(["google-font-inter", "google-font-roboto"]);

    const interLink = links.find((l) => l.id === "google-font-inter")!;
    const robotoLink = links.find((l) => l.id === "google-font-roboto")!;
    expect(interLink.href).toContain("family=Inter:");
    expect(robotoLink.href).toContain("family=Roboto:");
  });

  it("does not duplicate when the same family is requested after a different family", () => {
    loadGoogleFont("Inter");
    loadGoogleFont("Roboto");
    loadGoogleFont("Inter");

    const links = getFontLinks();
    expect(links).toHaveLength(2);
  });
});
