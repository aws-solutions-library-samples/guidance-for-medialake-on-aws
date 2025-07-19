import React, { useState, useEffect, useCallback } from "react";
import { useFeatureFlag } from "@/utils/featureFlags";
import { formatDate } from "@/utils/dateFormat";
import {
  Box,
  Typography,
  LinearProgress,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  Chip,
  OutlinedInput,
  SelectChangeEvent,
  Snackbar,
  Alert,
} from "@mui/material";
import SearchOffIcon from "@mui/icons-material/SearchOff";
import {
  RightSidebar,
  RightSidebarProvider,
} from "../components/common/RightSidebar";
import SearchFilters from "../components/search/SearchFilters";
import MasterResultsView from "../components/search/MasterResultsView";
import { useSearch } from "../api/hooks/useSearch";
import { useSearchFields, type FieldInfo } from "../api/hooks/useSearchFields";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import {
  type AssetBase,
  type ImageItem,
  type VideoItem,
  type AudioItem,
} from "@/types/search/searchResults";
import {
  type SortingState,
  type ColumnDef,
  type CellContext,
} from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import { SearchError } from "@/api/hooks/useSearch";
import TabbedSidebar from "../components/common/RightSidebar/TabbedSidebar";
import { useLocation, useSearchParams, useNavigate } from "react-router-dom";
import ApiStatusModal from "../components/ApiStatusModal";
import { useViewPreferences } from "@/hooks/useViewPreferences";
import { useAssetSelection } from "@/hooks/useAssetSelection";
import { useAssetFavorites } from "@/hooks/useAssetFavorites";

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
};
import { useSearchState } from "../hooks/useSearchState";
import { FacetFilters } from "../types/facetSearch";

interface LocationState {
  query?: string;
  isSemantic?: boolean;
  preserveSearch?: boolean;
  viewMode?: "card" | "table";
  cardSize?: "small" | "medium" | "large";
  aspectRatio?: "vertical" | "square" | "horizontal";
  thumbnailScale?: "fit" | "fill";
  showMetadata?: boolean;
  groupByType?: boolean;
  type?: string;
  extension?: string;
  LargerThan?: number;
  asset_size_lte?: number;
  asset_size_gte?: number;
  ingested_date_lte?: string;
  ingested_date_gte?: string;
  filename?: string;
}

interface Filters {
  mediaTypes: {
    videos: boolean;
    images: boolean;
    audio: boolean;
  };
  time: {
    recent: boolean;
    lastWeek: boolean;
    lastMonth: boolean;
    lastYear: boolean;
  };
}

const DEFAULT_PAGE_SIZE = 50;

interface SelectedAsset {
  id: string;
  name: string;
  type: string;
  inventoryID: string;
}

