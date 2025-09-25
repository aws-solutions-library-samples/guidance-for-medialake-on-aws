import React from "react";
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Alert,
} from "@mui/material";
import { Can, usePermission } from "../../permissions";
import SettingsIcon from "@mui/icons-material/Settings";
import SecurityIcon from "@mui/icons-material/Security";
import GroupIcon from "@mui/icons-material/Group";
import StorageIcon from "@mui/icons-material/Storage";
import BackupIcon from "@mui/icons-material/Backup";
import IntegrationInstructionsIcon from "@mui/icons-material/IntegrationInstructions";
import { useAuth } from "../../common/hooks/auth-context";
import { StorageHelper } from "../../common/helpers/storage-helper";

/**
 * Example component demonstrating group-based access control
 *
 * This component shows how to use the Can component to conditionally render
 * UI elements based on the user's group membership. In this case, system settings
 * are only visible to users in the "administrators" group.
 */
const GroupBasedAccess: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [userInfo, setUserInfo] = React.useState<any>(null);
  const { can, loading, error } = usePermission();

  // Check if the user can manage settings
  const canManageSettings = can("manage", "settings");

  // Log debugging information
  React.useEffect(() => {
    console.log("User Info:", userInfo);
    console.log("Can Manage Settings:", canManageSettings);
    console.log("Loading:", loading);
    console.log("Error:", error);
  }, [userInfo, canManageSettings, loading, error]);

  // Extract user information from JWT token for display purposes
  React.useEffect(() => {
    if (isAuthenticated) {
      try {
        const token = StorageHelper.getToken();
        if (token) {
          // Parse the JWT token to get user claims
          const tokenParts = token.split(".");
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]));
            setUserInfo(payload);

            // Log the extracted user information
            console.log("JWT Payload:", payload);
            console.log("Groups from JWT:", payload["cognito:groups"]);
          }
        }
      } catch (error) {
        console.error("Error extracting user from token:", error);
      }
    } else {
      setUserInfo(null);
    }
  }, [isAuthenticated]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Group-Based Access Control Example
      </Typography>

      <Typography variant="body1" paragraph>
        This component demonstrates how to use the Can component to
        conditionally render UI elements based on the user's group membership.
        In this case, system settings are only visible to users in the
        "administrators" group.
      </Typography>

      {userInfo && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Current User Information
          </Typography>
          <Typography variant="body2">User ID: {userInfo.sub}</Typography>
          <Typography variant="body2">
            Username: {userInfo["cognito:username"]}
          </Typography>
          <Typography variant="body2">Email: {userInfo.email}</Typography>
          <Typography variant="body2">
            Groups:{" "}
            {userInfo["cognito:groups"]
              ? userInfo["cognito:groups"].join(", ")
              : "None"}
          </Typography>
        </Paper>
      )}

      <Box
        sx={{
          display: "flex",
          gap: 2,
          flexDirection: { xs: "column", md: "row" },
        }}
      >
        {/* Regular settings - visible to all users */}
        <Paper sx={{ flex: 1, p: 2 }}>
          <Typography variant="h6" gutterBottom>
            User Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            These settings are available to all authenticated users.
          </Typography>

          <List>
            <ListItem>
              <ListItemIcon>
                <SettingsIcon />
              </ListItemIcon>
              <ListItemText
                primary="Profile Settings"
                secondary="Update your personal information"
              />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemIcon>
                <SecurityIcon />
              </ListItemIcon>
              <ListItemText
                primary="Security Settings"
                secondary="Manage your account security"
              />
            </ListItem>
          </List>
        </Paper>

        {/* System settings - only visible to administrators */}
        <Can I="manage" a="settings">
          {(allowed) => (
            <Paper sx={{ flex: 1, p: 2 }}>
              <Typography variant="h6" gutterBottom>
                System Settings
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                These settings are only available to users in the
                "administrators" group.
              </Typography>

              {/* Debug information */}
              <Box
                sx={{
                  mb: 2,
                  p: 1,
                  bgcolor: "background.paper",
                  border: "1px dashed grey",
                }}
              >
                <Typography variant="subtitle2">Debug Information:</Typography>
                <Typography variant="body2">
                  Can Manage Settings: {canManageSettings ? "Yes" : "No"}
                </Typography>
                <Typography variant="body2">
                  Allowed (from Can): {allowed ? "Yes" : "No"}
                </Typography>
                <Typography variant="body2">
                  Direct Group Check:{" "}
                  {userInfo &&
                  userInfo["cognito:groups"] &&
                  userInfo["cognito:groups"].includes("administrators")
                    ? "Yes"
                    : "No"}
                </Typography>
                <Typography variant="body2">
                  Loading: {loading ? "Yes" : "No"}
                </Typography>
                <Typography variant="body2">
                  Error: {error ? error.message : "None"}
                </Typography>
                {userInfo && (
                  <Typography variant="body2">
                    Groups: {JSON.stringify(userInfo["cognito:groups"])}
                  </Typography>
                )}
              </Box>

              {allowed ? (
                <List>
                  <ListItem>
                    <ListItemIcon>
                      <GroupIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary="User Management"
                      secondary="Manage users and permissions"
                    />
                  </ListItem>
                  <Divider />
                  <ListItem>
                    <ListItemIcon>
                      <StorageIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary="Storage Configuration"
                      secondary="Configure storage settings"
                    />
                  </ListItem>
                  <Divider />
                  <ListItem>
                    <ListItemIcon>
                      <BackupIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary="Backup Settings"
                      secondary="Configure backup settings"
                    />
                  </ListItem>
                  <Divider />
                  <ListItem>
                    <ListItemIcon>
                      <IntegrationInstructionsIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary="API Configuration"
                      secondary="Configure API settings"
                    />
                  </ListItem>
                </List>
              ) : (
                <Alert severity="warning">
                  You don't have permission to access system settings. Only
                  administrators can access these settings.
                </Alert>
              )}
            </Paper>
          )}
        </Can>
      </Box>
    </Box>
  );
};

export default GroupBasedAccess;
