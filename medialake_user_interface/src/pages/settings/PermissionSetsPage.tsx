import React, { useState } from "react";
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  CardActions,
  Grid,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  InputAdornment,
  Divider,
  Snackbar,
  FormHelperText,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Tabs,
  Tab,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SearchIcon from "@mui/icons-material/Search";
import FilterListIcon from "@mui/icons-material/FilterList";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import RemoveCircleOutlineIcon from "@mui/icons-material/RemoveCircleOutline";
import VisibilityIcon from "@mui/icons-material/Visibility";
import { useTranslation } from "react-i18next";
import { PageHeader, PageContent } from "@/components/common/layout";
import {
  useGetPermissionSets,
  useCreatePermissionSet,
  useUpdatePermissionSet,
  useDeletePermissionSet,
} from "@/api/hooks/usePermissionSets";
import { useGetPermissionSet } from "@/api/hooks/usePermissionSets";
import {
  PermissionSet,
  Permission,
  CreatePermissionSetRequest,
} from "@/api/types/permissionSet.types";
import PermissionMatrix from "@/components/settings/PermissionMatrix";
import EditPermissionMatrixModal from "@/components/settings/EditPermissionMatrixModal";

// Helper function to convert any permission format to Permission array
const convertToPermissionArray = (permissions: any): Permission[] => {
  if (!permissions) return [];

  // If it's already an array, return it
  if (Array.isArray(permissions)) {
    return permissions;
  }

  // If it's an object, convert it to an array of Permission objects
  if (typeof permissions === "object") {
    const result: Permission[] = [];

    // Handle flat structure with dot notation (e.g., "resource.action": true)
    Object.entries(permissions).forEach(([key, value]) => {
      if (typeof value === "boolean") {
        const parts = key.split(".");
        if (parts.length === 2) {
          result.push({
            resource: parts[0],
            action: parts[1],
            effect: value ? "Allow" : "Deny",
          });
        }
      }
    });

    // Handle nested structure (e.g., permissions.assets.view = true)
    Object.entries(permissions).forEach(([resource, actions]) => {
      if (
        typeof actions === "object" &&
        actions !== null &&
        !Array.isArray(actions)
      ) {
        Object.entries(actions as Record<string, any>).forEach(
          ([action, value]) => {
            if (typeof value === "boolean") {
              result.push({
                resource,
                action,
                effect: value ? "Allow" : "Deny",
              });
            } else if (typeof value === "object" && value !== null) {
              // Handle deeply nested structure (e.g., settings.users.edit)
              Object.entries(value as Record<string, any>).forEach(
                ([subAction, subValue]) => {
                  if (typeof subValue === "boolean") {
                    result.push({
                      resource,
                      action: `${action}.${subAction}`,
                      effect: subValue ? "Allow" : "Deny",
                    });
                  }
                },
              );
            }
          },
        );
      }
    });

    return result;
  }

  return [];
};

// Helper function to determine if a permission is allowed or denied
const getPermissionStatus = (
  permissions: any,
  action: string,
  resource: string,
): "Allowed" | "Denied" | "Not Set" => {
  // Handle permissions as an object with boolean properties
  if (
    permissions &&
    typeof permissions === "object" &&
    !Array.isArray(permissions)
  ) {
    // Check if there's a key like "resource.action" (e.g., "asset.view")
    const key = `${resource}.${action}`;
    if (key in permissions) {
      return permissions[key] ? "Allowed" : "Denied";
    }

    // Check nested structure
    if (permissions[resource] && typeof permissions[resource] === "object") {
      if (permissions[resource][action] === true) return "Allowed";
      if (permissions[resource][action] === false) return "Denied";

      // Check for deeply nested structure
      if (action.includes(".")) {
        const [mainAction, subAction] = action.split(".");
        if (
          permissions[resource][mainAction] &&
          typeof permissions[resource][mainAction] === "object" &&
          permissions[resource][mainAction][subAction] !== undefined
        ) {
          return permissions[resource][mainAction][subAction]
            ? "Allowed"
            : "Denied";
        }
      }
    }

    return "Not Set";
  }

  // Handle permissions as an array of Permission objects
  if (Array.isArray(permissions)) {
    const permission = permissions.find(
      (p) => p.action === action && p.resource === resource,
    );
    if (!permission) return "Not Set";
    return permission.effect === "Allow" ? "Allowed" : "Denied";
  }

  return "Not Set";
};

