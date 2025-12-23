import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import {
  Folder as FolderIcon,
  Work as WorkIcon,
  Campaign as CampaignIcon,
  Assignment as AssignmentIcon,
  Archive as ArchiveIcon,
  PhotoLibrary as PhotoLibraryIcon,
  Collections as CollectionsIcon,
  Category as CategoryIcon,
  Label as LabelIcon,
  Bookmarks as BookmarksIcon,
  Star as StarIcon,
  Favorite as FavoriteIcon,
  Inventory as InventoryIcon,
  Storage as StorageIcon,
  Dashboard as DashboardIcon,
} from "@mui/icons-material";
import {
  useCreateCollectionType,
  useUpdateCollectionType,
  type CollectionType,
} from "@/api/hooks/useCollections";

const AVAILABLE_ICONS = [
  { name: "Folder", icon: <FolderIcon /> },
  { name: "Work", icon: <WorkIcon /> },
  { name: "Campaign", icon: <CampaignIcon /> },
  { name: "Assignment", icon: <AssignmentIcon /> },
  { name: "Archive", icon: <ArchiveIcon /> },
  { name: "PhotoLibrary", icon: <PhotoLibraryIcon /> },
  { name: "Collections", icon: <CollectionsIcon /> },
  { name: "Category", icon: <CategoryIcon /> },
  { name: "Label", icon: <LabelIcon /> },
  { name: "Bookmarks", icon: <BookmarksIcon /> },
  { name: "Star", icon: <StarIcon /> },
  { name: "Favorite", icon: <FavoriteIcon /> },
  { name: "Inventory", icon: <InventoryIcon /> },
  { name: "Storage", icon: <StorageIcon /> },
  { name: "Dashboard", icon: <DashboardIcon /> },
];

const PRESET_COLORS = [
  "#1976d2", // Blue
  "#388e3c", // Green
  "#d32f2f", // Red
  "#f57c00", // Orange
  "#7b1fa2", // Purple
  "#0288d1", // Light Blue
  "#c2185b", // Pink
  "#5d4037", // Brown
  "#616161", // Grey
  "#00796b", // Teal
];

interface CollectionTypeFormDialogProps {
  open: boolean;
  onClose: () => void;
  type: CollectionType | null;
}

const CollectionTypeFormDialog: React.FC<CollectionTypeFormDialogProps> = ({
  open,
  onClose,
  type,
}) => {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(PRESET_COLORS[0]);
  const [icon, setIcon] = useState("Folder");
  const [isActive, setIsActive] = useState(true);

  const createMutation = useCreateCollectionType();
  const updateMutation = useUpdateCollectionType();

  const isEditMode = !!type;

  // Initialize form when dialog opens or type changes
  useEffect(() => {
    if (type) {
      setName(type.name);
      setDescription(type.description || "");
      setColor(type.color);
      setIcon(type.icon);
      setIsActive(type.isActive);
    } else {
      // Reset form for create mode
      setName("");
      setDescription("");
      setColor(PRESET_COLORS[0]);
      setIcon("Folder");
      setIsActive(true);
    }
  }, [type, open]);

  const handleSubmit = () => {
    const data = {
      name: name.trim(),
      description: description.trim() || undefined,
      color,
      icon,
      isActive,
    };

    if (isEditMode && type) {
      updateMutation.mutate(
        { id: type.id, data },
        {
          onSuccess: () => {
            onClose();
          },
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          onClose();
        },
      });
    }
  };

  const handleClose = () => {
    if (!createMutation.isPending && !updateMutation.isPending) {
      onClose();
    }
  };

  const isValid = name.trim().length > 0 && name.trim().length <= 50;
  const isLoading = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEditMode
          ? t("collectionTypes.dialogs.editTitle", "Edit Collection Type")
          : t("collectionTypes.dialogs.createTitle", "Create Collection Type")}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          <TextField
            label={t("collectionTypes.form.name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
            helperText={t("collectionTypes.form.nameHelper", "{{count}}/50 characters", {
              count: name.length,
            })}
            error={name.length > 50}
            autoFocus
          />

          <TextField
            label={t("collectionTypes.form.description")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={2}
            helperText={t("collectionTypes.form.descriptionHelper", "{{count}}/255 characters", {
              count: description.length,
            })}
            error={description.length > 255}
          />

          <FormControl fullWidth>
            <InputLabel>{t("common.icon")}</InputLabel>
            <Select value={icon} label={t("common.icon")} onChange={(e) => setIcon(e.target.value)}>
              {AVAILABLE_ICONS.map((item) => (
                <MenuItem key={item.name} value={item.name}>
                  <Box display="flex" alignItems="center" gap={1}>
                    {item.icon}
                    <Typography>{item.name}</Typography>
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box>
            <Typography variant="body2" gutterBottom>
              {t("collectionTypes.form.color", "Color")}
            </Typography>
            <Box display="flex" gap={1} flexWrap="wrap">
              {PRESET_COLORS.map((presetColor) => (
                <Box
                  key={presetColor}
                  onClick={() => setColor(presetColor)}
                  sx={{
                    width: 40,
                    height: 40,
                    backgroundColor: presetColor,
                    borderRadius: 1,
                    cursor: "pointer",
                    border: color === presetColor ? "3px solid #000" : "1px solid #ddd",
                    transition: "all 0.2s",
                    "&:hover": {
                      transform: "scale(1.1)",
                    },
                  }}
                />
              ))}
            </Box>
            <TextField
              label={t("collectionTypes.form.customColor")}
              value={color}
              onChange={(e) => setColor(e.target.value)}
              fullWidth
              size="small"
              sx={{ mt: 1 }}
              helperText={t("collectionTypes.form.colorFormatHelper")}
              error={!/^#[0-9A-Fa-f]{6}$/.test(color)}
            />
          </Box>

          <FormControlLabel
            control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
            label={t("collectionTypes.form.active")}
          />

          {/* Preview */}
          <Box>
            <Typography variant="body2" gutterBottom>
              {t("collectionTypes.form.preview", "Preview")}
            </Typography>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 2,
                p: 2,
                border: (theme) => `1px solid ${theme.palette.divider}`,
                borderRadius: 1,
                backgroundColor: (theme) => theme.palette.background.paper,
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 48,
                  height: 48,
                  borderRadius: 1,
                  backgroundColor: color + "20",
                  color: color,
                }}
              >
                {AVAILABLE_ICONS.find((i) => i.name === icon)?.icon}
              </Box>
              <Box>
                <Typography variant="body1" fontWeight="medium">
                  {name || t("collectionTypes.form.collectionNamePlaceholder", "Collection Name")}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {description || t("collectionTypes.form.descriptionPlaceholder", "Description")}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isLoading}>
          {t("common.actions.cancel")}
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={!isValid || isLoading}>
          {isLoading
            ? t("common.actions.saving")
            : isEditMode
              ? t("common.actions.update")
              : t("common.actions.create")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CollectionTypeFormDialog;
