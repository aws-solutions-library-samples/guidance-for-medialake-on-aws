/**
 * Collection Groups List Component
 * Displays a list of collection groups with search and pagination
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useCollectionGroups({ search, limit: 20 });
  const deleteGroup = useDeleteCollectionGroup();

  const handleDelete = async (groupId: string, groupName: string) => {
    if (window.confirm(t("collectionGroups.list.confirmDelete", { name: groupName }))) {
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
    return <Alert severity="error">{t("collectionGroups.list.errorLoading")}</Alert>;
  }

  const groups = data?.data || [];

  return (
    <Box>
      {/* Search */}
      <Box mb={3}>
        <TextField
          fullWidth
          placeholder={t("collectionGroups.list.searchPlaceholder")}
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
            {t("collectionGroups.list.noGroupsYet")}
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            {t("collectionGroups.list.createFirstGroup")}
          </Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={onCreateClick}>
            {t("collectionsPage.filters.createGroup")}
          </Button>
        </Box>
      ) : (
        <Box
          display="grid"
          sx={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}
          gap={2}
        >
          {groups.map((group) => (
            <Card
              key={group.id}
              sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                transition: "transform 0.2s, box-shadow 0.2s",
                cursor: "pointer",
                "&:hover": {
                  transform: "translateY(-4px)",
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate(`/collections/groups/${group.id}`)}
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
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditClick?.(group);
                        }}
                        title={t("collectionGroups.list.editGroup")}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(group.id, group.name);
                        }}
                        title={t("collectionGroups.list.deleteGroup")}
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
                    label={t("collectionGroups.list.collectionCount", {
                      count: group.collectionCount,
                    })}
                    size="small"
                    variant="outlined"
                  />
                  {group.isPublic && (
                    <Chip
                      label={t("common.public")}
                      size="small"
                      color="success"
                      variant="outlined"
                    />
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
