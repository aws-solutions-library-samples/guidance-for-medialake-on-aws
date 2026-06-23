import { describe, expect, it } from "vitest";

import type {
  PortalConfig,
  PortalPage,
  PortalPageElement,
} from "@/features/portal/types/portal.types";

import { buildSurveyJson } from "./portalSurveyModel";
import { PORTAL_QUESTION_TYPES } from "./registerPortalQuestions";

/**
 * Build a structurally-valid multi-page {@link PortalConfig} fixture.
 *
 * Two metadata fields are defined whose slugs ("project_code", "region") match
 * the `fieldKey`s referenced by the page elements, so the metadata-field
 * elements resolve to real questions. Pages are intentionally provided OUT OF
 * ORDER (page 2 before page 1) so tests can assert `buildSurveyJson` sorts by
 * ascending `pageNumber`.
 */
const buildConfig = (overrides: Partial<PortalConfig> = {}): PortalConfig => ({
  slug: "demo",
  name: "Demo Portal",
  accessMode: "public",
  tokenBypassesPassphrase: false,
  isActive: true,
  structuredPathMode: false,
  captchaEnabled: false,
  metadataFields: [
    { label: "Project code", type: "text", required: true, order: 0, pageNumber: 1 },
    {
      label: "Region",
      type: "select",
      required: false,
      order: 1,
      options: ["NA", "EU"],
      pageNumber: 1,
    },
  ],
  destinations: [
    {
      destinationId: "dest-1",
      friendlyName: "Bucket A",
      allowBrowsing: true,
      allowFolderCreation: false,
      order: 0,
      pageNumber: 1,
    },
    {
      destinationId: "dest-2",
      friendlyName: "Bucket B",
      allowBrowsing: true,
      allowFolderCreation: false,
      order: 1,
      pageNumber: 1,
    },
  ],
  pages: [
    // page 2 is listed first on purpose (out of order)
    {
      pageNumber: 2,
      title: "Upload",
      elements: [{ kind: "uploader" }],
    },
    {
      pageNumber: 1,
      title: "Details",
      elements: [
        { kind: "destination-selector" },
        { kind: "metadata-field", fieldKey: "project_code" },
        { kind: "metadata-field", fieldKey: "region" },
        { kind: "path-builder" },
      ],
    },
  ],
  ...overrides,
});

describe("buildSurveyJson — purity / determinism (Property 8, Req 5.1, 6.3)", () => {
  it("produces deep-equal output for the same input invoked twice", () => {
    const config = buildConfig();
    expect(buildSurveyJson(config)).toEqual(buildSurveyJson(config));
  });

  it("produces deep-equal output across two independently-built equal configs", () => {
    expect(buildSurveyJson(buildConfig())).toEqual(buildSurveyJson(buildConfig()));
  });

  it("does not mutate the input config", () => {
    const config = buildConfig();
    const before = structuredClone(config);
    buildSurveyJson(config);
    expect(config).toEqual(before);
  });

  it("does not share array references with the input config (choices are copied)", () => {
    const config = buildConfig();
    const selectField = config.metadataFields.find((f) => f.type === "select");
    const result = buildSurveyJson(config);
    const dropdown = result.pages.flatMap((p) => p.elements).find((q) => q.type === "dropdown");
    expect(dropdown?.choices).toEqual(["NA", "EU"]);
    // Mutating the output choices must not bleed back into the source config.
    dropdown?.choices?.push("APAC");
    expect(selectField?.options).toEqual(["NA", "EU"]);
  });
});

describe("buildSurveyJson — ordering (Req 5.2, 5.3)", () => {
  it("orders pages by ascending pageNumber even when supplied out of order", () => {
    const result = buildSurveyJson(buildConfig());
    expect(result.pages.map((p) => p.name)).toEqual(["page-1", "page-2"]);
  });

  it("preserves element order within a page exactly", () => {
    const result = buildSurveyJson(buildConfig());
    const page1 = result.pages.find((p) => p.name === "page-1");
    expect(page1?.elements.map((q) => q.name)).toEqual([
      "__destPicker",
      "project_code",
      "region",
      "__pathBuilder",
    ]);
  });

  it("maps element kinds to their question types in order", () => {
    const result = buildSurveyJson(buildConfig());
    const page1 = result.pages.find((p) => p.name === "page-1");
    expect(page1?.elements.map((q) => q.type)).toEqual([
      PORTAL_QUESTION_TYPES.destinationSelector,
      "text",
      "dropdown",
      PORTAL_QUESTION_TYPES.pathBuilder,
    ]);
  });
});

