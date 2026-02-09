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
  Snackbar,
  Alert,
  TextField,
  InputAdornment,
  IconButton,
  Tooltip,
  FormControl,
  Select,
  MenuItem,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Add as AddIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
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
  FolderSpecial as FolderSpecialIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ArrowUpward as AscIcon,
  ArrowDownward as DescIcon,
} from "@mui/icons-material";
import { PageContent } from "@/components/common/layout";
import { RefreshButton } from "@/components/common";
import {
  useGetCollections,
  useGetCollectionsSharedWithMe,
  useGetCollectionsSharedByMe,
  useDeleteCollection,
  useGetCollectionTypes,
  type Collection,
} from "../api/hooks/useCollections";
import { CreateCollectionModal } from "../components/collections/CreateCollectionModal";
import { EditCollectionModal } from "../components/collections/EditCollectionModal";
import { ShareManagementModal } from "../components/collections/ShareManagementModal";
import { ALL_ICONS } from "../components/collections/ThumbnailSelector";
import { CollectionGroupsList, CollectionGroupForm } from "@/features/collection-groups";
import type { CollectionGroup } from "@/features/collection-groups";
import { sortCollections } from "@/features/dashboard/utils/collectionFilters";
import { formatDateOnly } from "@/utils/dateFormat";
import type { SortBy, SortOrder } from "@/features/dashboard/types";

type FilterTab = "all" | "myCollections" | "sharedWithMe" | "sharedByMe" | "groups";

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