const SearchPage: React.FC = () => {
  const location = useLocation();
  const {
    query,
    isSemantic,
    type,
    extension,
    LargerThan,
    asset_size_lte,
    asset_size_gte,
    ingested_date_lte,
    ingested_date_gte,
    filename,
  } = (location.state as LocationState) || {};
  const [searchParams, setSearchParams] = useSearchParams();
  const currentPage = parseInt(searchParams.get("page") || "1", 10);
  const navigate = useNavigate();

  const [pageSize, setPageSize] = useState<number>(
    parseInt(searchParams.get("pageSize") || DEFAULT_PAGE_SIZE.toString(), 10),
  );

  // Initialize facet filters from URL params first, then fall back to location state
  const initialFacetFilters: FacetFilters = {
    // Get values from URL params first, then fall back to location state
    type: searchParams.get("type") || type,
    extension: searchParams.get("extension") || extension,
    LargerThan: searchParams.has("LargerThan")
      ? parseInt(searchParams.get("LargerThan") || "0", 10)
      : LargerThan,
    asset_size_lte: searchParams.has("asset_size_lte")
      ? parseInt(searchParams.get("asset_size_lte") || "0", 10)
      : asset_size_lte,
    asset_size_gte: searchParams.has("asset_size_gte")
      ? parseInt(searchParams.get("asset_size_gte") || "0", 10)
      : asset_size_gte,
    ingested_date_lte:
      searchParams.get("ingested_date_lte") || ingested_date_lte,
    ingested_date_gte:
      searchParams.get("ingested_date_gte") || ingested_date_gte,
    filename: searchParams.get("filename") || filename,
  };

  // Remove undefined values
  Object.keys(initialFacetFilters).forEach((key) => {
    if (initialFacetFilters[key as keyof FacetFilters] === undefined) {
      delete initialFacetFilters[key as keyof FacetFilters];
    }
  });

  // Use the new search state hook that integrates with Zustand
  const searchState = useSearchState({
    initialQuery: query,
    initialSemantic: isSemantic,
    initialFilters: initialFacetFilters,
  });

  // Get current values from the search state
  const currentQuery = searchState.query;
  const currentSemantic = searchState.isSemantic;
  const facetFilters = searchState.filters;

  // State for selected fields
  const [selectedFields, setSelectedFields] = useState<string[]>([]);

  const { data, isLoading, isFetching, error } = useSearch(currentQuery, {
    page: currentPage,
    pageSize: pageSize,
    isSemantic: currentSemantic,
    fields: selectedFields,
    ...facetFilters, // Include facet filters in the search
  });

  // Access the nested data structure correctly
  const searchData = data?.data;
  const searchResults = searchData?.results || [];
  const searchMetadata = searchData?.searchMetadata;

  // Store search results in sessionStorage for access by other components
  useEffect(() => {
    if (searchResults) {
      try {
        sessionStorage.setItem("searchResults", JSON.stringify(searchResults));
        // Trigger storage event for other components to detect the change
        window.dispatchEvent(new Event("storage"));
      } catch (e) {
        console.error("Error storing search results in session storage", e);
      }
    }
  }, [searchResults]);

  // Fetch search fields
  const {
    data: fieldsData,
    isLoading: isFieldsLoading,
    error: fieldsError,
  } = useSearchFields();

  // Extract fields data
  const defaultFields = fieldsData?.data?.defaultFields || [];
  const availableFields = fieldsData?.data?.availableFields || [];

  // Initialize selected fields with default fields when data is loaded
  useEffect(() => {
    if (defaultFields.length > 0 && selectedFields.length === 0) {
      setSelectedFields(defaultFields.map((field) => field.name));
    }
  }, [defaultFields, selectedFields.length]);

  // Handle field selection change
  const handleFieldsChange = (
    event: SelectChangeEvent<typeof selectedFields>,
  ) => {
    const {
      target: { value },
    } = event;
    const newSelectedFields =
      typeof value === "string" ? value.split(",") : value;

    // Check if fields were added or removed
    const fieldsAdded = newSelectedFields.some(
      (field) => !selectedFields.includes(field),
    );

    // Update the selected fields state
    setSelectedFields(newSelectedFields);

    // Only make a new API request if fields were added
    if (fieldsAdded) {
      // Reset to first page when adding fields
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        newParams.set("page", "1");
        return newParams;
      });
    }
    // If fields were only removed, don't make a new API request
  };

  const [filters, setFilters] = useState<Filters>({
    mediaTypes: {
      videos: true,
      images: true,
      audio: true,
    },
    time: {
      recent: false,
      lastWeek: false,
      lastMonth: false,
      lastYear: false,
    },
  });

  // Check if multi-select feature is enabled
  const multiSelectFeature = useFeatureFlag(
    "search-multi-select-enabled",
    false,
  );

  // Use custom hooks for view preferences, asset selection, and favorites
  const viewPreferences = useViewPreferences({
    initialViewMode: location.state?.preserveSearch
      ? location.state.viewMode
      : "card",
    initialCardSize: location.state?.preserveSearch
      ? location.state.cardSize
      : "medium",
    initialAspectRatio: location.state?.preserveSearch
      ? location.state.aspectRatio
      : "square",
    initialThumbnailScale: location.state?.preserveSearch
      ? location.state.thumbnailScale
      : "fit",
    initialShowMetadata: location.state?.preserveSearch
      ? location.state.showMetadata
      : true,
    initialGroupByType: location.state?.preserveSearch
      ? location.state.groupByType
      : false,
  });
  const [editingAssetId, setEditingAssetId] = useState<string>();
  const [editedName, setEditedName] = useState<string>();

  // Asset accessors for hooks
  const getAssetId = useCallback((asset: AssetItem) => asset.InventoryID, []);
  const getAssetName = useCallback(
    (asset: AssetItem) =>
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
        .ObjectKey.Name,
    [],
  );
  const getAssetType = useCallback(
    (asset: AssetItem) => asset.DigitalSourceAsset.Type,
    [],
  );
  const getAssetThumbnail = useCallback(
    (asset: AssetItem) => asset.thumbnailUrl || "",
    [],
  );

  // Use custom hooks for asset selection and favorites
  const assetSelection = useAssetSelection({
    getAssetId,
    getAssetName,
    getAssetType,
  });

  const assetFavorites = useAssetFavorites({
    getAssetId,
    getAssetName,
    getAssetType,
    getAssetThumbnail,
  });

  const {
    handleDeleteClick,
    handleStartEditing,
    handleNameChange,
    handleNameEditComplete,
    handleAction,
    handleDeleteConfirm,
    handleDeleteCancel,
    handleDownloadClick,
    editingAssetId: currentEditingAssetId,
    editedName: currentEditedName,
    isDeleteModalOpen,
    selectedAsset,
    alert,
    handleAlertClose,
    isLoading: assetOperationsLoading,
    renamingAssetId,
  } = useAssetOperations<AssetItem>();

  const handleAssetClick = useCallback(
    (asset: AssetItem) => {
      const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
      // Special case for audio to use singular form
      const pathPrefix = assetType === "audio" ? "/audio/" : `/${assetType}s/`;
      navigate(`${pathPrefix}${asset.InventoryID}`, {
        state: {
          assetType: asset.DigitalSourceAsset.Type,
          searchTerm: currentQuery,
          asset: asset,
        },
      });
    },
    [navigate, currentQuery],
  );

  // Update local state from useAssetOperations
  useEffect(() => {
    setEditingAssetId(currentEditingAssetId || undefined);
    setEditedName(currentEditedName);
  }, [currentEditingAssetId, currentEditedName]);

  const formatFileSize = (sizeInBytes: number) => {
    const sizes = ["B", "KB", "MB", "GB"];
    let i = 0;
    let size = sizeInBytes;
    while (size >= 1024 && i < sizes.length - 1) {
      size /= 1024;
      i++;
    }
    return `${Math.round(size * 100) / 100} ${sizes[i]}`;
  };

  const [columns, setColumns] = useState<AssetTableColumn<AssetItem>[]>([
    {
      id: "name",
      label: "Name",
      visible: true,
      minWidth: 200,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      cell: (info: CellContext<AssetItem, unknown>) =>
        info.getValue() as string,
      sortable: true,
      sortingFn: (rowA, rowB) =>
        rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.localeCompare(
          rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.ObjectKey.Name,
        ),
    },
    {
      id: "type",
      label: "Type",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) => row.DigitalSourceAsset.Type,
      sortable: true,
      sortingFn: (rowA, rowB) =>
        rowA.original.DigitalSourceAsset.Type.localeCompare(
          rowB.original.DigitalSourceAsset.Type,
        ),
    },
    {
      id: "format",
      label: "Format",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.Format,
      sortable: true,
      sortingFn: (rowA, rowB) =>
        rowA.original.DigitalSourceAsset.MainRepresentation.Format.localeCompare(
          rowB.original.DigitalSourceAsset.MainRepresentation.Format,
        ),
    },
    {
      id: "size",
      label: "Size",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .FileInfo.Size,
      cell: (info: CellContext<AssetItem, unknown>) =>
        formatFileSize(info.getValue() as number),
      sortable: true,
      sortingFn: (rowA, rowB) => {
        const a =
          rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.FileInfo.Size;
        const b =
          rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo
            .PrimaryLocation.FileInfo.Size;
        return a - b;
      },
    },
    {
      id: "date",
      label: "Date Created",
      visible: true,
      minWidth: 150,
      accessorFn: (row: AssetItem) => row.DigitalSourceAsset.CreateDate,
      cell: (info: CellContext<AssetItem, unknown>) => {
        return formatDate(info.getValue() as string);
      },
      sortable: true,
      sortingFn: (rowA, rowB) => {
        const a = new Date(
          rowA.original.DigitalSourceAsset.CreateDate,
        ).getTime();
        const b = new Date(
          rowB.original.DigitalSourceAsset.CreateDate,
        ).getTime();
        return a - b;
      },
    },
  ]);

  const handleColumnToggle = (columnId: string) => {
    setColumns((prev) =>
      prev.map((column) =>
        column.id === columnId
          ? { ...column, visible: !column.visible }
          : column,
      ),
    );
  };

  const filteredResults =
    searchResults?.filter((item) => {
      const isImage =
        item.DigitalSourceAsset.Type === "Image" && filters.mediaTypes.images;
      const isVideo =
        item.DigitalSourceAsset.Type === "Video" && filters.mediaTypes.videos;
      const isAudio =
        item.DigitalSourceAsset.Type === "Audio" && filters.mediaTypes.audio;

      // Time-based filtering
      const createdAt = new Date(item.DigitalSourceAsset.CreateDate);
      const now = new Date();
      const timeDiff = now.getTime() - createdAt.getTime();
      const isRecent = filters.time.recent && timeDiff <= 24 * 60 * 60 * 1000;
      const isLastWeek =
        filters.time.lastWeek && timeDiff <= 7 * 24 * 60 * 60 * 1000;
      const isLastMonth =
        filters.time.lastMonth && timeDiff <= 30 * 24 * 60 * 60 * 1000;
      const isLastYear =
        filters.time.lastYear && timeDiff <= 365 * 24 * 60 * 60 * 1000;

      const passesTimeFilter =
        (!filters.time.recent &&
          !filters.time.lastWeek &&
          !filters.time.lastMonth &&
          !filters.time.lastYear) ||
        isRecent ||
        isLastWeek ||
        isLastMonth ||
        isLastYear;

      return (isImage || isVideo || isAudio) && passesTimeFilter;
    }) || [];

  const imageResults = filteredResults.filter(
    (item) => item.DigitalSourceAsset.Type === "Image",
  );
  const videoResults = filteredResults.filter(
    (item) => item.DigitalSourceAsset.Type === "Video",
  );
  const audioResults = filteredResults.filter(
    (item) => item.DigitalSourceAsset.Type === "Audio",
  );

  const [expandedSections, setExpandedSections] = useState({
    mediaTypes: true,
    time: true,
    status: true,
  });

  // URL synchronization is now handled by useSearchState hook

  // No need for these effects as they're now handled in the useAssetSelection hook

  const handleFilterChange = (section: keyof Filters, filter: string) => {
    setFilters((prev) => {
      const newFilters = { ...prev };
      if (section === "time") {
        // Reset all time filters
        Object.keys(newFilters.time).forEach((key) => {
          newFilters.time[key as keyof typeof newFilters.time] = false;
        });
      }
      (newFilters[section] as any)[filter] = !(prev[section] as any)[filter];
      return newFilters;
    });
  };

  const handleSectionToggle = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section as keyof typeof prev],
    }));
  };

  const handleSearch = (params: { page: number }) => {
    let timeFilter = "";
    if (filters.time.recent) timeFilter = "recent";
    if (filters.time.lastWeek) timeFilter = "lastWeek";
    if (filters.time.lastMonth) timeFilter = "lastMonth";
    if (filters.time.lastYear) timeFilter = "lastYear";

    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev);
      newParams.set("page", params.page.toString());
      if (currentQuery) {
        newParams.set("q", currentQuery);
      }
      if (timeFilter) {
        newParams.set("time", timeFilter);
      }
      if (currentSemantic) {
        newParams.set("semantic", "true");
      }
      return newParams;
    });
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    // Reset to first page when changing page size
    setSearchParams((prev) => {
      prev.set("pageSize", newPageSize.toString());
      prev.set("page", "1");
      return prev;
    });
  };

  // No need for this handler as it's now handled in the useAssetSelection hook

  return (
    <RightSidebarProvider>
      <>
        <Box
          sx={{
            display: "flex",
            minHeight: "100%",
            bgcolor: "background.default",
            position: "relative",
            overflow: "auto",
          }}
        >
          {isFetching && (
            <LinearProgress
              sx={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                zIndex: 9999,
              }}
            />
          )}

          {/* Main Content */}
          <Box
            sx={{
              flexGrow: 1,
              px: 4,
              pt: 1,
              pb: 2,
              display: "flex",
              flexDirection: "column",
              gap: 6,
              minHeight: 0,
              marginBottom: 4,
            }}
          >
            {searchMetadata?.totalResults === 0 && currentQuery && (
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: "50vh",
                  textAlign: "center",
                  gap: 2,
                }}
              >
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 2,
                    bgcolor: "background.paper",
                    borderRadius: 2,
                  }}
                >
                  <SearchOffIcon
                    sx={{
                      fontSize: 64,
                      color: "text.secondary",
                      mb: 2,
                    }}
                  />
                  <Typography variant="h5" color="text.primary" gutterBottom>
                    No results found
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    We couldn't find any matches for "{currentQuery}"
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1 }}
                  >
                    Try adjusting your search or filters to find what you're
                    looking for
                  </Typography>
                </Paper>
              </Box>
            )}

            {(filteredResults.length > 0 && searchMetadata && !error) ||
            error ? (
              <MasterResultsView
                results={error ? [] : filteredResults}
                searchMetadata={{
                  totalResults: error ? 0 : searchMetadata?.totalResults || 0,
                  page: currentPage,
                  pageSize: pageSize,
                }}
                onPageChange={(newPage) => handleSearch({ page: newPage })}
                onPageSizeChange={handlePageSizeChange}
                searchTerm={currentQuery}
                selectedFields={selectedFields}
                availableFields={availableFields}
                onFieldsChange={handleFieldsChange}
                groupByType={viewPreferences.groupByType}
                onGroupByTypeChange={viewPreferences.handleGroupByTypeChange}
                viewMode={viewPreferences.viewMode}
                onViewModeChange={viewPreferences.handleViewModeChange}
                cardSize={viewPreferences.cardSize}
                onCardSizeChange={viewPreferences.handleCardSizeChange}
                aspectRatio={viewPreferences.aspectRatio}
                onAspectRatioChange={viewPreferences.handleAspectRatioChange}
                thumbnailScale={viewPreferences.thumbnailScale}
                onThumbnailScaleChange={
                  viewPreferences.handleThumbnailScaleChange
                }
                showMetadata={viewPreferences.showMetadata}
                onShowMetadataChange={viewPreferences.handleShowMetadataChange}
                sorting={viewPreferences.sorting}
                onSortChange={viewPreferences.handleSortChange}
                cardFields={viewPreferences.cardFields}
                onCardFieldToggle={viewPreferences.handleCardFieldToggle}
                columns={columns}
                onColumnToggle={handleColumnToggle}
                onAssetClick={handleAssetClick}
                onDeleteClick={handleDeleteClick}
                onMenuClick={handleDownloadClick}
                onEditClick={handleStartEditing}
                onEditNameChange={handleNameChange}
                onEditNameComplete={handleNameEditComplete}
                editingAssetId={editingAssetId}
                editedName={editedName}
                isAssetFavorited={assetFavorites.isAssetFavorited}
                onFavoriteToggle={assetFavorites.handleFavoriteToggle}
                // Only pass selection props if multi-select feature is enabled
                selectedAssets={
                  multiSelectFeature.value
                    ? assetSelection.selectedAssetIds
                    : []
                }
                onSelectToggle={
                  multiSelectFeature.value
                    ? assetSelection.handleSelectToggle
                    : undefined
                }
                hasSelectedAssets={
                  multiSelectFeature.value
                    ? assetSelection.selectedAssets.length > 0
                    : false
                }
                selectAllState={
                  multiSelectFeature.value
                    ? assetSelection.getSelectAllState(filteredResults)
                    : "none"
                }
                onSelectAllToggle={
                  multiSelectFeature.value
                    ? () => {
                        assetSelection.handleSelectAll(filteredResults);
                      }
                    : undefined
                }
                isRenaming={assetOperationsLoading.rename}
                renamingAssetId={renamingAssetId}
                error={
                  error
                    ? {
                        status:
                          (error as SearchError).apiResponse?.status ||
                          error.name,
                        message:
                          (error as SearchError).apiResponse?.message ||
                          error.message,
                      }
                    : undefined
                }
                isLoading={isLoading || isFetching}
              />
            ) : null}
          </Box>

          <RightSidebar>
            <TabbedSidebar
              selectedAssets={assetSelection.selectedAssets}
              onBatchDelete={assetSelection.handleBatchDelete}
              onBatchDownload={assetSelection.handleBatchDownload}
              onBatchShare={assetSelection.handleBatchShare}
              onClearSelection={assetSelection.handleClearSelection}
              onRemoveItem={assetSelection.handleRemoveAsset}
              isDownloadLoading={assetSelection.isDownloadLoading}
              filterComponent={
                <>
                  <SearchFilters
                    filters={filters}
                    expandedSections={expandedSections}
                    onFilterChange={handleFilterChange}
                    onSectionToggle={handleSectionToggle}
                  />
                </>
              }
            />
          </RightSidebar>
        </Box>

        {/* Menu removed - download functionality now directly triggered by the download button */}

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={isDeleteModalOpen}
          onClose={handleDeleteCancel}
          aria-labelledby="delete-dialog-title"
          aria-describedby="delete-dialog-description"
        >
          <DialogTitle id="delete-dialog-title">Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText id="delete-dialog-description">
              Are you sure you want to delete this asset? This action cannot be
              undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel}>Cancel</Button>
            <Button onClick={handleDeleteConfirm} color="error" autoFocus>
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        {/* API Status Modal for bulk download */}
        <ApiStatusModal
          open={assetSelection.modalState.open}
          onClose={assetSelection.handleModalClose}
          status={assetSelection.modalState.status}
          action={assetSelection.modalState.action}
          message={assetSelection.modalState.message}
        />

        <Snackbar
          open={!!alert}
          autoHideDuration={6000}
          onClose={handleAlertClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        >
          <Alert
            onClose={handleAlertClose}
            severity={alert?.severity}
            sx={{ width: "100%" }}
          >
            {alert?.message}
          </Alert>
        </Snackbar>
      </>
    </RightSidebarProvider>
  );
};

export default SearchPage;
