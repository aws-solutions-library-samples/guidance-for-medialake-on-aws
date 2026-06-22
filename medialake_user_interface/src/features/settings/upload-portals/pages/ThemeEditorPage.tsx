import React, { useEffect, useMemo, useState } from "react";
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

import { useCreateTheme, useGetTheme, useUpdateTheme } from "@/api/hooks/useThemes";
import type { PortalTheme } from "@/api/types/api.types";

import { usePortalEditorStore } from "../stores/usePortalEditorStore";
import AppearanceSection from "../components/editor/sections/AppearanceSection";
import TypographySection from "../components/editor/sections/TypographySection";
import LayoutSection from "../components/editor/sections/LayoutSection";
import PortalPreviewRenderer from "../components/editor/PortalPreviewRenderer";
import {
  PREVIEW_MOCK_DESTINATIONS,
  PREVIEW_MOCK_METADATA_FIELDS,
} from "../constants/previewMockData";

/**
 * ThemeEditorPage
 *
 * Create/edit a reusable appearance Theme. A Theme is appearance-only
 * (Requirement 16.1), so this editor reuses the EXISTING appearance-authoring
 * sections — `AppearanceSection` (colors + mode), `TypographySection`, and
 * `LayoutSection` — which all mutate the shared `usePortalEditorStore`
 * `appearance` slice directly. The live `PortalPreviewRenderer` shows the
 * look against mock content.
 *
 * Save serializes the editor appearance through `store.buildThemePayload`
 * (appearance only — no structure) and POSTs/PUTs via `useCreateTheme` /
 * `useUpdateTheme`.
 *
 * Routes:
 *   - /settings/upload-portals/themes/new        → create
 *   - /settings/upload-portals/themes/:id/edit   → edit
 *
 * Note on the shared singleton store: like the portal editor and its
 * `?duplicate=` flow, this page seeds the singleton editor store on mount via
 * `store.initialize`. The store's `appearance` slice is the single source of
 * truth the appearance sections read/write.
 */
const ThemeEditorPage: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isCreateMode = !id || id === "new";

  const themeQuery = useGetTheme(isCreateMode ? "" : (id ?? ""));
  const theme = themeQuery.data?.data as PortalTheme | undefined;

  const initialize = usePortalEditorStore((s) => s.initialize);
  const appearance = usePortalEditorStore((s) => s.appearance);
  const buildThemePayload = usePortalEditorStore((s) => s.buildThemePayload);

  const createTheme = useCreateTheme();
  const updateTheme = useUpdateTheme();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [toast, setToast] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  // Seed the editor store. In create mode seed defaults; in edit mode seed the
  // theme's appearance (merged onto DEFAULT by `initialize`).
  useEffect(() => {
    if (isCreateMode) {
      initialize();
      return;
    }
    if (theme) {
      initialize({ appearance: theme.appearance });
      setName(theme.name ?? "");
      setDescription(theme.description ?? "");
    }
  }, [isCreateMode, theme, initialize]);

  const previewPortalData = useMemo(
    () => ({
      name: name || "Theme preview",
      metadataFields: PREVIEW_MOCK_METADATA_FIELDS,
      destinations: PREVIEW_MOCK_DESTINATIONS,
    }),
    [name]
  );

  const isSaving = createTheme.isPending || updateTheme.isPending;
  const trimmedName = name.trim();
  const isSaveDisabled = trimmedName.length === 0 || isSaving;

  const handleBack = () => navigate("/settings/upload-portals/themes");

  const handleSave = async () => {
    if (trimmedName.length === 0) {
      setToast({ open: true, message: "Theme name is required.", severity: "error" });
      return;
    }
    const payload = buildThemePayload(trimmedName, description.trim() || undefined);
    try {
      if (isCreateMode) {
        await createTheme.mutateAsync(payload);
      } else {
        await updateTheme.mutateAsync({ id: id as string, data: payload });
      }
      setToast({ open: true, message: "Theme saved.", severity: "success" });
      navigate("/settings/upload-portals/themes");
    } catch (error) {
      const message =
        error instanceof Error && error.message ? error.message : "Failed to save theme.";
      setToast({ open: true, message, severity: "error" });
    }
  };

  const showLoading = !isCreateMode && themeQuery.isLoading;
  const showError = !isCreateMode && themeQuery.isError;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* Toolbar */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{
          height: 56,
          minHeight: 56,
          flexShrink: 0,
          px: 2,
          borderBottom: 1,
          borderColor: "divider",
          backgroundColor: "background.paper",
        }}
      >
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack} size="small">
          Themes
        </Button>
        <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: 500 }} noWrap>
          {isCreateMode ? "New Theme" : name || "Edit Theme"}
        </Typography>
        <Button variant="contained" size="small" onClick={handleSave} disabled={isSaveDisabled}>
          {isSaving ? "Saving…" : "Save Theme"}
        </Button>
      </Stack>

      {showError ? (
        <Box
          sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", p: 4 }}
        >
          <Stack spacing={2} alignItems="center">
            <Typography variant="h6">{t("uploadPortals.themes.editorLoadError")}</Typography>
            <Button variant="outlined" onClick={handleBack}>
              Back to themes
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
          {/* Left: name/description + appearance authoring controls */}
          <Box
            sx={{
              width: 360,
              minWidth: 360,
              flexShrink: 0,
              borderRight: 1,
              borderColor: "divider",
              backgroundColor: "background.paper",
              overflowY: "auto",
              p: 2,
            }}
          >
            <Stack spacing={2}>
              <TextField
                label="Theme name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                size="small"
                required
                fullWidth
              />
              <TextField
                label="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                size="small"
                fullWidth
                multiline
                minRows={2}
              />

              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Colors
                </Typography>
                <AppearanceSection />
              </Box>

              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Typography
                </Typography>
                <TypographySection />
              </Box>

              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Layout
                </Typography>
                <LayoutSection />
              </Box>
            </Stack>
          </Box>

          {/* Right: live preview */}
          <Box
            aria-hidden="true"
            sx={{
              flex: 1,
              minWidth: 0,
              overflow: "auto",
              p: 3,
              display: "flex",
              justifyContent: "center",
              alignItems: "flex-start",
            }}
          >
            <Box sx={{ width: "100%", maxWidth: 680 }}>
              <PortalPreviewRenderer appearance={appearance} portalData={previewPortalData} />
            </Box>
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

export default ThemeEditorPage;
