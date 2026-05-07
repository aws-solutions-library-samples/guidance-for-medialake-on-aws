import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  FormLabel,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Box,
  Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { Role, CreateRoleRequest } from "../../../../api/types/api.types";

interface RoleFormProps {
  open: boolean;
  onClose: () => void;
  onSave: (role: CreateRoleRequest) => Promise<any>;
  role?: Role;
}

const AVAILABLE_PERMISSIONS = [
  "READ_ASSETS",
  "WRITE_ASSETS",
  "DELETE_ASSETS",
  "MANAGE_USERS",
  "MANAGE_ROLES",
  "MANAGE_CONNECTORS",
  "VIEW_ANALYTICS",
  "MANAGE_SETTINGS",
];

const RoleForm: React.FC<RoleFormProps> = ({ open, onClose, onSave, role }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<CreateRoleRequest>({
    name: role?.name || "",
    description: role?.description || "",
    permissions: role?.permissions || [],
  });

  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await onSave(formData);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const handlePermissionChange = (permission: string) => {
    setFormData((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter((p) => p !== permission)
        : [...prev.permissions, permission],
    }));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>
          {role ? t("roles.tooltips.editRole") : t("roles.actions.addRole")}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <TextField
              label={t("userManagement.form.roleName")}
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              fullWidth
            />

            <TextField
              label={t("common.labels.description")}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              multiline
              rows={2}
              fullWidth
            />

            <FormControl component="fieldset" variant="standard">
              <FormLabel component="legend">{t("common.permissions")}</FormLabel>
              <FormGroup>
                {AVAILABLE_PERMISSIONS.map((permission) => (
                  <FormControlLabel
                    key={permission}
                    control={
                      <Checkbox
                        checked={formData.permissions.includes(permission)}
                        onChange={() => handlePermissionChange(permission)}
                      />
                    }
                    label={permission
                      .split("_")
                      .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
                      .join(" ")}
                  />
                ))}
              </FormGroup>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="submit" variant="contained" color="primary">
            {role ? t("common.save") : t("roles.actions.addRole")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default RoleForm;
