import React, { useState } from "react";
import { useNavigate } from "react-router";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Switch,
  IconButton,
  Tooltip,
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  ContentCopy as CopyIcon,
  Key as TokenIcon,
  Add as AddIcon,
  FileCopy as DuplicateIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetPortals, useDeletePortal, useTogglePortalActive } from "@/api/hooks/usePortals";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import type { PortalListItem, PortalResponse } from "@/api/types/api.types";

interface PortalsListProps {
  onOpenTokenManager: (portalId: string, portalSlug: string, portal: PortalListItem) => void;
}

const getStatusChip = (portal: PortalListItem) => {
  if (!portal.isActive) return <Chip label="Inactive" size="small" color="default" />;
  if (portal.expiresAt && new Date(portal.expiresAt) < new Date())
    return <Chip label="Expired" size="small" color="warning" />;
  return <Chip label="Active" size="small" color="success" />;
};

const getPortalPath = (portal: PortalListItem): string =>
  portal.accessMode === "public" ? `/p/${portal.slug}` : `/upload/${portal.slug}`;

const accessModeLabels: Record<string, string> = {
  public: "Public",
  "token-protected": "Token Protected",
  "cognito-groups": "Authenticated",
};

const DestinationCountCell: React.FC<{ portal: PortalListItem }> = ({ portal }) => {
  const { data, isLoading } = useQuery<PortalResponse, Error>({
    queryKey: QUERY_KEYS.PORTALS.detail(portal.portalId),
    enabled: portal.destinations === undefined,
    retry: 1,
    queryFn: async ({ signal }) => {
      const response = await apiClient.get<PortalResponse>(
        API_ENDPOINTS.PORTALS.GET(portal.portalId),
        { signal }
      );
      return response.data;
    },
  });
  if (portal.destinations !== undefined) return <>{portal.destinations.length}</>;
  if (isLoading) return <>—</>;
  return <>{data?.data?.destinations?.length ?? "—"}</>;
};

const PortalsList: React.FC<PortalsListProps> = ({ onOpenTokenManager }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: response, isLoading } = useGetPortals();
  const { mutateAsync: deletePortal } = useDeletePortal();
  const { mutate: toggleActive } = useTogglePortalActive();
  const [deleteTarget, setDeleteTarget] = useState<PortalListItem | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<{
    message: string;
    severity: "success" | "error";
  } | null>(null);

  const portals = response?.data ?? [];

  const handleCreateClick = () => navigate("/settings/upload-portals/new");

  const handleEditClick = (portal: PortalListItem) =>
    navigate(`/settings/upload-portals/${portal.portalId}/edit`);

  const handleDuplicateClick = (portal: PortalListItem) =>
    navigate(`/settings/upload-portals/new?duplicate=${portal.portalId}`);

  const handleCopyLink = async (portal: PortalListItem) => {
    const link = `${window.location.origin}${getPortalPath(portal)}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopyFeedback({ message: "Link copied to clipboard.", severity: "success" });
    } catch (err) {
      console.error("Failed to copy portal link", err);
      setCopyFeedback({
        message: `Unable to copy link. Please copy it manually: ${link}`,
        severity: "error",
      });
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deletePortal(deleteTarget.portalId);
      setDeleteTarget(null);
      setDeleteError(null);
    } catch (err) {
      console.error("Failed to delete portal", err);
      setDeleteError((err as Error)?.message || "Failed to delete portal. Please try again.");
    }
  };

  if (isLoading) return null;

  if (portals.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 8 }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          No upload portals yet
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreateClick}>
          Create Portal
        </Button>
      </Box>
    );
  }

  return (
    <>
      <TableContainer component={Paper} variant="outlined">
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>{t("uploadPortals.list.shortUrl")}</TableCell>
              <TableCell>Access</TableCell>
              <TableCell>Destinations</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Expiry</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {portals.map((portal) => (
              <TableRow key={portal.portalId}>
                <TableCell>{portal.name.replace(/[#*_~`>]/g, "")}</TableCell>
                <TableCell sx={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                  {getPortalPath(portal)}
                </TableCell>
                <TableCell>{accessModeLabels[portal.accessMode] ?? portal.accessMode}</TableCell>
                <TableCell>
                  <DestinationCountCell portal={portal} />
                </TableCell>
                <TableCell>{getStatusChip(portal)}</TableCell>
                <TableCell>
                  {portal.expiresAt ? new Date(portal.expiresAt).toLocaleDateString() : "—"}
                </TableCell>
                <TableCell>{new Date(portal.createdAt).toLocaleDateString()}</TableCell>
                <TableCell align="right">
                  <Switch
                    size="small"
                    checked={portal.isActive}
                    onChange={(_, checked) =>
                      toggleActive({ id: portal.portalId, isActive: checked })
                    }
                  />
                  <Tooltip title={t("uploadPortals.list.copyLink")}>
                    <IconButton size="small" onClick={() => handleCopyLink(portal)}>
                      <CopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Tokens">
                    <IconButton
                      size="small"
                      onClick={() => onOpenTokenManager(portal.portalId, portal.slug, portal)}
                    >
                      <TokenIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Duplicate">
                    <IconButton size="small" onClick={() => handleDuplicateClick(portal)}>
                      <DuplicateIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Edit">
                    <IconButton size="small" onClick={() => handleEditClick(portal)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" onClick={() => setDeleteTarget(portal)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>{t("uploadPortals.list.deletePortal")}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete &quot;{deleteTarget?.name}&quot;? This action cannot be
            undone.
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

      {copyFeedback && (
        <Dialog
          open={!!copyFeedback}
          onClose={() => setCopyFeedback(null)}
          maxWidth="xs"
          aria-labelledby="copy-feedback-title"
        >
          <DialogTitle id="copy-feedback-title">
            {copyFeedback.severity === "success" ? "Link copied" : "Copy failed"}
          </DialogTitle>
          <DialogContent>
            <DialogContentText>{copyFeedback.message}</DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCopyFeedback(null)} autoFocus>
              OK
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
};

export default PortalsList;
