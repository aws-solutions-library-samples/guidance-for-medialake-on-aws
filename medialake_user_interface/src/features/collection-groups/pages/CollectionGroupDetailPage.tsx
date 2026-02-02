/**
 * Collection Group Detail Page
 * Shows group details and allows managing collections within the group
 */

import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
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
import { CollectionGroupForm } from "../components/CollectionGroupForm";
import type { CollectionGroup } from "../types";

export const CollectionGroupDetailPage: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: groupData, isLoading, error } = useCollectionGroup(groupId!);
  const deleteGroup = useDeleteCollectionGroup();
  const addCollections = useAddCollectionsToGroup();
  const removeCollections = useRemoveCollectionsFromGroup();

  // Mock collections data - in real implementation, fetch from API
  const [availableCollections] = useState([
    { id: "col_1", name: "Marketing Assets 2024", itemCount: 45 },
    { id: "col_2", name: "Product Photos", itemCount: 128 },
    { id: "col_3", name: "Video Archive", itemCount: 67 },
    { id: "col_4", name: "Brand Guidelines", itemCount: 23 },
    { id: "col_5", name: "Social Media Content", itemCount: 89 },
  ]);

  const handleDelete = async () => {
    if (window.confirm(`Are you sure you want to delete "${groupData?.data.name}"?`)) {
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
    if (window.confirm("Remove this collection from the group?")) {
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
          <Alert severity="error">Error loading collection group. Please try again.</Alert>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate("/collection-groups")}
            sx={{ mt: 2 }}
          >
            Back to Groups
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
                Edit
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDelete}
                disabled={deleteGroup.isPending}
              >
                Delete
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
                  Collections
                </Typography>
                <Typography variant="h6">{group.collectionCount || 0}</Typography>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="text.secondary">
                  Visibility
                </Typography>
                <Box mt={0.5}>
                  <Chip
                    label={group.isPublic ? "Public" : "Private"}
                    size="small"
                    color={group.isPublic ? "success" : "default"}
                  />
                </Box>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="text.secondary">
                  Created
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
          <Typography variant="h5">Collections in this Group</Typography>
          {group.isOwner && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setAddDialogOpen(true)}
            >
              Add Collections
            </Button>
          )}
        </Box>

        {groupCollections.length === 0 ? (
          <Card>
            <CardContent>
              <Box textAlign="center" py={4}>
                <Typography variant="body1" color="text.secondary" gutterBottom>
                  No collections in this group yet
                </Typography>
                {group.isOwner && (
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setAddDialogOpen(true)}
                    sx={{ mt: 2 }}
                  >
                    Add Collections
                  </Button>
                )}
              </Box>
            </CardContent>
          </Card>
        ) : (
          <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(300px, 1fr))" gap={2}>
            {groupCollections.map((collection) => (
              <Card key={collection.id}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                    <Box flexGrow={1}>
                      <Typography variant="h6" gutterBottom>
                        {collection.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {collection.itemCount} items
                      </Typography>
                    </Box>
                    {group.isOwner && (
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveCollection(collection.id)}
                        disabled={removeCollections.isPending}
                        title="Remove from group"
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
          <DialogTitle>Add Collections to Group</DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              placeholder="Search collections..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{ mb: 2, mt: 1 }}
            />
            {filteredAvailableCollections.length === 0 ? (
              <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                {searchQuery ? "No collections found" : "All collections are already in this group"}
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
                      secondary={`${collection.itemCount} items`}
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
              Cancel
            </Button>
            <Button
              onClick={handleAddCollections}
              variant="contained"
              disabled={selectedCollections.length === 0 || addCollections.isPending}
            >
              Add {selectedCollections.length > 0 && `(${selectedCollections.length})`}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};
