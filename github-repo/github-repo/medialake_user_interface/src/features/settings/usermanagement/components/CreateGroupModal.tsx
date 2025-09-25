import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  CircularProgress,
  Snackbar,
  Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useCreateGroup } from "@/api/hooks/useGroups";
import { CreateGroupRequest } from "@/api/types/group.types";

interface CreateGroupModalProps {
  open: boolean;
  onClose: () => void;
}

const CreateGroupModal: React.FC<CreateGroupModalProps> = ({
  open,
  onClose,
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<CreateGroupRequest>({
    name: "",
    id: "",
    description: "",
    department: "",
    assignedPermissionSets: [],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({
    open: false,
    message: "",
    severity: "success",
  });

  const createGroupMutation = useCreateGroup();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear error when user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }));
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = t("validation.required");
    }

    if (!formData.id.trim()) {
      newErrors.id = t("validation.required");
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    try {
      await createGroupMutation.mutateAsync(formData);
      setSnackbar({
        open: true,
        message: t("groups.messages.createSuccess"),
        severity: "success",
      });

      // Reset form and close modal after successful creation
      setFormData({
        name: "",
        id: "",
        description: "",
        department: "",
        assignedPermissionSets: [],
      });
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (error) {
      console.error("Error creating group:", error);
      setSnackbar({
        open: true,
        message: t("groups.messages.createError"),
        severity: "error",
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Typography variant="h6" fontWeight={600}>
            {t("groups.actions.createGroup")}
          </Typography>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              name="name"
              label={t("groups.fields.name")}
              value={formData.name}
              onChange={handleChange}
              fullWidth
              margin="normal"
              error={!!errors.name}
              helperText={errors.name}
              required
            />
            <TextField
              name="id"
              label={t("groups.fields.id")}
              value={formData.id}
              onChange={handleChange}
              fullWidth
              margin="normal"
              error={!!errors.id}
              helperText={errors.id || t("groups.fields.idHelp")}
              required
            />
            <TextField
              name="description"
              label={t("groups.fields.description")}
              value={formData.description}
              onChange={handleChange}
              fullWidth
              margin="normal"
              multiline
              rows={3}
            />
            <TextField
              name="department"
              label={t("groups.fields.department")}
              value={formData.department}
              onChange={handleChange}
              fullWidth
              margin="normal"
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={onClose} variant="outlined">
            {t("common.actions.cancel")}
          </Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={createGroupMutation.isPending}
            startIcon={
              createGroupMutation.isPending ? (
                <CircularProgress size={20} />
              ) : null
            }
          >
            {t("common.actions.create")}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default CreateGroupModal;
