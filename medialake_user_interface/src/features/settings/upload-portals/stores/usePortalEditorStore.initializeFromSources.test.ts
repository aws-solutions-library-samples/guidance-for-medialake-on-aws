import { beforeEach, describe, expect, it } from "vitest";

import type {
  PortalDestination,
  PortalMetadataField,
  PortalPage,
  PortalTemplate,
  PortalTheme,
} from "@/api/types/api.types";

import { DEFAULT_PORTAL_APPEARANCE } from "../constants/appearanceDefaults";
import type { PortalAppearance } from "../types/appearance.types";
import { usePortalEditorStore } from "./usePortalEditorStore";

/**
 * Unit tests for the create-from-template/theme actions added in task 17.2:
 *   - `initializeFromSources({ template?, theme? })`
 *   - `applyTheme(theme)`
 *   - `buildThemePayload(name, description?)`
 *   - `buildTemplatePayload(name, description?, themeId?)`
 *
 * Validates: Requirements 16.5, 16.7, 16.9, 17.4, 17.5, 17.7
 *
 * Covers:
 *   - Appearance resolution order: default -> template inline -> selected
 *     theme, with later sources overriding earlier ones (Req 17.5).
 *   - Dangling `themeId` fallback to the template's inline appearance when the
 *     referenced theme isn't supplied (Req 16.9).
 *   - `applyTheme` replaces ONLY appearance and leaves structure untouched
 *     (Req 16.7).
 *   - Snapshot independence (Property 11 / Req 17.4): mutating the store after
 *     `initializeFromSources` does NOT change the source template/theme, and
 *     mutating the source objects afterward does NOT change the store.
 *   - "Save as Theme" serializer = appearance only; "Save as Template"
 *     serializer = full structure with NO passphrase (Req 17.7).
 */

// ---- Test data builders ----------------------------------------------------

/** A distinctive partial appearance used to prove which source "won". */
const themeColorPrimary = "#aa0000";
const templateColorPrimary = "#00bb00";
const templateColorAccent = "#0000cc";

const makeTheme = (
  themeId: string,
  primary: string,
  extra?: Partial<PortalAppearance>
): PortalTheme => ({
  themeId,
  name: `Theme ${themeId}`,
  appearance: {
    colors: { primary },
    ...extra,
  } as unknown as PortalAppearance,
});

const samplePages: PortalPage[] = [
  {
    pageNumber: 1,
    title: "Details",
    elements: [{ kind: "metadata-field", fieldKey: "project_name" }, { kind: "uploader" }],
  },
];

const sampleMetadataFields: PortalMetadataField[] = [
  { label: "Project Name", type: "text", required: true, order: 1, pageNumber: 1 },
];

const sampleDestinations: PortalDestination[] = [
  {
    destinationId: "dest-1",
    friendlyName: "Main bucket",
    connectorId: "connector-abc",
    rootPath: "/incoming",
    allowBrowsing: true,
    allowFolderCreation: false,
    order: 1,
    pageNumber: 1,
  },
];

const makeTemplate = (overrides?: Partial<PortalTemplate>): PortalTemplate => ({
  templateId: "tpl-1",
  name: "Sample template",
  pages: structuredClone(samplePages),
  metadataFields: structuredClone(sampleMetadataFields),
  destinations: structuredClone(sampleDestinations),
  appearance: {
    colors: { primary: templateColorPrimary, accent: templateColorAccent },
  } as unknown as PortalAppearance,
  accessMode: "token-protected",
  allowedGroups: ["admins"],
  ipAllowlist: ["10.0.0.0/8"],
  tokenBypassesPassphrase: true,
  structuredPathMode: true,
  captchaEnabled: true,
  maxFileSizeBytes: 1024,
  maxFilesPerSession: 5,
  ...overrides,
});