describe("buildSurveyJson — metadata field type mapping", () => {
  it("maps select/radiogroup/checkbox/tagbox to choice questions with choices, and boolean", () => {
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Fields",
        elements: [
          { kind: "metadata-field", fieldKey: "dropdown_field" },
          { kind: "metadata-field", fieldKey: "radio_field" },
          { kind: "metadata-field", fieldKey: "checkbox_field" },
          { kind: "metadata-field", fieldKey: "tags_field" },
          { kind: "metadata-field", fieldKey: "agree_field" },
          { kind: "uploader" },
        ],
      },
    ];
    const config = buildConfig({
      metadataFields: [
        {
          label: "Dropdown Field",
          type: "select",
          required: false,
          order: 0,
          options: ["a", "b"],
          pageNumber: 1,
        },
        {
          label: "Radio Field",
          type: "radiogroup",
          required: false,
          order: 1,
          options: ["x", "y"],
          pageNumber: 1,
        },
        {
          label: "Checkbox Field",
          type: "checkbox",
          required: false,
          order: 2,
          options: ["c", "d"],
          pageNumber: 1,
        },
        {
          label: "Tags Field",
          type: "tagbox",
          required: true,
          order: 3,
          options: ["t1", "t2"],
          pageNumber: 1,
        },
        { label: "Agree Field", type: "boolean", required: true, order: 4, pageNumber: 1 },
      ],
      pages,
    });

    const byName = new Map(buildSurveyJson(config).pages[0].elements.map((q) => [q.name, q]));

    // select → dropdown, carries choices.
    expect(byName.get("dropdown_field")?.type).toBe("dropdown");
    expect(byName.get("dropdown_field")?.choices).toEqual(["a", "b"]);
    // radiogroup → radiogroup, carries choices.
    expect(byName.get("radio_field")?.type).toBe("radiogroup");
    expect(byName.get("radio_field")?.choices).toEqual(["x", "y"]);
    // checkbox → checkbox, carries choices.
    expect(byName.get("checkbox_field")?.type).toBe("checkbox");
    expect(byName.get("checkbox_field")?.choices).toEqual(["c", "d"]);
    // tagbox → free-entry tags: allowCustomChoices, required flag, and any
    // admin options surface as suggestions.
    expect(byName.get("tags_field")?.type).toBe("tagbox");
    expect(byName.get("tags_field")?.allowCustomChoices).toBe(true);
    expect(byName.get("tags_field")?.choices).toEqual(["t1", "t2"]);
    expect(byName.get("tags_field")?.isRequired).toBe(true);
    // boolean → boolean, NO choices.
    expect(byName.get("agree_field")?.type).toBe("boolean");
    expect(byName.get("agree_field")?.choices).toBeUndefined();
    expect(byName.get("agree_field")?.isRequired).toBe(true);
  });

  it("emits a free-entry tagbox (allowCustomChoices, no choices) when no options are configured", () => {
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Fields",
        elements: [{ kind: "metadata-field", fieldKey: "tags" }, { kind: "uploader" }],
      },
    ];
    const config = buildConfig({
      // No `options` — a pure free-entry tag field (type + Enter to add).
      metadataFields: [{ label: "Tags", type: "tagbox", required: false, order: 0, pageNumber: 1 }],
      pages,
    });

    const tags = buildSurveyJson(config).pages[0].elements.find((q) => q.name === "tags");
    expect(tags?.type).toBe("tagbox");
    expect(tags?.allowCustomChoices).toBe(true);
    // No predefined pick-list when the admin configured no options.
    expect(tags?.choices).toBeUndefined();
  });
});

