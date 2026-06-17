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
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  AddCircleOutline as UsePortalIcon,
} from "@mui/icons-material";
import { useNavigate } from "react-router";

import { PageHeader, PageContent } from "@/components/common/layout";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
import { useListTemplates, useDeleteTemplate } from "@/api/hooks/useTemplates";
import type { PortalTemplate } from "@/api/types/api.types";
import UploadPortalsSubNav from "../components/UploadPortalsSubNav";

/**
 * TemplatesListPage
 *
 * Sibling list page for reusable portal Templates (Requirement 17.2 — list +
 * delete; create/edit live on `TemplateEditorPage`). Reuses the same MUI
 * table / delete-dialog pattern as `PortalsList`. Routed at
 * `/settings/upload-portals/templates`.
 *
 * Each row also offers "Create portal from this template", which routes to
 * the portal create flow seeded via `?template=<id>` (the same path used by
 * `CreatePortalMenu`).
 */
const TemplatesListPage: React.FC = () => {
  const navigate = useNavigate();
  const createPermission = useActionPermission("manage", "settings");
  const { data: response, isLoading } = useListTemplates();
  const { mutateAsync: deleteTemplate } = useDeleteTemplate();

  const [deleteTarget, setDeleteTarget] = useState<PortalTemplate | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const templates = response?.data ?? [];

  const handleCreate = () => navigate("/settings/upload-portals/templates/new");
  const handleEdit = (template: PortalTemplate) =>
    navigate(`/settings/upload-portals/templates/${template.templateId}/edit`);
  const handleCreatePortalFrom = (template: PortalTemplate) =>
    navigate(`/settings/upload-portals/new?template=${encodeURIComponent(template.templateId)}`);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteTemplate(deleteTarget.templateId);
      setDeleteTarget(null);
      setDeleteError(null);
    } catch (err) {
      setDeleteError((err as Error)?.message || "Failed to delete template. Please try again.");
    }
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title="Templates"
        description="Reusable portal structures you can use to start new portals from a known-good setup."
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreate}
            disabled={createPermission.disabled}
            title={createPermission.tooltip}
          >
            Create Template
          </Button>
        }
      />

      <PageContent isLoading={isLoading}>
        <UploadPortalsSubNav active="templates" />

        {templates.length === 0 ? (
          <Box sx={{ textAlign: "center", py: 8 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No templates yet
            </Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
              Create Template
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
                {templates.map((template) => (
                  <TableRow key={template.templateId}>
                    <TableCell>{template.name}</TableCell>
                    <TableCell>{template.description || "—"}</TableCell>
                    <TableCell>
                      {template.createdAt ? new Date(template.createdAt).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Create portal from this template">
                        <IconButton size="small" onClick={() => handleCreatePortalFrom(template)}>
                          <UsePortalIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton size="small" onClick={() => handleEdit(template)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton size="small" onClick={() => setDeleteTarget(template)}>
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
        <DialogTitle>Delete template</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete &quot;{deleteTarget?.name}&quot;? Portals already
            created from this template are independent and will not be affected.
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

export default TemplatesListPage;
