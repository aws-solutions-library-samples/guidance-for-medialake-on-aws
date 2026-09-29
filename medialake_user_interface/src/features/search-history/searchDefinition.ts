/**
 * A search definition is everything needed to reproduce a search exactly: the
 * query text, semantic flags and every filter. Search history and saved
 * searches store it, and it round-trips through the /search URL.
 *
 * Normalization and fingerprinting mirror
 * `lambdas/api/users/search_definition.py`; both are tested against
 * `__fixtures__/fingerprint-vectors.json` so the browser and the API always
 * agree on "the same search".
 */
import { subDays } from "date-fns";
import { appendFiltersToUrlParams } from "@/stores/searchStore";
import type { CustomMetadataApiFilter, FacetFilters } from "@/types/facetSearch";

export const SEARCH_DEFINITION_VERSION = 1;

export type SemanticMode = "full" | "clip";
export type SearchModality = "visual" | "audio" | "transcript";

export const SEMANTIC_MODES: readonly SemanticMode[] = ["full", "clip"];
export const SEARCH_MODALITIES: readonly SearchModality[] = ["visual", "audio", "transcript"];
export const RELATIVE_DATE_RANGES = ["24h", "7d", "14d", "30d"] as const;

/** URL parameter names for the semantic options (alongside `q`, `semantic` and filters). */
export const SEMANTIC_MODE_PARAM = "semanticMode";
export const SEARCH_MODES_PARAM = "modes";

export interface SearchDefinition {
  v: number;
  q: string;
  semantic: boolean;
  semanticMode?: SemanticMode;
  searchModes?: SearchModality[];
  filters?: FacetFilters;
}

/** The live search state a definition is captured from. */
export interface SearchStateSnapshot {
  query: string;
  isSemantic: boolean;
  semanticMode: SemanticMode;
  searchModes: SearchModality[];
  filters: FacetFilters;
}

const RELATIVE_DAYS: Record<string, number> = { "24h": 1, "7d": 7, "14d": 14, "30d": 30 };

const isRelativeRange = (value?: string) =>
  !!value && (RELATIVE_DATE_RANGES as readonly string[]).includes(value);

const normalizeList = (value: string | undefined, upper: boolean): string | undefined => {
  if (!value) return undefined;
  const parts = new Set(
    value
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => (upper ? part.toUpperCase() : part))
  );
  // Python's sorted() on str compares code points; so does this for BMP text.
  const joined = [...parts].sort(compareCodePoints).join(",");
  return joined || undefined;
};

function compareCodePoints(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** JSON with recursively sorted keys and no whitespace, matching Python's canonical form. */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, v]) => v !== undefined)
    .sort(([a], [b]) => compareCodePoints(a, b));
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${canonicalJson(v)}`).join(",")}}`;
}

function normalizeCustomMetadata(
  filters: CustomMetadataApiFilter[] | undefined
): CustomMetadataApiFilter[] | undefined {
  if (!filters?.length) return undefined;
  const normalized = filters.map((entry) => {
    const item: CustomMetadataApiFilter = { field: entry.field.trim(), operator: entry.operator };
    if (entry.gte !== undefined && entry.gte !== null && entry.gte !== "") item.gte = entry.gte;
    if (entry.lte !== undefined && entry.lte !== null && entry.lte !== "") item.lte = entry.lte;
    if (entry.value !== undefined && entry.value !== null && entry.value !== "")
      item.value = entry.value;
    if (entry.type) item.type = entry.type;
    return item;
  });
  return normalized.sort((a, b) => compareCodePoints(canonicalJson(a), canonicalJson(b)));
}

function normalizeFilters(filters: FacetFilters | undefined): FacetFilters | undefined {
  if (!filters) return undefined;
  const out: FacetFilters = {};

  const type = normalizeList(filters.type, false);
  if (type) out.type = type;
  const extension = normalizeList(filters.extension, true);
  if (extension) out.extension = extension;

  if (filters.filename && filters.filename.trim()) out.filename = filters.filename.trim();
  if (filters.ingested_date_gte) out.ingested_date_gte = filters.ingested_date_gte;
  if (filters.ingested_date_lte) out.ingested_date_lte = filters.ingested_date_lte;
  if (filters.date_range_option) out.date_range_option = filters.date_range_option;

  for (const key of ["asset_size_gte", "asset_size_lte", "LargerThan"] as const) {
    const value = filters[key];
    if (typeof value === "number" && Number.isFinite(value)) out[key] = value;
  }

  if (isRelativeRange(out.date_range_option)) {
    // Recomputed from "now" on replay; stored dates would make it go stale.
    delete out.ingested_date_gte;
    delete out.ingested_date_lte;
  }

  const custom = normalizeCustomMetadata(filters.customMetadataFilters);
  if (custom) out.customMetadataFilters = custom;

  return Object.keys(out).length ? out : undefined;
}

/** Canonical form of a definition; equal searches normalize to equal objects. */
export function normalizeDefinition(input: Partial<SearchDefinition>): SearchDefinition {
  const definition: SearchDefinition = {
    v: SEARCH_DEFINITION_VERSION,
    q: (input.q ?? "").split(/\s+/).filter(Boolean).join(" "),
    semantic: !!input.semantic,
  };
  if (definition.semantic) {
    if (input.semanticMode && SEMANTIC_MODES.includes(input.semanticMode)) {
      definition.semanticMode = input.semanticMode;
    }
    const modes = (input.searchModes ?? []).filter((m) => SEARCH_MODALITIES.includes(m));
    if (modes.length) definition.searchModes = [...new Set(modes)].sort(compareCodePoints);
  }
  const filters = normalizeFilters(input.filters);
  if (filters) definition.filters = filters;
  return definition;
}