describe("buildSurveyJson — built-in question titles", () => {
  it("gives every built-in question a friendly title (never the reserved name)", () => {
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Setup",
        elements: [
          { kind: "destination-selector" },
          { kind: "path-browser" },
          { kind: "path-builder" },
          { kind: "uploader" },
        ],
      },
    ];
    const result = buildSurveyJson(buildConfig({ pages }));
    const byType = new Map(result.pages[0].elements.map((q) => [q.type, q]));

    const destSelector = byType.get(PORTAL_QUESTION_TYPES.destinationSelector);
    const pathBrowser = byType.get(PORTAL_QUESTION_TYPES.pathBrowser);
    const pathBuilder = byType.get(PORTAL_QUESTION_TYPES.pathBuilder);
    const uploader = byType.get(PORTAL_QUESTION_TYPES.uploader);

    expect(destSelector?.title).toBe("Destination");
    expect(pathBrowser?.title).toBe("Upload location");
    expect(pathBuilder?.title).toBe("Upload path");
    expect(uploader?.title).toBe("Upload files");

    // No built-in question surfaces its reserved double-underscore name as a title.
    for (const q of result.pages[0].elements) {
      expect(q.title).toBeTruthy();
      expect(q.title).not.toMatch(/^__/);
    }
  });
});

describe("buildSurveyJson — destination-selector visibility (single vs multiple destinations)", () => {
  const pagesWithSelector: PortalPage[] = [
    {
      pageNumber: 1,
      title: "Choose",
      elements: [{ kind: "destination-selector" }, { kind: "uploader" }],
    },
  ];

  it("omits the destination-selector when the page offers only one destination", () => {
    const config = buildConfig({
      pages: pagesWithSelector,
      destinations: [
        {
          destinationId: "only",
          friendlyName: "Only Bucket",
          allowBrowsing: false,
          allowFolderCreation: false,
          order: 0,
          pageNumber: 1,
        },
      ],
    });
    const page1 = buildSurveyJson(config).pages.find((p) => p.name === "page-1");
    const types = page1?.elements.map((q) => q.type) ?? [];
    expect(types).not.toContain(PORTAL_QUESTION_TYPES.destinationSelector);
    // The uploader still renders — only the useless selector is dropped.
    expect(types).toContain(PORTAL_QUESTION_TYPES.uploader);
  });

  it("omits the destination-selector when there are no destinations", () => {
    const config = buildConfig({ pages: pagesWithSelector, destinations: [] });
    const page1 = buildSurveyJson(config).pages.find((p) => p.name === "page-1");
    const types = page1?.elements.map((q) => q.type) ?? [];
    expect(types).not.toContain(PORTAL_QUESTION_TYPES.destinationSelector);
  });

  it("emits the destination-selector when the page offers more than one destination", () => {
    const config = buildConfig({
      pages: pagesWithSelector,
      destinations: [
        {
          destinationId: "a",
          friendlyName: "Bucket A",
          allowBrowsing: false,
          allowFolderCreation: false,
          order: 0,
          pageNumber: 1,
        },
        {
          destinationId: "b",
          friendlyName: "Bucket B",
          allowBrowsing: false,
          allowFolderCreation: false,
          order: 1,
          pageNumber: 1,
        },
      ],
    });
    const page1 = buildSurveyJson(config).pages.find((p) => p.name === "page-1");
    const types = page1?.elements.map((q) => q.type) ?? [];
    expect(types).toContain(PORTAL_QUESTION_TYPES.destinationSelector);
  });

  it("counts only destinations assigned to the selector's page (multi-page)", () => {
    // Two destinations total, but only ONE on page 1 → selector omitted on
    // page 1 even though the portal has multiple destinations overall.
    const config = buildConfig({
      pages: [
        {
          pageNumber: 1,
          title: "Choose",
          elements: [{ kind: "destination-selector" }],
        },
        { pageNumber: 2, title: "Upload", elements: [{ kind: "uploader" }] },
      ],
      destinations: [
        {
          destinationId: "p1",
          friendlyName: "Page 1 Bucket",
          allowBrowsing: false,
          allowFolderCreation: false,
          order: 0,
          pageNumber: 1,
        },
        {
          destinationId: "p2",
          friendlyName: "Page 2 Bucket",
          allowBrowsing: false,
          allowFolderCreation: false,
          order: 1,
          pageNumber: 2,
        },
      ],
    });
    const page1 = buildSurveyJson(config).pages.find((p) => p.name === "page-1");
    const types = page1?.elements.map((q) => q.type) ?? [];
    expect(types).not.toContain(PORTAL_QUESTION_TYPES.destinationSelector);
  });
});

