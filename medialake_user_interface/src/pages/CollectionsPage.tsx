import React, { useState, useMemo, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
import {
  Box,
  Typography,
  useTheme,
  alpha,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Snackbar,
  Alert,
} from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Add as AddIcon,
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
} from "@mui/icons-material";
import type { SvgIconComponent } from "@mui/icons-material";
import { PageContent } from "@/components/common/layout";
import { RefreshButton } from "@/components/common";
import {
  useGetCollections,
  useGetAllCollections,
  useGetCollectionsSharedWithMe,
  useGetCollectionsSharedByMe,
  useDeleteCollection,
  useGetMetadataKeys,
  type Collection,
} from "../api/hooks/useCollections";
import { useCollectionCollectionTypes } from "../api/hooks/useCollectionCollectionTypes";
import { CreateCollectionModal } from "../components/collections/CreateCollectionModal";
import { EditCollectionModal } from "../components/collections/EditCollectionModal";
import { ShareManagementModal } from "../components/collections/ShareManagementModal";
import { ALL_ICONS } from "../components/collections/ThumbnailSelector";
import { CollectionCard } from "../components/collections/CollectionCard";
import { CollectionsFavoritesSection } from "../components/collections/CollectionsFavoritesSection";
import { CollectionCardViewControls } from "../components/collections/CollectionCardViewControls";
import { useCollectionViewPreferences } from "../hooks/useCollectionViewPreferences";
import { useCollectionFavorites } from "@/hooks/useCollectionFavorites";
import { buildFavoritesCollectionList } from "@/features/dashboard/utils/buildFavoritesCollectionList";
import {
  CollectionViewControls,
  type CollectionSortOption,
  type SortDirection,
} from "../components/collections/CollectionViewControls";
import {
  CollectionFilterDrawer,
  EMPTY_FILTER_STATE,
  countActiveFilters,
  type CollectionFilterState,
} from "../components/collections/CollectionFilterDrawer";
import { ActiveFilterChips } from "../components/collections/ActiveFilterChips";
import { CollectionGroupsList, CollectionGroupForm } from "@/features/collection-groups";
import type { CollectionGroup } from "@/features/collection-groups";
import AssetPagination from "@/components/shared/AssetPagination";
import { fetchAuthSession } from "aws-amplify/auth";
import { jwtDecode } from "jwt-decode";

const COLLECTIONS_DEFAULT_PAGE_SIZE = 100;

