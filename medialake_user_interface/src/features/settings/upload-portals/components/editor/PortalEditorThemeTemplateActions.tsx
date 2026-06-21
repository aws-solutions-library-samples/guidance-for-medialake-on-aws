import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PaletteIcon from "@mui/icons-material/Palette";
import SaveAltIcon from "@mui/icons-material/SaveAlt";

import { useCreateTheme, useGetTheme, useListThemes } from "@/api/hooks/useThemes";
import { useCreateTemplate } from "@/api/hooks/useTemplates";
import type { PortalTheme } from "@/api/types/api.types";

import { usePortalEditorStore } from "../../stores/usePortalEditorStore";

/**
 * PortalEditorThemeTemplateActions
 *
 * Toolbar controls added in task 17.3 for the portal editor:
 *
 *   - "Apply theme" — pick a saved Theme and call `store.applyTheme(theme)`,
 *     which replaces ONLY the editor `appearance` (structure untouched —
 *     Requirement 16.7). The full theme (with its `appearance`) is fetched
 *     via `useGetTheme` because the list response omits `appearance`.
 *   - "Save as Theme" — prompt for a name/description, serialize the current
 *     appearance via `store.buildThemePayload` (appearance only), and POST via
 *     `useCreateTheme` (Requirement 16.4 create).
 *   - "Save as Template" — prompt for a name/description, serialize the full
 *     structure via `store.buildTemplatePayload` (NO passphrase —
 *     Requirement 17.7), and POST via `useCreateTemplate` (Requirement 17.2
 *     create).
 *
 * Self-contained so `PortalEditorToolbar` only needs to render it in a slot.
 */
export interface PortalEditorThemeTemplateActionsProps {
  /** Surface a result message to the parent (reuses its snackbar). */
  onNotify?: (message: string, severity: "success" | "error") => void;
}

type SaveMode = "theme" | "template" | null;

const PortalEditorThemeTemplateActions: React.FC<PortalEditorThemeTemplateActionsProps> = ({
  onNotify,
}) => {
  const { t } = useTranslation();
  const applyTheme = usePortalEditorStore((s) => s.applyTheme);
  const buildThemePayload = usePortalEditorStore((s) => s.buildThemePayload);
  const buildTemplatePayload = usePortalEditorStore((s) => s.buildTemplatePayload);
  const themeIdFromStore = usePortalEditorStore(
    (s) => (s.portalData?.themeId as string | undefined) ?? undefined
  );

  const themesQuery = useListThemes();
  const themes = themesQuery.data?.data ?? [];

  const createTheme = useCreateTheme();
  const createTemplate = useCreateTemplate();

  // ---- Save menu ----
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

  // ---- Apply theme picker ----
  const [applyOpen, setApplyOpen] = useState(false);
  const [pendingThemeId, setPendingThemeId] = useState<string>("");
  // Fetch the full theme (with appearance) once one is picked.
  const pendingThemeQuery = useGetTheme(pendingThemeId);

  useEffect(() => {
    if (!pendingThemeId) return;
    const fullTheme = pendingThemeQuery.data?.data as PortalTheme | undefined;
    if (fullTheme && fullTheme.themeId === pendingThemeId) {
      applyTheme(fullTheme);
      onNotify?.(`Applied theme "${fullTheme.name}".`, "success");
      setPendingThemeId("");
      setApplyOpen(false);
    }
  }, [pendingThemeId, pendingThemeQuery.data, applyTheme, onNotify]);

  // ---- Save-as dialog ----
  const [saveMode, setSaveMode] = useState<SaveMode>(null);
  const [saveName, setSaveName] = useState("");
  const [saveDescription, setSaveDescription] = useState("");

  const openSaveDialog = (mode: Exclude<SaveMode, null>) => {
    setMenuAnchor(null);
    setSaveMode(mode);
    setSaveName("");
    setSaveDescription("");
  };
  const closeSaveDialog = () => setSaveMode(null);

  const isSavePending = createTheme.isPending || createTemplate.isPending;
  const trimmedName = saveName.trim();

  const handleConfirmSave = async () => {
    if (trimmedName.length === 0) return;
    const description = saveDescription.trim() || undefined;
    try {
      if (saveMode === "theme") {
        await createTheme.mutateAsync(buildThemePayload(trimmedName, description));
        onNotify?.(`Saved theme "${trimmedName}".`, "success");
      } else if (saveMode === "template") {
        await createTemplate.mutateAsync(
          buildTemplatePayload(trimmedName, description, themeIdFromStore)
        );
        onNotify?.(`Saved template "${trimmedName}".`, "success");
      }
      setSaveMode(null);
    } catch (error) {
      const message = error instanceof Error && error.message ? error.message : "Failed to save.";
      onNotify?.(message, "error");
    }
  };

  return (
    <>
      <Button
        variant="text"
        size="small"
        startIcon={<PaletteIcon fontSize="small" />}
        onClick={() => setApplyOpen(true)}
      >
        Apply theme
      </Button>
      <Button
        variant="text"
        size="small"
        startIcon={<SaveAltIcon fontSize="small" />}
        onClick={(e) => setMenuAnchor(e.currentTarget)}
        aria-haspopup="menu"
      >
        {t("uploadPortals.themeTemplateActions.saveAs")}
      </Button>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
        <MenuItem onClick={() => openSaveDialog("template")}>
          {t("uploadPortals.themeTemplateActions.saveAsTemplate")}
        </MenuItem>
        <MenuItem onClick={() => openSaveDialog("theme")}>
          {t("uploadPortals.themeTemplateActions.saveAsTheme")}
        </MenuItem>
      </Menu>

      {/* Apply theme picker */}
      <Dialog open={applyOpen} onClose={() => setApplyOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("uploadPortals.themeTemplateActions.applyTheme")}</DialogTitle>
        <DialogContent dividers>
          {themes.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No themes available. Save the current appearance as a theme first.
            </Typography>
          ) : (
            <List disablePadding>
              {themes.map((theme) => (
                <ListItemButton
                  key={theme.themeId}
                  selected={pendingThemeId === theme.themeId}
                  onClick={() => setPendingThemeId(theme.themeId)}
                >
                  <ListItemText primary={theme.name} secondary={theme.description || undefined} />
                </ListItemButton>
              ))}
            </List>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
            Applying a theme replaces the portal&apos;s appearance only. The page structure stays
            the same.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApplyOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Save-as dialog */}
      <Dialog open={saveMode !== null} onClose={closeSaveDialog} fullWidth maxWidth="xs">
        <DialogTitle>{saveMode === "theme" ? "Save as Theme" : "Save as Template"}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              size="small"
              required
              autoFocus
              fullWidth
            />
            <TextField
              label="Description"
              value={saveDescription}
              onChange={(e) => setSaveDescription(e.target.value)}
              size="small"
              fullWidth
              multiline
              minRows={2}
            />
            <Typography variant="caption" color="text.secondary">
              {saveMode === "theme"
                ? "A theme saves the appearance only (colors, typography, layout, branding, content styling)."
                : "A template saves the full portal structure (pages, fields, destinations, access settings, limits) and appearance. Passphrases are never saved."}
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeSaveDialog}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleConfirmSave}
            disabled={trimmedName.length === 0 || isSavePending}
          >
            {isSavePending ? "Saving…" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default PortalEditorThemeTemplateActions;