/** Stable identifier of a search; identical to the API's `fingerprint`. */
export async function fingerprintDefinition(input: Partial<SearchDefinition>): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(normalizeDefinition(input)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

/** A browse-everything search with no filters, which isn't worth recording. */
export function isBlankDefinition(definition: SearchDefinition): boolean {
  const normalized = normalizeDefinition(definition);
  return (normalized.q === "" || normalized.q === "*") && !normalized.filters;
}

export function definitionFromState(state: SearchStateSnapshot): SearchDefinition {
  return normalizeDefinition({
    q: state.query,
    semantic: state.isSemantic,
    semanticMode: state.semanticMode,
    searchModes: state.searchModes,
    filters: state.filters,
  });
}

/**
 * Turn relative date ranges ("last 7 days") back into absolute dates measured
 * from `now`, exactly as the filter dialog does when the option is picked.
 */
export function resolveRelativeDates(
  definition: SearchDefinition,
  now: Date = new Date()
): SearchDefinition {
  const range = definition.filters?.date_range_option;
  if (!range || !isRelativeRange(range)) return definition;
  return {
    ...definition,
    filters: {
      ...definition.filters,
      ingested_date_gte: subDays(now, RELATIVE_DAYS[range]).toISOString(),
      ingested_date_lte: now.toISOString(),
    },
  };
}

/** Build the /search query string that reproduces this definition. */
export function definitionToSearchParams(definition: SearchDefinition): URLSearchParams {
  const params = new URLSearchParams();
  params.set("q", definition.q);
  params.set("semantic", String(definition.semantic));
  if (definition.semantic) {
    if (definition.semanticMode) params.set(SEMANTIC_MODE_PARAM, definition.semanticMode);
    if (definition.searchModes?.length)
      params.set(SEARCH_MODES_PARAM, [...definition.searchModes].sort(compareCodePoints).join(","));
  }
  if (definition.filters) appendFiltersToUrlParams(params, definition.filters);
  return params;
}

export function searchUrlForDefinition(definition: SearchDefinition): string {
  return `/search?${definitionToSearchParams(resolveRelativeDates(definition)).toString()}`;
}

/** Read the semantic options out of a /search URL. Missing params return undefined. */
export function parseSemanticParams(params: URLSearchParams): {
  semanticMode?: SemanticMode;
  searchModes?: SearchModality[];
} {
  const mode = params.get(SEMANTIC_MODE_PARAM);
  const modes = params
    .get(SEARCH_MODES_PARAM)
    ?.split(",")
    .map((m) => m.trim())
    .filter((m): m is SearchModality => SEARCH_MODALITIES.includes(m as SearchModality));
  return {
    semanticMode: SEMANTIC_MODES.includes(mode as SemanticMode)
      ? (mode as SemanticMode)
      : undefined,
    searchModes: modes && modes.length ? modes : undefined,
  };
}

type Translate = (key: string, fallback: string, options?: Record<string, unknown>) => string;

/** Short, human-readable pieces describing a definition's options, for chips. */
export function describeDefinition(definition: SearchDefinition, t: Translate): string[] {
  const parts: string[] = [];
  if (definition.semantic) {
    parts.push(
      definition.semanticMode === "full"
        ? t("search.history.describe.semanticFull", "Semantic · Full")
        : t("search.history.describe.semantic", "Semantic")
    );
    if (definition.searchModes?.length) parts.push(definition.searchModes.join(" + "));
  }
  const f = definition.filters;
  if (f?.type) parts.push(f.type.split(",").join(", "));
  if (f?.extension) parts.push(f.extension.split(",").join(", "));
  if (f?.date_range_option && isRelativeRange(f.date_range_option))
    parts.push(
      t("search.history.describe.lastRange", "Last {{range}}", { range: f.date_range_option })
    );
  else if (f?.ingested_date_gte || f?.ingested_date_lte)
    parts.push(t("search.history.describe.dateRange", "Date range"));
  if (f?.asset_size_gte !== undefined || f?.asset_size_lte !== undefined)
    parts.push(t("search.history.describe.size", "Size"));
  if (f?.filename)
    parts.push(t("search.history.describe.file", "File: {{name}}", { name: f.filename }));
  if (f?.customMetadataFilters?.length)
    parts.push(
      f.customMetadataFilters.length === 1
        ? f.customMetadataFilters[0].field.replace(/^Metadata\./, "")
        : t("search.history.describe.metadataFilters", "{{count}} metadata filters", {
            count: f.customMetadataFilters.length,
          })
    );
  return parts;
}

/** A default name for saving a search: the query, else a summary of its filters. */
export function suggestSearchName(
  definition: SearchDefinition,
  t: Translate,
  fallback: string
): string {
  const pieces = [definition.q, ...describeDefinition(definition, t)].filter(Boolean);
  const name = pieces.join(" · ") || fallback;
  return name.length > 100 ? `${name.slice(0, 97)}...` : name;
}
