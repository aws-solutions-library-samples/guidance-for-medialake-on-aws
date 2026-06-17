import React, { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from "@mui/icons-material";
import { useNavigate } from "react-router";

import { PageHeader, PageContent } from "@/components/common/layout";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
import { useListThemes, useDeleteTheme } from "@/api/hooks/useThemes";
import type { PortalTheme } from "@/api/types/api.types";
import UploadPortalsSubNav from "../components/UploadPortalsSubNav";

/**
 * ThemesListPage
 *
 * Sibling list page for reusable appearance Themes (Requirement 16.4 — list +
 * delete; create/edit live on `ThemeEditorPage`). Reuses the same MUI table /
 * delete-dialog pattern as `PortalsList`. Routed at
 * `/settings/upload-portals/themes`.
 */
const ThemesListPage: React.FC = () => {
  const navigate = useNavigate();
  const createPermission = useActionPermission("manage", "settings");
  const { data: response, isLoading } = useListThemes();
  const { mutateAsync: deleteTheme } = useDeleteTheme();

  const [deleteTarget, setDeleteTarget] = useState<PortalTheme | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const themes = response?.data ?? [];

  const handleCreate = () => navigate("/settings/upload-portals/themes/new");
  const handleEdit = (theme: PortalTheme) =>
    navigate(`/settings/upload-portals/themes/${theme.themeId}/edit`);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteTheme(deleteTarget.themeId);
      setDeleteTarget(null);
      setDeleteError(null);
    } catch (err) {
      setDeleteError((err as Error)?.message || "Failed to delete theme. Please try again.");
    }
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title="Themes"
        description="Reusable appearance themes you can apply to new or existing portals."
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreate}
            disabled={createPermission.disabled}
            title={createPermission.tooltip}
          >
            Create Theme
          </Button>
        }
      />

      <PageContent isLoading={isLoading}>
        <UploadPortalsSubNav active="themes" />

        {themes.length === 0 ? (
          <Box sx={{ textAlign: "center", py: 8 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No themes yet
            </Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
              Create Theme
            </Button>
          </Box>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {themes.map((theme) => (
                  <TableRow key={theme.themeId}>
                    <TableCell>{theme.name}</TableCell>
                    <TableCell>{theme.description || "—"}</TableCell>
                    <TableCell>
                      {theme.createdAt ? new Date(theme.createdAt).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton size="small" onClick={() => handleEdit(theme)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton size="small" onClick={() => setDeleteTarget(theme)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </PageContent>

      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete theme</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete &quot;{deleteTarget?.name}&quot;? Portals and templates
            that were created from this theme keep their appearance — they are independent
            snapshots.
          </DialogContentText>
          {deleteError && (
            <DialogContentText color="error" sx={{ mt: 1 }}>
              {deleteError}
            </DialogContentText>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDeleteTarget(null);
              setDeleteError(null);
            }}
          >
            Cancel
          </Button>
          <Button onClick={handleDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ThemesListPage;
