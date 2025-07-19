import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useSearchStore, useDomainActions } from "../stores/searchStore";
import { FacetFilters } from "../types/facetSearch";

interface UseSearchStateProps {
  initialQuery?: string;
  initialSemantic?: boolean;
  initialFilters?: FacetFilters;
}

/**
 * Hook that manages search state using Zustand store and URL synchronization
 * This replaces the old useFacetSearch hook and provides better state persistence
 */
export const useSearchState = ({
  initialQuery = "",
  initialSemantic = false,
  initialFilters = {},
}: UseSearchStateProps = {}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const isInitialized = useRef(false);

  // Get state from Zustand store
  const searchStore = useSearchStore();
  const { setQuery, setIsSemantic, setFilters, updateFilter, clearFilters } =
    useDomainActions();

  // Initialize state from URL params or initial values - only run once
  useEffect(() => {
    if (isInitialized.current) return;

    const urlQuery = searchParams.get("q");
    const urlSemantic = searchParams.get("semantic") === "true";

    // Initialize query if not already set
    if ((urlQuery || initialQuery) && !searchStore.query) {
      setQuery(urlQuery || initialQuery);
    }

    // Initialize semantic search if not already set
    if ((urlSemantic || initialSemantic) && !searchStore.isSemantic) {
      setIsSemantic(urlSemantic || initialSemantic);
    }

    // Initialize filters from URL params
    const urlFilters: FacetFilters = {};

    // Extract facet parameters from URL
    if (searchParams.has("type"))
      urlFilters.type = searchParams.get("type") || undefined;
    if (searchParams.has("extension"))
      urlFilters.extension = searchParams.get("extension") || undefined;
    if (searchParams.has("filename"))
      urlFilters.filename = searchParams.get("filename") || undefined;

    // Parse numeric values
    if (searchParams.has("LargerThan")) {
      const largerThan = searchParams.get("LargerThan");
      urlFilters.LargerThan = largerThan ? parseInt(largerThan, 10) : undefined;
    }

    if (searchParams.has("asset_size_lte")) {
      const assetSizeLte = searchParams.get("asset_size_lte");
      urlFilters.asset_size_lte = assetSizeLte
        ? parseInt(assetSizeLte, 10)
        : undefined;
    }

    if (searchParams.has("asset_size_gte")) {
      const assetSizeGte = searchParams.get("asset_size_gte");
      urlFilters.asset_size_gte = assetSizeGte
        ? parseInt(assetSizeGte, 10)
        : undefined;
    }

    // Date values
    if (searchParams.has("ingested_date_lte")) {
      urlFilters.ingested_date_lte =
        searchParams.get("ingested_date_lte") || undefined;
    }

    if (searchParams.has("ingested_date_gte")) {
      urlFilters.ingested_date_gte =
        searchParams.get("ingested_date_gte") || undefined;
    }

    if (searchParams.has("date_range_option")) {
      urlFilters.date_range_option =
        searchParams.get("date_range_option") || undefined;
    }

    // Use URL filters if available, otherwise use initial filters
    const filtersToUse =
      Object.keys(urlFilters).length > 0 ? urlFilters : initialFilters;

    // Initialize filters if store is empty and we have filters to set
    if (
      Object.keys(searchStore.filters).length === 0 &&
      Object.keys(filtersToUse).length > 0
    ) {
      setFilters(filtersToUse);
    }

    isInitialized.current = true;
  }, []); // Empty dependency array - only run once on mount

  return {
    // Current state
    query: searchStore.query,
    isSemantic: searchStore.isSemantic,
    filters: searchStore.filters,

    // Actions
    setQuery,
    setIsSemantic,
    setFilters,
    updateFilter,
    clearFilters,

    // Computed values
    hasActiveFilters: searchStore.actions.hasActiveFilters(),
    activeFilterCount: searchStore.actions.activeFilterCount(),
  };
};
