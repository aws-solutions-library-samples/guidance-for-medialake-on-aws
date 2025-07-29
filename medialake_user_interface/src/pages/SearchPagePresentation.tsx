import React, { useCallback } from "react";
import { useNavigate } from "react-router-dom";
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
} from "@mui/material";
import SearchOffIcon from "@mui/icons-material/SearchOff";
import {
  RightSidebar,
  RightSidebarProvider,
} from "@/components/common/RightSidebar";
import SearchFilters from "@/components/search/SearchFilters";
import MasterResultsView from "@/components/search/MasterResultsView";
import TabbedSidebar from "@/components/common/RightSidebar/TabbedSidebar";
import ApiStatusModal from "@/components/ApiStatusModal";
import { type AssetItem, type Filters, type ExpandedSections } from "./types";

interface SearchPagePresentationProps {
  // Search data
  searchResults: AssetItem[];
  searchMetadata?: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  query: string;
  semantic: boolean;
  selectedFields: string[];

  // Fields data
  defaultFields: Array<{
    name: string;
    displayName: string;
    description: string;
    type: string;
    isDefault: boolean;
  }>;
  availableFields: Array<{
    name: string;
    displayName: string;
    description: string;
    type: string;
    isDefault: boolean;
  }>;
  onFieldsChange: (event: any) => void;

  // Filter state
  filters: Filters;
  expandedSections: ExpandedSections;
  onFilterChange: (section: string, filter: string) => void;
  onSectionToggle: (section: string) => void;

  // View preferences
  viewPreferences: {
    viewMode: "card" | "table";
    cardSize: "small" | "medium" | "large";
    aspectRatio: "vertical" | "square" | "horizontal";
    thumbnailScale: "fit" | "fill";
    showMetadata: boolean;
    groupByType: boolean;
    sorting: any;
    cardFields: { id: string; label: string; visible: boolean }[];
    handleViewModeChange: (
      event: React.MouseEvent<HTMLElement>,
      newMode: "card" | "table" | null,
    ) => void;
    handleCardSizeChange: (size: "small" | "medium" | "large") => void;
    handleAspectRatioChange: (
      ratio: "vertical" | "square" | "horizontal",
    ) => void;
    handleThumbnailScaleChange: (scale: "fit" | "fill") => void;
    handleShowMetadataChange: (show: boolean) => void;
    handleGroupByTypeChange: (checked: boolean) => void;
    handleSortChange: (sorting: any) => void;
    handleCardFieldToggle: (fieldId: string) => void;
  };

  // Asset state
  assetSelection: {
    selectedAssets: any[];
    selectedAssetIds: string[];
    handleSelectToggle: (
      asset: AssetItem,
      event: React.MouseEvent<HTMLElement>,
    ) => void;
    handleSelectAll: (assets: AssetItem[]) => void;
    getSelectAllState: (assets: AssetItem[]) => "none" | "some" | "all";
    handleBatchDelete: () => void;
    handleBatchDownload: () => void;
    handleBatchShare: () => void;
    handleClearSelection: () => void;
    handleRemoveAsset: (assetId: string) => void;
    isDownloadLoading: boolean;
    modalState: {
      open: boolean;
      status: string;
      action: string;
      message?: string;
    };
    handleModalClose: () => void;
  };

  assetFavorites: {
    isAssetFavorited: (assetId: string) => boolean;
    handleFavoriteToggle: (
      asset: AssetItem,
      event: React.MouseEvent<HTMLElement>,
    ) => void;
  };

  assetOperations: {
    handleDeleteClick: (
      asset: AssetItem,
      event: React.MouseEvent<HTMLElement>,
    ) => void;
    handleStartEditing: (
      asset: AssetItem,
      event: React.MouseEvent<HTMLElement>,
    ) => void;
    handleNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    handleNameEditComplete: (asset: AssetItem, save: boolean) => void;
    handleAction: (action: string, asset: AssetItem) => void;
    handleDeleteConfirm: () => void;
    handleDeleteCancel: () => void;
    handleDownloadClick: (
      asset: AssetItem,
      event: React.MouseEvent<HTMLElement>,
    ) => void;
    editingAssetId?: string;
    editedName?: string;
    isDeleteModalOpen: boolean;
    selectedAsset?: AssetItem;
  };

  // Feature flags
  multiSelectEnabled: boolean;

  // Loading states
  isLoading: boolean;
  isFetching: boolean;
  isFieldsLoading: boolean;

  // Error states
  error?: any;
  fieldsError?: any;
}

