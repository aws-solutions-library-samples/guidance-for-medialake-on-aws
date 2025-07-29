import React, { useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { useSearchState } from "@/hooks/useSearchState";
import { useSearch } from "@/api/hooks/useSearch";
import { useSearchFields } from "@/api/hooks/useSearchFields";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { useViewPreferences } from "@/hooks/useViewPreferences";
import { useAssetSelection } from "@/hooks/useAssetSelection";
import { useAssetFavorites } from "@/hooks/useAssetFavorites";
import { useFeatureFlag } from "@/utils/featureFlags";
import {
  useSearchQuery,
  useSemanticSearch,
  useSearchFilters,
  useDomainActions,
  useUIActions,
} from "@/stores/searchStore";
import SearchPagePresentation from "./SearchPagePresentation";
import { type AssetItem, type LocationState } from "./types";

const SearchPageContainer: React.FC = () => {
  const location = useLocation();
  const locationState = location.state as LocationState;

  // Initialize search state with URL sync
  const searchState = useSearchState({
    initialQuery: locationState?.query || "",
    initialSemantic: false,
    initialFilters: {},
  });

  // Core search state
  const query = useSearchQuery();
  const semantic = useSemanticSearch();
  const filters = useSearchFilters();

  // Actions
  const { setQuery, setIsSemantic, setFilters, updateFilter } =
    useDomainActions();
  const { openFilterModal, closeFilterModal, setLoading, setError } =
    useUIActions();

  // Convert filters to legacy format for useSearch
  const legacyParams = {
    page: 1,
    pageSize: 50,
    isSemantic: semantic,
    fields: [], // Default empty fields
    type: filters.type,
    extension: filters.extension,
    filename: filters.filename,
    asset_size_gte: filters.asset_size_gte,
    asset_size_lte: filters.asset_size_lte,
    ingested_date_gte: filters.ingested_date_gte,
    ingested_date_lte: filters.ingested_date_lte,
  };

  // API hooks with legacy parameters
  const {
    data: searchData,
    isLoading: isSearchLoading,
    isFetching: isSearchFetching,
    error: searchError,
  } = useSearch(query, legacyParams);

  const {
    data: fieldsData,
    isLoading: isFieldsLoading,
    error: fieldsError,
  } = useSearchFields();

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
  const selectedFields: string[] = []; // Default empty for now

  // Asset accessors for hooks
  const getAssetId = (asset: AssetItem) => asset.InventoryID;
  const getAssetName = (asset: AssetItem) =>
    asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
      .ObjectKey.Name;
  const getAssetType = (asset: AssetItem) => asset.DigitalSourceAsset.Type;
  const getAssetThumbnail = (asset: AssetItem) => asset.thumbnailUrl || "";

  // View preferences
  const viewPreferences = useViewPreferences({
    initialViewMode: locationState?.preserveSearch
      ? locationState.viewMode
      : "card",
    initialCardSize: locationState?.preserveSearch
      ? locationState.cardSize
      : "medium",
    initialAspectRatio: locationState?.preserveSearch
      ? locationState.aspectRatio
      : "square",
    initialThumbnailScale: locationState?.preserveSearch
      ? locationState.thumbnailScale
      : "fit",
    initialShowMetadata: locationState?.preserveSearch
      ? locationState.showMetadata
      : true,
    initialGroupByType: locationState?.preserveSearch
      ? locationState.groupByType
      : false,
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
  const multiSelectFeature = useFeatureFlag(
    "search-multi-select-enabled",
    false,
  );

  // Filter state for legacy components
  const typeArray = filters.type ? filters.type.split(",") : [];
  const legacyFilters = {
    mediaTypes: {
      videos: typeArray.includes("Video"),
      images: typeArray.includes("Image"),
      audio: typeArray.includes("Audio"),
    },
    time: {
      recent: false,
      lastWeek: false,
      lastMonth: false,
      lastYear: false,
    },
  };

  const expandedSections = {
    mediaTypes: true,
    time: true,
    status: true,
  };

  // Event handlers
  const handleFilterChange = (section: string, filter: string) => {
    if (section === "mediaTypes") {
      const currentTypes = filters.type ? filters.type.split(",") : [];
      const typeMap: Record<string, string> = {
        videos: "Video",
        images: "Image",
        audio: "Audio",
      };

      const actualType = typeMap[filter];
      if (actualType) {
        const index = currentTypes.indexOf(actualType);
        if (index > -1) {
          currentTypes.splice(index, 1);
        } else {
          currentTypes.push(actualType);
        }
        updateFilter(
          "type",
          currentTypes.length > 0 ? currentTypes.join(",") : undefined,
        );
      }
    }
  };

  const handleSectionToggle = (section: string) => {
    // Legacy implementation - could be enhanced with UI store
  };

  const handleFieldsChange = (event: any) => {
    const newFields =
      typeof event.target.value === "string"
        ? event.target.value.split(",")
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