// Component to display permission status
const PermissionStatus: React.FC<{
  status: "Allowed" | "Denied" | "Not Set";
}> = ({ status }) => {
  const color =
    status === "Allowed"
      ? "success"
      : status === "Denied"
        ? "error"
        : "default";
  return <Chip label={status} size="small" color={color} variant="outlined" />;
};

// Permission Set Card Component
const PermissionSetCard: React.FC<{
  permissionSet: PermissionSet;
  onEdit: (permissionSet: PermissionSet) => void;
  onDelete: (permissionSet: PermissionSet) => void;
  onView: (permissionSet: PermissionSet) => void;
}> = ({ permissionSet, onEdit, onDelete, onView }) => {
  // Get access level label
  const getAccessLevel = (permissions: any) => {
    if (!permissions) return "No Access";

    // If there's an effectiveRole, use that to determine access level
    if (permissionSet.effectiveRole) {
      switch (permissionSet.effectiveRole) {
        case "Administrator":
        case "SuperAdministrator":
          return "Full Access";
        case "Editor":
          return "Read/Write";
        case "Viewer":
          return "Read Only";
        default:
          return "Role-Based Access";
      }
    }

    // Otherwise check permissions directly
    // Check if it has full admin access
    const hasFullAdmin = Object.entries(permissions).some(([key, value]) => {
      if (typeof value === "object" && value !== null) {
        return Object.values(value).some((v) => v === true);
      }
      return value === true;
    });

    return hasFullAdmin ? "Custom Access" : "Limited Access";
  };

  // Get access level chip color
  const getAccessChipColor = (accessLevel: string) => {
    switch (accessLevel) {
      case "Full Access":
        return "success";
      case "Read/Write":
        return "info";
      case "Read Only":
        return "default";
      case "Custom Access":
        return "warning";
      default:
        return "default";
    }
  };

  const accessLevel = getAccessLevel(permissionSet.permissions);

  return (
    <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" component="div" gutterBottom>
          {permissionSet.name}
          {permissionSet.isSystem && (
            <Chip
              label="System"
              size="small"
              color="primary"
              variant="outlined"
              sx={{ ml: 1, verticalAlign: "middle" }}
            />
          )}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {permissionSet.description}
        </Typography>

        <Box mt={2}>
          <Chip
            label={accessLevel}
            size="small"
            color={getAccessChipColor(accessLevel) as any}
            sx={{ mb: 1 }}
          />
          <Typography variant="body2" color="text.secondary">
            {permissionSet.effectiveRole ? (
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                  mt: 0.5,
                }}
              >
                Effective Role:
                <Chip
                  label={permissionSet.effectiveRole}
                  size="small"
                  variant="outlined"
                  color="primary"
                  sx={{ ml: 0.5 }}
                />
              </Box>
            ) : (
              "Custom Permission Set"
            )}
          </Typography>
        </Box>
      </CardContent>
      <CardActions>
        <Button
          size="small"
          startIcon={<VisibilityIcon />}
          onClick={() => onView(permissionSet)}
        >
          View Details
        </Button>
        <Button
          size="small"
          startIcon={<EditIcon />}
          onClick={() => onEdit(permissionSet)}
        >
          Edit
        </Button>
        {!permissionSet.isSystem && (
          <Button
            size="small"
            startIcon={<DeleteIcon />}
            onClick={() => onDelete(permissionSet)}
            color="error"
          >
            Delete
          </Button>
        )}
      </CardActions>
    </Card>
  );
};

// Add New Permission Set Card Component
const AddNewPermissionSetCard: React.FC<{
  onClick: () => void;
}> = ({ onClick }) => {
  return (
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        border: "2px dashed #ccc",
        backgroundColor: "background.paper",
      }}
      onClick={onClick}
    >
      <CardContent sx={{ textAlign: "center" }}>
        <AddIcon sx={{ fontSize: 40, color: "primary.main", mb: 2 }} />
        <Typography variant="h6" component="div">
          Add New Permission Set
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Create a custom permission set
        </Typography>
      </CardContent>
    </Card>
  );
};