const SearchPagePresentation: React.FC<SearchPagePresentationProps> = ({
  searchResults,
  searchMetadata,
  query,
  semantic,
  selectedFields,
  defaultFields,
  availableFields,
  onFieldsChange,
  filters,
  expandedSections,
  onFilterChange,
  onSectionToggle,
  viewPreferences,
  assetSelection,
  assetFavorites,
  assetOperations,
  multiSelectEnabled,
  isLoading,
  isFetching,
  isFieldsLoading,
  error,
  fieldsError,
}) => {
  const navigate = useNavigate();

  const handleAssetClick = useCallback(
    (asset: AssetItem) => {
      const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
      // Special case for audio to use singular form
      const pathPrefix = assetType === "audio" ? "/audio/" : `/${assetType}s/`;
      navigate(`${pathPrefix}${asset.InventoryID}`, {
        state: {
          assetType: asset.DigitalSourceAsset.Type,
          searchTerm: query,
          asset: asset,
        },
      });
    },
    [navigate, query],
  );

  const handlePageChange = (newPage: number) => {
    // This will be handled by the container through URL sync
  };

  const handlePageSizeChange = (newPageSize: number) => {
    // This will be handled by the container through URL sync
  };

  // Define columns for table view
  const columns = [
    {
      id: "name",
      label: "Name",
      visible: true,
      minWidth: 200,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      cell: (info: any) => info.getValue() as string,
      sortable: true,
      sortingFn: (rowA: any, rowB: any) =>
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
      sortingFn: (rowA: any, rowB: any) =>
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
      sortingFn: (rowA: any, rowB: any) =>
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
      cell: (info: any) => {
        const sizeInBytes = info.getValue() as number;
        const sizes = ["B", "KB", "MB", "GB"];
        let i = 0;
        let size = sizeInBytes;
        while (size >= 1024 && i < sizes.length - 1) {
          size /= 1024;
          i++;
        }
        return `${Math.round(size * 100) / 100} ${sizes[i]}`;
      },
      sortable: true,
      sortingFn: (rowA: any, rowB: any) => {
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
      cell: (info: any) => {
        const date = new Date(info.getValue() as string);
        return date.toLocaleDateString();
      },
      sortable: true,
      sortingFn: (rowA: any, rowB: any) => {
        const a = new Date(
          rowA.original.DigitalSourceAsset.CreateDate,
        ).getTime();
        const b = new Date(
          rowB.original.DigitalSourceAsset.CreateDate,
        ).getTime();
        return a - b;
      },
    },
  ];

  const handleColumnToggle = (columnId: string) => {
    // This could be enhanced with column state management
  };

  // Filter results based on current filters
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
            {searchMetadata?.totalResults === 0 && query && (
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
                    We couldn't find any matches for "{query}"
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
                  page: searchMetadata?.page || 1,
                  pageSize: searchMetadata?.pageSize || 50,
                }}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
                searchTerm={query}
                selectedFields={selectedFields}
                availableFields={availableFields}
                onFieldsChange={onFieldsChange}
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
                onDeleteClick={assetOperations.handleDeleteClick}
                onMenuClick={assetOperations.handleDownloadClick}
                onEditClick={assetOperations.handleStartEditing}
                onEditNameChange={assetOperations.handleNameChange}
                onEditNameComplete={assetOperations.handleNameEditComplete}
                editingAssetId={assetOperations.editingAssetId}
                editedName={assetOperations.editedName}
                isAssetFavorited={assetFavorites.isAssetFavorited}
                onFavoriteToggle={assetFavorites.handleFavoriteToggle}
                // Only pass selection props if multi-select feature is enabled
                selectedAssets={
                  multiSelectEnabled ? assetSelection.selectedAssetIds : []
                }
                onSelectToggle={
                  multiSelectEnabled
                    ? assetSelection.handleSelectToggle
                    : undefined
                }
                hasSelectedAssets={
                  multiSelectEnabled
                    ? assetSelection.selectedAssets.length > 0
                    : false
                }
                selectAllState={
                  multiSelectEnabled
                    ? assetSelection.getSelectAllState(filteredResults)
                    : "none"
                }
                onSelectAllToggle={
                  multiSelectEnabled
                    ? () => {
                        assetSelection.handleSelectAll(filteredResults);
                      }
                    : undefined
                }
                error={
                  error
                    ? {
                        status: error.apiResponse?.status || error.name,
                        message: error.apiResponse?.message || error.message,
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
                    onFilterChange={onFilterChange}
                    onSectionToggle={onSectionToggle}
                  />
                </>
              }
            />
          </RightSidebar>
        </Box>

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={assetOperations.isDeleteModalOpen}
          onClose={assetOperations.handleDeleteCancel}
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
            <Button onClick={assetOperations.handleDeleteCancel}>Cancel</Button>
            <Button
              onClick={assetOperations.handleDeleteConfirm}
              color="error"
              autoFocus
            >
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        {/* API Status Modal for bulk download */}
        <ApiStatusModal
          open={assetSelection.modalState.open}
          onClose={assetSelection.handleModalClose}
          status={
            assetSelection.modalState.status as "loading" | "error" | "success"
          }
          action={assetSelection.modalState.action}
          message={assetSelection.modalState.message}
        />
      </>
    </RightSidebarProvider>
  );
};

export default SearchPagePresentation;