interface JwtPayload {
  sub?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

async function getCurrentUserId(): Promise<string> {
  try {
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();
    if (token) {
      const decoded = jwtDecode<JwtPayload>(token);
      return decoded.sub || "";
    }
    return "";
  } catch {
    return "";
  }
}

type FilterTab = "all" | "myCollections" | "sharedWithMe" | "sharedByMe" | "groups";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, SvgIconComponent> = {
  Folder: FolderIcon,
  FolderOpen: FolderOpenIcon,
  Work: Work,
  Campaign: Campaign,
  Assignment: Assignment,
  Archive: Archive,
  PhotoLibrary: PhotoLibraryIcon,
  Label: Label,
  Movie: Movie,
  Collections: CollectionsIcon,
  Dashboard: Dashboard,
  Storage: Storage,
  Inventory: Inventory,
  Category: Category,
  BookmarkBorder: BookmarkBorder,
  LocalOffer: LocalOffer,
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

  // Permission checks for collection actions
  const createCollectionPermission = useActionPermission("create", "collection");
  const deleteCollectionPermission = useActionPermission("delete", "collection");
  const editCollectionPermission = useActionPermission("edit", "collection");

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

  // Sorting state — sort field is a free-form string because the Sort popover
  // can select `customMetadata.<key>` values. Default stays `name asc`.
  const [sortField, setSortField] = useState<string>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  // Filter popover state — anchor element for the popover; null when closed.
  const [filterAnchor, setFilterAnchor] = useState<HTMLElement | null>(null);
  const [appliedFilters, setAppliedFilters] = useState<CollectionFilterState>(EMPTY_FILTER_STATE);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(COLLECTIONS_DEFAULT_PAGE_SIZE);

  // Current user ID for myCollections tab
  const [currentUserId, setCurrentUserId] = useState("");
  useEffect(() => {
    getCurrentUserId().then(setCurrentUserId);
  }, []);

  // Debounced search — updates 300ms after searchText changes
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  // Get filter from URL params
  const filterParam = searchParams.get("filter") as FilterTab | null;
  const activeTab: FilterTab = filterParam || "all";

  // Fetch metadata keys for filter dropdown
  const { data: metadataKeysResponse } = useGetMetadataKeys();
  const metadataKeys = useMemo(
    () => metadataKeysResponse?.data?.keys || [],
    [metadataKeysResponse]
  );

  // Card display preferences (preset, card size, visible fields/metadata keys).
  // Persists to localStorage and seeds `visibleMetadataKeys` with the first 3
  // alphabetical keys the first time the user lands on the page.
  const {
    prefs: cardDisplayPrefs,
    setPreset: setCardPreset,
    setCardSize: setCardSize,
    toggleCoreField: toggleCardCoreField,
    toggleMetadataKey: toggleCardMetadataKey,
  } = useCollectionViewPreferences({ availableMetadataKeys: metadataKeys });

  // Build the metadataFilters dict the API hook expects from the committed drawer rows
  const activeMetadataFilters = useMemo<Record<string, string> | undefined>(() => {
    const entries: Record<string, string> = {};
    for (const f of appliedFilters.metadataFilters) {
      if (f.key.trim() && f.value.trim()) entries[f.key.trim()] = f.value.trim();
    }
    return Object.keys(entries).length > 0 ? entries : undefined;
  }, [appliedFilters.metadataFilters]);

  const activeTagFilters = useMemo(
    () => (appliedFilters.tags.length > 0 ? appliedFilters.tags : undefined),
    [appliedFilters.tags]
  );

  const activeVisibilityFilters = useMemo(
    () => (appliedFilters.visibility.length > 0 ? appliedFilters.visibility : undefined),
    [appliedFilters.visibility]
  );

  const activeUpdatedWithin = appliedFilters.updatedWithin ?? undefined;

  // Determine if we're actively searching or filtering — include children so nested
  // collections surface in results.
  const isSearchingOrFiltering = !!(
    debouncedSearch ||
    activeMetadataFilters ||
    activeTagFilters ||
    appliedFilters.visibility.length > 0 ||
    appliedFilters.updatedWithin
  );

  // API hooks
  const {
    data: collectionsResponse,
    isLoading,
    error,
    refetch,
  } = useGetCollections({
    page,
    pageSize,
    sort: sortField,
    sortDirection,
    search: debouncedSearch || undefined,
    filterOwnerId: activeTab === "myCollections" ? currentUserId || undefined : undefined,
    enabled: activeTab !== "myCollections" || !!currentUserId,
    metadataFilters: activeMetadataFilters,
    tagFilters: activeTagFilters,
    visibilityFilters: activeVisibilityFilters,
    updatedWithin: activeUpdatedWithin,
    includeChildren: isSearchingOrFiltering || undefined,
  });
  const { data: sharedWithMeResponse, isLoading: isLoadingSharedWithMe } =
    useGetCollectionsSharedWithMe();
  const { data: sharedByMeResponse, isLoading: isLoadingSharedByMe } =
    useGetCollectionsSharedByMe();
  const { data: collectionTypesResponse, isLoading: isLoadingTypes } =
    useCollectionCollectionTypes();
  const deleteCollectionMutation = useDeleteCollection();

  // All collections (for parent name lookup when search results include children)
  const { data: allCollectionsLookupResponse } = useGetAllCollections();
  const parentNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of allCollectionsLookupResponse?.data || []) {
      map.set(c.id, c.name);
    }
    return map;
  }, [allCollectionsLookupResponse]);

  const allCollections = collectionsResponse?.data || [];
  const sharedWithMeCollections = sharedWithMeResponse?.data || [];
  const sharedByMeCollections = sharedByMeResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  // Shared collection-favorites state — single source of truth across surfaces.
  const { favorites, isCollectionFavorited, handleFavoriteToggle } = useCollectionFavorites();

  // Favorites section (My Collections tab): join the favorited-id set against the
  // loaded datasets (which carry `userRole` for correct action gating), then
  // append a metadata fallback card for favorited ids not present in those
  // datasets (e.g. favorited collections on another page or shared collections).
  const favoritePoolIds = useMemo(
    () =>
      new Set(
        [...allCollections, ...sharedWithMeCollections, ...sharedByMeCollections].map((c) => c.id)
      ),
    [allCollections, sharedWithMeCollections, sharedByMeCollections]
  );
  const favoritesList = useMemo(
    () =>
      buildFavoritesCollectionList(
        [allCollections, sharedWithMeCollections, sharedByMeCollections],
        favorites ?? [],
        currentUserId,
        { sortBy: "name", sortOrder: "asc" }
      ),
    [allCollections, sharedWithMeCollections, sharedByMeCollections, favorites, currentUserId]
  );

  // Sort options for the toolbar — standard fields always visible; custom
  // metadata keys are appended by `CollectionViewControls` from the
  // `customMetadataKeys` prop.
  const standardSortOptions = useMemo<CollectionSortOption[]>(
    () => [
      {
        id: "name",
        label: t("collectionsPage.sort.name", "Name"),
        defaultDirection: "asc",
      },
      {
        id: "createdAt",
        label: t("collectionsPage.sort.createdAt", "Created"),
        defaultDirection: "desc",
      },
      {
        id: "updatedAt",
        label: t("collectionsPage.sort.updatedAt", "Updated"),
        defaultDirection: "desc",
      },
    ],
    [t]
  );

  // Collection type name lookup for the filter chip row
  const collectionTypeNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const ct of collectionTypes) {
      map[ct.id] = ct.name;
    }
    return map;
  }, [collectionTypes]);

  // Available tag list for the filter drawer — derived from the all-collections
  // lookup cache. Deduped and sorted alphabetically.
  const availableTags = useMemo(() => {
    const set = new Set<string>();
    for (const c of allCollectionsLookupResponse?.data || []) {
      if (Array.isArray(c.tags)) {
        for (const tag of c.tags) {
          if (tag) set.add(tag);
        }
      }
    }
    return Array.from(set).sort();
  }, [allCollectionsLookupResponse]);

  const activeFilterCount = useMemo(() => countActiveFilters(appliedFilters), [appliedFilters]);

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
        IconComponent: FolderIcon,
        color: theme.palette.primary.main,
        borderColor: "divider",
        thumbnailUrl: null,
      };
    }

    const collectionType = collectionTypes.find((type) => type.id === collection.collectionTypeId);

    if (!collectionType) {
      return {
        icon: <FolderIcon sx={{ fontSize: 32, mr: 1.5, color: theme.palette.primary.main }} />,
        IconComponent: FolderIcon,
        color: theme.palette.primary.main,
        borderColor: "divider",
        thumbnailUrl: null,
      };
    }

    const IconComp = (collectionType.icon && ICON_MAP[collectionType.icon]) || FolderIcon;
    const iconComponent = <IconComp sx={{ color: collectionType.color, fontSize: 32, mr: 1.5 }} />;

    return {
      icon: iconComponent,
      IconComponent: IconComp,
      color: collectionType.color,
      borderColor: collectionType.color,
      thumbnailUrl: null,
    };
  };

  // Get collections for the current tab
  // "all" and "myCollections" use server-side pagination via useGetCollections
  // "sharedWithMe" and "sharedByMe" use their own hooks
  const filteredCollections = useMemo(() => {
    switch (activeTab) {
      case "sharedWithMe":
        return sharedWithMeCollections;
      case "sharedByMe":
        return sharedByMeCollections;
      case "all":
      case "myCollections":
      default:
        return allCollections;
    }
  }, [activeTab, allCollections, sharedWithMeCollections, sharedByMeCollections]);

  const rootCollections = filteredCollections;

  // Total count: use API pagination for all/myCollections tabs, local count for shared tabs
  const totalCollections = useMemo(() => {
    if (activeTab === "sharedWithMe" || activeTab === "sharedByMe") {
      return rootCollections.length;
    }
    return collectionsResponse?.pagination?.totalResults ?? 0;
  }, [activeTab, rootCollections.length, collectionsResponse]);

  // Reset to page 1 when filters, search, sort, or pageSize changes
  React.useEffect(() => {
    setPage(1);
  }, [activeTab, searchText, sortField, sortDirection, pageSize, appliedFilters]);

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    // Scroll to top of the collections grid
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1);
  };

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

  // Shared card-grid column rule — column min-width scales with card size so
  // S/M/L all stay uniformly packed. Used by both the My Collections favorites
  // section and the main collections grid.
  const cardGridSx = {
    display: "grid",
    gridTemplateColumns: {
      xs: "1fr",
      sm: `repeat(auto-fill, minmax(${
        cardDisplayPrefs.cardSize === "small"
          ? 220
          : cardDisplayPrefs.cardSize === "large"
            ? 340
            : 280
      }px, 1fr))`,
      md: `repeat(auto-fill, minmax(${
        cardDisplayPrefs.cardSize === "small"
          ? 220
          : cardDisplayPrefs.cardSize === "large"
            ? 340
            : 280
      }px, 1fr))`,
    },
    gap: 2.5,
    pt: 0.5,
  } as const;

  // Single card renderer shared by the favorites section and the main grid.
  // `withActions` gates the owner-only mutation menu (omitted for metadata
  // fallback cards, which carry no real `userRole`); `withSearchContext` gates
  // the search-only parent breadcrumb and custom-metadata explainer chip.
  const renderCollectionCard = (
    collection: Collection,
    opts: { withActions: boolean; withSearchContext: boolean }
  ) => {
    const style = getCollectionStyle(collection);
    const sortedMetadataKey = sortField.startsWith("customMetadata.")
      ? sortField.substring("customMetadata.".length)
      : undefined;
    const parentName =
      opts.withSearchContext && collection.parentId && isSearchingOrFiltering
        ? parentNameMap.get(collection.parentId)
        : undefined;
    const collectionType = collection.collectionTypeId
      ? collectionTypes.find((ct) => ct.id === collection.collectionTypeId)
      : undefined;
    const placeholderIconName = collectionType?.icon;
    return (
      <CollectionCard
        key={collection.id}
        collection={collection}
        onClick={handleViewCollection}
        onShareClick={opts.withActions ? handleShareClick : undefined}
        onEditClick={opts.withActions ? handleEditClick : undefined}
        onDeleteClick={opts.withActions ? handleDeleteClick : undefined}
        editPermission={editCollectionPermission}
        deletePermission={deleteCollectionPermission}
        accentColor={style.color}
        placeholderIconName={placeholderIconName}
        sortedMetadataKey={opts.withSearchContext ? sortedMetadataKey : undefined}
        parentName={parentName}
        display={cardDisplayPrefs}
        isFavorite={isCollectionFavorited(collection.id)}
        onFavoriteToggle={(e) => handleFavoriteToggle(collection, e)}
      />
    );
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Page header — title row with action buttons */}
      <Box sx={{ mb: 4 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            mb: 3,
          }}
        >
          <Box>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                mb: 1,
                color: theme.palette.primary.main,
              }}
            >
              {t("collectionsPage.title")}
            </Typography>
            <Typography variant="body1" sx={{ color: "text.secondary", maxWidth: 600 }}>
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
                disabled={createCollectionPermission.disabled}
                title={createCollectionPermission.tooltip}
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
                disabled={createCollectionPermission.disabled}
                title={createCollectionPermission.tooltip}
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
                    transition:
                      "background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease",
                  }}
                  endIcon={
                    badgeCount ? (
                      <Box
                        component="span"
                        sx={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          height: 18,
                          minWidth: 18,
                          px: 0.5,
                          borderRadius: 0.75,
                          fontSize: "0.6rem",
                          fontWeight: 600,
                          lineHeight: 1,
                          bgcolor: isActive
                            ? alpha(theme.palette.common.white, 0.22)
                            : alpha(theme.palette.primary.main, 0.1),
                          color: isActive
                            ? theme.palette.primary.contrastText
                            : theme.palette.primary.main,
                        }}
                      >
                        {badgeCount}
                      </Box>
                    ) : undefined
                  }
                >
                  {t(labelKey, fallback)}
                </Button>
              );
            })}
          </Box>

          {/* Toolbar rendered below via CollectionViewControls + ActiveFilterChips */}
        </Box>
      </Box>

      {/* Toolbar strip — mirrors the Search page's AssetViewControls pattern so the
          two list surfaces share the same visual language. No horizontal padding
          here; the AppLayout already pads the page so this row lines up with the
          header action cluster above it and the card grid below it. */}
      {!isGroupsTab && (
        <Box>
          <CollectionViewControls
            searchValue={searchText}
            onSearchChange={setSearchText}
            sortField={sortField}
            sortDirection={sortDirection}
            onSortChange={(field, direction) => {
              setSortField(field);
              setSortDirection(direction);
            }}
            standardSortOptions={standardSortOptions}
            customMetadataKeys={metadataKeys}
            onOpenFilters={(e) => setFilterAnchor(e.currentTarget)}
            activeFilterCount={activeFilterCount}
            endSlot={
              <CollectionCardViewControls
                prefs={cardDisplayPrefs}
                onPresetChange={setCardPreset}
                onCardSizeChange={setCardSize}
                onCoreFieldToggle={toggleCardCoreField}
                onMetadataKeyToggle={toggleCardMetadataKey}
                availableMetadataKeys={metadataKeys}
              />
            }
          />
          <ActiveFilterChips
            search={debouncedSearch}
            sortLabel={
              standardSortOptions.find((o) => o.id === sortField)?.label ??
              (sortField.startsWith("customMetadata.")
                ? sortField.substring("customMetadata.".length)
                : sortField)
            }
            sortDirection={sortDirection}
            sortIsDefault={sortField === "name" && sortDirection === "asc"}
            filters={appliedFilters}
            collectionTypeNameById={collectionTypeNameById}
            onClearSearch={() => setSearchText("")}
            onClearSort={() => {
              setSortField("name");
              setSortDirection("asc");
            }}
            onRemoveVisibility={(v) =>
              setAppliedFilters((s) => ({
                ...s,
                visibility: s.visibility.filter((x) => x !== v),
              }))
            }
            onRemoveType={(id) =>
              setAppliedFilters((s) => ({
                ...s,
                collectionTypeIds: s.collectionTypeIds.filter((x) => x !== id),
              }))
            }
            onRemoveTag={(tag) =>
              setAppliedFilters((s) => ({
                ...s,
                tags: s.tags.filter((t) => t !== tag),
              }))
            }
            onRemoveMetadata={(id) =>
              setAppliedFilters((s) => ({
                ...s,
                metadataFilters: s.metadataFilters.filter((f) => f.id !== id),
              }))
            }
            onClearUpdatedWithin={() => setAppliedFilters((s) => ({ ...s, updatedWithin: null }))}
            onClearAll={() => {
              setAppliedFilters(EMPTY_FILTER_STATE);
              setSearchText("");
              setSortField("name");
              setSortDirection("asc");
            }}
          />
        </Box>
      )}

      {/* Main content */}
      <PageContent
        isLoading={isGroupsTab ? false : isLoadingCollections}
        error={isGroupsTab ? null : (error as Error)}
      >
        {/* My Collections tab: a Favorites section stacked above the user's own
            collections. Favorited collections absent from the loaded datasets are
            rendered from captured metadata so they still appear here. */}
        {activeTab === "myCollections" && (
          <CollectionsFavoritesSection
            favorites={favoritesList}
            isLive={(id) => favoritePoolIds.has(id)}
            gridSx={cardGridSx}
            renderCard={(collection, withActions) =>
              renderCollectionCard(collection, { withActions, withSearchContext: false })
            }
          />
        )}
        {activeTab === "myCollections" && (
          <Typography variant="h6" component="h2" sx={{ fontWeight: 600, mb: 2 }}>
            {t("collectionsPage.filters.myCollections", "My Collections")}
          </Typography>
        )}
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
                disabled={createCollectionPermission.disabled}
                title={createCollectionPermission.tooltip}
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
          /* Card grid — see `cardGridSx` for the column rule. */
          <Box sx={cardGridSx}>
            {rootCollections.map((collection) =>
              renderCollectionCard(collection, { withActions: true, withSearchContext: true })
            )}
          </Box>
        )}
        {/* Pagination — only for tabs with server-side pagination */}
        {totalCollections > 0 &&
          activeTab !== "sharedWithMe" &&
          activeTab !== "sharedByMe" &&
          !isGroupsTab && (
            <AssetPagination
              page={page}
              pageSize={pageSize}
              totalResults={totalCollections}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
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

      {/* Filter popover — anchored to the Filters toolbar button like the Sort popover.
          Closing via `onClose` or Apply discards/commits the local draft. */}
      <CollectionFilterDrawer
        anchorEl={filterAnchor}
        onClose={() => setFilterAnchor(null)}
        applied={appliedFilters}
        onApply={setAppliedFilters}
        availableCollectionTypes={collectionTypes.map((ct) => ({
          id: ct.id,
          name: ct.name,
        }))}
        availableTags={availableTags}
        availableMetadataKeys={metadataKeys}
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
