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
  Typography,
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

  // Fetch collection types
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

    // Check if type is in use (you may want to add a usage count API)
    if (
      window.confirm(
        t("collectionTypes.alerts.confirmDelete", `Are you sure you want to delete "{{name}}"?`, {
          name: type.name,
        })
      )
    ) {
      deleteTypeMutation.mutate(type.id, {
        onError: (error: any) => {
          // Handle TYPE_IN_USE error
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
      <Box display="flex" justifyContent="center" alignItems="center" p={4}>
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
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6" gutterBottom>
            {t("collectionTypes.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t(
              "collectionTypes.description",
              "Manage collection types for organizing your media assets"
            )}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreateClick}>
          {t("collectionTypes.createType")}
        </Button>
      </Box>

      <TableContainer component={Paper} elevation={1}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t("common.icon")}</TableCell>
              <TableCell>{t("common.name")}</TableCell>
              <TableCell>{t("common.description")}</TableCell>
              <TableCell>{t("common.labels.status")}</TableCell>
              <TableCell align="right">{t("common.labels.actions")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {collectionTypes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} sx={{ p: 0, border: 0 }}>
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
                <TableRow key={type.id} hover>
                  <TableCell>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 40,
                        height: 40,
                        borderRadius: 1,
                        backgroundColor: type.color + "20",
                        color: type.color,
                      }}
                    >
                      {ICON_MAP[type.icon] || <FolderIcon />}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box>
                      <Typography variant="body1" fontWeight="medium">
                        {type.name}
                      </Typography>
                      {type.isSystem && (
                        <Chip
                          label={t("collectionTypes.labels.system")}
                          size="small"
                          sx={{ mt: 0.5 }}
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        maxWidth: 300,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {type.description || "—"}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={
                        type.isActive ? t("common.status.active") : t("common.status.inactive")
                      }
                      size="small"
                      color={type.isActive ? "success" : "default"}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={() => handleEditClick(type)}
                      disabled={type.isSystem}
                      title={
                        type.isSystem
                          ? t("common.messages.cannotEditSystemTypes")
                          : t("common.messages.editType")
                      }
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteClick(type)}
                      disabled={type.isSystem}
                      title={
                        type.isSystem
                          ? t("common.messages.cannotDeleteSystemTypes")
                          : t("common.messages.deleteType")
                      }
                      color="error"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
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
        availableTypes={collectionTypes.filter((t) => t.id !== selectedType?.id)}
      />
    </Box>
  );
};

export default CollectionTypesManagement;
