import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  LinearProgress,
  alpha,
  useTheme,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  CircularProgress,
  Snackbar,
  Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import { formatFileSize } from "@/utils/fileSize";
import { formatDate } from "@/utils/dateFormat";
import ModularUnifiedResultsView from "@/components/search/ModularUnifiedResultsView";
import {
  useConnectorAssets,
  type AssetItem,
  type ConnectorAssetsResponse,
} from "@/api/hooks/useConnectorAssets";
import { useAssetOperations } from "@/hooks/useAssetOperations";
import {
  useGetFavorites,
  useAddFavorite,
  useRemoveFavorite,
} from "@/api/hooks/useFavorites";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";

interface AssetExplorerProps {
  connectorId: string;
  bucketName?: string;
}

const AssetExplorer: React.FC<AssetExplorerProps> = ({
  connectorId,
  bucketName,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState("createdAt");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [assetType, setAssetType] = useState<string | undefined>(undefined);

  // UI state
  const [viewMode, setViewMode] = useState<"card" | "table">("card");
  const [cardSize, setCardSize] = useState<"small" | "medium" | "large">(
    "medium",
  );
  const [aspectRatio, setAspectRatio] = useState<
    "vertical" | "square" | "horizontal"
  >("square");
  const [thumbnailScale, setThumbnailScale] = useState<"fit" | "fill">("fit");
  const [showMetadata, setShowMetadata] = useState(true);
  const [groupByType, setGroupByType] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([]);

  // Fetch bucket assets using search endpoint with bucket filter
  const {
    data: searchResponse,
    isLoading,
    error,
  } = useConnectorAssets({
    bucketName: bucketName || "",
    page,
    pageSize,
    sortBy,
    sortDirection,
    assetType,
  }) as {
    data: ConnectorAssetsResponse | undefined;
    isLoading: boolean;
    error: any;
  };

  // Favorites functionality
  const { data: favorites, isLoading: isFavoritesLoading } =
    useGetFavorites("ASSET");
  const { mutate: addFavorite } = useAddFavorite();
  const { mutate: removeFavorite } = useRemoveFavorite();

  // Check if an asset is favorited
  const isAssetFavorited = (assetId: string) => {
    if (!favorites) return false;
    return favorites.some((favorite) => favorite.itemId === assetId);
  };

  // Handle favorite toggle
  const handleFavoriteToggle = (
    asset: AssetItem,
    event: React.MouseEvent<HTMLElement>,
  ) => {
    event.stopPropagation();
    console.log("handleFavoriteToggle called with asset:", asset.InventoryID);

    const assetId = asset.InventoryID;
    const isFavorited = isAssetFavorited(assetId);
    console.log("Current favorite status:", isFavorited);

    try {
      if (isFavorited) {
        console.log("Removing favorite:", assetId);
        removeFavorite({ itemId: assetId, itemType: "ASSET" });
      } else {
        console.log("Adding favorite:", assetId);
        addFavorite({
          itemId: assetId,
          itemType: "ASSET",
          metadata: {
            name: asset.DigitalSourceAsset.MainRepresentation.StorageInfo
              .PrimaryLocation.ObjectKey.Name,
            assetType: asset.DigitalSourceAsset.Type,
            thumbnailUrl: asset.thumbnailUrl || "",
            format: asset.DigitalSourceAsset.MainRepresentation.Format,
          },
        });
      }
    } catch (error) {
      console.error("Error toggling favorite:", error);
    }
  };

  // Asset operations
  const {
    handleDeleteClick,
    handleMenuOpen,
    handleStartEditing,
    handleNameChange,
    handleNameEditComplete,
    handleMenuClose,
    handleAction,
    handleDeleteConfirm,
    handleDeleteCancel,
    editingAssetId,
    editedName,
    isDeleteModalOpen,
    menuAnchorEl,
    selectedAsset,
    alert,
    handleAlertClose,
    isLoading: assetOperationsLoading,
    renamingAssetId,
  } = useAssetOperations<AssetItem>();

  // Card fields configuration
  const [cardFields, setCardFields] = useState([
    { id: "name", label: "Object Name", visible: true },
    { id: "type", label: "Type", visible: true },
    { id: "format", label: "Format", visible: true },
    { id: "size", label: "Size", visible: false },
    { id: "createdAt", label: "Date Created", visible: true },
  ]);

  // Table columns configuration
  const [columns, setColumns] = useState<AssetTableColumn<AssetItem>[]>([
    {
      id: "name",
      label: "Name",
      visible: true,
      minWidth: 200,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .ObjectKey.Name,
      cell: (info) => info.getValue() as string,
      sortable: true,
    },
    {
      id: "type",
      label: "Type",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) => row.DigitalSourceAsset.Type,
      sortable: true,
    },
    {
      id: "format",
      label: "Format",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.Format,
      sortable: true,
    },
    {
      id: "size",
      label: "Size",
      visible: true,
      minWidth: 100,
      accessorFn: (row: AssetItem) =>
        row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation
          .FileInfo.Size,
      cell: (info) => formatFileSize(info.getValue() as number),
      sortable: true,
    },
    {
      id: "date",
      label: "Date Created",
      visible: true,
      minWidth: 150,
      accessorFn: (row: AssetItem) => row.DigitalSourceAsset.CreateDate,
      cell: (info) => formatDate(info.getValue() as string),
      sortable: true,
    },
  ]);

  // Handle asset click to navigate to detail page
  const handleAssetClick = useCallback(
    (asset: AssetItem) => {
      const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
      // Special case for audio to use singular form
      const pathPrefix = assetType === "audio" ? "/audio/" : `/${assetType}s/`;
      navigate(`${pathPrefix}${asset.InventoryID}`, {
        state: {
          assetType: asset.DigitalSourceAsset.Type,
          connectorId,
          bucketName,
        },
      });
    },
    [navigate, connectorId, bucketName],
  );

  // Handle view mode change
  const handleViewModeChange = (
    _: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
  ) => {
    if (newMode) setViewMode(newMode);
  };

  // Handle card field toggle
  const handleCardFieldToggle = (fieldId: string) => {
    setCardFields((prev) =>
      prev.map((field) =>
        field.id === fieldId ? { ...field, visible: !field.visible } : field,
      ),
    );
  };

  // Handle column toggle
  const handleColumnToggle = (columnId: string) => {
    setColumns((prev) =>
      prev.map((column) =>
        column.id === columnId
          ? { ...column, visible: !column.visible }
          : column,
      ),
    );
  };

  // Handle page change
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  // Handle page size change
  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1); // Reset to first page when changing page size
  };

  // Handle sort change
  const handleSortChange = (newSorting: SortingState) => {
    setSorting(newSorting);

    if (newSorting.length > 0) {
      const { id, desc } = newSorting[0];
      setSortBy(id);
      setSortDirection(desc ? "desc" : "asc");
    }
  };

  // If there's no bucket selected, show a message
  if (!bucketName) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
          p: 3,
          color: "text.secondary",
        }}
      >
        <Typography variant="h6">
          {t("assetExplorer.noConnectorSelected")}
        </Typography>
      </Box>
    );
  }

  // If there are no assets in the bucket, show a message
  const hasNoAssets =
    !isLoading &&
    searchResponse?.data?.results &&
    searchResponse.data.results.length === 0;

  if (hasNoAssets) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
          p: 3,
          color: "text.secondary",
        }}
      >
        <FolderOpenIcon
          sx={{
            fontSize: 64,
            mb: 2,
            color: alpha(theme.palette.text.secondary, 0.5),
          }}
        />
        <Typography variant="h6">{t("assetExplorer.noAssetsFound")}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          {t("assetExplorer.noIndexedAssets", { bucketName })}
        </Typography>
      </Box>
    );
  }

  // Don't show content while loading initial data
  if (
    isLoading &&
    (!searchResponse ||
      searchResponse?.data == null ||
      !searchResponse?.data?.results)
  ) {
    return (
      <Box
        sx={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          p: 2,
        }}
      >
        <CircularProgress size={40} />
        <Typography variant="body1" sx={{ mt: 2 }}>
          {t("assetExplorer.loadingAssets")}
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "100%", overflow: "auto", p: 2 }}>
      {isLoading && (
        <LinearProgress
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
          }}
        />
      )}

      {/* Only show the results view when we have data or after initial loading */}
      {(!isLoading ||
        (searchResponse &&
          searchResponse?.data != null &&
          searchResponse?.data?.results)) && (
        <Box
          sx={{
            "& h1": {
              display: "none !important",
            },
            "& > div > div:first-of-type": {
              mb: 0,
            },
          }}
        >
          <ModularUnifiedResultsView
            results={searchResponse?.data?.results || []}
            searchMetadata={{
              totalResults:
                searchResponse?.data?.searchMetadata?.totalResults || 0,
              page,
              pageSize,
            }}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
            searchTerm=""
            groupByType={groupByType}
            onGroupByTypeChange={setGroupByType}
            viewMode={viewMode}
            onViewModeChange={handleViewModeChange}
            cardSize={cardSize}
            onCardSizeChange={setCardSize}
            aspectRatio={aspectRatio}
            onAspectRatioChange={setAspectRatio}
            thumbnailScale={thumbnailScale}
            onThumbnailScaleChange={setThumbnailScale}
            showMetadata={showMetadata}
            onShowMetadataChange={setShowMetadata}
            sorting={sorting}
            onSortChange={handleSortChange}
            cardFields={cardFields}
            onCardFieldToggle={handleCardFieldToggle}
            columns={columns}
            onColumnToggle={handleColumnToggle}
            onAssetClick={handleAssetClick}
            onDeleteClick={handleDeleteClick}
            onMenuClick={handleMenuOpen}
            onEditClick={handleStartEditing}
            onEditNameChange={handleNameChange}
            onEditNameComplete={handleNameEditComplete}
            editingAssetId={editingAssetId}
            editedName={editedName}
            isAssetFavorited={isAssetFavorited}
            onFavoriteToggle={handleFavoriteToggle}
            error={
              error
                ? {
                    status: error.name || "Error",
                    message: error.message || "Failed to load assets",
                  }
                : undefined
            }
            isLoading={isLoading || isFavoritesLoading}
            isRenaming={assetOperationsLoading.rename}
            renamingAssetId={renamingAssetId}
          />
        </Box>
      )}

      {/* Show loading indicator during initial load */}
      {isLoading &&
        (!searchResponse ||
          searchResponse?.data == null ||
          !searchResponse?.data?.results) && (
          <Box
            sx={{
              height: "100%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              p: 2,
            }}
          >
            <CircularProgress size={40} />
            <Typography variant="body1" sx={{ mt: 2 }}>
              {t("assetExplorer.loadingAssets")}
            </Typography>
          </Box>
        )}

      {/* Asset Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
        MenuListProps={{
          "aria-labelledby": selectedAsset
            ? `asset-menu-button-${selectedAsset.InventoryID}`
            : undefined,
        }}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
        PaperProps={{
          elevation: 0,
          sx: {
            borderRadius: "8px",
            minWidth: 200,
            mt: 1,
            border: (theme) => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            backgroundColor: (theme) => theme.palette.background.paper,
            overflow: "visible",
            position: "fixed",
            zIndex: 1400,
          },
        }}
        slotProps={{
          paper: {
            sx: {
              overflow: "visible",
              position: "fixed",
            },
          },
        }}
      >
        <MenuItem onClick={() => handleAction("rename")}>
          {t("assetExplorer.menu.rename")}
        </MenuItem>
        <MenuItem onClick={() => handleAction("share")}>
          {t("assetExplorer.menu.share")}
        </MenuItem>
        <MenuItem onClick={() => handleAction("download")}>
          {t("assetExplorer.menu.download")}
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
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
            {t("assetExplorer.deleteDialog.description")}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDeleteCancel}
            disabled={assetOperationsLoading.delete}
          >
            {t("assetExplorer.deleteDialog.cancel")}
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            autoFocus
            disabled={assetOperationsLoading.delete}
            startIcon={
              assetOperationsLoading.delete ? (
                <CircularProgress size={16} />
              ) : undefined
            }
          >
            {assetOperationsLoading.delete
              ? t("assetExplorer.deleteDialog.deleting")
              : t("assetExplorer.deleteDialog.confirm")}
          </Button>
        </DialogActions>
      </Dialog>

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
    </Box>
  );
};

export default AssetExplorer;