describe("usePortalEditorStore.initializeFromSources", () => {
  beforeEach(() => {
    usePortalEditorStore.getState().reset();
  });

  describe("appearance resolution order (Req 17.5)", () => {
    it("with no sources, seeds the default appearance and empty structure", () => {
      usePortalEditorStore.getState().initializeFromSources({});

      const state = usePortalEditorStore.getState();
      expect(state.appearance).toEqual(DEFAULT_PORTAL_APPEARANCE);
      expect(state.portalData).toEqual({});
      expect(state.isInitialized).toBe(true);
      expect(state.isDirty).toBe(false);
    });

    it("layers the template's inline appearance over the default", () => {
      usePortalEditorStore.getState().initializeFromSources({ template: makeTemplate() });

      const { appearance } = usePortalEditorStore.getState();
      // Template overrides win.
      expect(appearance.colors.primary).toBe(templateColorPrimary);
      expect(appearance.colors.accent).toBe(templateColorAccent);
      // Unspecified colors fall back to the default baseline.
      expect(appearance.colors.background).toBe(DEFAULT_PORTAL_APPEARANCE.colors.background);
      // Sibling slices remain at defaults.
      expect(appearance.typography).toEqual(DEFAULT_PORTAL_APPEARANCE.typography);
    });

    it("an explicitly selected theme overrides the template's appearance", () => {
      // template sets primary; selected theme also sets primary -> theme wins.
      const template = makeTemplate();
      const theme = makeTheme("theme-x", themeColorPrimary);

      usePortalEditorStore.getState().initializeFromSources({ template, theme });

      const { appearance } = usePortalEditorStore.getState();
      // Selected theme wins on the overlapping key.
      expect(appearance.colors.primary).toBe(themeColorPrimary);
      // The template's non-overlapping key still shows through (theme didn't
      // set accent), proving layering is a deep-merge, not a wholesale swap.
      expect(appearance.colors.accent).toBe(templateColorAccent);
    });

    it("when the template references the supplied theme, uses the theme's appearance", () => {
      // Template carries an inline appearance AND a themeId pointing at the
      // supplied theme. Per resolution, the referenced theme's appearance is
      // used as the template's contribution (not the inline one).
      const theme = makeTheme("theme-ref", themeColorPrimary);
      const template = makeTemplate({ themeId: "theme-ref" });

      usePortalEditorStore.getState().initializeFromSources({ template, theme });

      const { appearance } = usePortalEditorStore.getState();
      // Both the template-contribution layer and the selected-theme layer are
      // the same theme here, so primary is the theme color.
      expect(appearance.colors.primary).toBe(themeColorPrimary);
      // The template's inline `accent` was bypassed in favor of the referenced
      // theme (which has no accent) -> accent falls back to default.
      expect(appearance.colors.accent).toBe(DEFAULT_PORTAL_APPEARANCE.colors.accent);
    });

    it("a theme alone seeds appearance but leaves structure at the default", () => {
      const theme = makeTheme("theme-only", themeColorPrimary);

      usePortalEditorStore.getState().initializeFromSources({ theme });

      const state = usePortalEditorStore.getState();
      expect(state.appearance.colors.primary).toBe(themeColorPrimary);
      // No template -> empty structure.
      expect(state.portalData?.pages).toBeUndefined();
      expect(state.portalData?.destinations).toBeUndefined();
      // themeId recorded informationally.
      expect(state.portalData?.themeId).toBe("theme-only");
    });
  });

  describe("dangling themeId fallback (Req 16.9)", () => {
    it("ignores a dangling themeId and uses the template's inline appearance", () => {
      // Template references a theme that is NOT supplied.
      const template = makeTemplate({ themeId: "missing-theme" });

      usePortalEditorStore.getState().initializeFromSources({ template });

      const { appearance, portalData } = usePortalEditorStore.getState();
      // Falls back to the template's INLINE appearance.
      expect(appearance.colors.primary).toBe(templateColorPrimary);
      expect(appearance.colors.accent).toBe(templateColorAccent);
      // No resolved theme -> themeId is NOT recorded as applied.
      expect(portalData?.themeId).toBeUndefined();
    });

    it("uses the inline appearance when a DIFFERENT theme is supplied than referenced", () => {
      // Template references theme-A (not supplied); a standalone theme-B is.
      const template = makeTemplate({ themeId: "theme-A" });
      const theme = makeTheme("theme-B", themeColorPrimary);

      usePortalEditorStore.getState().initializeFromSources({ template, theme });

      const { appearance, portalData } = usePortalEditorStore.getState();
      // template contribution = inline (themeId dangling) -> primary green,
      // then selected theme-B overrides primary -> red.
      expect(appearance.colors.primary).toBe(themeColorPrimary);
      // Inline accent survives (theme-B didn't set it).
      expect(appearance.colors.accent).toBe(templateColorAccent);
      // The applied theme is the explicitly selected one.
      expect(portalData?.themeId).toBe("theme-B");
    });
  });

  describe("structure seeding from template (Req 17.4)", () => {
    it("seeds pages, fields, destinations, access settings, and limits", () => {
      const template = makeTemplate();

      usePortalEditorStore.getState().initializeFromSources({ template });

      const { portalData } = usePortalEditorStore.getState();
      expect(portalData?.pages).toEqual(samplePages);
      expect(portalData?.metadataFields).toEqual(sampleMetadataFields);
      expect(portalData?.destinations).toEqual(sampleDestinations);
      // Destinations keep connectorId + pageNumber verbatim.
      expect((portalData?.destinations as PortalDestination[])[0].connectorId).toBe(
        "connector-abc"
      );
      expect((portalData?.destinations as PortalDestination[])[0].pageNumber).toBe(1);
      // Access settings + limits.
      expect(portalData?.accessMode).toBe("token-protected");
      expect(portalData?.allowedGroups).toEqual(["admins"]);
      expect(portalData?.ipAllowlist).toEqual(["10.0.0.0/8"]);
      expect(portalData?.tokenBypassesPassphrase).toBe(true);
      expect(portalData?.structuredPathMode).toBe(true);
      expect(portalData?.captchaEnabled).toBe(true);
      expect(portalData?.maxFileSizeBytes).toBe(1024);
      expect(portalData?.maxFilesPerSession).toBe(5);
    });
  });

  describe("snapshot independence (Property 11 / Req 17.4)", () => {
    it("mutating the store after seeding does NOT change the source template", () => {
      const template = makeTemplate();
      const templateSnapshot = structuredClone(template);

      usePortalEditorStore.getState().initializeFromSources({ template });

      // Mutate the store's structure via the store actions.
      usePortalEditorStore.getState().updatePortalData({
        destinations: [
          ...(usePortalEditorStore.getState().portalData?.destinations as PortalDestination[]),
          {
            destinationId: "dest-2",
            friendlyName: "Added",
            connectorId: "x",
            rootPath: "/",
            allowBrowsing: false,
            allowFolderCreation: false,
            order: 2,
          },
        ],
      });
      usePortalEditorStore.getState().updateColor("primary", "#ffffff");

      // The source template object is byte-for-byte unchanged.
      expect(template).toEqual(templateSnapshot);
    });

    it("mutating the source template after seeding does NOT change the store", () => {
      const template = makeTemplate();

      usePortalEditorStore.getState().initializeFromSources({ template });
      const storeDestinationsBefore = structuredClone(
        usePortalEditorStore.getState().portalData?.destinations
      );

      // Mutate the source AFTER seeding.
      (template.destinations as PortalDestination[])[0].connectorId = "MUTATED";
      (template.pages as PortalPage[])[0].title = "MUTATED";
      template.appearance = { colors: { primary: "#999999" } } as unknown as PortalAppearance;

      const state = usePortalEditorStore.getState();
      expect(state.portalData?.destinations).toEqual(storeDestinationsBefore);
      expect((state.portalData?.pages as PortalPage[])[0].title).toBe("Details");
      // Appearance is unaffected by the post-seed source mutation.
      expect(state.appearance.colors.primary).toBe(templateColorPrimary);
    });

    it("mutating the source theme after seeding does NOT change the store", () => {
      const theme = makeTheme("theme-snap", themeColorPrimary);

      usePortalEditorStore.getState().initializeFromSources({ theme });
      expect(usePortalEditorStore.getState().appearance.colors.primary).toBe(themeColorPrimary);

      // Mutate the source theme appearance.
      (theme.appearance as PortalAppearance).colors.primary = "#123123";

      expect(usePortalEditorStore.getState().appearance.colors.primary).toBe(themeColorPrimary);
    });
  });
});

