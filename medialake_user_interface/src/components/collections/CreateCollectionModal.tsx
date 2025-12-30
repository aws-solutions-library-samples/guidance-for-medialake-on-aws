import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Box,
  CircularProgress,
  Alert,
} from "@mui/material";
import {
  useCreateCollection,
  useGetCollections,
  useGetCollectionTypes,
} from "../../api/hooks/useCollections";

interface CreateCollectionModalProps {
  open: boolean;
  onClose: () => void;
  defaultParentId?: string;
}

export const CreateCollectionModal: React.FC<CreateCollectionModalProps> = ({
  open,
  onClose,
  defaultParentId,
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    parentId: defaultParentId || "",
    isPublic: false,
    collectionTypeId: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // API hooks
  const createCollectionMutation = useCreateCollection();
  const { data: collectionsResponse } = useGetCollections();
  const { data: collectionTypesResponse } = useGetCollectionTypes();

  const collections = collectionsResponse?.data || [];
  const collectionTypes = collectionTypesResponse?.data || [];

  const handleInputChange = (field: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  const handleSelectChange = (field: string) => (event: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: event.target.value,
    }));
    // Clear error when user makes selection
    if (errors[field]) {
      setErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    // Name validation
    if (!formData.name.trim()) {
      newErrors.name = t("collectionsPage.form.validation.nameRequired");
    } else if (formData.name.trim().length < 2) {
      newErrors.name = t("collectionsPage.form.validation.nameMinLength");
    } else if (formData.name.trim().length > 100) {
      newErrors.name = t("collectionsPage.form.validation.nameMaxLength");
    }

    // Description validation
    if (formData.description && formData.description.length > 500) {
      newErrors.description = t("collectionsPage.form.validation.descriptionMaxLength");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      const createData = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        parentId: formData.parentId || undefined,
        isPublic: formData.isPublic,
        collectionTypeId: formData.collectionTypeId || undefined,
      };

      await createCollectionMutation.mutateAsync(createData);

      // Reset form and close modal
      setFormData({
        name: "",
        description: "",
        parentId: defaultParentId || "",
        isPublic: false,
        collectionTypeId: "",
      });
      setErrors({});
      onClose();
    } catch (error) {
      console.error("Failed to create collection:", error);
    }
  };

  const handleClose = () => {
    if (!createCollectionMutation.isPending) {
      setFormData({
        name: "",
        description: "",
        parentId: defaultParentId || "",
        isPublic: false,
        collectionTypeId: "",
      });
      setErrors({});
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle sx={{ fontWeight: 600 }}>{t("collectionsPage.createCollection")}</DialogTitle>

      <DialogContent sx={{ pb: 2 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3, mt: 1 }}>
          {/* Collection Name */}
          <TextField
            fullWidth
            label={t("collectionsPage.form.name")}
            placeholder={t("collectionsPage.form.namePlaceholder")}
            value={formData.name}
            onChange={handleInputChange("name")}
            error={Boolean(errors.name)}
            helperText={errors.name}
            required
            disabled={createCollectionMutation.isPending}
          />

          {/* Description */}
          <TextField
            fullWidth
            label={t("collectionsPage.form.description")}
            placeholder={t("collectionsPage.form.descriptionPlaceholder")}
            value={formData.description}
            onChange={handleInputChange("description")}
            error={Boolean(errors.description)}
            helperText={errors.description}
            multiline
            rows={3}
            disabled={createCollectionMutation.isPending}
          />

          {/* Collection Type */}
          {collectionTypes.length > 0 && (
            <FormControl fullWidth disabled={createCollectionMutation.isPending}>
              <InputLabel>{t("collectionsPage.form.type")}</InputLabel>
              <Select
                value={formData.collectionTypeId}
                label={t("collectionsPage.form.type")}
                onChange={handleSelectChange("collectionTypeId")}
              >
                <MenuItem value="">
                  <em>{t("common.none")}</em>
                </MenuItem>
                {collectionTypes
                  .filter((type) => type.isActive)
                  .map((type) => (
                    <MenuItem key={type.id} value={type.id}>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                        }}
                      >
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: "50%",
                            bgcolor: type.color,
                          }}
                        />
                        {type.name}
                      </Box>
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
          )}

          {/* Parent Collection - Only show if no default parent is set */}
          {!defaultParentId && collections.length > 0 && (
            <FormControl fullWidth disabled={createCollectionMutation.isPending}>
              <InputLabel>{t("collectionsPage.form.parentCollection")}</InputLabel>
              <Select
                value={formData.parentId}
                label={t("collectionsPage.form.parentCollection")}
                onChange={handleSelectChange("parentId")}
              >
                <MenuItem value="">
                  <em>{t("collectionsPage.form.selectParent")}</em>
                </MenuItem>
                {collections.map((collection) => (
                  <MenuItem key={collection.id} value={collection.id}>
                    {collection.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {/* Public/Private Toggle */}
          <FormControlLabel
            control={
              <Switch
                checked={formData.isPublic}
                onChange={handleInputChange("isPublic")}
                disabled={createCollectionMutation.isPending}
              />
            }
            label={t("collectionsPage.form.isPublic")}
          />

          {/* Error Alert */}
          {createCollectionMutation.isError && <Alert severity="error">{t("common.error")}</Alert>}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={handleClose} disabled={createCollectionMutation.isPending}>
          {t("common.cancel")}
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={createCollectionMutation.isPending || !formData.name.trim()}
          startIcon={createCollectionMutation.isPending ? <CircularProgress size={20} /> : null}
        >
          {createCollectionMutation.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
