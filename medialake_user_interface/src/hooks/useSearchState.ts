import { useRef, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router";
import {
  useSearchQuery,
  useSemanticSearch,
  useSearchFilters,
  useDomainActions,
} from "../stores/searchStore";
import { FacetFilters, CustomMetadataApiFilter } from "../types/facetSearch";

interface UseSearchStateProps {
  initialQuery?: string;
  initialSemantic?: boolean;
  initialFilters?: FacetFilters;
}

/**
 * Parse filter-related search params into a FacetFilters object.
 */
function parseFiltersFromParams(searchParams: URLSearchParams): FacetFilters {
  const filters: FacetFilters = {};

  if (searchParams.has("type")) filters.type = searchParams.get("type") || undefined;
  if (searchParams.has("extension")) filters.extension = searchParams.get("extension") || undefined;
  if (searchParams.has("filename")) filters.filename = searchParams.get("filename") || undefined;

  if (searchParams.has("LargerThan")) {
    const v = searchParams.get("LargerThan");
    filters.LargerThan = v ? parseInt(v, 10) : undefined;
  }
  if (searchParams.has("asset_size_lte")) {
    const v = searchParams.get("asset_size_lte");
    filters.asset_size_lte = v ? parseInt(v, 10) : undefined;
  }
  if (searchParams.has("asset_size_gte")) {
    const v = searchParams.get("asset_size_gte");
    filters.asset_size_gte = v ? parseInt(v, 10) : undefined;
  }

  if (searchParams.has("ingested_date_lte"))
    filters.ingested_date_lte = searchParams.get("ingested_date_lte") || undefined;
  if (searchParams.has("ingested_date_gte"))
    filters.ingested_date_gte = searchParams.get("ingested_date_gte") || undefined;
  if (searchParams.has("date_range_option"))
    filters.date_range_option = searchParams.get("date_range_option") || undefined;

  // Custom metadata filters are serialized as a JSON array under `custom_md`.
  // These originate from the FilterModal and must round-trip through the URL
  // so they persist across search submissions (alongside regular filters).
  if (searchParams.has("custom_md")) {
    const raw = searchParams.get("custom_md");
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as CustomMetadataApiFilter[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          filters.customMetadataFilters = parsed;
        }
      } catch {
        // Malformed custom_md param — ignore and continue without custom filters
      }
    }
  }

  return filters;
}

/**
 * Hook that manages search state using Zustand store and URL synchronization.
 *
 * The hook computes the "effective" query, semantic flag, and filters by merging
 * URL params with the Zustand store. URL params always win — this prevents stale
 * store state from persisting across URL navigations.
 *
 * Uses targeted selectors (useSearchQuery, useSemanticSearch, useSearchFilters)
 * instead of subscribing to the entire store, so unrelated store changes (e.g.
 * filterModalDraft, aggregations, loading) do not trigger re-renders here.
 *
 * Store sync is performed in useEffect (not during render) to avoid the
 * side-effect-during-render anti-pattern that caused guaranteed double-renders.
 */
export const useSearchState = ({
  initialQuery = "",
  initialSemantic = false,
  initialFilters = {},
}: UseSearchStateProps = {}) => {
  const [searchParams] = useSearchParams();
  const isFirstMount = useRef(true);
  const prevParamsRef = useRef<string>("");

  // Targeted selectors — only re-render when these specific slices change
  const storeQuery = useSearchQuery();
  const storeIsSemantic = useSemanticSearch();
  const storeFilters = useSearchFilters();
  const { setQuery, setIsSemantic, setFilters, updateFilter, clearFilters } = useDomainActions();

  // ── Compute effective state from URL (pure computation, no side effects) ──
  const currentParamsKey = searchParams.toString();

  const { effectiveQuery, effectiveSemantic, effectiveFilters } = useMemo(() => {
    const urlQuery = searchParams.get("q");
    const urlSemantic = searchParams.get("semantic") === "true";
    const urlFilters = parseFiltersFromParams(searchParams);
    const hasUrlFilters = Object.keys(urlFilters).length > 0;

    // URL params take precedence over store values
    let query = storeQuery;
    let semantic = storeIsSemantic;
    let filters = storeFilters;

    if (urlQuery !== null) {
      query = urlQuery;
    } else if (isFirstMount.current && initialQuery) {
      query = initialQuery;
    }

    if (searchParams.has("semantic")) {
      semantic = urlSemantic;
    } else if (isFirstMount.current && initialSemantic) {
      semantic = initialSemantic;
    }

    if (hasUrlFilters) {
      filters = urlFilters;
    } else if (isFirstMount.current && Object.keys(initialFilters).length > 0) {
      filters = initialFilters;
    } else if (!isFirstMount.current && !hasUrlFilters) {
      filters = {};
    }

    return { effectiveQuery: query, effectiveSemantic: semantic, effectiveFilters: filters };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentParamsKey, storeQuery, storeIsSemantic, storeFilters]);

  // ── Sync store from URL in useEffect (not during render) ──
  useEffect(() => {
    const urlChanged = currentParamsKey !== prevParamsRef.current;
    if (!urlChanged) return;

    prevParamsRef.current = currentParamsKey;

    const urlQuery = searchParams.get("q");
    const urlSemantic = searchParams.get("semantic") === "true";
    const urlFilters = parseFiltersFromParams(searchParams);
    const hasUrlFilters = Object.keys(urlFilters).length > 0;

    if (isFirstMount.current) {
      isFirstMount.current = false;

      if (urlQuery !== null) {
        setQuery(urlQuery);
      } else if (initialQuery) {
        setQuery(initialQuery);
      }

      if (searchParams.has("semantic")) {
        setIsSemantic(urlSemantic);
      } else if (initialSemantic) {
        setIsSemantic(initialSemantic);
      }

      if (hasUrlFilters) {
        setFilters(urlFilters);
      } else if (Object.keys(initialFilters).length > 0) {
        setFilters(initialFilters);
      }
    } else {
      if (urlQuery !== null) {
        setQuery(urlQuery);
      }

      if (searchParams.has("semantic")) {
        setIsSemantic(urlSemantic);
      }

      if (hasUrlFilters) {
        setFilters(urlFilters);
      } else {
        clearFilters();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentParamsKey]);

  return {
    query: effectiveQuery,
    isSemantic: effectiveSemantic,
    filters: effectiveFilters,

    setQuery,
    setIsSemantic,
    setFilters,
    updateFilter,
    clearFilters,

    hasActiveFilters: Object.keys(effectiveFilters).length > 0,
    activeFilterCount: Object.keys(effectiveFilters).length,
  };
};
