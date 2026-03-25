/**
 * Collection Group Detail Page
 * Shows group details and allows managing collections within the group
 */

import React, { useState } from "react";
import { useParams, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItemButton,
  ListItemText,
  Checkbox,
  TextField,
  Grid,
  alpha,
  useTheme,
} from "@mui/material";
import {
  ArrowBack as ArrowBackIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  FolderSpecial as FolderSpecialIcon,
  Folder as FolderIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  PhotoLibrary as PhotoLibraryIcon,
  CalendarToday as CalendarIcon,
} from "@mui/icons-material";
import {
  useCollectionGroup,
  useDeleteCollectionGroup,
  useAddCollectionsToGroup,
  useRemoveCollectionsFromGroup,
} from "../hooks/useCollectionGroups";
import { useGetCollections } from "@/api/hooks/useCollections";
import { useCollectionCollectionTypes } from "@/api/hooks/useCollectionCollectionTypes";
import { CollectionGroupForm } from "../components/CollectionGroupForm";
import { formatDate } from "@/utils/dateFormat";
import type { CollectionGroup } from "../types";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <FolderIcon />,
};

export const CollectionGroupDetailPage: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const theme = useTheme();
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: groupData, isLoading, error } = useCollectionGroup(groupId!);
  const { data: collectionsData, isLoading: isLoadingCollections } = useGetCollections();
  const { data: collectionTypesResponse, isLoading: isLoadingTypes } =
    useCollectionCollectionTypes();
  const deleteGroup = useDeleteCollectionGroup();
  const addCollections = useAddCollectionsToGroup();
  const removeCollections = useRemoveCollectionsFromGroup();

  // Get all available collections from API
  const availableCollections = collectionsData?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  // Helper to get icon and color for a collection
  const getCollectionStyle = (collection: any) => {
    if (!collection.collectionTypeId || isLoadingTypes) {
      return {
        icon: <FolderIcon sx={{ color: theme.palette.primary.main, fontSize: 32, mr: 1.5 }} />,
        color: theme.palette.primary.main,
        borderColor: "divider",
      };
    }

    const collectionType = collectionTypes.find((type) => type.id === collection.collectionTypeId);

    if (!collectionType) {
      return {
        icon: <FolderIcon sx={{ color: theme.palette.primary.main, fontSize: 32, mr: 1.5 }} />,
        color: theme.palette.primary.main,
        borderColor: "divider",
      };
    }

    return {
      icon: <FolderIcon sx={{ color: collectionType.color, fontSize: 32, mr: 1.5 }} />,
      color: collectionType.color,
      borderColor: collectionType.color,
    };
  };

  const handleDelete = async () => {
    if (
      window.confirm(t("collectionGroups.detailPage.confirmDelete", { name: groupData?.data.name }))
    ) {
      try {
        await deleteGroup.mutateAsync(groupId!);
        navigate("/collections?filter=groups");
      } catch (err) {
        console.error("Failed to delete group:", err);
      }
    }
  };

  const handleAddCollections = async () => {
    if (selectedCollections.length === 0) return;

    try {
      await addCollections.mutateAsync({
        groupId: groupId!,
        collectionIds: selectedCollections,
      });
      setAddDialogOpen(false);
      setSelectedCollections([]);
    } catch (err) {
      console.error("Failed to add collections:", err);
    }
  };

  const handleRemoveCollection = async (e: React.MouseEvent, collectionId: string) => {
    e.stopPropagation();
    if (window.confirm(t("collectionGroups.detailPage.confirmRemove"))) {
      try {
        await removeCollections.mutateAsync({
          groupId: groupId!,
          collectionIds: [collectionId],
        });
      } catch (err) {
        console.error("Failed to remove collection:", err);
      }
    }
  };

  const handleViewCollection = (collectionId: string) => {
    navigate(`/collections/${collectionId}/view`);
  };

  const toggleCollectionSelection = (collectionId: string) => {
    setSelectedCollections((prev) =>
      prev.includes(collectionId)
        ? prev.filter((id) => id !== collectionId)
        : [...prev, collectionId]
    );
  };

  const filteredAvailableCollections = availableCollections.filter(
    (col) =>
      col.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !(groupData?.data?.collectionIds || []).includes(col.id)
  );

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !groupData) {
    return (
      <Box>
        <Alert severity="error">{t("collectionGroups.detailPage.errorLoading")}</Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate("/collections?filter=groups")}
          sx={{ mt: 2 }}
        >
          {t("collectionGroups.detailPage.backToGroups")}
        </Button>
      </Box>
    );
  }

  const group = groupData.data;
  const groupCollections = availableCollections.filter((col) =>
    (group?.collectionIds || []).includes(col.id)
  );

  return (
    <Box>
      <Box>
        {/* Header */}
        <Box display="flex" alignItems="center" gap={2} mb={3}>
          <IconButton onClick={() => navigate("/collections?filter=groups")}>
            <ArrowBackIcon />
          </IconButton>
          <FolderSpecialIcon color="primary" sx={{ fontSize: 40 }} />
          <Box flexGrow={1}>
            <Typography variant="h4" component="h1">
              {group.name}
            </Typography>
            {group.description && (
              <Typography variant="body1" color="text.secondary">
                {group.description}
              </Typography>
            )}
          </Box>
          {group.isOwner && (
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                startIcon={<EditIcon />}
                onClick={() => setEditFormOpen(true)}
              >
                {t("common.actions.edit")}
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDelete}
                disabled={deleteGroup.isPending}
              >
                {t("common.actions.delete")}
              </Button>
            </Box>
          )}
        </Box>

        {/* Group Info */}
        <Card sx={{ mb: 3, borderRadius: 3 }}>
          <CardContent>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.collections")}
                </Typography>
                <Typography variant="h6">{group.collectionCount || 0}</Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.visibility")}
                </Typography>
                <Box mt={0.5}>
                  <Chip
                    label={group.isPublic ? t("common.public") : t("common.private")}
                    size="small"
                    icon={group.isPublic ? <PublicIcon /> : <PrivateIcon />}
                    sx={{
                      height: 22,
                      color: group.isPublic ? "success.dark" : theme.palette.primary.main,
                      bgcolor: group.isPublic
                        ? alpha(theme.palette.success.main, 0.08)
                        : alpha(theme.palette.primary.main, 0.1),
                      border: `1px solid ${
                        group.isPublic ? theme.palette.success.dark : theme.palette.primary.main
                      }`,
                      "& .MuiChip-icon": {
                        color: group.isPublic ? "success.dark" : theme.palette.primary.main,
                        fontSize: 14,
                      },
                    }}
                  />
                </Box>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.created")}
                </Typography>
                <Typography variant="body2">{formatDate(group.createdAt)}</Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Collections in Group */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h5">
            {t("collectionGroups.detailPage.collectionsInGroup")}
          </Typography>
          {group.isOwner && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setAddDialogOpen(true)}
            >
              {t("collectionGroups.detailPage.addCollections")}
            </Button>
          )}
        </Box>

        {groupCollections.length === 0 ? (
          <Card sx={{ borderRadius: 3 }}>
            <CardContent>
              <Box textAlign="center" py={4}>
                <Typography variant="body1" color="text.secondary" gutterBottom>
                  {t("collectionGroups.detailPage.noCollectionsYet")}
                </Typography>
                {group.isOwner && (
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setAddDialogOpen(true)}
                    sx={{ mt: 2 }}
                  >
                    {t("collectionGroups.detailPage.addCollections")}
                  </Button>
                )}
              </Box>
            </CardContent>
          </Card>
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
              pt: 0.5,
            }}
          >
            {groupCollections.map((collection) => {
              const style = getCollectionStyle(collection);
              return (
                <Card
                  key={collection.id}
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    borderRadius: 3,
                    border: "2px solid",
                    borderColor: style.borderColor,
                    overflow: "visible",
                    transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
                    "&:hover": {
                      transform: "translateY(-4px)",
                      boxShadow: theme.shadows[6],
                      cursor: "pointer",
                    },
                  }}
                  onClick={() => handleViewCollection(collection.id)}
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
                        {/* Badges: Public/Private */}
                        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                          <Chip
                            label={collection.isPublic ? t("common.public") : t("common.private")}
                            size="small"
                            icon={collection.isPublic ? <PublicIcon /> : <PrivateIcon />}
                            sx={{
                              height: 22,
                              color: collection.isPublic
                                ? "success.dark"
                                : theme.palette.primary.main,
                              bgcolor: collection.isPublic
                                ? alpha(theme.palette.success.main, 0.08)
                                : alpha(theme.palette.primary.main, 0.1),
                              border: `1px solid ${
                                collection.isPublic
                                  ? theme.palette.success.dark
                                  : theme.palette.primary.main
                              }`,
                              "& .MuiChip-icon": {
                                color: collection.isPublic
                                  ? "success.dark"
                                  : theme.palette.primary.main,
                                fontSize: 14,
                              },
                            }}
                          />
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

                    {/* Description */}
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
                        mt: "auto",
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
                          {collection.itemCount}{" "}
                          {collection.itemCount !== 1 ? t("common.items") : t("common.item")}
                        </Typography>
                      </Box>

                      {/* Created date */}
                      {collection.createdAt && (
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                          }}
                        >
                          <CalendarIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                          <Typography variant="body2" color="text.secondary">
                            {t("common.created")}: {formatDate(collection.createdAt)}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </CardContent>

                  {/* Actions */}
                  {group.isOwner && (
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
                      <Button
                        size="small"
                        color="error"
                        startIcon={<RemoveIcon />}
                        onClick={(e) => handleRemoveCollection(e, collection.id)}
                        disabled={removeCollections.isPending}
                        sx={{ textTransform: "none" }}
                      >
                        {t("collectionGroups.detailPage.removeFromGroup")}
                      </Button>
                    </CardActions>
                  )}
                </Card>
              );
            })}
          </Box>
        )}

        {/* Edit Form Dialog */}
        <CollectionGroupForm
          open={editFormOpen}
          onClose={() => setEditFormOpen(false)}
          group={group}
        />

        {/* Add Collections Dialog */}
        <Dialog
          open={addDialogOpen}
          onClose={() => {
            setAddDialogOpen(false);
            setSelectedCollections([]);
            setSearchQuery("");
          }}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>{t("collectionGroups.detailPage.addCollectionsDialog.title")}</DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              placeholder={t("collectionGroups.detailPage.addCollectionsDialog.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{ mb: 2, mt: 1 }}
            />
            {filteredAvailableCollections.length === 0 ? (
              <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                {searchQuery
                  ? t("collectionGroups.detailPage.addCollectionsDialog.noCollectionsFound")
                  : t("collectionGroups.detailPage.addCollectionsDialog.allInGroup")}
              </Typography>
            ) : (
              <List>
                {filteredAvailableCollections.map((collection) => (
                  <ListItemButton
                    key={collection.id}
                    onClick={() => toggleCollectionSelection(collection.id)}
                  >
                    <Checkbox
                      checked={selectedCollections.includes(collection.id)}
                      tabIndex={-1}
                      disableRipple
                    />
                    <ListItemText
                      primary={collection.name}
                      secondary={`${collection.itemCount} ${
                        collection.itemCount !== 1 ? t("common.items") : t("common.item")
                      }`}
                    />
                  </ListItemButton>
                ))}
              </List>
            )}
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => {
                setAddDialogOpen(false);
                setSelectedCollections([]);
                setSearchQuery("");
              }}
            >
              {t("common.actions.cancel")}
            </Button>
            <Button
              onClick={handleAddCollections}
              variant="contained"
              disabled={selectedCollections.length === 0 || addCollections.isPending}
            >
              {t("collectionGroups.detailPage.addCollectionsDialog.addButton")}{" "}
              {selectedCollections.length > 0 && `(${selectedCollections.length})`}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Box>
  );
};
