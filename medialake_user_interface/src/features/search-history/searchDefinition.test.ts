import { describe, expect, it } from "vitest";
import vectorFile from "./__fixtures__/fingerprint-vectors.json";
import {
  canonicalJson,
  definitionFromState,
  definitionToSearchParams,
  fingerprintDefinition,
  isBlankDefinition,
  normalizeDefinition,
  parseSemanticParams,
  resolveRelativeDates,
  searchUrlForDefinition,
  type SearchDefinition,
} from "./searchDefinition";

interface Vector {
  name: string;
  input: Partial<SearchDefinition>;
  canonical: string;
  fingerprint: string;
}

const vectors = (vectorFile as { vectors: Vector[] }).vectors;

describe("fingerprint contract shared with the API", () => {
  it.each(vectors.map((v) => [v.name, v] as const))("%s", async (_name, vector) => {
    const normalized = normalizeDefinition(vector.input);
    expect(canonicalJson(normalized)).toBe(vector.canonical);
    expect(await fingerprintDefinition(vector.input)).toBe(vector.fingerprint);
  });
});

describe("URL round trip", () => {
  it("carries semantic mode and search modes so the search is exact", () => {
    const params = definitionToSearchParams(
      normalizeDefinition({
        q: "dog",
        semantic: true,
        semanticMode: "full",
        searchModes: ["audio", "visual"],
        filters: {
          type: "Video",
          customMetadataFilters: [{ field: "a", operator: "term", value: "b" }],
        },
      })
    );
    expect(params.get("q")).toBe("dog");
    expect(params.get("semantic")).toBe("true");
    expect(params.get("semanticMode")).toBe("full");
    expect(params.get("modes")).toBe("audio,visual");
    expect(params.get("type")).toBe("Video");
    expect(JSON.parse(params.get("custom_md")!)).toEqual([
      { field: "a", operator: "term", value: "b" },
    ]);
    expect(parseSemanticParams(params)).toEqual({
      semanticMode: "full",
      searchModes: ["audio", "visual"],
    });
  });

  it("omits semantic params for keyword searches", () => {
    const params = definitionToSearchParams(normalizeDefinition({ q: "dog" }));
    expect(params.has("semanticMode")).toBe(false);
    expect(params.has("modes")).toBe(false);
  });

  it("ignores unknown or missing semantic params (old links keep working)", () => {
    expect(parseSemanticParams(new URLSearchParams("q=x&semantic=true"))).toEqual({
      semanticMode: undefined,
      searchModes: undefined,
    });
    expect(
      parseSemanticParams(new URLSearchParams("semanticMode=sideways&modes=smell,audio"))
    ).toEqual({ semanticMode: undefined, searchModes: ["audio"] });
  });
});

describe("relative date ranges", () => {
  it("are recomputed from now on replay", () => {
    const definition = normalizeDefinition({
      q: "news",
      filters: {
        date_range_option: "7d",
        ingested_date_gte: "2020-01-01T00:00:00.000Z",
        ingested_date_lte: "2020-01-08T00:00:00.000Z",
      },
    });
    // Stored without the stale absolute dates.
    expect(definition.filters).toEqual({ date_range_option: "7d" });

    const now = new Date("2026-09-24T12:00:00.000Z");
    const resolved = resolveRelativeDates(definition, now);
    expect(resolved.filters?.ingested_date_lte).toBe(now.toISOString());
    expect(resolved.filters?.ingested_date_gte).toBe("2026-09-17T12:00:00.000Z");
  });

  it("leave custom ranges untouched", () => {
    const definition = normalizeDefinition({
      q: "news",
      filters: { ingested_date_gte: "2026-01-01T00:00:00.000Z" },
    });
    expect(resolveRelativeDates(definition)).toBe(definition);
    expect(searchUrlForDefinition(definition)).toContain(
      "ingested_date_gte=2026-01-01T00%3A00%3A00.000Z"
    );
  });
});

describe("capturing the live search state", () => {
  it("drops semantic options for keyword searches", () => {
    expect(
      definitionFromState({
        query: " cat ",
        isSemantic: false,
        semanticMode: "clip",
        searchModes: ["visual"],
        filters: {},
      })
    ).toEqual({ v: 1, q: "cat", semantic: false });
  });

  it("treats browse-everything as blank", () => {
    expect(isBlankDefinition(normalizeDefinition({ q: "" }))).toBe(true);
    expect(isBlankDefinition(normalizeDefinition({ q: "*" }))).toBe(true);
    expect(isBlankDefinition(normalizeDefinition({ q: "", filters: { type: "Image" } }))).toBe(
      false
    );
  });
});
