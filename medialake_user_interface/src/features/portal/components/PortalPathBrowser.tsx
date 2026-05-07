import React, { useEffect, useState, useCallback } from "react";
import {
  Box,
  Breadcrumbs,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import CreateNewFolderIcon from "@mui/icons-material/CreateNewFolder";
import { useTranslation } from "react-i18next";
import { usePortalApi } from "../hooks/usePortalApi";
import type { PortalDestination } from "../types/portal.types";

interface Props {
  open: boolean;
  onClose: () => void;
  slug: string;
  sessionJwt: string;
  destination: PortalDestination;
  currentPath: string;
  onPathSelect: (path: string) => void;
}

interface FolderEntry {
  name: string;
  prefix: string;
}

const PortalPathBrowser: React.FC<Props> = ({
  open,
  onClose,
  slug,
  sessionJwt,
  destination,
  currentPath,
  onPathSelect,
}) => {
  const [browsePath, setBrowsePath] = useState(currentPath);
  const [folders, setFolders] = useState<FolderEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { t } = useTranslation();
  const { browse, createFolder } = usePortalApi(slug, sessionJwt);

  const safeRootPath = destination.rootPath ?? "";

  const fetchFolders = useCallback(
    async (prefix: string) => {
      setLoading(true);
      try {
        const result = await browse(prefix, destination.destinationId);
        const items: FolderEntry[] = (result.commonPrefixes || []).map((p: string) => ({
          name: p.split("/").filter(Boolean).pop() || p,
          prefix: p,
        }));
        setFolders(items);
      } catch {
        setFolders([]);
      } finally {
        setLoading(false);
      }
    },
    [browse, destination.destinationId]
  );

  useEffect(() => {
    if (open) {
      setBrowsePath(currentPath);
      fetchFolders(currentPath);
    }
  }, [open, currentPath, fetchFolders]);

  const navigateTo = (prefix: string) => {
    setBrowsePath(prefix);
    fetchFolders(prefix);
  };

  const goUp = () => {
    const parts = browsePath.replace(/\/$/, "").split("/").filter(Boolean);
    parts.pop();
    const parent = parts.length ? parts.join("/") + "/" : "";
    navigateTo(safeRootPath && !parent.startsWith(safeRootPath) ? safeRootPath : parent);
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    // Guard against accidental double-submits (Enter key + button) which
    // would fire two create-folder requests back-to-back.
    if (isCreating) return;
    const folderPath = browsePath + newFolderName.trim() + "/";
    setIsCreating(true);
    setCreateError(null);
    try {
      await createFolder(folderPath, destination.destinationId);
      setNewFolderName("");
      setShowNewFolder(false);
      fetchFolders(browsePath);
    } catch (err) {
      console.error("Failed to create folder", err);
      setCreateError(
        (err as Error)?.message || t("uploadPortals.pathBrowser.createFolderFailed"),
      );
    } finally {
      setIsCreating(false);
    }
  };

  const breadcrumbParts = browsePath.split("/").filter(Boolean);
  const isAtRoot = browsePath === safeRootPath || browsePath === "";

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("uploadPortals.pathBrowser.browseDestination")}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
          <IconButton size="small" onClick={goUp} disabled={isAtRoot}>
            <ArrowUpwardIcon fontSize="small" />
          </IconButton>
          <Breadcrumbs sx={{ flex: 1 }}>
            <Typography
              variant="body2"
              sx={{ cursor: "pointer" }}
              onClick={() => navigateTo(safeRootPath)}
            >
              root
            </Typography>
            {breadcrumbParts.map((part, i) => (
              <Typography
                key={i}
                variant="body2"
                sx={{ cursor: "pointer" }}
                onClick={() => navigateTo(breadcrumbParts.slice(0, i + 1).join("/") + "/")}
              >
                {part}
              </Typography>
            ))}
          </Breadcrumbs>
          {destination.allowFolderCreation && (
            <IconButton size="small" onClick={() => setShowNewFolder(true)}>
              <CreateNewFolderIcon fontSize="small" />
            </IconButton>
          )}
        </Box>

        {showNewFolder && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5, mb: 1 }}>
            <Box sx={{ display: "flex", gap: 1 }}>
              <TextField
                size="small"
                placeholder={t("uploadPortals.pathBrowser.folderName")}
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                autoFocus
                disabled={isCreating}
                onKeyDown={(e) => e.key === "Enter" && handleCreateFolder()}
              />
              <Button size="small" onClick={handleCreateFolder} disabled={isCreating}>
                {t("uploadPortals.pathBrowser.create")}
              </Button>
              <Button
                size="small"
                onClick={() => {
                  setShowNewFolder(false);
                  setCreateError(null);
                }}
                disabled={isCreating}
              >
                {t("uploadPortals.pathBrowser.cancel")}
              </Button>
            </Box>
            {createError && (
              <Typography variant="caption" color="error">
                {createError}
              </Typography>
            )}
          </Box>
        )}

        {loading ? (
          <Box sx={{ textAlign: "center", py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : folders.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
            {t("uploadPortals.pathBrowser.noSubfolders")}
          </Typography>
        ) : (
          <List dense>
            {folders.map((f) => (
              <ListItemButton key={f.prefix} onClick={() => navigateTo(f.prefix)}>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <FolderIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={f.name} />
              </ListItemButton>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => onPathSelect(browsePath)}>
          Select
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PortalPathBrowser;
