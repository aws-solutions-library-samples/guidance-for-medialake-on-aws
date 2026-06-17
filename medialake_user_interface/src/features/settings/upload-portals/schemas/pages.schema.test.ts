import { describe, expect, it } from "vitest";

import type { PortalPage } from "../../../portal/types/portal.types";
import {
  portalPageElementSchema,
  portalPageSchema,
  portalPagesSchema,
  portalPagesSchemaWithFieldKeys,
  validateMetadataFieldRefs,
} from "./pages.schema";

/**
 * A minimal, structurally-valid two-page portal:
 *   page 1 hosts a metadata field + destination selector
 *   page 2 hosts the (single) uploader
 * Field key "project_code" is referenced and is considered valid by the
 * field-key-aware helpers below.
 */
const validPages = (): PortalPage[] => [
  {
    pageNumber: 1,
    title: "Details",
    elements: [
      { kind: "metadata-field", fieldKey: "project_code" },
      { kind: "destination-selector" },
    ],
  },
  {
    pageNumber: 2,
    title: "Upload",
    elements: [{ kind: "uploader" }],
  },
];

const VALID_FIELD_KEYS = ["project_code", "region"];

describe("portalPageElementSchema", () => {
  it("accepts each element kind", () => {
    expect(
      portalPageElementSchema.safeParse({ kind: "metadata-field", fieldKey: "x" }).success
    ).toBe(true);
    expect(portalPageElementSchema.safeParse({ kind: "destination-selector" }).success).toBe(true);
    expect(portalPageElementSchema.safeParse({ kind: "path-browser" }).success).toBe(true);
    expect(portalPageElementSchema.safeParse({ kind: "path-builder" }).success).toBe(true);
    expect(portalPageElementSchema.safeParse({ kind: "uploader" }).success).toBe(true);
  });

  it("rejects an unknown kind", () => {
    expect(portalPageElementSchema.safeParse({ kind: "mystery" }).success).toBe(false);
  });

  it("rejects a metadata-field element with an empty fieldKey", () => {
    expect(
      portalPageElementSchema.safeParse({ kind: "metadata-field", fieldKey: "" }).success
    ).toBe(false);
  });

  it("rejects a metadata-field element missing fieldKey", () => {
    expect(portalPageElementSchema.safeParse({ kind: "metadata-field" }).success).toBe(false);
  });
});

describe("portalPageSchema", () => {
  it("accepts a minimal valid page", () => {
    const page: PortalPage = { pageNumber: 1, title: "Page", elements: [] };
    expect(portalPageSchema.safeParse(page).success).toBe(true);
  });

  it("accepts optional descriptionHtml and visibleIf", () => {
    const page: PortalPage = {
      pageNumber: 1,
      title: "Page",
      descriptionHtml: "<p>hi</p>",
      visibleIf: "{x} notempty",
      elements: [],
    };
    expect(portalPageSchema.safeParse(page).success).toBe(true);
  });

  it("rejects a non-positive pageNumber", () => {
    expect(portalPageSchema.safeParse({ pageNumber: 0, title: "P", elements: [] }).success).toBe(
      false
    );
  });

  it("rejects a non-integer pageNumber", () => {
    expect(portalPageSchema.safeParse({ pageNumber: 1.5, title: "P", elements: [] }).success).toBe(
      false
    );
  });

  it("rejects an empty title", () => {
    expect(portalPageSchema.safeParse({ pageNumber: 1, title: "", elements: [] }).success).toBe(
      false
    );
  });

  it("rejects a title over the max length", () => {
    expect(
      portalPageSchema.safeParse({ pageNumber: 1, title: "x".repeat(121), elements: [] }).success
    ).toBe(false);
  });
});