describe("usePortalEditorStore.applyTheme", () => {
  beforeEach(() => {
    usePortalEditorStore.getState().reset();
  });

  it("replaces ONLY appearance and leaves structure untouched (Req 16.7)", () => {
    // Seed an existing portal with structure first.
    usePortalEditorStore.getState().initialize({
      name: "Existing portal",
      slug: "existing",
      pages: structuredClone(samplePages),
      metadataFields: structuredClone(sampleMetadataFields),
      destinations: structuredClone(sampleDestinations),
    });

    const structureBefore = structuredClone(usePortalEditorStore.getState().portalData);

    const theme = makeTheme("theme-apply", themeColorPrimary);
    usePortalEditorStore.getState().applyTheme(theme);

    const state = usePortalEditorStore.getState();
    // Appearance replaced from the theme (merged onto defaults).
    expect(state.appearance.colors.primary).toBe(themeColorPrimary);
    expect(state.appearance.colors.background).toBe(DEFAULT_PORTAL_APPEARANCE.colors.background);

    // Structure is unchanged (aside from the informational themeId).
    expect(state.portalData?.pages).toEqual(structureBefore?.pages);
    expect(state.portalData?.metadataFields).toEqual(structureBefore?.metadataFields);
    expect(state.portalData?.destinations).toEqual(structureBefore?.destinations);
    expect(state.portalData?.name).toBe("Existing portal");
    expect(state.portalData?.slug).toBe("existing");

    // themeId recorded informationally; store marked dirty.
    expect(state.portalData?.themeId).toBe("theme-apply");
    expect(state.isDirty).toBe(true);
  });

  it("stays independent of the source theme (Property 11)", () => {
    usePortalEditorStore.getState().initialize({ name: "P", slug: "p" });
    const theme = makeTheme("theme-indep", themeColorPrimary);

    usePortalEditorStore.getState().applyTheme(theme);
    (theme.appearance as PortalAppearance).colors.primary = "#000000";

    expect(usePortalEditorStore.getState().appearance.colors.primary).toBe(themeColorPrimary);
  });
});