const TAB_CONFIG: {
  value: FilterTab;
  labelKey: string;
  fallback: string;
  icon: React.ReactElement;
}[] = [
  {
    value: "all",
    labelKey: "collectionsPage.filters.all",
    fallback: "All",
    icon: <FolderIcon sx={{ fontSize: 18 }} />,
  },
  {
    value: "myCollections",
    labelKey: "collectionsPage.filters.myCollections",
    fallback: "Mine",
    icon: <PersonIcon sx={{ fontSize: 18 }} />,
  },
  {
    value: "sharedWithMe",
    labelKey: "collectionsPage.filters.sharedWithMe",
    fallback: "Shared with me",
    icon: <PeopleIcon sx={{ fontSize: 18 }} />,
  },
  {
    value: "sharedByMe",
    labelKey: "collectionsPage.filters.sharedByMe",
    fallback: "Shared by me",
    icon: <ShareIcon sx={{ fontSize: 18 }} />,
  },
  {
    value: "groups",
    labelKey: "collectionsPage.filters.groups",
    fallback: "Groups",
    icon: <FolderSpecialIcon sx={{ fontSize: 18 }} />,
  },
];

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
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [alert, setAlert] = useState<{
    message: string;
    severity: "success" | "error";
  } | null>(null);

  // Collection Groups state
  const [groupFormOpen, setGroupFormOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<CollectionGroup | null>(null);

  // Sorting state — defaults match the dashboard widget (name, asc)
  const [sortBy, setSortBy] = useState<SortBy>("name");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");

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

  const allCollections = collectionsResponse?.data || [];
  const sharedWithMeCollections = sharedWithMeResponse?.data || [];
  const sharedByMeCollections = sharedByMeResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  // Handle tab change
  const handleTabChange = (newValue: FilterTab) => {
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
    // Priority 1: Collection's own thumbnail icon
    if (collection.thumbnailType === "icon" && collection.thumbnailValue) {
      const ThumbnailIcon = ALL_ICONS[collection.thumbnailValue];
      if (ThumbnailIcon) {
        return {
          icon: <ThumbnailIcon sx={{ fontSize: 32, mr: 1.5, color: theme.palette.primary.main }} />,
          color: theme.palette.primary.main,
          borderColor: "divider",
          thumbnailUrl: null,
        };
      }
    }

    // Priority 2: Uploaded/asset thumbnail image
    if (collection.thumbnailUrl && collection.thumbnailType !== "icon") {
      return {
        icon: null,
        color: theme.palette.primary.main,
        borderColor: "divider",
        thumbnailUrl: collection.thumbnailUrl,
      };
    }

    // Priority 3: Collection type icon
    if (!collection.collectionTypeId || isLoadingTypes) {
      return {
        icon: <FolderIcon sx={{ fontSize: 32, mr: 1.5, color: theme.palette.primary.main }} />,
        color: theme.palette.primary.main,
        borderColor: "divider",
        thumbnailUrl: null,
      };
    }

    const collectionType = collectionTypes.find((type) => type.id === collection.collectionTypeId);

    if (!collectionType) {
      return {
        icon: <FolderIcon sx={{ fontSize: 32, mr: 1.5, color: theme.palette.primary.main }} />,
        color: theme.palette.primary.main,
        borderColor: "divider",
        thumbnailUrl: null,
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
      thumbnailUrl: null,
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

  // Get filtered collections based on active tab + search
  const filteredCollections = useMemo(() => {
    let collections: Collection[] = [];

    switch (activeTab) {
      case "myCollections":
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
        collections = allCollections.filter((c) => !c.parentId);
        break;
    }

    // Apply search filter
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      collections = collections.filter(
        (c) => c.name.toLowerCase().includes(query) || c.description?.toLowerCase().includes(query)
      );
    }

    return sortCollections(
      collections.map((c) => ({
        ...c,
        totalDescendants: calculateTotalDescendants(c.id, allCollections),
      })),
      { sortBy, sortOrder }
    );
  }, [
    activeTab,
    allCollections,
    sharedWithMeCollections,
    sharedByMeCollections,
    searchText,
    sortBy,
    sortOrder,
  ]);

  const rootCollections = filteredCollections;

  // Badge counts for tabs
  const tabBadgeCounts: Partial<Record<FilterTab, number>> = {
    sharedWithMe: sharedWithMeCollections.length,
    sharedByMe: sharedByMeCollections.length,
  };

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
    setEditDialogOpen(true);
  };

  const handleEditClose = () => {
    setEditDialogOpen(false);
    setSelectedCollection(null);
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
      } catch {
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

  // Collection Groups handlers
  const handleCreateGroupClick = () => {
    setSelectedGroup(null);
    setGroupFormOpen(true);
  };

  const handleEditGroupClick = (group: CollectionGroup) => {
    setSelectedGroup(group);
    setGroupFormOpen(true);
  };

  const handleGroupFormClose = () => {
    setGroupFormOpen(false);
    setSelectedGroup(null);
  };

  const isGroupsTab = activeTab === "groups";

  return (
    <Box sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Page header — title row with action buttons */}
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            mb: 2,
          }}
        >
          <Box>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                mb: 0.5,
                color: theme.palette.primary.main,
              }}
            >
              {t("collectionsPage.title")}
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", maxWidth: 480 }}>
              {t("collectionsPage.description")}
            </Typography>
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <RefreshButton
              onRefresh={handleRefresh}
              isRefreshing={isRefreshing}
              disabled={isLoading}
              variant="icon"
            />
            {isGroupsTab ? (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleCreateGroupClick}
                sx={{
                  borderRadius: 2,
                  textTransform: "none",
                  fontWeight: 600,
                  px: 2.5,
                  height: 38,
                }}
              >
                {t("collectionsPage.filters.createGroup", "Create Group")}
              </Button>
            ) : (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setCreateModalOpen(true)}
                sx={{
                  borderRadius: 2,
                  textTransform: "none",
                  fontWeight: 600,
                  px: 2.5,
                  height: 38,
                }}
              >
                {t("collectionsPage.createCollection")}
              </Button>
            )}
          </Box>
        </Box>

        {/* Toolbar row — filter tabs + search */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
            flexWrap: "wrap",
          }}
        >
          {/* Pill-style filter tabs */}
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
            {TAB_CONFIG.map(({ value, labelKey, fallback, icon }) => {
              const isActive = activeTab === value;
              const badgeCount = tabBadgeCounts[value];
              return (
                <Button
                  key={value}
                  size="small"
                  startIcon={icon}
                  onClick={() => handleTabChange(value)}
                  sx={{
                    borderRadius: 6,
                    textTransform: "none",
                    fontWeight: isActive ? 600 : 400,
                    fontSize: "0.82rem",
                    px: 2,
                    py: 0.6,
                    minHeight: 34,
                    color: isActive ? theme.palette.primary.contrastText : "text.secondary",
                    bgcolor: isActive
                      ? theme.palette.primary.main
                      : alpha(theme.palette.action.hover, 0.06),
                    border: "1px solid",
                    borderColor: isActive
                      ? theme.palette.primary.main
                      : alpha(theme.palette.divider, 0.12),
                    "&:hover": {
                      bgcolor: isActive
                        ? theme.palette.primary.dark
                        : alpha(theme.palette.action.hover, 0.12),
                    },
                    transition: "all 0.15s ease",
                  }}
                  endIcon={
                    badgeCount ? (
                      <Chip
                        label={badgeCount}
                        size="small"
                        sx={{
                          height: 20,
                          minWidth: 20,
                          fontSize: "0.7rem",
                          fontWeight: 600,
                          bgcolor: isActive
                            ? alpha(theme.palette.common.white, 0.25)
                            : alpha(theme.palette.primary.main, 0.12),
                          color: isActive
                            ? theme.palette.primary.contrastText
                            : theme.palette.primary.main,
                          "& .MuiChip-label": { px: 0.6 },
                        }}
                      />
                    ) : undefined
                  }
                >
                  {t(labelKey, fallback)}
                </Button>
              );
            })}
          </Box>

          {/* Search + Sort controls */}
          {!isGroupsTab && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              {/* Sort by */}
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <Select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortBy)}
                  sx={{
                    borderRadius: 2,
                    height: 36,
                    fontSize: "0.85rem",
                  }}
                >
                  <MenuItem value="name">{t("collectionsPage.sort.name", "Name")}</MenuItem>
                  <MenuItem value="createdAt">
                    {t("collectionsPage.sort.createdAt", "Created")}
                  </MenuItem>
                  <MenuItem value="updatedAt">
                    {t("collectionsPage.sort.updatedAt", "Updated")}
                  </MenuItem>
                </Select>
              </FormControl>

              {/* Sort order toggle */}
              <ToggleButtonGroup
                value={sortOrder}
                exclusive
                onChange={(_e, val) => {
                  if (val) setSortOrder(val as SortOrder);
                }}
                size="small"
                sx={{ height: 36 }}
              >
                <ToggleButton
                  value="asc"
                  aria-label={t("collectionsPage.sort.ascending", "Ascending")}
                >
                  <AscIcon sx={{ fontSize: 18 }} />
                </ToggleButton>
                <ToggleButton
                  value="desc"
                  aria-label={t("collectionsPage.sort.descending", "Descending")}
                >
                  <DescIcon sx={{ fontSize: 18 }} />
                </ToggleButton>
              </ToggleButtonGroup>

              {/* Search */}
              <TextField
                size="small"
                placeholder={t("collectionsPage.searchPlaceholder", "Search collections...")}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                sx={{
                  width: 260,
                  "& .MuiOutlinedInput-root": {
                    borderRadius: 2,
                    height: 36,
                    fontSize: "0.85rem",
                  },
                }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon sx={{ fontSize: 18, color: "text.secondary" }} />
                    </InputAdornment>
                  ),
                  endAdornment: searchText ? (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setSearchText("")} sx={{ p: 0.25 }}>
                        <ClearIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </InputAdornment>
                  ) : null,
                }}
              />
            </Box>
          )}
        </Box>
      </Box>

      {/* Main content */}
      <PageContent
        isLoading={isGroupsTab ? false : isLoadingCollections}
        error={isGroupsTab ? null : (error as Error)}
      >
        {isGroupsTab ? (
          <CollectionGroupsList
            onCreateClick={handleCreateGroupClick}
            onEditClick={handleEditGroupClick}
          />
        ) : rootCollections.length === 0 ? (
          /* Empty state */
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: 360,
              textAlign: "center",
              py: 6,
            }}
          >
            <Box
              sx={{
                width: 80,
                height: 80,
                borderRadius: "50%",
                bgcolor: alpha(theme.palette.primary.main, 0.08),
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: 2.5,
              }}
            >
              {activeTab === "sharedWithMe" ? (
                <PeopleIcon
                  sx={{
                    fontSize: 40,
                    color: alpha(theme.palette.primary.main, 0.4),
                  }}
                />
              ) : activeTab === "sharedByMe" ? (
                <ShareIcon
                  sx={{
                    fontSize: 40,
                    color: alpha(theme.palette.primary.main, 0.4),
                  }}
                />
              ) : (
                <FolderOpenIcon
                  sx={{
                    fontSize: 40,
                    color: alpha(theme.palette.primary.main, 0.4),
                  }}
                />
              )}
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5, color: "text.primary" }}>
              {searchText
                ? t("collectionsPage.noSearchResults", "No matching collections")
                : activeTab === "sharedWithMe"
                  ? t("collectionsPage.noSharedWithMe", "No collections shared with you")
                  : activeTab === "sharedByMe"
                    ? t("collectionsPage.noSharedByMe", "You haven't shared any collections")
                    : t("collectionsPage.noCollections", "No collections found")}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 320 }}>
              {searchText
                ? t(
                    "collectionsPage.tryDifferentSearch",
                    "Try a different search term or clear the filter"
                  )
                : activeTab === "sharedWithMe"
                  ? t(
                      "collectionsPage.noSharedWithMeDescription",
                      "When someone shares a collection with you, it will appear here"
                    )
                  : activeTab === "sharedByMe"
                    ? t(
                        "collectionsPage.noSharedByMeDescription",
                        "Collections you share with others will appear here"
                      )
                    : t(
                        "collectionsPage.createFirstCollection",
                        "Create your first collection to get started"
                      )}
            </Typography>
            {!searchText && activeTab !== "sharedWithMe" && activeTab !== "sharedByMe" && (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setCreateModalOpen(true)}
                sx={{
                  borderRadius: 2,
                  textTransform: "none",
                  fontWeight: 600,
                  px: 3,
                }}
              >
                {t("collectionsPage.createCollection", "Create Collection")}
              </Button>
            )}
          </Box>
        ) : (
          /* Card grid */
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(auto-fill, minmax(280px, 1fr))",
                md: "repeat(auto-fill, minmax(300px, 1fr))",
              },
              gap: 2.5,
              pt: 0.5,
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
                    overflow: "hidden",
                    border: "1px solid",
                    borderColor: alpha(theme.palette.divider, 0.1),
                    bgcolor: "background.paper",
                    transition:
                      "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    "&:hover": {
                      transform: "translateY(-4px)",
                      boxShadow: `0 8px 32px ${alpha(theme.palette.common.black, 0.2)}`,
                      cursor: "pointer",
                      "& .card-actions-overlay": {
                        opacity: 1,
                      },
                    },
                  }}
                  onClick={() => handleViewCollection(collection)}
                >
                  {/* Thumbnail area */}
                  <Box sx={{ p: 1.25, pb: 0 }}>
                    <Box
                      sx={{
                        height: 180,
                        borderRadius: 2.5,
                        overflow: "hidden",
                        position: "relative",
                        bgcolor: style.thumbnailUrl
                          ? "transparent"
                          : alpha(theme.palette.primary.main, 0.04),
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {style.thumbnailUrl ? (
                        <Box
                          component="img"
                          src={style.thumbnailUrl}
                          alt={collection.name}
                          sx={{
                            width: "100%",
                            height: "100%",
                            objectFit: "cover",
                          }}
                        />
                      ) : style.icon ? (
                        React.cloneElement(style.icon as React.ReactElement, {
                          sx: {
                            fontSize: 56,
                            color: alpha(theme.palette.primary.main, 0.18),
                          },
                        })
                      ) : (
                        <FolderIcon
                          sx={{
                            fontSize: 56,
                            color: alpha(theme.palette.primary.main, 0.18),
                          }}
                        />
                      )}

                      {/* Action buttons overlay */}
                      {!collection.sharedWithMe && (
                        <Box
                          className="card-actions-overlay"
                          sx={{
                            position: "absolute",
                            top: 8,
                            right: 8,
                            display: "flex",
                            gap: 0.5,
                            opacity: 0,
                            transition: "opacity 0.15s ease",
                          }}
                        >
                          {[
                            {
                              icon: <ShareIcon sx={{ fontSize: 15 }} />,
                              tip: t("common.share", "Share"),
                              handler: handleShareClick,
                              color: "text.primary",
                            },
                            {
                              icon: <EditIcon sx={{ fontSize: 15 }} />,
                              tip: t("common.edit", "Edit"),
                              handler: handleEditClick,
                              color: "text.primary",
                            },
                            {
                              icon: <DeleteIcon sx={{ fontSize: 15 }} />,
                              tip: t("common.delete", "Delete"),
                              handler: handleDeleteClick,
                              color: "error.main",
                            },
                          ].map(({ icon, tip, handler, color }) => (
                            <Tooltip key={tip} title={tip}>
                              <Button
                                size="small"
                                sx={{
                                  minWidth: 0,
                                  p: 0.6,
                                  borderRadius: 1.5,
                                  bgcolor: alpha(theme.palette.background.paper, 0.85),
                                  backdropFilter: "blur(8px)",
                                  color,
                                  border: "1px solid",
                                  borderColor: alpha(theme.palette.divider, 0.12),
                                  "&:hover": {
                                    bgcolor: theme.palette.background.paper,
                                  },
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handler(collection);
                                }}
                              >
                                {icon}
                              </Button>
                            </Tooltip>
                          ))}
                        </Box>
                      )}
                    </Box>
                  </Box>

                  {/* Info section */}
                  <CardContent sx={{ px: 1.75, pt: 1.25, pb: 1.25, "&:last-child": { pb: 1.25 } }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.25 }}>
                      <FolderIcon
                        sx={{
                          fontSize: 18,
                          color: alpha(theme.palette.primary.main, 0.5),
                        }}
                      />
                      <Typography
                        variant="subtitle2"
                        component="h3"
                        sx={{
                          fontWeight: 600,
                          fontSize: "0.9rem",
                          lineHeight: 1.4,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          flex: 1,
                        }}
                      >
                        {collection.name}
                      </Typography>
                    </Box>

                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontSize: "0.75rem" }}
                      >
                        {collection.itemCount} asset{collection.itemCount !== 1 ? "s" : ""}
                        {collection.childCollectionCount > 0 &&
                          ` · ${collection.childCollectionCount} sub`}
                        {collection.createdAt && ` · ${formatDateOnly(collection.createdAt)}`}
                      </Typography>
                      <Chip
                        label={
                          collection.isPublic
                            ? t("collectionsPage.collectionTypes.public", "Public")
                            : t("collectionsPage.collectionTypes.private", "Private")
                        }
                        size="small"
                        icon={collection.isPublic ? <PublicIcon /> : <PrivateIcon />}
                        variant="outlined"
                        sx={{
                          height: 22,
                          fontSize: "0.68rem",
                          fontWeight: 500,
                          color: collection.isPublic ? "#38A169" : "text.secondary",
                          borderColor: collection.isPublic
                            ? alpha("#38A169", 0.35)
                            : alpha(theme.palette.text.secondary, 0.15),
                          bgcolor: collection.isPublic ? alpha("#38A169", 0.06) : "transparent",
                          "& .MuiChip-icon": {
                            color: collection.isPublic ? "#38A169" : "text.secondary",
                            fontSize: 13,
                          },
                        }}
                      />
                    </Box>
                  </CardContent>
                </Card>
              );
            })}
          </Box>
        )}
      </PageContent>

      {/* Edit Collection Modal */}
      <EditCollectionModal
        open={editDialogOpen}
        onClose={handleEditClose}
        collection={selectedCollection}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 3, backgroundImage: "none" },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600 }}>
          {t("collectionsPage.dialogs.deleteTitle")}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete &ldquo;{selectedCollection?.name}&rdquo;? This will
            permanently delete the collection and all its contents. This action cannot be undone.
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
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleDeleteCancel} sx={{ textTransform: "none" }}>
            {t("common.cancel")}
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteCollectionMutation.isPending}
            sx={{ textTransform: "none", borderRadius: 2 }}
          >
            {deleteCollectionMutation.isPending ? "Deleting..." : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Collection Modal */}
      <CreateCollectionModal open={createModalOpen} onClose={() => setCreateModalOpen(false)} />

      {/* Collection Group Form Modal */}
      <CollectionGroupForm
        open={groupFormOpen}
        onClose={handleGroupFormClose}
        group={selectedGroup}
      />

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
