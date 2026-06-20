import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useNavigate, useParams } from "react-router";
import { useTranslation } from "react-i18next";

import { useCreateTemplate, useGetTemplate, useUpdateTemplate } from "@/api/hooks/useTemplates";
import type { PortalTemplate } from "@/api/types/api.types";

import { usePortalEditorStore } from "../stores/usePortalEditorStore";
import PortalEditorSidebar from "../components/editor/PortalEditorSidebar";
import PortalEditorPreview from "../components/editor/PortalEditorPreview";

/**
 * TemplateEditorPage
 *
 * Create/edit a reusable portal Template (full structure snapshot —
 * Requirements 17.1, 17.9). Reuses the existing portal editor surface:
 * `PortalEditorSidebar` (structure + appearance authoring sections) and
 * `PortalEditorPreview`, both backed by the shared `usePortalEditorStore`.
 *
 * Edit flow (Requirement 17.9 — load → modify → save back):
 *   - `useGetTemplate(id)` fetches the full snapshot.
 *   - `store.initializeFromSources({ template })` seeds the editor structure
 *     (`pages`, `metadataFields`, `destinations` incl. `connectorId` +
 *     `pageNumber`, access settings, limits) and appearance by deep-cloned
 *     snapshot (Property 11 — no live link to the source template object).
 *   - On save, `store.buildTemplatePayload(name, description, themeId)`
 *     serializes the FULL structure (NO passphrase — Requirement 17.7) and
 *     PUTs via `useUpdateTemplate`. The backend re-runs
 *     `_validate_portal_structure` and rejects an invalid template with 400.
 *
 * Create flow seeds editor defaults via `store.initialize()`; the admin
 * builds the structure from scratch, then POSTs via `useCreateTemplate`.
 *
 * Template-level identity (`name`, `description`, `themeId`) is held in local
 * state — it is not part of the portal structure the store models — and the
 * portal `slug`/`passphrase` fields on the shared sidebar are simply ignored
 * by `buildTemplatePayload` (templates carry neither).
 *
 * Routes:
 *   - /settings/upload-portals/templates/new        → create
 *   - /settings/upload-portals/templates/:id/edit   → edit
 */
const TemplateEditorPage: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isCreateMode = !id || id === "new";

  const templateQuery = useGetTemplate(isCreateMode ? "" : (id ?? ""));
  const template = templateQuery.data?.data as PortalTemplate | undefined;

  const initialize = usePortalEditorStore((s) => s.initialize);
  const initializeFromSources = usePortalEditorStore((s) => s.initializeFromSources);
  const buildTemplatePayload = usePortalEditorStore((s) => s.buildTemplatePayload);
  const activeSection = usePortalEditorStore((s) => s.activeSection);
  const setActiveSection = usePortalEditorStore((s) => s.setActiveSection);
  const previewMode = usePortalEditorStore((s) => s.previewMode);
  const setPreviewMode = usePortalEditorStore((s) => s.setPreviewMode);

  const createTemplate = useCreateTemplate();
  const updateTemplate = useUpdateTemplate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [themeId, setThemeId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  useEffect(() => {
    if (isCreateMode) {
      initialize();
      return;
    }
    if (template) {
      initializeFromSources({ template });
      setName(template.name ?? "");
      setDescription(template.description ?? "");
      setThemeId(template.themeId);
    }
  }, [isCreateMode, template, initialize, initializeFromSources]);

  const isSaving = createTemplate.isPending || updateTemplate.isPending;
  const trimmedName = name.trim();
  const isSaveDisabled = trimmedName.length === 0 || isSaving;

  const handleBack = () => navigate("/settings/upload-portals/templates");

  const handleSave = async () => {
    if (trimmedName.length === 0) {
      setToast({ open: true, message: "Template name is required.", severity: "error" });
      return;
    }
    const payload = buildTemplatePayload(trimmedName, description.trim() || undefined, themeId);
    try {
      if (isCreateMode) {
        await createTemplate.mutateAsync(payload);
      } else {
        await updateTemplate.mutateAsync({ id: id as string, data: payload });
      }
      setToast({ open: true, message: "Template saved.", severity: "success" });
      navigate("/settings/upload-portals/templates");
    } catch (error) {
      // The backend rejects an invalid structure with a 400; surface it.
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Failed to save template. Check that the page structure is valid.";
      setToast({ open: true, message, severity: "error" });
    }
  };

  const showLoading = !isCreateMode && templateQuery.isLoading;
  const showError = !isCreateMode && templateQuery.isError;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* Toolbar: back, name/description, save */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={2}
        sx={{
          minHeight: 56,
          flexShrink: 0,
          px: 2,
          py: 1,
          borderBottom: 1,
          borderColor: "divider",
          backgroundColor: "background.paper",
        }}
      >
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} size="small">
          Templates
        </Button>
        <TextField
          label="Template name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          size="small"
          required
          sx={{ minWidth: 220 }}
        />
        <TextField
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          size="small"
          sx={{ flex: 1, minWidth: 0 }}
        />
        <Button variant="contained" size="small" onClick={handleSave} disabled={isSaveDisabled}>
          {isSaving ? "Saving…" : "Save Template"}
        </Button>
      </Stack>

      {showError ? (
        <Box
          sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", p: 4 }}
        >
          <Stack spacing={2} alignItems="center">
            <Typography variant="h6">{t("uploadPortals.templates.editorLoadError")}</Typography>
            <Button variant="outlined" onClick={handleBack}>
              Back to templates
            </Button>
          </Stack>
        </Box>
      ) : showLoading ? (
        <Box
          sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", p: 4 }}
        >
          <CircularProgress />
        </Box>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "row", flex: 1, minHeight: 0 }}>
          <Box
            sx={{
              width: 360,
              minWidth: 360,
              flexShrink: 0,
              borderRight: 1,
              borderColor: "divider",
              backgroundColor: "background.paper",
            }}
          >
            <PortalEditorSidebar activeSection={activeSection} onSectionChange={setActiveSection} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <PortalEditorPreview previewMode={previewMode} onPreviewModeChange={setPreviewMode} />
          </Box>
        </Box>
      )}

      <Snackbar
        open={toast.open}
        autoHideDuration={6000}
        onClose={() => setToast((p) => ({ ...p, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          onClose={() => setToast((p) => ({ ...p, open: false }))}
          severity={toast.severity}
          variant="filled"
          sx={{ width: "100%" }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TemplateEditorPage;
