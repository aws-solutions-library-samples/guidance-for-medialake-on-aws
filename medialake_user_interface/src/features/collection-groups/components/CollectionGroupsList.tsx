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
  CardActions,
  Typography,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Chip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  FolderSpecial as FolderSpecialIcon,
  FolderOpen as FolderOpenIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  CalendarToday as CalendarIcon,
  Collections as CollectionsIcon,
} from "@mui/icons-material";
import { useCollectionGroups, useDeleteCollectionGroup } from "../hooks/useCollectionGroups";
import { formatDate } from "@/utils/dateFormat";
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
  const theme = useTheme();
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
          <FolderOpenIcon
            sx={{ fontSize: 64, color: alpha(theme.palette.text.secondary, 0.5), mb: 2 }}
          />
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
          {groups.map((group) => (
            <Card
              key={group.id}
              sx={{
                display: "flex",
                flexDirection: "column",
                borderRadius: 3,
                border: "2px solid",
                borderColor: theme.palette.primary.main,
                overflow: "visible",
                transition: "transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out",
                "&:hover": {
                  transform: "translateY(-4px)",
                  boxShadow: theme.shadows[6],
                  cursor: "pointer",
                },
              }}
              onClick={() => navigate(`/collections/groups/${group.id}`)}
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
                  <FolderSpecialIcon
                    sx={{ color: theme.palette.primary.main, fontSize: 32, mr: 1.5 }}
                  />
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
                      {group.name}
                    </Typography>
                    {/* Badges: Public/Private */}
                    <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                      <Chip
                        label={group.isPublic ? t("common.public") : t("common.private")}
                        size="small"
                        icon={group.isPublic ? <PublicIcon /> : <PrivateIcon />}
                        sx={{
                          height: 22,
                          color: group.isPublic ? "#2e7d32" : theme.palette.primary.main,
                          bgcolor: group.isPublic
                            ? "#e8f5e8"
                            : alpha(theme.palette.primary.main, 0.1),
                          border: `1px solid ${
                            group.isPublic ? "#2e7d32" : theme.palette.primary.main
                          }`,
                          "& .MuiChip-icon": {
                            color: group.isPublic ? "#2e7d32" : theme.palette.primary.main,
                            fontSize: 14,
                          },
                        }}
                      />
                      {group.userRole && group.userRole !== "owner" && (
                        <Chip
                          label={group.userRole}
                          size="small"
                          sx={{
                            height: 22,
                            color: theme.palette.info.main,
                            bgcolor: alpha(theme.palette.info.main, 0.1),
                            border: `1px solid ${theme.palette.info.main}`,
                          }}
                        />
                      )}
                    </Box>
                  </Box>
                </Box>

                {/* Description */}
                <Box
                  sx={{
                    minHeight: group.description ? "40px" : "0px",
                    mb: 2,
                  }}
                >
                  {group.description && (
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
                      {group.description}
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
                  {/* Collection count */}
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                    }}
                  >
                    <CollectionsIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                    <Typography variant="body2" color="text.secondary">
                      {t("collectionGroups.list.collectionCount", { count: group.collectionCount })}
                    </Typography>
                  </Box>

                  {/* Created date */}
                  {group.createdAt && (
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <CalendarIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                      <Typography variant="body2" color="text.secondary">
                        {t("common.created")}: {formatDate(group.createdAt)}
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
                    startIcon={<EditIcon />}
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditClick?.(group);
                    }}
                    sx={{ textTransform: "none" }}
                  >
                    {t("common.edit")}
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(group.id, group.name);
                    }}
                    disabled={deleteGroup.isPending}
                    sx={{ textTransform: "none" }}
                  >
                    {t("common.delete")}
                  </Button>
                </CardActions>
              )}
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
};
