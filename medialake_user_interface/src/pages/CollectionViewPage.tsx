import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate } from "react-router-dom";
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
  Snackbar,
  Alert,
  Breadcrumbs,
  Link,
  useTheme,
} from "@mui/material";
import {
  Home as HomeIcon,
  Folder as FolderIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  ChevronLeft,
  ChevronRight,
  AccountTree as CollectionsTreeIcon,
} from "@mui/icons-material";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { CreateCollectionModal } from "@/components/collections/CreateCollectionModal";
import { EditCollectionModal } from "@/components/collections/EditCollectionModal";
import { CollectionTreeView } from "@/components/collections/CollectionTreeView";
import { BulkDeleteDialog } from "@/components/assets/BulkDeleteDialog";
import {
  useAddItemToCollection,
  useGetCollection,
  useGetChildCollections,
  useDeleteCollection,
  useDeleteItemFromCollection,
} from "@/api/hooks/useCollections";
import { useGetCollectionAssets } from "@/api/hooks/useCollections";
import { RightSidebar, RightSidebarProvider } from "../components/common/RightSidebar";
import SearchFilters from "../components/search/SearchFilters";
import AssetResultsView from "../components/shared/AssetResultsView";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import { type ImageItem, type VideoItem, type AudioItem } from "@/types/search/searchResults";
import { type CellContext } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import TabbedSidebar from "../components/common/RightSidebar/TabbedSidebar";
import { useSearchParams } from "react-router-dom";
import ApiStatusModal from "../components/ApiStatusModal";
import { useViewPreferences } from "@/hooks/useViewPreferences";
import { useAssetSelection } from "@/hooks/useAssetSelection";
import { useAssetFavorites } from "@/hooks/useAssetFavorites";
import { getOriginalAssetId } from "@/utils/clipTransformation";

type AssetItem = (ImageItem | VideoItem | AudioItem) & {
  DigitalSourceAsset: {
    Type: string;
  };
  clipBoundary?: {
    startTime?: string;
    endTime?: string;
  };
  addedAt?: string;
  addedBy?: string;
};

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
const DRAWER_WIDTH = 280;
const COLLAPSED_DRAWER_WIDTH = 60;

