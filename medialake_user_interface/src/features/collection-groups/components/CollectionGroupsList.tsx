/**
 * Collection Groups List Component
 * Displays collection groups in a card grid with server-side search, sort, and pagination
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router";
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
  ToggleButtonGroup,
  ToggleButton,
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
  ArrowUpward as AscIcon,
  ArrowDownward as DescIcon,
} from "@mui/icons-material";
import { useCollectionGroups, useDeleteCollectionGroup } from "../hooks/useCollectionGroups";
import { formatDateOnly } from "@/utils/dateFormat";
import AssetPagination from "@/components/shared/AssetPagination";
import type { CollectionGroup } from "../types";

const GROUPS_DEFAULT_PAGE_SIZE = 100;

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

  // Search state with debounce
  const [searchText, setSearchText] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  // Sort state
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(GROUPS_DEFAULT_PAGE_SIZE);

  // Reset to page 1 when search or sort changes
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, sortOrder, pageSize]);

  const { data, isLoading, error } = useCollectionGroups({
    search: debouncedSearch || undefined,
    page,
    pageSize,
    sort: "name",
    sortDirection: sortOrder,
  });
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

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1);
  };

  if (isLoading && !data) {
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
  const totalResults = data?.pagination?.totalResults ?? 0;

  return (
    <Box>
      {/* Search + Sort controls */}
      <Box
        sx={{
          mb: 2.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: 1.5,
        }}
      >
        {/* Sort direction */}
        <ToggleButtonGroup
          value={sortOrder}
          exclusive
          onChange={(_, val) => val && setSortOrder(val)}
          size="small"
          sx={{ height: 36 }}
        >
          <ToggleButton value="asc" sx={{ px: 1.2 }}>
            <AscIcon sx={{ fontSize: 16 }} />
          </ToggleButton>
          <ToggleButton value="desc" sx={{ px: 1.2 }}>
            <DescIcon sx={{ fontSize: 16 }} />
          </ToggleButton>
        </ToggleButtonGroup>

        {/* Search */}
        <TextField
          size="small"
          placeholder={t("collectionGroups.list.searchPlaceholder", "Search groups...")}
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

      {/* Empty state */}
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
            <FolderOpenIcon sx={{ fontSize: 40, color: alpha(theme.palette.primary.main, 0.4) }} />
          </Box>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5, color: "text.primary" }}>
            {searchText
              ? t("collectionGroups.list.noSearchResults", "No matching groups")
              : t("collectionGroups.list.noGroupsYet", "No collection groups yet")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 320 }}>
            {searchText
              ? t("collectionGroups.list.tryDifferentSearch", "Try a different search term")
              : t(
                  "collectionGroups.list.createFirstGroup",
                  "Create your first group to organize collections"
                )}
          </Typography>
          {!searchText && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={onCreateClick}
              sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600, px: 3 }}
            >
              {t("collectionsPage.filters.createGroup", "Create Group")}
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
                  "& .card-actions-overlay": { opacity: 1 },
                },
              }}
              onClick={() => navigate(`/collections/groups/${group.id}`)}
            >
              {/* Thumbnail area */}
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
                    sx={{ fontSize: 56, color: alpha(theme.palette.primary.main, 0.18) }}
                  />
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
                              "&:hover": { bgcolor: theme.palette.background.paper },
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

              {/* Info section */}
              <CardContent sx={{ px: 1.75, pt: 1.25, pb: 1.25, "&:last-child": { pb: 1.25 } }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.25 }}>
                  <FolderSpecialIcon
                    sx={{ fontSize: 18, color: alpha(theme.palette.primary.main, 0.5) }}
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
                    sx={{
                      height: 22,
                      fontSize: "0.68rem",
                      fontWeight: 600,
                      letterSpacing: "0.02em",
                      color: theme.palette.primary.contrastText,
                      bgcolor: group.isPublic
                        ? theme.palette.primary.main
                        : theme.palette.primary.dark,
                      border: "none",
                      boxShadow: `0 1px 3px ${alpha(theme.palette.primary.main, 0.3)}`,
                      "& .MuiChip-icon": {
                        color: theme.palette.primary.contrastText,
                        fontSize: 13,
                      },
                      "& .MuiChip-label": { px: 0.8 },
                    }}
                  />
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {/* Pagination */}
      {totalResults > 0 && (
        <AssetPagination
          page={page}
          pageSize={pageSize}
          totalResults={totalResults}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />
      )}
    </Box>
  );
};
