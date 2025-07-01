import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useSearchInitialization, useOptimizedSearchParams } from '@/hooks/useSearchState';
import { useSearch } from '@/api/hooks/useSearch';
import { useSearchFields } from '@/api/hooks/useSearchFields';
import { useAssetOperations } from '@/hooks/useAssetOperations';
import { useViewPreferences } from '@/hooks/useViewPreferences';
import { useAssetSelection } from '@/hooks/useAssetSelection';
import { useAssetFavorites } from '@/hooks/useAssetFavorites';
import { useFeatureFlag } from '@/utils/featureFlags';
import {
  useSearchQuery,
  useSemanticSearch,
  useSelectedFields,
  useCoreActions,
  useFilterActions,
  useUIActions,
  useTypeFilters,
  useExtensionFilters,
  useSizeFilter,
  useDateFilter,
  useTextFilters
} from '@/stores/searchStore';
import SearchPagePresentation from './SearchPagePresentation';
import { type AssetItem, type LocationState } from './types';

const SearchPageContainer: React.FC = () => {
  const location = useLocation();
  const locationState = location.state as LocationState;
  
  // Initialize search state with URL sync
  const { initialize } = useSearchInitialization(locationState?.query);
  
  // Get optimized search parameters
  const { apiParams } = useOptimizedSearchParams();
  
  // Core search state
  const query = useSearchQuery();
  const semantic = useSemanticSearch();
  const selectedFields = useSelectedFields();
  
  // Filter state
  const typeFilters = useTypeFilters();
  const extensionFilters = useExtensionFilters();
  const sizeFilter = useSizeFilter();
  const dateFilter = useDateFilter();
  const textFilters = useTextFilters();
  
  // Actions
  const { setQuery, setPage, setPageSize, setSemantic } = useCoreActions();
  const { setTypeFilters, setExtensionFilters, setSizeFilter, setDateFilter, setTextFilters } = useFilterActions();
  const { setLoading, setError } = useUIActions();
  
  // Convert optimized parameters to legacy format for useSearch
  const legacyParams = {
    page: apiParams.page,
    pageSize: apiParams.pageSize,
    isSemantic: apiParams.semantic,
    fields: selectedFields, // Use the resolved field paths as string array
    type: apiParams.type,
    extension: apiParams.extension,
    filename: apiParams.filename,
    // Map other parameters as needed
  };

  // API hooks with legacy parameters
  const {
    data: searchData,
    isLoading: isSearchLoading,
    isFetching: isSearchFetching,
    error: searchError
  } = useSearch(query, legacyParams);
  
  const {
    data: fieldsData,
    isLoading: isFieldsLoading,
    error: fieldsError
  } = useSearchFields();
  
  // Initialize on mount
  useEffect(() => {
    initialize();
  }, [initialize]);
  
  // Sync loading state
  useEffect(() => {
    setLoading(isSearchLoading || isSearchFetching);
  }, [isSearchLoading, isSearchFetching, setLoading]);
  
  // Sync error state
  useEffect(() => {
    if (searchError) {
      setError(searchError.message);
    } else {
      setError(undefined);
    }
  }, [searchError, setError]);
  
  // Extract search results
  const searchResults = searchData?.data?.results || [];
  const searchMetadata = searchData?.data?.searchMetadata;
  
  // Extract fields data
  const defaultFields = fieldsData?.data?.defaultFields || [];
  const availableFields = fieldsData?.data?.availableFields || [];
  
  // Asset accessors for hooks
  const getAssetId = (asset: AssetItem) => asset.InventoryID;
  const getAssetName = (asset: AssetItem) => 
    asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
  const getAssetType = (asset: AssetItem) => asset.DigitalSourceAsset.Type;
  const getAssetThumbnail = (asset: AssetItem) => asset.thumbnailUrl || '';
  
  // View preferences
  const viewPreferences = useViewPreferences({
    initialViewMode: locationState?.preserveSearch ? locationState.viewMode : 'card',
    initialCardSize: locationState?.preserveSearch ? locationState.cardSize : 'medium',
    initialAspectRatio: locationState?.preserveSearch ? locationState.aspectRatio : 'square',
    initialThumbnailScale: locationState?.preserveSearch ? locationState.thumbnailScale : 'fit',
    initialShowMetadata: locationState?.preserveSearch ? locationState.showMetadata : true,
    initialGroupByType: locationState?.preserveSearch ? locationState.groupByType : false,
  });
  
  // Asset selection
  const assetSelection = useAssetSelection({
    getAssetId,
    getAssetName,
    getAssetType,
  });
  
  // Asset favorites
  const assetFavorites = useAssetFavorites({
    getAssetId,
    getAssetName,
    getAssetType,
    getAssetThumbnail,
  });
  
  // Asset operations
  const assetOperations = useAssetOperations<AssetItem>();
  
  // Feature flags
  const multiSelectFeature = useFeatureFlag('search-multi-select-enabled', false);
  
  // Filter state for legacy components
  const legacyFilters = {
    mediaTypes: {
      videos: typeFilters.includes('Video'),
      images: typeFilters.includes('Image'),
      audio: typeFilters.includes('Audio'),
    },
    time: {
      recent: false,
      lastWeek: false,
      lastMonth: false,
      lastYear: false,
    }
  };
  
  const expandedSections = {
    mediaTypes: true,
    time: true,
    status: true,
  };
  
  // Event handlers
  const handleFilterChange = (section: string, filter: string) => {
    if (section === 'mediaTypes') {
      const currentTypes = [...typeFilters];
      const typeMap: Record<string, string> = {
        videos: 'Video',
        images: 'Image',
        audio: 'Audio'
      };
      
      const actualType = typeMap[filter];
      if (actualType) {
        const index = currentTypes.indexOf(actualType);
        if (index > -1) {
          currentTypes.splice(index, 1);
        } else {
          currentTypes.push(actualType);
        }
        setTypeFilters(currentTypes);
      }
    }
  };
  
  const handleSectionToggle = (section: string) => {
    // Legacy implementation - could be enhanced with UI store
  };
  
  const handleFieldsChange = (event: any) => {
    const newFields = typeof event.target.value === 'string' 
      ? event.target.value.split(',') 
      : event.target.value;
    
    // This will be handled by the field actions in the store
    // For now, maintain compatibility
  };
  
  return (
    <SearchPagePresentation
      // Search data
      searchResults={searchResults}
      searchMetadata={searchMetadata}
      query={query}
      semantic={semantic}
      selectedFields={selectedFields}
      
      // Fields data
      defaultFields={defaultFields}
      availableFields={availableFields}
      onFieldsChange={handleFieldsChange}
      
      // Filter state
      filters={legacyFilters}
      expandedSections={expandedSections}
      onFilterChange={handleFilterChange}
      onSectionToggle={handleSectionToggle}
      
      // View preferences
      viewPreferences={viewPreferences}
      
      // Asset state
      assetSelection={assetSelection}
      assetFavorites={assetFavorites}
      assetOperations={assetOperations}
      
      // Feature flags
      multiSelectEnabled={multiSelectFeature.value}
      
      // Loading states
      isLoading={isSearchLoading}
      isFetching={isSearchFetching}
      isFieldsLoading={isFieldsLoading}
      
      // Error states
      error={searchError}
      fieldsError={fieldsError}
    />
  );
};

export default SearchPageContainer;