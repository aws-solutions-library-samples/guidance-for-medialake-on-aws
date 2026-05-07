/**
 * Collection Group Form Component
 * Form for creating or editing a collection group
 * Styled to match the CreateCollectionModal design
 */

import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  TextField,
  Switch,
  Box,
  CircularProgress,
  Alert,
  Typography,
  IconButton,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Close as CloseIcon,
  Add as AddIcon,
  Edit as EditIcon,
  FolderSpecial as FolderSpecialIcon,
  Public as PublicIcon,
} from "@mui/icons-material";
import { useForm, Controller } from "react-hook-form";
import { useCreateCollectionGroup, useUpdateCollectionGroup } from "../hooks/useCollectionGroups";
import type { CollectionGroup, CreateGroupRequest, UpdateGroupRequest } from "../types";

interface CollectionGroupFormProps {
  open: boolean;
  onClose: () => void;
  group?: CollectionGroup | null;
}

interface FormData {
  name: string;
  description: string;
}

export const CollectionGroupForm: React.FC<CollectionGroupFormProps> = ({
  open,
  onClose,
  group,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const isEditMode = !!group;
  const createGroup = useCreateCollectionGroup();
  const updateGroup = useUpdateCollectionGroup();

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    defaultValues: {
      name: "",
      description: "",
    },
  });

  // Reset form when group changes or dialog opens
  useEffect(() => {
    if (open) {
      if (group) {
        reset({
          name: group.name,
          description: group.description || "",
        });
      } else {
        reset({
          name: "",
          description: "",
        });
      }
    }
  }, [open, group, reset]);

  const isPending = createGroup.isPending || updateGroup.isPending;

  const onSubmit = async (data: FormData) => {
    try {
      if (isEditMode && group) {
        const updateData: UpdateGroupRequest = {
          name: data.name,
          description: data.description || undefined,
          isPublic: true,
        };
        await updateGroup.mutateAsync({ groupId: group.id, data: updateData });
      } else {
        const createData: CreateGroupRequest = {
          name: data.name,
          description: data.description || undefined,
          isPublic: true,
        };
        await createGroup.mutateAsync(createData);
      }
      onClose();
    } catch (error) {
      console.error("Failed to save group:", error);
    }
  };

  const handleClose = () => {
    if (!isPending) onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            borderRadius: 3,
            bgcolor: "background.paper",
            backgroundImage: "none",
            overflow: "hidden",
            maxHeight: "85vh",
          },
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          pt: 2.5,
          pb: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.2 }}>
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.primary.main, isDark ? 0.15 : 0.1),
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {isEditMode ? (
              <EditIcon sx={{ fontSize: 18, color: "primary.main" }} />
            ) : (
              <AddIcon sx={{ fontSize: 18, color: "primary.main" }} />
            )}
          </Box>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              fontSize: "1.1rem",
              letterSpacing: "-0.01em",
            }}
          >
            {isEditMode
              ? t("collectionGroups.form.editTitle", "Edit Collection Group")
              : t("collectionGroups.form.createTitle", "Create Collection Group")}
          </Typography>
        </Box>
        <IconButton
          onClick={handleClose}
          disabled={isPending}
          size="small"
          sx={{
            color: "text.secondary",
            "&:hover": { bgcolor: alpha(theme.palette.text.secondary, 0.08) },
          }}
          aria-label="Close dialog"
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <DialogContent sx={{ p: 0, display: "flex", flexDirection: "column" }}>
        <form onSubmit={handleSubmit(onSubmit)}>
          <Box sx={{ px: 3, pt: 2.5, pb: 2, display: "flex", flexDirection: "column", gap: 2.5 }}>
            {/* Group icon preview */}
            <Box sx={{ display: "flex", justifyContent: "center" }}>
              <Box
                sx={{
                  width: 72,
                  height: 72,
                  borderRadius: 2.5,
                  bgcolor: alpha(theme.palette.primary.main, isDark ? 0.1 : 0.06),
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <FolderSpecialIcon
                  sx={{
                    fontSize: 36,
                    color: alpha(theme.palette.primary.main, 0.4),
                  }}
                />
              </Box>
            </Box>

            {/* Name */}
            <Controller
              name="name"
              control={control}
              rules={{
                required: t("collectionGroups.form.validation.nameRequired", "Name is required"),
                minLength: {
                  value: 1,
                  message: t(
                    "collectionGroups.form.validation.nameEmpty",
                    "Name must not be empty"
                  ),
                },
                maxLength: {
                  value: 200,
                  message: t(
                    "collectionGroups.form.validation.nameMaxLength",
                    "Name must be less than 200 characters"
                  ),
                },
              }}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t("collectionGroups.form.name", "Name")}
                  placeholder={t(
                    "collectionGroups.form.namePlaceholder",
                    "e.g. Marketing Campaign Assets"
                  )}
                  required
                  error={!!errors.name}
                  helperText={errors.name?.message}
                  disabled={isPending}
                  autoFocus
                  size="small"
                  sx={{ "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
                />
              )}
            />

            {/* Description */}
            <Controller
              name="description"
              control={control}
              rules={{
                maxLength: {
                  value: 1000,
                  message: t(
                    "collectionGroups.form.validation.descriptionMaxLength",
                    "Description must be less than 1000 characters"
                  ),
                },
              }}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t("collectionGroups.form.description", "Description")}
                  placeholder={t(
                    "collectionGroups.form.descriptionPlaceholder",
                    "Describe this collection group..."
                  )}
                  multiline
                  rows={2}
                  error={!!errors.description}
                  helperText={errors.description?.message}
                  disabled={isPending}
                  size="small"
                  sx={{ "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
                />
              )}
            />

            {/* Visibility (locked to public) */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                px: 1.5,
                py: 1,
                borderRadius: 1.5,
                bgcolor: alpha(theme.palette.text.primary, isDark ? 0.04 : 0.02),
                border: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
                opacity: 0.6,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <PublicIcon sx={{ fontSize: 18, color: "success.main" }} />
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 500, fontSize: "0.82rem" }}>
                    {t("collectionsPage.form.public", "Public")}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", fontSize: "0.7rem" }}
                  >
                    {t("collectionGroups.form.publicDescription", "Visible to all users")}
                  </Typography>
                </Box>
              </Box>
              <Switch checked disabled size="small" />
            </Box>

            {/* Error */}
            {(createGroup.isError || updateGroup.isError) && (
              <Alert
                severity="error"
                variant="outlined"
                sx={{ borderRadius: 2, fontSize: "0.82rem" }}
              >
                {isEditMode
                  ? t(
                      "collectionGroups.form.updateFailed",
                      "Failed to update collection group. Please try again."
                    )
                  : t(
                      "collectionGroups.form.createFailed",
                      "Failed to create collection group. Please try again."
                    )}
              </Alert>
            )}
          </Box>

          {/* Footer */}
          <Box
            sx={{
              px: 3,
              py: 2,
              borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 1,
            }}
          >
            <Box
              component="button"
              type="button"
              onClick={handleClose}
              disabled={isPending}
              sx={{
                px: 2.5,
                py: 0.9,
                border: "none",
                borderRadius: 1.5,
                bgcolor: "transparent",
                color: "text.secondary",
                fontSize: "0.82rem",
                fontWeight: 500,
                cursor: "pointer",
                "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.06) },
                "&:disabled": { opacity: 0.5, cursor: "default" },
              }}
            >
              {t("common.cancel", "Cancel")}
            </Box>
            <Box
              component="button"
              type="submit"
              disabled={isPending}
              sx={{
                px: 3,
                py: 0.9,
                border: "none",
                borderRadius: 1.5,
                bgcolor: "primary.main",
                color: "primary.contrastText",
                fontSize: "0.82rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 0.7,
                transition: "background-color 0.15s ease, opacity 0.15s ease",
                "&:hover": { bgcolor: "primary.dark" },
                "&:disabled": { opacity: 0.4, cursor: "default" },
              }}
            >
              {isPending ? (
                <CircularProgress size={16} color="inherit" />
              ) : isEditMode ? (
                <EditIcon sx={{ fontSize: 16 }} />
              ) : (
                <AddIcon sx={{ fontSize: 18 }} />
              )}
              {isPending
                ? isEditMode
                  ? t("common.saving", "Saving...")
                  : t("common.creating", "Creating...")
                : isEditMode
                  ? t("common.save", "Save Changes")
                  : t("collectionGroups.form.createButton", "Create Group")}
            </Box>
          </Box>
        </form>
      </DialogContent>
    </Dialog>
  );
};