const CollectionViewPage: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentPage = parseInt(searchParams.get("page") || "1", 10);

  const [pageSize, setPageSize] = useState<number>(
    parseInt(searchParams.get("pageSize") || DEFAULT_PAGE_SIZE.toString(), 10)
  );

  // Sidebar collapse state
  const [isTreeCollapsed, setIsTreeCollapsed] = useState(false);

  // Add to Collection state
  const [addToCollectionModalOpen, setAddToCollectionModalOpen] = useState(false);
  const [selectedAssetForCollection, setSelectedAssetForCollection] = useState<AssetItem | null>(
    null
  );
  const addItemToCollectionMutation = useAddItemToCollection();
  const deleteItemMutation = useDeleteItemFromCollection();

  // Collection Edit/Delete state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isCreateSubCollectionOpen, setIsCreateSubCollectionOpen] = useState(false);
  const [collectionAlert, setCollectionAlert] = useState<{
    severity: "success" | "error" | "info" | "warning";
    message: string;
  } | null>(null);

  const deleteCollectionMutation = useDeleteCollection();

  // Get collection details
  const { data: collectionResponse, isLoading: isLoadingCollection } = useGetCollection(id!);
  const collection = collectionResponse?.data;

  // Get collection assets using the new hook
  const {
    data: assetsResponse,
    isLoading,
    isFetching,
    error,
  } = useGetCollectionAssets(id!, {
    page: currentPage,
    pageSize: pageSize,
  });

  // Extract assets data
  const assetsData = assetsResponse?.data;
  const assets = assetsData?.results || [];
  const searchMetadata = assetsData?.searchMetadata;

  // Get child collections (not currently used but kept for future feature)
  useGetChildCollections(id!);

  // Get ancestors from collection data (now included in collection response)
  const ancestors = collection?.ancestors || [];

  // Use custom hooks for view preferences, asset selection, and favorites
  const viewPreferences = useViewPreferences({
    initialViewMode: "card",
    initialCardSize: "medium",
    initialAspectRatio: "square",
    initialThumbnailScale: "fit",
    initialShowMetadata: true,
    initialGroupByType: false,
  });

  const [editingAssetId, setEditingAssetId] = useState<string>();
  const [editedName, setEditedName] = useState<string>();

  // Asset accessors for hooks
  const getAssetId = useCallback((asset: AssetItem) => {
    // Create unique key combining InventoryID with clip boundary or timestamp
    // This prevents duplicate keys when the same asset appears multiple times
    // (e.g., once as full file, once as clip)
    const baseId = asset.InventoryID;
    const clipBoundary = asset.clipBoundary;

    if (clipBoundary && clipBoundary.startTime && clipBoundary.endTime) {
      // For clips, create key like: assetId#CLIP#startTime_endTime
      const sanitizedStart = clipBoundary.startTime.replace(/:/g, "-");
      const sanitizedEnd = clipBoundary.endTime.replace(/:/g, "-");
      return `${baseId}#CLIP#${sanitizedStart}_${sanitizedEnd}`;
    } else {
      // For full files, use addedAt to ensure uniqueness
      // (in case the same full file is added multiple times)
      return `${baseId}#FULL#${asset.addedAt}`;
    }
  }, []);
  const getAssetName = useCallback(
    (asset: AssetItem) =>
      asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
    []
  );
  const getAssetType = useCallback((asset: AssetItem) => asset.DigitalSourceAsset.Type, []);
  const getAssetThumbnail = useCallback((asset: AssetItem) => asset.thumbnailUrl || "", []);
  const getAssetProxy = useCallback((asset: AssetItem) => asset.proxyUrl || "", []);

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
    handleDeleteConfirm,
    handleDeleteCancel,
    handleDownloadClick,
    editingAssetId: currentEditingAssetId,
    editedName: currentEditedName,
    isDeleteModalOpen,
    alert,
    handleAlertClose,
    isLoading: assetOperationsLoading,
    renamingAssetId,
    deleteModalState,
    handleDeleteModalClose,
  } = useAssetOperations<AssetItem>();
  const handleAssetClick = useCallback(
    (asset: AssetItem) => {
      const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
      // Special case for audio to use singular form
      const pathPrefix = assetType === "audio" ? "/audio/" : `/${assetType}s/`;
      // Always use the original asset ID, not the clip ID
      const originalAssetId = getOriginalAssetId(asset);
      navigate(`${pathPrefix}${originalAssetId}`, {
        state: {
          assetType: asset.DigitalSourceAsset.Type,
          searchTerm: "",
          asset: asset,
        },
      });
    },
    [navigate, collection?.name]
  );

  // Handle Remove from Collection click
  const handleRemoveFromCollectionClick = useCallback(
    (asset: AssetItem, event: React.MouseEvent<HTMLElement>) => {
      console.log("CollectionViewPage: Remove from Collection clicked!", asset);
      event.stopPropagation();

      // Use the collectionItemId (SK) if available, otherwise fall back to InventoryID
      // The collectionItemId is the SK from DynamoDB (e.g., "ITEM#uuid" or "ASSET#uuid")
      const itemId = (asset as any).collectionItemId || asset.InventoryID;

      console.log("CollectionViewPage: Attempting to delete", {
        collectionId: id,
        itemId,
        hasCollectionItemId: !!(asset as any).collectionItemId,
        inventoryID: asset.InventoryID,
      });

      if (id && itemId) {
        deleteItemMutation.mutate({ collectionId: id, itemId });
      }
    },
    [id, deleteItemMutation]
  );

  // Handle actually adding the asset to a collection
  const handleAddToCollection = useCallback(
    async (collectionId: string) => {
      if (!selectedAssetForCollection) return;

      const assetId = getOriginalAssetId(selectedAssetForCollection);

      // Check if this asset has clip data
      const clipData = (selectedAssetForCollection as any).clipData;
      let clipBoundary = undefined;

      if (clipData && clipData.start_timecode && clipData.end_timecode) {
        clipBoundary = {
          startTime: clipData.start_timecode,
          endTime: clipData.end_timecode,
        };
      }

      await addItemToCollectionMutation.mutateAsync({
        collectionId,
        data: {
          assetId: assetId,
          clipBoundary: clipBoundary,
        },
      });
    },
    [selectedAssetForCollection, addItemToCollectionMutation]
  );

  // Handle collection selection from tree (soft navigation)
  const handleCollectionSelect = useCallback(
    (collectionId: string) => {
      // Use navigate without replace to allow back button
      navigate(`/collections/${collectionId}/view`);
    },
    [navigate]
  );

  // Toggle sidebar
  const toggleTreeSidebar = () => {
    setIsTreeCollapsed(!isTreeCollapsed);
  };

  // Edit collection handlers
  const handleEditClick = () => {
    setIsEditModalOpen(true);
  };

  const handleEditModalClose = () => {
    setIsEditModalOpen(false);
  };

  // Delete collection handlers
  const handleCollectionDeleteClick = () => {
    setIsDeleteDialogOpen(true);
  };

  const handleCollectionDeleteClose = () => {
    setIsDeleteDialogOpen(false);
  };

  const handleCollectionDeleteConfirm = async () => {
    if (!id) return;

    try {
      await deleteCollectionMutation.mutateAsync(id);
      setCollectionAlert({
        severity: "success",
        message: t("common.messages.collectionDeletedSuccessfully"),
      });
      handleCollectionDeleteClose();
      // Navigate to collections list after successful deletion
      setTimeout(() => {
        navigate("/collections");
      }, 1000);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : t("collectionsPage.collectionDeleteFailed", "Failed to delete collection");
      setCollectionAlert({
        severity: "error",
        message: errorMessage,
      });
      handleCollectionDeleteClose();
    }
  };

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
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
      cell: (info: CellContext<AssetItem, unknown>) => info.getValue() as string,
      sortable: true,
      sortingFn: (rowA, rowB) =>
        rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.localeCompare(
          rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey
            .Name
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
        rowA.original.DigitalSourceAsset.Type.localeCompare(rowB.original.DigitalSourceAsset.Type),
    },
    {
      id: "format",
      label: "Format",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) => row.DigitalSourceAsset.MainRepresentation.Format,
      sortable: true,
      sortingFn: (rowA, rowB) =>
        rowA.original.DigitalSourceAsset.MainRepresentation.Format.localeCompare(
          rowB.original.DigitalSourceAsset.MainRepresentation.Format
        ),
    },
    {
      id: "size",
      label: "Size",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
      cell: (info: CellContext<AssetItem, unknown>) => formatFileSize(info.getValue() as number),
      sortable: true,
      sortingFn: (rowA, rowB) => {
        const a =
          rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo
            .Size;
        const b =
          rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo
            .Size;
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
        const a = new Date(rowA.original.DigitalSourceAsset.CreateDate).getTime();
        const b = new Date(rowB.original.DigitalSourceAsset.CreateDate).getTime();
        return a - b;
      },
    },
  ]);

  const handleColumnToggle = (columnId: string) => {
    setColumns((prev) =>
      prev.map((column) =>
        column.id === columnId ? { ...column, visible: !column.visible } : column
      )
    );
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

  const filteredResults =
    assets?.filter((item) => {
      const isImage = item.DigitalSourceAsset.Type === "Image" && filters.mediaTypes.images;
      const isVideo = item.DigitalSourceAsset.Type === "Video" && filters.mediaTypes.videos;
      const isAudio = item.DigitalSourceAsset.Type === "Audio" && filters.mediaTypes.audio;

      // Time-based filtering
      const createdAt = new Date(item.DigitalSourceAsset.CreateDate);
      const now = new Date();
      const timeDiff = now.getTime() - createdAt.getTime();
      const isRecent = filters.time.recent && timeDiff <= 24 * 60 * 60 * 1000;
      const isLastWeek = filters.time.lastWeek && timeDiff <= 7 * 24 * 60 * 60 * 1000;
      const isLastMonth = filters.time.lastMonth && timeDiff <= 30 * 24 * 60 * 60 * 1000;
      const isLastYear = filters.time.lastYear && timeDiff <= 365 * 24 * 60 * 60 * 1000;

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

  const [expandedSections, setExpandedSections] = useState({
    mediaTypes: true,
    time: true,
    status: true,
  });

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

  const handlePageChange = (newPage: number) => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev);
      newParams.set("page", newPage.toString());
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

  const renderCardField = useCallback((fieldId: string, asset: AssetItem) => {
    switch (fieldId) {
      case "name":
        return getAssetName(asset);
      case "type":
        return getAssetType(asset);
      case "size":
        return formatFileSize(
          asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size
        );
      case "date":
        return formatDate(asset.DigitalSourceAsset.CreateDate);
      default:
        return "";
    }
  }, []);

  // Show error if collection not found and not loading
  if (!isLoadingCollection && !collection) {
    return (
      <Box sx={{ p: 4 }}>
        <Typography variant="h6" color="error">
          Collection not found
        </Typography>
      </Box>
    );
  }

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
          {/* Show loading indicator for both initial load and navigation */}
          {(isLoadingCollection || isFetching) && (
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

          {/* Left Sidebar - Collection Tree (Collapsible) */}
          <Box
            sx={{
              width: isTreeCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
              minWidth: isTreeCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
              flexShrink: 0,
              height: "100vh",
              position: "sticky",
              top: 0,
              display: "flex",
              flexDirection: "column",
              backgroundColor: "background.paper",
              borderRadius: 2,
              transition: theme.transitions.create(["width", "min-width"], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
              overflow: "visible",
              zIndex: 1,
              mr: 3,
            }}
          >
            {/* Collapse/Expand Button */}
            <Button
              onClick={toggleTreeSidebar}
              sx={{
                position: "absolute",
                right: -16,
                top: "50%",
                transform: "translateY(-50%)",
                minWidth: "32px",
                width: "32px",
                height: "32px",
                bgcolor: "background.paper",
                borderRadius: "8px",
                boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid",
                borderColor: "divider",
                zIndex: 1200,
                padding: 0,
                "&:hover": {
                  bgcolor: "background.paper",
                  boxShadow: "0px 6px 12px rgba(0, 0, 0, 0.2)",
                },
              }}
            >
              {isTreeCollapsed ? (
                <ChevronRight sx={{ fontSize: 20 }} />
              ) : (
                <ChevronLeft sx={{ fontSize: 20 }} />
              )}
            </Button>

            {isTreeCollapsed ? (
              // Collapsed view - show only the icon, centered
              <Box
                sx={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  pl: 0,
                  pr: 2,
                }}
              >
                <CollectionsTreeIcon
                  sx={{
                    color: (theme) => theme.palette.primary.main,
                    fontSize: 24,
                  }}
                />
              </Box>
            ) : (
              // Expanded view - show tree
              <Box
                sx={{
                  flexGrow: 1,
                  overflowY: "auto",
                  overflowX: "hidden",
                }}
              >
                <CollectionTreeView
                  currentCollectionId={id}
                  onCollectionSelect={handleCollectionSelect}
                />
              </Box>
            )}
          </Box>

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
            {/* Breadcrumbs with Action Buttons */}
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 3,
              }}
            >
              <Breadcrumbs aria-label="breadcrumb">
                <Link
                  underline="hover"
                  color="inherit"
                  href="/"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/");
                  }}
                  sx={{ display: "flex", alignItems: "center" }}
                >
                  <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                  Home
                </Link>
                <Link
                  underline="hover"
                  color="inherit"
                  href="/collections"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/collections");
                  }}
                  sx={{ display: "flex", alignItems: "center" }}
                >
                  <FolderIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                  Collections
                </Link>
                {/* Show full path from ancestors */}
                {ancestors.slice(0, -1).map((ancestor) => (
                  <Link
                    key={ancestor.id}
                    underline="hover"
                    color="inherit"
                    href={`/collections/${ancestor.id}/view`}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(`/collections/${ancestor.id}/view`);
                    }}
                    sx={{ display: "flex", alignItems: "center" }}
                  >
                    <FolderIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                    {ancestor.name}
                  </Link>
                ))}
                <Typography color="text.primary" sx={{ display: "flex", alignItems: "center" }}>
                  <FolderIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                  {collection?.name || "Loading..."}
                </Typography>
              </Breadcrumbs>

              {/* Action Buttons */}
              {collection && (
                <Box sx={{ display: "flex", gap: 2 }}>
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setIsCreateSubCollectionOpen(true)}
                    size="small"
                  >
                    Create Sub-Collection
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<EditIcon />}
                    onClick={handleEditClick}
                    size="small"
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={handleCollectionDeleteClick}
                    size="small"
                  >
                    Delete
                  </Button>
                </Box>
              )}
            </Box>

            {isLoading || isFetching ? (
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
                <LinearProgress sx={{ width: "100%", maxWidth: 400 }} />
                <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
                  Loading assets...
                </Typography>
              </Box>
            ) : filteredResults.length > 0 && searchMetadata && !error ? (
              <AssetResultsView
                results={filteredResults}
                searchMetadata={{
                  totalResults: searchMetadata?.totalResults || 0,
                  page: currentPage,
                  pageSize: pageSize,
                }}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
                searchTerm=""
                title=""
                isSemantic={false}
                groupByType={viewPreferences.groupByType}
                onGroupByTypeChange={viewPreferences.handleGroupByTypeChange}
                viewMode={viewPreferences.viewMode}
                onViewModeChange={viewPreferences.handleViewModeChange}
                cardSize={viewPreferences.cardSize}
                onCardSizeChange={viewPreferences.handleCardSizeChange}
                aspectRatio={viewPreferences.aspectRatio}
                onAspectRatioChange={viewPreferences.handleAspectRatioChange}
                thumbnailScale={viewPreferences.thumbnailScale}
                onThumbnailScaleChange={viewPreferences.handleThumbnailScaleChange}
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
                onDownloadClick={handleDownloadClick}
                onAddToCollectionClick={handleRemoveFromCollectionClick}
                showRemoveButton={true}
                onEditClick={handleStartEditing}
                onEditNameChange={handleNameChange}
                onEditNameComplete={handleNameEditComplete}
                editingAssetId={editingAssetId}
                editedName={editedName}
                isAssetFavorited={assetFavorites.isAssetFavorited}
                onFavoriteToggle={assetFavorites.handleFavoriteToggle}
                isAssetSelected={(assetId: string) =>
                  assetSelection.selectedAssetIds.includes(assetId)
                }
                onSelectToggle={assetSelection.handleSelectToggle}
                hasSelectedAssets={assetSelection.selectedAssets.length > 0}
                selectAllState={assetSelection.getSelectAllState(filteredResults)}
                onSelectAllToggle={() => {
                  assetSelection.handleSelectAll(filteredResults);
                }}
                isRenaming={assetOperationsLoading.rename}
                renamingAssetId={renamingAssetId}
                error={
                  error
                    ? {
                        status: (error as any).apiResponse?.status || error.name,
                        message: (error as any).apiResponse?.message || error.message,
                      }
                    : undefined
                }
                isLoading={isLoading || isFetching}
                getAssetId={getAssetId}
                getAssetName={getAssetName}
                getAssetType={getAssetType}
                getAssetThumbnail={getAssetThumbnail}
                getAssetProxy={getAssetProxy}
                renderCardField={renderCardField}
              />
            ) : (
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
                  <FolderIcon
                    sx={{
                      fontSize: 64,
                      color: "text.secondary",
                      mb: 2,
                    }}
                  />
                  <Typography variant="h5" color="text.primary" gutterBottom>
                    No assets found
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    This collection doesn't contain any assets yet
                  </Typography>
                </Paper>
              </Box>
            )}
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
              isDeleteLoading={assetSelection.isDeleteLoading}
              filterComponent={
                <SearchFilters
                  filters={filters}
                  expandedSections={expandedSections}
                  onFilterChange={handleFilterChange}
                  onSectionToggle={handleSectionToggle}
                />
              }
            />
          </RightSidebar>
        </Box>

        {/* Delete Asset Confirmation Dialog */}
        <Dialog
          open={isDeleteModalOpen}
          onClose={handleDeleteCancel}
          aria-labelledby="delete-dialog-title"
          aria-describedby="delete-dialog-description"
        >
          <DialogTitle id="delete-dialog-title">
            {t("assetExplorer.deleteDialog.title")}
          </DialogTitle>
          <DialogContent>
            <DialogContentText id="delete-dialog-description">
              Are you sure you want to delete this asset? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel}>{t("common.cancel")}</Button>
            <Button onClick={handleDeleteConfirm} color="error" autoFocus>
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        {/* Create Sub-Collection Modal */}
        <CreateCollectionModal
          open={isCreateSubCollectionOpen}
          onClose={() => setIsCreateSubCollectionOpen(false)}
          defaultParentId={id}
        />

        {/* Edit Collection Modal */}
        <EditCollectionModal
          open={isEditModalOpen}
          onClose={handleEditModalClose}
          collection={collection || null}
        />

        {/* Delete Collection Confirmation Dialog */}
        <Dialog
          open={isDeleteDialogOpen}
          onClose={handleCollectionDeleteClose}
          aria-labelledby="delete-collection-dialog-title"
          aria-describedby="delete-collection-dialog-description"
        >
          <DialogTitle id="delete-collection-dialog-title">
            {t("collectionsPage.dialogs.deleteTitle")}
          </DialogTitle>
          <DialogContent>
            <DialogContentText id="delete-collection-dialog-description">
              Are you sure you want to delete this collection? This will permanently delete the
              collection and remove all items from it. This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCollectionDeleteClose}>{t("common.cancel")}</Button>
            <Button
              onClick={handleCollectionDeleteConfirm}
              color="error"
              variant="contained"
              disabled={deleteCollectionMutation.isPending}
            >
              {deleteCollectionMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Bulk Delete Confirmation Dialog */}
        <BulkDeleteDialog
          open={assetSelection.isDeleteDialogOpen}
          onClose={assetSelection.handleDeleteDialogClose}
          onConfirm={assetSelection.handleConfirmDelete}
          selectedCount={assetSelection.selectedAssets.length}
          confirmationText={assetSelection.deleteConfirmationText}
          onConfirmationTextChange={assetSelection.setDeleteConfirmationText}
          isLoading={assetSelection.isDeleteLoading}
        />

        {/* API Status Modal for bulk operations */}
        <ApiStatusModal
          open={assetSelection.modalState.open}
          onClose={assetSelection.handleModalClose}
          status={assetSelection.modalState.status}
          action={assetSelection.modalState.action}
          message={assetSelection.modalState.message}
        />

        {/* API Status Modal for single asset delete operation */}
        <ApiStatusModal
          open={deleteModalState.open}
          onClose={handleDeleteModalClose}
          status={deleteModalState.status}
          action={deleteModalState.action}
          message={deleteModalState.message}
        />

        {/* Asset operation alerts */}
        <Snackbar
          open={!!alert}
          autoHideDuration={6000}
          onClose={handleAlertClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        >
          <Alert onClose={handleAlertClose} severity={alert?.severity} sx={{ width: "100%" }}>
            {alert?.message}
          </Alert>
        </Snackbar>

        {/* Collection operation alerts */}
        <Snackbar
          open={!!collectionAlert}
          autoHideDuration={6000}
          onClose={() => setCollectionAlert(null)}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        >
          <Alert
            onClose={() => setCollectionAlert(null)}
            severity={collectionAlert?.severity}
            sx={{ width: "100%" }}
          >
            {collectionAlert?.message}
          </Alert>
        </Snackbar>

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
    </RightSidebarProvider>
  );
};

export default CollectionViewPage;
