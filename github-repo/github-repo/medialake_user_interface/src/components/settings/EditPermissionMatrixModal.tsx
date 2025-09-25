import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import RemoveIcon from "@mui/icons-material/Remove";

// Define the permission status types
type PermissionStatus = "Allow" | "Deny" | "Not Set";

// Define the resource types
type ResourceType =
  | "assets"
  | "collections"
  | "pipelines"
  | "integrations"
  | "settings";

// Define the action types
type ActionType = "view" | "create" | "edit" | "delete" | "admin";

// Interface for the permission matrix modal props
interface EditPermissionMatrixModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (permissions: any) => void;
  permissions: any;
  title?: string;
  resourceName?: string;
}

// Main EditPermissionMatrixModal component
const EditPermissionMatrixModal: React.FC<EditPermissionMatrixModalProps> = ({
  open,
  onClose,
  onSave,
  permissions: initialPermissions,
  title = "Edit Permissions",
  resourceName,
}) => {
  // State to track the edited permissions
  const [permissions, setPermissions] = useState<any>(initialPermissions || {});

  // Reset permissions when modal opens with new data
  useEffect(() => {
    if (open) {
      setPermissions(initialPermissions || {});
    }
  }, [open, initialPermissions]);

  // Define the resources and actions to display in the matrix
  const resources: ResourceType[] = [
    "assets",
    "collections",
    "pipelines",
    "integrations",
    "settings",
  ];

  // Define actions based on resource type
  const getActionsForResource = (resource: ResourceType): ActionType[] => {
    switch (resource) {
      case "settings":
        return ["view", "edit", "admin"];
      default:
        return ["view", "create", "edit", "delete", "admin"];
    }
  };

  // Resource display names
  const resourceDisplayNames: Record<ResourceType, string> = {
    assets: "Assets",
    collections: "Collections",
    pipelines: "Pipelines",
    integrations: "Integrations",
    settings: "Settings",
  };

  // Action display names
  const actionDisplayNames: Record<ActionType, string> = {
    view: "VIEW",
    create: "CREATE",
    edit: "EDIT",
    delete: "DELETE",
    admin: "ADMIN",
  };

  // Helper function to get permission status
  const getPermissionStatus = (
    resource: string,
    action: string,
  ): PermissionStatus => {
    if (!permissions) return "Not Set";

    // Handle array of permission objects
    if (Array.isArray(permissions)) {
      const permission = permissions.find(
        (p) => p.resource === resource && p.action === action,
      );
      if (permission) {
        return permission.effect === "Allow" ? "Allow" : "Deny";
      }
      return "Not Set";
    }

    // Handle nested structure
    if (permissions[resource] && typeof permissions[resource] === "object") {
      if (permissions[resource][action] === true) return "Allow";
      if (permissions[resource][action] === false) return "Deny";
      return "Not Set";
    }

    // Handle flat structure with dot notation
    const key = `${resource}.${action}`;
    if (key in permissions) {
      return permissions[key] ? "Allow" : "Deny";
    }

    return "Not Set";
  };

  // Function to update permission status
  const updatePermissionStatus = (
    resource: string,
    action: string,
    status: PermissionStatus,
  ) => {
    // Create a copy of the permissions to modify
    let updatedPermissions;

    // Handle array of permission objects
    if (Array.isArray(permissions)) {
      updatedPermissions = [...permissions];
      const existingIndex = updatedPermissions.findIndex(
        (p) => p.resource === resource && p.action === action,
      );

      if (status === "Not Set") {
        // Remove the permission if it exists
        if (existingIndex !== -1) {
          updatedPermissions.splice(existingIndex, 1);
        }
      } else {
        // Update or add the permission
        if (existingIndex !== -1) {
          updatedPermissions[existingIndex] = {
            ...updatedPermissions[existingIndex],
            effect: status,
          };
        } else {
          updatedPermissions.push({
            resource,
            action,
            effect: status,
          });
        }
      }
    } else {
      // Handle object structure
      updatedPermissions = { ...permissions };

      // Ensure the resource object exists
      if (!updatedPermissions[resource]) {
        updatedPermissions[resource] = {};
      }

      // Update the permission
      if (status === "Not Set") {
        // Remove the permission
        if (typeof updatedPermissions[resource] === "object") {
          const resourceObj = { ...updatedPermissions[resource] };
          delete resourceObj[action];
          updatedPermissions[resource] = resourceObj;
        }
      } else {
        // Set the permission
        updatedPermissions[resource] = {
          ...updatedPermissions[resource],
          [action]: status === "Allow",
        };
      }
    }

    setPermissions(updatedPermissions);
  };

  // Handle save button click
  const handleSave = () => {
    onSave(permissions);
    onClose();
  };

  // Component to render the permission status toggle
  const PermissionStatusToggle: React.FC<{
    resource: string;
    action: string;
    status: PermissionStatus;
    onChange: (status: PermissionStatus) => void;
  }> = ({ resource, action, status, onChange }) => {
    return (
      <ToggleButtonGroup
        value={status}
        exclusive
        onChange={(_, newStatus) => {
          if (newStatus !== null) {
            onChange(newStatus as PermissionStatus);
          }
        }}
        size="small"
        aria-label="permission status"
      >
        <ToggleButton value="Allow" aria-label="allow">
          <Tooltip title="Permit">
            <CheckCircleIcon
              color={status === "Allow" ? "success" : "inherit"}
            />
          </Tooltip>
        </ToggleButton>
        <ToggleButton value="Deny" aria-label="deny">
          <Tooltip title="Deny">
            <CancelIcon color={status === "Deny" ? "error" : "inherit"} />
          </Tooltip>
        </ToggleButton>
        <ToggleButton value="Not Set" aria-label="not set">
          <Tooltip title="Not Set">
            <RemoveIcon color={status === "Not Set" ? "action" : "inherit"} />
          </Tooltip>
        </ToggleButton>
      </ToggleButtonGroup>
    );
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Box sx={{ width: "100%", mt: 2 }}>
          {resourceName && (
            <Typography variant="h6" gutterBottom>
              {resourceName}
            </Typography>
          )}

          <TableContainer component={Paper} sx={{ overflowX: "auto" }}>
            <Table aria-label="permission matrix table">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: "bold", width: "200px" }}>
                    RESOURCE
                  </TableCell>
                  {/* Get all unique actions across all resources */}
                  {Array.from(
                    new Set(resources.flatMap((r) => getActionsForResource(r))),
                  ).map((action) => (
                    <TableCell
                      key={action}
                      align="center"
                      sx={{ fontWeight: "bold" }}
                    >
                      {actionDisplayNames[action]}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {resources.map((resource) => (
                  <TableRow
                    key={resource}
                    sx={{ "&:last-child td, &:last-child th": { border: 0 } }}
                  >
                    <TableCell component="th" scope="row">
                      <Box
                        sx={{ display: "flex", alignItems: "center", gap: 1 }}
                      >
                        <Typography>
                          {resourceDisplayNames[resource]}
                        </Typography>
                      </Box>
                    </TableCell>
                    {getActionsForResource(resource).map((action) => {
                      const status = getPermissionStatus(resource, action);

                      return (
                        <TableCell key={`${resource}-${action}`} align="center">
                          <PermissionStatusToggle
                            resource={resource}
                            action={action}
                            status={status}
                            onChange={(newStatus) =>
                              updatePermissionStatus(
                                resource,
                                action,
                                newStatus,
                              )
                            }
                          />
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditPermissionMatrixModal;
