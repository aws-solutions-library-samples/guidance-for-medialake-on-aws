import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Paper,
  useTheme,
  alpha,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Divider,
  CircularProgress,
  TextField,
  InputAdornment,
  IconButton,
  Button,
  Chip,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Card,
  CardContent,
  CardActions,
  Grid,
} from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ChevronLeft,
  ChevronRight,
  Add as AddIcon,
  MoreVert as MoreVertIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Share as SharedIcon,
  Person as PersonIcon,
  Schedule as ScheduleIcon,
} from "@mui/icons-material";
import {
  useGetCollections,
  useGetSharedCollections,
  useDeleteCollection,
  useUpdateCollection,
  type Collection,
} from "../api/hooks/useCollections";
import { CreateCollectionModal } from "../components/collections/CreateCollectionModal";

const DRAWER_WIDTH = 280;
const COLLAPSED_DRAWER_WIDTH = 60;

const CollectionsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const [selectedTab, setSelectedTab] = useState<"my" | "shared" | "public">(
    "my",
  );
  const [filterText, setFilterText] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editedDescription, setEditedDescription] = useState("");
  const [selectedCollection, setSelectedCollection] =
    useState<Collection | null>(null);
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);

  // API hooks
  const { data: collectionsResponse, isLoading: isLoadingCollections } =
    useGetCollections();
  const { data: sharedCollectionsResponse, isLoading: isLoadingShared } =
    useGetSharedCollections();
  const deleteCollectionMutation = useDeleteCollection();
  const updateCollectionMutation = useUpdateCollection();

  const collections = collectionsResponse?.data || [];
  const sharedCollections = sharedCollectionsResponse?.data || [];

  // Filter collections based on search text and selected tab
  const getFilteredCollections = () => {
    let collectionsToFilter: Collection[] = [];

    switch (selectedTab) {
      case "my":
        // Show collections where user is the owner and not public
        collectionsToFilter = collections.filter((c) => !c.isPublic);
        break;
      case "shared":
        collectionsToFilter = sharedCollections;
        break;
      case "public":
        // Show collections that are marked as public
        collectionsToFilter = collections.filter((c) => c.isPublic);
        break;
      default:
        collectionsToFilter = collections;
    }

    return collectionsToFilter.filter(
      (collection) =>
        collection.name.toLowerCase().includes(filterText.toLowerCase()) ||
        collection.description
          ?.toLowerCase()
          .includes(filterText.toLowerCase()),
    );
  };

  const filteredCollections = getFilteredCollections();

  const handleClearFilter = () => {
    setFilterText("");
  };

  const toggleDrawer = () => {
    setIsCollapsed(!isCollapsed);
  };

  const handleMenuOpen = (
    event: React.MouseEvent<HTMLElement>,
    collection: Collection,
  ) => {
    event.stopPropagation();
    setSelectedCollection(collection);
    setMenuAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedCollection(null);
  };

  const handleEditClick = () => {
    if (selectedCollection) {
      setEditedDescription(selectedCollection.description || "");
      setEditDialogOpen(true);
      handleMenuClose();
    }
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
      } catch (error) {
        console.error("Failed to update collection:", error);
      }
    }
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (selectedCollection) {
      try {
        await deleteCollectionMutation.mutateAsync(selectedCollection.id);
        setDeleteDialogOpen(false);
        setSelectedCollection(null);
      } catch (error) {
        console.error("Failed to delete collection:", error);
      }
    }
  };

  const handleViewCollection = (collection: Collection) => {
    navigate(`/collections/${collection.id}/view`);
  };

  const getCollectionTypeIcon = (type: string) => {
    switch (type) {
      case "public":
        return <PublicIcon fontSize="small" />;
      case "private":
        return <PrivateIcon fontSize="small" />;
      case "shared":
        return <SharedIcon fontSize="small" />;
      default:
        return <FolderIcon fontSize="small" />;
    }
  };

  const getCollectionTypeBadge = (type: string) => {
    const colors = {
      public: { color: "#2e7d32", bgcolor: "#e8f5e8" },
      private: { color: "#1976d2", bgcolor: "#e3f2fd" },
      shared: { color: "#ed6c02", bgcolor: "#fff3e0" },
    };

    const config = colors[type as keyof typeof colors] || colors.private;

    return (
      <Chip
        label={t(`collectionsPage.collectionTypes.${type}`)}
        size="small"
        icon={getCollectionTypeIcon(type)}
        sx={{
          color: config.color,
          bgcolor: config.bgcolor,
          border: `1px solid ${alpha(config.color, 0.3)}`,
          "& .MuiChip-icon": {
            color: config.color,
          },
        }}
      />
    );
  };

  const isLoading = isLoadingCollections || isLoadingShared;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        px: 4,
        pt: 0,
        mt: -1.5,
      }}
    >
      {/* Collections title with gradient styling */}
      <Box sx={{ mb: 0.75 }}>
        <Typography
          variant="h4"
          component="h1"
          sx={{
            fontWeight: 700,
            mb: 0,
            background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            color: "transparent",
          }}
        >
          {t("collectionsPage.title")}
        </Typography>
      </Box>

      {/* Main content area with sidebar and content */}
      <Box
        sx={{
          display: "flex",
          flexGrow: 1,
          height: "calc(100% - 28px)",
          position: "relative",
        }}
      >
        {/* Left Panel - Collection tabs and filters */}
        <Box
          sx={{
            width: isCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
            minWidth: isCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
            mr: 3,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            backgroundColor: "background.paper",
            borderRadius: 2,
            transition: theme.transitions.create(
              ["width", "margin", "min-width"],
              {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              },
            ),
            overflow: "visible",
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* Collapse/Expand Button */}
          <Button
            onClick={toggleDrawer}
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
            {isCollapsed ? (
              <ChevronRight sx={{ fontSize: 20 }} />
            ) : (
              <ChevronLeft sx={{ fontSize: 20 }} />
            )}
          </Button>

          {isCollapsed ? (
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
              <FolderIcon
                sx={{
                  color: theme.palette.primary.main,
                  fontSize: 24,
                }}
              />
            </Box>
          ) : (
            // Expanded view - show full content
            <>
              <Box sx={{ p: 1.5, pb: 1 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    mb: 1,
                  }}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {t("collectionsPage.title")}
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<AddIcon />}
                    onClick={() => setCreateModalOpen(true)}
                    sx={{ minWidth: "auto" }}
                  >
                    {t("collectionsPage.createCollection")}
                  </Button>
                </Box>

                {/* Search field */}
                <TextField
                  fullWidth
                  size="small"
                  placeholder={t("common.search")}
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  sx={{
                    mb: 1,
                    width: "90%",
                    mx: "auto",
                    "& .MuiInputBase-root": {
                      height: 32,
                      fontSize: "0.875rem",
                    },
                    "& .MuiInputBase-input": {
                      py: 0.5,
                    },
                  }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon fontSize="small" sx={{ fontSize: 18 }} />
                      </InputAdornment>
                    ),
                    endAdornment: filterText ? (
                      <InputAdornment position="end">
                        <IconButton
                          size="small"
                          onClick={handleClearFilter}
                          edge="end"
                          sx={{ p: 0.5 }}
                        >
                          <ClearIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </InputAdornment>
                    ) : null,
                  }}
                />
              </Box>

              <Divider />

              {/* Collection type tabs */}
              <Box sx={{ p: 1 }}>
                <List dense disablePadding>
                  <ListItem disablePadding>
                    <ListItemButton
                      selected={selectedTab === "my"}
                      onClick={() => setSelectedTab("my")}
                      sx={{
                        borderRadius: 1,
                        "&.Mui-selected": {
                          backgroundColor: alpha(
                            theme.palette.primary.main,
                            0.1,
                          ),
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <PrivateIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={t("collectionsPage.myCollections")}
                      />
                    </ListItemButton>
                  </ListItem>
                  <ListItem disablePadding>
                    <ListItemButton
                      selected={selectedTab === "shared"}
                      onClick={() => setSelectedTab("shared")}
                      sx={{
                        borderRadius: 1,
                        "&.Mui-selected": {
                          backgroundColor: alpha(
                            theme.palette.primary.main,
                            0.1,
                          ),
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <SharedIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={t("collectionsPage.sharedCollections")}
                      />
                    </ListItemButton>
                  </ListItem>
                  <ListItem disablePadding>
                    <ListItemButton
                      selected={selectedTab === "public"}
                      onClick={() => setSelectedTab("public")}
                      sx={{
                        borderRadius: 1,
                        "&.Mui-selected": {
                          backgroundColor: alpha(
                            theme.palette.primary.main,
                            0.1,
                          ),
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <PublicIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={t("collectionsPage.publicCollections")}
                      />
                    </ListItemButton>
                  </ListItem>
                </List>
              </Box>
            </>
          )}
        </Box>

        {/* Main Content Area - Collections Grid */}
        <Box
          sx={{
            flexGrow: 1,
            height: "100%",
            overflow: "auto",
            backgroundColor: alpha(theme.palette.background.default, 0.5),
          }}
        >
          <Paper
            elevation={0}
            sx={{
              height: "100%",
              borderRadius: "12px",
              border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
              backgroundColor: theme.palette.background.paper,
              overflow: "hidden",
              p: 3,
            }}
          >
            {isLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
                <CircularProgress />
              </Box>
            ) : filteredCollections.length === 0 ? (
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
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
                  {t("collectionsPage.noCollections")}
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setCreateModalOpen(true)}
                >
                  {t("collectionsPage.actions.createNew")}
                </Button>
              </Box>
            ) : (
              <Grid container spacing={3}>
                {filteredCollections.map((collection) => (
                  <Grid item xs={12} sm={6} md={4} lg={3} key={collection.id}>
                    <Card
                      sx={{
                        height: "100%",
                        display: "flex",
                        flexDirection: "column",
                        transition:
                          "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
                        "&:hover": {
                          transform: "translateY(-2px)",
                          boxShadow: theme.shadows[4],
                        },
                      }}
                    >
                      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "flex-start",
                            mb: 1,
                          }}
                        >
                          <FolderIcon
                            sx={{
                              color: theme.palette.primary.main,
                              mr: 1,
                              mt: 0.5,
                            }}
                          />
                          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                            <Typography
                              variant="h6"
                              component="h3"
                              sx={{
                                fontWeight: 600,
                                fontSize: "1rem",
                                lineHeight: 1.2,
                                mb: 0.5,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {collection.name}
                            </Typography>
                            {getCollectionTypeBadge(collection.type)}
                          </Box>
                          <IconButton
                            size="small"
                            onClick={(e) => handleMenuOpen(e, collection)}
                            sx={{ ml: 1 }}
                          >
                            <MoreVertIcon fontSize="small" />
                          </IconButton>
                        </Box>

                        {collection.description && (
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{
                              mb: 2,
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

                        <Box
                          sx={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 1,
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 2,
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {t("collectionsPage.stats.itemCount", {
                                count: collection.itemCount,
                              })}
                            </Typography>
                            {collection.childCount > 0 && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {t("collectionsPage.stats.childCount", {
                                  count: collection.childCount,
                                })}
                              </Typography>
                            )}
                          </Box>

                          {collection.ownerName &&
                            collection.type === "shared" && (
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 0.5,
                                }}
                              >
                                <PersonIcon
                                  sx={{ fontSize: 14, color: "text.secondary" }}
                                />
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                >
                                  {t("collectionsPage.stats.createdBy", {
                                    name: collection.ownerName,
                                  })}
                                </Typography>
                              </Box>
                            )}

                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 0.5,
                            }}
                          >
                            <ScheduleIcon
                              sx={{ fontSize: 14, color: "text.secondary" }}
                            />
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {t("collectionsPage.stats.lastModified", {
                                date: new Date(
                                  collection.updatedAt,
                                ).toLocaleDateString(),
                              })}
                            </Typography>
                          </Box>
                        </Box>
                      </CardContent>

                      <CardActions sx={{ pt: 0, px: 2, pb: 2 }}>
                        <Button
                          size="small"
                          sx={{ ml: "auto" }}
                          onClick={() => handleViewCollection(collection)}
                        >
                          {t("collectionsPage.actions.view")}
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </Paper>
        </Box>
      </Box>

      {/* Context Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <MenuItem
          onClick={() => {
            if (selectedCollection) {
              handleViewCollection(selectedCollection);
            }
            handleMenuClose();
          }}
        >
          {t("collectionsPage.actions.view")}
        </MenuItem>
        <MenuItem onClick={handleEditClick}>
          {t("collectionsPage.actions.edit")}
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          {t("collectionsPage.actions.share")}
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleDeleteClick} sx={{ color: "error.main" }}>
          {t("collectionsPage.actions.delete")}
        </MenuItem>
      </Menu>

      {/* Edit Collection Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Edit Collection</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Description"
            type="text"
            fullWidth
            multiline
            rows={4}
            value={editedDescription}
            onChange={(e) => setEditedDescription(e.target.value)}
            placeholder="Enter collection description"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
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
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t("collectionsPage.deleteDialog.title")}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t("collectionsPage.deleteDialog.description")}
          </DialogContentText>
          {selectedCollection && selectedCollection.childCount > 0 && (
            <DialogContentText sx={{ mt: 1, color: "warning.main" }}>
              {t("collectionsPage.deleteDialog.cascadeWarning")}
            </DialogContentText>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>
            {t("collectionsPage.deleteDialog.cancel")}
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteCollectionMutation.isPending}
          >
            {deleteCollectionMutation.isPending
              ? t("collectionsPage.deleteDialog.deleting")
              : t("collectionsPage.deleteDialog.confirm")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Collection Modal */}
      <CreateCollectionModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
      />
    </Box>
  );
};

export default CollectionsPage;
