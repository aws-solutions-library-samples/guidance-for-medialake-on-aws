import { describe, expect, it } from "vitest";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import type { PortalAppearance } from "../types/appearance.types";
import {
  colorStringSchema,
  HEX_COLOR_RE,
  portalAppearanceSchema,
  RGBA_COLOR_RE,
} from "./appearance.schema";

/**
 * Produce a mutable clone of the default appearance so each test can mutate
 * a single field without leaking state into the next case. The defaults are
 * deeply nested plain objects, so structured cloning is both correct and
 * terse here.
 */
const cloneDefault = (): PortalAppearance => structuredClone(DEFAULT_PORTAL_APPEARANCE);

describe("color regex constants", () => {
  it("HEX_COLOR_RE matches the documented hex shapes", () => {
    expect(HEX_COLOR_RE.test("#fff")).toBe(true);
    expect(HEX_COLOR_RE.test("#FFFFFF")).toBe(true);
    expect(HEX_COLOR_RE.test("#ffffff80")).toBe(true); // RRGGBBAA
    expect(HEX_COLOR_RE.test("fff")).toBe(false);
    expect(HEX_COLOR_RE.test("#ZZZ")).toBe(false);
  });

  it("RGBA_COLOR_RE matches rgb/rgba with optional alpha", () => {
    expect(RGBA_COLOR_RE.test("rgb(0, 0, 0)")).toBe(true);
    expect(RGBA_COLOR_RE.test("rgba(255, 128, 0, 0.5)")).toBe(true);
    expect(RGBA_COLOR_RE.test("rgba(0,0,0,1)")).toBe(true);
    expect(RGBA_COLOR_RE.test("rgba(0,0,0,.25)")).toBe(true);
    // Alpha > 1 is not representable by the alpha group, so it is rejected
    // regardless of the (unbounded) channel values.
    expect(RGBA_COLOR_RE.test("rgb(300,0,0,2)")).toBe(false);
    expect(RGBA_COLOR_RE.test("not-a-color")).toBe(false);
  });
});

describe("colorStringSchema", () => {
  it("accepts hex and rgba strings", () => {
    expect(colorStringSchema.safeParse("#123").success).toBe(true);
    expect(colorStringSchema.safeParse("#abcdef").success).toBe(true);
    expect(colorStringSchema.safeParse("#abcdef80").success).toBe(true);
    expect(colorStringSchema.safeParse("rgb(0, 0, 0)").success).toBe(true);
    expect(colorStringSchema.safeParse("rgba(0, 0, 0, 0.5)").success).toBe(true);
  });

  it("rejects strings that match neither pattern", () => {
    expect(colorStringSchema.safeParse("not-a-color").success).toBe(false);
    expect(colorStringSchema.safeParse("#ZZZ").success).toBe(false);
    expect(colorStringSchema.safeParse("").success).toBe(false);
  });
});

describe("portalAppearanceSchema", () => {
  describe("happy path", () => {
    it("accepts DEFAULT_PORTAL_APPEARANCE", () => {
      const result = portalAppearanceSchema.safeParse(DEFAULT_PORTAL_APPEARANCE);
      expect(result.success).toBe(true);
    });

    it("accepts rgba, #RGB, and #RRGGBBAA color variants", () => {
      const a = cloneDefault();
      a.colors.primary = "rgba(12, 34, 56, 0.8)";
      a.colors.background = "#fff";
      a.colors.cardBackground = "#abcdef80";
      expect(portalAppearanceSchema.safeParse(a).success).toBe(true);
    });

    it("accepts optional branding fields when omitted", () => {
      const a = cloneDefault();
      delete a.branding.bannerS3Key;
      delete a.branding.bannerUrl;
      delete a.branding.faviconS3Key;
      expect(portalAppearanceSchema.safeParse(a).success).toBe(true);
    });

    it("accepts optional branding fields when present", () => {
      const a = cloneDefault();
      a.branding.bannerS3Key = "portals/abc/banner.png";
      a.branding.bannerUrl = "https://example.com/banner.png";
      a.branding.faviconS3Key = "portals/abc/favicon.ico";
      expect(portalAppearanceSchema.safeParse(a).success).toBe(true);
    });
  });

  describe("color rejections", () => {
    it.each([
      ["not-a-color"],
      ["#ZZZ"],
      // Alpha value out of range — the rgba pattern only permits [0, 1].
      ["rgb(300,0,0,2)"],
    ])("rejects %s as colors.primary", (bad) => {
      const a = cloneDefault();
      a.colors.primary = bad;
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });
  });

  describe("numeric range rejections", () => {
    it.each<[keyof PortalAppearance["typography"], number]>([
      ["baseFontSize", 10],
      ["baseFontSize", 30],
    ])("rejects typography.%s = %s", (key, value) => {
      const a = cloneDefault();
      (a.typography[key] as number) = value;
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it.each<[keyof PortalAppearance["layout"], number]>([
      ["cardMaxWidth", 300],
      ["cardMaxWidth", 1500],
    ])("rejects layout.%s = %s", (key, value) => {
      const a = cloneDefault();
      (a.layout[key] as number) = value;
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it.each<[keyof PortalAppearance["branding"], number]>([
      ["bannerHeight", -1],
      ["bannerHeight", 500],
    ])("rejects branding.%s = %s", (key, value) => {
      const a = cloneDefault();
      (a.branding[key] as number) = value;
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });
  });

  describe("enum rejections", () => {
    it("rejects an invalid mode value", () => {
      const a = cloneDefault();
      // Intentional type-cheat: the schema is the runtime guard.
      (a.mode as unknown) = "neon";
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("rejects an invalid cardShadow value", () => {
      const a = cloneDefault();
      (a.layout.cardShadow as unknown) = "xl";
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });
  });

  describe("content length rejections", () => {
    it("rejects titleHtml longer than 5000 characters", () => {
      const a = cloneDefault();
      a.content.titleHtml = "x".repeat(5001);
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("rejects descriptionHtml longer than 10000 characters", () => {
      const a = cloneDefault();
      a.content.descriptionHtml = "x".repeat(10001);
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("rejects footerHtml longer than 2000 characters", () => {
      const a = cloneDefault();
      a.content.footerHtml = "x".repeat(2001);
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("rejects empty submitButtonText", () => {
      const a = cloneDefault();
      a.content.submitButtonText = "";
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("rejects submitButtonText longer than 50 characters", () => {
      const a = cloneDefault();
      a.content.submitButtonText = "x".repeat(51);
      expect(portalAppearanceSchema.safeParse(a).success).toBe(false);
    });

    it("accepts submitButtonText at the 50-character boundary", () => {
      const a = cloneDefault();
      a.content.submitButtonText = "x".repeat(50);
      expect(portalAppearanceSchema.safeParse(a).success).toBe(true);
    });
  });
});
