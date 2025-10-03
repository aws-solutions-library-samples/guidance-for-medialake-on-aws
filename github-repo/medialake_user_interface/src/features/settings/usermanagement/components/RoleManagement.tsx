import React, { useState } from "react";
import {
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Box,
  Tooltip,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
}

interface RoleManagementProps {
  roles: Role[];
  onAddRole: (role: Omit<Role, "id">) => void;
  onEditRole: (role: Role) => void;
  onDeleteRole: (roleId: string) => void;
}

const RoleManagement: React.FC<RoleManagementProps> = ({
  roles,
  onAddRole,
  onEditRole,
  onDeleteRole,
}) => {
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formData, setFormData] = useState<Omit<Role, "id">>({
    name: "",
    description: "",
    permissions: [],
  });

  const handleOpenDialog = (role?: Role) => {
    if (role) {
      setEditingRole(role);
      setFormData({
        name: role.name,
        description: role.description,
        permissions: role.permissions,
      });
    } else {
      setEditingRole(null);
      setFormData({
        name: "",
        description: "",
        permissions: [],
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingRole(null);
    setFormData({
      name: "",
      description: "",
      permissions: [],
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingRole) {
      onEditRole({ ...editingRole, ...formData });
    } else {
      onAddRole(formData);
    }
    handleCloseDialog();
  };

  const handlePermissionAdd = (permission: string) => {
    if (permission && !formData.permissions.includes(permission)) {
      setFormData({
        ...formData,
        permissions: [...formData.permissions, permission],
      });
    }
  };

  const handlePermissionRemove = (permission: string) => {
    setFormData({
      ...formData,
      permissions: formData.permissions.filter((p) => p !== permission),
    });
  };

  return (
    <Paper sx={{ p: 3, mt: 3 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="h6">Role Management</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Role
        </Button>
      </Box>

      <List>
        {roles.map((role) => (
          <ListItem
            key={role.id}
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              mb: 1,
            }}
          >
            <ListItemText
              primary={role.name}
              secondary={
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    {role.description}
                  </Typography>
                  <Box
                    sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1 }}
                  >
                    {role.permissions.map((permission) => (
                      <Chip
                        key={permission}
                        label={permission}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </Box>
              }
            />
            <ListItemSecondaryAction>
              <Tooltip title="Edit Role">
                <IconButton
                  edge="end"
                  onClick={() => handleOpenDialog(role)}
                  sx={{ mr: 1 }}
                >
                  <EditIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete Role">
                <IconButton
                  edge="end"
                  onClick={() => onDeleteRole(role.id)}
                  color="error"
                >
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </ListItemSecondaryAction>
          </ListItem>
        ))}
      </List>

      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <form onSubmit={handleSubmit}>
          <DialogTitle>
            {editingRole ? "Edit Role" : "Add New Role"}
          </DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}
            >
              <TextField
                label="Role Name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
                fullWidth
              />
              <TextField
                label="Description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                multiline
                rows={2}
                fullWidth
              />
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Permissions
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                  {formData.permissions.map((permission) => (
                    <Chip
                      key={permission}
                      label={permission}
                      onDelete={() => handlePermissionRemove(permission)}
                      size="small"
                    />
                  ))}
                </Box>
                <TextField
                  label="Add Permission"
                  size="small"
                  fullWidth
                  sx={{ mt: 1 }}
                  onKeyPress={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handlePermissionAdd((e.target as HTMLInputElement).value);
                      (e.target as HTMLInputElement).value = "";
                    }
                  }}
                />
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseDialog}>Cancel</Button>
            <Button type="submit" variant="contained" color="primary">
              {editingRole ? "Save Changes" : "Add Role"}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Paper>
  );
};

export default RoleManagement;
