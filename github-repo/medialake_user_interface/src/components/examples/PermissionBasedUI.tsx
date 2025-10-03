import React from "react";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Divider,
  Grid,
} from "@mui/material";
import { Can } from "@/permissions";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import ShareIcon from "@mui/icons-material/Share";
import VisibilityIcon from "@mui/icons-material/Visibility";

/**
 * Example component demonstrating how to use the Can component for permission-based UI rendering
 *
 * This component shows different ways to use the Can component:
 * 1. Simple conditional rendering (hide elements)
 * 2. Conditional rendering with a function child (for more complex logic)
 * 3. Using passThrough to disable rather than hide elements
 */
const PermissionBasedUI: React.FC = () => {
  // Example asset object
  const asset = {
    id: "123",
    name: "Example Asset",
    type: "image",
    owner: "current-user",
    size: 1024000,
    createdAt: new Date().toISOString(),
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Permission-Based UI Examples
      </Typography>

      <Typography variant="body1" paragraph>
        This component demonstrates different ways to use the Can component for
        permission-based UI rendering.
      </Typography>

      <Grid container spacing={3}>
        {/* Example 1: Simple conditional rendering */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Example 1: Hide Elements</Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Elements are completely hidden when user doesn't have permission
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                {/* Always visible */}
                <Button variant="outlined" startIcon={<VisibilityIcon />}>
                  View
                </Button>

                {/* Only visible with edit permission */}
                <Can I="edit" a="asset" subject={asset}>
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<EditIcon />}
                  >
                    Edit
                  </Button>
                </Can>

                {/* Only visible with delete permission */}
                <Can I="delete" a="asset" subject={asset}>
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<DeleteIcon />}
                  >
                    Delete
                  </Button>
                </Can>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Example 2: Conditional rendering with function child */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6">Example 2: Function Child</Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Using a function child for more complex conditional rendering
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Can I="share" a="asset" subject={asset}>
                {(allowed) => (
                  <Box>
                    <Button
                      variant="contained"
                      color="secondary"
                      startIcon={<ShareIcon />}
                      fullWidth
                    >
                      Share Asset
                    </Button>

                    {allowed && (
                      <Typography
                        variant="caption"
                        sx={{ mt: 1, display: "block" }}
                      >
                        You can share this asset with other users
                      </Typography>
                    )}
                  </Box>
                )}
              </Can>
            </CardContent>
          </Card>
        </Grid>

        {/* Example 3: Using passThrough to disable rather than hide */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6">Example 3: Disable Elements</Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Using passThrough to disable elements rather than hiding them
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: "flex", gap: 2 }}>
                <Can I="download" a="asset" subject={asset} passThrough>
                  <Button
                    variant="outlined"
                    color="primary"
                    startIcon={<DownloadIcon />}
                    sx={{ minWidth: "150px" }}
                  >
                    Download
                  </Button>
                </Can>

                <Can I="delete" a="asset" subject={asset} passThrough>
                  {(allowed) => (
                    <Button
                      variant="outlined"
                      color="error"
                      startIcon={<DeleteIcon />}
                      disabled={!allowed}
                      title={
                        !allowed
                          ? "You don't have permission to delete this asset"
                          : ""
                      }
                      sx={{ minWidth: "150px" }}
                    >
                      Delete
                    </Button>
                  )}
                </Can>
              </Box>
            </CardContent>

            <CardActions>
              <Typography variant="caption" color="text.secondary">
                Note: Disabled buttons are shown with reduced opacity
              </Typography>
            </CardActions>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default PermissionBasedUI;
