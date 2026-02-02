/**
 * Collection Group Detail Page
 * Shows group details and allows managing collections within the group
 */

import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Container,
  Typography,
  Button,
  Card,
  CardContent,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Checkbox,
  TextField,
  Grid,
} from "@mui/material";
import {
  ArrowBack as ArrowBackIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Folder as FolderIcon,
} from "@mui/icons-material";
import {
  useCollectionGroup,
  useDeleteCollectionGroup,
  useAddCollectionsToGroup,
  useRemoveCollectionsFromGroup,
} from "../hooks/useCollectionGroups";
import { useGetCollections } from "@/api/hooks/useCollections";
import { CollectionGroupForm } from "../components/CollectionGroupForm";
import type { CollectionGroup } from "../types";

export const CollectionGroupDetailPage: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: groupData, isLoading, error } = useCollectionGroup(groupId!);
  const { data: collectionsData, isLoading: isLoadingCollections } = useGetCollections();
  const deleteGroup = useDeleteCollectionGroup();
  const addCollections = useAddCollectionsToGroup();
  const removeCollections = useRemoveCollectionsFromGroup();

  // Get all available collections from API
  const availableCollections = collectionsData?.data || [];

  const handleDelete = async () => {
    if (
      window.confirm(t("collectionGroups.detailPage.confirmDelete", { name: groupData?.data.name }))
    ) {
      try {
        await deleteGroup.mutateAsync(groupId!);
        navigate("/collection-groups");
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

  const handleRemoveCollection = async (collectionId: string) => {
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
      <Container maxWidth="lg">
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !groupData) {
    return (
      <Container maxWidth="lg">
        <Box py={4}>
          <Alert severity="error">{t("collectionGroups.detailPage.errorLoading")}</Alert>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate("/collection-groups")}
            sx={{ mt: 2 }}
          >
            {t("collectionGroups.detailPage.backToGroups")}
          </Button>
        </Box>
      </Container>
    );
  }

  const group = groupData.data;
  const groupCollections = availableCollections.filter((col) =>
    (group?.collectionIds || []).includes(col.id)
  );

  return (
    <Container maxWidth="lg">
      <Box py={4}>
        {/* Header */}
        <Box display="flex" alignItems="center" gap={2} mb={3}>
          <IconButton onClick={() => navigate("/collection-groups")}>
            <ArrowBackIcon />
          </IconButton>
          <FolderIcon color="primary" sx={{ fontSize: 40 }} />
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
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.collections")}
                </Typography>
                <Typography variant="h6">{group.collectionCount || 0}</Typography>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.visibility")}
                </Typography>
                <Box mt={0.5}>
                  <Chip
                    label={group.isPublic ? t("common.public") : t("common.private")}
                    size="small"
                    color={group.isPublic ? "success" : "default"}
                  />
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="text.secondary">
                  {t("collectionGroups.detailPage.info.created")}
                </Typography>
                <Typography variant="body2">
                  {new Date(group.createdAt).toLocaleDateString()}
                </Typography>
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
          <Card>
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
            display="grid"
            sx={{
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(auto-fill, minmax(300px, 1fr))",
              },
            }}
            gap={2}
          >
            {groupCollections.map((collection) => (
              <Card key={collection.id}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box flexGrow={1}>
                      <Typography variant="h6" gutterBottom>
                        {collection.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {collection.itemCount} {t("common.items")}
                      </Typography>
                    </Box>
                    {group.isOwner && (
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveCollection(collection.id)}
                        disabled={removeCollections.isPending}
                        title={t("collectionGroups.detailPage.removeFromGroup")}
                      >
                        <RemoveIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </CardContent>
              </Card>
            ))}
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
                      secondary={t("common.items", { count: collection.itemCount })}
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
    </Container>
  );
};
