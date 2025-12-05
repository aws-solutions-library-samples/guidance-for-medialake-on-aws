import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
  Alert,
} from "@mui/material";
import {
  Folder as FolderIcon,
  Work as WorkIcon,
  Campaign as CampaignIcon,
  Assignment as AssignmentIcon,
  Archive as ArchiveIcon,
  PhotoLibrary as PhotoLibraryIcon,
} from "@mui/icons-material";
import {
  useMigrateCollectionType,
  useDeleteCollectionType,
  type CollectionType,
} from "@/api/hooks/useCollections";

const ICON_MAP: Record<string, React.ReactElement> = {
  Folder: <FolderIcon />,
  Work: <WorkIcon />,
  Campaign: <CampaignIcon />,
  Assignment: <AssignmentIcon />,
  Archive: <ArchiveIcon />,
  PhotoLibrary: <PhotoLibraryIcon />,
};

interface MigrateCollectionTypeDialogProps {
  open: boolean;
  onClose: () => void;
  sourceType: CollectionType | null;
  availableTypes: CollectionType[];
}

const MigrateCollectionTypeDialog: React.FC<MigrateCollectionTypeDialogProps> = ({
  open,
  onClose,
  sourceType,
  availableTypes,
}) => {
  const { t } = useTranslation();
  const [targetTypeId, setTargetTypeId] = useState("");

  const migrateMutation = useMigrateCollectionType();
  const deleteMutation = useDeleteCollectionType();

  const handleMigrate = async () => {
    if (!sourceType || !targetTypeId) return;

    try {
      await migrateMutation.mutateAsync({
        sourceTypeId: sourceType.id,
        targetTypeId,
      });

      // After successful migration, try to delete the source type
      await deleteMutation.mutateAsync(sourceType.id);

      onClose();
    } catch (error) {
      console.error("Migration failed:", error);
    }
  };

  const handleClose = () => {
    if (!migrateMutation.isPending && !deleteMutation.isPending) {
      setTargetTypeId("");
      onClose();
    }
  };

  const isLoading = migrateMutation.isPending || deleteMutation.isPending;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("collectionTypes.dialogs.migrateTitle")}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          <Alert severity="warning">
            This collection type is in use and cannot be deleted directly. You must first migrate
            all collections to another type.
          </Alert>

          {sourceType && (
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Source Type
              </Typography>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  p: 2,
                  border: "1px solid #ddd",
                  borderRadius: 1,
                  backgroundColor: "#f5f5f5",
                }}
              >
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 40,
                    height: 40,
                    borderRadius: 1,
                    backgroundColor: sourceType.color + "20",
                    color: sourceType.color,
                  }}
                >
                  {ICON_MAP[sourceType.icon] || <FolderIcon />}
                </Box>
                <Typography variant="body1" fontWeight="medium">
                  {sourceType.name}
                </Typography>
              </Box>
            </Box>
          )}

          <FormControl fullWidth>
            <InputLabel>{t("migrateCollectionType.targetType")}</InputLabel>
            <Select
              value={targetTypeId}
              label={t("migrateCollectionType.targetType")}
              onChange={(e) => setTargetTypeId(e.target.value)}
            >
              {availableTypes
                .filter((t) => t.isActive)
                .map((type) => (
                  <MenuItem key={type.id} value={type.id}>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 24,
                          height: 24,
                          borderRadius: 0.5,
                          backgroundColor: type.color + "20",
                          color: type.color,
                          fontSize: "0.875rem",
                        }}
                      >
                        {ICON_MAP[type.icon] || <FolderIcon fontSize="small" />}
                      </Box>
                      <Typography>{type.name}</Typography>
                    </Box>
                  </MenuItem>
                ))}
            </Select>
          </FormControl>

          {targetTypeId && (
            <Alert severity="info">
              All collections will be migrated to the selected type, and the source type will be
              deleted.
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleMigrate}
          variant="contained"
          color="primary"
          disabled={!targetTypeId || isLoading}
        >
          {isLoading ? "Migrating..." : "Migrate & Delete"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default MigrateCollectionTypeDialog;
