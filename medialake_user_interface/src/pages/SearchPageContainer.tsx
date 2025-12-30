import React, { useEffect, useState, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { useSearchState } from "@/hooks/useSearchState";
import { useSearch } from "@/api/hooks/useSearch";
import { useSearchFields } from "@/api/hooks/useSearchFields";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { useViewPreferences } from "@/hooks/useViewPreferences";
import { useAssetSelection } from "@/hooks/useAssetSelection";
import { useAssetFavorites } from "@/hooks/useAssetFavorites";
import {
  useSearchQuery,
  useSemanticSearch,
  useSemanticMode,
  useSearchFilters,
  useDomainActions,
  useUIActions,
} from "@/stores/searchStore";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { useAddItemToCollection } from "@/api/hooks/useCollections";
import { getOriginalAssetId } from "@/utils/clipTransformation";
import SearchPagePresentation from "./SearchPagePresentation";
import { type AssetItem, type LocationState } from "./types";

const SearchPageContainer: React.FC = () => {
  const location = useLocation();
  const locationState = location.state as LocationState;

  // Add to Collection state
  const [addToCollectionModalOpen, setAddToCollectionModalOpen] = useState(false);
  const [selectedAssetForCollection, setSelectedAssetForCollection] = useState<AssetItem | null>(
    null
  );
  const addItemToCollectionMutation = useAddItemToCollection();

  // Initialize search state with URL sync
  useSearchState({
    initialQuery: locationState?.query || "",
    initialSemantic: false,
    initialFilters: {},
  });

  // Core search state
  const query = useSearchQuery();
  const semantic = useSemanticSearch();
  const semanticMode = useSemanticMode();
  const filters = useSearchFilters();

  // Confidence threshold state for semantic search
  const [confidenceThreshold, setConfidenceThreshold] = React.useState<number>(0.57);

  // Actions
  const { updateFilter } = useDomainActions();
  const { setLoading, setError } = useUIActions();

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

  const { data: fieldsData, isLoading: isFieldsLoading, error: fieldsError } = useSearchFields();

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
    asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name;
  const getAssetType = (asset: AssetItem) => asset.DigitalSourceAsset.Type;
  const getAssetThumbnail = (asset: AssetItem) => asset.thumbnailUrl || "";

  // View preferences
  const viewPreferences = useViewPreferences({
    initialViewMode: locationState?.preserveSearch ? locationState.viewMode : "card",
    initialCardSize: locationState?.preserveSearch ? locationState.cardSize : "medium",
    initialAspectRatio: locationState?.preserveSearch ? locationState.aspectRatio : "square",
    initialThumbnailScale: locationState?.preserveSearch ? locationState.thumbnailScale : "fit",
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
        updateFilter("type", currentTypes.length > 0 ? currentTypes.join(",") : undefined);
      }
    }
  };
  const handleSectionToggle = () => {
    // Legacy implementation - could be enhanced with UI store
  };

  const handleFieldsChange = (event: any) => {
    const newFields =
      typeof event.target.value === "string" ? event.target.value.split(",") : event.target.value;

    // Future implementation: use newFields with field actions in the store
    console.log("Fields changed:", newFields);
  };

  // Handle Add to Collection click
  const handleAddToCollectionClick = useCallback(
    (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => {
      console.log("SearchPageContainer: Add to Collection clicked!", asset);
      event.stopPropagation();
      setSelectedAssetForCollection(asset);
      setAddToCollectionModalOpen(true);
    },
    []
  );

  // Handle actually adding the asset to a collection
  const handleAddToCollection = useCallback(
    async (collectionId: string) => {
      if (!selectedAssetForCollection) return;

      const assetId = getOriginalAssetId(selectedAssetForCollection);

      // Determine clip boundary based on semantic mode
      let clipBoundary = {};
      let addAllClips = false;

      if (semantic && semanticMode === "clip") {
        // In clip mode - add specific clip
        const clipData = (selectedAssetForCollection as any).clipData;
        if (clipData && clipData.start_timecode && clipData.end_timecode) {
          clipBoundary = {
            startTime: clipData.start_timecode,
            endTime: clipData.end_timecode,
          };
        }
      } else if (semantic && semanticMode === "full") {
        // In full mode with semantic search - add all clips
        addAllClips = true;
      }
      // Otherwise (non-semantic), add full file without clips

      await addItemToCollectionMutation.mutateAsync({
        collectionId,
        data: {
          assetId: assetId,
          clipBoundary: Object.keys(clipBoundary).length > 0 ? clipBoundary : undefined,
          addAllClips: addAllClips,
        },
      });
    },
    [selectedAssetForCollection, addItemToCollectionMutation, semantic, semanticMode]
  );

  return (
    <>
      <SearchPagePresentation
        // Search data
        searchResults={searchResults}
        searchMetadata={searchMetadata}
        query={query}
        semantic={semantic}
        selectedFields={selectedFields}
        confidenceThreshold={confidenceThreshold}
        onConfidenceThresholdChange={setConfidenceThreshold}
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
        // Add to Collection
        onAddToCollectionClick={handleAddToCollectionClick}
        // Feature flags
        multiSelectEnabled={true}
        // Loading states
        isLoading={isSearchLoading}
        isFetching={isSearchFetching}
        isFieldsLoading={isFieldsLoading}
        // Error states
        error={searchError}
        fieldsError={fieldsError}
      />

      {/* Add to Collection Modal */}
      {selectedAssetForCollection && (
        <AddToCollectionModal
          open={addToCollectionModalOpen}
          onClose={() => {
            setAddToCollectionModalOpen(false);
            setSelectedAssetForCollection(null);
          }}
          assetId={getOriginalAssetId(selectedAssetForCollection)}
          assetName={
            selectedAssetForCollection.DigitalSourceAsset.MainRepresentation.StorageInfo
              .PrimaryLocation.ObjectKey.Name
          }
          assetType={selectedAssetForCollection.DigitalSourceAsset.Type}
          onAddToCollection={handleAddToCollection}
        />
      )}
    </>
  );
};

export default SearchPageContainer;
