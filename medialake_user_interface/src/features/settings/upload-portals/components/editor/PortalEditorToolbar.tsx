import React from "react";
import { Box, Button, IconButton, Stack, Tooltip, Typography } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";

/**
 * Props for {@link PortalEditorToolbar}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces" exactly so later
 * tasks (5.8, 5.11, 5.12, 5.13, 5.19) can supply real handlers without
 * reshaping the component API.
 */
export interface PortalEditorToolbarProps {
  portalName: string;
  isCreateMode: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onPublish: () => void;
  onPreviewInNewTab: () => void;
  onBack: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
}

/**
 * PortalEditorToolbar
 *
 * Phase-1 scaffold of the sticky top toolbar for the portal visual editor.
 *
 * Layout (56px tall, horizontally flex):
 *   ┌──────────┬──────────────────────────────┬────────────────────────────┐
 *   │ [Back]   │ Breadcrumb  ● (dirty dot)    │ [Preview] [Save] [Publish] │
 *   └──────────┴──────────────────────────────┴────────────────────────────┘
 *
 * Behavior honored in this scaffold:
 *   - Back: renders as an `IconButton` wired to `onBack`.
 *   - Breadcrumb text: "New Portal" in create mode, else `portalName` or
 *     "Untitled Portal" fallback.
 *   - Dirty indicator: small "●" dot shown only when `isDirty === true`. // i18n-ignore
 *   - Preview button: calls `onPreviewInNewTab`; disabled in create mode
 *     (no public URL to open yet) per Requirement 10.15.
 *   - Save: disabled when `!isDirty || isSaving` (Requirement 10.2).
 *   - Publish: disabled only while `isSaving` (Publish may flip
 *     `isActive=true` even on a clean portal).
 *
 * Real save/publish logic and validation are wired by tasks 5.8 / 5.11 /
 * 5.12 / 5.13 / 5.19; this scaffold simply forwards to the handler props.
 */
const PortalEditorToolbar: React.FC<PortalEditorToolbarProps> = ({
  portalName,
  isCreateMode,
  isDirty,
  isSaving,
  onSave,
  onPublish,
  onPreviewInNewTab,
  onBack,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
}) => {
  const breadcrumbText = isCreateMode ? "New Portal" : portalName || "Untitled Portal";

  const isSaveDisabled = !isDirty || isSaving;
  const isPublishDisabled = isSaving;
  // Preview-in-new-tab has no target until the portal is saved at least once.
  const isPreviewDisabled = isCreateMode;

  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1}
      role="toolbar"
      aria-label="Editor actions"
      sx={{
        height: 56,
        minHeight: 56,
        flexShrink: 0,
        px: 2,
      }}
    >
      {/* Left: Back */}
      {/* i18n-ignore */}
      <Tooltip title="Back to portals">
        <IconButton onClick={onBack} size="small" aria-label="Back to portals">
          <ArrowBackIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      {/* Middle: breadcrumb + dirty indicator */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ flex: 1, minWidth: 0, ml: 1 }}>
        <Typography variant="subtitle1" noWrap sx={{ fontWeight: 500 }} title={breadcrumbText}>
          {breadcrumbText}
        </Typography>
        {/*
         * Dirty indicator wrapped in an `aria-live="polite"` container so
         * screen readers announce "Unsaved changes" when the flag flips
         * on (Requirement 16.18). The inner span carries the actual
         * accessible name; the outer Box is the live region. Kept empty
         * when `!isDirty` so the region has no content to announce until
         * the user starts editing.
         */}
        <Box aria-live="polite" sx={{ display: "inline-flex", alignItems: "center" }}>
          {isDirty && (
            <Box
              component="span"
              aria-label="Unsaved changes"
              title="Unsaved changes" // i18n-ignore
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: "warning.main",
                flexShrink: 0,
              }}
            />
          )}
        </Box>
      </Stack>

      {/* Right: Undo, Redo, Preview, Save, Publish */}
      <Stack direction="row" alignItems="center" spacing={1}>
        {/* i18n-ignore */}
        <Tooltip title="Undo (Ctrl+Z)">
          <span>
            <IconButton onClick={onUndo} disabled={!canUndo} size="small" aria-label="Undo">
              <UndoIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        {/* i18n-ignore */}
        <Tooltip title="Redo (Ctrl+Shift+Z)">
          <span>
            <IconButton onClick={onRedo} disabled={!canRedo} size="small" aria-label="Redo">
              <RedoIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip
          title={isPreviewDisabled ? "Save the portal first to preview" : ""}
          disableHoverListener={!isPreviewDisabled}
        >
          <span>
            <Button
              variant="text"
              size="small"
              startIcon={<OpenInNewIcon fontSize="small" />}
              onClick={onPreviewInNewTab}
              disabled={isPreviewDisabled}
            >
              Preview
            </Button>
          </span>
        </Tooltip>
        <Button variant="outlined" size="small" onClick={onSave} disabled={isSaveDisabled}>
          Save
        </Button>
        <Button variant="contained" size="small" onClick={onPublish} disabled={isPublishDisabled}>
          Publish
        </Button>
      </Stack>
    </Stack>
  );
};

export { PortalEditorToolbar };
export default PortalEditorToolbar;