describe("usePortalEditorStore save-as serializers", () => {
  beforeEach(() => {
    usePortalEditorStore.getState().reset();
  });

  describe("buildThemePayload (Save as Theme — appearance only)", () => {
    it("returns name + appearance only, with NO structure", () => {
      usePortalEditorStore.getState().initialize({
        name: "Portal",
        slug: "portal",
        pages: structuredClone(samplePages),
        destinations: structuredClone(sampleDestinations),
        appearance: { colors: { primary: "#abcdef" } } as unknown as PortalAppearance,
      });

      const payload = usePortalEditorStore.getState().buildThemePayload("My Theme", "desc");

      expect(payload.name).toBe("My Theme");
      expect(payload.description).toBe("desc");
      expect(payload.appearance?.colors.primary).toBe("#abcdef");
      // No structure keys leak into a theme payload.
      expect(payload).not.toHaveProperty("pages");
      expect(payload).not.toHaveProperty("destinations");
      expect(payload).not.toHaveProperty("metadataFields");
    });

    it("omits description when not supplied", () => {
      usePortalEditorStore.getState().initialize({ name: "P", slug: "p" });
      const payload = usePortalEditorStore.getState().buildThemePayload("Theme");
      expect(payload).not.toHaveProperty("description");
    });

    it("returns an appearance independent of the live store (Property 11)", () => {
      usePortalEditorStore.getState().initialize({ name: "P", slug: "p" });
      const payload = usePortalEditorStore.getState().buildThemePayload("Theme");

      // Mutate the store after building -> payload is unaffected.
      usePortalEditorStore.getState().updateColor("primary", "#000000");

      expect(payload.appearance?.colors.primary).toBe(DEFAULT_PORTAL_APPEARANCE.colors.primary);
    });
  });

  describe("buildTemplatePayload (Save as Template — full structure, no passphrase)", () => {
    it("returns the full structure snapshot with optional themeId", () => {
      usePortalEditorStore.getState().initialize({
        name: "Portal",
        slug: "portal",
        pages: structuredClone(samplePages),
        metadataFields: structuredClone(sampleMetadataFields),
        destinations: structuredClone(sampleDestinations),
        accessMode: "cognito-groups",
        allowedGroups: ["g1"],
        ipAllowlist: ["1.2.3.4"],
        tokenBypassesPassphrase: true,
        structuredPathMode: false,
        captchaEnabled: true,
        maxFileSizeBytes: 2048,
        maxFilesPerSession: 3,
      });

      const payload = usePortalEditorStore
        .getState()
        .buildTemplatePayload("My Template", "tdesc", "theme-bundled");

      expect(payload.name).toBe("My Template");
      expect(payload.description).toBe("tdesc");
      expect(payload.themeId).toBe("theme-bundled");
      expect(payload.pages).toEqual(samplePages);
      expect(payload.metadataFields).toEqual(sampleMetadataFields);
      expect(payload.destinations).toEqual(sampleDestinations);
      // Destinations keep connectorId + pageNumber.
      expect(payload.destinations[0].connectorId).toBe("connector-abc");
      expect(payload.destinations[0].pageNumber).toBe(1);
      expect(payload.appearance).toBeDefined();
      // Access settings + limits round-trip.
      expect(payload.accessMode).toBe("cognito-groups");
      expect(payload.allowedGroups).toEqual(["g1"]);
      expect(payload.ipAllowlist).toEqual(["1.2.3.4"]);
      expect(payload.tokenBypassesPassphrase).toBe(true);
      expect(payload.structuredPathMode).toBe(false);
      expect(payload.captchaEnabled).toBe(true);
      expect(payload.maxFileSizeBytes).toBe(2048);
      expect(payload.maxFilesPerSession).toBe(3);
    });

    it("NEVER includes a passphrase even when one is present in portalData (Req 17.7)", () => {
      usePortalEditorStore.getState().initialize({
        name: "Portal",
        slug: "portal",
        pages: structuredClone(samplePages),
        destinations: structuredClone(sampleDestinations),
        passphrase: "super-secret",
      } as never);

      const payload = usePortalEditorStore.getState().buildTemplatePayload("T");

      expect(payload).not.toHaveProperty("passphrase");
      // Sanity: ensure no nested value carries the secret.
      expect(JSON.stringify(payload)).not.toContain("super-secret");
    });

    it("omits optional fields and themeId when not supplied / absent", () => {
      usePortalEditorStore.getState().initialize({ name: "P", slug: "p" });

      const payload = usePortalEditorStore.getState().buildTemplatePayload("T");

      expect(payload).not.toHaveProperty("description");
      expect(payload).not.toHaveProperty("themeId");
      expect(payload).not.toHaveProperty("accessMode");
      expect(payload).not.toHaveProperty("allowedGroups");
      // Required arrays default to empty.
      expect(payload.pages).toEqual([]);
      expect(payload.destinations).toEqual([]);
      expect(payload.metadataFields).toEqual([]);
    });

    it("returns structure independent of the live store (Property 11)", () => {
      usePortalEditorStore.getState().initialize({
        name: "P",
        slug: "p",
        pages: structuredClone(samplePages),
      });

      const payload = usePortalEditorStore.getState().buildTemplatePayload("T");

      // Mutate the store's pages after building -> payload is unaffected.
      usePortalEditorStore.getState().updatePage(1, { title: "Changed" });

      expect(payload.pages[0].title).toBe("Details");
    });
  });
});
