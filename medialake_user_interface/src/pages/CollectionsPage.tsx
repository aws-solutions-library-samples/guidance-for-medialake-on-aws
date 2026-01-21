import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  Typography,
  useTheme,
  alpha,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Card,
  CardContent,
  CardActions,
  Snackbar,
  Alert,
  TextField,
  Tabs,
  Tab,
  Tooltip,
  Badge,
} from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Add as AddIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  CalendarToday as CalendarIcon,
  AccountTree as TreeIcon,
  PhotoLibrary as PhotoLibraryIcon,
  Work,
  Campaign,
  Assignment,
  Archive,
  Label,
  Movie,
  Collections as CollectionsIcon,
  Dashboard,
  Storage,
  Inventory,
  Category,
  BookmarkBorder,
  LocalOffer,
  Share as ShareIcon,
  People as PeopleIcon,
  PersonOutline as PersonIcon,
} from "@mui/icons-material";
import { PageHeader, PageContent } from "@/components/common/layout";
import { RefreshButton } from "@/components/common";
import {
  useGetCollections,
  useGetCollectionsSharedWithMe,
  useGetCollectionsSharedByMe,
  useDeleteCollection,
  useUpdateCollection,
  useGetCollectionTypes,
  type Collection,
} from "../api/hooks/useCollections";
import { CreateCollectionModal } from "../components/collections/CreateCollectionModal";
import { ShareManagementModal } from "../components/collections/ShareManagementModal";
import { formatDate } from "@/utils/dateFormat";

type FilterTab = "all" | "myCollections" | "sharedWithMe" | "sharedByMe";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <FolderIcon />,
  FolderOpen: <FolderOpenIcon />,
  Work: <Work />,
  Campaign: <Campaign />,
  Assignment: <Assignment />,
  Archive: <Archive />,
  PhotoLibrary: <PhotoLibraryIcon />,
  Label: <Label />,
  Movie: <Movie />,
  Collections: <CollectionsIcon />,
  Dashboard: <Dashboard />,
  Storage: <Storage />,
  Inventory: <Inventory />,
  Category: <Category />,
  BookmarkBorder: <BookmarkBorder />,
  LocalOffer: <LocalOffer />,
};

const CollectionsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [editedDescription, setEditedDescription] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [alert, setAlert] = useState<{
    message: string;
    severity: "success" | "error";
  } | null>(null);

  // Get filter from URL params
  const filterParam = searchParams.get("filter") as FilterTab | null;
  const activeTab: FilterTab = filterParam || "all";

  // API hooks
  const { data: collectionsResponse, isLoading, error, refetch } = useGetCollections();
  const { data: sharedWithMeResponse, isLoading: isLoadingSharedWithMe } =
    useGetCollectionsSharedWithMe();
  const { data: sharedByMeResponse, isLoading: isLoadingSharedByMe } =
    useGetCollectionsSharedByMe();
  const { data: collectionTypesResponse, isLoading: isLoadingTypes } = useGetCollectionTypes();
  const deleteCollectionMutation = useDeleteCollection();
  const updateCollectionMutation = useUpdateCollection();

  const allCollections = collectionsResponse?.data || [];
  const sharedWithMeCollections = sharedWithMeResponse?.data || [];
  const sharedByMeCollections = sharedByMeResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: FilterTab) => {
    if (newValue === "all") {
      searchParams.delete("filter");
    } else {
      searchParams.set("filter", newValue);
    }
    setSearchParams(searchParams);
  };

  // Handle share button click
  const handleShareClick = (collection: Collection) => {
    setSelectedCollection(collection);
    setShareModalOpen(true);
  };

  const handleShareModalClose = () => {
    setShareModalOpen(false);
    setSelectedCollection(null);
  };

  // Helper to get icon and color for a collection
  const getCollectionStyle = (collection: Collection) => {
    if (!collection.collectionTypeId || isLoadingTypes) {
      return {
        icon: <FolderIcon />,
        color: theme.palette.primary.main,
        borderColor: "divider",
      };
    }

    const collectionType = collectionTypes.find((type) => type.id === collection.collectionTypeId);

    if (!collectionType) {
      return {
        icon: <FolderIcon />,
        color: theme.palette.primary.main,
        borderColor: "divider",
      };
    }

    const iconComponent =
      collectionType.icon && ICON_MAP[collectionType.icon] ? (
        React.cloneElement(ICON_MAP[collectionType.icon], {
          sx: { color: collectionType.color, fontSize: 32, mr: 1.5 },
        })
      ) : (
        <FolderIcon sx={{ color: collectionType.color, fontSize: 32, mr: 1.5 }} />
      );

    return {
      icon: iconComponent,
      color: collectionType.color,
      borderColor: collectionType.color,
    };
  };

  // Calculate total descendant count recursively
  const calculateTotalDescendants = (collectionId: string, collections: Collection[]): number => {
    const children = collections.filter((c) => c.parentId === collectionId);
    let count = children.length;
    children.forEach((child) => {
      count += calculateTotalDescendants(child.id, collections);
    });
    return count;
  };

  // Get filtered collections based on active tab
  const filteredCollections = useMemo(() => {
    let collections: Collection[] = [];

    switch (activeTab) {
      case "myCollections":
        // Only collections owned by the user (not shared with them)
        collections = allCollections.filter((c) => !c.parentId && !c.sharedWithMe);
        break;
      case "sharedWithMe":
        collections = sharedWithMeCollections;
        break;
      case "sharedByMe":
        collections = sharedByMeCollections;
        break;
      case "all":
      default:
        // All root collections the user has access to
        collections = allCollections.filter((c) => !c.parentId);
        break;
    }

    return collections.map((c) => ({
      ...c,
      totalDescendants: calculateTotalDescendants(c.id, allCollections),
    }));
  }, [activeTab, allCollections, sharedWithMeCollections, sharedByMeCollections]);

  // For backwards compatibility
  const rootCollections = filteredCollections;

  // Determine loading state based on active tab
  const isLoadingCollections = useMemo(() => {
    switch (activeTab) {
      case "sharedWithMe":
        return isLoadingSharedWithMe;
      case "sharedByMe":
        return isLoadingSharedByMe;
      default:
        return isLoading;
    }
  }, [activeTab, isLoading, isLoadingSharedWithMe, isLoadingSharedByMe]);

  // Handle refresh
  const handleRefresh = () => {
    setIsRefreshing(true);
    refetch().finally(() => {
      setIsRefreshing(false);
    });
  };

  const handleEditClick = (collection: Collection) => {
    setSelectedCollection(collection);
    setEditedDescription(collection.description || "");
    setEditDialogOpen(true);
  };

  const handleEditSave = async () => {
    if (selectedCollection) {
      try {
        await updateCollectionMutation.mutateAsync({
          id: selectedCollection.id,
          data: {
            description: editedDescription,
          },
        });
        setEditDialogOpen(false);
        setSelectedCollection(null);
        setEditedDescription("");
        setAlert({
          message: t("collectionsPage.collectionUpdated", "Collection updated successfully"),
          severity: "success",
        });
      } catch (error) {
        setAlert({
          message: t("collectionsPage.collectionUpdateFailed", "Failed to update collection"),
          severity: "error",
        });
        setEditDialogOpen(false);
        setSelectedCollection(null);
        setEditedDescription("");
      }
    }
  };

  const handleEditCancel = () => {
    setEditDialogOpen(false);
    setSelectedCollection(null);
    setEditedDescription("");
  };

  const handleDeleteClick = (collection: Collection) => {
    setSelectedCollection(collection);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (selectedCollection) {
      try {
        await deleteCollectionMutation.mutateAsync(selectedCollection.id);
        setDeleteDialogOpen(false);
        setSelectedCollection(null);
        setAlert({
          message: t("collectionsPage.collectionDeleted", "Collection deleted successfully"),
          severity: "success",
        });
      } catch (error) {
        setAlert({
          message: t("collectionsPage.collectionDeleteFailed", "Failed to delete collection"),
          severity: "error",
        });
        setDeleteDialogOpen(false);
        setSelectedCollection(null);
      }
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSelectedCollection(null);
  };

  const handleViewCollection = (collection: Collection) => {
    navigate(`/collections/${collection.id}/view`);
  };

  const handleAlertClose = () => {
    setAlert(null);
  };

  return (
    <Box sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title={t("collectionsPage.title")}
        description={t("collectionsPage.description")}
        action={
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <RefreshButton
              onRefresh={handleRefresh}
              isRefreshing={isRefreshing}
              disabled={isLoading}
              variant="icon"
            />
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateModalOpen(true)}
              sx={{
                borderRadius: 2,
                textTransform: "none",
                px: 3,
                height: 40,
              }}
            >
              {t("collectionsPage.createCollection")}
            </Button>
          </Box>
        }
      />

      {/* Filter Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          aria-label="collection filter tabs"
          sx={{
            "& .MuiTab-root": {
              textTransform: "none",
              minHeight: 48,
            },
          }}
        >
          <Tab
            value="all"
            label={t("collectionsPage.filters.all", "All Collections")}
            icon={<FolderIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
          />
          <Tab
            value="myCollections"
            label={t("collectionsPage.filters.myCollections", "My Collections")}
            icon={<PersonIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
          />
          <Tab
            value="sharedWithMe"
            label={
              <Badge
                badgeContent={sharedWithMeCollections.length}
                color="primary"
                max={99}
                sx={{ "& .MuiBadge-badge": { right: -12, top: 2 } }}
              >
                {t("collectionsPage.filters.sharedWithMe", "Shared With Me")}
              </Badge>
            }
            icon={<PeopleIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
          />
          <Tab
            value="sharedByMe"
            label={
              <Badge
                badgeContent={sharedByMeCollections.length}
                color="secondary"
                max={99}
                sx={{ "& .MuiBadge-badge": { right: -12, top: 2 } }}
              >
                {t("collectionsPage.filters.sharedByMe", "Shared By Me")}
              </Badge>
            }
            icon={<ShareIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
          />
        </Tabs>
      </Box>

      <PageContent isLoading={isLoadingCollections} error={error as Error}>
        {rootCollections.length === 0 ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "400px",
              textAlign: "center",
            }}
          >
            <FolderOpenIcon
              sx={{
                fontSize: 64,
                color: alpha(theme.palette.text.secondary, 0.5),
                mb: 2,
              }}
            />
            <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
              {t("collectionsPage.noCollections", "No collections found")}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t(
                "collectionsPage.createFirstCollection",
                "Create your first collection to get started"
              )}
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateModalOpen(true)}
            >
              {t("collectionsPage.createCollection", "Create Collection")}
            </Button>
          </Box>
        ) : (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(auto-fill, minmax(300px, 1fr))",
                md: "repeat(auto-fill, minmax(350px, 1fr))",
              },
              gap: 3,
              pt: 0.5, // Add padding to prevent clipping on hover
            }}
          >
            {rootCollections.map((collection) => {
              const style = getCollectionStyle(collection);
              return (
                <Card
                  key={collection.id}
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    borderRadius: 3,
                    border: `2px solid`,
                    borderColor: style.borderColor,
                    overflow: "visible", // Prevent clipping on hover
                    transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
                    "&:hover": {
                      transform: "translateY(-4px)",
                      boxShadow: theme.shadows[6],
                      cursor: "pointer",
                    },
                  }}
                  onClick={() => handleViewCollection(collection)}
                >
                  <CardContent
                    sx={{
                      flexGrow: 1,
                      pb: 2,
                      display: "flex",
                      flexDirection: "column",
                    }}
                  >
                    {/* Header with icon and name */}
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "flex-start",
                        mb: 2,
                      }}
                    >
                      {style.icon}
                      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                        <Typography
                          variant="h6"
                          component="h3"
                          sx={{
                            fontWeight: 600,
                            fontSize: "1.1rem",
                            lineHeight: 1.3,
                            mb: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {collection.name}
                        </Typography>
                        {/* Badges: Public/Private, Sharing Status, and Collection Type */}
                        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                          <Chip
                            label={
                              collection.isPublic
                                ? t("collectionsPage.collectionTypes.public", "Public")
                                : t("collectionsPage.collectionTypes.private", "Private")
                            }
                            size="small"
                            icon={collection.isPublic ? <PublicIcon /> : <PrivateIcon />}
                            sx={{
                              height: 22,
                              color: collection.isPublic ? "#2e7d32" : theme.palette.primary.main,
                              bgcolor: collection.isPublic
                                ? "#e8f5e8"
                                : alpha(theme.palette.primary.main, 0.1),
                              border: `1px solid ${
                                collection.isPublic ? "#2e7d32" : theme.palette.primary.main
                              }`,
                              "& .MuiChip-icon": {
                                color: collection.isPublic ? "#2e7d32" : theme.palette.primary.main,
                                fontSize: 14,
                              },
                            }}
                          />
                          {/* Shared with me indicator */}
                          {collection.sharedWithMe && (
                            <Chip
                              label={t("collectionsPage.sharedWithYou", "Shared with you")}
                              size="small"
                              icon={<PeopleIcon />}
                              sx={{
                                height: 22,
                                color: theme.palette.info.main,
                                bgcolor: alpha(theme.palette.info.main, 0.1),
                                border: `1px solid ${theme.palette.info.main}`,
                                "& .MuiChip-icon": {
                                  color: theme.palette.info.main,
                                  fontSize: 14,
                                },
                              }}
                            />
                          )}
                          {/* Shared by me indicator */}
                          {collection.isShared && !collection.sharedWithMe && (
                            <Tooltip
                              title={t(
                                "collectionsPage.sharedWithCount",
                                "Shared with {{count}} people",
                                {
                                  count: collection.shareCount || 0,
                                }
                              )}
                            >
                              <Chip
                                label={
                                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                                    <ShareIcon sx={{ fontSize: 14 }} />
                                    {collection.shareCount || 0}
                                  </Box>
                                }
                                size="small"
                                sx={{
                                  height: 22,
                                  color: theme.palette.secondary.main,
                                  bgcolor: alpha(theme.palette.secondary.main, 0.1),
                                  border: `1px solid ${theme.palette.secondary.main}`,
                                }}
                              />
                            </Tooltip>
                          )}
                          {collection.collectionTypeId &&
                            !isLoadingTypes &&
                            (() => {
                              const collectionType = collectionTypes.find(
                                (type) => type.id === collection.collectionTypeId
                              );
                              return collectionType ? (
                                <Chip
                                  label={collectionType.name}
                                  size="small"
                                  sx={{
                                    height: 22,
                                    color: collectionType.color,
                                    bgcolor: alpha(collectionType.color, 0.1),
                                    border: `1px solid ${collectionType.color}`,
                                    fontWeight: 500,
                                  }}
                                />
                              ) : null;
                            })()}
                        </Box>
                      </Box>
                    </Box>

                    {/* Description - Always render container for consistent spacing */}
                    <Box
                      sx={{
                        minHeight: collection.description ? "40px" : "0px",
                        mb: 2,
                      }}
                    >
                      {collection.description && (
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                          }}
                        >
                          {collection.description}
                        </Typography>
                      )}
                    </Box>

                    {/* Stats */}
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 1,
                        mt: "auto", // Push to bottom
                      }}
                    >
                      {/* Item count */}
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                        }}
                      >
                        <PhotoLibraryIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                        <Typography variant="body2" color="text.secondary">
                          {collection.itemCount} item
                          {collection.itemCount !== 1 ? "s" : ""}
                        </Typography>
                      </Box>

                      {/* Sub-collections count */}
                      {collection.totalDescendants > 0 && (
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                          }}
                        >
                          <TreeIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                          <Typography variant="body2" color="text.secondary">
                            {collection.totalDescendants} sub-collection
                            {collection.totalDescendants !== 1 ? "s" : ""}
                          </Typography>
                        </Box>
                      )}

                      {/* Created date */}
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                        }}
                      >
                        <CalendarIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                        <Typography variant="body2" color="text.secondary">
                          Created: {formatDate(collection.createdAt)}
                        </Typography>
                      </Box>

                      {/* Modified date */}
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                        }}
                      >
                        <CalendarIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                        <Typography variant="body2" color="text.secondary">
                          Modified: {formatDate(collection.updatedAt)}
                        </Typography>
                      </Box>
                    </Box>
                  </CardContent>

                  {/* Actions */}
                  <CardActions
                    sx={{
                      pt: 0,
                      px: 2,
                      pb: 2,
                      display: "flex",
                      justifyContent: "flex-end",
                      gap: 1,
                    }}
                  >
                    {/* Only show Share button for collections user owns */}
                    {!collection.sharedWithMe && (
                      <Button
                        size="small"
                        startIcon={<ShareIcon />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleShareClick(collection);
                        }}
                        sx={{ textTransform: "none" }}
                        color="secondary"
                      >
                        {t("common.share", "Share")}
                      </Button>
                    )}
                    {/* Only show Edit/Delete for collections user owns */}
                    {!collection.sharedWithMe && (
                      <>
                        <Button
                          size="small"
                          startIcon={<EditIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditClick(collection);
                          }}
                          sx={{ textTransform: "none" }}
                        >
                          {t("common.edit", "Edit")}
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          startIcon={<DeleteIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(collection);
                          }}
                          sx={{ textTransform: "none" }}
                        >
                          {t("common.delete", "Delete")}
                        </Button>
                      </>
                    )}
                  </CardActions>
                </Card>
              );
            })}
          </Box>
        )}
      </PageContent>

      {/* Edit Collection Dialog */}
      <Dialog open={editDialogOpen} onClose={handleEditCancel} maxWidth="sm" fullWidth>
        <DialogTitle>{t("collectionsPage.dialogs.editTitle")}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label={t("collectionsPage.form.description")}
            type="text"
            fullWidth
            multiline
            rows={4}
            value={editedDescription}
            onChange={(e) => setEditedDescription(e.target.value)}
            placeholder={t("common.placeholders.enterCollectionDescription")}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEditCancel}>{t("common.cancel")}</Button>
          <Button
            onClick={handleEditSave}
            variant="contained"
            disabled={updateCollectionMutation.isPending}
          >
            {updateCollectionMutation.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel} maxWidth="sm" fullWidth>
        <DialogTitle>{t("collectionsPage.dialogs.deleteTitle")}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{selectedCollection?.name}"? This will permanently
            delete the collection and all its contents. This action cannot be undone.
          </DialogContentText>
          {selectedCollection && (selectedCollection as any).totalDescendants > 0 && (
            <DialogContentText sx={{ mt: 2, color: "warning.main" }}>
              Warning: This collection has {(selectedCollection as any).totalDescendants}{" "}
              sub-collection
              {(selectedCollection as any).totalDescendants !== 1 ? "s" : ""} that will also be
              deleted.
            </DialogContentText>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>{t("common.cancel")}</Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteCollectionMutation.isPending}
          >
            {deleteCollectionMutation.isPending ? "Deleting..." : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Collection Modal */}
      <CreateCollectionModal open={createModalOpen} onClose={() => setCreateModalOpen(false)} />

      {/* Share Management Modal */}
      <ShareManagementModal
        open={shareModalOpen}
        onClose={handleShareModalClose}
        collection={selectedCollection}
      />

      {/* Alert Snackbar */}
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
    </Box>
  );
};

export default CollectionsPage;
