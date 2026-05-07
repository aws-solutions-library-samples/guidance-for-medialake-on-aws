import React, { useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  alpha,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Folder as FolderIcon,
  Work as WorkIcon,
  Campaign as CampaignIcon,
  Assignment as AssignmentIcon,
  Archive as ArchiveIcon,
  PhotoLibrary as PhotoLibraryIcon,
} from "@mui/icons-material";
import {
  useGetCollectionTypes,
  useDeleteCollectionType,
  type CollectionType,
} from "@/api/hooks/useCollections";
import CollectionTypeFormDialog from "@/components/settings/CollectionTypeFormDialog";
import MigrateCollectionTypeDialog from "@/components/settings/MigrateCollectionTypeDialog";
import { EmptyTableState } from "@/components/common/table";
import { formatRelativeTime, formatLocalDateTime } from "@/shared/utils/dateUtils";

const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <FolderIcon />,
  Work: <WorkIcon />,
  Campaign: <CampaignIcon />,
  Assignment: <AssignmentIcon />,
  Archive: <ArchiveIcon />,
  PhotoLibrary: <PhotoLibraryIcon />,
};

const CollectionTypesManagement: React.FC = () => {
  const { t } = useTranslation();
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [migrateDialogOpen, setMigrateDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<CollectionType | null>(null);

  const { data: typesResponse, isLoading, error } = useGetCollectionTypes();
  const deleteTypeMutation = useDeleteCollectionType();

  const collectionTypes = typesResponse?.data || [];

  const handleCreateClick = () => {
    setSelectedType(null);
    setFormDialogOpen(true);
  };

  const handleEditClick = (type: CollectionType) => {
    setSelectedType(type);
    setFormDialogOpen(true);
  };

  const handleDeleteClick = (type: CollectionType) => {
    if (type.isSystem) {
      alert(
        t("collectionTypes.alerts.cannotDeleteSystem", "Cannot delete system collection types")
      );
      return;
    }

    if (
      window.confirm(
        t("collectionTypes.alerts.confirmDelete", `Are you sure you want to delete "{{name}}"?`, {
          name: type.name,
        })
      )
    ) {
      deleteTypeMutation.mutate(type.id, {
        onError: (error: any) => {
          if (error.response?.status === 409) {
            setSelectedType(type);
            setMigrateDialogOpen(true);
          }
        },
      });
    }
  };

  const handleFormClose = () => {
    setFormDialogOpen(false);
    setSelectedType(null);
  };

  const handleMigrateClose = () => {
    setMigrateDialogOpen(false);
    setSelectedType(null);
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={6}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4}>
        <Typography color="error">{t("errors.failedToLoadCollectionTypes")}</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header — matches ApiKeyManagement layout */}
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
            {t("collectionTypes.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t(
              "collectionTypes.description",
              "Manage collection types for organizing your media assets"
            )}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreateClick}
          sx={{ flexShrink: 0 }}
        >
          {t("collectionTypes.createType")}
        </Button>
      </Box>

      {/* Table */}
      <TableContainer component={Paper} elevation={1} sx={{ borderRadius: 2, overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600, width: 56 }}>{t("common.icon")}</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>{t("common.name")}</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>{t("common.description")}</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>{t("common.labels.status")}</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>
                {t("apiKeys.details.created", "Created")}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600 }}>
                {t("common.labels.actions")}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {collectionTypes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} sx={{ p: 0, border: 0 }}>
                  <EmptyTableState
                    message={t("common.noCollectionTypesFound")}
                    icon={<FolderIcon sx={{ fontSize: 40 }} />}
                    action={
                      <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={handleCreateClick}
                      >
                        {t("collectionTypes.createType")}
                      </Button>
                    }
                  />
                </TableCell>
              </TableRow>
            ) : (
              collectionTypes.map((type) => (
                <TableRow key={type.id} hover sx={{ "&:last-child td": { border: 0 } }}>
                  {/* Icon */}
                  <TableCell>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 36,
                        height: 36,
                        borderRadius: 1,
                        backgroundColor: (theme) =>
                          alpha(type.color || theme.palette.primary.main, 0.12),
                        color: type.color,
                      }}
                    >
                      {ICON_MAP[type.icon] || <FolderIcon />}
                    </Box>
                  </TableCell>

                  {/* Name */}
                  <TableCell>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {type.name}
                      </Typography>
                      {type.isSystem && (
                        <Chip
                          label={t("collectionTypes.labels.system")}
                          size="small"
                          variant="outlined"
                          sx={{ height: 20, fontSize: "0.7rem" }}
                        />
                      )}
                    </Box>
                  </TableCell>

                  {/* Description */}
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        maxWidth: 260,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {type.description || "—"}
                    </Typography>
                  </TableCell>

                  {/* Status */}
                  <TableCell>
                    <Chip
                      label={
                        type.isActive ? t("common.status.active") : t("common.status.inactive")
                      }
                      size="small"
                      color={type.isActive ? "success" : "default"}
                      variant="outlined"
                      sx={{ fontWeight: 500 }}
                    />
                  </TableCell>

                  {/* Created */}
                  <TableCell>
                    {type.createdAt ? (
                      <Tooltip title={formatLocalDateTime(type.createdAt)} arrow>
                        <Typography variant="body2" color="text.secondary">
                          {formatRelativeTime(type.createdAt)}
                        </Typography>
                      </Tooltip>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>

                  {/* Actions */}
                  <TableCell align="right">
                    <Box display="flex" justifyContent="flex-end" gap={0.5}>
                      <Tooltip
                        title={
                          type.isSystem
                            ? t("common.messages.cannotEditSystemTypes")
                            : t("common.messages.editType")
                        }
                      >
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => handleEditClick(type)}
                            disabled={type.isSystem}
                            aria-label={t("common.messages.editType")}
                            sx={{ color: "info.main" }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip
                        title={
                          type.isSystem
                            ? t("common.messages.cannotDeleteSystemTypes")
                            : t("common.messages.deleteType")
                        }
                      >
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => handleDeleteClick(type)}
                            disabled={type.isSystem}
                            aria-label={t("common.messages.deleteType")}
                            sx={{ color: "error.main" }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <CollectionTypeFormDialog
        open={formDialogOpen}
        onClose={handleFormClose}
        type={selectedType}
      />

      <MigrateCollectionTypeDialog
        open={migrateDialogOpen}
        onClose={handleMigrateClose}
        sourceType={selectedType}
        availableTypes={collectionTypes.filter((ct) => ct.id !== selectedType?.id)}
      />
    </Box>
  );
};

export default CollectionTypesManagement;
