import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FacetFilters } from '../components/search/FacetSearch';

interface UseFacetSearchProps {
  initialFilters?: FacetFilters;
}

interface UseFacetSearchResult {
  filters: FacetFilters;
  setFilters: (filters: FacetFilters) => void;
  updateFilter: <K extends keyof FacetFilters>(key: K, value: FacetFilters[K]) => void;
  clearFilters: () => void;
  hasActiveFilters: boolean;
  activeFilterCount: number;
}

/**
 * Hook to manage facet search filters
 * Handles state management and URL synchronization for facet filters
 */
export const useFacetSearch = ({ initialFilters = {} }: UseFacetSearchProps = {}): UseFacetSearchResult => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFiltersInternal] = useState<FacetFilters>(initialFilters);

  // Initialize filters from URL params on mount
  useEffect(() => {
    const filtersFromUrl: FacetFilters = {};
    
    // Extract facet parameters from URL
    if (searchParams.has('type')) filtersFromUrl.type = searchParams.get('type') || undefined;
    if (searchParams.has('extension')) filtersFromUrl.extension = searchParams.get('extension') || undefined;
    if (searchParams.has('filename')) filtersFromUrl.filename = searchParams.get('filename') || undefined;
    
    // Parse numeric values
    if (searchParams.has('LargerThan')) {
      const largerThan = searchParams.get('LargerThan');
      filtersFromUrl.LargerThan = largerThan ? parseInt(largerThan, 10) : undefined;
    }
    
    if (searchParams.has('asset_size_lte')) {
      const assetSizeLte = searchParams.get('asset_size_lte');
      filtersFromUrl.asset_size_lte = assetSizeLte ? parseInt(assetSizeLte, 10) : undefined;
    }
    
    if (searchParams.has('asset_size_gte')) {
      const assetSizeGte = searchParams.get('asset_size_gte');
      filtersFromUrl.asset_size_gte = assetSizeGte ? parseInt(assetSizeGte, 10) : undefined;
    }
    
    // Date values
    if (searchParams.has('ingested_date_lte')) {
      filtersFromUrl.ingested_date_lte = searchParams.get('ingested_date_lte') || undefined;
    }
    
    if (searchParams.has('ingested_date_gte')) {
      filtersFromUrl.ingested_date_gte = searchParams.get('ingested_date_gte') || undefined;
    }
    
    // Only update state if we have filters from URL
    if (Object.keys(filtersFromUrl).length > 0) {
      setFiltersInternal(filtersFromUrl);
    }
  }, []);

  // Update URL when filters change
  const setFilters = useCallback((newFilters: FacetFilters) => {
    setFiltersInternal(newFilters);
    
    // Update URL params
    setSearchParams(prev => {
      const updatedParams = new URLSearchParams(prev);
      
      // Remove all existing facet params
      updatedParams.delete('type');
      updatedParams.delete('extension');
      updatedParams.delete('LargerThan');
      updatedParams.delete('asset_size_lte');
      updatedParams.delete('asset_size_gte');
      updatedParams.delete('ingested_date_lte');
      updatedParams.delete('ingested_date_gte');
      updatedParams.delete('filename');
      
      // Add new facet params if they exist
      if (newFilters.type) updatedParams.set('type', newFilters.type);
      if (newFilters.extension) updatedParams.set('extension', newFilters.extension);
      if (newFilters.LargerThan) updatedParams.set('LargerThan', newFilters.LargerThan.toString());
      if (newFilters.asset_size_lte) updatedParams.set('asset_size_lte', newFilters.asset_size_lte.toString());
      if (newFilters.asset_size_gte) updatedParams.set('asset_size_gte', newFilters.asset_size_gte.toString());
      if (newFilters.ingested_date_lte) updatedParams.set('ingested_date_lte', newFilters.ingested_date_lte);
      if (newFilters.ingested_date_gte) updatedParams.set('ingested_date_gte', newFilters.ingested_date_gte);
      if (newFilters.filename) updatedParams.set('filename', newFilters.filename);
      
      return updatedParams;
    });
  }, [setSearchParams]);

  // Update a single filter
  const updateFilter = useCallback(<K extends keyof FacetFilters>(key: K, value: FacetFilters[K]) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  }, [setFilters]);

  // Clear all filters
  const clearFilters = useCallback(() => {
    setFilters({});
  }, [setFilters]);

  // Calculate if there are any active filters
  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  const hasActiveFilters = activeFilterCount > 0;

  return {
    filters,
    setFilters,
    updateFilter,
    clearFilters,
    hasActiveFilters,
    activeFilterCount
  };
};