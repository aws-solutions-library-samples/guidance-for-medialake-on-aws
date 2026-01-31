/**
 * Collection Groups List Component
 * Displays a list of collection groups with search and pagination
 */

import React, { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  CircularProgress,
  Alert,
  IconButton,
  Chip,
} from "@mui/material";
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Folder as FolderIcon,
} from "@mui/icons-material";
import { useCollectionGroups, useDeleteCollectionGroup } from "../hooks/useCollectionGroups";
import type { CollectionGroup } from "../types";

interface CollectionGroupsListProps {
  onCreateClick?: () => void;
  onEditClick?: (group: CollectionGroup) => void;
}

export const CollectionGroupsList: React.FC<CollectionGroupsListProps> = ({
  onCreateClick,
  onEditClick,
}) => {
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useCollectionGroups({ search, limit: 20 });
  const deleteGroup = useDeleteCollectionGroup();

  const handleDelete = async (groupId: string, groupName: string) => {
    if (window.confirm(`Are you sure you want to delete "${groupName}"?`)) {
      try {
        await deleteGroup.mutateAsync(groupId);
      } catch (err) {
        console.error("Failed to delete group:", err);
      }
    }
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">Error loading collection groups. Please try again.</Alert>;
  }

  const groups = data?.data || [];

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Collection Groups
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={onCreateClick}>
          Create Group
        </Button>
      </Box>

      {/* Search */}
      <Box mb={3}>
        <TextField
          fullWidth
          placeholder="Search groups..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          variant="outlined"
        />
      </Box>

      {/* Groups List */}
      {groups.length === 0 ? (
        <Box textAlign="center" py={8}>
          <FolderIcon sx={{ fontSize: 80, color: "grey.400", mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No collection groups yet
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Create your first group to organize collections
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={onCreateClick}>
            Create Group
          </Button>
        </Box>
      ) : (
        <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(300px, 1fr))" gap={2}>
          {groups.map((group) => (
            <Card
              key={group.id}
              sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "transform 0.2s, box-shadow 0.2s",
                "&:hover": {
                  transform: "translateY(-4px)",
                  boxShadow: 4,
                },
              }}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <FolderIcon color="primary" />
                    <Typography variant="h6" component="h2" noWrap>
                      {group.name}
                    </Typography>
                  </Box>
                  {group.isOwner && (
                    <Box>
                      <IconButton
                        size="small"
                        onClick={() => onEditClick?.(group)}
                        title="Edit group"
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(group.id, group.name)}
                        title="Delete group"
                        disabled={deleteGroup.isPending}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  )}
                </Box>

                {group.description && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    mb={2}
                    sx={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    {group.description}
                  </Typography>
                )}

                <Box display="flex" gap={1} flexWrap="wrap" mt="auto">
                  <Chip
                    label={`${group.collectionCount} collection${
                      group.collectionCount !== 1 ? "s" : ""
                    }`}
                    size="small"
                    variant="outlined"
                  />
                  {group.isPublic && (
                    <Chip label="Public" size="small" color="success" variant="outlined" />
                  )}
                  {group.userRole && group.userRole !== "owner" && (
                    <Chip label={group.userRole} size="small" variant="outlined" />
                  )}
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
};