// Permission Set Form Dialog Component
const PermissionSetFormDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onSave: (data: CreatePermissionSetRequest) => void;
  permissionSet?: PermissionSet;
}> = ({ open, onClose, onSave, permissionSet }) => {
  const [name, setName] = useState(permissionSet?.name || "");
  const [description, setDescription] = useState(
    permissionSet?.description || "",
  );
  const [permissions, setPermissions] = useState<Permission[]>(
    convertToPermissionArray(permissionSet?.permissions),
  );
  const [openMatrixModal, setOpenMatrixModal] = useState(false);

  // Form validation
  const [nameError, setNameError] = useState("");

  // Reset form when dialog opens/closes or permission set changes
  React.useEffect(() => {
    if (open) {
      setName(permissionSet?.name || "");
      setDescription(permissionSet?.description || "");
      setPermissions(convertToPermissionArray(permissionSet?.permissions));
      setNameError("");
    }
  }, [open, permissionSet]);

  const validateForm = (): boolean => {
    let isValid = true;

    if (!name.trim()) {
      setNameError("Name is required");
      isValid = false;
    } else {
      setNameError("");
    }

    return isValid;
  };

  const handleEditPermissions = () => {
    setOpenMatrixModal(true);
  };

  const handleSave = () => {
    if (!validateForm()) return;

    onSave({
      name,
      description,
      permissions,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {permissionSet ? "Edit Permission Set" : "Add Permission Set"}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            margin="normal"
            required
            error={!!nameError}
            helperText={nameError}
          />
          <TextField
            fullWidth
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            margin="normal"
            multiline
            rows={3}
          />

          <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
            Permissions
          </Typography>

          <Box
            sx={{ mb: 3, p: 2, border: "1px solid #e0e0e0", borderRadius: 1 }}
          >
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 2,
              }}
            >
              <Typography variant="subtitle1">Permission Matrix</Typography>
              <Button
                variant="contained"
                color="primary"
                onClick={handleEditPermissions}
                startIcon={<EditIcon />}
              >
                Edit Permissions
              </Button>
            </Box>

            <PermissionMatrix permissions={permissions} showExport={false} />
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          {permissionSet ? "Update" : "Create"}
        </Button>
      </DialogActions>

      {/* Permission Matrix Modal */}
      <EditPermissionMatrixModal
        open={openMatrixModal}
        onClose={() => setOpenMatrixModal(false)}
        permissions={permissions}
        title="Edit Permission Matrix"
        onSave={(updatedPermissions) => {
          setPermissions(convertToPermissionArray(updatedPermissions));
          setOpenMatrixModal(false);
        }}
      />
    </Dialog>
  );
};

