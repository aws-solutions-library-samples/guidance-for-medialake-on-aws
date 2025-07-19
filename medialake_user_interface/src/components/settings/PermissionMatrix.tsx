import React from "react";
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Button,
  Tooltip,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import RemoveIcon from "@mui/icons-material/Remove";
import DownloadIcon from "@mui/icons-material/Download";

// Define the permission status types
type PermissionStatus = "Allow" | "Deny" | "Not Set";

// Define the resource types based on the auth_seeder
type ResourceType =
  | "assets"
  | "pipelines"
  | "pipelinesExecutions"
  | "collections"
  | "settings";

// Define the action types
type ActionType =
  | "view"
  | "edit"
  | "delete"
  | "create"
  | "admin"
  | "retry"
  | "cancel";

// Interface for the permission matrix props
interface PermissionMatrixProps {
  permissions: any;
  title?: string;
  showExport?: boolean;
  onExport?: () => void;
  onCellClick?: (
    resource: string,
    action: string,
    status: PermissionStatus,
  ) => void;
  interactive?: boolean;
}

// Helper function to determine permission status
const getPermissionStatus = (
  permissions: any,
  resource: string,
  action: string,
): PermissionStatus => {
  if (!permissions) return "Not Set";

  // Handle nested structure like in the auth_seeder
  if (permissions[resource] && typeof permissions[resource] === "object") {
    // Handle deeply nested structure (e.g., settings.users.edit)
    if (action.includes(".")) {
      const actionParts = action.split(".");
      let current = permissions[resource];

      // Navigate through the nested structure
      for (let i = 0; i < actionParts.length - 1; i++) {
        if (
          current[actionParts[i]] &&
          typeof current[actionParts[i]] === "object"
        ) {
          current = current[actionParts[i]];
        } else {
          return "Not Set";
        }
      }

      // Check the final action
      const finalAction = actionParts[actionParts.length - 1];
      if (current[finalAction] === true) return "Allow";
      if (current[finalAction] === false) return "Deny";
      return "Not Set";
    }

    // Handle simple nested structure
    if (permissions[resource][action] === true) return "Allow";
    if (permissions[resource][action] === false) return "Deny";
    return "Not Set";
  }

  // Handle flat structure with dot notation
  const key = `${resource}.${action}`;
  if (key in permissions) {
    return permissions[key] ? "Allow" : "Deny";
  }

  // Handle array of permission objects
  if (Array.isArray(permissions)) {
    // Try exact match first
    const exactPermission = permissions.find(
      (p) => p.resource === resource && p.action === action,
    );
    if (exactPermission) {
      return exactPermission.effect === "Allow" ? "Allow" : "Deny";
    }

    // Try with dot notation for nested actions
    if (action.includes(".")) {
      const nestedPermission = permissions.find(
        (p) =>
          p.resource === resource &&
          (p.action === action || action.startsWith(`${p.action}.`)),
      );
      if (nestedPermission) {
        return nestedPermission.effect === "Allow" ? "Allow" : "Deny";
      }
    }
  }

  return "Not Set";
};

// Component to render the permission status icon
const PermissionStatusIcon: React.FC<{ status: PermissionStatus }> = ({
  status,
}) => {
  switch (status) {
    case "Allow":
      return <CheckCircleIcon color="success" />;
    case "Deny":
      return <CancelIcon color="error" />;
    default:
      return <RemoveIcon color="action" />;
  }
};

// Main Permission Matrix component
const PermissionMatrix: React.FC<PermissionMatrixProps> = ({
  permissions,
  title = "Permission Matrix",
  showExport = true,
  onExport,
  onCellClick,
  interactive = false,
}) => {
  // Define the resources and actions to display in the matrix
  const resources: ResourceType[] = [
    "assets",
    "pipelines",
    "pipelinesExecutions",
    "collections",
    "settings",
  ];

  // Define actions based on resource type
  const getActionsForResource = (resource: ResourceType): ActionType[] => {
    switch (resource) {
      case "pipelinesExecutions":
        return ["view", "retry", "cancel"];
      case "settings":
        return ["view", "edit", "admin"];
      default:
        return ["view", "create", "edit", "delete"];
    }
  };

  // Resource display names and icons (simplified for now)
  const resourceDisplayNames: Record<ResourceType, string> = {
    assets: "Assets",
    pipelines: "Pipelines",
    pipelinesExecutions: "Pipeline Executions",
    collections: "Collections",
    settings: "Settings",
  };

  // Action display names
  const actionDisplayNames: Record<ActionType, string> = {
    view: "VIEW",
    create: "CREATE",
    edit: "EDIT",
    delete: "DELETE",
    admin: "ADMIN",
    retry: "RETRY",
    cancel: "CANCEL",
  };

  // Handle export button click
  const handleExport = () => {
    if (onExport) {
      onExport();
    } else {
      // Default export functionality
      console.log("Exporting permission matrix:", permissions);
      // Implement actual export functionality here
    }
  };

  return (
    <Box sx={{ width: "100%" }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="h5" component="h2">
          {title}
        </Typography>
        {showExport && (
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleExport}
            variant="outlined"
            color="primary"
          >
            Export
          </Button>
        )}
      </Box>

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
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    {/* Resource icon would go here */}
                    <Typography>{resourceDisplayNames[resource]}</Typography>
                  </Box>
                </TableCell>
                {getActionsForResource(resource).map((action) => {
                  // Handle special case for settings with nested permissions
                  let status: PermissionStatus;
                  if (resource === "settings" && action === "edit") {
                    // Check if any settings edit permissions exist
                    const hasUsersEdit = getPermissionStatus(
                      permissions,
                      "settings",
                      "users.edit",
                    );
                    const hasSystemEdit = getPermissionStatus(
                      permissions,
                      "settings",
                      "system.edit",
                    );
                    const hasRegionsEdit = getPermissionStatus(
                      permissions,
                      "settings",
                      "regions.edit",
                    );

                    if (
                      hasUsersEdit === "Allow" ||
                      hasSystemEdit === "Allow" ||
                      hasRegionsEdit === "Allow"
                    ) {
                      status = "Allow";
                    } else if (
                      hasUsersEdit === "Deny" &&
                      hasSystemEdit === "Deny" &&
                      hasRegionsEdit === "Deny"
                    ) {
                      status = "Deny";
                    } else {
                      status = "Not Set";
                    }
                  } else {
                    status = getPermissionStatus(permissions, resource, action);
                  }

                  return (
                    <TableCell
                      key={`${resource}-${action}`}
                      align="center"
                      onClick={() =>
                        interactive &&
                        onCellClick &&
                        onCellClick(resource, action, status)
                      }
                      sx={
                        interactive
                          ? {
                              cursor: "pointer",
                              "&:hover": {
                                backgroundColor: "rgba(0, 0, 0, 0.04)",
                                transition: "background-color 0.2s",
                              },
                            }
                          : {}
                      }
                    >
                      <Tooltip title={interactive ? "Click to edit" : status}>
                        <Box>
                          <PermissionStatusIcon status={status} />
                        </Box>
                      </Tooltip>
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default PermissionMatrix;