describe("buildSurveyJson — visibleIf / enableIf passthrough (Req 5.4)", () => {
  it("emits a page-level visibleIf character-for-character", () => {
    const visibleIf = "{region} = 'EU' and {__selectedDestinationId} notempty";
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Conditional",
        visibleIf,
        elements: [{ kind: "uploader" }],
      },
    ];
    const result = buildSurveyJson(buildConfig({ pages }));
    expect(result.pages[0].visibleIf).toBe(visibleIf);
  });

  it("emits element-level visibleIf and enableIf character-for-character", () => {
    const visibleIf = "{project_code} = 'ABC-123'";
    const enableIf = "{region} anyof ['NA', 'EU']";
    // visibleIf/enableIf are read off the element at runtime; the cast mirrors
    // how an authored element carries these optional expressions.
    const conditionalElement = {
      kind: "path-builder",
      visibleIf,
      enableIf,
    } as PortalPageElement;
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Conditional element",
        elements: [conditionalElement, { kind: "uploader" }],
      },
    ];
    const result = buildSurveyJson(buildConfig({ pages }));
    const pathBuilder = result.pages[0].elements.find(
      (q) => q.type === PORTAL_QUESTION_TYPES.pathBuilder
    );
    expect(pathBuilder?.visibleIf).toBe(visibleIf);
    expect(pathBuilder?.enableIf).toBe(enableIf);
  });

  it("lets an authored visibleIf override a built-in default", () => {
    const visibleIf = "{custom} = 1";
    const browserElement = { kind: "path-browser", visibleIf } as PortalPageElement;
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Override",
        elements: [browserElement, { kind: "uploader" }],
      },
    ];
    const result = buildSurveyJson(buildConfig({ pages }));
    const browser = result.pages[0].elements.find(
      (q) => q.type === PORTAL_QUESTION_TYPES.pathBrowser
    );
    // The default ("{__selectedDestinationId} notempty") is replaced verbatim.
    expect(browser?.visibleIf).toBe(visibleIf);
  });
});

// ---------------------------------------------------------------------------
// collection-picker role (portal-metadata-automation-design.md, Layer A/D)
// ---------------------------------------------------------------------------

describe("buildSurveyJson — collection-picker role", () => {
  it("renders a multi-select tagbox with {value,text} choices from allowedCollections", () => {
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Pick",
        elements: [{ kind: "metadata-field", fieldKey: "add_to_collection" }, { kind: "uploader" }],
      },
    ];
    const config = buildConfig({
      metadataFields: [
        {
          label: "Add to collection",
          type: "tagbox",
          required: true,
          order: 0,
          pageNumber: 1,
          role: "collection-picker",
          roleConfig: {
            multiple: true,
            allowedCollections: [
              { id: "col_mk26", name: "Marketing 2026" },
              { id: "col_raw", name: "Raw Footage" },
            ],
          },
        },
      ],
      pages,
    });

    const q = buildSurveyJson(config).pages[0].elements.find((e) => e.name === "add_to_collection");
    expect(q?.type).toBe("tagbox");
    expect(q?.isRequired).toBe(true);
    expect(q?.choices).toEqual([
      { value: "col_mk26", text: "Marketing 2026" },
      { value: "col_raw", text: "Raw Footage" },
    ]);
  });

  it("renders a single-select dropdown when multiple is false", () => {
    const pages: PortalPage[] = [
      {
        pageNumber: 1,
        title: "Pick",
        elements: [{ kind: "metadata-field", fieldKey: "collection" }, { kind: "uploader" }],
      },
    ];
    const config = buildConfig({
      metadataFields: [
        {
          label: "Collection",
          type: "tagbox",
          required: false,
          order: 0,
          pageNumber: 1,
          role: "collection-picker",
          roleConfig: {
            multiple: false,
            allowedCollections: [{ id: "col_a", name: "Alpha" }],
          },
        },
      ],
      pages,
    });

    const q = buildSurveyJson(config).pages[0].elements.find((e) => e.name === "collection");
    expect(q?.type).toBe("dropdown");
    expect(q?.choices).toEqual([{ value: "col_a", text: "Alpha" }]);
  });
});