// Delete Confirmation Dialog
const DeleteConfirmationDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  permissionSet?: PermissionSet;
}> = ({ open, onClose, onConfirm, permissionSet }) => {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Delete Permission Set</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to delete the permission set "
          {permissionSet?.name}"? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} color="error" variant="contained">
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// Permission Set Detail Dialog Component
const PermissionSetDetailDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  permissionSetId?: string;
  onEditPermissions?: (permissionSet: PermissionSet) => void;
}> = ({ open, onClose, permissionSetId, onEditPermissions }) => {
  const [activeTab, setActiveTab] = useState(0);

  // Only fetch data when dialog is open and we have a valid ID
  const shouldFetch = open && !!permissionSetId;
  const {
    data: permissionSet,
    isLoading,
    error,
  } = shouldFetch
    ? useGetPermissionSet(permissionSetId || "")
    : { data: undefined, isLoading: false, error: undefined };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  if (isLoading) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>Permission Set Details</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
            <CircularProgress />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  if (error || !permissionSet) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>Permission Set Details</DialogTitle>
        <DialogContent>
          <Alert severity="error">
            {error
              ? `Error loading permission set: ${(error as Error).message}`
              : "Permission set not found"}
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {permissionSet.name}
        {permissionSet.isSystem && (
          <Chip
            label="System"
            size="small"
            color="primary"
            variant="outlined"
            sx={{ ml: 1, verticalAlign: "middle" }}
          />
        )}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" paragraph>
          {permissionSet.description}
        </Typography>

        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}
        >
          <Tab label="Permission Matrix" />
          <Tab label="Assigned Users" />
          <Tab label="Assigned Groups" />
        </Tabs>

        {activeTab === 0 && (
          <Box sx={{ mt: 2 }}>
            <PermissionMatrix
              permissions={permissionSet.permissions}
              title={`Permissions for ${permissionSet.name}`}
              interactive={true}
              onCellClick={(resource, action, status) => {
                if (onEditPermissions) {
                  onEditPermissions(permissionSet);
                }
              }}
            />
            {permissionSet.effectiveRole && (
              <Box
                sx={{
                  mt: 2,
                  p: 2,
                  bgcolor: "background.paper",
                  borderRadius: 1,
                  border: "1px solid #e0e0e0",
                }}
              >
                <Typography variant="subtitle1" gutterBottom>
                  Effective Role:{" "}
                  <Chip
                    label={permissionSet.effectiveRole}
                    color="primary"
                    size="small"
                  />
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  This permission set inherits permissions from the{" "}
                  {permissionSet.effectiveRole} role.
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {activeTab === 1 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body1">
              This permission set is assigned to the following users:
            </Typography>
            {/* Placeholder for assigned users list */}
            <List>
              <ListItem>
                <ListItemText primary="No users assigned" />
              </ListItem>
            </List>
          </Box>
        )}

        {activeTab === 2 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body1">
              This permission set is assigned to the following groups:
            </Typography>
            {/* Placeholder for assigned groups list */}
            <List>
              <ListItem>
                <ListItemText primary="No groups assigned" />
              </ListItem>
            </List>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

// Main Permission Sets Page Component
const PermissionSetsPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [openPermissionSetForm, setOpenPermissionSetForm] = useState(false);
  const [openPermissionSetDetail, setOpenPermissionSetDetail] = useState(false);
  const [selectedPermissionSet, setSelectedPermissionSet] = useState<
    PermissionSet | undefined
  >();
  const [editingPermissionSet, setEditingPermissionSet] = useState<
    PermissionSet | undefined
  >();
  const [deletingPermissionSet, setDeletingPermissionSet] = useState<
    PermissionSet | undefined
  >();
  const [openDeleteDialog, setOpenDeleteDialog] = useState(false);
  const [openPermissionMatrixModal, setOpenPermissionMatrixModal] =
    useState(false);
  const [editingPermissions, setEditingPermissions] = useState<any>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error" | "info" | "warning";
  }>({
    open: false,
    message: "",
    severity: "info",
  });

  // API Hooks - Enable API call when this page is loaded
  const { data: permissionSets, isLoading, error } = useGetPermissionSets(true);
  const createPermissionSetMutation = useCreatePermissionSet();
  const updatePermissionSetMutation = useUpdatePermissionSet();
  const deletePermissionSetMutation = useDeletePermissionSet();

  // Filter permission sets based on search term and category
  const filteredPermissionSets = permissionSets?.filter((ps) => {
    const matchesSearch =
      searchTerm === "" ||
      ps.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ps.description.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesCategory =
      filterCategory === "all" ||
      (filterCategory === "system" && ps.isSystem) ||
      (filterCategory === "custom" && !ps.isSystem);

    return matchesSearch && matchesCategory;
  });

  const handleAddPermissionSet = () => {
    setEditingPermissionSet(undefined);
    setOpenPermissionSetForm(true);
  };

  const handleEditPermissionSet = (permissionSet: PermissionSet) => {
    setEditingPermissionSet(permissionSet);
    setOpenPermissionSetForm(true);
  };

  const handleViewPermissionSet = (permissionSet: PermissionSet) => {
    setSelectedPermissionSet(permissionSet);
    setOpenPermissionSetDetail(true);
  };

  const handleDeletePermissionSet = (permissionSet: PermissionSet) => {
    setDeletingPermissionSet(permissionSet);
    setOpenDeleteDialog(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingPermissionSet) return;

    try {
      await deletePermissionSetMutation.mutateAsync(deletingPermissionSet.id);
      setSnackbar({
        open: true,
        message: `Permission set "${deletingPermissionSet.name}" has been deleted.`,
        severity: "success",
      });
    } catch (err) {
      console.error("Error deleting permission set:", err);
      setSnackbar({
        open: true,
        message: `Failed to delete permission set: ${(err as Error).message}`,
        severity: "error",
      });
    } finally {
      setOpenDeleteDialog(false);
      setDeletingPermissionSet(undefined);
    }
  };

  const handleSavePermissionSet = async (data: CreatePermissionSetRequest) => {
    try {
      if (editingPermissionSet) {
        await updatePermissionSetMutation.mutateAsync({
          id: editingPermissionSet.id,
          updates: data,
        });
        setSnackbar({
          open: true,
          message: `Permission set "${data.name}" has been updated.`,
          severity: "success",
        });
      } else {
        await createPermissionSetMutation.mutateAsync(data);
        setSnackbar({
          open: true,
          message: `Permission set "${data.name}" has been created.`,
          severity: "success",
        });
      }
      setOpenPermissionSetForm(false);
    } catch (err) {
      console.error("Error saving permission set:", err);
      setSnackbar({
        open: true,
        message: `Failed to save permission set: ${(err as Error).message}`,
        severity: "error",
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  return (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flex: 1,
        width: "100%",
        position: "relative",
        maxWidth: "100%",
        p: 3,
      }}
    >
      <PageHeader
        title="Resource-Centric Permission Matrix"
        description="Manage permission sets to control access to resources"
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddPermissionSet}
            sx={{
              borderRadius: "8px",
              textTransform: "none",
              px: 3,
              height: 40,
            }}
          >
            Add Permission Set
          </Button>
        }
      />

      {/* Search and Filters */}
      <Box sx={{ mb: 3, display: "flex", gap: 2, flexWrap: "wrap" }}>
        <TextField
          placeholder="Search permission sets..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          sx={{ flexGrow: 1, minWidth: "200px" }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />

        <FormControl sx={{ minWidth: "150px" }}>
          <InputLabel id="category-filter-label">Category</InputLabel>
          <Select
            labelId="category-filter-label"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            label="Category"
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="system">System</MenuItem>
            <MenuItem value="custom">Custom</MenuItem>
          </Select>
        </FormControl>

        <Button
          variant="outlined"
          startIcon={<FilterListIcon />}
          sx={{ height: "56px" }}
        >
          Filters
        </Button>
      </Box>

      <PageContent isLoading={isLoading} error={error as Error}>
        <Grid container spacing={3}>
          {/* Add New Permission Set Card */}
          <Grid item xs={12} sm={6} md={4}>
            <AddNewPermissionSetCard onClick={handleAddPermissionSet} />
          </Grid>

          {/* Permission Set Cards */}
          {filteredPermissionSets?.map((permissionSet) => (
            <Grid item xs={12} sm={6} md={4} key={permissionSet.id}>
              <PermissionSetCard
                permissionSet={permissionSet}
                onEdit={handleEditPermissionSet}
                onDelete={handleDeletePermissionSet}
                onView={handleViewPermissionSet}
              />
            </Grid>
          ))}
        </Grid>
      </PageContent>

      {/* Permission Set Form Dialog */}
      <PermissionSetFormDialog
        open={openPermissionSetForm}
        onClose={() => setOpenPermissionSetForm(false)}
        onSave={handleSavePermissionSet}
        permissionSet={editingPermissionSet}
      />

      {/* Permission Set Detail Dialog */}
      <PermissionSetDetailDialog
        open={openPermissionSetDetail}
        onClose={() => setOpenPermissionSetDetail(false)}
        permissionSetId={selectedPermissionSet?.id}
        onEditPermissions={(permissionSet) => {
          setEditingPermissionSet(permissionSet);
          setEditingPermissions(permissionSet.permissions);
          setOpenPermissionMatrixModal(true);
        }}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        open={openDeleteDialog}
        onClose={() => setOpenDeleteDialog(false)}
        onConfirm={handleConfirmDelete}
        permissionSet={deletingPermissionSet}
      />

      {/* Edit Permission Matrix Modal */}
      <EditPermissionMatrixModal
        open={openPermissionMatrixModal}
        onClose={() => setOpenPermissionMatrixModal(false)}
        permissions={editingPermissions}
        title={`Edit Permissions for ${editingPermissionSet?.name || ""}`}
        onSave={async (updatedPermissions) => {
          if (!editingPermissionSet) return;

          try {
            await updatePermissionSetMutation.mutateAsync({
              id: editingPermissionSet.id,
              updates: {
                permissions: updatedPermissions,
              },
            });

            setSnackbar({
              open: true,
              message: `Permissions for "${editingPermissionSet.name}" have been updated.`,
              severity: "success",
            });
          } catch (err) {
            console.error("Error updating permissions:", err);
            setSnackbar({
              open: true,
              message: `Failed to update permissions: ${(err as Error).message}`,
              severity: "error",
            });
          }
        }}
      />

      {/* Snackbar for feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default PermissionSetsPage;
