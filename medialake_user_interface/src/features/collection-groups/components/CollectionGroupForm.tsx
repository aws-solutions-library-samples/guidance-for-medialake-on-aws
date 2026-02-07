/**
 * Collection Group Form Component
 * Form for creating or editing a collection group
 */

import React, { useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControlLabel,
  Switch,
  Box,
  CircularProgress,
} from "@mui/material";
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
  isPublic: boolean;
}

export const CollectionGroupForm: React.FC<CollectionGroupFormProps> = ({
  open,
  onClose,
  group,
}) => {
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
      isPublic: true,
    },
  });

  // Reset form when group changes or dialog opens
  useEffect(() => {
    if (open) {
      if (group) {
        reset({
          name: group.name,
          description: group.description || "",
          isPublic: group.isPublic,
        });
      } else {
        reset({
          name: "",
          description: "",
          isPublic: true,
        });
      }
    }
  }, [open, group, reset]);

  const onSubmit = async (data: FormData) => {
    try {
      if (isEditMode && group) {
        // Update existing group
        const updateData: UpdateGroupRequest = {
          name: data.name,
          description: data.description || undefined,
          isPublic: data.isPublic,
        };
        await updateGroup.mutateAsync({ groupId: group.id, data: updateData });
      } else {
        // Create new group
        const createData: CreateGroupRequest = {
          name: data.name,
          description: data.description || undefined,
          isPublic: data.isPublic,
        };
        await createGroup.mutateAsync(createData);
      }
      onClose();
    } catch (error) {
      console.error("Failed to save group:", error);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit(onSubmit)}>
        <DialogTitle>
          {isEditMode ? "Edit Collection Group" : "Create Collection Group"}
        </DialogTitle>

        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} pt={1}>
            {/* Name Field */}
            <Controller
              name="name"
              control={control}
              rules={{
                required: "Name is required",
                minLength: { value: 1, message: "Name must not be empty" },
                maxLength: { value: 200, message: "Name must be less than 200 characters" },
              }}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="Name"
                  required
                  fullWidth
                  error={!!errors.name}
                  helperText={errors.name?.message}
                  autoFocus
                />
              )}
            />

            {/* Description Field */}
            <Controller
              name="description"
              control={control}
              rules={{
                maxLength: {
                  value: 1000,
                  message: "Description must be less than 1000 characters",
                },
              }}
              render={({ field }) => (
                <TextField
                  {...field}
                  label="Description"
                  fullWidth
                  multiline
                  rows={3}
                  error={!!errors.description}
                  helperText={errors.description?.message}
                />
              )}
            />

            {/* Public Switch */}
            <Controller
              name="isPublic"
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={<Switch {...field} checked={field.value} />}
                  label="Public (visible to all users)"
                />
              )}
            />
          </Box>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            startIcon={isSubmitting && <CircularProgress size={16} />}
          >
            {isEditMode ? "Update" : "Create"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