describe("portalPagesSchema (self-contained invariants)", () => {
  it("accepts a structurally valid pages array", () => {
    expect(portalPagesSchema.safeParse(validPages()).success).toBe(true);
  });

  describe("contiguous page numbers from 1", () => {
    it("rejects page numbers with a gap", () => {
      const pages = validPages();
      pages[1].pageNumber = 3; // 1, 3 -> gap
      const result = portalPagesSchema.safeParse(pages);
      expect(result.success).toBe(false);
      expect(result.error?.issues.some((i) => i.message.includes("contiguous"))).toBe(true);
    });

    it("rejects page numbers not starting at 1", () => {
      const pages = validPages();
      pages[0].pageNumber = 2;
      pages[1].pageNumber = 3; // 2, 3
      expect(portalPagesSchema.safeParse(pages).success).toBe(false);
    });

    it("rejects duplicate page numbers", () => {
      const pages = validPages();
      pages[1].pageNumber = 1; // 1, 1
      expect(portalPagesSchema.safeParse(pages).success).toBe(false);
    });

    it("accepts pages provided out of order as long as the set is 1..N", () => {
      const pages = [validPages()[1], validPages()[0]]; // [pageNumber 2, pageNumber 1]
      expect(portalPagesSchema.safeParse(pages).success).toBe(true);
    });
  });

  describe("exactly one uploader element", () => {
    it("rejects zero uploader elements", () => {
      const pages = validPages();
      pages[1].elements = [{ kind: "path-browser" }]; // remove the uploader
      const result = portalPagesSchema.safeParse(pages);
      expect(result.success).toBe(false);
      expect(result.error?.issues.some((i) => i.message.includes("uploader"))).toBe(true);
    });

    it("rejects two uploader elements", () => {
      const pages = validPages();
      pages[0].elements.push({ kind: "uploader" }); // now two uploaders total
      const result = portalPagesSchema.safeParse(pages);
      expect(result.success).toBe(false);
      expect(result.error?.issues.some((i) => i.message.includes("found 2"))).toBe(true);
    });
  });

  it("does NOT validate metadata-field references (needs field keys)", () => {
    const pages = validPages();
    pages[0].elements[0] = { kind: "metadata-field", fieldKey: "does_not_exist" };
    // portalPagesSchema cannot see field keys, so this still passes here.
    expect(portalPagesSchema.safeParse(pages).success).toBe(true);
  });
});

describe("portalPagesSchemaWithFieldKeys (all three invariants)", () => {
  it("accepts valid pages whose metadata-field references resolve", () => {
    const schema = portalPagesSchemaWithFieldKeys(VALID_FIELD_KEYS);
    expect(schema.safeParse(validPages()).success).toBe(true);
  });

  it("rejects a metadata-field element referencing an unknown key", () => {
    const pages = validPages();
    pages[0].elements[0] = { kind: "metadata-field", fieldKey: "ghost_field" };
    const schema = portalPagesSchemaWithFieldKeys(VALID_FIELD_KEYS);
    const result = schema.safeParse(pages);
    expect(result.success).toBe(false);
    expect(result.error?.issues.some((i) => i.message.includes("ghost_field"))).toBe(true);
  });

  it("still enforces contiguity and single-uploader alongside field refs", () => {
    const pages = validPages();
    pages[1].pageNumber = 5; // break contiguity
    const schema = portalPagesSchemaWithFieldKeys(VALID_FIELD_KEYS);
    const result = schema.safeParse(pages);
    expect(result.success).toBe(false);
    expect(result.error?.issues.some((i) => i.message.includes("contiguous"))).toBe(true);
  });

  it("accepts a Set of field keys", () => {
    const schema = portalPagesSchemaWithFieldKeys(new Set(VALID_FIELD_KEYS));
    expect(schema.safeParse(validPages()).success).toBe(true);
  });
});

describe("validateMetadataFieldRefs", () => {
  it("returns an empty list when all references resolve", () => {
    expect(validateMetadataFieldRefs(validPages(), VALID_FIELD_KEYS)).toEqual([]);
  });

  it("returns the dangling keys when references do not resolve", () => {
    const pages = validPages();
    pages[0].elements[0] = { kind: "metadata-field", fieldKey: "ghost_field" };
    expect(validateMetadataFieldRefs(pages, VALID_FIELD_KEYS)).toEqual(["ghost_field"]);
  });
});
