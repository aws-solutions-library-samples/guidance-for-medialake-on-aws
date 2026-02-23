/**
 * Collection Groups List Component
 * Displays collection groups in a card grid cohesive with the collections page design
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
  InputAdornment,
  IconButton,
  CircularProgress,
  Alert,
  Chip,
  Tooltip,
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
  Collections as CollectionsIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from "@mui/icons-material";
import { useCollectionGroups, useDeleteCollectionGroup } from "../hooks/useCollectionGroups";
import { formatDateOnly } from "@/utils/dateFormat";
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

  const handleDelete = async (e: React.MouseEvent, groupId: string, groupName: string) => {
    e.stopPropagation();
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
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="360px">
        <CircularProgress size={36} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{t("collectionGroups.list.errorLoading")}</Alert>;
  }

  const groups = data?.data || [];

  return (
    <Box>
      {/* Search — matches the collections page search style */}
      <Box sx={{ mb: 2.5, display: "flex", justifyContent: "flex-end" }}>
        <TextField
          size="small"
          placeholder={t("collectionGroups.list.searchPlaceholder", "Search groups...")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
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
            endAdornment: search ? (
              <InputAdornment position="end">
                <IconButton size="small" onClick={() => setSearch("")} sx={{ p: 0.25 }}>
                  <ClearIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </InputAdornment>
            ) : null,
          }}
        />
      </Box>

      {/* Empty state — matches collections empty state */}
      {groups.length === 0 ? (
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
            <FolderOpenIcon
              sx={{
                fontSize: 40,
                color: alpha(theme.palette.primary.main, 0.4),
              }}
            />
          </Box>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5, color: "text.primary" }}>
            {search
              ? t("collectionGroups.list.noSearchResults", "No matching groups")
              : t("collectionGroups.list.noGroupsYet", "No collection groups yet")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 320 }}>
            {search
              ? t("collectionGroups.list.tryDifferentSearch", "Try a different search term")
              : t(
                  "collectionGroups.list.createFirstGroup",
                  "Create your first group to organize collections"
                )}
          </Typography>
          {!search && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={onCreateClick}
              sx={{
                borderRadius: 2,
                textTransform: "none",
                fontWeight: 600,
                px: 3,
              }}
            >
              {t("collectionsPage.filters.createGroup", "Create Group")}
            </Button>
          )}
        </Box>
      ) : (
        /* Card grid — matches collection cards layout */
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
          {groups.map((group) => (
            <Card
              key={group.id}
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
              onClick={() => navigate(`/collections/groups/${group.id}`)}
            >
              {/* Thumbnail area — gradient with icon */}
              <Box sx={{ p: 1.25, pb: 0 }}>
                <Box
                  sx={{
                    height: 180,
                    borderRadius: 2.5,
                    overflow: "hidden",
                    position: "relative",
                    background: `linear-gradient(135deg, ${alpha(
                      theme.palette.primary.main,
                      0.08
                    )} 0%, ${alpha(theme.palette.primary.light, 0.04)} 100%)`,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 1.5,
                  }}
                >
                  <FolderSpecialIcon
                    sx={{
                      fontSize: 56,
                      color: alpha(theme.palette.primary.main, 0.18),
                    }}
                  />

                  {/* Collection count pill */}
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      px: 1.5,
                      py: 0.4,
                      borderRadius: 5,
                      bgcolor: alpha(theme.palette.primary.main, 0.08),
                      border: "1px solid",
                      borderColor: alpha(theme.palette.primary.main, 0.12),
                    }}
                  >
                    <CollectionsIcon
                      sx={{ fontSize: 14, color: alpha(theme.palette.primary.main, 0.6) }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 600,
                        fontSize: "0.72rem",
                        color: alpha(theme.palette.primary.main, 0.7),
                      }}
                    >
                      {group.collectionCount}{" "}
                      {group.collectionCount === 1
                        ? t("collectionGroups.list.collection", "collection")
                        : t("collectionGroups.list.collections", "collections")}
                    </Typography>
                  </Box>

                  {/* Action buttons overlay */}
                  {group.isOwner && (
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
                          icon: <EditIcon sx={{ fontSize: 15 }} />,
                          tip: t("common.edit", "Edit"),
                          handler: (e: React.MouseEvent) => {
                            e.stopPropagation();
                            onEditClick?.(group);
                          },
                          color: "text.primary",
                        },
                        {
                          icon: <DeleteIcon sx={{ fontSize: 15 }} />,
                          tip: t("common.delete", "Delete"),
                          handler: (e: React.MouseEvent) => handleDelete(e, group.id, group.name),
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
                            onClick={handler}
                            disabled={tip === t("common.delete", "Delete") && deleteGroup.isPending}
                          >
                            {icon}
                          </Button>
                        </Tooltip>
                      ))}
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Info section — matches collection card info */}
              <CardContent sx={{ px: 1.75, pt: 1.25, pb: 1.25, "&:last-child": { pb: 1.25 } }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.25 }}>
                  <FolderSpecialIcon
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
                    {group.name}
                  </Typography>
                </Box>

                {/* Description */}
                {group.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      display: "-webkit-box",
                      WebkitLineClamp: 1,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      fontSize: "0.75rem",
                      mb: 0.5,
                      lineHeight: 1.4,
                    }}
                  >
                    {group.description}
                  </Typography>
                )}

                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.75rem" }}>
                    {group.collectionCount}{" "}
                    {group.collectionCount === 1
                      ? t("collectionGroups.list.collection", "collection")
                      : t("collectionGroups.list.collections", "collections")}
                    {group.createdAt && ` · ${formatDateOnly(group.createdAt)}`}
                  </Typography>
                  <Chip
                    label={
                      group.isPublic ? t("common.public", "Public") : t("common.private", "Private")
                    }
                    size="small"
                    icon={group.isPublic ? <PublicIcon /> : <PrivateIcon />}
                    variant="outlined"
                    sx={{
                      height: 22,
                      fontSize: "0.68rem",
                      fontWeight: 500,
                      color: group.isPublic ? "success.main" : "text.secondary",
                      borderColor: group.isPublic
                        ? alpha(theme.palette.success.main, 0.35)
                        : alpha(theme.palette.text.secondary, 0.15),
                      bgcolor: group.isPublic
                        ? alpha(theme.palette.success.main, 0.06)
                        : "transparent",
                      "& .MuiChip-icon": {
                        color: group.isPublic ? "success.main" : "text.secondary",
                        fontSize: 13,
                      },
                    }}
                  />
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
};
